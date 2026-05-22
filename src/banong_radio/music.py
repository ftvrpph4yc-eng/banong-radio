"""Music source contracts for the Jianya local radio runtime."""

from __future__ import annotations

import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class MusicRequest:
    segment_id: str
    mood: str
    prompt: str
    duration: int
    fallback_path: Path


@dataclass(frozen=True)
class MusicResult:
    song_path: Path
    prompt: str
    duration: int
    metadata: dict[str, Any]


class MusicGenerator(Protocol):
    """Generate or retrieve music for a radio segment."""

    def generate(self, request: MusicRequest, index: int = 0) -> MusicResult:
        """Return a playable music result for the request."""


class FallbackMusicGenerator:
    """Generate or reuse deterministic local fallback music."""

    def __init__(self, frequencies: list[int] | None = None) -> None:
        self.frequencies = frequencies or [392, 330, 440, 294, 349]

    def generate(self, request: MusicRequest, index: int = 0) -> MusicResult:
        if not request.fallback_path.exists():
            request.fallback_path.parent.mkdir(parents=True, exist_ok=True)
            frequency = self.frequencies[index % len(self.frequencies)]
            make_fallback_audio(request.fallback_path, frequency=frequency, duration=request.duration)

        return MusicResult(
            song_path=request.fallback_path,
            prompt=request.prompt,
            duration=request.duration,
            metadata={
                "source": "fallback",
                "mood": request.mood,
                "segment_id": request.segment_id,
            },
        )


class AceStepApiError(RuntimeError):
    """Raised when the ACE-Step API cannot produce a usable audio file."""


