"""Command line interface for the Banong Radio demo runtime."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from banong_radio.music import ace_step_preflight
from banong_radio.runtime import (
    PROJECT_ROOT,
    generate_segment,
    read_status,
    start_demo,
    stop_demo,
)
from banong_radio.status_server import serve_status_screen


def main() -> None:
    parser = argparse.ArgumentParser(prog="banong-radio")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start-demo", help="Start the local fallback radio loop.")
    start.add_argument("--manifest", default=str(PROJECT_ROOT / "demo/demo_manifest.json"))

    gen = sub.add_parser("generate-segment", help="Queue a requested demo segment.")
    gen.add_argument("--mood", required=True, help="Target mood.")
    gen.add_argument("--source", default="", help="Content source label.")

    sub.add_parser("status", help="Print current runtime status.")
    sub.add_parser("stop", help="Stop the local radio loop.")
    sub.add_parser("preflight-ace", help="Inspect local ACE-Step readiness without generation.")

    serve = sub.add_parser("serve-status", help="Serve the read-only status screen.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)

    args = parser.parse_args()

    try:
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
        else:
            parser.error(f"unknown command: {args.command}")
            return
    except subprocess.CalledProcessError as exc:
        result = {
            "ok": False,
            "error": "command_failed",
            "cmd": exc.cmd,
            "stderr": exc.stderr,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
