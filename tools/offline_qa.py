"""Bounded hardware-free QA launcher. Run with the task's pinned Python.

Usage: python tools/offline_qa.py --seconds 180 -- python -m pytest -q
Inherit HP437B_QA_DEADLINE (Unix seconds) to enforce a whole-task ceiling.
Only inspected Python test/build commands belong behind this accident guard.
"""

import argparse
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument(
        "--final", action="store_true", help="Verification/reporting in final reserve"
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command or not 0 < args.seconds <= 1800:
        parser.error("Provide a command and a limit in (0, 1800] seconds")
    global_end = float(os.environ.get("HP437B_QA_DEADLINE", time.time() + 14400))
    if not math.isfinite(global_end):
        parser.error("Global deadline must be finite")
    reserve = 0 if args.final else 1800
    budget = min(args.seconds, global_end - time.time() - reserve)
    if budget <= 0:
        return 124
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent / "offline_guard")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["HP437B_QA_DEADLINE"] = str(global_end)
    process = subprocess.Popen(command, env=env, cwd=args.cwd, start_new_session=True)
    try:
        return process.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        print("Offline QA deadline reached", file=sys.stderr)
        return 124
    finally:
        # Reap all owned descendants, even when their direct parent exits first.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=1)


if __name__ == "__main__":
    sys.exit(main())
