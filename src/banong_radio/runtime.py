"""Runtime helpers for the Jianya local radio presentation path."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from banong_radio.domain import BroadcastPlan
from banong_radio.music import (
    AceStepMusicGenerator,
    FallbackMusicGenerator,
    MusicGenerator,
    MusicRequest,
    MusicResult,
    music_error_metadata,
    music_request_from_segment,
)
from banong_radio.mixer import mix_voice_over_music
from banong_radio.tts import synthesize


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = Path("/Users/detroxryo/Music/BanongRadio")
CACHE_ROOT = Path("/Users/detroxryo/.cache/banong-radio")
STATUS_PATH = CACHE_ROOT / "status.json"
LOG_PATH = CACHE_ROOT / "logs/player.log"

IDLE_PLAYBACK_FIELDS = {
    "asset_error",
    "cache_key",
    "content_source",
    "content_provider",
    "current_path",
    "music_prompt",
    "playlist_index",
    "slot_type",
    "tts_path",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def audio_file_ready(path: Path) -> bool:
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def normalize_status_payload(status: dict[str, Any]) -> dict[str, Any]:
    status = dict(status)
    if status.get("mode") == "idle":
        had_playback_source = any(
            status.get(field)
            for field in ("cache_key", "content_provider", "content_source", "slot_type")
        )
        for field in IDLE_PLAYBACK_FIELDS:
            status.pop(field, None)
        if had_playback_source:
            status.pop("requested_source", None)
        status["pid"] = None
        status["current_segment"] = ""
        status["next_segment"] = ""
        status["source"] = ""
    return status


def read_status() -> dict[str, Any]:
    status = read_json(STATUS_PATH, {})
    if not status:
        return {
            "ok": True,
            "mode": "idle",
            "pid": None,
            "status_path": str(STATUS_PATH),
            "updated_at": now_iso(),
            "process_alive": False,
        }
    status = normalize_status_payload(status)
    status["ok"] = True
    status["process_alive"] = is_process_alive(status.get("pid"))
    return status


def write_status(**updates: Any) -> dict[str, Any]:
    status = read_json(STATUS_PATH, {})
    status.update(updates)
    status = normalize_status_payload(status)
    status["updated_at"] = now_iso()
    write_json(STATUS_PATH, status)
    return status


def load_broadcast_plan(manifest_path: Path) -> BroadcastPlan:
    manifest = read_json(manifest_path, {"segments": []})
    return BroadcastPlan.from_manifest_payload(manifest, plan_id=manifest_path.stem)


def is_process_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def ensure_fallback_assets(manifest_path: Path) -> list[dict[str, Any]]:
    plan = load_broadcast_plan(manifest_path)
    segments = plan.to_runtime_segments()

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
        for field in [
            "fallback_reason",
            "fallback_error_category",
            "fallback_error_type",
        ]:
            if field in music.metadata:
                segment[field] = music.metadata[field]
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
        metadata.update(music_error_metadata(exc))
        metadata["ace_step_error"] = metadata["fallback_error_message"]
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
        music_source = str(segment.get("music_source", "music"))

        if intro_text:
            try:
                generated_tts, tts_source = synthesize(intro_text, tts_path)
                if (
                    audio_file_ready(mixed_path)
                    and not mix_cache_matches(
                        mixed_path,
                        music_path=song_path,
                        tts_path=generated_tts,
                        intro_text=intro_text,
                    )
                ):
                    mixed_path.unlink(missing_ok=True)
                    mix_cache_path(mixed_path).unlink(missing_ok=True)
                if generated_tts and not audio_file_ready(mixed_path):
                    mix_voice_over_music(song_path, generated_tts, mixed_path)
                    write_mix_cache(
                        mixed_path,
                        music_path=song_path,
                        tts_path=generated_tts,
                        intro_text=intro_text,
                        tts_source=tts_source,
                    )
                if audio_file_ready(mixed_path):
                    segment["playback_path"] = str(mixed_path)
                    segment["playback_source"] = f"mixed:{tts_source}"
                    segment["tts_path"] = str(generated_tts or "")
                else:
                    segment["playback_path"] = str(song_path)
                    segment["playback_source"] = f"{music_source}:no-mix"
            except Exception as exc:
                segment["playback_path"] = str(song_path)
                segment["playback_source"] = f"{music_source}:tts-or-mix-error"
                segment["asset_error"] = str(exc)
        else:
            segment["playback_path"] = str(song_path)
            segment["playback_source"] = f"{music_source}:no-script"

        playable_segments.append(segment)
    return playable_segments


def mix_cache_path(mixed_path: Path) -> Path:
    return mixed_path.with_suffix(".json")


def mix_cache_matches(
    mixed_path: Path,
    *,
    music_path: Path,
    tts_path: Path | None,
    intro_text: str,
) -> bool:
    if not audio_file_ready(mixed_path) or tts_path is None:
        return False
    try:
        metadata = read_json(mix_cache_path(mixed_path), {})
    except Exception:
        return False
    return metadata == mix_cache_metadata(
        music_path=music_path,
        tts_path=tts_path,
        intro_text=intro_text,
        tts_source=str(metadata.get("tts_source", "")),
    )


def write_mix_cache(
    mixed_path: Path,
    *,
    music_path: Path,
    tts_path: Path,
    intro_text: str,
    tts_source: str,
) -> None:
    write_json(
        mix_cache_path(mixed_path),
        mix_cache_metadata(
            music_path=music_path,
            tts_path=tts_path,
            intro_text=intro_text,
            tts_source=tts_source,
        ),
    )


def mix_cache_metadata(
    *,
    music_path: Path,
    tts_path: Path,
    intro_text: str,
    tts_source: str,
) -> dict[str, Any]:
    return {
        "music": audio_cache_identity(music_path),
        "tts": audio_cache_identity(tts_path),
        "intro_text": intro_text,
        "tts_source": tts_source,
    }


def audio_cache_identity(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }

def start_demo(manifest_path: Path) -> dict[str, Any]:
    status = read_status()
    if is_process_alive(status.get("pid")):
        return {
            "ok": True,
            "mode": status.get("mode", "playing"),
            "message": "radio loop already running",
            "pid": status["pid"],
            "status_path": str(STATUS_PATH),
        }

    plan = load_broadcast_plan(manifest_path)
    segments = ensure_playable_assets(manifest_path)
    command = [
        sys.executable,
        "-m",
        "banong_radio.player_worker",
        "--manifest",
        str(manifest_path),
    ]
    if plan.metadata.get("play_mode") == "once":
        command.append("--once")
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = LOG_PATH.open("a")
    proc = subprocess.Popen(
        command,
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
        note="Request recorded for Hermes-driven control; current playback loop stays conservative.",
    )
    return {
        "ok": True,
        "queued": True,
        "mood": mood,
        "source": source,
        "status_path": str(STATUS_PATH),
        "status": status,
    }
