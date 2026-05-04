"""tbh-code CLI entry point.

Chapter 0: stub that accepts --mode and --task flags so the CLI is
callable from Chapter 1 validation tests.
Chapter 1: replace the stub body with the real one-shot and loop logic.
"""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tbh-code")
    parser.add_argument(
        "--mode",
        choices=["oneshot", "loop"],
        default="oneshot",
        help="Run mode: oneshot or loop (default: oneshot)",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task description for the agent",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Max loop iterations (loop mode only, default: 5)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Chapter 0 stub — implement real logic in Chapter 1.
    print(f"tbh-code ready | mode={args.mode} | task={args.task!r}")
    sys.exit(0)


if __name__ == "__main__":
    main()
