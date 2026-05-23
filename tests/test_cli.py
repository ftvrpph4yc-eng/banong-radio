import json

from banong_radio import cli


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
