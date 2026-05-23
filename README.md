# 剪鸭村融媒体

剪鸭村融媒体是面向村镇经济体的 AI 信息服务与内容工作流。本仓库交付第一条可运行产品线：伴农电台本地运行时，用结构化村庄信息生成可播放的中文电台段落，并提供 CLI、混音、fallback 和只读状态大屏。

对外项目名是“剪鸭村融媒体”。代码包名和 CLI 暂保留 `banong_radio` / `banong-radio`，避免破坏已经稳定的运行入口。

评委或现场演示请先读 [Judge Submission Pack](docs/judge-submission.md)，再按 [Live Demo Runbook](docs/live-demo-runbook.md) 操作。

## 1 分钟理解

| 问题 | 当前答案 |
| --- | --- |
| 面向谁 | 村两委、村书记、老人、新村民、离乡青年、文旅 / 农产品运营者 |
| 解决什么 | 把分散的村务通知、社区动态、农忙和在地内容组织成低门槛可听输出 |
| 当前能运行什么 | 从已确认的村庄信息 feed 生成可变时长 `BroadcastProgram`，也可生成 07:00-19:00 的 `daily_12h` 节目单和 3 段可渲染预览 manifest；同一上下文还可生成日报、数字村报草稿和村务通知 text output pack；本地链路支持 TTS、音乐、FFmpeg 混音、播放和状态大屏 |
| 当前不做什么 | 不接入真实微信群、天气 API、政府官网或口播转写；不实现完整 24 小时电台调度；不把 `daily_12h` 写成真实 12 小时全量音频或已接真实外部内容 API；不包含公网部署、小程序或视频生成 |
| 技术边界 | Runtime 只消费确认后的播放计划；音乐来源只通过 `MusicGenerator`；Mixer / Player 只处理本地音频路径 |

## 已实现

- CLI：`plan-broadcast`、`render-program`、`plan-workflow`、`plan-daily-schedule`、`render-daily-schedule`、`start-broadcast`、`status`、`stop`、`generate-segment`、`serve-status`、`preflight-ace`；旧 `start-demo` / `plan-demo-feed` 入口保留兼容。
- 可变节目编排：`ProgramPreset` 支持 `trailer_45s`、`briefing_3m`、`show_2h`、`daily_12h`，短预告只是节目 preset，不是系统上限。
- 十二小时节目单：`daily_12h` 输出 `DailySchedule`、`ProgramSlot`、`ContentAsset` JSON 和 3 段 preview manifest；长内容只走授权库存 / API contract 或本地 fallback，不直接生成 12 小时全量音频。
- 播放计划边界：`demo/demo_manifest.json` 会先转换为 `BroadcastPlan`，再进入本地音频运行时。
- 文字信息流入口：`SourceAdapter` 协议、`DemoVillageFeedAdapter`、真实输入源 adapter registry 和 adapter stub；stub 默认未配置，不访问外部世界。
- 文字处理链路：`RawTextItem -> SanitizedTextItem -> VillageSignal -> ContextPacket -> TaskBrief -> BroadcastProgram -> BroadcastPlan` 的最小确定性切片，不调用 LLM。
- 多输出文本包：同一套 demo `ContextPacket` 可生成日报、数字村报草稿和村务通知 JSON，不触碰 Radio Runtime。
- 官方 Agents SDK 编排：`--orchestrator sdk` 显式启用 `openai-agents`，由 `VillageMediaOrchestrator` 调度 `VillageSignalCollectorAgent`、`RadioDirectorAgent`、`PromptComposerAgent`、`ScriptwriterAgent`、`TextOutputEditorAgent`、`WorkflowReviewerAgent`，默认 local 路径仍不调用外部模型。
- 音乐来源边界：`MusicRequest` / `MusicResult` / `MusicGenerator`，支持 fallback 与显式 ACE-Step API 来源。
- fallback 安全链路：ACE-Step 不可用时仍可准备可播放 mp3。
- 中文 TTS：优先 `edge-tts`，本机不可用时降级到 macOS `say`。
- FFmpeg 混音：音乐底、中文串词、fade、ducking、amix、limiter。
- 只读状态大屏：本地 HTTP 页面轮询 `/status.json`。
- ACE-Step preflight：只检查环境，不下载模型、不生成音频。

## 当前边界

