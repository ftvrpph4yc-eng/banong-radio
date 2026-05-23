"""Background fallback player for the Jianya local radio runtime."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
from pathlib import Path

from banong_radio.runtime import (
    ensure_playable_assets,
    now_iso,
    write_status,
)


RUNNING = True


def handle_signal(signum: int, frame: object) -> None:
    global RUNNING
    RUNNING = False


def play_manifest(manifest_path: Path, *, once: bool = False) -> None:
    segments = ensure_playable_assets(manifest_path)
    if not segments:
        write_status(mode="idle", error="empty manifest", stopped_at=now_iso())
        return

    index = 0
    while RUNNING and (not once or index < len(segments)):
        segment = segments[index % len(segments)]
        segment_metadata = segment.get("metadata", {})
        current_label = segment.get("label", segment.get("id", "unknown"))
        next_segment = segments[(index + 1) % len(segments)]
        next_label = next_segment.get("label", next_segment.get("id", "unknown"))
        playback_path = Path(segment.get("playback_path", segment["fallback_path"]))

        write_status(
            mode="playing",
            current_segment=current_label,
            next_segment=next_label,
            playlist_index=index % len(segments),
            playlist_total=len(segments),
            music_prompt=segment.get("music_prompt", ""),
            source=segment.get("playback_source", "fallback"),
            current_path=str(playback_path),
            tts_path=segment.get("tts_path", ""),
            requested_source=segment.get("source", ""),
            cache_key=segment_metadata.get("cache_key", ""),
            content_provider=segment_metadata.get("provider", ""),
            slot_type=segment_metadata.get("slot_type", ""),
            asset_error=segment.get("asset_error", ""),
        )

        proc = subprocess.Popen(["afplay", str(playback_path)])
        while RUNNING and proc.poll() is None:
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                continue
        if not RUNNING and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        index += 1

    write_status(mode="idle", current_segment="", next_segment="", stopped_at=now_iso())


def main() -> None:
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    try:
        play_manifest(Path(args.manifest), once=args.once)
    except Exception as exc:
        write_status(mode="error", error=str(exc), stopped_at=now_iso())
        raise


if __name__ == "__main__":
    main()
