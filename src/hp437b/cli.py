"""Command-line software entry point: real USB access requires the explicit log command."""

import argparse
import json
import sys

from .commands import COMMANDS
from .errors import HP437BError
from .instrument import BUS_GUARDS, Instrument
from .logger import collect
from .simulation import DemoTransport
from .transport import VisaTransport


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="HP 437B control and finite CSV logging")
    sub = result.add_subparsers(dest="operation", required=True)
    sub.add_parser("capabilities", help="Show software coverage and guards without device I/O")
    for name in ("log", "demo"):
        command = sub.add_parser(
            name,
            help="Collect USB measurements"
            if name == "log"
            else "Write explicitly synthetic demo data",
        )
        if name == "log":
            command.add_argument("--resource", required=True, help="Explicit USB…::INSTR resource")
        command.add_argument("--output", required=True)
        bounds = command.add_mutually_exclusive_group()
        bounds.add_argument("--count", type=int, default=None)
        bounds.add_argument("--duration", type=float, default=None)
        command.add_argument("--interval", type=float, default=1.0)
        command.add_argument("--timeout", type=float, default=10.0)
        command.add_argument("--unit", choices=("W", "dBm"), default="dBm")
        command.add_argument("--meter-serial", default="unrecorded")
        command.add_argument("--sensor-serial", default="unrecorded")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.operation == "capabilities":
        print(
            json.dumps(
                {
                    "commands": {
                        spec.id: {"code": spec.code, "deferred": spec.deferred}
                        for spec in COMMANDS.values()
                    },
                    "bus_guards": BUS_GUARDS,
                },
                indent=2,
            )
        )
        return 0
    transport = None
    try:
        transport = DemoTransport() if args.operation == "demo" else VisaTransport(args.resource)
        instrument = Instrument(transport, timeout=args.timeout)
        record = collect(
            instrument,
            args.output,
            count=(
                None if args.duration is not None else (10 if args.count is None else args.count)
            ),
            duration=args.duration,
            interval=args.interval,
            unit=args.unit,
            simulation=args.operation == "demo",
            connect=(lambda: transport.open(args.timeout)) if args.operation == "log" else None,
            context={
                "resource": getattr(args, "resource", "synthetic"),
                "meter_serial": args.meter_serial,
                "sensor_serial": args.sensor_serial,
            },
        )
        print(
            json.dumps(
                {
                    "status": record["status"],
                    "rows": record["rows"],
                    "simulation": record["simulation"],
                }
            )
        )
        return 0
    except KeyboardInterrupt:
        print("Collection interrupted; inspect the session record before reuse.", file=sys.stderr)
        return 130
    except (HP437BError, ValueError, OSError) as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if transport is not None:
            transport.close()


if __name__ == "__main__":
    raise SystemExit(main())
