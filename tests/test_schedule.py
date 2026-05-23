import json
from dataclasses import replace

from banong_radio.runtime import load_broadcast_plan
from banong_radio.schedule import (
    DAILY_12H_PRESET,
    build_daily_schedule,
    build_daily_schedule_preview_plan,
    write_daily_schedule,
    write_daily_schedule_preview_manifest,
)


def test_daily_schedule_covers_twelve_hours_without_gaps() -> None:
    schedule = build_daily_schedule(date="2026-05-24")

    assert schedule.preset == DAILY_12H_PRESET
    assert schedule.start_time == "07:00"
    assert schedule.end_time == "19:00"
    assert schedule.total_duration == 12 * 60 * 60
    assert len(schedule.slots) == 19
    assert schedule.prefetch_window_minutes == 120
    assert schedule.slots[0].title == "开台与今日三件事"
    assert schedule.slots[-1].title == "收台故事"

    slot_types = {slot.slot_type for slot in schedule.slots}
    assert {"podcast", "music", "opera", "audiobook", "village_info"}.issubset(slot_types)
    for current, next_slot in zip(schedule.slots, schedule.slots[1:]):
        assert current.end_time == next_slot.start_time


def test_daily_schedule_defaults_to_a_date_for_cache_keys() -> None:
    schedule = build_daily_schedule()

    assert schedule.date
    assert schedule.date in schedule.schedule_id
    assert schedule.date in schedule.slots[0].asset.cache_key


def test_provider_failure_uses_local_fallback_without_breaking_schedule() -> None:
    schedule = build_daily_schedule(
        date="2026-05-24",
        unavailable_providers=("opera_catalog",),
    )
    opera_slots = [slot for slot in schedule.slots if slot.primary_provider == "opera_catalog"]

    assert opera_slots
    assert all(slot.asset.provider == "local_fallback" for slot in opera_slots)
    assert all(slot.asset.fallback_for == "opera_catalog" for slot in opera_slots)
    assert schedule.fallback_slot_count == len(opera_slots)
    schedule.validate()


def test_cache_keys_are_stable_and_hourly_refresh_is_scoped() -> None:
    first = build_daily_schedule(date="2026-05-24", refresh_token="weather-a")
    second = build_daily_schedule(date="2026-05-24", refresh_token="weather-a")
    refreshed = build_daily_schedule(date="2026-05-24", refresh_token="weather-b")

    first_keys = {slot.slot_id: slot.asset.cache_key for slot in first.slots}
    second_keys = {slot.slot_id: slot.asset.cache_key for slot in second.slots}
    refreshed_keys = {slot.slot_id: slot.asset.cache_key for slot in refreshed.slots}

    assert first_keys == second_keys
    assert first_keys["hourly-news-1000"] != refreshed_keys["hourly-news-1000"]
    assert first_keys["afternoon-update"] != refreshed_keys["afternoon-update"]
    assert first_keys["morning-opera"] == refreshed_keys["morning-opera"]
    assert first_keys["audiobook-afternoon"] == refreshed_keys["audiobook-afternoon"]


def test_preview_manifest_uses_three_representative_safe_slots(tmp_path) -> None:
    schedule = build_daily_schedule(date="2026-05-24")
    schedule_path = write_daily_schedule(schedule, tmp_path / "schedule.json")
    preview_path = write_daily_schedule_preview_manifest(
        schedule,
        tmp_path / "preview_manifest.json",
    )

    payload = json.loads(schedule_path.read_text(encoding="utf-8"))
    loaded = load_broadcast_plan(preview_path)

    assert payload["preset"] == "daily_12h"
    assert payload["slots"][0]["asset"]["license_status"] in {"generated", "authorized"}
    assert loaded.source == "manifest"
    assert len(loaded.segments) == 3
    assert [segment.metadata["slot_type"] for segment in loaded.segments] == [
        "village_info",
        "podcast",
        "opera",
    ]
    assert all(segment.metadata["license_status"] in {"generated", "authorized", "local_fallback"} for segment in loaded.segments)


def test_unauthorized_asset_cannot_enter_preview_manifest() -> None:
    schedule = build_daily_schedule(date="2026-05-24")
    bad_asset = replace(schedule.slots[0].asset, license_status="unknown")
    bad_slot = replace(schedule.slots[0], asset=bad_asset)
    unsafe_schedule = replace(schedule, slots=(bad_slot, *schedule.slots[1:]))

    try:
        build_daily_schedule_preview_plan(unsafe_schedule)
    except ValueError as exc:
        assert "not authorized for manifest" in str(exc)
    else:
        raise AssertionError("expected ValueError")
