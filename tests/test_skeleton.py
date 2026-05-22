from pathlib import Path

from banong_radio import __version__
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
from banong_radio.runtime import generate_music_with_fallback, is_process_alive
from banong_radio.tts import DEFAULT_VOICE


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_is_process_alive_rejects_empty_pid() -> None:
    assert is_process_alive(None) is False
    assert is_process_alive("") is False
    assert is_process_alive(-1) is False


def test_default_voice_is_chinese() -> None:
    assert DEFAULT_VOICE == "zh-CN-YunJianNeural"


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


def test_ace_step_payload_uses_live_demo_models() -> None:
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
            "result": '[{"file": "/v1/audio?path=%2Ftmp%2Fdemo.mp3", "status": 1}]',
        }
    )

    assert result["file"].endswith("demo.mp3")


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
