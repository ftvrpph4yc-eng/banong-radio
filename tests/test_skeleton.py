import json
from pathlib import Path

from banong_radio import __version__
from banong_radio import cli
from banong_radio.domain import (
    BroadcastPlan,
    ContextPacket,
    RawTextItem,
    TaskBrief,
    VillageSignal,
)
from banong_radio.music import (
    AceStepApiError,
    AceStepMusicGenerator,
    FallbackMusicGenerator,
    MusicResult,
    parse_ace_step_result,
    stable_seed,
    ace_step_preflight,
    music_request_from_segment,
)
from banong_radio.runtime import (
    generate_music_with_fallback,
    is_process_alive,
    load_broadcast_plan,
    read_json,
    read_status,
    write_json,
    write_status,
)
from banong_radio.status_server import dashboard_url
from banong_radio.tts import DEFAULT_VOICE


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_is_process_alive_rejects_empty_pid() -> None:
    assert is_process_alive(None) is False
    assert is_process_alive("") is False
    assert is_process_alive(-1) is False


def test_default_voice_is_chinese() -> None:
    assert DEFAULT_VOICE == "zh-CN-YunJianNeural"


def test_manifest_is_broadcast_plan_input() -> None:
    plan = BroadcastPlan.from_manifest_payload(
        {
            "id": "demo",
            "title": "剪鸭村融媒体本地电台",
            "segments": [
                {
                    "id": "longtan_morning",
                    "label": "龙潭清晨",
                    "music_prompt": "peaceful morning",
                    "intro_text": "早上好。",
                    "duration": 18,
                    "fallback_path": "/tmp/longtan_morning.mp3",
                }
            ],
        }
    )

    assert plan.source == "manifest"
    assert plan.segments[0].segment_id == "longtan_morning"
    assert plan.to_runtime_segments()[0]["fallback_path"] == "/tmp/longtan_morning.mp3"


def test_text_flow_domain_objects_are_separate_from_radio_runtime() -> None:
    raw = RawTextItem(item_id="wx-1", source="mock-wechat", text="今晚可能下雨")
    signal = VillageSignal(
        signal_id="weather-1",
        title="天气提醒",
        summary="今晚可能下雨",
        topics=("weather",),
        urgency="normal",
    )
    packet = ContextPacket(packet_id="today", signals=(signal,), audience=("villagers",))
    brief = TaskBrief(
        task="radio",
        context_packet_id=packet.packet_id,
        intent="prepare broadcast plan",
        inputs=(raw.item_id,),
    )

    assert raw.source == "mock-wechat"
    assert packet.signals[0].title == "天气提醒"
    assert brief.task == "radio"


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


def test_music_request_preserves_source_boundary() -> None:
    request = music_request_from_segment(
        {
            "id": "siping_night",
            "label": "四坪夜晚",
            "music_prompt": "night cricket ambient",
            "duration": 18,
            "fallback_path": "/tmp/siping_night.mp3",
        }
    )

    assert request.segment_id == "siping_night"
    assert request.mood == "四坪夜晚"
    assert request.prompt == "night cricket ambient"
    assert request.duration == 18
    assert request.fallback_path == Path("/tmp/siping_night.mp3")


def test_music_result_shape_matches_solid_contract() -> None:
    result = MusicResult(
        song_path=Path("/tmp/example.mp3"),
        prompt="pastoral electronic",
        duration=18,
        metadata={"source": "fallback", "mood": "田野未来主义"},
    )

    assert result.prompt == "pastoral electronic"
    assert result.metadata["source"] == "fallback"


def test_ace_step_preflight_is_non_generating_report() -> None:
    report = ace_step_preflight()

    assert report["stage"] == "ace-step-preflight"
    assert "commands" in report
    assert "packages" in report
    assert "fallback_required" in report
    assert "recommendation" in report


def test_ace_step_payload_uses_live_presentation_models() -> None:
    request = music_request_from_segment(
        {
            "id": "longtan_morning",
            "label": "龙潭清晨",
            "music_prompt": "peaceful morning",
            "duration": 18,
            "fallback_path": "/tmp/longtan_morning.mp3",
        }
    )
    generator = AceStepMusicGenerator()

    payload = generator._payload(request, index=0)

    assert payload["model"] == "acestep-v15-turbo"
    assert payload["lm_model_path"] == "acestep-5Hz-lm-1.7B"
    assert payload["thinking"] is True
    assert payload["audio_duration"] == 18
    assert payload["audio_format"] == "mp3"


def test_parse_ace_step_result_extracts_audio_file() -> None:
    result = parse_ace_step_result(
        {
            "status": 1,
            "result": '[{"file": "/v1/audio?path=%2Ftmp%2Fsample.mp3", "status": 1}]',
        }
    )

    assert result["file"].endswith("sample.mp3")


def test_stable_seed_is_repeatable() -> None:
    assert stable_seed("siping_night", 1) == stable_seed("siping_night", 1)
    assert stable_seed("siping_night", 1) != stable_seed("siping_night", 2)


def test_ace_step_error_falls_back_to_local_music() -> None:
    class FailingGenerator:
        def generate(self, request, index=0):
            raise AceStepApiError("server unavailable")

    request = music_request_from_segment(
        {
            "id": "field_future",
            "label": "田野未来主义",
            "music_prompt": "pastoral electronic",
            "duration": 10,
            "fallback_path": "/tmp/field_future.mp3",
        }
    )

    result = generate_music_with_fallback(FailingGenerator(), FallbackMusicGenerator(), request)

    assert result.metadata["source"] == "fallback"
    assert result.metadata["fallback_reason"] == "ace-step-error"


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


def test_read_write_json_round_trip(tmp_path) -> None:
    path = tmp_path / "nested" / "payload.json"
    write_json(path, {"name": "剪鸭村融媒体", "ok": True})

    assert read_json(path, {}) == {"name": "剪鸭村融媒体", "ok": True}


def test_cli_status_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["banong-radio", "status"])
    monkeypatch.setattr(cli, "read_status", lambda: {"ok": True, "mode": "idle"})

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {"ok": True, "mode": "idle"}


def test_dashboard_url_normalizes_public_bind_hosts() -> None:
    assert dashboard_url("0.0.0.0", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("::", 8765) == "http://127.0.0.1:8765/"
    assert dashboard_url("localhost", 8765) == "http://localhost:8765/"
