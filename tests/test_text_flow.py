from banong_radio.domain import RawTextItem, SanitizedTextItem
from banong_radio.text_flow import sanitize_text_items


def test_sanitizer_empty_input_returns_empty_list() -> None:
    assert sanitize_text_items([]) == []


def test_sanitizer_deduplicates_by_item_id() -> None:
    items = [
        RawTextItem(item_id="notice-1", source="synthetic", text="第一条通知"),
        RawTextItem(item_id="notice-1", source="synthetic", text="重复通知"),
        RawTextItem(item_id="notice-2", source="synthetic", text="第二条通知"),
    ]

    sanitized = sanitize_text_items(items)

    assert [item.item_id for item in sanitized] == ["notice-1", "notice-2"]
    assert sanitized[0].text == "第一条通知"


def test_sanitizer_drops_empty_text_before_deduplicating() -> None:
    items = [
        RawTextItem(item_id="notice-1", source="synthetic", text="   "),
        RawTextItem(item_id="notice-1", source="synthetic", text="后续有效通知"),
    ]

    sanitized = sanitize_text_items(items)

    assert [item.text for item in sanitized] == ["后续有效通知"]


def test_sanitizer_redacts_sensitive_fields() -> None:
    items = [
        RawTextItem(
            item_id="private-1",
            source="synthetic",
            text="请联系 13812345678，身份证 11010519491231002X，地址：龙潭村 3 组 12 号",
        )
    ]

    sanitized = sanitize_text_items(items)

    assert len(sanitized) == 1
    text = sanitized[0].text
    assert "13812345678" not in text
    assert "11010519491231002X" not in text
    assert "龙潭村 3 组 12 号" not in text
    assert "phone" in sanitized[0].metadata["redactions"]
    assert "id_card" in sanitized[0].metadata["redactions"]
    assert "precise_address" in sanitized[0].metadata["redactions"]


def test_sanitizer_preserves_source_metadata_and_marks_sanitized() -> None:
    items = [
        RawTextItem(
            item_id="community-1",
            source="synthetic-community",
            text="  周末  集市  招募志愿者  ",
            metadata={"batch": "demo"},
        )
    ]

    sanitized = sanitize_text_items(items)

    assert sanitized == [
        SanitizedTextItem(
            item_id="community-1",
            source="synthetic-community",
            text="周末 集市 招募志愿者",
            metadata={
                "batch": "demo",
                "sanitized": True,
                "source_item_id": "community-1",
            },
        )
    ]


def test_sanitizer_does_not_cross_into_signal_or_plan_generation() -> None:
    sanitized = sanitize_text_items(
        [RawTextItem(item_id="radio-1", source="synthetic", text="今晚村口有电影")]
    )

    assert all(type(item) is SanitizedTextItem for item in sanitized)
    assert all("signals" not in item.metadata for item in sanitized)
    assert all("broadcast_plan" not in item.metadata for item in sanitized)
