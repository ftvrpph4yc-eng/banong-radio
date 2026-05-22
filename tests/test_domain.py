from pathlib import Path

from banong_radio.domain import (
    BroadcastPlan,
    ContextPacket,
    MediaSegment,
    RawTextItem,
    SanitizedTextItem,
    TaskBrief,
    VillageSignal,
)


def test_manifest_is_broadcast_plan_input() -> None:
    plan = BroadcastPlan.from_manifest_payload(
        {
            "id": "demo",
            "title": "剪鸭村融媒体本地电台",
            "segments": [
                {
                    "id": "longtan_morning",
                    "label": "龙潭清晨",
                    "music_prompt": "peaceful morning",
                    "intro_text": "早上好。",
                    "duration": 18,
                    "fallback_path": "/tmp/longtan_morning.mp3",
                }
            ],
        }
    )

    assert plan.source == "manifest"
    assert plan.segments[0].segment_id == "longtan_morning"
    assert plan.to_runtime_segments()[0]["fallback_path"] == "/tmp/longtan_morning.mp3"


def test_empty_manifest_is_rejected() -> None:
    try:
        BroadcastPlan.from_manifest_payload({"segments": []}, plan_id="empty")
    except ValueError as exc:
        assert str(exc) == "broadcast plan has no segments: empty"
    else:
        raise AssertionError("expected ValueError")


def test_media_segment_mapping_keeps_runtime_boundary_shape() -> None:
    segment = MediaSegment.from_mapping(
        {
            "id": "field_future",
            "label": "田野未来主义",
            "intro_text": "新的节拍。",
            "music_prompt": "pastoral electronic",
            "duration": "18",
            "fallback_path": "/tmp/field_future.mp3",
            "source": "demo-manifest",
            "metadata": {"topic": "future"},
        }
    )

    runtime = segment.to_runtime_dict()

    assert segment.segment_id == "field_future"
    assert segment.fallback_path == Path("/tmp/field_future.mp3")
    assert runtime == {
        "id": "field_future",
        "label": "田野未来主义",
        "intro_text": "新的节拍。",
        "music_prompt": "pastoral electronic",
        "duration": 18,
        "fallback_path": "/tmp/field_future.mp3",
        "source": "demo-manifest",
        "metadata": {"topic": "future"},
    }


def test_media_segment_mapping_uses_safe_defaults() -> None:
    segment = MediaSegment.from_mapping(
        {
            "id": "longtan_morning",
            "fallback_path": "/tmp/longtan_morning.mp3",
        }
    )

    assert segment.label == "longtan_morning"
    assert segment.intro_text == ""
    assert segment.music_prompt == ""
    assert segment.duration == 18
    assert segment.source_label == ""
    assert segment.metadata == {}


def test_text_flow_domain_objects_are_separate_from_radio_runtime() -> None:
    raw = RawTextItem(item_id="wx-1", source="mock-wechat", text="今晚可能下雨")
    sanitized = SanitizedTextItem(
        item_id=raw.item_id,
        source=raw.source,
        text="今晚可能下雨",
        metadata={"privacy": "demo"},
    )
    signal = VillageSignal(
        signal_id="weather-1",
        title="天气提醒",
        summary="今晚可能下雨",
        topics=("weather",),
        urgency="normal",
    )
    packet = ContextPacket(packet_id="today", signals=(signal,), audience=("villagers",))
    brief = TaskBrief(
        task="radio",
        context_packet_id=packet.packet_id,
        intent="prepare broadcast plan",
        inputs=(raw.item_id,),
    )

    assert raw.source == "mock-wechat"
    assert sanitized.metadata["privacy"] == "demo"
    assert packet.signals[0].title == "天气提醒"
    assert brief.task == "radio"
