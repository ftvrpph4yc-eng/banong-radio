"""Command line interface for the Jianya local radio runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from banong_radio.music import ace_step_preflight
from banong_radio.program import (
    build_broadcast_program_from_feed,
    write_broadcast_program_manifest,
)
from banong_radio.runtime import (
    CACHE_ROOT,
    PROJECT_ROOT,
    ensure_playable_assets,
    generate_segment,
    read_status,
    start_demo,
    stop_demo,
)
from banong_radio.status_server import serve_status_screen
from banong_radio.text_flow import (
    build_demo_feed_broadcast_plan,
    write_broadcast_plan_manifest,
)
from banong_radio.sdk_workflow import (
    SDKWorkflowError,
    build_local_workflow_artifacts,
    build_sdk_workflow_from_feed,
    write_agent_workflow_report,
    write_sdk_workflow_artifacts,
)
from banong_radio.text_outputs import (
    build_demo_feed_text_output_pack,
    write_text_output_pack,
)


class CliUsageError(Exception):
    def __init__(self, message: str, usage: str) -> None:
        super().__init__(message)
        self.message = message
        self.usage = usage.strip()


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message, self.format_usage())


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    parser = JsonArgumentParser(prog="banong-radio")
    sub = parser.add_subparsers(
        dest="command",
        parser_class=JsonArgumentParser,
        required=True,
    )

    start = sub.add_parser("start-demo", help="Start the local presentation radio loop.")
    start.add_argument("--manifest", default=str(PROJECT_ROOT / "demo/demo_manifest.json"))

    start_broadcast = sub.add_parser(
        "start-broadcast",
        help="Start the local AI broadcast loop from a prepared manifest.",
    )
    start_broadcast.add_argument(
        "--manifest",
        default=str(CACHE_ROOT / "broadcast_manifest.json"),
    )

    gen = sub.add_parser("generate-segment", help="Queue a requested radio segment.")
    gen.add_argument("--mood", required=True, help="Target mood.")
    gen.add_argument("--source", default="", help="Content source label.")

    sub.add_parser("status", help="Print current runtime status.")
    sub.add_parser("stop", help="Stop the local radio loop.")
    sub.add_parser("preflight-ace", help="Inspect local ACE-Step readiness without generation.")

    serve = sub.add_parser("serve-status", help="Serve the read-only status screen.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)

    plan_feed = sub.add_parser(
        "plan-demo-feed",
        help="Generate a runtime manifest from the synthetic village feed.",
    )
    plan_feed.add_argument("--feed", default=str(PROJECT_ROOT / "demo/village_feed.json"))
    plan_feed.add_argument(
        "--output",
        default=str(CACHE_ROOT / "demo_feed_manifest.json"),
    )
    plan_feed.add_argument("--date", default="")
    plan_feed.add_argument("--place", default="剪鸭村")

    plan_outputs = sub.add_parser(
        "plan-demo-outputs",
        help="Generate daily report, newspaper draft, and notices from the synthetic village feed.",
    )
    plan_outputs.add_argument("--feed", default=str(PROJECT_ROOT / "demo/village_feed.json"))
    plan_outputs.add_argument(
        "--output",
        default=str(CACHE_ROOT / "demo_text_outputs.json"),
    )
    plan_outputs.add_argument("--date", default="")
    plan_outputs.add_argument("--place", default="剪鸭村")

    plan_broadcast = sub.add_parser(
        "plan-broadcast",
        help="Generate a product broadcast manifest from the village feed.",
    )
    plan_broadcast.add_argument("--feed", default=str(PROJECT_ROOT / "demo/village_feed.json"))
    plan_broadcast.add_argument(
        "--output",
        default=str(CACHE_ROOT / "broadcast_manifest.json"),
    )
    plan_broadcast.add_argument("--preset", default="trailer_45s")
    plan_broadcast.add_argument("--date", default="")
    plan_broadcast.add_argument("--place", default="剪鸭村")
    plan_broadcast.add_argument("--orchestrator", choices=("local", "sdk"), default="local")
    plan_broadcast.add_argument(
        "--report-output",
        default=str(CACHE_ROOT / "agent_workflow_report.json"),
    )

    render_program = sub.add_parser(
        "render-program",
        help="Generate a product broadcast manifest and prepare playable audio assets.",
    )
    render_program.add_argument("--feed", default=str(PROJECT_ROOT / "demo/village_feed.json"))
    render_program.add_argument(
        "--output",
        default=str(CACHE_ROOT / "broadcast_manifest.json"),
    )
    render_program.add_argument("--preset", default="trailer_45s")
    render_program.add_argument("--date", default="")
    render_program.add_argument("--place", default="剪鸭村")
    render_program.add_argument("--orchestrator", choices=("local", "sdk"), default="local")
    render_program.add_argument(
        "--report-output",
        default=str(CACHE_ROOT / "agent_workflow_report.json"),
    )

    plan_workflow = sub.add_parser(
        "plan-workflow",
        help="Generate broadcast, text outputs, and workflow report from one feed.",
    )
    plan_workflow.add_argument("--feed", default=str(PROJECT_ROOT / "demo/village_feed.json"))
    plan_workflow.add_argument(
        "--broadcast-output",
        default=str(CACHE_ROOT / "broadcast_manifest.json"),
    )
    plan_workflow.add_argument(
        "--text-output",
        default=str(CACHE_ROOT / "demo_text_outputs.json"),
    )
    plan_workflow.add_argument(
        "--report-output",
        default=str(CACHE_ROOT / "agent_workflow_report.json"),
    )
    plan_workflow.add_argument("--preset", default="trailer_45s")
    plan_workflow.add_argument("--date", default="")
    plan_workflow.add_argument("--place", default="剪鸭村")
    plan_workflow.add_argument("--orchestrator", choices=("local", "sdk"), default="local")

    try:
        args = parser.parse_args()
        if args.command == "start-demo":
            result = start_demo(Path(args.manifest))
        elif args.command == "start-broadcast":
            result = start_demo(Path(args.manifest))
        elif args.command == "generate-segment":
            result = generate_segment(args.mood, args.source)
        elif args.command == "status":
            result = read_status()
        elif args.command == "stop":
            result = stop_demo()
        elif args.command == "preflight-ace":
            result = ace_step_preflight()
        elif args.command == "serve-status":
            serve_status_screen(args.host, args.port)
            return
        elif args.command == "plan-demo-feed":
            plan = build_demo_feed_broadcast_plan(
                Path(args.feed),
                date=args.date or None,
                place=args.place or None,
            )
            output_path = write_broadcast_plan_manifest(plan, Path(args.output))
            result = {
                "ok": True,
                "manifest_path": str(output_path),
                "plan_id": plan.plan_id,
                "source": plan.source,
                "segments": len(plan.segments),
            }
        elif args.command == "plan-demo-outputs":
            pack = build_demo_feed_text_output_pack(
                Path(args.feed),
                date=args.date or None,
                place=args.place or None,
            )
            output_path = write_text_output_pack(pack, Path(args.output))
            result = {
                "ok": True,
                "output_path": str(output_path),
                "pack_id": pack.pack_id,
                "source": pack.source,
                "daily_sections": len(pack.daily_report.sections),
                "newspaper_pages": len(pack.village_newspaper.pages),
                "notices": len(pack.notices),
            }
        elif args.command in {"plan-broadcast", "render-program"}:
            if args.orchestrator == "sdk":
                artifacts = build_sdk_workflow_from_feed(
                    Path(args.feed),
                    preset_name=args.preset,
                    date=args.date or None,
                    place=args.place or None,
                )
                program = artifacts.program
                report_path = write_agent_workflow_report(
                    artifacts.report,
                    Path(args.report_output),
                )
            else:
                program = build_broadcast_program_from_feed(
                    Path(args.feed),
                    preset_name=args.preset,
                    date=args.date or None,
                    place=args.place or None,
                )
                report_path = None
            output_path = write_broadcast_program_manifest(program, Path(args.output))
            result = {
                "ok": True,
                "orchestrator": args.orchestrator,
                "manifest_path": str(output_path),
                "program_id": program.program_id,
                "preset": program.preset.name,
                "target_duration": program.target_duration,
                "actual_duration": program.actual_duration,
                "segments": len(program.segments),
                "source": program.source,
            }
            if report_path is not None:
                result["report_path"] = str(report_path)
            if args.command == "render-program":
                playable_segments = ensure_playable_assets(output_path)
                result["playable_segments"] = len(playable_segments)
        elif args.command == "plan-workflow":
            if args.orchestrator == "sdk":
                artifacts = build_sdk_workflow_from_feed(
                    Path(args.feed),
                    preset_name=args.preset,
                    date=args.date or None,
                    place=args.place or None,
                )
            else:
                artifacts = build_local_workflow_artifacts(
                    Path(args.feed),
                    preset_name=args.preset,
                    date=args.date or None,
                    place=args.place or None,
                )
            broadcast_path, text_path, report_path = write_sdk_workflow_artifacts(
                artifacts,
                broadcast_output=Path(args.broadcast_output),
                text_output=Path(args.text_output),
                report_output=Path(args.report_output),
            )
            result = {
                "ok": True,
                "orchestrator": args.orchestrator,
                "manifest_path": str(broadcast_path),
                "output_path": str(text_path),
                "report_path": str(report_path),
                "program_id": artifacts.program.program_id,
                "pack_id": artifacts.text_outputs.pack_id,
                "preset": artifacts.program.preset.name,
                "segments": len(artifacts.program.segments),
                "daily_sections": len(artifacts.text_outputs.daily_report.sections),
                "newspaper_pages": len(artifacts.text_outputs.village_newspaper.pages),
                "notices": len(artifacts.text_outputs.notices),
            }
        else:
            parser.error(f"unknown command: {args.command}")
            return
    except CliUsageError as exc:
        print_json(
            {
                "ok": False,
                "error": "usage_error",
                "message": exc.message,
                "usage": exc.usage,
            }
        )
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        result = {
            "ok": False,
            "error": "command_failed",
            "cmd": exc.cmd,
            "stderr": exc.stderr,
        }
        print_json(result)
        sys.exit(1)
    except SDKWorkflowError as exc:
        print_json(
            {
                "ok": False,
                "error": exc.error_code,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        )
        sys.exit(1)
    except Exception as exc:
        print_json(
            {
                "ok": False,
                "error": "runtime_error",
                "error_type": exc.__class__.__name__,
                "message": str(exc),
            }
        )
        sys.exit(1)

    print_json(result)


if __name__ == "__main__":
    main()
