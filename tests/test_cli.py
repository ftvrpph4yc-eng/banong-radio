import json

from banong_radio import cli
from banong_radio.sdk_workflow import (
    SDKConfigurationError,
    build_local_workflow_artifacts,
)


def test_cli_status_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["banong-radio", "status"])
    monkeypatch.setattr(cli, "read_status", lambda: {"ok": True, "mode": "idle"})

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {"ok": True, "mode": "idle"}


def test_cli_plan_demo_feed_writes_manifest(monkeypatch, capsys, tmp_path) -> None:
    output = tmp_path / "generated_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-demo-feed",
            "--feed",
            "demo/village_feed.json",
            "--output",
            str(output),
            "--date",
            "2026-05-23",
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["manifest_path"] == str(output)
    assert parsed["source"] == "task_brief"
    assert parsed["segments"] == 5
    assert output.exists()


def test_cli_plan_demo_outputs_writes_output_pack(monkeypatch, capsys, tmp_path) -> None:
    output = tmp_path / "outputs.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-demo-outputs",
            "--feed",
            "demo/village_feed.json",
            "--output",
            str(output),
            "--date",
            "2026-05-23",
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["output_path"] == str(output)
    assert parsed["source"] == "task_brief"
    assert parsed["daily_sections"] == 5
    assert parsed["newspaper_pages"] >= 3
    assert parsed["notices"] >= 2
    assert output.exists()


def test_cli_plan_broadcast_writes_product_manifest(monkeypatch, capsys, tmp_path) -> None:
    output = tmp_path / "broadcast_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-broadcast",
            "--feed",
            "demo/village_feed.json",
            "--output",
            str(output),
            "--preset",
            "trailer_45s",
            "--date",
            "2026-05-23",
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["manifest_path"] == str(output)
    assert parsed["preset"] == "trailer_45s"
    assert 45 <= parsed["target_duration"] <= 60
    assert parsed["actual_duration"] == parsed["target_duration"]
    assert parsed["segments"] == 1
    assert parsed["source"] == "program_preset"
    assert output.exists()


