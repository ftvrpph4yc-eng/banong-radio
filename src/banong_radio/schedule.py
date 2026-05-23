"""Daily radio schedule planning above the local audio runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as local_date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

from banong_radio.agent_contracts import ensure_runtime_guardrails
from banong_radio.domain import BroadcastPlan, MediaSegment
from banong_radio.text_flow import DEFAULT_FALLBACK_ROOT


DAILY_12H_PRESET = "daily_12h"
SCHEDULE_START = "07:00"
SCHEDULE_END = "19:00"
GENERATION_TIME = "05:30"
PREFETCH_WINDOW_MINUTES = 120
LOCAL_FALLBACK_PROVIDER = "local_fallback"

GENERATED_PROVIDERS = {"podcast_api", "tts_api"}
AUTHORIZED_CATALOG_PROVIDERS = {
    "music_catalog",
    "opera_catalog",
    "audiobook_catalog",
}
MANIFEST_SAFE_LICENSES = {"authorized", "generated", "local_fallback"}


@dataclass(frozen=True)
class ContentAsset:
    """Resolved audio or script asset for one schedule slot."""

    asset_id: str
    title: str
    asset_type: str
    provider: str
    duration: int
    cache_key: str
    license_status: str
    renderable: bool = True
    fallback_for: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def manifest_safe(self) -> bool:
        return self.license_status in MANIFEST_SAFE_LICENSES

    def to_mapping(self) -> dict[str, Any]:
        payload = {
            "id": self.asset_id,
            "title": self.title,
            "type": self.asset_type,
            "provider": self.provider,
            "duration": self.duration,
            "cache_key": self.cache_key,
            "license_status": self.license_status,
            "renderable": self.renderable,
            "metadata": dict(self.metadata),
        }
        if self.fallback_for:
            payload["fallback_for"] = self.fallback_for
        return payload


@dataclass(frozen=True)
class ProgramSlot:
    """One block in the 07:00-19:00 daily radio schedule."""

    slot_id: str
    start_time: str
    end_time: str
    title: str
    slot_type: str
    content_shape: str
    primary_provider: str
    refresh_policy: str
    asset: ContentAsset
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> int:
        return (_time_to_minutes(self.end_time) - _time_to_minutes(self.start_time)) * 60

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.slot_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "title": self.title,
            "slot_type": self.slot_type,
            "content_shape": self.content_shape,
            "primary_provider": self.primary_provider,
            "refresh_policy": self.refresh_policy,
            "asset": self.asset.to_mapping(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DailySchedule:
    """A full-day program plan plus cache and provider policy."""

    schedule_id: str
    date: str | None
    place: str
    preset: str
    start_time: str
    end_time: str
    generation_time: str
    prefetch_window_minutes: int
    slots: tuple[ProgramSlot, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> int:
        return sum(slot.duration for slot in self.slots)

    @property
    def fallback_slot_count(self) -> int:
        return sum(1 for slot in self.slots if slot.asset.provider == LOCAL_FALLBACK_PROVIDER)

    def validate(self) -> None:
        if self.preset != DAILY_12H_PRESET:
            raise ValueError(f"unsupported schedule preset: {self.preset}")
        if not self.slots:
            raise ValueError("daily schedule requires at least one slot")
        if self.start_time != self.slots[0].start_time:
            raise ValueError("daily schedule has wrong start time")
        if self.end_time != self.slots[-1].end_time:
            raise ValueError("daily schedule has wrong end time")
        expected_start = self.start_time
        for slot in self.slots:
            if slot.start_time != expected_start:
                raise ValueError(f"daily schedule has a gap or overlap before {slot.slot_id}")
            if slot.asset.duration != slot.duration:
                raise ValueError(f"slot asset duration mismatch: {slot.slot_id}")
            expected_start = slot.end_time
        if self.total_duration != 12 * 60 * 60:
            raise ValueError("daily schedule must cover exactly 12 hours")

    def to_mapping(self) -> dict[str, Any]:
        self.validate()
        return {
            "id": self.schedule_id,
            "date": self.date,
            "place": self.place,
            "preset": self.preset,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration": self.total_duration,
            "generation_time": self.generation_time,
            "prefetch_window_minutes": self.prefetch_window_minutes,
            "fallback_slot_count": self.fallback_slot_count,
            "slots": [slot.to_mapping() for slot in self.slots],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class _SlotTemplate:
    slot_id: str
    start_time: str
    end_time: str
    title: str
    slot_type: str
    content_shape: str
    primary_provider: str
    refresh_policy: str = "daily_fixed"


DAILY_12H_SLOT_TEMPLATES: tuple[_SlotTemplate, ...] = (
    _SlotTemplate("opening-briefing", "07:00", "07:15", "开台与今日三件事", "village_info", "天气、农忙、村务、交通", "tts_api", "daily_update"),
    _SlotTemplate("morning-music", "07:15", "08:00", "清晨陪伴音乐", "music", "轻音乐、乡村氛围音乐", "music_catalog"),
    _SlotTemplate("village-podcast", "08:00", "08:30", "今日村里事", "podcast", "双人播客，解读当天重点", "podcast_api", "daily_update"),
    _SlotTemplate("farming-service", "08:30", "09:00", "农技与办事提醒", "service", "农技、政策、村务服务", "tts_api", "daily_update"),
    _SlotTemplate("morning-opera", "09:00", "10:00", "戏曲早场", "opera", "地方戏曲、曲艺精选", "opera_catalog"),
    _SlotTemplate("hourly-news-1000", "10:00", "10:15", "整点快讯", "village_info", "村务、天气、活动更新", "tts_api", "hourly_update"),
    _SlotTemplate("audiobook-morning", "10:15", "11:00", "有声书一段", "audiobook", "乡土文学、儿童/老人友好内容", "audiobook_catalog"),
    _SlotTemplate("market-products", "11:00", "11:30", "集市与农产品", "service", "农产品、文旅、店铺、直播预告", "tts_api", "daily_update"),
    _SlotTemplate("midday-music", "11:30", "12:30", "午间音乐带", "music", "音乐 + 少量服务提醒", "music_catalog"),
    _SlotTemplate("midday-mediation", "12:30", "13:00", "午间说和", "podcast", "新村民、邻里故事、公共议题", "podcast_api", "daily_update"),
    _SlotTemplate("audiobook-afternoon", "13:00", "14:00", "午后有声书", "audiobook", "长内容低打扰陪伴", "audiobook_catalog"),
    _SlotTemplate("opera-long", "14:00", "15:00", "戏曲长段", "opera", "戏曲/评书/地方曲艺", "opera_catalog"),
    _SlotTemplate("afternoon-update", "15:00", "15:15", "午后信息更新", "village_info", "天气、农忙、安全提醒", "tts_api", "hourly_update"),
    _SlotTemplate("work-music", "15:15", "16:00", "劳作陪伴音乐", "music", "稳定背景音乐", "music_catalog"),
    _SlotTemplate("returning-youth-podcast", "16:00", "16:45", "返乡青年播客", "podcast", "文旅、农产品、创业、村庄运营", "podcast_api", "daily_update"),
    _SlotTemplate("evening-service", "16:45", "17:15", "傍晚服务台", "service", "交通、晚间活动、明日安排", "tts_api", "daily_update"),
    _SlotTemplate("evening-opera-music", "17:15", "18:00", "傍晚戏曲/音乐", "opera", "家庭收听友好内容", "opera_catalog"),
    _SlotTemplate("evening-briefing", "18:00", "18:30", "晚间村务简报", "village_info", "一天回顾 + 明日预告", "tts_api", "daily_update"),
    _SlotTemplate("closing-story", "18:30", "19:00", "收台故事", "audiobook", "乡土故事、有声书片段、结束语", "audiobook_catalog"),
)


def build_daily_schedule(
    *,
    date: str | None = None,
    place: str = "剪鸭村",
    unavailable_providers: Iterable[str] = (),
    refresh_token: str | None = None,
) -> DailySchedule:
    """Build the 07:00-19:00 schedule without calling external providers."""

    schedule_date = date or local_date.today().isoformat()
    unavailable = {provider.strip() for provider in unavailable_providers if provider.strip()}
    slots = tuple(
        _build_slot(
            template,
            date=schedule_date,
            place=place,
            unavailable_providers=unavailable,
            refresh_token=refresh_token,
        )
        for template in DAILY_12H_SLOT_TEMPLATES
    )
    schedule = DailySchedule(
        schedule_id=f"daily:{schedule_date}:{place}:{DAILY_12H_PRESET}",
        date=schedule_date,
        place=place,
        preset=DAILY_12H_PRESET,
        start_time=SCHEDULE_START,
        end_time=SCHEDULE_END,
        generation_time=GENERATION_TIME,
        prefetch_window_minutes=PREFETCH_WINDOW_MINUTES,
        slots=slots,
        metadata={
            "provider_policy": "authorized_catalog_or_generated_with_local_fallback",
            "external_api_calls": "not_called_by_schedule_planner",
            "prefetch_policy": "prefetch_next_2_hours",
            "fallback_provider": LOCAL_FALLBACK_PROVIDER,
        },
    )
    schedule.validate()
    return schedule


def write_daily_schedule(schedule: DailySchedule, output_path: Path | str) -> Path:
    output = Path(output_path)
    _write_json_atomic(output, schedule.to_mapping())
    return output


def build_daily_schedule_preview_plan(
    schedule: DailySchedule,
    *,
    fallback_root: Path | str = DEFAULT_FALLBACK_ROOT,
) -> BroadcastPlan:
    """Build a short renderable manifest that samples the daily schedule."""

    preview_segments = tuple(
        _slot_to_preview_segment(slot, fallback_root=Path(fallback_root))
        for slot in select_preview_slots(schedule)
    )
    plan = BroadcastPlan(
        plan_id=f"{schedule.schedule_id}:preview",
        title=f"{schedule.place}十二小时节目单预览",
        source="daily_schedule_preview",
        segments=preview_segments,
        metadata={
            "schedule_id": schedule.schedule_id,
            "preset": schedule.preset,
            "start_time": schedule.start_time,
            "end_time": schedule.end_time,
            "total_duration": schedule.total_duration,
            "preview_only": True,
        },
    )
    ensure_runtime_guardrails(plan)
    return plan


def write_daily_schedule_preview_manifest(
    schedule: DailySchedule,
    output_path: Path | str,
    *,
    fallback_root: Path | str = DEFAULT_FALLBACK_ROOT,
) -> Path:
    plan = build_daily_schedule_preview_plan(schedule, fallback_root=fallback_root)
    output = Path(output_path)
    payload = {
        "id": plan.plan_id,
        "title": plan.title,
        "source": plan.source,
        "metadata": dict(plan.metadata),
        "schedule": schedule.to_mapping(),
        "segments": plan.to_runtime_segments(),
    }
    _write_json_atomic(output, payload)
    return output


def select_preview_slots(schedule: DailySchedule) -> tuple[ProgramSlot, ...]:
    wanted_types = ("village_info", "podcast", "opera")
    selected: list[ProgramSlot] = []
    for slot_type in wanted_types:
        for slot in schedule.slots:
            if slot.slot_type == slot_type and slot.asset.renderable:
                selected.append(slot)
                break
    if len(selected) != len(wanted_types):
        raise ValueError("daily schedule preview requires village_info, podcast, and opera slots")
    return tuple(selected)


def _build_slot(
    template: _SlotTemplate,
    *,
    date: str | None,
    place: str,
    unavailable_providers: set[str],
    refresh_token: str | None,
) -> ProgramSlot:
    duration = (_time_to_minutes(template.end_time) - _time_to_minutes(template.start_time)) * 60
    asset = _resolve_asset(
        template,
        date=date,
        place=place,
        duration=duration,
        unavailable_providers=unavailable_providers,
        refresh_token=refresh_token,
    )
    return ProgramSlot(
        slot_id=template.slot_id,
        start_time=template.start_time,
        end_time=template.end_time,
        title=template.title,
        slot_type=template.slot_type,
        content_shape=template.content_shape,
        primary_provider=template.primary_provider,
        refresh_policy=template.refresh_policy,
        asset=asset,
        metadata={
            "prefetch_window_minutes": PREFETCH_WINDOW_MINUTES,
            "cache_scope": _cache_scope(template.refresh_policy),
        },
    )


def _resolve_asset(
    template: _SlotTemplate,
    *,
    date: str | None,
    place: str,
    duration: int,
    unavailable_providers: set[str],
    refresh_token: str | None,
) -> ContentAsset:
    provider = template.primary_provider
    if provider in unavailable_providers:
        return _fallback_asset(template, date=date, place=place, duration=duration, fallback_for=provider)

    if provider in GENERATED_PROVIDERS:
        license_status = "generated"
    elif provider in AUTHORIZED_CATALOG_PROVIDERS:
        license_status = "authorized"
    else:
        return _fallback_asset(template, date=date, place=place, duration=duration, fallback_for=provider)

    return ContentAsset(
        asset_id=f"{template.slot_id}:{provider}",
        title=template.title,
        asset_type=template.slot_type,
        provider=provider,
        duration=duration,
        cache_key=_cache_key(template, date=date, place=place, provider=provider, refresh_token=refresh_token),
        license_status=license_status,
        metadata={
            "external_call": "deferred_to_provider_adapter",
            "authorization": _authorization_note(provider),
            "content_shape": template.content_shape,
        },
    )


def _fallback_asset(
    template: _SlotTemplate,
    *,
    date: str | None,
    place: str,
    duration: int,
    fallback_for: str,
) -> ContentAsset:
    return ContentAsset(
        asset_id=f"{template.slot_id}:{LOCAL_FALLBACK_PROVIDER}",
        title=f"{template.title}（fallback）",
        asset_type=template.slot_type,
        provider=LOCAL_FALLBACK_PROVIDER,
        duration=duration,
        cache_key=_cache_key(template, date=date, place=place, provider=LOCAL_FALLBACK_PROVIDER),
        license_status="local_fallback",
        fallback_for=fallback_for,
        metadata={
            "external_call": "skipped",
            "fallback_reason": f"{fallback_for} unavailable or not authorized",
            "content_shape": template.content_shape,
        },
    )


def _slot_to_preview_segment(slot: ProgramSlot, *, fallback_root: Path) -> MediaSegment:
    asset = slot.asset
    if not asset.manifest_safe:
        raise ValueError(f"slot asset is not authorized for manifest: {slot.slot_id}")
    duration = min(slot.duration, 90)
    source_label = f"{asset.provider}:{asset.license_status}:{asset.cache_key}"
    return MediaSegment(
        segment_id=f"{DAILY_12H_PRESET}-{slot.slot_id}",
        label=slot.title,
        intro_text=_preview_intro(slot),
        music_prompt=_preview_music_prompt(slot),
        duration=duration,
        fallback_path=fallback_root / f"{DAILY_12H_PRESET}-{slot.slot_id}.mp3",
        source_label=source_label,
        metadata={
            "generated_from": "daily_schedule_preview",
            "schedule_slot_id": slot.slot_id,
            "schedule_start_time": slot.start_time,
            "schedule_end_time": slot.end_time,
            "slot_type": slot.slot_type,
            "provider": asset.provider,
            "primary_provider": slot.primary_provider,
            "license_status": asset.license_status,
            "cache_key": asset.cache_key,
            "fallback_for": asset.fallback_for or "",
            "sanitized": True,
        },
    )


def _preview_intro(slot: ProgramSlot) -> str:
    if slot.asset.provider == LOCAL_FALLBACK_PROVIDER:
        return f"{slot.start_time}，{slot.title}进入 fallback 播出，先用本地安全音频和简短播报补位。"
    return (
        f"{slot.start_time}，伴农电台进入《{slot.title}》。"
        f"本栏目采用{slot.content_shape}，来源策略是{slot.primary_provider}，"
        "音频按节目块预取缓存，播放端只接收本地 manifest。"
    )


def _preview_music_prompt(slot: ProgramSlot) -> str:
    prompts = {
        "village_info": "warm local radio bed, light percussion, clear morning service tone",
        "podcast": "gentle conversational podcast underscore, warm village atmosphere",
        "opera": "traditional Chinese opera stage ambience, respectful and calm",
        "audiobook": "soft narration bed, quiet rural evening, low distraction",
        "music": "licensed rural companion music placeholder, warm and steady",
        "service": "clear public service radio bed, concise and trustworthy",
    }
    return prompts.get(slot.slot_type, "warm rural radio bed, instrumental")


def _authorization_note(provider: str) -> str:
    if provider in AUTHORIZED_CATALOG_PROVIDERS:
        return "requires_authorized_catalog_or_commercial_api"
    if provider in GENERATED_PROVIDERS:
        return "generated_script_or_audio_without_private_source_text"
    return "local_runtime_fallback"


def _cache_key(
    template: _SlotTemplate,
    *,
    date: str | None,
    place: str,
    provider: str,
    refresh_token: str | None = None,
) -> str:
    parts = ["daily", date or "undated", place, template.slot_id, provider]
    if template.refresh_policy == "hourly_update" and refresh_token:
        parts.append(refresh_token)
    return ":".join(part.strip().replace(" ", "-") for part in parts)


def _cache_scope(refresh_policy: str) -> str:
    if refresh_policy == "hourly_update":
        return "slot_refresh"
    return "daily_slot"


def _time_to_minutes(value: str) -> int:
    hour_text, minute_text = value.split(":", 1)
    return int(hour_text) * 60 + int(minute_text)


def _write_json_atomic(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp_file:
        temp_file.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        temp_path = Path(temp_file.name)
    temp_path.replace(output)
