import json
from types import SimpleNamespace

from banong_radio.sdk_workflow import (
    SDKConfigurationError,
    build_local_workflow_artifacts,
    build_sdk_workflow_from_feed,
    write_sdk_workflow_artifacts,
)


DEMO_FEED_PATH = "demo/village_feed.json"


class FakeAgent:
    created = []

    def __init__(self, *, name, instructions, tools=None):
        self.name = name
        self.instructions = instructions
        self.tools = list(tools or [])
        FakeAgent.created.append(self)

    def as_tool(self, *, tool_name, tool_description):
        return {
            "agent": self.name,
            "tool_name": tool_name,
            "tool_description": tool_description,
        }


class FakeRunner:
    last_agent = None
    last_input = ""

    @staticmethod
    def run_sync(agent, input):
        FakeRunner.last_agent = agent
        FakeRunner.last_input = input
        return SimpleNamespace(
            final_output='{"approved": true, "summary": "workflow reviewed"}'
        )


def fake_sdk():
    FakeAgent.created = []
    FakeRunner.last_agent = None
    FakeRunner.last_input = ""
    return FakeAgent, FakeRunner


def test_sdk_workflow_runs_manager_with_specialist_tools(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("banong_radio.sdk_workflow._load_agents_sdk", fake_sdk)

    artifacts = build_sdk_workflow_from_feed(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )

    created_names = [agent.name for agent in FakeAgent.created]
    assert "VillageMediaOrchestrator" in created_names
    assert "TextOutputEditorAgent" in created_names
    assert "WorkflowReviewerAgent" in created_names
    assert FakeRunner.last_agent.name == "VillageMediaOrchestrator"
    assert len(FakeRunner.last_agent.tools) == 6
    assert '"broadcast_program"' in FakeRunner.last_input
    assert artifacts.program.program_id.startswith("broadcast:trailer_45s")
    assert artifacts.text_outputs.pack_id == "outputs:context:2026-05-23:剪鸭村"
    assert artifacts.report.metadata["orchestrator"] == "sdk"
    assert "workflow reviewed" in artifacts.sdk_final_output


def test_sdk_workflow_requires_openai_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    try:
        build_sdk_workflow_from_feed(DEMO_FEED_PATH)
    except SDKConfigurationError as exc:
        assert exc.error_code == "sdk_configuration_error"
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected SDKConfigurationError")


def test_local_workflow_writes_broadcast_text_and_report(tmp_path) -> None:
    artifacts = build_local_workflow_artifacts(
        DEMO_FEED_PATH,
        preset_name="trailer_45s",
        date="2026-05-23",
    )

    broadcast_path, text_path, report_path = write_sdk_workflow_artifacts(
        artifacts,
        broadcast_output=tmp_path / "broadcast.json",
        text_output=tmp_path / "outputs.json",
        report_output=tmp_path / "report.json",
    )

    broadcast = json.loads(broadcast_path.read_text(encoding="utf-8"))
    text = json.loads(text_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert broadcast["program"]["preset"]["name"] == "trailer_45s"
    assert text["daily_report"]["sections"]
    assert report["agent"] == "LocalWorkflow"
    assert report["metadata"]["orchestrator"] == "local"
