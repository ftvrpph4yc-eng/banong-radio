# Banong Radio

伴农电台是一个乡村黑客松 5-10 分钟 demo：通过飞书 / Hermes 指挥本地电台，生成或切换音乐、中文串词、混音和播放状态。

## Source Of Truth

项目知识中枢在 Obsidian：

`/Users/detroxryo/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/ai radio/00-项目索引.md`

运行代码在本目录。大模型、生成音频、缓存和日志不进入本仓库。

## Planned CLI

```bash
banong-radio start-demo
banong-radio generate-segment --mood "四坪夜晚" --source "群聊吐槽日报"
banong-radio status
banong-radio stop
```

During Phase 1, the CLI uses fallback audio so the demo can be heard before
ACE-Step is integrated. During Phase 2, it overlays short Chinese host scripts
using edge-tts when available and macOS `say` as a local fallback.

Phase 5 introduces a stable `MusicRequest` / `MusicResult` boundary in
`src/banong_radio/music.py`. The default implementation still uses local
fallback music. ACE-Step is available as an opt-in API-backed
`MusicGenerator`; Mixer and Player do not know which source produced
`song_path`.

Run the non-generating ACE-Step preflight:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src /Users/detroxryo/.local/bin/python3.11 -m banong_radio.cli preflight-ace
```

The default system `python3` is currently 3.9, so use Python 3.10+ for ACE-Step
or any future Agents SDK work.

For this Mac mini M4 16GB demo, the primary ACE-Step target is the official
macOS MLX backend with `acestep-v15-turbo` and `acestep-5Hz-lm-1.7B`. Keep XL
models and the 4B LM out of the live path unless they pass offline A/B testing.

The official checkout lives outside this project:

```text
/Users/detroxryo/Dev/Sandbox/ACE-Step-1.5
```

To opt into ACE-Step generation, start the official API server first, then set:

```bash
BANONG_MUSIC_SOURCE=ace-step
```

If the ACE-Step API is unavailable or generation fails, runtime asset
preparation falls back to local fallback audio and records
`fallback_reason=ace-step-error` in `music_metadata`.

Phase 10 generated one ACE-Step smoke-test file:

```text
/Users/detroxryo/Music/BanongRadio/generated/ace-step/longtan_morning.mp3
```

The file is technically valid audio, but still needs human listening approval
before replacing any demo segment. The official API automatically downgraded
the LM to `acestep-5Hz-lm-0.6B` on this machine even when `1.7B` was requested,
so treat the 1.7B path as unverified for real generation.

## Status Screen

Phase 3 adds a read-only local dashboard. It serves the static screen and the
runtime status JSON through the Python standard library:

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli serve-status
```

Open `http://127.0.0.1:8765/`. The page polls `/status.json`, which mirrors
`/Users/detroxryo/.cache/banong-radio/status.json`.

## Asset Paths

- Audio assets: `/Users/detroxryo/Music/BanongRadio`
- Runtime cache: `/Users/detroxryo/.cache/banong-radio`
- ACE-Step models: `/Users/detroxryo/.cache/ace-step/checkpoints`
- Hermes skill: `/Users/detroxryo/.hermes/profiles/feishu/skills/media/banong-radio`
