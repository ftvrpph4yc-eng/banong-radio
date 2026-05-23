# Live Demo Runbook

This is the F-01 operator script for presenting 剪鸭村融媒体. It keeps the live path predictable and avoids changing scope during the presentation.

## Before Opening

Confirm the repository state:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
git status --short --branch
git log --oneline -3
python3 -m compileall -q src tests
```

Expected:

- working tree is clean
- `main` is aligned with `origin/main`
- compile gate passes

## Terminal 1: Status Screen

Start the read-only dashboard:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli serve-status
```

Open:

```text
http://127.0.0.1:8765/
```

Keep this terminal running during the demo. The status server is separate from the player process.

## Terminal 2: Demo Loop

Prepare the synthetic village feed as the runtime manifest:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli plan-demo-feed
```

Start the generated demo feed:

```bash
PYTHONPATH=src python3 -m banong_radio.cli start-demo --manifest /Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json
```

Check state:

```bash
PYTHONPATH=src python3 -m banong_radio.cli status
```

Stop playback:

```bash
PYTHONPATH=src python3 -m banong_radio.cli stop
```

Expected live evidence:

- `plan-demo-feed` writes `/Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json`
- `start-demo --manifest ...` reports `ok=true`
- dashboard changes from idle to playing
- status shows `playlist_total=5`
- `stop` returns the player to idle

## Talking Order

1. This is 剪鸭村融媒体, with local radio as the first runnable product line.
2. The input is a synthetic village feed, not private real chat data.
3. The code turns feed items into sanitized text, village signals, a context packet, a task brief, and then a `BroadcastPlan`.
4. The radio runtime consumes only the final manifest, so upstream text flow stays separate from Mixer and Player.
5. The live path uses TTS, music, FFmpeg mixing, local playback, and a read-only status screen.
6. Fallback is intentional reliability, not a failed model path.
7. Real WeChat group, weather API, government website, voice-source ingestion, public deployment, mini-program, digital newspaper, video, and full 24-hour scheduling are roadmap items.

## Accepted Demo Quality

The current demo TTS and music listening quality was manually accepted on 2026-05-23. This does not verify ACE-Step 1.7B real generation; keep the 1.7B caveat in all technical discussion.

## Emergency Path

If the generated demo feed path is interrupted, use the static manifest:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli start-demo --manifest demo/demo_manifest.json
```

If the dashboard is unavailable, continue with:

```bash
PYTHONPATH=src python3 -m banong_radio.cli status
```

If playback must stop immediately:

```bash
PYTHONPATH=src python3 -m banong_radio.cli stop
```

Do not debug real-source adapters, ACE-Step model downloads, public deployment, or new output products during the live demo.
