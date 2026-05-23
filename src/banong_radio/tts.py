"""Speech synthesis adapters for the Jianya local radio runtime."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


DEFAULT_VOICE = "zh-CN-YunJianNeural"


def synthesize(text: str, output_path: Path, voice: str = DEFAULT_VOICE) -> tuple[Path | None, str]:
    """Generate speech audio, preferring edge-tts and falling back to macOS say."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if _audio_file_ready(output_path) and _cache_matches(output_path, text=text, voice=voice):
        return output_path, "cache"
    output_path.unlink(missing_ok=True)
    _cache_path(output_path).unlink(missing_ok=True)

    if shutil.which("edge-tts"):
        result = subprocess.run(
            [
                "edge-tts",
                "-v",
                voice,
                "-t",
                text,
                "--write-media",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0 and output_path.exists():
            _write_cache(output_path, text=text, voice=voice, source="edge-tts")
            return output_path, "edge-tts"

    say_path = shutil.which("say")
    if not say_path:
        return None, "unavailable"

    aiff_path = output_path.with_suffix(".aiff")
    subprocess.run(
        [say_path, "-o", str(aiff_path), text],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(aiff_path),
            "-ar",
            "44100",
            "-ac",
            "2",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    aiff_path.unlink(missing_ok=True)
    _write_cache(output_path, text=text, voice=voice, source="macos-say")
    return output_path, "macos-say"


def _audio_file_ready(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def _cache_path(output_path: Path) -> Path:
    return output_path.with_suffix(".json")


def _cache_matches(output_path: Path, *, text: str, voice: str) -> bool:
    try:
        payload = json.loads(_cache_path(output_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("text") == text and payload.get("voice") == voice


def _write_cache(output_path: Path, *, text: str, voice: str, source: str) -> None:
    _cache_path(output_path).write_text(
        json.dumps(
            {
                "text": text,
                "voice": voice,
                "source": source,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
