from tempfile import TemporaryDirectory
from pathlib import Path

from banong_radio.domain import (
    BroadcastPlan,
    ContextPacket,
    RawTextItem,
    SanitizedTextItem,
    TaskBrief,
    VillageSignal,
)
from banong_radio.text_flow import (
    RadioPlanner,
    build_real_source_adapters,
    CommunitySourceAdapter,
    ContextBuilder,
    DemoVillageFeedAdapter,
    get_real_source_adapter_registry,
    GovernmentWebsiteSourceAdapter,
    PublicNoticeSourceAdapter,
    SignalExtractor,
    SourceAdapterNotConfigured,
    TaskPlanner,
    VoiceTranscriptSourceAdapter,
    WeatherSourceAdapter,
    WeChatGroupSourceAdapter,
    broadcast_plan_to_manifest_payload,
    build_demo_feed_broadcast_plan,
    load_village_feed,
    sanitize_text_items,
    write_broadcast_plan_manifest,
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
        GovernmentWebsiteSourceAdapter,
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
        GovernmentWebsiteSourceAdapter,
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


def test_real_source_adapter_registry_preserves_target_interfaces() -> None:
    registry = get_real_source_adapter_registry()

    assert [(entry.key, entry.source_type, entry.adapter_class) for entry in registry] == [
        ("wechat_group", "chat_excerpt", WeChatGroupSourceAdapter),
        ("weather_api", "weather", WeatherSourceAdapter),
        ("government_website", "public_notice", GovernmentWebsiteSourceAdapter),
        ("voice_transcript", "voice_transcript", VoiceTranscriptSourceAdapter),
        ("community_source", "community", CommunitySourceAdapter),
    ]
    assert all(entry.status == "fixture_only" for entry in registry)
    assert all("without" in entry.boundary for entry in registry)


def test_build_real_source_adapters_allows_partial_fixture_configuration() -> None:
    weather_items = [
        RawTextItem(
            item_id="weather-fixture-1",
            source="weather",
            text="午后短时阵雨，注意晾晒。",
            metadata={"fixture": True},
        )
    ]

    adapters = build_real_source_adapters({"weather_api": weather_items})

    assert set(adapters) == {
        "wechat_group",
        "weather_api",
        "government_website",
        "voice_transcript",
        "community_source",
    }
    assert adapters["weather_api"].fetch_items() == weather_items

    try:
        adapters["wechat_group"].fetch_items()
    except SourceAdapterNotConfigured:
        pass
    else:
        raise AssertionError("unconfigured source adapter returned data")


def test_build_real_source_adapters_rejects_unknown_keys() -> None:
    try:
        build_real_source_adapters({"unknown_source": []})
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unknown real source key was accepted")

    assert "unknown real source adapter key: unknown_source" == message


def test_signal_extractor_turns_sanitized_demo_items_into_village_signals() -> None:
    raw_items = DemoVillageFeedAdapter(DEMO_FEED_PATH).fetch_items()
    sanitized = sanitize_text_items(raw_items)

    signals = SignalExtractor().extract(sanitized)

    assert len(signals) == 5
    assert all(type(signal) is VillageSignal for signal in signals)
    assert signals[0].signal_id == "signal:public-notice-001"
    assert signals[0].title == "镇政府公开公告 synthetic fixture"
    assert signals[0].summary == "今天上午村口道路养护，农产品运输车辆请从东侧便道绕行。"
    assert "traffic" in signals[0].topics
    assert signals[0].urgency == "high"
    assert signals[0].metadata == {
        "source": "public_notice",
        "source_item_id": "public-notice-001",
        "sanitized": True,
    }


def test_context_builder_groups_signals_without_generating_outputs() -> None:
    raw_items = DemoVillageFeedAdapter(DEMO_FEED_PATH).fetch_items()
    sanitized = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized)

    packet = ContextBuilder().build(
        signals,
        date="2026-05-23",
        place="剪鸭村",
        audience=("villagers", "operators"),
    )

    assert type(packet) is ContextPacket
    assert packet.packet_id == "context:2026-05-23:剪鸭村"
    assert packet.date == "2026-05-23"
    assert packet.place == "剪鸭村"
    assert packet.audience == ("villagers", "operators")
    assert packet.signals == tuple(signals)
    assert packet.metadata["signal_count"] == 5
    assert "weather" in packet.metadata["topics"]
    assert packet.metadata["urgency_counts"]["high"] >= 1


