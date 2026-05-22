"""Pure text-flow helpers for upstream village content."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from banong_radio.domain import RawTextItem, SanitizedTextItem

PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)")
PRECISE_ADDRESS_PATTERN = re.compile(r"(家庭住址|住址|地址|门牌)[:：]?[^，。；;\n]*")


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