- 当前版本用 manifest / `BroadcastProgram` 代表已确认输入，不读取原始聊天记录、天气 API、政府网页或口播原文。
- `banong_radio.domain` 已提供 `RawTextItem`、`SanitizedTextItem`、`VillageSignal`、`ContextPacket`、`TaskBrief`、`BroadcastPlan` 等上游文字信息流数据边界；`banong_radio.text_flow` 已实现 demo feed adapter、real-source adapter registry、sanitizer、signal extractor、context builder、task planner 和 radio planner，但真实 SourceAdapter 尚未接入。
- `banong_radio.program` 已提供可变时长节目层；`banong_radio.schedule` 已提供 07:00-19:00 的 MVP 节目单层；`banong_radio.agent_contracts` 和 `banong_radio.sdk_workflow` 提供官方 OpenAI Agents SDK 的 opt-in 多 Agent 编排层。它不是自研 agent 框架；SDK 路径需要 `OPENAI_API_KEY`，并且失败时返回结构化错误，不自动伪装成本地成功。
- 当前本地播放链路的 TTS 与音乐听感已在 2026-05-23 由用户人工确认通过；ACE-Step 1.7B 真实生成仍不在已验证范围内。
- 本机官方 API 曾把请求的 `acestep-5Hz-lm-1.7B` 自动降级为 `acestep-5Hz-lm-0.6B`；不要把当前结果宣传为 1.7B 已真实生成验证。
- 本仓库不保存音频资产、模型权重、cache、日志或密钥。

## 运行方式

未安装为全局命令时，从仓库根目录运行：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli status
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-broadcast --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-program --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-daily-schedule
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-broadcast --manifest /Users/detroxryo/.cache/banong-radio/broadcast_manifest.json
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli stop
```

真实多 Agent 编排需要显式 opt-in，并要求环境中有 `OPENAI_API_KEY`：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-workflow --orchestrator sdk --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-program --orchestrator sdk --preset trailer_45s
```

启动只读状态大屏：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli serve-status
```

浏览器打开：

```text
http://127.0.0.1:8765/
```

检查 ACE-Step 环境：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli preflight-ace
```

生成产品化广播 manifest，并准备预告片 preset 的可播放资产：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-broadcast --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-program --preset trailer_45s
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-broadcast --manifest /Users/detroxryo/.cache/banong-radio/broadcast_manifest.json
```

`trailer_45s`、`briefing_3m`、`show_2h` 共享同一套节目抽象；切换 preset 改的是节目时长预算和结构，不会把系统锁死在 45 秒。`daily_12h` 是 schedule preset：它生成 07:00-19:00 节目单和预览 manifest，不要求一次性生成 12 小时音频。

生成 12 小时节目单和 3 段可渲染预览；不传 `--date` 时默认使用当天日期生成缓存键：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-daily-schedule --date 2026-05-24
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli render-daily-schedule --date 2026-05-24
```

显式启用 ACE-Step 音乐来源前，需要先启动官方 API。否则运行时会记录 fallback reason 并继续使用本地音频：

```bash
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
BANONG_MUSIC_SOURCE=ace-step PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-demo
```

从 synthetic village feed 生成 runtime manifest：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-feed
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli start-demo --manifest /Users/detroxryo/.cache/banong-radio/demo_feed_manifest.json
```

从同一份 synthetic village feed 生成日报、数字村报草稿和村务通知文本包：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m banong_radio.cli plan-demo-outputs
```

## 验证

最终提交验收使用 Python 3.10+。本机系统 `python3` 是 3.9，提交前请显式使用 `/Users/detroxryo/.local/bin/python3.11`：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
"$BANONG_PY" -m compileall -q src tests
```

如果安装了 `pytest`：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" -m pytest
```

如需补齐完整测试依赖，可在可联网环境创建本地 `.venv` 并安装测试 extra。`.venv/` 已被 `.gitignore` 忽略：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
/Users/detroxryo/.local/bin/python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
PYTHONPATH=src python -m pytest
```

当前提交验收不因本机缺少 `pytest` 阻塞。没有 `pytest` 时，至少运行 `compileall`、文档边界检查和直接断言验证 fallback asset preparation：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
PYTHONPATH=src "$BANONG_PY" - <<'PY'
from pathlib import Path
from banong_radio.runtime import ensure_playable_assets
segments = ensure_playable_assets(Path('demo/demo_manifest.json'))
assert len(segments) == 3
assert sorted({segment['music_source'] for segment in segments}) == ['fallback']
assert all(segment['id'] for segment in segments)
assert all(segment['playback_path'].endswith('.mp3') for segment in segments)
print({'segments': len(segments), 'music_source': sorted({segment['music_source'] for segment in segments})})
PY
```

文档边界检查可直接调用测试文件中的检查函数：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
BANONG_PY=/Users/detroxryo/.local/bin/python3.11
"$BANONG_PY" - <<'PY'
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

## 文档

- [Architecture](docs/architecture.md)
- [Operation](docs/operation.md)
- [Judge Submission Pack](docs/judge-submission.md)
- [Presentation Flow](docs/demo-flow.md)
- [Final Acceptance](docs/final-acceptance.md)
- [Live Demo Runbook](docs/live-demo-runbook.md)
- [Decisions](docs/decisions.md)

内部 Obsidian 项目脑：

```text
/Users/detroxryo/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/ai radio
```
