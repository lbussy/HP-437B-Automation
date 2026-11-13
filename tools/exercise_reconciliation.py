"""Exercise bounded reconciliation with explicit fakes; no hardware mode exists."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from hp437b.reconciliation import Target, run_simulated
from hp437b.simulation import DemoTransport, status_fixture

RESOURCE = "FAKE::REFERENCE-DEMO"
ADAPTER = "SYNTHETIC-ADAPTER-001"
IDN = b"HEWLETT-PACKARD,437B,,1.9\r\n"


class FakeReference(DemoTransport):
    capabilities = DemoTransport.capabilities | {"go_to_local"}

    def __init__(self, scenario, attempt):
        super().__init__()
        self.scenario, self.attempt = scenario, attempt
        self.metadata = dict(resource=RESOURCE, adapter_identity=ADAPTER)

    def open(self, timeout):
        if self.scenario == "absent-then-healthy" and self.attempt == 1:
            raise FileNotFoundError("Simulated adapter absent on first attempt")

    def write(self, data, deadline):
        if data == b"TR3":
            return
        super().write(data, deadline)

    def read(self, deadline):
        if self.pending == b"SM" and self.scenario == "source-on":
            self.pending = None
            status = bytearray(status_fixture())
            status[16] = ord("1")
            return bytes(status)
        return super().read(deadline)

    def return_local(self, deadline):
        return {"status": "accepted"}


@dataclass(frozen=True)
class FakeFactory:
    scenario: str
    simulation = True

    def __call__(self, resource, attempt):
        if resource != RESOURCE:
            raise ValueError("Unexpected simulated target")
        return FakeReference(self.scenario, attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scenario", choices=("healthy", "absent-then-healthy", "source-on"), default="healthy"
    )
    args = parser.parse_args()
    result = run_simulated(
        args.output,
        target=Target(RESOURCE, ADAPTER, IDN),
        factory=FakeFactory(args.scenario),
        lock_root=args.output.parent / ".reconciliation-demo-locks",
        failed_run_id="synthetic-failed-run",
        prior_worker_stopped=True,
    )
    print(
        json.dumps(
            dict(
                status=result["status"],
                reason=result["reason"],
                attempts=len(result["attempts"]),
                receipt=str(args.output / "reconciliation.json"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