def test_task_planner_creates_radio_brief_without_broadcast_plan() -> None:
    raw_items = DemoVillageFeedAdapter(DEMO_FEED_PATH).fetch_items()
    sanitized = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized)
    packet = ContextBuilder().build(signals, date="2026-05-23", place="剪鸭村")

    brief = TaskPlanner().plan(packet, task="radio")

    assert type(brief) is TaskBrief
    assert brief.task == "radio"
    assert brief.context_packet_id == "context:2026-05-23:剪鸭村"
    assert brief.intent == "prepare a radio task brief from sanitized village signals"
    assert brief.inputs == tuple(signal.signal_id for signal in signals)
    assert brief.metadata["signal_count"] == 5
    assert brief.metadata["next_step"] == "radio_planner"
    assert "broadcast_plan" not in brief.metadata
    assert "segments" not in brief.metadata


def test_task_planner_rejects_empty_context() -> None:
    packet = ContextBuilder().build([], date="2026-05-23", place="剪鸭村")

    try:
        TaskPlanner().plan(packet, task="radio")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("empty context produced a task brief")

    assert "requires at least one village signal" in message


def test_radio_planner_generates_broadcast_plan_from_task_brief() -> None:
    raw_items = DemoVillageFeedAdapter(DEMO_FEED_PATH).fetch_items()
    sanitized = sanitize_text_items(raw_items)
    signals = SignalExtractor().extract(sanitized)
    packet = ContextBuilder().build(signals, date="2026-05-23", place="剪鸭村")
    brief = TaskPlanner().plan(packet, task="radio")

    with TemporaryDirectory() as tmpdir:
        fallback_root = Path(tmpdir) / "fallback"
        plan = RadioPlanner(fallback_root=fallback_root).generate(brief)

        assert type(plan) is BroadcastPlan
        assert plan.plan_id == "radio:context:2026-05-23:剪鸭村"
        assert plan.source == "task_brief"
        assert len(plan.segments) == 5
        first = plan.segments[0]
        assert first.segment_id == "radio-public-notice-001"
        assert first.label.startswith("村口道路")
        assert "道路养护" in first.intro_text
        assert "slightly urgent but calm" in first.music_prompt
        assert first.fallback_path == fallback_root / "radio-public-notice-001.mp3"
        assert first.metadata["source_signal_id"] == "signal:public-notice-001"


def test_radio_planner_rejects_non_radio_task() -> None:
    brief = TaskBrief(
        task="daily",
        context_packet_id="context:demo",
        intent="daily",
        inputs=("signal:1",),
        metadata={"signals": ({"signal_id": "signal:1", "summary": "x"},)},
    )

    try:
        RadioPlanner(fallback_root=Path("/tmp")).generate(brief)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("non-radio task produced a broadcast plan")

    assert "requires task='radio'" in message


def test_demo_feed_broadcast_plan_can_be_written_as_runtime_manifest() -> None:
    with TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_path = tmp_path / "demo_feed_manifest.json"

        plan = build_demo_feed_broadcast_plan(
            DEMO_FEED_PATH,
            date="2026-05-23",
            place="剪鸭村",
            fallback_root=tmp_path / "fallback",
        )
        written_path = write_broadcast_plan_manifest(plan, output_path)
        payload = broadcast_plan_to_manifest_payload(plan)

        assert written_path == output_path
        assert payload["source"] == "task_brief"
        assert len(payload["segments"]) == 5
        assert output_path.exists()
