from pathlib import Path

from banong_radio.domain import RawTextItem, SanitizedTextItem
from banong_radio.text_flow import (
    CommunitySourceAdapter,
    DemoVillageFeedAdapter,
    PublicNoticeSourceAdapter,
    SourceAdapterNotConfigured,
    VoiceTranscriptSourceAdapter,
    WeatherSourceAdapter,
    WeChatGroupSourceAdapter,
    load_village_feed,
    sanitize_text_items,
)


DEMO_FEED_PATH = Path("demo/village_feed.json")


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


def test_demo_village_feed_adapter_loads_raw_items() -> None:
    items = DemoVillageFeedAdapter(DEMO_FEED_PATH).fetch_items()

    assert len(items) == 5
    assert all(type(item) is RawTextItem for item in items)
    assert {item.source for item in items} == {
        "public_notice",
        "weather",
        "community",
        "chat_excerpt",
        "voice_transcript",
    }
    assert items[0].item_id == "public-notice-001"
    assert items[0].observed_at == "2026-05-23T07:30:00+08:00"
    assert items[0].metadata["feed_id"] == "jianya-demo-feed"
    assert items[0].metadata["source_label"] == "镇政府公开公告 synthetic fixture"


def test_demo_village_feed_can_enter_sanitizer() -> None:
    raw_items = load_village_feed(DEMO_FEED_PATH)

    sanitized = sanitize_text_items(raw_items)

    assert len(sanitized) == len(raw_items)
    assert all(item.metadata["sanitized"] is True for item in sanitized)
    assert all("broadcast_plan" not in item.metadata for item in sanitized)


def test_real_source_adapter_stubs_are_not_configured_by_default() -> None:
    for adapter_class in (
        WeChatGroupSourceAdapter,
        WeatherSourceAdapter,
        PublicNoticeSourceAdapter,
        VoiceTranscriptSourceAdapter,
        CommunitySourceAdapter,
    ):
        adapter = adapter_class()
        try:
            adapter.fetch_items()
        except SourceAdapterNotConfigured as exc:
            message = str(exc)
        else:
            raise AssertionError(f"{adapter_class.__name__} accessed a source")

        assert "not configured" in message
        assert "external data sources" in message


def test_real_source_adapter_stubs_can_return_explicit_fixture_items() -> None:
    for adapter_class in (
        WeChatGroupSourceAdapter,
        WeatherSourceAdapter,
        PublicNoticeSourceAdapter,
        VoiceTranscriptSourceAdapter,
        CommunitySourceAdapter,
    ):
        fixture_items = [
            RawTextItem(
                item_id=f"{adapter_class.source_type}-fixture-1",
                source=adapter_class.source_type,
                text="公开低敏 fixture",
                metadata={"fixture": True},
            )
        ]
        adapter = adapter_class(fixture_items=fixture_items)

        assert adapter.fetch_items() == fixture_items
