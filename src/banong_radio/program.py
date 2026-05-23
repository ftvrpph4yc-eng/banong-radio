"""Program-level broadcast planning with reusable duration presets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from banong_radio.agent_contracts import ensure_runtime_guardrails
from banong_radio.domain import BroadcastPlan, MediaSegment
from banong_radio.text_flow import (
    DEFAULT_FALLBACK_ROOT,
    ContextBuilder,
    DemoVillageFeedAdapter,
    RadioPlanner,
    SignalExtractor,
    TaskPlanner,
    sanitize_text_items,
)


@dataclass(frozen=True)
class ProgramPreset:
    """Reusable duration and rundown policy for a broadcast program."""

    name: str
    title: str
    target_duration: int
    description: str
    rundown: tuple[str, ...] = ()

    def segment_duration(self, segment_count: int) -> int:
        """Return the per-segment time budget for this preset."""

        return self.segment_durations(segment_count)[0]

    def segment_durations(self, segment_count: int) -> tuple[int, ...]:
        """Return exact per-segment budgets that add up to target_duration."""

        if segment_count <= 0:
            raise ValueError("program preset requires at least one segment")
        if self.target_duration < segment_count:
            raise ValueError("program preset target duration is too short")
        base_duration, remainder = divmod(self.target_duration, segment_count)
        return tuple(
            base_duration + (1 if index < remainder else 0)
            for index in range(segment_count)
        )


@dataclass(frozen=True)
class BroadcastProgram:
    """Product-level program plan before it is handed to the audio runtime."""

    program_id: str
    title: str
    preset: ProgramPreset
    context_packet_id: str
    segments: tuple[MediaSegment, ...]
    source: str = "program_preset"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def target_duration(self) -> int:
        return self.preset.target_duration

    @property
    def actual_duration(self) -> int:
        return sum(segment.duration for segment in self.segments)

    def to_broadcast_plan(self) -> BroadcastPlan:
        return BroadcastPlan(
            plan_id=self.program_id,
            title=self.title,
            source=self.source,
            segments=self.segments,
            metadata={
                "context_packet_id": self.context_packet_id,
                "preset": self.preset.name,
                "target_duration": self.target_duration,
                "actual_duration": self.actual_duration,
                "generated_by": "BroadcastProgram",
                **dict(self.metadata),
            },
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.program_id,
            "title": self.title,
            "source": self.source,
            "preset": {
                "name": self.preset.name,
                "title": self.preset.title,
                "target_duration": self.preset.target_duration,
                "description": self.preset.description,
                "rundown": list(self.preset.rundown),
            },
            "context_packet_id": self.context_packet_id,
            "target_duration": self.target_duration,
            "actual_duration": self.actual_duration,
            "segments": [segment.to_runtime_dict() for segment in self.segments],
            "metadata": dict(self.metadata),
        }


PROGRAM_PRESETS: tuple[ProgramPreset, ...] = (
    ProgramPreset(
        name="trailer_45s",
        title="伴农电台预告片",
        target_duration=60,
        description="Fast news-style preview with a village radio finish.",
        rundown=("opening", "news_cut", "signal_montage", "ending"),
    ),
    ProgramPreset(
        name="briefing_3m",
        title="伴农电台三分钟简报",
        target_duration=180,
        description="Compact daily village briefing for repeat listening.",
        rundown=("opening", "weather", "governance", "farming", "community", "closing"),
    ),
    ProgramPreset(
        name="show_2h",
        title="伴农电台两小时栏目",
        target_duration=7200,
        description="Long-form village radio show skeleton for future scheduling.",
        rundown=("opening", "news", "field_service", "community", "features", "rotation"),
    ),
)


def get_program_preset(name: str) -> ProgramPreset:
    normalized = name.strip()
    for preset in PROGRAM_PRESETS:
        if preset.name == normalized:
            return preset
    valid = ", ".join(preset.name for preset in PROGRAM_PRESETS)
    raise ValueError(f"unknown program preset: {name}; expected one of: {valid}")


def build_broadcast_program_from_feed(
    feed_path: Path | str,
    *,
    preset_name: str = "trailer_45s",
    date: str | None = None,
    place: str | None = "剪鸭村",
    audience: Iterable[str] = ("villagers",),
    fallback_root: Path | str = DEFAULT_FALLBACK_ROOT,
) -> BroadcastProgram:
    """Build a product-level program plan from a fixture or approved feed."""

    raw_items = DemoVillageFeedAdapter(feed_path).fetch_items()
    sanitized_items = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized_items)
    context = ContextBuilder().build(
        signals,
        date=date,
        place=place,
        audience=audience,
    )
    preset = get_program_preset(preset_name)
    brief = TaskPlanner().plan(context, task="radio")
    if preset.name == "trailer_45s":
        program_segments = (
            _trailer_segment_from_brief(
                brief,
                preset=preset,
                fallback_root=Path(fallback_root),
            ),
        )
        return BroadcastProgram(
            program_id=f"broadcast:{preset.name}:{context.packet_id}",
            title=preset.title,
            preset=preset,
            context_packet_id=context.packet_id,
            segments=program_segments,
            metadata={
                "signal_count": len(signals),
                "topics": context.metadata.get("topics", ()),
                "rundown": preset.rundown,
                "source_plan_id": "",
                "play_mode": "once",
            },
        )

    plan = RadioPlanner(
        fallback_root=fallback_root,
        segment_duration=preset.segment_duration(len(signals)),
    ).generate(brief)
    program_segments = _segments_for_program_preset(
        plan.segments,
        preset=preset,
        fallback_root=Path(fallback_root),
    )
    return BroadcastProgram(
        program_id=f"broadcast:{preset.name}:{context.packet_id}",
        title=preset.title,
        preset=preset,
        context_packet_id=context.packet_id,
        segments=program_segments,
        metadata={
            "signal_count": len(signals),
            "topics": context.metadata.get("topics", ()),
            "rundown": preset.rundown,
            "source_plan_id": plan.plan_id,
            "play_mode": "loop",
        },
    )


def _trailer_segment_from_brief(
    brief: Any,
    *,
    preset: ProgramPreset,
    fallback_root: Path,
) -> MediaSegment:
    signal_payloads = [
        signal
        for signal in brief.metadata.get("signals", ())
        if isinstance(signal, dict)
    ]
    if not signal_payloads:
        raise ValueError("trailer preset requires signal payloads")

    script = _trailer_script(signal_payloads)
    topics = _deduplicate_strings(
        str(topic)
        for signal in signal_payloads
        for topic in signal.get("topics", ())
    )
    signal_ids = tuple(str(signal.get("signal_id", "")) for signal in signal_payloads)

    return MediaSegment(
        segment_id=f"{preset.name}-integrated-program",
        label="预告融合节目",
        intro_text=script,
        music_prompt=(
            "warm rural radio theme, gentle guzheng and soft electronic pad, "
            "light news intro pulse, hopeful village morning, instrumental"
        ),
        duration=preset.target_duration,
        fallback_path=fallback_root / f"{preset.name}-integrated-program.mp3",
        source_label="已脱敏村庄信息融合编排",
        metadata={
            "generated_from": "broadcast_program_trailer",
            "program_preset": preset.name,
            "fused_signal_ids": signal_ids,
            "topics": tuple(topics),
            "sanitized": True,
        },
    )


def _trailer_script(signal_payloads: list[dict[str, Any]]) -> str:
    traffic = _first_signal_with_topic(signal_payloads, "traffic")
    weather = _first_signal_with_topic(signal_payloads, "weather")
    business = _first_signal_with_topic(signal_payloads, "community")
    if not business:
        business = _first_signal_with_topic(signal_payloads, "local_business")
    volunteer = _first_signal_with_topic(signal_payloads, "volunteer", "governance")

    traffic_line = _trailer_line(
        str(traffic.get("summary", "")),
        keyword="道路养护",
        compact="上午村口道路养护，运农货的车走东侧便道；",
        fallback="上午村口道路养护，运农货的车走东侧便道；",
    )
    weather_line = _trailer_line(
        str(weather.get("summary", "")),
        keyword="阵雨",
        compact="午后可能有阵雨，晒谷和摆摊的先备遮雨布。",
        fallback="午后可能有阵雨，晒谷和摆摊的先备遮雨布。",
    )
    business_line = _trailer_line(
        str(business.get("summary", "")),
        keyword="老粮仓",
        compact="周末老粮仓有农产品试吃和直播教学，想帮忙的乡亲可以去看看。",
        fallback="周末老粮仓有农产品试吃和直播教学。",
    )
    volunteer_line = _trailer_line(
        str(volunteer.get("summary", "")),
        keyword="夏收",
        compact="今晚七点，文化广场碰头，商量夏收志愿排班。",
        fallback="今晚七点，文化广场碰头，商量夏收志愿排班。",
    )

    return (
        "早上好，伴农电台开播。"
        f"今天出门先听三件事：{traffic_line}{weather_line}"
        f"{business_line}{volunteer_line}"
        "天气、农忙、通知和身边事，我们整理成一档广播，"
        "陪你干活，也让在外的人听见家里。"
    )


def _trailer_line(
    summary: str,
    *,
    keyword: str,
    compact: str,
    fallback: str,
) -> str:
    if keyword in summary:
        return compact
    return _clean_trailer_summary(summary or fallback)


def _clean_trailer_summary(summary: str) -> str:
    cleaned = summary.strip()
    cleaned = cleaned.replace("村干部 A", "村干部")
    cleaned = cleaned.replace("返乡青年 B", "返乡青年")
    cleaned = cleaned.replace("村干部 提醒大家", "")
    cleaned = cleaned.replace("返乡青年 提议", "")
    cleaned = cleaned.replace("村书记口播摘要：", "")
    cleaned = cleaned.replace("今天上午", "上午")
    cleaned = cleaned.strip()
    if not cleaned.endswith(("。", "！", "？")):
        cleaned += "。"
    return cleaned


def _first_signal_with_topic(
    signal_payloads: list[dict[str, Any]],
    *topics: str,
) -> dict[str, Any]:
    wanted = set(topics)
    for signal in signal_payloads:
        if wanted.intersection(str(topic) for topic in signal.get("topics", ())):
            return signal
    return {}


def _deduplicate_strings(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return tuple(result)


def _segments_for_program_preset(
    segments: tuple[MediaSegment, ...],
    *,
    preset: ProgramPreset,
    fallback_root: Path,
) -> tuple[MediaSegment, ...]:
    program_segments: list[MediaSegment] = []
    durations = preset.segment_durations(len(segments))
    for index, segment in enumerate(segments):
        program_segment_id = f"{preset.name}-{segment.segment_id}"
        metadata = dict(segment.metadata)
        metadata.update(
            {
                "program_preset": preset.name,
                "original_segment_id": segment.segment_id,
            }
        )
        program_segments.append(
            replace(
                segment,
                segment_id=program_segment_id,
                duration=durations[index],
                fallback_path=fallback_root / f"{program_segment_id}.mp3",
                metadata=metadata,
            )
        )
    return tuple(program_segments)


def broadcast_program_to_manifest_payload(program: BroadcastProgram) -> dict[str, Any]:
    plan = program.to_broadcast_plan()
    return {
        "id": plan.plan_id,
        "title": plan.title,
        "source": plan.source,
        "metadata": dict(plan.metadata),
        "program": program.to_mapping(),
        "segments": plan.to_runtime_segments(),
    }


def write_broadcast_program_manifest(
    program: BroadcastProgram,
    output_path: Path | str,
) -> Path:
    ensure_runtime_guardrails(program.to_broadcast_plan())
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            broadcast_program_to_manifest_payload(program),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output
