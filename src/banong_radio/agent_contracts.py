"""SDK-style agent orchestration contracts without invoking external LLMs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from banong_radio.domain import BroadcastPlan


PHONE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\w)")
SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|cookie|token|secret)\s*[:=]\s*\S+"
)


@dataclass(frozen=True)
class AgentRoleSpec:
    """A narrow role definition aligned with OpenAI Agents SDK concepts."""

    name: str
    responsibility: str
    input_contract: str
    output_contract: str
    forbidden_actions: tuple[str, ...] = ()
    handoff_to: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "responsibility": self.responsibility,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "forbidden_actions": list(self.forbidden_actions),
            "handoff_to": list(self.handoff_to),
        }


@dataclass(frozen=True)
class AgentHandoffContract:
    """Structured handoff between two narrow agents."""

    from_agent: str
    to_agent: str
    goal: str
    input_contract: str
    output_contract: str
    guardrails: tuple[str, ...] = ()

    def to_mapping(self) -> dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "goal": self.goal,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "guardrails": list(self.guardrails),
        }


@dataclass(frozen=True)
class AgentVerification:
    cmd: str
    result: str
    key_output: str = ""

    def to_mapping(self) -> dict[str, str]:
        return {
            "cmd": self.cmd,
            "result": self.result,
            "key_output": self.key_output,
        }


@dataclass(frozen=True)
class StructuredAgentReport:
    """Uniform report shape for future SDK-backed or local agent tasks."""

    agent: str
    changed_paths: tuple[str, ...] = ()
    verification: tuple[AgentVerification, ...] = ()
    risks: tuple[str, ...] = ()
    next_suggestions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "changed_paths": list(self.changed_paths),
            "verification": [item.to_mapping() for item in self.verification],
            "risks": list(self.risks),
            "next_suggestions": list(self.next_suggestions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GuardrailFinding:
    code: str
    message: str
    scope: str

    def to_mapping(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "scope": self.scope,
        }


AGENT_ROLE_SPECS: tuple[AgentRoleSpec, ...] = (
    AgentRoleSpec(
        name="VillageSignalCollector",
        responsibility="collect approved source text into sanitized village signals",
        input_contract="approved SourceAdapter output or fixture RawTextItem values",
        output_contract="SanitizedTextItem and VillageSignal values",
        forbidden_actions=(
            "write host scripts",
            "touch audio runtime",
            "read private sources without approval",
        ),
        handoff_to=("RadioDirector",),
    ),
    AgentRoleSpec(
        name="RadioDirector",
        responsibility="turn sanitized context into a broadcast program plan",
        input_contract="ContextPacket, ProgramPreset, runtime status summary",
        output_contract="BroadcastProgram or BroadcastPlan JSON",
        forbidden_actions=("call TTS", "call ffmpeg", "call ACE-Step", "play audio"),
        handoff_to=("PromptComposer", "Scriptwriter", "TextOutputEditor"),
    ),
    AgentRoleSpec(
        name="PromptComposer",
        responsibility="compose music prompts, durations, and generation hints",
        input_contract="BroadcastProgram segment intents and place metadata",
        output_contract="music prompt fields on MediaSegment-compatible payloads",
        forbidden_actions=("read audio files", "invoke model APIs", "mix audio"),
        handoff_to=("Scriptwriter",),
    ),
    AgentRoleSpec(
        name="Scriptwriter",
        responsibility="write concise Chinese host scripts from sanitized context",
        input_contract="BroadcastProgram plan and sanitized signal summaries",
        output_contract="intro_text fields safe for TTS",
        forbidden_actions=("include real names", "include secrets", "include raw private text"),
        handoff_to=("WorkflowReviewer",),
    ),
    AgentRoleSpec(
        name="TextOutputEditor",
        responsibility="prepare daily report, newspaper draft, and notice outputs",
        input_contract="ContextPacket and task briefs derived from sanitized signals",
        output_contract="TextOutputPack JSON",
        forbidden_actions=(
            "read private sources",
            "publish outputs",
            "touch audio runtime",
        ),
        handoff_to=("WorkflowReviewer",),
    ),
    AgentRoleSpec(
        name="WorkflowReviewer",
        responsibility="review all planned outputs before runtime handoff",
        input_contract="BroadcastProgram, TextOutputPack, and guardrail findings",
        output_contract="StructuredAgentReport with approval or blocking risks",
        forbidden_actions=("play audio", "edit Mixer", "edit Player", "read secrets"),
        handoff_to=("RuntimeOperator",),
    ),
    AgentRoleSpec(
        name="RuntimeOperator",
        responsibility="invoke CLI contracts and report runtime status",
        input_contract="confirmed BroadcastPlan manifest path",
        output_contract="StructuredAgentReport with command results and risks",
        forbidden_actions=("implement generation algorithms", "edit Mixer", "edit Player"),
    ),
)


def get_agent_role_specs() -> tuple[AgentRoleSpec, ...]:
    return AGENT_ROLE_SPECS


def build_agent_handoff_contracts() -> tuple[AgentHandoffContract, ...]:
    specs = {spec.name: spec for spec in AGENT_ROLE_SPECS}
    contracts: list[AgentHandoffContract] = []
    for spec in AGENT_ROLE_SPECS:
        for target_name in spec.handoff_to:
            target = specs[target_name]
            contracts.append(
                AgentHandoffContract(
                    from_agent=spec.name,
                    to_agent=target.name,
                    goal=f"{spec.name} hands off narrow structured output to {target.name}",
                    input_contract=target.input_contract,
                    output_contract=target.output_contract,
                    guardrails=(
                        "handoff payload must be structured",
                        "private source text must be sanitized before scripting",
                        "runtime agents receive manifests, not raw source records",
                    ),
                )
            )
    return tuple(contracts)


def validate_runtime_guardrails(plan: BroadcastPlan) -> tuple[GuardrailFinding, ...]:
    """Check that runtime-bound audio scripts do not carry unsafe source material."""

    findings: list[GuardrailFinding] = []
    for segment in plan.segments:
        scope = f"segment:{segment.segment_id}"
        if PHONE_PATTERN.search(segment.intro_text):
            findings.append(
                GuardrailFinding(
                    code="phone_in_runtime_script",
                    message="runtime script contains an unredacted phone number",
                    scope=scope,
                )
            )
        if ID_CARD_PATTERN.search(segment.intro_text):
            findings.append(
                GuardrailFinding(
                    code="id_card_in_runtime_script",
                    message="runtime script contains an unredacted ID number",
                    scope=scope,
                )
            )
        if SECRET_PATTERN.search(segment.intro_text):
            findings.append(
                GuardrailFinding(
                    code="secret_in_runtime_script",
                    message="runtime script contains a token-like secret",
                    scope=scope,
                )
            )
        if segment.metadata.get("sanitized") is False:
            findings.append(
                GuardrailFinding(
                    code="unsanitized_runtime_source",
                    message="runtime segment metadata marks source material as unsanitized",
                    scope=scope,
                )
            )
        if segment.metadata.get("source_kind") == "private":
            findings.append(
                GuardrailFinding(
                    code="private_source_in_runtime",
                    message="runtime segment still references private source material",
                    scope=scope,
                )
            )
    return tuple(findings)


def ensure_runtime_guardrails(plan: BroadcastPlan) -> None:
    findings = validate_runtime_guardrails(plan)
    if findings:
        codes = ", ".join(finding.code for finding in findings)
        raise ValueError(f"broadcast plan failed runtime guardrails: {codes}")
