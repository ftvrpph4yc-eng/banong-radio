"""Command line interface for the Jianya local radio runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from banong_radio.music import ace_step_preflight
from banong_radio.runtime import (
    CACHE_ROOT,
    PROJECT_ROOT,
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

    try:
        args = parser.parse_args()
        if args.command == "start-demo":
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
