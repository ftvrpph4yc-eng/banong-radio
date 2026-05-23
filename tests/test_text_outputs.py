import json
from pathlib import Path

from banong_radio.domain import DailyReport, TaskBrief, TextOutputPack, VillageNewspaper
from banong_radio.text_outputs import (
    NoticeGenerator,
    build_demo_feed_text_output_pack,
    write_text_output_pack,
)


DEMO_FEED_PATH = Path("demo/village_feed.json")


def test_demo_feed_text_output_pack_reuses_one_context_without_runtime() -> None:
    pack = build_demo_feed_text_output_pack(
        DEMO_FEED_PATH,
        date="2026-05-23",
        place="剪鸭村",
    )

    assert type(pack) is TextOutputPack
    assert type(pack.daily_report) is DailyReport
    assert type(pack.village_newspaper) is VillageNewspaper
    assert pack.pack_id == "outputs:context:2026-05-23:剪鸭村"
    assert pack.source == "task_brief"
    assert len(pack.daily_report.sections) == 5
    assert len(pack.village_newspaper.pages) >= 3
    assert len(pack.notices) >= 2
    assert pack.metadata["signal_count"] == 5


def test_daily_report_and_newspaper_keep_signal_references() -> None:
    pack = build_demo_feed_text_output_pack(DEMO_FEED_PATH, date="2026-05-23")

    first_section = pack.daily_report.sections[0]
    cover = pack.village_newspaper.pages[0]

    assert first_section["source_signal_id"] == "signal:public-notice-001"
    assert first_section["title"].startswith("重点提醒")
    assert cover["title"] == "封面"
    assert cover["items"][0]["source_signal_id"] == "signal:public-notice-001"


def test_notice_generator_rejects_wrong_task() -> None:
    brief = TaskBrief(
        task="daily",
        context_packet_id="context:demo",
        intent="daily",
        inputs=("signal:1",),
        metadata={
            "signals": (
                {
                    "signal_id": "signal:1",
                    "title": "道路提醒",
                    "summary": "请绕行。",
                    "topics": ("traffic",),
                    "urgency": "high",
                },
            )
        },
    )

    try:
        NoticeGenerator().generate(brief)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("wrong task produced notices")

    assert "alert generator requires task='alert'" in message


def test_write_text_output_pack_writes_json(tmp_path) -> None:
    pack = build_demo_feed_text_output_pack(DEMO_FEED_PATH, date="2026-05-23")
    output = tmp_path / "outputs.json"

    written = write_text_output_pack(pack, output)
    payload = json.loads(output.read_text())

    assert written == output
    assert payload["id"] == pack.pack_id
    assert payload["daily_report"]["sections"]
    assert payload["village_newspaper"]["pages"]
    assert payload["notices"]
