# Judge Submission Pack

This page is the fastest path for a judge or teammate to evaluate 剪鸭村融媒体 without reading every design note first.

## One-line Claim

剪鸭村融媒体 turns structured village information into local media outputs. This repository proves the first runnable product line: a fallback-safe local AI broadcast runtime with variable program presets, a 07:00-19:00 schedule preset, a synthetic village feed, text-flow boundaries, an opt-in OpenAI Agents SDK manager workflow, Chinese TTS, music, FFmpeg mixing, playback, tests, a read-only status screen, and a deterministic text output pack for daily report, village newspaper draft, and notices.

## Why It Should Stand Out

| Dimension | Evidence to show |
| --- | --- |
| Innovation | Voice-first village media workflow, not another app or notice board |
| Rural fit | Sound matches elders, broadcasts, local opera habits, farming routines, and low-friction village communication |
| Technical quality | `SourceAdapter -> Sanitizer -> SignalExtractor -> ContextBuilder -> TaskPlanner -> BroadcastProgram -> BroadcastPlan`, plus SDK-style handoff contracts, then TTS/music/mix/playback/status for radio |
| Completion | Runnable CLI, variable broadcast manifest, `daily_12h` schedule JSON, generated feed manifest, text output pack, local playback, dashboard, fallback, tests, GitHub Actions compile/test workflow, and documented acceptance commands |
| Market fit | Useful for village committees, residents, new villagers, returning youth, tourism, agricultural products, and local operations |

These dimensions organize submission material. Do not present them as official scoring weights unless final official rules are available.

## Live Demo Path

Use two terminals.

Terminal 1 keeps the status screen running:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli serve-status
```

Open:

```text
http://127.0.0.1:8765/
```

Terminal 2 runs the product broadcast loop:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-broadcast --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-program --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-outputs
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-broadcast --manifest /Users/detroxryo/.cache/banong-radio/broadcast_manifest.json
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli status
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli stop
```

The compatibility path remains available:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-feed
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-demo --manifest /Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli status
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli stop
```

Expected evidence:

- `plan-demo-feed` writes `/Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json`
- `plan-broadcast` writes `/Users/detroxryo/.cache/banong-radio/broadcast_manifest.json`
- `render-program --preset trailer_45s` prepares playable assets from the variable program layer
- `plan-daily-schedule` writes a 19-slot, 12-hour `daily_12h` schedule
- `render-daily-schedule` prepares 3 representative preview segments without generating 12 hours of audio
- `plan-demo-outputs` writes `/Users/detroxryo/.cache/banong-radio/demo_text_outputs.json`
- playback reports `ok=true`
- product broadcast status shows `playlist_total=1`; compatibility demo feed still has 5 source-derived segments
- dashboard changes from idle to playing
- `stop` returns the player to idle

## Verification Before Presenting

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
"$BANONG_PY" -m compileall -q src tests
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli preflight-ace
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-broadcast --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-daily-schedule --date 2026-05-24
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-daily-schedule --date 2026-05-24
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-feed
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-outputs
```

If `.venv` is absent, create it with:

```bash
/Users/detroxryo/.local/bin/python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
```

## Talk Track

1. Village information is fragmented across notices, group chats, oral updates, tourism resources, and agricultural operations.
2. The first medium is sound because it is low-friction, ambient, and native to rural culture.
3. The code turns a synthetic village feed into sanitized items, signals, context, task briefs, a variable `BroadcastProgram`, a runtime `BroadcastPlan`, and a separate text output pack.
4. The radio runtime consumes only the final manifest, keeping upstream text flow and text outputs separate from Mixer and Player.
5. The code also provides an official OpenAI Agents SDK manager workflow behind `--orchestrator sdk`, with specialist agents for signal review, radio direction, prompt review, script review, text outputs, and workflow review.
6. The live path uses TTS, music, FFmpeg mixing, local playback, fallback, and a read-only dashboard.
7. Fallback is the reliability strategy for a live presentation, while ACE-Step remains behind `MusicGenerator` as an opt-in source.

## Claim Boundaries

Implemented here:

- local CLI
- variable `BroadcastProgram` presets
- `daily_12h` 07:00-19:00 schedule preset and 3-segment preview manifest
- OpenAI Agents SDK manager workflow and role/handoff contracts
- demo feed planning
- `BroadcastPlan` manifest handoff
- daily report text output
- digital village newspaper draft JSON
- village notice text output
- Chinese TTS
- music source boundary
- FFmpeg mixing
- local playback
- fallback
- status JSON and dashboard
- tests and acceptance docs

Preserved for later:

- WeChat group source interface
- weather API source interface
- government website source interface
- voice transcript source interface
- community source interface

Do not claim:

- Do not claim real WeChat group, weather API, government website, or voice-source ingestion is connected.
- Do not claim complete 24-hour station scheduling is implemented.
- Do not claim public deployment, mini-program listening, rendered digital village newspaper product, or video generation is complete.
- Do not claim ACE-Step 1.7B real generation is verified on this machine.
- Do not claim synthetic fixture data is real village data.

## Emergency Path

If the generated demo feed path is interrupted, use the static manifest:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-demo --manifest demo/demo_manifest.json
```

If the dashboard is unavailable, continue with:

```bash
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli status
```
