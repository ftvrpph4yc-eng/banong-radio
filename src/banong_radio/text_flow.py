"""Pure text-flow helpers for upstream village content."""

from __future__ import annotations

import re
from collections.abc import Iterable

from banong_radio.domain import RawTextItem, SanitizedTextItem

PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)")
PRECISE_ADDRESS_PATTERN = re.compile(r"(家庭住址|住址|地址|门牌)[:：]?[^，。；;\n]*")


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
