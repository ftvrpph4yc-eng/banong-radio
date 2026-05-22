# Operation

This document describes the local runtime path used by the 剪鸭村融媒体 radio product line. "Jianya Village Media" is only an English translation when needed; the external project name is 剪鸭村融媒体.

## Paths

| Purpose | Path |
| --- | --- |
| Code | `/Users/detroxryo/Dev/Sandbox/banong-radio` |
| Obsidian brain | `/Users/detroxryo/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/ai radio` |
| Audio assets | `/Users/detroxryo/Music/BanongRadio` |
| Runtime cache | `/Users/detroxryo/.cache/banong-radio` |
| ACE-Step checkout | `/Users/detroxryo/Dev/Sandbox/ACE-Step-1.5` |
| ACE-Step checkpoints | `/Users/detroxryo/.cache/ace-step/checkpoints` |

## Local Commands

Run from the repository root:

```bash
PYTHONPATH=src python3 -m banong_radio.cli status
PYTHONPATH=src python3 -m banong_radio.cli start-demo
PYTHONPATH=src python3 -m banong_radio.cli stop
```

`start-demo` is retained as the existing CLI name. In product language it starts the local presentation radio loop.

Queue a requested segment from Hermes or a local operator:

```bash
PYTHONPATH=src python3 -m banong_radio.cli generate-segment --mood "四坪夜晚" --source "群聊吐槽日报"
```

Serve the read-only status screen:

```bash
PYTHONPATH=src python3 -m banong_radio.cli serve-status
```

Open:

```text
http://127.0.0.1:8765/
```

## ACE-Step Preflight

Use Python 3.10+ for ACE-Step and future Agents SDK work. On this machine, use:

```bash
PYTHONPATH=src /Users/detroxryo/.local/bin/python3.11 -m banong_radio.cli preflight-ace
```

The preflight command must remain non-generating. It checks Python, CLI launchers, packages, independent checkout state, and model cache evidence. It does not download checkpoints, start model inference, or alter Mixer / Player behavior.

## Optional ACE-Step Source

The default source is fallback. ACE-Step is opt-in:

```bash
BANONG_MUSIC_SOURCE=ace-step PYTHONPATH=src /Users/detroxryo/.local/bin/python3.11 -m banong_radio.cli start-demo
```

If the official ACE-Step API is unavailable, times out, returns no audio, or downloads an empty file, runtime preparation falls back to local audio and records `fallback_reason=ace-step-error`.

Known caveat: the official API may auto-downgrade the requested `acestep-5Hz-lm-1.7B` to `acestep-5Hz-lm-0.6B` on this machine. Do not claim 1.7B real generation until server logs and listening evidence confirm it.

## Fallback Assets

At least these files should be available or generatable under `/Users/detroxryo/Music/BanongRadio/fallback`:

- `longtan_morning.mp3`
- `siping_night.mp3`
- `field_future.mp3`

Fallback generation uses FFmpeg synthetic tone/noise beds. These are not final creative assets; they keep the runtime path testable when model generation is unavailable.

## BroadcastPlan Boundary

The current demo manifest is treated as one input format for `BroadcastPlan`. It is not a live upstream data source. The first text-flow slice now sanitizes `RawTextItem -> SanitizedTextItem` with empty-text filtering, `item_id` deduplication, and sensitive-field redaction. Future village text-flow work should continue with `VillageSignal -> ContextPacket -> TaskBrief`, and only the confirmed radio task should become a `BroadcastPlan` for this runtime.

Mixer and Player continue to receive local audio paths only.

## Village Feed Fixture

`demo/village_feed.json` is a synthetic fixture for text-flow tests. `DemoVillageFeedAdapter` can read it and return `RawTextItem` values for public notice, weather, community, chat excerpt, and voice transcript examples.

The real-source adapter stubs for WeChat group, weather, public notice, voice transcript, and community sources are not configured by default. They raise `SourceAdapterNotConfigured` unless explicit fixture items are supplied by a test or later approved task. They do not read chat exports, call weather APIs, scrape government websites, or load voice originals.

## Verification

Compile:

```bash
python3 -m compileall -q src tests
```

Run tests if available:

```bash
PYTHONPATH=src python3 -m pytest
```

Install the optional test dependency only when a full local test run is needed:

```bash
python3 -m pip install -e ".[test]"
```

For submission prep on a machine without `pytest`, do not change runtime code just to satisfy the missing tool. The minimum acceptable verification is:

1. `python3 -m compileall -q src tests`
2. the direct documentation-boundary check below
3. the direct fallback assertion below
4. `PYTHONPATH=src python3 -m banong_radio.cli status`

Direct documentation-boundary check when `pytest` is unavailable:

```bash
python3 - <<'PY'
import runpy
ns = runpy.run_path('tests/test_docs.py')
for name in [
    'test_docs_do_not_claim_unimplemented_capabilities',
    'test_docs_keep_required_boundary_caveats',
    'test_docs_keep_sdk_only_agent_boundary',
]:
    ns[name]()
print({'docs_checks': 'pass', 'checked': 3})
PY
```

Direct fallback assertion when `pytest` is unavailable:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from banong_radio.runtime import ensure_playable_assets
segments = ensure_playable_assets(Path('demo/demo_manifest.json'))
assert len(segments) == 3
assert sorted({segment['music_source'] for segment in segments}) == ['fallback']
print({'segments': len(segments), 'source': sorted({segment['music_source'] for segment in segments})})
PY
```

Status endpoint smoke test:

```bash
PYTHONPATH=src python3 -m banong_radio.cli serve-status
curl -fsS http://127.0.0.1:8765/status.json
```

## Troubleshooting

| Problem | Check |
| --- | --- |
| No sound | output device, `afplay <file>`, current status `current_path` |
| TTS unavailable | `edge-tts`, macOS `say`, FFmpeg conversion |
| Mix fails | input files exist and `ffprobe` can read them |
| Status screen blank | `serve-status` running, `/status.json` returns JSON |
| ACE-Step slow or absent | use fallback, keep presentation moving |
| Unexpected 1.7B claim | inspect ACE-Step server logs for actual LM loaded |
