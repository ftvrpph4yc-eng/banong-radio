"""Speech synthesis adapters for the Banong Radio demo."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


DEFAULT_VOICE = "zh-CN-YunJianNeural"


def synthesize(text: str, output_path: Path, voice: str = DEFAULT_VOICE) -> tuple[Path | None, str]:
    """Generate speech audio, preferring edge-tts and falling back to macOS say."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        return output_path, "cache"

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
    return output_path, "macos-say"
