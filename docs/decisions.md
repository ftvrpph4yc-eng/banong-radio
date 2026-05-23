# Decisions

## Use "剪鸭村融媒体" as the external project frame

The external project is broader than one radio command-line tool. "剪鸭村融媒体" captures the product idea: village information can be processed once and expressed as radio, newspaper, web pages, and later video. "Jianya Village Media" may be used as a plain English translation when needed, but it is not a separate product name.

The repository remains the local radio runtime, not the entire future platform.

## Align with village economy and AI empowerment evidence

Documentation and presentation should organize evidence across innovation, rural fit, technical difficulty, completion, and market fit. Unless a final official scoring rule is available, these dimensions are material organization language rather than confirmed official weights.

The project should be framed as village information service and content workflow infrastructure, not only as a radio experience. The radio remains the first working output because it is the most rural-native interface.

## Keep `banong_radio` and `banong-radio`

The package name and CLI already work. Renaming them now would create avoidable breakage before submission. Product-facing copy can say "剪鸭村融媒体 / 伴农电台本地运行时" while code keeps stable names.

## GitHub is the primary submission surface

The code repository should show engineering quality directly: architecture, operation, decisions, tests, and limitations. Obsidian remains the internal brain for continuity and planning.

## Keep fallback as the live path

Fallback audio is a reliability boundary. It allows the local radio path, status screen, TTS, mixer, and player to keep working when ACE-Step is slow, unavailable, or unsuitable for live presentation.

## Treat manifest as a BroadcastPlan input

The demo manifest is not the long-term upstream model. It is the first concrete input that can be adapted into `BroadcastPlan`, while future text-flow work can produce the same plan through `RawTextItem`, `VillageSignal`, `ContextPacket`, and `TaskBrief` boundaries.

## Keep text sanitization pure and upstream of signal extraction

The sanitizer implementation only converts `RawTextItem` values into `SanitizedTextItem` values. It filters empty text, deduplicates by `item_id`, redacts obvious sensitive fields, and marks sanitized metadata, but it does not read real data sources or generate `VillageSignal`, `ContextPacket`, `TaskBrief`, or `BroadcastPlan` objects.

## Keep source adapters fixture-first

`DemoVillageFeedAdapter` is the only source adapter that runs without extra configuration, and it only reads the synthetic `demo/village_feed.json` fixture. Real-source adapter classes exist to preserve the architecture boundary, but they default to `SourceAdapterNotConfigured` and may return only explicitly supplied fixture items until a separate source-specific task is approved.

The preserved real-source adapter registry is intentionally explicit: `wechat_group`, `weather_api`, `government_website`, `voice_transcript`, and `community_source`. This lets a later task connect one approved source without deleting the other source interfaces or widening the live demo path.

## Keep task planning deterministic before output generation

`SignalExtractor`, `ContextBuilder`, and `TaskPlanner` use simple deterministic rules over sanitized demo text. They produce `VillageSignal`, `ContextPacket`, and `TaskBrief` objects, but they do not call an LLM and do not change the audio runtime. Radio output generation stays isolated in `RadioPlanner`.

## Generate radio plans through a manifest handoff

`RadioPlanner` converts a radio `TaskBrief` into a `BroadcastPlan` with runtime-compatible media segments, then the CLI can write that plan as a manifest. The product path now enters through `start-broadcast --manifest`, while `start-demo --manifest` remains a compatibility alias. Mixer and Player continue to see only local audio segment paths and never upstream text-flow objects.

## Add BroadcastProgram presets above BroadcastPlan

`BroadcastProgram` is the product-level program plan. `ProgramPreset` makes duration a preset decision, not a fixed system limit. The first presets are `trailer_45s`, `briefing_3m`, and `show_2h`; each can produce a runtime-compatible `BroadcastPlan` without changing Mixer or Player.

The short preview is therefore one program shape, not the maximum length of the station or future schedule. Its exact duration can stretch toward a minute when the music intro, host read, lift, and ending stinger need room.

## Generate multi-output text packs without touching audio runtime

Daily reports, digital village newspaper drafts, and village notices are generated as a deterministic text output pack from the same `ContextPacket` / `TaskBrief` boundary used by Radio. This proves the multi-output product path without connecting real sources, changing Mixer / Player, or claiming a rendered public newspaper product.

## Integrate ACE-Step behind `MusicGenerator`

ACE-Step must remain one music source implementation. Mixer, Player, status screen, and Hermes should not depend on ACE-Step details.

## Treat ACE-Step 1.7B as recommended but not verified

The recommended live configuration still points at `acestep-v15-turbo` and `acestep-5Hz-lm-1.7B`, but server logs showed automatic downgrade to `acestep-5Hz-lm-0.6B` on this machine. Submission material must preserve that caveat.

## Use official Agents SDK for opt-in orchestration

The repository now includes `openai-agents` as the only external agent framework. Default local commands remain deterministic and do not call external models. The explicit `--orchestrator sdk` path runs a real manager agent, `VillageMediaOrchestrator`, with specialist agents exposed as tools: `VillageSignalCollectorAgent`, `RadioDirectorAgent`, `PromptComposerAgent`, `ScriptwriterAgent`, `TextOutputEditorAgent`, and `WorkflowReviewerAgent`.

Do not create a parallel local agent framework or new incompatible terminology. The SDK path requires `OPENAI_API_KEY`; if it fails, it returns a structured SDK error instead of silently falling back to local output.
