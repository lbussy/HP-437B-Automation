"""Explicit WF-02 fakes over the unchanged Instrument/collect APIs; virtual time only."""

import platform
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from . import report_context, report_identity
from . import reporting as r
from . import stability as s
from .errors import OperationTimeout, ProtocolError, TransportError
from .instrument import Instrument
from .logger import collect
from .simulation import status_fixture
from .workflow_report import _seal, preflight

SCENARIOS = (
    "constant",
    "ramp",
    "step",
    "missing-first",
    "missing-last",
    "irregular",
    "excess-drift",
    "timeout",
    "malformed",
    "cancel",
    "source-off-failure",
    "nonpositive",
)


class Bench:
    def __init__(self, scenario):
        self.scenario = scenario
        self.now = 0.0
        self.source = False
        self.local = True
        self.uncertain = False
        self.stage = "preflight"
        self.reads = 0
        self.origin = None
        self.trace = []

    def event(self, operation, **fields):
        self.trace.append(
            {
                "mode": "synthetic",
                "stage": self.stage,
                "elapsed_s": self.now,
                "operation": operation,
                **fields,
            }
        )

    def sleep(self, amount):
        if self.stage == "plateau" and self.scenario == "cancel" and self.reads == 4:
            raise KeyboardInterrupt("synthetic cancellation between completed transactions")
        if self.stage == "plateau" and self.scenario == "irregular":
            amount += (self.reads % 3) * 0.7
        self.now += amount

    def utc(self):
        return self.epoch + timedelta(seconds=self.now)


class Wire:
    capabilities = frozenset({"read", "write", "eom", "go_to_local"})
    metadata = {"transport": "WF-02 explicit fake", "hardware": "none", "simulation": True}

    def __init__(self, bench):
        self.bench = bench
        self.pending = None
        self.closed = False
        self.local_return = None
        bench.event("session_open")

    def write(self, data, deadline):
        if self.closed or self.pending is not None:
            raise AssertionError("Overlapping/closed fake transaction")
        b = self.bench
        b.event("write", raw_hex=data.hex())
        b.local = False
        if data in (b"OC0", b"OC1"):
            if data == b"OC0" and b.scenario == "source-off-failure":
                raise TransportError("synthetic source-off failure")
            b.source = data == b"OC1"
        elif data in (b"*IDN?", b"SM", b"TR2"):
            self.pending = data
        elif data not in (b"RL0", b"LN", b"TR3"):
            raise AssertionError(f"Unsupported fake operation {data!r}")

    def read(self, deadline):
        if self.pending is None or self.closed:
            raise AssertionError("No fake response")
        b = self.bench
        request, self.pending = self.pending, None
        if request == b"*IDN?":
            raw = b"HEWLETT-PACKARD,437B,SYNTHETIC-WF02,1.9\r\n"
        elif request == b"SM":
            raw = bytearray(status_fixture(logarithmic=False))
            raw[16] = ord("1" if b.source else "0")
            raw = bytes(raw)
        else:
            b.reads += 1
            if b.stage == "plateau" and b.reads == 4:
                if b.scenario == "timeout":
                    b.event("read_error", reason="synthetic timeout")
                    raise OperationTimeout("synthetic timeout; no USB/native timeout induced")
                if b.scenario == "malformed":
                    raw = b"MALFORMED\r\n"
                    b.event("read", raw_hex=raw.hex())
                    return raw
            if b.stage == "plateau" and b.reads == 2:
                b.origin = b.now
            b.now += 0.02
            value = Decimal("-0.00000002") if not b.source else Decimal("0.001")
            if b.stage == "plateau":
                elapsed = Decimal(str(b.now - (b.origin if b.origin is not None else b.now)))
                if b.scenario in ("ramp", "irregular", "excess-drift"):
                    value += elapsed * Decimal(
                        "0.0000001" if b.scenario == "excess-drift" else "0.00000001"
                    )
                elif b.scenario == "step" and elapsed >= 900:
                    value += Decimal("0.00005")
                elif b.scenario == "nonpositive":
                    value = Decimal("-0.00000002")
            mantissa, exponent = format(value, "+.4E").split("E")
            raw = (mantissa + "E" + f"{int(exponent):+03d}" + "\r\n").encode("ascii")
        b.event("read", raw_hex=raw.hex())
        return raw

    def return_local(self, deadline):
        self.bench.local = True
        self.local_return = {"status": "accepted", "mode": "synthetic"}
        self.bench.event("go_to_local")

    def close(self):
        if not self.closed:
            self.closed = True
            self.bench.event("session_close")


class StageInstrument(Instrument):
    def __init__(self, wire, source):
        super().__init__(wire)
        self.source = source

    def read_status(self):
        status = super().read_status()
        if (
            status.unit != "W"
            or status.reference_on != self.source
            or status.relative
            or status.offset_on
            or status.duty_on
            or status.measurement_error
            or status.entry_error
        ):
            raise ProtocolError("WF-02 stage precondition mismatch")
        return status

    def acquire(self, trigger="TR2"):
        value = super().acquire(trigger)
        if value.error_code:
            raise ProtocolError("WF-02 stops on instrument error")
        return value


