"""Pure text-flow helpers for upstream village content."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from banong_radio.domain import (
    BroadcastPlan,
    ContextPacket,
    MediaSegment,
    RawTextItem,
    SanitizedTextItem,
    TaskBrief,
    VillageSignal,
)

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
    "governance": "prepare a governance task brief from sanitized village signals",
}
DEFAULT_FALLBACK_ROOT = Path("/Users/detroxryo/Music/BanongRadio/fallback")
DEFAULT_SEGMENT_DURATION = 18
TOPIC_MOOD_MAP = {
    "weather": "雨天提醒",
    "traffic": "村口道路",
    "farming": "农忙田野",
    "local_business": "农产集市",
    "volunteer": "志愿服务",
    "governance": "村务讨论",
    "voice_transcript": "书记口播",
    "community": "社区动态",
    "notice": "村务公告",
}
TOPIC_PROMPT_MAP = {
    "weather": "gentle rainy village radio bed, soft guzheng, calm reminder",
    "traffic": "steady village road bulletin bed, light percussion, practical",
    "farming": "warm field recording texture, acoustic folk, harvest morning",
    "local_business": "bright rural market groove, light electronic folk, upbeat",
    "volunteer": "warm community service theme, soft piano, hopeful",
    "governance": "clear public announcement bed, calm strings, trustworthy",
    "voice_transcript": "spoken village bulletin bed, warm ambient, grounded",
    "community": "friendly community radio bed, acoustic guitar, warm",
    "notice": "clear village notice bed, guzheng, light pulse",
}


class SourceAdapter(Protocol):
    """Adapter contract for converting one upstream source into RawTextItem values."""

    source_type: str

    def fetch_items(self) -> list[RawTextItem]:
        """Return raw text items without planning, summarizing, or runtime side effects."""
        ...


class SourceAdapterNotConfigured(RuntimeError):
    """Raised when a real-source adapter has no explicit safe configuration."""


@dataclass(frozen=True)
class SourceAdapterRegistration:
    """Auditable registry entry for a future real-source adapter boundary."""

    key: str
    source_type: str
    adapter_class: type[Any]
    status: str
    boundary: str


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
            f"{type(self).__name__} is not configured; this demo does not access "
            "external data sources by default."
        )


class WeChatGroupSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "chat_excerpt"


class WeatherSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "weather"


class PublicNoticeSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "public_notice"


class GovernmentWebsiteSourceAdapter(PublicNoticeSourceAdapter):
    """Future government-website adapter boundary that yields public notices."""


class VoiceTranscriptSourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "voice_transcript"


class CommunitySourceAdapter(_FixtureBackedSourceAdapter):
    source_type = "community"


REAL_SOURCE_ADAPTER_REGISTRY: tuple[SourceAdapterRegistration, ...] = (
    SourceAdapterRegistration(
        key="wechat_group",
        source_type=WeChatGroupSourceAdapter.source_type,
        adapter_class=WeChatGroupSourceAdapter,
        status="fixture_only",
        boundary="does not read chat exports or live WeChat data without an approved task",
    ),
    SourceAdapterRegistration(
        key="weather_api",
        source_type=WeatherSourceAdapter.source_type,
        adapter_class=WeatherSourceAdapter,
        status="fixture_only",
        boundary="does not call weather APIs without credentials and approval",
    ),
    SourceAdapterRegistration(
        key="government_website",
        source_type=GovernmentWebsiteSourceAdapter.source_type,
        adapter_class=GovernmentWebsiteSourceAdapter,
        status="fixture_only",
        boundary="does not scrape or fetch government websites without approval",
    ),
    SourceAdapterRegistration(
        key="voice_transcript",
        source_type=VoiceTranscriptSourceAdapter.source_type,
        adapter_class=VoiceTranscriptSourceAdapter,
        status="fixture_only",
        boundary="does not load voice originals or transcripts without approval",
    ),
    SourceAdapterRegistration(
        key="community_source",
        source_type=CommunitySourceAdapter.source_type,
        adapter_class=CommunitySourceAdapter,
        status="fixture_only",
        boundary="does not read private community sources without approval",
    ),
)


def get_real_source_adapter_registry() -> tuple[SourceAdapterRegistration, ...]:
    """Return the stable real-source interfaces preserved for future rollout."""

    return REAL_SOURCE_ADAPTER_REGISTRY


def build_real_source_adapters(
    fixture_items_by_key: Mapping[str, Iterable[RawTextItem]] | None = None,
) -> dict[str, SourceAdapter]:
    """Build fixture-backed real-source adapters without touching external data."""

    fixtures = dict(fixture_items_by_key or {})
    known_keys = {registration.key for registration in REAL_SOURCE_ADAPTER_REGISTRY}
    unknown_keys = sorted(set(fixtures) - known_keys)
    if unknown_keys:
        raise ValueError(f"unknown real source adapter key: {', '.join(unknown_keys)}")

    adapters: dict[str, SourceAdapter] = {}
    for registration in REAL_SOURCE_ADAPTER_REGISTRY:
        adapters[registration.key] = registration.adapter_class(
            fixture_items=fixtures.get(registration.key)
        )
    return adapters


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


class RadioPlanner:
    """Turn a radio task brief into a BroadcastPlan without touching runtime."""

    def __init__(
        self,
        *,
        fallback_root: Path | str = DEFAULT_FALLBACK_ROOT,
        segment_duration: int = DEFAULT_SEGMENT_DURATION,
    ) -> None:
        self.fallback_root = Path(fallback_root)
        self.segment_duration = segment_duration

    def generate(self, brief: TaskBrief) -> BroadcastPlan:
        if brief.task != "radio":
            raise ValueError(f"radio planner requires task='radio': {brief.task}")

        signal_payloads = brief.metadata.get("signals", ())
        if not isinstance(signal_payloads, (list, tuple)) or not signal_payloads:
            raise ValueError("radio planner requires task brief signal payloads")

        segments = tuple(
            self._segment_from_signal(signal, index=index)
            for index, signal in enumerate(signal_payloads)
            if isinstance(signal, dict)
        )
        if not segments:
            raise ValueError("radio planner produced no segments")

        return BroadcastPlan(
            plan_id=f"radio:{brief.context_packet_id}",
            title="剪鸭村融媒体本地 AI 广播",
            source="task_brief",
            segments=segments,
            metadata={
                "context_packet_id": brief.context_packet_id,
                "task": brief.task,
                "signal_count": brief.metadata.get("signal_count", len(segments)),
                "topics": brief.metadata.get("topics", ()),
                "generated_by": "RadioPlanner",
            },
        )

    def _segment_from_signal(
        self,
        signal_payload: dict[str, Any],
        *,
        index: int,
    ) -> MediaSegment:
        signal_id = str(signal_payload.get("signal_id", f"signal:{index + 1}"))
        topics = _deduplicate(str(topic) for topic in signal_payload.get("topics", ()))
        primary_topic = topics[0] if topics else "community"
        segment_id = f"radio-{_safe_segment_id(signal_id)}"
        title = str(signal_payload.get("title", f"村庄信号 {index + 1}"))
        summary = str(signal_payload.get("summary", ""))
        urgency = str(signal_payload.get("urgency", "normal"))

        return MediaSegment(
            segment_id=segment_id,
            label=_label_for_topic(primary_topic, title),
            intro_text=_intro_text(title=title, summary=summary, urgency=urgency),
            music_prompt=_music_prompt_for_topic(primary_topic, urgency=urgency),
            duration=self.segment_duration,
            fallback_path=self.fallback_root / f"{segment_id}.mp3",
            source_label=title,
            metadata={
                "source_signal_id": signal_id,
                "topics": topics,
                "urgency": urgency,
                "generated_from": "task_brief",
            },
        )


def build_demo_feed_broadcast_plan(
    feed_path: Path | str,
    *,
    date: str | None = None,
    place: str | None = "剪鸭村",
    audience: Iterable[str] = ("villagers",),
    fallback_root: Path | str = DEFAULT_FALLBACK_ROOT,
) -> BroadcastPlan:
    raw_items = DemoVillageFeedAdapter(feed_path).fetch_items()
    sanitized_items = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized_items)
    context = ContextBuilder().build(
        signals,
        date=date,
        place=place,
        audience=audience,
    )
    brief = TaskPlanner().plan(context, task="radio")
    return RadioPlanner(fallback_root=fallback_root).generate(brief)


def broadcast_plan_to_manifest_payload(plan: BroadcastPlan) -> dict[str, Any]:
    return {
        "id": plan.plan_id,
        "title": plan.title,
        "source": plan.source,
        "metadata": dict(plan.metadata),
        "segments": plan.to_runtime_segments(),
    }


def write_broadcast_plan_manifest(plan: BroadcastPlan, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(broadcast_plan_to_manifest_payload(plan), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return output


def _default_packet_id(*, date: str | None, place: str | None) -> str:
    parts = ["context", date or "demo"]
    if place:
        parts.append(place)
    return ":".join(parts)


def _safe_segment_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-").lower()
    if cleaned.startswith("signal-"):
        cleaned = cleaned.removeprefix("signal-")
    return cleaned or "segment"


def _label_for_topic(topic: str, title: str) -> str:
    mood = TOPIC_MOOD_MAP.get(topic, "社区动态")
    if title and title != topic:
        return f"{mood}：{title}"
    return mood


def _music_prompt_for_topic(topic: str, *, urgency: str) -> str:
    prompt = TOPIC_PROMPT_MAP.get(
        topic,
        "warm village radio bed, soft acoustic texture, community bulletin",
    )
    if urgency == "high":
        return f"{prompt}, slightly urgent but calm"
    return prompt


def _intro_text(*, title: str, summary: str, urgency: str) -> str:
    prefix = "这里是剪鸭村融媒体。"
    urgency_text = "这是一条需要优先注意的提醒。" if urgency == "high" else ""
    return f"{prefix}{urgency_text}{title}：{summary}"