class AceStepApiClient:
    """Small client for the official ACE-Step REST API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8001",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._request_json("GET", "/health")

    def release_task(self, payload: dict[str, Any]) -> str:
        response = self._request_json("POST", "/release_task", payload)
        task_id = response.get("data", {}).get("task_id")
        if not task_id:
            raise AceStepApiError(f"ACE-Step release_task returned no task_id: {response}")
        return str(task_id)

    def query_result(self, task_id: str) -> dict[str, Any]:
        response = self._request_json("POST", "/query_result", {"task_id_list": [task_id]})
        tasks = response.get("data")
        if not isinstance(tasks, list) or not tasks:
            raise AceStepApiError(f"ACE-Step query_result returned no task data: {response}")
        return dict(tasks[0])

    def wait_for_result(
        self,
        task_id: str,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_task: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            task = self.query_result(task_id)
            last_task = task
            status = task.get("status")
            if status == 1:
                return parse_ace_step_result(task)
            if status == 2:
                raise AceStepApiError(f"ACE-Step task failed: {task}")
            time.sleep(poll_interval)
        raise AceStepApiError(f"ACE-Step task timed out: task_id={task_id}, last={last_task}")

    def download_audio(self, file_url: str, output_path: Path) -> Path:
        url = self._absolute_url(file_url)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                output_path.write_bytes(response.read())
        except (OSError, urllib.error.URLError) as exc:
            raise AceStepApiError(f"ACE-Step audio download failed: {exc}") from exc
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise AceStepApiError(f"ACE-Step downloaded empty audio: {output_path}")
        return output_path

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = self._headers()
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self._absolute_url(path),
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except (OSError, urllib.error.URLError) as exc:
            raise AceStepApiError(f"ACE-Step API request failed: {method} {path}: {exc}") from exc
        parsed = json.loads(body)
        if parsed.get("code") not in (None, 200):
            raise AceStepApiError(f"ACE-Step API returned error: {parsed}")
        return parsed

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _absolute_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        if path_or_url.startswith("/"):
            return f"{self.base_url}{path_or_url}"
        return f"{self.base_url}/{path_or_url}"


class AceStepMusicGenerator:
    """Generate music through ACE-Step while preserving the MusicGenerator boundary."""

    def __init__(
        self,
        client: AceStepApiClient | None = None,
        output_root: Path | None = None,
        model: str = "acestep-v15-turbo",
        lm_model: str = "acestep-5Hz-lm-1.7B",
        poll_interval: float = 2.0,
        generation_timeout: float = 600.0,
    ) -> None:
        self.client = client or AceStepApiClient()
        self.output_root = output_root or Path("/Users/detroxryo/Music/BanongRadio/generated/ace-step")
        self.model = model
        self.lm_model = lm_model
        self.poll_interval = poll_interval
        self.generation_timeout = generation_timeout

    def generate(self, request: MusicRequest, index: int = 0) -> MusicResult:
        output_path = self.output_root / f"{request.segment_id}.mp3"
        if output_path.exists() and output_path.stat().st_size > 0:
            return self._result(request, output_path, {"cached": True})

        self.client.health()
        task_id = self.client.release_task(self._payload(request, index))
        task_result = self.client.wait_for_result(
            task_id,
            poll_interval=self.poll_interval,
            timeout=self.generation_timeout,
        )
        file_url = task_result.get("file")
        if not isinstance(file_url, str) or not file_url:
            raise AceStepApiError(f"ACE-Step result did not include an audio file: {task_result}")
        self.client.download_audio(file_url, output_path)
        return self._result(request, output_path, {"task_id": task_id, "result": task_result})

    def _payload(self, request: MusicRequest, index: int) -> dict[str, Any]:
        return {
            "prompt": request.prompt,
            "lyrics": "[Instrumental]",
            "audio_duration": max(10, request.duration),
            "audio_format": "mp3",
            "model": self.model,
            "lm_model_path": self.lm_model,
            "thinking": True,
            "inference_steps": 8,
            "batch_size": 1,
            "use_random_seed": False,
            "seed": stable_seed(request.segment_id, index),
        }

    def _result(
        self,
        request: MusicRequest,
        output_path: Path,
        extra: dict[str, Any],
    ) -> MusicResult:
        metadata = {
            "source": "ace-step",
            "mood": request.mood,
            "segment_id": request.segment_id,
            "api_base_url": self.client.base_url,
            "model": self.model,
            "lm_model": self.lm_model,
        }
        metadata.update(extra)
        return MusicResult(
            song_path=output_path,
            prompt=request.prompt,
            duration=request.duration,
            metadata=metadata,
        )


def music_request_from_segment(segment: dict[str, Any]) -> MusicRequest:
    segment_id = str(segment["id"])
    return MusicRequest(
        segment_id=segment_id,
        mood=str(segment.get("label", segment_id)),
        prompt=str(segment.get("music_prompt", "")),
        duration=int(segment.get("duration", 18)),
        fallback_path=Path(segment["fallback_path"]),
    )


def parse_ace_step_result(task: dict[str, Any]) -> dict[str, Any]:
    raw_result = task.get("result")
    if isinstance(raw_result, str):
        parsed = json.loads(raw_result)
    else:
        parsed = raw_result
    if not isinstance(parsed, list) or not parsed:
        raise AceStepApiError(f"ACE-Step task result is empty: {task}")
    result = dict(parsed[0])
    if result.get("status") == 2:
        raise AceStepApiError(f"ACE-Step generated result failed: {result}")
    return result


def stable_seed(segment_id: str, index: int = 0) -> int:
    value = 0
    for character in f"{segment_id}:{index}":
        value = (value * 131 + ord(character)) % 2_147_483_647
    return value or 1


def ace_step_preflight() -> dict[str, Any]:
    """Inspect local ACE-Step readiness without generating audio."""
    command_names = ["ace-step", "acestep", "mlx-audio"]
    package_names = ["ace_step", "acestep", "mlx", "mlx_audio", "mlx_lm", "torch", "transformers"]

    commands = {name: shutil.which(name) for name in command_names}
    commands["uv"] = shutil.which("uv")
    packages = {name: importlib.util.find_spec(name) is not None for name in package_names}
    checkouts = find_ace_step_checkouts()
    checkout_runtimes = [inspect_ace_step_checkout(path, package_names) for path in checkouts]
    model_cache = inspect_ace_step_model_cache(checkouts)
    python_version = {
        "executable": sys.executable,
        "version": platform.python_version(),
        "meets_minimum": sys.version_info >= (3, 10),
    }
    checkout_has_cli = any(runtime["commands"] for runtime in checkout_runtimes)
    checkout_has_ml_runtime = any(
        runtime["packages"].get("mlx")
        or runtime["packages"].get("mlx_lm")
        or runtime["packages"].get("torch")
        for runtime in checkout_runtimes
    )

    blockers: list[str] = []
    if not python_version["meets_minimum"]:
        blockers.append("python>=3.10 is required")
    if not any(commands[name] for name in command_names) and not checkouts and not checkout_has_cli:
        blockers.append("no ACE-Step checkout or installed ACE/MLX audio CLI found")
    if not (
        packages["mlx"]
        or packages["mlx_audio"]
        or packages["mlx_lm"]
        or packages["torch"]
        or checkout_has_ml_runtime
    ):
        blockers.append("no local ML runtime package found")
    if not model_cache["ready"]:
        blockers.append("no matching ACE-Step 1.5 turbo + 1.7B model cache found")

    return {
        "ok": not blockers,
        "stage": "ace-step-preflight",
        "python": python_version,
        "commands": commands,
        "packages": packages,
        "checkout_runtimes": checkout_runtimes,
        "cache_roots": {
            name: str(path) for name, path in model_cache["roots"].items()
        },
        "cache_matches": model_cache["matches"],
        "model_cache": model_cache["models"],
        "checkouts": [str(path) for path in checkouts],
        "recommendation": ace_step_recommendation(),
        "blockers": blockers,
        "fallback_required": bool(blockers),
    }


def ace_step_recommendation() -> dict[str, Any]:
    avoid_for_live = [
        {
            "model": "acestep-v15-xl-*",
            "reason": "higher quality but official guidance says XL needs offload below 20GB, which is risky on a 16GB live presentation machine",
        },
        {
            "model": "acestep-5Hz-lm-4B",
            "reason": "best quality tier is aimed at >=24GB; use later only for offline A/B if needed",
        },
    ]
    return {
        "primary": {
            "runtime": "official ACE-Step 1.5 macOS MLX backend",
            "dit": "acestep-v15-turbo",
            "lm": "acestep-5Hz-lm-1.7B",
            "reason": "best balance for Mac mini M4 16GB live presentation: faster than sft/xl, still keeps the 1.7B planner for prompt structure",
        },
        "fallback": {
            "runtime": "existing local fallback mp3 assets",
            "reason": "must remain active until preflight ok=true and a generated segment passes listening test",
        },
        "avoid_for_live_demo": avoid_for_live,
        "avoid_for_live_presentation": avoid_for_live,
        "optional_experiment": {
            "runtime": "mlx-community/ACE-Step1.5-MLX-4bit",
            "reason": "compact 4-bit MLX weights are promising, but official ACE-Step macOS scripts/API are the primary integration path for this runtime",
        },
    }


def find_ace_step_checkouts() -> list[Path]:
    candidates = [
        Path("/Users/detroxryo/Dev/Sandbox/ACE-Step-1.5"),
        Path("/Users/detroxryo/Dev/Sandbox/ACE-Step"),
        Path("/Users/detroxryo/Dev/ACE-Step-1.5"),
        Path("/Users/detroxryo/Dev/ACE-Step"),
    ]
    return [path for path in candidates if (path / "pyproject.toml").exists()]


def inspect_ace_step_checkout(path: Path, package_names: list[str]) -> dict[str, Any]:
    """Inspect an independent ACE-Step checkout and its private uv environment."""
    venv_bin = path / ".venv" / "bin"
    python = venv_bin / "python"
    commands = {
        name: str(venv_bin / name)
        for name in ["acestep", "acestep-api", "acestep-download"]
        if (venv_bin / name).exists()
    }
    launchers = [
        str(path / name)
        for name in ["start_api_server_macos.sh", "start_gradio_ui_macos.sh"]
        if (path / name).exists()
    ]
    packages = (
        inspect_python_packages(python, package_names)
        if python.exists()
        else {name: False for name in package_names}
    )

    return {
        "path": str(path),
        "python": str(python) if python.exists() else None,
        "commands": commands,
        "launchers": launchers,
        "packages": packages,
        "env": read_ace_step_env(path / ".env"),
    }


def inspect_python_packages(python: Path, package_names: list[str]) -> dict[str, bool]:
    """Return import availability for packages inside another Python environment."""
    script = (
        "import importlib.util, json; "
        f"names={package_names!r}; "
        "print(json.dumps({name: importlib.util.find_spec(name) is not None for name in names}))"
    )
    try:
        result = subprocess.run(
            [str(python), "-c", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {name: False for name in package_names}
    return json.loads(result.stdout)


def read_ace_step_env(path: Path) -> dict[str, str]:
    """Read non-secret ACE-Step runtime settings from a dotenv-style file."""
    if not path.exists():
        return {}

    visible_keys = {
        "ACESTEP_CONFIG_PATH",
        "ACESTEP_LM_MODEL_PATH",
        "ACESTEP_LM_BACKEND",
        "ACESTEP_INIT_LLM",
        "ACESTEP_CHECKPOINTS_DIR",
        "ACESTEP_DOWNLOAD_SOURCE",
    }
    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in visible_keys:
            values[key] = value.strip().strip('"').strip("'")
    return values


def inspect_ace_step_model_cache(checkouts: list[Path]) -> dict[str, Any]:
    """Inspect model cache roots for the selected ACE-Step 1.5 live presentation models."""
    roots: dict[str, Path] = {
        "ace_step": Path.home() / ".cache" / "ace-step" / "checkpoints",
        "huggingface": Path.home() / ".cache" / "huggingface",
    }
    for checkout in checkouts:
        roots[f"checkout:{checkout.name}"] = checkout / "checkpoints"
        env = read_ace_step_env(checkout / ".env")
        env_root = env.get("ACESTEP_CHECKPOINTS_DIR")
        if env_root:
            roots[f"env:{checkout.name}"] = Path(env_root).expanduser()

    required = ["acestep-v15-turbo", "acestep-5Hz-lm-1.7B", "vae"]
    found: dict[str, list[str]] = {name: [] for name in required}
    matches: dict[str, list[str]] = {}
    for name, root in roots.items():
        matches[name] = [str(path) for path in find_cache_matches(root, ["ace", "step", "mlx"])]
        for model_name in required:
            model_path = root / model_name
            if model_cache_dir_ready(model_path):
                found[model_name].append(str(model_path))

    return {
        "ready": all(found[name] for name in required),
        "roots": roots,
        "matches": matches,
        "models": {
            "required": required,
            "found": found,
        },
    }


def model_cache_dir_ready(path: Path) -> bool:
    """Return true when a model directory contains at least one expected weight file."""
    if not path.exists():
        return False
    weight_names = [
        "model.safetensors",
        "model.safetensors.index.json",
        "pytorch_model.bin",
        "pytorch_model.bin.index.json",
        "diffusion_pytorch_model.safetensors",
        "diffusion_pytorch_model.safetensors.index.json",
    ]
    return any((path / name).exists() for name in weight_names)


def find_cache_matches(root: Path, terms: list[str], max_results: int = 30) -> list[Path]:
    if not root.exists():
        return []

    lowered_terms = [term.lower() for term in terms]
    matches: list[Path] = []
    for path in root.rglob("*"):
        lowered = path.name.lower()
        if any(term in lowered for term in lowered_terms):
            matches.append(path)
            if len(matches) >= max_results:
                break
    return matches


def make_fallback_audio(path: Path, frequency: int, duration: int) -> None:
    fade_out_start = max(duration - 2, 1)
    filter_graph = (
        f"[0:a]volume=0.16,afade=t=in:st=0:d=1,"
        f"afade=t=out:st={fade_out_start}:d=2[tone];"
        f"[1:a]volume=0.035[noise];"
        f"[tone][noise]amix=inputs=2:duration=shortest,"
        f"alimiter=limit=0.8[aout]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:duration={duration}:amplitude=0.08",
            "-filter_complex",
            filter_graph,
            "-map",
            "[aout]",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
