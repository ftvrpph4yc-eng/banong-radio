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
