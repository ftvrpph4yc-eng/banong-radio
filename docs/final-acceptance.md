# Final Acceptance

This document is the R-11 submission and acceptance checklist for 剪鸭村融媒体. It turns the implemented demo loop into judge-facing evidence without expanding the product claim beyond the current repository.

## Submission Claim

The repository implements the first runnable product line: a local AI radio runtime for village information service.

The complete demo loop is:

```text
demo/village_feed.json
  -> DemoVillageFeedAdapter
  -> RawTextItem
  -> SanitizedTextItem
  -> VillageSignal
  -> ContextPacket
  -> TaskBrief
  -> RadioPlanner
  -> BroadcastPlan manifest
  -> local runtime
  -> fallback or generated music
  -> Chinese TTS
  -> FFmpeg mix
  -> local playback
  -> read-only status screen
```

Real-source interfaces are present as boundaries, but real private inputs are not connected in this repository.

## Demo Script

For the exact two-terminal operator flow, use [Live Demo Runbook](live-demo-runbook.md).

Run from the repository root:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
python3 -m compileall -q src tests
PYTHONPATH=src python3 -m banong_radio.cli plan-demo-feed
PYTHONPATH=src python3 -m banong_radio.cli start-demo --manifest /Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json
PYTHONPATH=src python3 -m banong_radio.cli status
PYTHONPATH=src python3 -m banong_radio.cli stop
```

For the read-only dashboard:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli serve-status
```

Open:

```text
http://127.0.0.1:8765/
```

## Acceptance Checklist

| Check | Expected result |
| --- | --- |
| Repository baseline | `main` and `origin/main` point to the submitted commit |
| Syntax gate | `python3 -m compileall -q src tests` passes |
| Documentation boundary | docs do not claim real-source automation, public deployment, mini-program, digital newspaper, video, or verified 1.7B generation |
| Demo feed planning | `plan-demo-feed` writes `/Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json` |
| Runtime fallback | generated demo feed manifest can enter `ensure_playable_assets` and produce fallback-playable segments |
| CLI status | `PYTHONPATH=src python3 -m banong_radio.cli status` returns `ok=true` |
| Manual listening | local playback is audible, understandable, and can be stopped cleanly |
| Status screen | `serve-status` exposes `/status.json` and the HTML dashboard reads it |

## Manual Listening Gate

Before presenting, run one local playback loop and confirm:

- the host voice is audible and not clipped
- background music does not overpower the voice
- `stop` ends playback cleanly
- the dashboard changes match the current runtime state
- if ACE-Step is disabled or unavailable, fallback still keeps the demo moving

Manual listening is intentionally separate from automated tests because the final acceptance standard includes presentation quality, not only file generation. The current demo TTS and music listening quality was manually accepted on 2026-05-23.

## Evidence Language

Use these exact claim states:

- Implemented: local CLI, demo feed planning, `BroadcastPlan` manifest handoff, TTS, FFmpeg mix, playback, fallback, status JSON, status dashboard, docs and tests.
- Demonstrable: synthetic village feed to playable local radio loop through the fallback-safe runtime.
- Preserved interface: WeChat group, weather, public notice, voice transcript, and community source adapter boundaries.
- Roadmap: real private data ingestion, full daily scheduling, public deployment, mini-program, digital village newspaper, and video output.

## Do Not Claim

- Do not claim real WeChat group, weather API, government website, or voice-source ingestion is connected.
- Do not claim a complete 24-hour station is implemented.
- Do not claim public deployment, mini-program listening, digital village newspaper, or video generation is complete.
- Do not claim ACE-Step 1.7B real generation is verified on this machine.
- Do not present synthetic fixture data as real village data.
- Do not commit generated audio, model weights, cache, logs, secrets, or private source material.
