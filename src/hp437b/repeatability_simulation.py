"""WF-03 synthetic source cycles over unchanged Instrument/collect APIs."""

import platform
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from . import repeatability as w
from . import report_context, report_identity
from . import reporting as r
from . import stability_simulation as base
from .errors import OperationTimeout, ProtocolError, TransportError
from .instrument import Instrument
from .logger import collect
from .workflow_report import _seal, preflight

SCENARIOS = (
    "repeatable",
    "shifted",
    "unequal-counts",
    "partial-cycle",
    "missing-cycle",
    "cancel",
    "timeout",
    "malformed",
    "instrument-error",
    "source-off-failure",
    "still-on",
    "source-mismatch",
    "nonpositive",
    "initial-on",
)


class Bench(base.Bench):
    def __init__(self, scenario):
        super().__init__(scenario)
        self.cycle = None
        self.epoch = datetime.now(UTC)

    def event(self, operation, **fields):
        super().event(operation, cycle_id=self.cycle, **fields)

    def advance(self, seconds):
        if seconds < 0 or self.now + seconds > w.PROFILE["whole_run_ceiling_s"]:
            raise OperationTimeout("WF-03 virtual workflow budget exhausted")
        self.now += seconds

    def sleep(self, seconds):
        if self.stage == "C02-plateau" and self.scenario == "cancel" and self.reads == 3:
            raise KeyboardInterrupt("Synthetic between-read cancellation")
        if self.stage == "C03-plateau" and self.scenario == "partial-cycle" and self.reads == 11:
            raise KeyboardInterrupt("Synthetic partial third cycle")
        if self.stage == "C02-plateau" and self.scenario == "unequal-counts":
            seconds += 1
        self.advance(seconds)


class Wire(base.Wire):
    metadata = {"transport": "WF-03 explicit fake", "hardware": "none", "simulation": True}

    def write(self, data, deadline):
        if data in (b"OC0", b"OC1"):
            if self.closed or self.pending is not None:
                raise AssertionError("Overlapping/closed fake transaction")
            b = self.bench
            b.event("write", raw_hex=data.hex())
            b.local = False
            if data == b"OC0" and b.cycle == "C02":
                if b.scenario == "source-off-failure":
                    raise TransportError("Synthetic second-cycle off transfer failure")
                if b.scenario == "still-on":
                    return
            b.source = data == b"OC1"
            return
        super().write(data, deadline)

    def read(self, deadline):
        b = self.bench
        if self.closed or self.pending is None:
            raise AssertionError("No fake response pending")
        if self.pending == b"*IDN?":
            self.pending = None
            raw = b"HEWLETT-PACKARD,437B,SYNTHETIC-WF03,1.9\r\n"
            b.event("read", raw_hex=raw.hex())
            return raw
        if self.pending == b"TR2":
            self.pending = None
            b.reads += 1
            b.advance(0.02)
            raw = None
            if b.stage == "C02-plateau" and b.reads == 4:
                if b.scenario == "timeout":
                    b.event("read_error", reason="synthetic timeout")
                    raise OperationTimeout("Synthetic read timeout; no USB/native fault")
                if b.scenario == "malformed":
                    raw = b"MALFORMED\r\n"
                if b.scenario == "instrument-error":
                    raw = b"+9.0031E+40\r\n"
            if raw is None:
                value = D("0.001") if b.source else D("-0.00000002")
                if b.source and b.scenario in ("shifted", "unequal-counts"):
                    value = (D("0.001"), D("0.00099"), D("0.00101"), D("0.001"), D("0.001"))[
                        int(b.cycle[1:]) - 1
                    ]
                if b.source and b.scenario == "nonpositive":
                    value = D("-0.00000002")
                mantissa, exponent = format(value, "+.4E").split("E")
                raw = (mantissa + "E" + f"{int(exponent):+03d}" + "\r\n").encode("ascii")
            b.event("read", raw_hex=raw.hex())
            return raw
        if self.pending == b"SM" and b.stage == "C02-plateau" and b.scenario == "source-mismatch":
            # A complete but wrong-state response is a healthy policy failure.
            raw = bytearray(super().read(deadline))
            raw[16] = ord("0")
            raw = bytes(raw)
            b.event("injected_status_mismatch", raw_hex=raw.hex())
            return raw
        return super().read(deadline)


