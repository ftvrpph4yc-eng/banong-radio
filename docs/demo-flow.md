# Presentation Flow

This document is for presentation preparation. It should not overstate implementation status.

## Positioning

Project name: 剪鸭村融媒体

Repository role: local AI radio runtime for the first product line.

Core sentence: use sound to turn village affairs, community dynamics, cultural tourism, and local operations into an AI-assisted media and information service.

## Judge-facing Frame

The event asks for AI empowerment of village economies beyond basic informatization. Position the project as a village information-service workflow while separating product vision from current implementation:

- The product architecture uses an LLM / Agent workflow to process village inputs, but the current repository only proves the local radio runtime and data boundaries.
- Sound is the first output because it fits rural usage habits.
- The same data loop can later support village newspaper, web pages, tourism content, agricultural product promotion, and governance summaries.

## Three-minute Flow

1. Problem: village information is fragmented across notices, group chats, oral updates, tourism resources, and agricultural operations.
2. Medium choice: sound is zero-friction, ambient, emotional, and native to rural culture.
3. Product: a village AI media workflow whose first demonstrable output is a local radio stream.
4. Demo loop: synthetic village feed becomes `RawTextItem -> SanitizedTextItem -> VillageSignal -> ContextPacket -> TaskBrief -> BroadcastPlan`, then enters the existing runtime through a manifest.
5. Technical proof: local music/TTS/mix/playback, status screen, fallback, ACE-Step preflight, and optional ACE-Step source behind `MusicGenerator`.
6. Evidence organization: show innovation, rural fit, technical quality, completion, and market fit explicitly.
7. Boundary: current repository proves the local radio runtime and preserves real-source interfaces; full data source automation and other media outputs are roadmap items.

## Live Evidence

- Generate the demo feed manifest with `PYTHONPATH=src python3 -m banong_radio.cli plan-demo-feed`.
- Start the local radio loop with `PYTHONPATH=src python3 -m banong_radio.cli start-demo --manifest /Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json`.
- Show status JSON through the status screen.
- Show how a mood/source command updates requested fields.
- Mention that audio generation is isolated behind `MusicGenerator`.
- Mention fallback as a reliability feature, not as a failure.

## Suggested Talking Points

- "We are not building another app for elders to learn. We are using the village's existing sound tradition."
- "The radio is the first media output. The product boundary is village input data, AI processing, and reusable media output; this repository proves the local radio runtime slice."
- "The code is intentionally conservative: if model generation fails, the live radio path still works."
- "The same data loop can later produce a digital village newspaper, but that is not claimed as implemented in this repository."
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
- Do not claim public deployment, mini-program listening, digital village newspaper, or video output is complete.
- Do not claim spatial computing or complex-systems simulation is implemented.
- Do not claim ACE-Step 1.7B real generation is verified on this machine.
- Do not present original group-chat text as directly broadcastable content.
- Do not say the project is "only a demo" in external-facing material; internally, keep implementation boundaries explicit.

## Acceptance Standard

The presentation should make the product feel complete enough to evaluate while keeping engineering claims auditable. Every claim should fit one of these states:

- Implemented in this repository.
- Locally demonstrable with current assets.
- Product roadmap, not yet implemented.

Use [Final Acceptance](final-acceptance.md) as the submission checklist before presenting.
Use [Live Demo Runbook](live-demo-runbook.md) for the exact operator command order.
