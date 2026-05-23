# Presentation Flow

This document is for presentation preparation. It should not overstate implementation status.

## Positioning

Project name: 剪鸭村融媒体

Repository role: local AI radio runtime for the first product line.

Core sentence: use sound to turn village affairs, community dynamics, cultural tourism, and local operations into an AI-assisted media and information service.

## Judge-facing Frame

The event asks for AI empowerment of village economies beyond basic informatization. Position the project as a village information-service workflow while separating product vision from current implementation:

- The product architecture uses an LLM / Agent workflow to process village inputs. The current repository proves the local radio runtime, variable program presets, data boundaries, and an explicit OpenAI Agents SDK manager workflow behind `--orchestrator sdk`.
- Sound is the first output because it fits rural usage habits.
- The same data loop can later support village newspaper, web pages, tourism content, agricultural product promotion, and governance summaries.

## Three-minute Flow

1. Problem: village information is fragmented across notices, group chats, oral updates, tourism resources, and agricultural operations.
2. Medium choice: sound is zero-friction, ambient, emotional, and native to rural culture.
3. Product: a village AI media workflow whose first demonstrable output is a local radio stream.
4. Broadcast loop: synthetic village feed becomes `RawTextItem -> SanitizedTextItem -> VillageSignal -> ContextPacket -> TaskBrief -> BroadcastProgram -> BroadcastPlan`, then enters the existing runtime through a manifest.
5. Multi-output proof: the same `ContextPacket` can also generate a daily report, digital village newspaper draft, and short notices as a local text output pack.
6. Technical proof: local music/TTS/mix/playback, status screen, fallback, ACE-Step preflight, and optional ACE-Step source behind `MusicGenerator`.
7. Evidence organization: show innovation, rural fit, technical quality, completion, and market fit explicitly.
8. Boundary: current repository proves the local radio runtime, local text output pack, and preserved real-source interfaces; real data source automation, public deployment, mini-program, and video are roadmap items.

## Live Evidence

- Set `BANONG_PY=/Users/detroxryo/.local/bin/python3.11` for final verification and live commands on this machine.
- Generate the product broadcast manifest with `PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-broadcast --preset trailer_45s`.
- Prepare playable program assets with `PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-program --preset trailer_45s`.
- Generate the text output pack with `PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-outputs`.
- When `OPENAI_API_KEY` is configured, run the real multi-agent path with `PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-workflow --orchestrator sdk --preset trailer_45s`.
- Start the local radio loop with `PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-broadcast --manifest /Users/detroxryo/.cache/banong-radio/broadcast_manifest.json`.
- Show status JSON through the status screen.
- Show how a mood/source command updates requested fields.
- Mention that audio generation is isolated behind `MusicGenerator`.
- Mention fallback as a reliability feature, not as a failure.

## Suggested Talking Points

- "We are not building another app for elders to learn. We are using the village's existing sound tradition."
- "The radio is the first media output. The product boundary is village input data, AI processing, and reusable media output; this repository proves the local radio runtime slice."
- "The code is intentionally conservative: if model generation fails, the live radio path still works."
- "The same data loop now produces a local digital village newspaper draft JSON, but the rendered product, public deployment, and mini-program are roadmap items."
- "For the submission evidence: innovation is the voice-first workflow, rural fit is the village information scenario, technical difficulty is the local generation and fallback runtime, completion is the working CLI/status/audio path, and market fit is village governance plus local operations."

## Evidence Checklist

Use these dimensions to organize presentation material. Do not present them as official scoring weights unless final official rules are available.

| Dimension | Say this briefly |
| --- | --- |
| 创新性 | The product is designed to turn village data into a living media service, with radio as the first working output |
| 乡村契合度 | Sound matches elders, village broadcasts, opera, farming routines, and low-friction information access |
| 技术难度 | Local runtime, ACE-Step boundary, TTS, FFmpeg mixing, fallback, status observability |
| 完成度 | Runnable commands, local playback, dashboard, documented verification, known limitations |
| 市场契合度 | Useful for village committees, residents, new villagers, returning youth, tourism and agricultural operations |

## Do Not Claim

- Do not claim a complete 24-hour station is implemented.
- Do not claim all three real data sources are fully automated.
- Do not claim public deployment, mini-program listening, rendered digital village newspaper product, or video output is complete.
- Do not claim spatial computing or complex-systems simulation is implemented.
- Do not claim ACE-Step 1.7B real generation is verified on this machine.
- Do not present original group-chat text as directly broadcastable content.
- Do not say the project is "only a demo" in external-facing material; internally, keep implementation boundaries explicit.

## Acceptance Standard

The presentation should make the product feel complete enough to evaluate while keeping engineering claims auditable. Every claim should fit one of these states:

- Implemented in this repository.
- Locally demonstrable with current assets.
- Product roadmap, not yet implemented.

Use [Judge Submission Pack](judge-submission.md) as the fast judge-facing entry point.
Use [Final Acceptance](final-acceptance.md) as the submission checklist before presenting.
Use [Live Demo Runbook](live-demo-runbook.md) for the exact operator command order.