class StageInstrument(Instrument):
    def __init__(self, wire, source_on):
        super().__init__(wire, timeout=10)
        self.source_on = source_on

    def read_status(self):
        status = super().read_status()
        w.require_status(status.raw.hex(), self.source_on)
        return status

    def acquire(self, trigger="TR2"):
        result = super().acquire(trigger)
        if result.error_code:
            raise ProtocolError(f"WF-03 stops on complete instrument error {result.error_code}")
        return result


def run(
    output, scenario="repeatable", *, report_output=None, plots=True, criteria=None, operator=None
):
    w.p.require(scenario in SCENARIOS, "Unknown synthetic WF-03 scenario")
    w.validate_criteria(criteria)
    operator = report_context.resolve_operator(operator)["value"]
    output = Path(output).resolve()
    if report_output is not None:
        _, report_output = preflight(output, report_output, plots=plots)
    w.p.require(
        not output.exists() and not w.p.sidecar_path(output).exists(),
        "Capture/sidecar output already exists",
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "stages").mkdir()
    b = Bench(scenario)
    b.source = scenario == "initial-on"
    record = {
        "schema": w.SCHEMA,
        "workflow_id": w.WORKFLOW,
        "mode": "synthetic",
        "simulation": True,
        "run_id": str(uuid.uuid4()),
        "status": "running",
        "scenario": scenario,
        "profile": dict(w.PROFILE),
        "criteria": criteria,
        "operator": operator,
        "started_utc": b.utc().isoformat(),
        "subject": "Fictional POWER REF source - WF-03 simulation",
        "equipment": {
            "source": "SYNTHETIC-POWER-REF-WF03-50MHz",
            "meter": "SYNTHETIC-437B-WF03",
            "sensor": "SYNTHETIC-8482A-WF03",
            "adapter": "SYNTHETIC-WIRE-NO-USB",
        },
        "software": {
            **report_identity.identify(),
            "python": platform.python_version(),
            "runner_sha256": r.digest(Path(__file__).read_bytes()),
            "analysis_sha256": r.digest(Path(w.__file__).read_bytes()),
            "fake_helper_sha256": r.digest(Path(base.__file__).read_bytes()),
        },
        "preflight": {"status": "pending"},
        "stages": {stage: {"status": "pending"} for stage in w.STAGES},
        "cycles": [
            {
                "cycle_id": cid,
                "status": "pending",
                "source_on": {"status": "pending"},
                "source_off": {"status": "pending"},
                "off_wait": {"status": "pending"},
            }
            for cid in w.CYCLES
        ],
    }
    (output / "starting.json").write_bytes(r.encoded(record))
    for name, path in (
        ("simulation-source.txt", Path(__file__)),
        ("analysis-source.txt", Path(w.__file__)),
        ("fake-helper-source.txt", Path(base.__file__)),
    ):
        (output / name).write_bytes(path.read_bytes())
    active = None
    off_attempted = False
    activated = False

    def session(action, expected):
        if b.uncertain:
            raise ProtocolError("No new fake session after uncertain transaction")
        instrument = StageInstrument(Wire(b), expected)
        try:
            action(instrument)
        finally:
            b.uncertain |= instrument._uncertain
            try:
                instrument.close()
            except BaseException:
                b.uncertain = True
                raise

    def probe(i):
        i.configure_absolute("W")
        i.acquire()
        return i.read_status()

    def control(on, entry):
        nonlocal off_attempted, activated
        b.stage = f"{b.cycle}-source-" + ("on" if on else "off")
        entry.update(status="running", start_s=b.now)
        if on:
            activated = True
        else:
            off_attempted = True

        def action(i):
            i.command("OC1" if on else "OC0", confirmed=True)
            i.source_on = on
            entry["status_raw_hex"] = probe(i).raw.hex()

        try:
            session(action, b.source)
            entry.update(status="completed", end_s=b.now)
        except (Exception, KeyboardInterrupt) as exc:
            entry.update(
                status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                error=f"{type(exc).__name__}: {exc}",
                end_s=b.now,
            )
            raise

    def capture(stage, duration=None):
        b.stage, b.reads = stage, 0
        item = record["stages"][stage]
        item.update(status="running", start_s=b.now)
        instrument = StageInstrument(Wire(b), b.source)
        origin = b.now + 0.02
        try:
            collect(
                instrument,
                output / "stages" / f"{stage}.csv",
                count=None if duration else 3,
                duration=duration,
                interval=1,
                unit="W",
                simulation=True,
                clock=lambda: round(b.now - origin, 6),
                sleep=b.sleep,
                utcnow=b.utc,
                context={
                    "workflow_id": w.WORKFLOW,
                    "workflow_run_id": record["run_id"],
                    "stage_id": stage,
                    "cycle_id": b.cycle,
                    "mode": "synthetic",
                },
            )

            def verify(i):
                item["final_status_raw_hex"] = probe(i).raw.hex()

            session(verify, b.source)
            item.update(status="completed", end_s=b.now)
        except (Exception, KeyboardInterrupt) as exc:
            item.update(
                status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                end_s=b.now,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        finally:
            b.uncertain |= instrument._uncertain

    try:
        record["preflight"]["status"] = "running"
        b.stage = "preflight"
        session(lambda i: record["preflight"].update(status_raw_hex=probe(i).raw.hex()), False)
        record["preflight"]["status"] = "completed"
        capture("baseline-before")
        for active in record["cycles"]:
            b.cycle = active["cycle_id"]
            active.update(status="running", start_s=b.now)
            activated = False
            off_attempted = False
            if scenario == "missing-cycle" and b.cycle == "C03":
                raise KeyboardInterrupt(
                    "Synthetic third cycle unavailable; subsequent cycles not attempted"
                )
            control(True, active["source_on"])
            capture(b.cycle + "-settling", 20)
            capture(b.cycle + "-plateau", 30)
            control(False, active["source_off"])
            b.stage = b.cycle + "-off-wait"
            active["off_wait"].update(status="running", start_s=b.now)
            b.sleep(20)
            active["off_wait"].update(status="completed", duration_s=20, end_s=b.now)
            capture(b.cycle + "-off-baseline")
            active.update(status="completed", end_s=b.now)
        record["status"] = "completed"
    except (Exception, KeyboardInterrupt) as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        if record["preflight"]["status"] == "running":
            record["preflight"].update(status=record["status"], error=record["error"])
        if active is not None:
            active.update(status=record["status"], end_s=b.now, error=record["error"])
        if activated and not off_attempted and b.source and not b.uncertain:
            record["emergency_cleanup"] = {"status": "pending"}
            try:
                control(False, record["emergency_cleanup"])
            except (Exception, KeyboardInterrupt) as cleanup:
                record["cleanup_error"] = str(cleanup)
    for item in record["stages"].values():
        if item["status"] == "pending":
            item.update(status="skipped", reason="Earlier stage/control did not complete")
    for cycle in record["cycles"]:
        if cycle["status"] == "pending":
            cycle.update(status="skipped", reason="Earlier cycle did not complete")
        for key in ("source_on", "source_off", "off_wait"):
            if cycle[key]["status"] == "pending":
                cycle[key].update(status="skipped", reason="Cycle did not complete")
    record.update(
        finished_utc=b.utc().isoformat(),
        virtual_duration_s=b.now,
        final_state={
            "source": "unknown" if b.uncertain else "on" if b.source else "off",
            "local": "unknown" if b.uncertain else str(b.local).lower(),
        },
    )
    w.p.require(b.now <= 900, "WF-03 virtual ceiling exceeded")
    (output / "trace.json").write_bytes(r.encoded({"mode": "synthetic", "events": b.trace}))
    (output / "workflow.json").write_bytes(r.encoded(record))
    _seal(
        output,
        {
            "schema": "hp437b.repeatability-export.v1",
            "mode": "synthetic",
            "run_id": record["run_id"],
        },
    )
    w.load(output)
    if report_output is not None:
        w.publish(output, report_output, plots=plots, operator=operator)
    return record
