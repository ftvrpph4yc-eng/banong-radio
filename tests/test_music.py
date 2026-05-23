from pathlib import Path

from banong_radio.music import (
    AceStepApiError,
    AceStepMusicGenerator,
    FallbackMusicGenerator,
    MusicResult,
    ace_step_preflight,
    music_request_from_segment,
    parse_ace_step_result,
    stable_seed,
)
from banong_radio.runtime import generate_music_with_fallback


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


def test_fallback_generator_regenerates_empty_cached_file(monkeypatch, tmp_path) -> None:
    fallback_path = tmp_path / "field_future.mp3"
    fallback_path.write_bytes(b"")
    writes: list[tuple[Path, int, int]] = []

    def fake_make_fallback_audio(path: Path, frequency: int, duration: int) -> None:
        writes.append((path, frequency, duration))
        path.write_bytes(b"usable fallback mp3")

    monkeypatch.setattr(
        "banong_radio.music.make_fallback_audio",
        fake_make_fallback_audio,
    )

    request = music_request_from_segment(
        {
            "id": "field_future",
            "label": "田野未来主义",
            "music_prompt": "pastoral electronic",
            "duration": 10,
            "fallback_path": str(fallback_path),
        }
    )

    result = FallbackMusicGenerator().generate(request)

    assert result.song_path == fallback_path
    assert fallback_path.read_bytes() == b"usable fallback mp3"
    assert writes == [(fallback_path, 392, 10)]


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
    assert result.metadata["fallback_error_category"] == "ace-step-api"
    assert result.metadata["fallback_error_type"] == "AceStepApiError"
    assert result.metadata["fallback_error_message"] == "server unavailable"
    assert result.metadata["ace_step_error"] == "server unavailable"


def test_generic_music_error_gets_stable_fallback_classification() -> None:
    class FailingGenerator:
        def generate(self, request, index=0):
            raise RuntimeError("unexpected generator failure")

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
    assert result.metadata["fallback_reason"] == "music-generator-error"
    assert result.metadata["fallback_error_category"] == "music-generator"
    assert result.metadata["fallback_error_type"] == "RuntimeError"
    assert result.metadata["fallback_error_message"] == "unexpected generator failure"
