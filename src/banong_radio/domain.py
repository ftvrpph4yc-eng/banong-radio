"""Domain objects for village media planning boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RawTextItem:
    """Single upstream text item before sanitization or task planning."""

    item_id: str
    source: str
    text: str
    observed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SanitizedTextItem:
    """Cleaned and source-labeled text safe for downstream processing."""

    item_id: str
    source: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VillageSignal:
    """Structured village signal extracted from sanitized text."""

    signal_id: str
    title: str
    summary: str
    topics: tuple[str, ...] = ()
    urgency: str = "normal"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextPacket:
    """Signals grouped for a date, place, audience, or topic."""

    packet_id: str
    signals: tuple[VillageSignal, ...]
    date: str | None = None
    place: str | None = None
    audience: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskBrief:
    """Task-specific input derived from a ContextPacket."""

    task: str
    context_packet_id: str
    intent: str
    inputs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DailyReport:
    """Daily text report generated from a task brief."""

    report_id: str
    title: str
    date: str | None = None
    place: str | None = None
    sections: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.report_id,
            "title": self.title,
            "date": self.date,
            "place": self.place,
            "sections": [dict(section) for section in self.sections],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VillageNewspaper:
    """Page-based village newspaper draft generated from a task brief."""

    newspaper_id: str
    title: str
    pages: tuple[dict[str, Any], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.newspaper_id,
            "title": self.title,
            "pages": [dict(page) for page in self.pages],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class VillageNotice:
    """Short village notice generated from urgent or public-service signals."""

    notice_id: str
    title: str
    body: str
    urgency: str = "normal"
    audience: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.notice_id,
            "title": self.title,
            "body": self.body,
            "urgency": self.urgency,
            "audience": list(self.audience),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TextOutputPack:
    """Multi-output text pack derived from one shared context packet."""

    pack_id: str
    daily_report: DailyReport
    village_newspaper: VillageNewspaper
    notices: tuple[VillageNotice, ...] = ()
    source: str = "task_brief"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "id": self.pack_id,
            "source": self.source,
            "daily_report": self.daily_report.to_mapping(),
            "village_newspaper": self.village_newspaper.to_mapping(),
            "notices": [notice.to_mapping() for notice in self.notices],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MediaSegment:
    """Reusable media segment for radio, web, or village newspaper outputs."""

    segment_id: str
    label: str
    intro_text: str
    music_prompt: str
    duration: int
    fallback_path: Path
    source_label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "MediaSegment":
        segment_id = str(payload["id"])
        return cls(
            segment_id=segment_id,
            label=str(payload.get("label", segment_id)),
            intro_text=str(payload.get("intro_text", "")),
            music_prompt=str(payload.get("music_prompt", "")),
            duration=int(payload.get("duration", 18)),
            fallback_path=Path(payload["fallback_path"]),
            source_label=str(payload.get("source", "")),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_runtime_dict(self) -> dict[str, Any]:
        return {
            "id": self.segment_id,
            "label": self.label,
            "intro_text": self.intro_text,
            "music_prompt": self.music_prompt,
            "duration": self.duration,
            "fallback_path": str(self.fallback_path),
            "source": self.source_label,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BroadcastPlan:
    """Radio plan consumed by the local audio runtime."""

    plan_id: str
    segments: tuple[MediaSegment, ...]
    title: str = "剪鸭村融媒体本地电台"
    source: str = "manifest"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_manifest_payload(
        cls,
        payload: dict[str, Any],
        plan_id: str = "demo_manifest",
    ) -> "BroadcastPlan":
        segments = tuple(
            MediaSegment.from_mapping(item) for item in payload.get("segments", [])
        )
        if not segments:
            raise ValueError(f"broadcast plan has no segments: {plan_id}")
        return cls(
            plan_id=str(payload.get("id", plan_id)),
            title=str(payload.get("title", "剪鸭村融媒体本地电台")),
            source="manifest",
            segments=segments,
            metadata=dict(payload.get("metadata", {})),
        )

    def to_runtime_segments(self) -> list[dict[str, Any]]:
        return [segment.to_runtime_dict() for segment in self.segments]
