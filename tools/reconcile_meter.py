"""Opt-in supervised reconciliation of the current USBGpib/437B; never resumes tests.

--help is I/O-free. Normal hp437b logging is unchanged. No fault injection,
reference switching, USB reset, or adapter target selection is provided.
"""

import argparse
import json
import signal
import threading
from pathlib import Path

from hp437b.reconciliation_physical import PhysicalTarget, run_physical

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failed-run-id", required=True)
    parser.add_argument("--confirm-supervised", action="store_true")
    parser.add_argument("--confirm-prior-worker-stopped", action="store_true")
    args = parser.parse_args()
    if not args.confirm_supervised:
        parser.error("Fresh supervised setup confirmation is required before hardware access")
    if args.setup.stat().st_size > 16 * 1024:
        parser.error("Setup file exceeds 16 KiB")
    setup = json.loads(args.setup.read_text())
    stop = threading.Event()
    previous = signal.signal(signal.SIGINT, lambda *_: stop.set())
    try:
        result = run_physical(
            args.output,
            target=PhysicalTarget(
                args.resource,
                (args.resource.split("::")[3] if len(args.resource.split("::")) > 3 else ""),
                setup["expected_idn"].encode("ascii") + b"\r\n",
            ),
            prepared=setup["prepared"],
            equipment={key: setup[key] for key in ("meter_serial", "sensor_serial")},
            confirmed=args.confirm_supervised,
            prior_worker_stopped=args.confirm_prior_worker_stopped,
            workflow_lock_root=ROOT / "tmp/workflow-locks",
            failed_run_id=args.failed_run_id,
            cancelled=stop.is_set,
        )
    finally:
        signal.signal(signal.SIGINT, previous)
    print(
        json.dumps(
            dict(
                status=result["status"],
                reason=result["reason"],
                receipt=str(args.output / "reconciliation.json"),
            ),
            indent=2,
        )
    )
    return (
        0
        if result["status"] == "communication_reconciled"
        else 130
        if result["status"] == "cancelled"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
