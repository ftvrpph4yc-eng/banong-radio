import signal
from pathlib import Path

from banong_radio.runtime import (
    is_process_alive,
    ensure_fallback_assets,
    load_broadcast_plan,
    read_json,
    read_status,
    write_json,
    write_status,
)
from banong_radio.text_flow import build_demo_feed_broadcast_plan, write_broadcast_plan_manifest


def test_is_process_alive_rejects_empty_pid() -> None:
    assert is_process_alive(None) is False
    assert is_process_alive("") is False
    assert is_process_alive(-1) is False


def test_load_broadcast_plan_from_manifest(tmp_path) -> None:
    manifest = tmp_path / "demo_manifest.json"
    write_json(
        manifest,
        {
            "segments": [
                {
                    "id": "field_future",
                    "label": "田野未来主义",
                    "music_prompt": "pastoral electronic",
                    "intro_text": "新的节拍。",
                    "duration": 18,
                    "fallback_path": "/tmp/field_future.mp3",
                }
            ]
        },
    )

    plan = load_broadcast_plan(manifest)

    assert plan.plan_id == "demo_manifest"
    assert plan.segments[0].label == "田野未来主义"


def test_load_broadcast_plan_rejects_empty_manifest(tmp_path) -> None:
    manifest = tmp_path / "empty_manifest.json"
    write_json(manifest, {"segments": []})

    try:
        load_broadcast_plan(manifest)
    except ValueError as exc:
        assert str(exc) == "broadcast plan has no segments: empty_manifest"
    else:
        raise AssertionError("expected ValueError")


def test_status_read_write_uses_json_shape(tmp_path, monkeypatch) -> None:
    status_path = tmp_path / "status.json"
    monkeypatch.setattr("banong_radio.runtime.STATUS_PATH", status_path)

    status = write_status(mode="playing", current_segment="龙潭清晨")
    assert status["mode"] == "playing"
    assert status["current_segment"] == "龙潭清晨"
    assert status["updated_at"]

    loaded = read_status()
    assert loaded["ok"] is True
    assert loaded["mode"] == "playing"
    assert loaded["process_alive"] is False


def test_idle_status_drops_stale_playback_evidence(tmp_path, monkeypatch) -> None:
    status_path = tmp_path / "status.json"
    monkeypatch.setattr("banong_radio.runtime.STATUS_PATH", status_path)

    write_status(
        mode="playing",
        pid=12345,
        current_segment="龙潭清晨",
        next_segment="四坪夜晚",
        playlist_index=0,
        playlist_total=3,
        music_prompt="peaceful morning",
        source="mixed:macos-say",
        current_path="/tmp/longtan_morning.mp3",
        tts_path="/tmp/longtan_morning_tts.mp3",
        asset_error="",
        status_path=str(status_path),
    )

    idle = write_status(mode="idle", stopped_at="2026-05-22T20:00:00+08:00")

    assert idle["mode"] == "idle"
    assert idle["pid"] is None
    assert idle["current_segment"] == ""
    assert idle["next_segment"] == ""
    assert idle["source"] == ""
    assert idle["playlist_total"] == 3
    assert idle["status_path"] == str(status_path)
    assert "current_path" not in idle
    assert "tts_path" not in idle
    assert "music_prompt" not in idle
    assert "asset_error" not in idle
    assert "playlist_index" not in idle


def test_read_status_normalizes_existing_idle_payload(tmp_path, monkeypatch) -> None:
    status_path = tmp_path / "status.json"
    monkeypatch.setattr("banong_radio.runtime.STATUS_PATH", status_path)
    write_json(
        status_path,
        {
            "mode": "idle",
            "pid": 12345,
            "current_segment": "龙潭清晨",
            "next_segment": "四坪夜晚",
            "music_prompt": "peaceful morning",
            "current_path": "/tmp/longtan_morning.mp3",
            "tts_path": "/tmp/longtan_morning_tts.mp3",
        },
    )

    status = read_status()

    assert status["ok"] is True
    assert status["mode"] == "idle"
    assert status["pid"] is None
    assert status["process_alive"] is False
    assert status["current_segment"] == ""
    assert status["next_segment"] == ""
    assert "current_path" not in status
    assert "tts_path" not in status
    assert "music_prompt" not in status


def test_read_write_json_round_trip(tmp_path) -> None:
    path = tmp_path / "nested" / "payload.json"
    write_json(path, {"name": "剪鸭村融媒体", "ok": True})

    assert read_json(path, {}) == {"name": "剪鸭村融媒体", "ok": True}