def test_cli_render_program_prepares_playable_assets(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    output = tmp_path / "broadcast_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "render-program",
            "--feed",
            "demo/village_feed.json",
            "--output",
            str(output),
            "--preset",
            "trailer_45s",
        ],
    )
    monkeypatch.setattr(
        cli,
        "ensure_playable_assets",
        lambda manifest_path: [{"id": "segment-1"}],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["playable_segments"] == 1
    assert output.exists()


def test_cli_plan_broadcast_can_use_sdk_orchestrator(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    output = tmp_path / "broadcast_manifest.json"
    report = tmp_path / "agent_report.json"
    artifacts = build_local_workflow_artifacts(
        "demo/village_feed.json",
        preset_name="trailer_45s",
        date="2026-05-23",
    )
    monkeypatch.setattr(
        cli,
        "build_sdk_workflow_from_feed",
        lambda *args, **kwargs: artifacts,
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-broadcast",
            "--orchestrator",
            "sdk",
            "--feed",
            "demo/village_feed.json",
            "--output",
            str(output),
            "--report-output",
            str(report),
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["orchestrator"] == "sdk"
    assert parsed["manifest_path"] == str(output)
    assert parsed["report_path"] == str(report)
    assert output.exists()
    assert report.exists()


def test_cli_plan_workflow_writes_all_outputs(monkeypatch, capsys, tmp_path) -> None:
    broadcast_output = tmp_path / "broadcast.json"
    text_output = tmp_path / "outputs.json"
    report_output = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-workflow",
            "--feed",
            "demo/village_feed.json",
            "--broadcast-output",
            str(broadcast_output),
            "--text-output",
            str(text_output),
            "--report-output",
            str(report_output),
            "--preset",
            "trailer_45s",
            "--date",
            "2026-05-23",
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["orchestrator"] == "local"
    assert parsed["manifest_path"] == str(broadcast_output)
    assert parsed["output_path"] == str(text_output)
    assert parsed["report_path"] == str(report_output)
    assert parsed["daily_sections"] == 5
    assert parsed["notices"] >= 2
    assert broadcast_output.exists()
    assert text_output.exists()
    assert report_output.exists()


def test_cli_plan_daily_schedule_writes_schedule_and_preview(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    schedule_output = tmp_path / "daily_schedule.json"
    preview_output = tmp_path / "preview_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-daily-schedule",
            "--output",
            str(schedule_output),
            "--preview-manifest-output",
            str(preview_output),
            "--date",
            "2026-05-24",
            "--unavailable-provider",
            "opera_catalog",
        ],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["schedule_path"] == str(schedule_output)
    assert parsed["preview_manifest_path"] == str(preview_output)
    assert parsed["preset"] == "daily_12h"
    assert parsed["total_duration"] == 12 * 60 * 60
    assert parsed["slots"] == 19
    assert parsed["fallback_slots"] > 0
    assert schedule_output.exists()
    assert preview_output.exists()


def test_cli_render_daily_schedule_prepares_preview_assets(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    schedule_output = tmp_path / "daily_schedule.json"
    preview_output = tmp_path / "preview_manifest.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "render-daily-schedule",
            "--output",
            str(schedule_output),
            "--preview-manifest-output",
            str(preview_output),
            "--date",
            "2026-05-24",
        ],
    )
    monkeypatch.setattr(
        cli,
        "ensure_playable_assets",
        lambda manifest_path: [{"id": "opening"}, {"id": "podcast"}, {"id": "opera"}],
    )

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is True
    assert parsed["playable_segments"] == 3
    assert schedule_output.exists()
    assert preview_output.exists()


def test_cli_sdk_failure_prints_structured_error(monkeypatch, capsys, tmp_path) -> None:
    def fail_sdk(*args, **kwargs):
        raise SDKConfigurationError("OPENAI_API_KEY is required for --orchestrator sdk.")

    monkeypatch.setattr(cli, "build_sdk_workflow_from_feed", fail_sdk)
    monkeypatch.setattr(
        "sys.argv",
        [
            "banong-radio",
            "plan-broadcast",
            "--orchestrator",
            "sdk",
            "--output",
            str(tmp_path / "broadcast.json"),
        ],
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is False
    assert parsed["error"] == "sdk_configuration_error"
    assert parsed["error_type"] == "SDKConfigurationError"
    assert "OPENAI_API_KEY" in parsed["message"]


def test_cli_start_broadcast_reuses_runtime_entrypoint(monkeypatch, capsys) -> None:
    def fake_start(manifest_path):
        return {"ok": True, "manifest_path": str(manifest_path)}

    monkeypatch.setattr(
        "sys.argv",
        ["banong-radio", "start-broadcast", "--manifest", "/tmp/broadcast.json"],
    )
    monkeypatch.setattr(cli, "start_demo", fake_start)

    cli.main()

    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {"ok": True, "manifest_path": "/tmp/broadcast.json"}


def test_cli_missing_required_argument_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["banong-radio", "generate-segment"])

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is False
    assert parsed["error"] == "usage_error"
    assert "--mood" in parsed["message"]
    assert "usage:" in parsed["usage"]


def test_cli_unknown_command_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["banong-radio", "not-a-command"])

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected SystemExit")

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["ok"] is False
    assert parsed["error"] == "usage_error"
    assert "invalid choice" in parsed["message"]


def test_cli_runtime_error_prints_json(monkeypatch, capsys) -> None:
    def fail_start_demo(manifest_path):
        raise ValueError("broadcast plan has no segments: missing")

    monkeypatch.setattr("sys.argv", ["banong-radio", "start-demo", "--manifest", "/tmp/missing.json"])
    monkeypatch.setattr(cli, "start_demo", fail_start_demo)

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("expected SystemExit")

    parsed = json.loads(capsys.readouterr().out)
    assert parsed == {
        "ok": False,
        "error": "runtime_error",
        "error_type": "ValueError",
        "message": "broadcast plan has no segments: missing",
    }
