"""OpenAI Agents SDK orchestration for village media planning."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from banong_radio.agent_contracts import (
    AgentVerification,
    StructuredAgentReport,
    build_agent_handoff_contracts,
    ensure_runtime_guardrails,
    validate_runtime_guardrails,
)
from banong_radio.domain import TextOutputPack
from banong_radio.program import BroadcastProgram, build_broadcast_program_from_feed
from banong_radio.text_outputs import (
    build_demo_feed_text_output_pack,
    write_text_output_pack,
)


class SDKWorkflowError(RuntimeError):
    """Base error for SDK-backed orchestration failures."""

    error_code = "sdk_orchestration_failed"


class SDKConfigurationError(SDKWorkflowError):
    error_code = "sdk_configuration_error"


class SDKGuardrailError(SDKWorkflowError):
    error_code = "sdk_guardrail_failed"


@dataclass(frozen=True)
class SDKWorkflowArtifacts:
    """Artifacts produced by the SDK manager workflow."""

    program: BroadcastProgram
    text_outputs: TextOutputPack
    report: StructuredAgentReport
    sdk_final_output: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "program_id": self.program.program_id,
            "text_output_pack_id": self.text_outputs.pack_id,
            "report_agent": self.report.agent,
            "sdk_final_output": self.sdk_final_output,
        }


def build_sdk_workflow_from_feed(
    feed_path: Path | str,
    *,
    preset_name: str = "trailer_45s",
    date: str | None = None,
    place: str | None = "剪鸭村",
    audience: Iterable[str] = ("villagers",),
) -> SDKWorkflowArtifacts:
    """Run the official Agents SDK manager workflow over approved demo feed data."""

    _require_openai_api_key()
    Agent, Runner = _load_agents_sdk()

    program = build_broadcast_program_from_feed(
        feed_path,
        preset_name=preset_name,
        date=date,
        place=place,
        audience=audience,
    )
    text_outputs = build_demo_feed_text_output_pack(
        feed_path,
        date=date,
        place=place,
        audience=audience,
    )

    findings = validate_runtime_guardrails(program.to_broadcast_plan())
    if findings:
        codes = ", ".join(finding.code for finding in findings)
        raise SDKGuardrailError(f"SDK workflow candidate failed guardrails: {codes}")

    final_output = _run_manager_agent(
        Agent,
        Runner,
        program=program,
        text_outputs=text_outputs,
        feed_path=Path(feed_path),
        preset_name=preset_name,
    )
    report = _build_report(
        program=program,
        text_outputs=text_outputs,
        final_output=final_output,
    )
    return SDKWorkflowArtifacts(
        program=program,
        text_outputs=text_outputs,
        report=report,
        sdk_final_output=final_output,
    )


def write_agent_workflow_report(report: StructuredAgentReport, output_path: Path | str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_mapping(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def write_sdk_workflow_artifacts(
    artifacts: SDKWorkflowArtifacts,
    *,
    broadcast_output: Path | str,
    text_output: Path | str,
    report_output: Path | str,
) -> tuple[Path, Path, Path]:
    from banong_radio.program import write_broadcast_program_manifest

    ensure_runtime_guardrails(artifacts.program.to_broadcast_plan())
    broadcast_path = write_broadcast_program_manifest(
        artifacts.program,
        broadcast_output,
    )
    text_path = write_text_output_pack(artifacts.text_outputs, text_output)
    report_path = write_agent_workflow_report(artifacts.report, report_output)
    return broadcast_path, text_path, report_path


def build_local_workflow_artifacts(
    feed_path: Path | str,
    *,
    preset_name: str = "trailer_45s",
    date: str | None = None,
    place: str | None = "剪鸭村",
    audience: Iterable[str] = ("villagers",),
) -> SDKWorkflowArtifacts:
    """Build workflow artifacts without the SDK for local fallback-compatible runs."""

    program = build_broadcast_program_from_feed(
        feed_path,
        preset_name=preset_name,
        date=date,
        place=place,
        audience=audience,
    )
    text_outputs = build_demo_feed_text_output_pack(
        feed_path,
        date=date,
        place=place,
        audience=audience,
    )
    report = StructuredAgentReport(
        agent="LocalWorkflow",
        verification=(
            AgentVerification(
                cmd="local deterministic planners",
                result="pass",
                key_output=f"program={program.program_id}; outputs={text_outputs.pack_id}",
            ),
        ),
        risks=("SDK orchestration was not used for this local run.",),
        next_suggestions=("Run with --orchestrator sdk when OPENAI_API_KEY is configured.",),
        metadata={
            "orchestrator": "local",
            "program_id": program.program_id,
            "text_output_pack_id": text_outputs.pack_id,
        },
    )
    return SDKWorkflowArtifacts(
        program=program,
        text_outputs=text_outputs,
        report=report,
        sdk_final_output="",
    )


def _require_openai_api_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SDKConfigurationError(
            "OPENAI_API_KEY is required for --orchestrator sdk."
        )


def _load_agents_sdk() -> tuple[Any, Any]:
    try:
        from agents import Agent, Runner
    except ModuleNotFoundError as exc:
        raise SDKConfigurationError(
            "openai-agents is not installed; install project dependencies first."
        ) from exc
    return Agent, Runner


def _run_manager_agent(
    Agent: Any,
    Runner: Any,
    *,
    program: BroadcastProgram,
    text_outputs: TextOutputPack,
    feed_path: Path,
    preset_name: str,
) -> str:
    specialists = _build_specialist_agents(Agent)
    manager = Agent(
        name="VillageMediaOrchestrator",
        instructions=(
            "You are the main manager agent for Jianya Village Media. "
            "Use the specialist agent tools to inspect the prepared sanitized "
            "workflow artifacts, summarize whether the broadcast program and "
            "text outputs are coherent, and call out any blocking risk. "
            "Do not request raw private sources, do not modify runtime audio "
            "paths, and do not claim external data sources are connected. "
            "Return a concise JSON object with approved, summary, risks, and "
            "called_specialists fields."
        ),
        tools=[
            specialists["VillageSignalCollectorAgent"].as_tool(
                tool_name="collect_village_signals",
                tool_description="Review sanitized village signal and context coverage.",
            ),
            specialists["RadioDirectorAgent"].as_tool(
                tool_name="direct_radio_program",
                tool_description="Review the broadcast program plan and runtime manifest shape.",
            ),
            specialists["PromptComposerAgent"].as_tool(
                tool_name="compose_music_prompt_review",
                tool_description="Review music prompts, durations, and generation hints.",
            ),
            specialists["ScriptwriterAgent"].as_tool(
                tool_name="review_host_scripts",
                tool_description="Review host scripts for clarity and privacy boundaries.",
            ),
            specialists["TextOutputEditorAgent"].as_tool(
                tool_name="edit_text_outputs",
                tool_description="Review daily report, newspaper, and notice outputs.",
            ),
            specialists["WorkflowReviewerAgent"].as_tool(
                tool_name="review_workflow_boundaries",
                tool_description="Review final workflow risks and SDK boundary compliance.",
            ),
        ],
    )
    result = Runner.run_sync(
        manager,
        input=_manager_input(
            program=program,
            text_outputs=text_outputs,
            feed_path=feed_path,
            preset_name=preset_name,
        ),
    )
    return _stringify_final_output(getattr(result, "final_output", result))


def _build_specialist_agents(Agent: Any) -> dict[str, Any]:
    return {
        "VillageSignalCollectorAgent": Agent(
            name="VillageSignalCollectorAgent",
            instructions=(
                "Review only sanitized source/context coverage. Never ask for raw "
                "WeChat, weather API, government website, or voice-source data."
            ),
        ),
        "RadioDirectorAgent": Agent(
            name="RadioDirectorAgent",
            instructions=(
                "Review BroadcastProgram structure, preset fit, and runtime "
                "manifest compatibility. Do not call TTS, ffmpeg, ACE-Step, or playback."
            ),
        ),
        "PromptComposerAgent": Agent(
            name="PromptComposerAgent",
            instructions=(
                "Review music prompt fields and duration intent. Do not read or "
                "write audio files."
            ),
        ),
        "ScriptwriterAgent": Agent(
            name="ScriptwriterAgent",
            instructions=(
                "Review Chinese host scripts for clarity, village tone, and privacy. "
                "Block raw names, phone numbers, ID numbers, secrets, and private text."
            ),
        ),
        "TextOutputEditorAgent": Agent(
            name="TextOutputEditorAgent",
            instructions=(
                "Review the daily report, digital newspaper draft, and village notices. "
                "Do not publish outputs or claim unavailable external data sources."
            ),
        ),
        "WorkflowReviewerAgent": Agent(
            name="WorkflowReviewerAgent",
            instructions=(
                "Review overall workflow boundaries, guardrail status, and remaining risks. "
                "Keep fallback, Mixer, Player, and real-source boundaries explicit."
            ),
        ),
    }


def _manager_input(
    *,
    program: BroadcastProgram,
    text_outputs: TextOutputPack,
    feed_path: Path,
    preset_name: str,
) -> str:
    payload = {
        "task": "review and approve SDK-backed village media workflow artifacts",
        "feed_path": str(feed_path),
        "preset": preset_name,
        "broadcast_program": program.to_mapping(),
        "text_outputs": text_outputs.to_mapping(),
        "handoff_contracts": [
            contract.to_mapping() for contract in build_agent_handoff_contracts()
        ],
        "guardrail_status": "local runtime guardrails passed before SDK review",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_report(
    *,
    program: BroadcastProgram,
    text_outputs: TextOutputPack,
    final_output: str,
) -> StructuredAgentReport:
    return StructuredAgentReport(
        agent="VillageMediaOrchestrator",
        verification=(
            AgentVerification(
                cmd="OpenAI Agents SDK Runner.run_sync",
                result="pass",
                key_output=_truncate(final_output, 500),
            ),
            AgentVerification(
                cmd="local runtime guardrails",
                result="pass",
                key_output=f"segments={len(program.segments)}",
            ),
        ),
        risks=(
            "SDK review does not verify real external source ingestion.",
            "Manual listening is still required after render-program.",
        ),
        next_suggestions=("Run render-program --orchestrator sdk for playable assets.",),
        metadata={
            "orchestrator": "sdk",
            "sdk_pattern": "manager_agents_as_tools",
            "program_id": program.program_id,
            "text_output_pack_id": text_outputs.pack_id,
            "sdk_final_output": final_output,
        },
    )


def _stringify_final_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