def test_runtime_segment_exposes_stable_fallback_error_fields(monkeypatch, tmp_path) -> None:
    from banong_radio import runtime
    from banong_radio.music import AceStepApiError, FallbackMusicGenerator

    class FailingGenerator:
        def generate(self, request, index=0):
            raise AceStepApiError("server unavailable")

    manifest = tmp_path / "demo_manifest.json"
    fallback_path = tmp_path / "fallback.mp3"
    write_json(
        manifest,
        {
            "segments": [
                {
                    "id": "field_future",
                    "label": "田野未来主义",
                    "music_prompt": "pastoral electronic",
                    "intro_text": "",
                    "duration": 18,
                    "fallback_path": str(fallback_path),
                }
            ]
        },
    )
    fallback_path.parent.mkdir(parents=True, exist_ok=True)
    fallback_path.write_bytes(b"fake mp3")
    monkeypatch.setattr(runtime, "select_music_generator", lambda: FailingGenerator())
    monkeypatch.setattr(
        FallbackMusicGenerator,
        "generate",
        lambda self, request, index=0: runtime.MusicResult(
            song_path=request.fallback_path,
            prompt=request.prompt,
            duration=request.duration,
            metadata={
                "source": "fallback",
                "mood": request.mood,
                "segment_id": request.segment_id,
            },
        ),
    )

    segments = runtime.ensure_fallback_assets(manifest)

    assert segments[0]["music_source"] == "fallback"
    assert segments[0]["fallback_reason"] == "ace-step-error"
    assert segments[0]["fallback_error_category"] == "ace-step-api"
    assert segments[0]["fallback_error_type"] == "AceStepApiError"
    assert segments[0]["music_metadata"]["fallback_error_message"] == "server unavailable"


def test_generated_demo_feed_manifest_enters_runtime_fallback(monkeypatch, tmp_path) -> None:
    from banong_radio import runtime
    from banong_radio.music import FallbackMusicGenerator

    plan = build_demo_feed_broadcast_plan(
        "demo/village_feed.json",
        date="2026-05-23",
        fallback_root=tmp_path / "fallback",
    )
    manifest = write_broadcast_plan_manifest(plan, tmp_path / "demo_feed_manifest.json")

    monkeypatch.setattr(
        FallbackMusicGenerator,
        "generate",
        lambda self, request, index=0: runtime.MusicResult(
            song_path=request.fallback_path,
            prompt=request.prompt,
            duration=request.duration,
            metadata={
                "source": "fallback",
                "mood": request.mood,
                "segment_id": request.segment_id,
            },
        ),
    )

    loaded = load_broadcast_plan(manifest)
    segments = ensure_fallback_assets(manifest)

    assert loaded.source == "manifest"
    assert loaded.metadata["generated_by"] == "RadioPlanner"
    assert len(segments) == 5
    assert sorted({segment["music_source"] for segment in segments}) == ["fallback"]
    assert segments[0]["id"] == "radio-public-notice-001"


def test_start_demo_returns_existing_process_without_rebuilding_assets(monkeypatch) -> None:
    from banong_radio import runtime

    monkeypatch.setattr(
        runtime,
        "read_status",
        lambda: {"mode": "playing", "pid": 12345},
    )
    monkeypatch.setattr(runtime, "is_process_alive", lambda pid: pid == 12345)
    monkeypatch.setattr(
        runtime,
        "ensure_playable_assets",
        lambda manifest_path: (_ for _ in ()).throw(AssertionError("unexpected asset rebuild")),
    )

    result = runtime.start_demo(Path("demo/demo_manifest.json"))

    assert result["ok"] is True
    assert result["mode"] == "playing"
    assert result["message"] == "radio loop already running"
    assert result["pid"] == 12345


def test_stop_demo_terminates_alive_process_and_writes_idle(monkeypatch) -> None:
    from banong_radio import runtime

    killed: list[tuple[int, int]] = []
    written: list[dict[str, object]] = []

    monkeypatch.setattr(runtime, "read_status", lambda: {"mode": "playing", "pid": 12345})
    monkeypatch.setattr(runtime, "is_process_alive", lambda pid: pid == 12345)
    monkeypatch.setattr(runtime.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(runtime, "write_status", lambda **updates: written.append(updates) or updates)

    result = runtime.stop_demo()

    assert result["ok"] is True
    assert result["mode"] == "idle"
    assert result["stopped"] is True
    assert killed == [(12345, signal.SIGTERM)]
    assert written[0]["mode"] == "idle"
    assert written[0]["pid"] is None
