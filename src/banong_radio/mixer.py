"""FFmpeg mixing helpers for the Jianya local radio runtime."""

from __future__ import annotations

import subprocess
from pathlib import Path


def duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return float(result.stdout.strip())


def mix_voice_over_music(music_path: Path, tts_path: Path, output_path: Path) -> Path:
    """Duck the music bed and place the host voice on top."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    music_duration = duration(music_path)
    fade_out_start = max(music_duration - 2.0, 0.5)
    tts_duration = duration(tts_path)
    tts_fade_out_start = max(tts_duration - 0.35, 0.1)
    filter_graph = (
        f"[0:a]volume=0.24,afade=t=in:st=0:d=1,"
        f"afade=t=out:st={fade_out_start:.3f}:d=2[music];"
        f"[1:a]volume=0.95,afade=t=in:st=0:d=0.2,"
        f"afade=t=out:st={tts_fade_out_start:.3f}:d=0.35[voice];"
        f"[music][voice]amix=inputs=2:duration=first:normalize=0,"
        f"alimiter=limit=0.86[aout]"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(music_path),
            "-i",
            str(tts_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[aout]",
            "-ar",
            "44100",
            "-ac",
            "2",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return output_path
