import re
from pathlib import Path


DOC_PATHS = [
    Path("README.md"),
    Path("docs/architecture.md"),
    Path("docs/operation.md"),
    Path("docs/judge-submission.md"),
    Path("docs/demo-flow.md"),
    Path("docs/final-acceptance.md"),
    Path("docs/live-demo-runbook.md"),
    Path("docs/decisions.md"),
]

FORBIDDEN_CLAIMS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"已接入微信群",
        r"微信群.*已接入",
        r"已接入天气\s*API",
        r"天气\s*API.*已接入",
        r"已接入政府官网",
        r"政府官网.*已接入",
        r"真实数据源.*已接入",
        r"完整\s*24\s*小时电台.*已实现",
        r"公网部署.*已完成",
        r"小程序.*已完成",
        r"数字村报.*已完成",
        r"视频生成.*已完成",
        r"1\.7B.*已真实生成验证",
        r"1\.7B.*real generation.*verified",
    ]
]


def doc_texts() -> dict[Path, str]:
    return {path: path.read_text() for path in DOC_PATHS}


def is_boundary_caveat(line: str) -> bool:
    caveat_markers = [
        "不",
        "不要",
        "not",
        "Do not",
        "caveat",
        "roadmap",
        "后续",
    ]
    return any(marker in line for marker in caveat_markers)


def test_docs_do_not_claim_unimplemented_capabilities() -> None:
    violations: list[str] = []
    for path, text in doc_texts().items():
        for line_number, line in enumerate(text.splitlines(), start=1):
            if is_boundary_caveat(line):
                continue
            for pattern in FORBIDDEN_CLAIMS:
                if pattern.search(line):
                    violations.append(f"{path}:{line_number}: {line}")

    assert violations == []


def test_docs_keep_required_boundary_caveats() -> None:
    readme = Path("README.md").read_text()
    operation = Path("docs/operation.md").read_text()
    judge_submission = Path("docs/judge-submission.md").read_text()
    demo_flow = Path("docs/demo-flow.md").read_text()
    final_acceptance = Path("docs/final-acceptance.md").read_text()
    live_demo_runbook = Path("docs/live-demo-runbook.md").read_text()
    decisions = Path("docs/decisions.md").read_text()

    assert "不接入真实微信群、天气 API、政府官网或口播转写" in readme
    assert "不实现完整 24 小时电台调度" in readme
    assert "不包含公网部署、小程序或视频生成" in readme
    assert "Do not claim 1.7B real generation" in operation
    assert "Do not claim:" in judge_submission
    assert "ACE-Step 1.7B real generation is verified" in judge_submission
    assert "Do not claim ACE-Step 1.7B real generation is verified" in demo_flow
    assert "Do not claim ACE-Step 1.7B real generation is verified" in final_acceptance
    assert "Do not claim real WeChat group, weather API, government website, or voice-source ingestion is connected" in final_acceptance
    assert "This does not verify ACE-Step 1.7B real generation" in live_demo_runbook
    assert "automatic downgrade to `acestep-5Hz-lm-0.6B`" in decisions


def test_docs_keep_sdk_only_agent_boundary() -> None:
    architecture = Path("docs/architecture.md").read_text()
    decisions = Path("docs/decisions.md").read_text()
    readme = Path("README.md").read_text()

    assert "OpenAI Agents SDK" in architecture
    assert "Do not add a separate local agent framework" in architecture
    assert "Do not create a parallel local agent framework" in decisions
    assert "`--orchestrator sdk` 显式启用 `openai-agents`" in readme
    assert "默认 local 路径仍不调用外部模型" in readme


def test_docs_describe_variable_program_presets() -> None:
    readme = Path("README.md").read_text()
    operation = Path("docs/operation.md").read_text()
    decisions = Path("docs/decisions.md").read_text()

    assert "`ProgramPreset` 支持 `trailer_45s`、`briefing_3m`、`show_2h`" in readme
    assert "短预告只是节目 preset，不是系统上限" in readme
    assert "plan-broadcast --preset trailer_45s" in operation
    assert "The short preview is therefore one program shape" in decisions
