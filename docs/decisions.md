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

## Keep task planning deterministic before output generation

`SignalExtractor`, `ContextBuilder`, and `TaskPlanner` use simple deterministic rules over sanitized demo text. They produce `VillageSignal`, `ContextPacket`, and `TaskBrief` objects, but they do not call an LLM and do not change the audio runtime. Radio output generation stays isolated in `RadioPlanner`.

## Generate radio plans through a manifest handoff

`RadioPlanner` converts a radio `TaskBrief` into a `BroadcastPlan` with runtime-compatible media segments, then the CLI can write that plan as a manifest. The runtime still enters through `start-demo --manifest`, so Mixer and Player continue to see only local audio segment paths and never upstream text-flow objects.

## Integrate ACE-Step behind `MusicGenerator`

ACE-Step must remain one music source implementation. Mixer, Player, status screen, and Hermes should not depend on ACE-Step details.

## Treat ACE-Step 1.7B as recommended but not verified

The recommended live configuration still points at `acestep-v15-turbo` and `acestep-5Hz-lm-1.7B`, but server logs showed automatic downgrade to `acestep-5Hz-lm-0.6B` on this machine. Submission material must preserve that caveat.

## Use SDK vocabulary only for future agent orchestration

If real external orchestration is added, use the official OpenAI Agents SDK concepts and package. Do not create a parallel local agent framework or new incompatible terminology.
