"""Explicit supervised source-off diagnostics; --help never opens hardware."""

import argparse
import json
import signal
import threading
from pathlib import Path

from hp437b.diagnostics_physical import run_physical
from hp437b.reconciliation_physical import PhysicalTarget

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workflow-lock-root", type=Path, default=ROOT / "tmp/workflow-locks")
    parser.add_argument("--confirm-supervised", action="store_true")
    parser.add_argument("--confirm-prior-worker-stopped", action="store_true")
    parser.add_argument("--include-latched-reads", action="store_true")
    parser.add_argument("--lifecycle", action="store_true")
    parser.add_argument(
        "--err-selection", action="store_true", help="QX-only query-order/timing experiment"
    )
    parser.add_argument("--confirm-fixed-error-fixtures", action="store_true")
    args = parser.parse_args()
    if args.lifecycle and args.err_selection:
        parser.error("Select only one fixed experiment")
    experiment = args.lifecycle or args.err_selection
    if experiment and (not args.confirm_fixed_error_fixtures or args.include_latched_reads):
        parser.error("Fixed experiment requires fixture confirmation and no passive latch flag")
    if args.confirm_fixed_error_fixtures and not experiment:
        parser.error("Fixed-error confirmation applies only to a fixed experiment")
    if not args.confirm_supervised or not args.confirm_prior_worker_stopped:
        parser.error("Fresh supervised setup and prior-worker-stop confirmation required")
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
                args.resource.split("::")[3] if len(args.resource.split("::")) > 3 else "",
                setup["expected_idn"].encode("ascii") + b"\r\n",
            ),
            prepared=setup["prepared"],
            equipment={key: setup[key] for key in ("meter_serial", "sensor_serial")},
            confirmed=args.confirm_supervised,
            prior_worker_stopped=args.confirm_prior_worker_stopped,
            workflow_lock_root=args.workflow_lock_root,
            include_latched_reads=args.include_latched_reads,
            lifecycle=args.lifecycle,
            err_selection=args.err_selection,
            confirmed_error_fixtures=args.confirm_fixed_error_fixtures,
            cancelled=stop.is_set,
        )
    finally:
        signal.signal(signal.SIGINT, previous)
    print(
        json.dumps(
            dict(status=result["status"], receipt=str(args.output / "diagnostics.json")), indent=2
        )
    )
    return 0 if result["status"] == "completed" else 130 if result["status"] == "cancelled" else 1


if __name__ == "__main__":
    raise SystemExit(main())
