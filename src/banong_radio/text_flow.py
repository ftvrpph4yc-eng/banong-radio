"""Pure text-flow helpers for upstream village content."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from banong_radio.domain import ContextPacket, RawTextItem, SanitizedTextItem, TaskBrief, VillageSignal

PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)")
PRECISE_ADDRESS_PATTERN = re.compile(r"(家庭住址|住址|地址|门牌)[:：]?[^，。；;\n]*")
SOURCE_TOPIC_MAP = {
    "public_notice": ("notice",),
    "weather": ("weather",),
    "community": ("community",),
    "chat_excerpt": ("community",),
    "voice_transcript": ("voice_transcript",),
}
KEYWORD_TOPIC_MAP = {
    "道路": "traffic",
    "绕行": "traffic",
    "阵雨": "weather",
    "防雨": "weather",
    "谷物": "farming",
    "农产品": "local_business",
    "直播": "local_business",
    "志愿": "volunteer",
    "排班": "governance",
}
HIGH_URGENCY_KEYWORDS = ("预警", "紧急", "立即", "绕行", "防雨")
TASK_INTENTS = {
    "radio": "prepare a radio task brief from sanitized village signals",
    "daily": "prepare a daily summary task brief from sanitized village signals",
    "newspaper": "prepare a village newspaper task brief from sanitized village signals",
    "alert": "prepare an alert task brief from sanitized village signals",
}


class SourceAdapter(Protocol):
    """Adapter contract for converting one upstream source into RawTextItem values."""

    source_type: str

    def fetch_items(self) -> list[RawTextItem]:
        """Return raw text items without planning, summarizing, or runtime side effects."""
        ...


class SourceAdapterNotConfigured(RuntimeError):
    """Raised when a real-source adapter has no explicit safe configuration."""


def raw_text_item_from_mapping(
    payload: dict[str, Any],
    *,
    feed_id: str | None = None,
) -> RawTextItem:
    item_id = str(payload.get("id", "")).strip()
    if not item_id:
        raise ValueError("village feed item missing id")

    source_type = str(payload.get("source_type", "")).strip()
    if not source_type:
        raise ValueError(f"village feed item missing source_type: {item_id}")

    metadata = dict(payload.get("metadata", {}))
    for field in (
        "source_label",
        "published_at",
        "sensitivity",
        "consent_status",
    ):
        value = payload.get(field)
        if value is not None:
            metadata[field] = str(value)
    if feed_id:
        metadata["feed_id"] = feed_id

    captured_at = payload.get("captured_at")
    return RawTextItem(
        item_id=item_id,
        source=source_type,
        text=str(payload.get("text", "")),
        observed_at=str(captured_at) if captured_at is not None else None,
        metadata=metadata,
    )


def load_village_feed(feed_path: Path | str) -> list[RawTextItem]:
    payload = json.loads(Path(feed_path).read_text(encoding="utf-8"))
    feed_id = str(payload.get("id", Path(feed_path).stem))
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("village feed items must be a list")

    raw_items: list[RawTextItem] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("village feed item must be an object")
        raw_items.append(raw_text_item_from_mapping(item, feed_id=feed_id))
    return raw_items


class DemoVillageFeedAdapter:
    """Fixture adapter for the local synthetic demo feed."""

    source_type = "demo_village_feed"

    def __init__(self, feed_path: Path | str) -> None:
        self.feed_path = Path(feed_path)

    def fetch_items(self) -> list[RawTextItem]:
        return load_village_feed(self.feed_path)


class _FixtureBackedSourceAdapter:
    source_type = "source"

    def __init__(self, fixture_items: Iterable[RawTextItem] | None = None) -> None:
        self._fixture_items = (
            tuple(fixture_items) if fixture_items is not None else None
        )

    def fetch_items(self) -> list[RawTextItem]:
        if self._fixture_items is not None:
            return list(self._fixture_items)
        raise SourceAdapterNotConfigured(
            f"{type(self).__name__} is not configured; R-08 does not access "
            "external data sources by default."
        )


class WeChatGroupSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "chat_excerpt"


class WeatherSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "weather"


class PublicNoticeSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "public_notice"


class VoiceTranscriptSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "voice_transcript"


class CommunitySourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "community"


def normalize_whitespace(text: str) -> str:
    """Collapse text whitespace without changing content semantics."""

    return " ".join(text.split())


def redact_sensitive_text(text: str) -> tuple[str, tuple[str, ...]]:
    redactions: list[str] = []

    redacted = PHONE_PATTERN.sub("[手机号已脱敏]", text)
    if redacted != text:
        redactions.append("phone")

    before = redacted
    redacted = ID_CARD_PATTERN.sub("[身份证号已脱敏]", redacted)
    if redacted != before:
        redactions.append("id_card")

    before = redacted
    redacted = PRECISE_ADDRESS_PATTERN.sub(
        lambda match: f"{match.group(1)}[地址已脱敏]",
        redacted,
    )
    if redacted != before:
        redactions.append("precise_address")

    return redacted, tuple(redactions)


def sanitize_text_items(raw_items: Iterable[RawTextItem]) -> list[SanitizedTextItem]:
    """Return sanitized upstream text items without crossing into planning."""

    sanitized_items: list[SanitizedTextItem] = []
    seen_item_ids: set[str] = set()

    for raw_item in raw_items:
        if raw_item.item_id in seen_item_ids:
            continue

        text = normalize_whitespace(raw_item.text)
        if not text:
            continue
        seen_item_ids.add(raw_item.item_id)

        text, redactions = redact_sensitive_text(text)
        metadata = dict(raw_item.metadata)
        metadata.update(
            {
                "sanitized": True,
                "source_item_id": raw_item.item_id,
            }
        )
        if redactions:
            metadata["redactions"] = redactions

        sanitized_items.append(
            SanitizedTextItem(
                item_id=raw_item.item_id,
                source=raw_item.source,
                text=text,
                metadata=metadata,
            )
        )

    return sanitized_items


def _deduplicate(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _topics_for_item(item: SanitizedTextItem) -> tuple[str, ...]:
    metadata_topic = item.metadata.get("topic")
    metadata_topics = item.metadata.get("topics")
    topics: list[str] = []
    if isinstance(metadata_topic, str):
        topics.append(metadata_topic)
    if isinstance(metadata_topics, (list, tuple)):
        topics.extend(str(topic) for topic in metadata_topics)
    topics.extend(SOURCE_TOPIC_MAP.get(item.source, (item.source,)))
    for keyword, topic in KEYWORD_TOPIC_MAP.items():
        if keyword in item.text:
            topics.append(topic)
    return _deduplicate(topics)


def _urgency_for_item(item: SanitizedTextItem) -> str:
    if any(keyword in item.text for keyword in HIGH_URGENCY_KEYWORDS):
        return "high"
    return "normal"


class SignalExtractor:
    """Deterministic extractor for already-sanitized demo text."""

    def extract(self, items: Iterable[SanitizedTextItem]) -> list[VillageSignal]:
        signals: list[VillageSignal] = []
        for item in items:
            topics = _topics_for_item(item)
            source_label = str(item.metadata.get("source_label", item.source))
            signal = VillageSignal(
                signal_id=f"signal:{item.item_id}",
                title=source_label,
                summary=item.text,
                topics=topics,
                urgency=_urgency_for_item(item),
                confidence=0.9 if item.metadata.get("fixture") else 0.8,
                metadata={
                    "source": item.source,
                    "source_item_id": item.metadata.get("source_item_id", item.item_id),
                    "sanitized": item.metadata.get("sanitized") is True,
                },
            )
            signals.append(signal)
        return signals


class ContextBuilder:
    """Group village signals for one date/place/audience context packet."""

    def build(
        self,
        signals: Iterable[VillageSignal],
        *,
        date: str | None = None,
        place: str | None = None,
        audience: Iterable[str] = ("villagers",),
        packet_id: str | None = None,
    ) -> ContextPacket:
        signal_tuple = tuple(signals)
        audience_tuple = tuple(audience)
        topics = _deduplicate(
            topic for signal in signal_tuple for topic in signal.topics
        )
        urgency_counts: dict[str, int] = {}
        for signal in signal_tuple:
            urgency_counts[signal.urgency] = urgency_counts.get(signal.urgency, 0) + 1

        return ContextPacket(
            packet_id=packet_id or _default_packet_id(date=date, place=place),
            signals=signal_tuple,
            date=date,
            place=place,
            audience=audience_tuple,
            metadata={
                "signal_count": len(signal_tuple),
                "topics": topics,
                "urgency_counts": urgency_counts,
            },
        )


class TaskPlanner:
    """Create task briefs from context without generating final outputs."""

    def plan(self, context: ContextPacket, *, task: str = "radio") -> TaskBrief:
        if not context.signals:
            raise ValueError("task brief requires at least one village signal")

        task_name = task.strip() or "radio"
        signal_payloads = tuple(
            {
                "signal_id": signal.signal_id,
                "title": signal.title,
                "summary": signal.summary,
                "topics": signal.topics,
                "urgency": signal.urgency,
            }
            for signal in context.signals
        )
        return TaskBrief(
            task=task_name,
            context_packet_id=context.packet_id,
            intent=TASK_INTENTS.get(
                task_name,
                f"prepare a {task_name} task brief from sanitized village signals",
            ),
            inputs=tuple(signal.signal_id for signal in context.signals),
            metadata={
                "signal_count": len(context.signals),
                "topics": context.metadata.get("topics", ()),
                "urgency_counts": context.metadata.get("urgency_counts", {}),
                "date": context.date,
                "place": context.place,
                "audience": context.audience,
                "signals": signal_payloads,
                "next_step": f"{task_name}_planner",
            },
        )


def _default_packet_id(*, date: str | None, place: str | None) -> str:
    parts = ["context", date or "demo"]
    if place:
        parts.append(place)
    return ":".join(parts)
