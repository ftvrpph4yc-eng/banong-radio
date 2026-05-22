# 剪鸭村融媒体

剪鸭村融媒体是一个面向乡村连接、治理和内容生产的智能融媒体项目。本仓库承载其中的本地 AI 电台运行时：把村庄信息、乡土语境、音乐生成、TTS、混音和状态展示组织成一条可验证的声音产品线。

对外项目名使用“剪鸭村融媒体”。当前代码包名和 CLI 仍保留 `banong_radio` / `banong-radio`，避免破坏已经稳定的运行入口。

## 赛事方向对齐

主办方强调“村镇经济体与 AI 乡村赋能”：跨越基础信息化阶段，探索 LLM、空间计算与复杂系统模拟在乡村经济体中的深度应用。

本项目当前选择一个可落地切口：先用 LLM / Agent 工作流把村务信息、社区动态和在地内容转成可听、可展示、可继续扩展的融媒体输出。电台不是终点，而是村镇经济体信息服务的第一个低门槛入口。

| 主办方方向 | 本项目对应 |
| --- | --- |
| Vibe Coding | 快速迭代出可运行的本地电台 runtime、状态大屏、CLI 和文档化验证路径 |
| OpenClaw / JAF | 用窄职责 Agent 工作流思路设计感知、合成、生成、调度层，后续可接外部编排 |
| 村务信息服务 | 以村书记口播、天气预警、农忙通知、群聊摘要为目标输入，解决村务信息到达问题 |
| 村镇经济体 | 把村务、文旅、农产品、社区动态处理成可传播内容资产，服务治理和经营 |

## 评分维度对齐

以下维度用于组织提交材料和路演证据；若没有官方最终评分细则来源，不把它们写成确定比例。

| 评分项 | 本项目证据 |
| --- | --- |
| 创新性 | 不做传统信息发布栏，而是把声音作为乡村 AI 信息服务入口；用 LLM / Agent 工作流把村庄数据转成媒体内容 |
| 乡村契合度 | 声音符合老人、村口广播、戏曲、收音机等乡村媒介习惯；信息源围绕村民群、新村民社区、村书记口播 |
| 技术难度 | 本地音乐生成接口、TTS、FFmpeg 混音、状态大屏、fallback、ACE-Step preflight、清晰模块边界和测试 |
| 完成度 | 已有可运行 CLI、可播放音频链路、可观察状态屏、可降级 fallback、可验证命令 |
| 市场契合度 | 面向村书记、老人、离乡青年、新村民、文旅/农产品运营者，覆盖村务服务和乡村内容经营 |

## 为什么是声音

乡村的信息断裂不是单一技术问题。老人、新村民、离乡青年、村书记和外部访客之间经常彼此听不见对方的声音。声音是乡村里门槛最低的媒介：不要求识字，不要求学习 App，也能像收音机和村口广播一样持续陪伴。

项目的第一条产品线是本地 AI 电台。它把分散信息编排成可听内容，用音乐、串词、台呼、转场和旁链压缩形成接近广播的听感。

## 信息源设计

参赛叙事中的信息源分三类：

- 村民群日常：乡村生活动态、邻里故事、农事经验和本地事件。
- 新村民社区动态：数字游民、创业者和外来参与者的生活分享、吐槽、项目进展。
- 村书记口播：政务通知、农忙信息、天气预警、紧急工作播报。

当前仓库没有接入完整三类真实数据源；运行时使用 manifest 中的结构化段落作为已验证输入。群聊脱敏、书记口述入口和数字村报属于后续产品线或上游数据处理能力。

## 四层智能架构

项目按四层理解，不把所有职责塞进一个万能 Agent：

- 感知层：把天气、政务、群聊、口述等原始信息转为结构化上下文。
- 合成层：把结构化内容编织成有乡土语境的播报稿，严肃通知和轻松段子分层处理。
- 生成层：根据文本情绪生成或选择音乐，生成中文语音。
- 调度层：生成播放计划，处理台呼、转场、音量闪避、播放和状态展示。

本仓库主要实现生成层和调度层中的本地电台运行时。上游感知和合成在当前版本用 manifest 合约代替。

## 当前已实现

- CLI 合约：`start-demo`、`status`、`stop`、`generate-segment`、`serve-status`、`preflight-ace`。
- 领域边界：`demo/demo_manifest.json` 会先转换为 `BroadcastPlan`，再进入本地音频运行时。
- 稳定音乐来源边界：`MusicRequest` / `MusicResult` / `MusicGenerator`。
- fallback 音频生成与缓存：ACE-Step 不可用时仍可完成本地播放链路。
- 中文 TTS：优先 `edge-tts`，本机不可用时降级到 macOS `say`。
- FFmpeg 混音：音乐底、中文串词、fade、ducking、amix、limiter。
- 只读状态大屏：本地 HTTP 页面轮询 `/status.json`。
- ACE-Step preflight：只检查环境，不下载模型、不生成音频。
- ACE-Step API 音乐来源：显式启用后调用官方 API，失败自动回到 fallback。

## 文字信息流边界

当前第一轮代码重构只落地边界，不接入真实微信群、天气 API、政府官网或口播转写。`banong_radio.domain` 中的 `RawTextItem`、`SanitizedTextItem`、`VillageSignal`、`ContextPacket`、`TaskBrief` 是后续上游文字信息流的稳定数据结构；现有 demo manifest 被视为 `BroadcastPlan` 的一种输入。

运行时仍只消费已经确认的 `BroadcastPlan` 段落，不读取原始聊天记录，也不让 Mixer / Player 感知上游数据源。

## 运行方式

未安装为全局命令时，从仓库根目录运行：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli status
PYTHONPATH=src python3 -m banong_radio.cli start-demo
PYTHONPATH=src python3 -m banong_radio.cli stop
```

启动只读状态大屏：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m banong_radio.cli serve-status
```

浏览器打开：

```text
http://127.0.0.1:8765/
```

检查 ACE-Step 环境：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src /Users/detroxryo/.local/bin/python3.11 -m banong_radio.cli preflight-ace
```

显式启用 ACE-Step 音乐来源前，需要先启动官方 API。否则运行时会记录 fallback reason 并继续使用本地音频：

```bash
BANONG_MUSIC_SOURCE=ace-step PYTHONPATH=src /Users/detroxryo/.local/bin/python3.11 -m banong_radio.cli start-demo
```

## 验证

基础语法验证：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
python3 -m compileall -q src tests
```

如果安装了 `pytest`：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 -m pytest
```

当前环境可能没有 `pytest`，可以用直接断言验证 fallback asset preparation：

```bash
cd /Users/detroxryo/Dev/Sandbox/banong-radio
PYTHONPATH=src python3 - <<'PY'
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

## 已知边界

- 当前仓库不实现完整 24 小时电台调度。
- 当前仓库不包含公网部署、小程序、数字村报或视频生成。
- 当前仓库不保存音频资产、模型权重、cache、日志或密钥。
- ACE-Step 单段 smoke 文件已经技术验证为非静音音频，但还需要人工听感确认。
- 本机官方 API 曾把请求的 `acestep-5Hz-lm-1.7B` 自动降级为 `acestep-5Hz-lm-0.6B`；不要把当前结果宣传为 1.7B 已真实生成验证。

## 文档

- [Architecture](docs/architecture.md)
- [Operation](docs/operation.md)
- [Presentation Flow](docs/demo-flow.md)
- [Decisions](docs/decisions.md)

内部 Obsidian 项目脑仍保留在：

```text
/Users/detroxryo/Library/Mobile Documents/com~apple~CloudDocs/Obsidian/ai radio
```
