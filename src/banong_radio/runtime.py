"""Runtime helpers for the Banong Radio demo."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from banong_radio.music import (
    AceStepMusicGenerator,
    FallbackMusicGenerator,
    MusicGenerator,
    MusicRequest,
    MusicResult,
    music_request_from_segment,
)
from banong_radio.mixer import mix_voice_over_music
from banong_radio.tts import synthesize


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = Path("/Users/detroxryo/Music/BanongRadio")
CACHE_ROOT = Path("/Users/detroxryo/.cache/banong-radio")
STATUS_PATH = CACHE_ROOT / "status.json"
LOG_PATH = CACHE_ROOT / "logs/player.log"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def read_status() -> dict[str, Any]:
    status = read_json(STATUS_PATH, {})
    if not status:
        return {
            "ok": True,
            "mode": "idle",
            "status_path": str(STATUS_PATH),
            "updated_at": now_iso(),
        }
    status["ok"] = True
    status["process_alive"] = is_process_alive(status.get("pid"))
    return status


def write_status(**updates: Any) -> dict[str, Any]:
    status = read_json(STATUS_PATH, {})
    status.update(updates)
    status["updated_at"] = now_iso()
    write_json(STATUS_PATH, status)
    return status


def is_process_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ensure_fallback_assets(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = read_json(manifest_path, {"segments": []})
    segments = manifest.get("segments", [])
    if not segments:
        raise ValueError(f"manifest has no segments: {manifest_path}")

    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    for folder in ["generated", "tts", "mixed", "fallback"]:
        (ASSET_ROOT / folder).mkdir(parents=True, exist_ok=True)

    generator = select_music_generator()
    fallback = FallbackMusicGenerator()
    prepared_segments: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        segment = dict(segment)
        request = music_request_from_segment(segment)
        music = generate_music_with_fallback(generator, fallback, request, index=index)
        segment["song_path"] = str(music.song_path)
        segment["fallback_path"] = str(request.fallback_path)
        segment["music_prompt"] = music.prompt
        segment["duration"] = music.duration
        segment["music_source"] = music.metadata["source"]
        segment["music_metadata"] = music.metadata
        prepared_segments.append(segment)
    return prepared_segments


def select_music_generator() -> MusicGenerator:
    source = os.environ.get("BANONG_MUSIC_SOURCE", "fallback").strip().lower()
    if source in {"ace", "ace-step", "ace_step", "acestep"}:
        return AceStepMusicGenerator()
    return FallbackMusicGenerator()


def generate_music_with_fallback(
    generator: MusicGenerator,
    fallback: FallbackMusicGenerator,
    request: MusicRequest,
    index: int = 0,
) -> MusicResult:
    try:
        return generator.generate(request, index=index)
    except Exception as exc:
        if isinstance(generator, FallbackMusicGenerator):
            raise
        music = fallback.generate(request, index=index)
        metadata = dict(music.metadata)
        metadata["ace_step_error"] = str(exc)
        metadata["fallback_reason"] = "ace-step-error"
        return MusicResult(
            song_path=music.song_path,
            prompt=music.prompt,
            duration=music.duration,
            metadata=metadata,
        )


def ensure_playable_assets(manifest_path: Path) -> list[dict[str, Any]]:
    """Ensure every segment has fallback music and, when possible, a mixed version."""
    segments = ensure_fallback_assets(manifest_path)
    playable_segments: list[dict[str, Any]] = []

    for segment in segments:
        segment = dict(segment)
        segment_id = segment["id"]
        song_path = Path(segment.get("song_path", segment["fallback_path"]))
        intro_text = segment.get("intro_text", "")
        tts_path = ASSET_ROOT / "tts" / f"{segment_id}.mp3"
        mixed_path = ASSET_ROOT / "mixed" / f"{segment_id}.mp3"

        if intro_text:
            try:
                generated_tts, tts_source = synthesize(intro_text, tts_path)
                if generated_tts and not mixed_path.exists():
                    mix_voice_over_music(song_path, generated_tts, mixed_path)
                if mixed_path.exists():
                    segment["playback_path"] = str(mixed_path)
                    segment["playback_source"] = f"mixed:{tts_source}"
                    segment["tts_path"] = str(generated_tts)
                else:
                    segment["playback_path"] = str(song_path)
                    segment["playback_source"] = "fallback:no-mix"
            except Exception as exc:
                segment["playback_path"] = str(song_path)
                segment["playback_source"] = "fallback:tts-or-mix-error"
                segment["asset_error"] = str(exc)
        else:
            segment["playback_path"] = str(song_path)
            segment["playback_source"] = "fallback:no-script"

        playable_segments.append(segment)
    return playable_segments

def start_demo(manifest_path: Path) -> dict[str, Any]:
    status = read_status()
    if is_process_alive(status.get("pid")):
        return {
            "ok": True,
            "mode": status.get("mode", "playing"),
            "message": "demo already running",
            "pid": status["pid"],
            "status_path": str(STATUS_PATH),
        }

    segments = ensure_playable_assets(manifest_path)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_PATH.open("a")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "banong_radio.player_worker",
            "--manifest",
            str(manifest_path),
        ],
        cwd=str(PROJECT_ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "src")},
    )
    write_status(
        mode="playing",
        pid=proc.pid,
        manifest_path=str(manifest_path),
        status_path=str(STATUS_PATH),
        log_path=str(LOG_PATH),
        playlist_total=len(segments),
        current_segment="starting",
        next_segment=segments[0].get("label", segments[0].get("id", "")),
        source="mixed-or-fallback",
    )
    return {
        "ok": True,
        "mode": "playing",
        "pid": proc.pid,
        "playlist_total": len(segments),
        "status_path": str(STATUS_PATH),
        "log_path": str(LOG_PATH),
    }


def stop_demo() -> dict[str, Any]:
    status = read_status()
    pid = status.get("pid")
    stopped = False
    if is_process_alive(pid):
        os.kill(pid, signal.SIGTERM)
        stopped = True
    write_status(
        mode="idle",
        pid=None,
        current_segment="",
        next_segment="",
        source="",
        stopped_at=now_iso(),
    )
    return {
        "ok": True,
        "mode": "idle",
        "stopped": stopped,
        "status_path": str(STATUS_PATH),
    }


def generate_segment(mood: str, source: str) -> dict[str, Any]:
    status = write_status(
        requested_mood=mood,
        requested_source=source,
        next_segment=mood,
        source="fallback",
        note="Request recorded for Hermes-driven demo control; current playback loop stays conservative.",
    )
    return {
        "ok": True,
        "queued": True,
        "mood": mood,
        "source": source,
        "status_path": str(STATUS_PATH),
        "status": status,
    }
