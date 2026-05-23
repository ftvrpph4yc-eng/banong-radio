"""Speech synthesis adapters for the Jianya local radio runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_VOICE = "zh-CN-YunJianNeural"
DEFAULT_SAY_VOICE = "Tingting"
DEFAULT_SAY_RATE = "170"


def synthesize(text: str, output_path: Path, voice: str = DEFAULT_VOICE) -> tuple[Path | None, str]:
    """Generate speech audio, preferring edge-tts and falling back to macOS say."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    say_voice = os.environ.get("BANONG_SAY_VOICE", DEFAULT_SAY_VOICE)
    say_rate = os.environ.get("BANONG_SAY_RATE", DEFAULT_SAY_RATE)
    if _audio_file_ready(output_path) and _cache_matches(
        output_path,
        text=text,
        voice=voice,
        say_voice=say_voice,
        say_rate=say_rate,
    ):
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
        [
            say_path,
            "-v",
            say_voice,
            "-r",
            say_rate,
            "-o",
            str(aiff_path),
            text,
        ],
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
    _write_cache(
        output_path,
        text=text,
        voice=voice,
        source="macos-say",
        say_voice=say_voice,
        say_rate=say_rate,
    )
    return output_path, "macos-say"


def _audio_file_ready(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def _cache_path(output_path: Path) -> Path:
    return output_path.with_suffix(".json")


def _cache_matches(
    output_path: Path,
    *,
    text: str,
    voice: str,
    say_voice: str,
    say_rate: str,
) -> bool:
    try:
        payload = json.loads(_cache_path(output_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload.get("text") != text or payload.get("voice") != voice:
        return False
    if payload.get("source") == "edge-tts":
        return True
    if payload.get("source") == "macos-say":
        return payload.get("say_voice") == say_voice and payload.get("say_rate") == say_rate
    return False


def _write_cache(
    output_path: Path,
    *,
    text: str,
    voice: str,
    source: str,
    say_voice: str = "",
    say_rate: str = "",
) -> None:
    _cache_path(output_path).write_text(
        json.dumps(
            {
                "text": text,
                "voice": voice,
                "source": source,
                "say_voice": say_voice,
                "say_rate": say_rate,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
