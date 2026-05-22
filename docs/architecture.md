# Architecture

剪鸭村融媒体的第一条可验证产品线是本地 AI 电台。本仓库不实现完整融媒体平台，而是把声音链路做成可运行、可审查、可降级的核心运行时。

## Hackathon Direction Mapping

主办方方向是“村镇经济体与 AI 乡村赋能”，并点名 Vibe Coding、OpenClaw / JAF、村务信息服务。本仓库的架构对齐方式如下：

| Direction | Architecture Response |
| --- | --- |
| Vibe Coding | Keep the runtime small, runnable, and easy to iterate through CLI, manifest, docs, and status screen |
| OpenClaw / JAF | Treat future orchestration as narrow Agent handoffs rather than a monolithic local framework |
| 村务信息服务 | Model village notices, weather, farming reminders, group-chat summaries, and secretary voice notes as upstream context |
| 村镇经济体 | Turn local information into reusable media assets that can support governance, tourism, agricultural products, and community operations |

## Product Layers

| Layer | Role | Current Repository Boundary |
| --- | --- | --- |
| 感知层 | 接收天气、政务、群聊、口述等输入，清洗为结构化上下文 | 已实现 `SourceAdapter` 协议、`DemoVillageFeedAdapter` 和 `RawTextItem -> SanitizedTextItem` 最小纯函数清洗，不接真实数据源 |
| 合成层 | 把结构化内容改写为乡土语境播报稿、摘要、故事或说和内容 | 当前只保留 `VillageSignal` / `ContextPacket` / `TaskBrief` 边界，用 manifest 中的 `intro_text` 代替 |
| 生成层 | 生成或读取音乐，生成中文 TTS | 已实现 `MusicGenerator`、fallback、ACE-Step API adapter、TTS adapter |
| 调度层 | 组织播放计划、混音、播放、状态展示 | 已实现 `BroadcastPlan` manifest adapter、CLI、FFmpeg mixer、afplay worker、status screen |

这种分层让参赛叙事可以讲清楚完整产品，同时不把尚未落地的上游数据源写成当前代码事实。

## Module Boundaries

| Module | Input | Output | Responsibility |
| --- | --- | --- | --- |
| CLI | user / Hermes command | JSON result | Stable local operation contract |
| Domain | manifest or future task brief | `BroadcastPlan`, `MediaSegment` | Keep upstream text-flow objects separate from audio runtime |
| SourceAdapter | synthetic fixture or explicitly configured source | `RawTextItem` list | Convert one upstream source shape into raw text without summary, planning, or runtime side effects |
| TextFlow | `RawTextItem` iterable | `SanitizedTextItem` list | Filter empty text, deduplicate by `item_id`, redact sensitive fields, and stop before signal or plan generation |
| Runtime | `BroadcastPlan`, env, status | prepared segments, status JSON | Orchestrate local playback preparation |
| MusicGenerator | `MusicRequest` | `MusicResult` | Generate or retrieve music from fallback or ACE-Step |
| SpeechSynthesizer | text, voice | mp3 path | Generate voice with `edge-tts` or macOS fallback |
| Mixer | music path, voice path | mixed mp3 path | Broadcast-like fade, ducking, amix, limiter |
| Player | playback path queue | runtime status | Play local audio and stop cleanly |
| Status screen | `status.json` | HTML / JSON evidence surface | Read-only presentation surface |

Mixer and Player consume file paths only. They do not know whether music came from local fallback, ACE-Step, cache, or any future source.

## SOLID Notes

- Single Responsibility: Obsidian records decisions, this repo runs the local radio path, assets live outside source control.
- Open/Closed: New music sources are added behind `MusicGenerator`; existing Mixer and Player code should not change.
- Liskov Substitution: every music source must return the same `MusicResult` shape.
- Interface Segregation: Hermes needs CLI commands and status only; the status page reads status only; audio code does not know group-chat internals.
- Dependency Inversion: high-level orchestration depends on stable request/result objects and CLI contracts, not concrete model APIs.

## SDK-only Agent Boundary

The project documentation uses the OpenAI Agents SDK vocabulary as the only external architecture reference. If a real external orchestrator is added later, use the official `openai-agents` package and keep roles narrow:

- `RadioDirector`: chooses the next segment from current state and sanitized context.
- `PromptComposer`: turns segment intent into music prompts and generation settings.
- `Scriptwriter`: writes short host scripts and anonymized summaries.
- `RuntimeOperator`: invokes this repository's CLI and reports status.

Do not add a separate local agent framework, and do not let a broad "Audio Producer" role absorb generation, TTS, mixing, and playback responsibilities.

## Safety and Privacy Boundaries

- Group-chat material must be sanitized upstream before becoming manifest input.
- Real-source adapter stubs default to not configured; they may return only explicitly supplied fixture items until a separate source-specific task is approved.
- Real names, private chat text, secrets, tokens, generated audio, and model weights do not enter this repository.
- Conflict mediation content should be transformed into anonymized stories or general guidance, not rebroadcast as the original dispute.
- ACE-Step failures must degrade to fallback audio instead of blocking the live path.

## Submission Evidence

These dimensions organize submission material. They should not be presented as confirmed official scoring weights unless final official rules are available.

| Dimension | Evidence in this repository |
| --- | --- |
| 创新性 | Voice-first AI media service instead of another village app or notice board |
| 乡村契合度 | Built around elders, village notices, local opera/radio habits, community groups, and secretary announcements |
| 技术难度 | Local runtime contracts, ACE-Step adapter, TTS, FFmpeg mix, fallback, status server, tests |
| 完成度 | Runnable CLI path, local dashboard, prepared manifest, fallback playback, documented verification |
| 市场契合度 | Serves village governance, community operations, cultural tourism, agricultural content, and returning youth |