def run(
    output, scenario="constant", *, report_output=None, plots=True, criteria=None, operator=None
):
    """Run a fixed 30-minute virtual profile. No physical factory/driver parameter exists."""
    s.p.require(scenario in SCENARIOS, "Unknown synthetic WF-02 scenario")
    s.validate_criteria(criteria)
    operator = report_context.resolve_operator(operator)["value"]
    output = Path(output).resolve()
    if report_output is not None:
        _, report_output = preflight(output, report_output, plots=plots)
    s.p.require(
        not output.exists() and not s.p.sidecar_path(output).exists(),
        "Capture/sidecar output already exists",
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "stages").mkdir()
    b = Bench(scenario)
    b.epoch = datetime.now(UTC)
    record = {
        "schema": s.SCHEMA,
        "workflow_id": s.WORKFLOW,
        "mode": "synthetic",
        "simulation": True,
        "run_id": str(uuid.uuid4()),
        "scenario": scenario,
        "status": "running",
        "started_utc": b.utc().isoformat(),
        "profile": dict(s.PROFILE),
        "criteria": criteria,
        "operator": operator,
        "subject": "Fictional POWER REF source — WF-02 simulation",
        "equipment": {
            "source": "SYNTHETIC-POWER-REF-50MHz-1mW",
            "meter": "SYNTHETIC-437B-WF02",
            "sensor": "SYNTHETIC-8482A-WF02",
            "adapter": "SYNTHETIC-WIRE-NO-USB",
        },
        "software": {
            **report_identity.identify(),
            "python": platform.python_version(),
            "runner_sha256": r.digest(Path(__file__).read_bytes()),
            "analysis_sha256": r.digest(Path(s.__file__).read_bytes()),
        },
        "stages": {name: {"status": "pending"} for name in s.STAGES},
    }
    (output / "starting.json").write_bytes(r.encoded(record))
    # Preserve inspectable producer snapshots as data only; reporting never executes them.
    (output / "simulation-source.txt").write_bytes(Path(__file__).read_bytes())
    (output / "analysis-source.txt").write_bytes(Path(s.__file__).read_bytes())

    def session(action, expected):
        instrument = StageInstrument(Wire(b), expected)
        try:
            action(instrument)
        finally:
            b.uncertain |= instrument._uncertain
            instrument.close()

    def control(on):
        def action(i):
            i.command("OC1" if on else "OC0", confirmed=True)
            i.source = on
            i.configure_absolute("W")
            i.acquire()
            i.read_status()

        session(action, b.source)

    def capture(stage, duration=None, offset=0):
        b.stage, b.reads = stage, 0
        record["stages"][stage] = {"status": "running", "window_offset_s": offset, "start_s": b.now}
        i = StageInstrument(Wire(b), b.source)
        # Normalize the fake clock after the setup read. This prevents floating-point
        # cancellation at finite-window boundaries without altering collect itself.
        capture_origin = b.now + 0.02
        try:
            collect(
                i,
                output / "stages" / f"{stage}.csv",
                count=None if duration else 3,
                duration=duration,
                interval=1,
                unit="W",
                simulation=True,
                clock=lambda: round(b.now - capture_origin, 6),
                sleep=b.sleep,
                utcnow=b.utc,
                context={
                    "workflow_id": s.WORKFLOW,
                    "workflow_run_id": record["run_id"],
                    "stage_id": stage,
                    "mode": "synthetic",
                },
            )

            def verify(i):
                i.configure_absolute("W")
                i.acquire()
                status = i.read_status()
                record["stages"][stage]["final_status_raw_hex"] = status.raw.hex()

            session(verify, b.source)
            record["stages"][stage].update(status="completed", end_s=b.now)
        finally:
            b.uncertain |= i._uncertain

    try:
        # All preflight/control/status requests go through the existing serialized API.
        session(lambda i: (i.configure_absolute("W"), i.acquire(), i.read_status()), False)
        capture("baseline-before")
        b.stage = "source-on"
        control(True)
        capture("settling", duration=20)
        offset = 300 if scenario == "missing-first" else 0
        if offset:
            b.now += offset
        capture(
            "plateau",
            duration=1500 if scenario in ("missing-first", "missing-last") else 1800,
            offset=offset,
        )
        if scenario in ("missing-first", "missing-last"):
            record["stages"]["plateau"]["status"] = "interrupted"
            record["status"] = "interrupted"
            record["error"] = "Synthetic endpoint window intentionally unavailable"
        else:
            record["status"] = "completed"
        b.stage = "source-off"
        control(False)
        capture("baseline-after")
    except (Exception, KeyboardInterrupt) as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        if b.stage in record["stages"]:
            record["stages"][b.stage].update(
                status=record["status"], end_s=b.now, error=record["error"]
            )
        if b.source and not b.uncertain:
            b.stage = "cleanup-source-off"
            try:
                control(False)
            except Exception as cleanup:
                b.uncertain = True
                record["cleanup_error"] = str(cleanup)
    for stage in s.STAGES:
        if record["stages"][stage]["status"] == "pending":
            record["stages"][stage] = {
                "status": "skipped",
                "reason": "Earlier stage/control did not complete",
            }
    record.update(
        finished_utc=b.utc().isoformat(),
        virtual_duration_s=b.now,
        final_state={
            "source": "unknown" if b.uncertain else "on" if b.source else "off",
            "local": "unknown" if b.uncertain else str(b.local).lower(),
        },
    )
    s.p.require(b.now <= s.PROFILE["whole_run_ceiling_s"], "Synthetic whole-run budget exceeded")
    (output / "trace.json").write_bytes(r.encoded({"mode": "synthetic", "events": b.trace}))
    (output / "workflow.json").write_bytes(r.encoded(record))
    _seal(
        output,
        {"schema": "hp437b.stability-export.v1", "mode": "synthetic", "run_id": record["run_id"]},
    )
    # A report error leaves this sealed capture intact, never repeats acquisition.
    s.load(output)
    if report_output is not None:
        s.publish(output, report_output, plots=plots, operator=operator)
    return record
