from banong_radio.agent_contracts import (
    AgentVerification,
    StructuredAgentReport,
    build_agent_handoff_contracts,
    ensure_runtime_guardrails,
    get_agent_role_specs,
    validate_runtime_guardrails,
)
from banong_radio.domain import BroadcastPlan, MediaSegment


def test_agent_role_specs_are_narrow_and_sdk_compatible() -> None:
    specs = get_agent_role_specs()
    names = [spec.name for spec in specs]

    assert names == [
        "VillageSignalCollector",
        "RadioDirector",
        "PromptComposer",
        "Scriptwriter",
        "TextOutputEditor",
        "WorkflowReviewer",
        "RuntimeOperator",
    ]
    assert "touch audio runtime" in specs[0].forbidden_actions
    assert "call ffmpeg" in specs[1].forbidden_actions
    assert "publish outputs" in specs[4].forbidden_actions
    assert "read secrets" in specs[5].forbidden_actions
    assert "confirmed BroadcastPlan manifest path" in specs[-1].input_contract


def test_agent_handoff_contracts_are_structured() -> None:
    handoffs = build_agent_handoff_contracts()

    assert handoffs[0].from_agent == "VillageSignalCollector"
    assert handoffs[0].to_agent == "RadioDirector"
    assert all("structured" in handoff.guardrails[0] for handoff in handoffs)
    assert any(handoff.to_agent == "TextOutputEditor" for handoff in handoffs)
    assert any(handoff.to_agent == "WorkflowReviewer" for handoff in handoffs)
    assert any(handoff.to_agent == "RuntimeOperator" for handoff in handoffs)


def test_structured_agent_report_matches_required_shape() -> None:
    report = StructuredAgentReport(
        agent="RuntimeOperator",
        changed_paths=("/tmp/broadcast.json",),
        verification=(
            AgentVerification(
                cmd="banong-radio status",
                result="pass",
                key_output="mode=idle",
            ),
        ),
        risks=("manual listening still required",),
        next_suggestions=("run render-program",),
    )

    payload = report.to_mapping()

    assert payload["changed_paths"] == ["/tmp/broadcast.json"]
    assert payload["verification"][0]["result"] == "pass"
    assert payload["risks"] == ["manual listening still required"]
    assert payload["next_suggestions"] == ["run render-program"]


def test_runtime_guardrails_block_sensitive_or_private_payloads(tmp_path) -> None:
    plan = BroadcastPlan(
        plan_id="unsafe",
        segments=(
            MediaSegment(
                segment_id="unsafe",
                label="unsafe",
                intro_text="请联系 13812345678，token=abc123",
                music_prompt="quiet",
                duration=9,
                fallback_path=tmp_path / "unsafe.mp3",
                metadata={"sanitized": False, "source_kind": "private"},
            ),
        ),
    )

    findings = validate_runtime_guardrails(plan)

    assert {finding.code for finding in findings} == {
        "phone_in_runtime_script",
        "secret_in_runtime_script",
        "unsanitized_runtime_source",
        "private_source_in_runtime",
    }
    try:
        ensure_runtime_guardrails(plan)
    except ValueError as exc:
        assert "broadcast plan failed runtime guardrails" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_runtime_guardrails_allow_sanitized_runtime_plan(tmp_path) -> None:
    plan = BroadcastPlan(
        plan_id="safe",
        segments=(
            MediaSegment(
                segment_id="safe",
                label="safe",
                intro_text="这里是伴农电台。今天午后可能有阵雨，请提前收好晾晒谷物。",
                music_prompt="warm village radio bed",
                duration=9,
                fallback_path=tmp_path / "safe.mp3",
                metadata={"sanitized": True},
            ),
        ),
    )

    assert validate_runtime_guardrails(plan) == ()
    ensure_runtime_guardrails(plan)
