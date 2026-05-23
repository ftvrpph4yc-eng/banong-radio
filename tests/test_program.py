import json
from dataclasses import replace
from pathlib import Path

from banong_radio.program import (
    ProgramPreset,
    build_broadcast_program_from_feed,
    get_program_preset,
    write_broadcast_program_manifest,
)
from banong_radio.runtime import load_broadcast_plan


DEMO_FEED_PATH = Path("demo/village_feed.json")


def test_program_presets_have_independent_time_budgets() -> None:
    trailer = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )
    briefing = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="briefing_3m",
        date="2026-05-23",
    )
    show = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="show_2h",
        date="2026-05-23",
    )

    assert 45 <= trailer.target_duration <= 60
    assert trailer.actual_duration == trailer.target_duration
    assert len(trailer.segments) == 1
    assert trailer.segments[0].duration == trailer.target_duration
    assert trailer.segments[0].segment_id == "trailer_45s-integrated-program"
    assert "trailer_45s-integrated-program" in str(trailer.segments[0].fallback_path)
    assert trailer.metadata["play_mode"] == "once"
    assert briefing.target_duration == 180
    assert briefing.actual_duration == 180
    assert len(briefing.segments) == 5
    assert briefing.metadata["play_mode"] == "loop"
    assert show.target_duration == 7200
    assert show.actual_duration == 7200
    assert get_program_preset("daily_12h").target_duration == 43200


def test_program_manifest_remains_runtime_compatible(tmp_path) -> None:
    program = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )
    output = write_broadcast_program_manifest(program, tmp_path / "broadcast.json")

    loaded = load_broadcast_plan(output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert loaded.plan_id == program.program_id
    assert loaded.source == "manifest"
    assert len(loaded.segments) == 1
    assert payload["program"]["preset"]["name"] == "trailer_45s"
    assert 45 <= payload["metadata"]["target_duration"] <= 60
    assert payload["metadata"]["play_mode"] == "once"


def test_trailer_script_is_fused_and_not_repetitive() -> None:
    program = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )
    script = program.segments[0].intro_text

    assert script.count("剪鸭村") == 0
    assert script.count("伴农电台") == 1
    assert "道路养护" in script
    assert "阵雨" in script
    assert "老粮仓" in script
    assert "夏收志愿排班" in script
    assert "村干部 A" not in script
    assert "返乡青年 B" not in script


def test_program_preset_distributes_non_even_duration_budget() -> None:
    preset = ProgramPreset(
        name="custom",
        title="custom",
        target_duration=46,
        description="custom budget",
    )

    assert preset.segment_durations(5) == (10, 9, 9, 9, 9)
    assert sum(preset.segment_durations(5)) == 46


def test_program_manifest_write_runs_runtime_guardrails(tmp_path) -> None:
    program = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )
    unsafe_segment = replace(
        program.segments[0],
        intro_text="请联系 13812345678",
    )
    unsafe_program = replace(
        program,
        segments=(unsafe_segment, *program.segments[1:]),
    )

    try:
        write_broadcast_program_manifest(unsafe_program, tmp_path / "unsafe.json")
    except ValueError as exc:
        assert "broadcast plan failed runtime guardrails" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_unknown_program_preset_is_rejected() -> None:
    try:
        get_program_preset("fixed_45s_only")
    except ValueError as exc:
        assert "unknown program preset" in str(exc)
        assert "trailer_45s" in str(exc)
        assert "show_2h" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_program_title_uses_product_language() -> None:
    program = build_broadcast_program_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
    )

    assert "Demo" not in program.title
    assert "预告片" in program.title


def test_daily_schedule_preset_is_not_rendered_as_one_broadcast_program() -> None:
    try:
        build_broadcast_program_from_feed(
            DEMO_FEED_PATH,
            preset_name="daily_12h",
        )
    except ValueError as exc:
        assert "use plan-daily-schedule" in str(exc)
    else:
        raise AssertionError("expected ValueError")
