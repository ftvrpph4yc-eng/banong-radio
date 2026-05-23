"""Deterministic text output generators for village media tasks."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from banong_radio.domain import (
    ContextPacket,
    DailyReport,
    RawTextItem,
    TaskBrief,
    TextOutputPack,
    VillageNewspaper,
    VillageNotice,
)
from banong_radio.text_flow import (
    ContextBuilder,
    DemoVillageFeedAdapter,
    SignalExtractor,
    TaskPlanner,
    sanitize_text_items,
)

NOTICE_TOPICS = {"notice", "weather", "traffic", "governance"}
NEWSPAPER_PAGE_TOPICS = (
    ("村务与提醒", {"notice", "traffic", "weather", "governance"}),
    ("社区与生活", {"community", "volunteer", "voice_transcript"}),
    ("文旅与农产", {"farming", "local_business"}),
)


class DailyReportGenerator:
    """Generate a daily report from a daily task brief."""

    def generate(self, brief: TaskBrief) -> DailyReport:
        _require_task(brief, "daily")
        signals = _signal_payloads(brief)
        date = _optional_str(brief.metadata.get("date"))
        place = _optional_str(brief.metadata.get("place"))
        sections = tuple(
            {
                "title": _section_title(signal),
                "summary": str(signal.get("summary", "")),
                "topics": list(_topics(signal)),
                "urgency": str(signal.get("urgency", "normal")),
                "source_signal_id": str(signal.get("signal_id", "")),
            }
            for signal in signals
        )
        return DailyReport(
            report_id=f"daily:{brief.context_packet_id}",
            title=_title("剪鸭村日报", date=date, place=place),
            date=date,
            place=place,
            sections=sections,
            metadata={
                "context_packet_id": brief.context_packet_id,
                "generated_by": "DailyReportGenerator",
                "signal_count": len(sections),
            },
        )


class VillageNewspaperGenerator:
    """Generate a page-based newspaper draft from a newspaper task brief."""

    def generate(self, brief: TaskBrief) -> VillageNewspaper:
        _require_task(brief, "newspaper")
        signals = _signal_payloads(brief)
        pages: list[dict[str, Any]] = [
            {
                "title": "封面",
                "headline": _title(
                    "剪鸭村数字村报",
                    date=_optional_str(brief.metadata.get("date")),
                    place=_optional_str(brief.metadata.get("place")),
                ),
                "items": [_compact_item(signal) for signal in signals[:3]],
            }
        ]
        for page_title, topic_set in NEWSPAPER_PAGE_TOPICS:
            items = [
                _compact_item(signal)
                for signal in signals
                if set(_topics(signal)).intersection(topic_set)
            ]
            if items:
                pages.append({"title": page_title, "items": items})

        return VillageNewspaper(
            newspaper_id=f"newspaper:{brief.context_packet_id}",
            title=str(pages[0]["headline"]),
            pages=tuple(pages),
            metadata={
                "context_packet_id": brief.context_packet_id,
                "generated_by": "VillageNewspaperGenerator",
                "page_count": len(pages),
            },
        )


class NoticeGenerator:
    """Generate short village notices without touching runtime playback."""

    def generate(self, brief: TaskBrief) -> tuple[VillageNotice, ...]:
        _require_task(brief, "alert")
        audience = tuple(str(item) for item in brief.metadata.get("audience", ()))
        notices: list[VillageNotice] = []
        for signal in _signal_payloads(brief):
            topics = set(_topics(signal))
            urgency = str(signal.get("urgency", "normal"))
            if urgency != "high" and not topics.intersection(NOTICE_TOPICS):
                continue
            signal_id = str(signal.get("signal_id", "signal"))
            notices.append(
                VillageNotice(
                    notice_id=f"notice:{_safe_output_id(signal_id)}",
                    title=str(signal.get("title", "村务通知")),
                    body=str(signal.get("summary", "")),
                    urgency=urgency,
                    audience=audience,
                    metadata={
                        "source_signal_id": signal_id,
                        "topics": tuple(_topics(signal)),
                        "generated_by": "NoticeGenerator",
                    },
                )
            )
        return tuple(notices)


def build_text_output_pack(context: ContextPacket) -> TextOutputPack:
    """Build all text outputs from one shared context packet."""

    planner = TaskPlanner()
    daily = DailyReportGenerator().generate(planner.plan(context, task="daily"))
    newspaper = VillageNewspaperGenerator().generate(
        planner.plan(context, task="newspaper")
    )
    notices = NoticeGenerator().generate(planner.plan(context, task="alert"))
    return TextOutputPack(
        pack_id=f"outputs:{context.packet_id}",
        daily_report=daily,
        village_newspaper=newspaper,
        notices=notices,
        metadata={
            "context_packet_id": context.packet_id,
            "date": context.date,
            "place": context.place,
            "audience": context.audience,
            "signal_count": len(context.signals),
            "generated_by": "build_text_output_pack",
        },
    )


def build_demo_feed_text_output_pack(
    feed_path: Path | str,
    *,
    date: str | None = None,
    place: str | None = "剪鸭村",
    audience: Iterable[str] = ("villagers",),
) -> TextOutputPack:
    """Build text outputs from the synthetic demo feed only."""

    raw_items: list[RawTextItem] = DemoVillageFeedAdapter(feed_path).fetch_items()
    sanitized_items = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized_items)
    context = ContextBuilder().build(
        signals,
        date=date,
        place=place,
        audience=audience,
    )
    return build_text_output_pack(context)


def write_text_output_pack(pack: TextOutputPack, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(pack.to_mapping(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _require_task(brief: TaskBrief, task: str) -> None:
    if brief.task != task:
        raise ValueError(f"{task} generator requires task='{task}': {brief.task}")


def _signal_payloads(brief: TaskBrief) -> tuple[dict[str, Any], ...]:
    signals = brief.metadata.get("signals", ())
    if not isinstance(signals, (list, tuple)) or not signals:
        raise ValueError(f"{brief.task} generator requires task brief signal payloads")
    return tuple(signal for signal in signals if isinstance(signal, dict))


def _topics(signal: dict[str, Any]) -> tuple[str, ...]:
    topics = signal.get("topics", ())
    if not isinstance(topics, (list, tuple)):
        return ()
    return tuple(str(topic) for topic in topics)


def _section_title(signal: dict[str, Any]) -> str:
    title = str(signal.get("title", "村庄动态"))
    urgency = str(signal.get("urgency", "normal"))
    if urgency == "high":
        return f"重点提醒：{title}"
    return title


def _compact_item(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _section_title(signal),
        "summary": str(signal.get("summary", "")),
        "topics": list(_topics(signal)),
        "source_signal_id": str(signal.get("signal_id", "")),
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _title(base: str, *, date: str | None, place: str | None) -> str:
    parts = [place or "剪鸭村", base]
    if date:
        parts.append(date)
    return " · ".join(parts)


def _safe_output_id(value: str) -> str:
    return value.replace(":", "-").strip("-") or "output"
