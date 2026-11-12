"""Physical WF-01 POWER REF runner; generic hp437b log is unchanged.

Requires explicit resource, prepared-setup JSON, and --confirm-prepared-reference.
Only the fixed supervised off/on/off profile is supported. No fault injection.
Use --help without opening hardware. QA must inject an explicit fake factory.
"""

import argparse
import fcntl
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from importlib.metadata import version
from pathlib import Path
from runpy import run_path

from hp437b.errors import OperationTimeout, ProtocolError
from hp437b.instrument import Instrument
from hp437b.logger import _atomic_json, collect
from hp437b.provenance import export_wf01, sidecar_path
from hp437b.transport import VisaTransport

ROOT = Path(__file__).resolve().parents[1]
INSPECT = run_path(str(ROOT / "tools/exercise_workflow.py"))["inspect_stage"]
SELECT_TARGET = run_path(str(ROOT / "tools/usbgpib_target.py"))["select_target"]
LIMITS = {"S00": 60, "S10": 90, "S20": 60, "S30": 90, "S40": 420, "S50": 20, "S60": 90, "S70": 30}
PREPARED = (
    "adapter_on_mac",
    "direct_sensor_reference_path",
    "reference_off",
    "warmed_up",
    "other_apps_closed",
    "operator_available",
)


def validate_setup(resource, setup, confirmed):
    if confirmed is not True or any(setup.get(key) is not True for key in PREPARED):
        raise ValueError(
            "Explicit prepared reference path, initial off, warm-up, exclusivity, and recovery confirmation required"
        )
    if not isinstance(setup.get("meter_serial"), str) or not setup["meter_serial"]:
        raise ValueError("Record the meter label identity")
    if not isinstance(setup.get("sensor_serial"), str) or not setup["sensor_serial"]:
        raise ValueError("Record the sensor label identity")
    if not isinstance(setup.get("known_issues"), list):
        raise ValueError("Record known equipment issues (empty list only if none reported)")
    if setup.get("select_adapter_target") is True:
        address = setup.get("adapter_target_address")
        if isinstance(address, bool) or not isinstance(address, int) or not 1 <= address <= 30:
            raise ValueError("Explicit adapter target address must be 1..30")
    json.dumps(setup, allow_nan=False)
    VisaTransport(resource)  # I/O-free validation of the explicit USB resource syntax.
    if sys.flags.optimize:
        raise ValueError("Optimized Python is unsupported by the prototype evidence validator")


@contextmanager
def ownership(resource):
    folder = ROOT / "tmp/workflow-locks"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (hashlib.sha256(resource.encode()).hexdigest() + ".lock")
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another WF-01 runner owns this resource") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class Controller:
    def __init__(self, output, record, clock, sleep, utcnow):
        self.output, self.record = output, record
        self.clock, self.sleep, self.utcnow = clock, sleep, utcnow
        self.started = clock()
        self.end = self.started + 900
        self.work_end = self.end - 60
        self.stage = "S00"
        self.stage_end = self.started + 60
        self.faulted = False
        self.activated = False
        self.off_attempted = False
        self.change_pending = False
        self.last_source = None
        self.local = "not verified"
        self.trace = []
        self.session_id = None

    def event(self, operation, **data):
        self.trace.append(
            {
                "mode": "physical",
                "stage": self.stage,
                "session": self.session_id,
                "elapsed_s": self.clock() - self.started,
                "utc": self.utcnow().isoformat(),
                "operation": operation,
                **data,
            }
        )

    def checkpoint(self):
        self.record.update(
            elapsed_s=self.clock() - self.started, checkpoint_utc=self.utcnow().isoformat()
        )
        self.record["final_state"] = self.state()
        _atomic_json(self.output / "workflow.json", self.record)
        _atomic_json(self.output / "trace.json", {"mode": "physical", "events": self.trace})

    def begin(self, stage, *, cleanup=False):
        self.stage = stage
        self.stage_end = min(
            self.clock() + (20 if cleanup else LIMITS[stage]),
            self.end - 30 if cleanup else self.work_end,
        )
        if self.stage_end <= self.clock():
            raise OperationTimeout("Workflow has no remaining stage budget")
        if not cleanup:
            self.record["stages"][stage] = {
                "status": "running",
                "start_s": self.clock() - self.started,
            }
            self.checkpoint()

    def done(self):
        self.record["stages"][self.stage].update(
            status="completed", end_s=self.clock() - self.started
        )
        self.checkpoint()

    def deadline(self, requested):
        cap = min(requested, self.stage_end)
        if self.clock() >= cap:
            raise OperationTimeout("WF-01 stage deadline expired")
        return cap

    def wait(self, seconds):
        if seconds < 0 or self.clock() + seconds >= self.stage_end:
            raise OperationTimeout("Insufficient workflow stage time for wait")
        self.sleep(seconds)
        self.deadline(self.stage_end)

    def observe(self, status):
        self.last_source = status.reference_on
        self.change_pending = False
        data = asdict(status)
        data["raw"] = status.raw.hex()
        self.event("fresh_status", status=data)

    def state(self):
        source = (
            "unknown"
            if self.faulted or self.change_pending or self.last_source is None
            else ("on" if self.last_source else "off")
        )
        return {
            "source": source,
            "last_observed_source_on": self.last_source,
            "local": self.local if not self.faulted else "unknown",
            "front_panel_confirmation": "pending",
            "origin": "physical protocol observations; local control status is not a front-panel observation",
        }


class RecordedWire:
    def __init__(self, wire, controller):
        self.wire, self.controller = wire, controller
        self.closed = False

    def __getattr__(self, name):
        return getattr(self.wire, name)

    def call(self, operation, action, **evidence):
        controller = self.controller
        if controller.faulted:
            raise ProtocolError("Workflow protocol is uncertain; no new transaction permitted")
        controller.event(operation + "_start", **evidence)
        try:
            result = action()
        except BaseException as exc:
            controller.faulted = True
            controller.event(operation + "_error", error=f"{type(exc).__name__}: {exc}")
            raise
        controller.event(
            operation + "_complete",
            **({"raw_hex": result.hex()} if isinstance(result, bytes) else {}),
        )
        return result

    def open(self):
        self.call(
            "open",
            lambda: self.wire.open(
                min(
                    10,
                    self.controller.deadline(self.controller.stage_end) - self.controller.clock(),
                )
            ),
        )
        self.controller.event(
            "transport",
            metadata=dict(self.wire.metadata),
            capabilities=sorted(self.wire.capabilities),
        )
        if "go_to_local" not in self.wire.capabilities:
            raise ProtocolError("WF-01 requires the previously negotiated local-return profile")

    def write(self, data, deadline):
        self.controller.local = "not verified (active session)"
        self.call(
            "write",
            lambda: self.wire.write(data, self.controller.deadline(deadline)),
            raw_hex=data.hex(),
        )

    def read(self, deadline):
        return self.call("read", lambda: self.wire.read(self.controller.deadline(deadline)))

    def return_local(self, deadline):
        result = self.call(
            "go_to_local", lambda: self.wire.return_local(self.controller.deadline(deadline))
        )
        if self.wire.local_return.get("status") != "accepted":
            raise ProtocolError("Local-return status was not accepted")
        self.controller.local = "USB488 GTL accepted; front panel not yet confirmed"
        return result

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.wire.close()
            except BaseException as exc:
                self.controller.faulted = True
                self.controller.event("transport_close_error", error=f"{type(exc).__name__}: {exc}")
                raise
            self.controller.event(
                "transport_closed",
                read_deadline_cleanup=getattr(self.wire, "read_deadline_cleanup", None),
                local_return=getattr(self.wire, "local_return", None),
            )


class WorkflowInstrument(Instrument):
    def __init__(self, wire, controller, expected_source):
        super().__init__(wire, timeout=10)
        self.controller, self.expected_source = controller, expected_source

    @contextmanager
    def _operation(self):
        with super()._operation() as deadline:
            try:
                yield self.controller.deadline(deadline)
            except BaseException:
                self.controller.faulted = True
                raise

    def read_status(self):
        status = super().read_status()
        self.controller.observe(status)
        if (
            status.unit != "W"
            or status.reference_on != self.expected_source
            or status.operating_mode != 0
            or status.relative
            or status.offset_on
            or status.duty_on
            or status.measurement_error
            or status.entry_error
            or status.range_code not in range(11, 16)
            or status.filter_code not in range(10, 20)
        ):
            raise ProtocolError(
                "WF-01 status/source/correction precondition mismatch; settings not repaired"
            )
        return status

    def acquire(self, trigger="TR2"):
        result = super().acquire(trigger)
        if result.error_code:
            raise ProtocolError(
                f"WF-01 stops on complete instrument-error sentinel {result.error_code}"
            )
        return result


def physical_report(record, analysis):
    lines = [
        "# WF-01 POWER REF measurement report",
        "",
        "**PHYSICAL RUN — current meter and sensor; descriptive measurement report.**",
        "",
        f"Execution: **{record['status']}**. Run: `{record['run_id']}`. Host elapsed: {record['elapsed_s']:.3f} s.",
        "",
        "## Provenance and configuration",
        "",
        "Nominal source: internal POWER REF, 50 MHz / 1 mW. W, automatic range/filter required, 1-second requested interval, 300-second sustained acquisition-start window, 10-second operations. Setup/probe readings are excluded from CSV counts. No zero/CAL/factor/preset/reset command is issued.",
        "",
        "Supplied equipment/setup record (historical fields retain their observation dates):",
        "",
        "```json",
        json.dumps(record["setup"], indent=2),
        "```",
        "",
        "Observed identities, raw status, command/reply frames, source observations, dependency versions, and cleanup outcomes are retained in workflow.json and trace.json. Meter label identity is supplied provenance; a blank ID serial does not independently verify the label. The documented +5 V issue remains a measurement limitation, not a software-project gate.",
        "",
        "## Stage outcomes",
        "",
        "| Stage | State | Reason |",
        "| --- | --- | --- |",
    ]
    for stage, item in record["stages"].items():
        error = item.get("error", "").replace("|", "/").replace("\n", " ")
        lines.append(f"| {stage} | {item['status']} | {error} |")
    lines += [
        "",
        "## Results from saved CSV evidence",
        "",
        "| Stage | Attempted / valid / nonvalid | Mean (mW) | Min / max (mW) | Peak-to-peak (mW) | Sample SD (mW) | Median receipt spacing (s) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for stage, result in analysis["stages"].items():

        def metric(name, result=result):
            value = result["metrics"][name]
            return f"{Decimal(value) * 1000:.6g}" if value is not None else "undefined"

        lines.append(
            f"| [{stage}]({result['csv']}) | {result['attempted']} / {result['valid']} / {result['nonvalid']} | {metric('mean_W')} | {metric('min_W')} / {metric('max_W')} | {metric('peak_to_peak_W')} | {metric('sample_sd_W')} | {result['median_receipt_spacing_s']} |"
        )
    lines += [
        "",
        f"Data integrity: **{analysis['integrity']}**. Measurement criteria: **not evaluated** (no accuracy/stability acceptance limits supplied).",
        "",
        "Comparisons (W / percent as keyed; null means unavailable):",
        "",
        "```json",
        json.dumps(analysis["comparisons"], indent=2),
        "```",
        "",
        "These are sample-weighted statistics; sample SD uses n−1 and is not measurement uncertainty. Source-off values may be negative/below the normal sensor range and are descriptive baselines, not calibrated low-power results or corrections. Six significant digits is display/computational rounding, not an accuracy claim. Nominal difference does not establish calibration or equipment compliance. Invalid rows remain diagnostic and are excluded from numerical summaries.",
        "",
        "## Final state",
        "",
        "Emergency cleanup: "
        + record.get("emergency_cleanup", "not required / not permitted after uncertainty")
        + ".",
        "",
        "```json",
        json.dumps(record["final_state"], indent=2),
        "```",
        "",
        "Fresh status documents observation points, not continuous source state at every sample. GTL acceptance alone does not prove RMT off or working controls; front-panel confirmation is recorded separately. Failed/uncertain I/O stops further instrument traffic and can require manual source-off/local recovery.",
        "",
        "## Evidence and reproducibility",
        "",
        "[Manifest](workflow.json), [analysis](analysis.json), [transaction trace](trace.json), [artifact hashes](artifacts.json), and CSV/session pairs. The bundle includes definition, runner/helper/runtime snapshots, setup inputs, and original notices. Bundle completeness requires the final manifest/hash inventory to agree. No automatic measurement retry, induced physical fault, independent accuracy test, plot rendering, or external agent call occurred. Narrative is deterministic.",
        "",
    ]
    return "\n".join(lines)


def execute(
    output,
    resource,
    setup,
    *,
    confirmed=False,
    factory=VisaTransport,
    clock=time.monotonic,
    sleep=time.sleep,
    utcnow=lambda: datetime.now(UTC),
):
    validate_setup(resource, setup, confirmed)
    with ownership(resource):
        output = Path(output)
        if sidecar_path(output).exists():
            raise FileExistsError("Provenance sidecar path already exists")
        output.mkdir()
        (output / "stages").mkdir()
        record = {
            "mode": "physical",
            "simulation": False,
            "workflow_id": "power-reference-v1",
            "run_id": str(uuid.uuid4()),
            "resource": resource,
            "setup": setup,
            "status": "running",
            "started_utc": utcnow().isoformat(),
            "stages": {s: {"status": "pending"} for s in LIMITS},
            "sessions": [],
            "software": {
                "commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "dirty": bool(
                    subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
                ),
                "python": platform.python_version(),
                "dependencies": {name: version(name) for name in ("PyVISA", "PyVISA-py", "PyUSB")},
            },
            "profile": {
                "unit": "W",
                "requested_interval_s": 1,
                "duration_s": 300,
                "timeout_s": 10,
                "outer_budget_s": 900,
            },
        }
        control = Controller(output, record, clock, sleep, utcnow)
        control.checkpoint()
        snapshots = {
            "runner.py": Path(__file__),
            "helper.py": ROOT / "tools/exercise_workflow.py",
            "adapter_helper.py": ROOT / "tools/usbgpib_target.py",
            "definition.md": ROOT / "docs/workflows/POWER-REFERENCE-V1.md",
            "LICENSE": ROOT / "LICENSE",
            "THIRD_PARTY_NOTICES.md": ROOT / "THIRD_PARTY_NOTICES.md",
        }
        import hp437b

        for path in Path(hp437b.__file__).parent.glob("*.py"):
            snapshots["runtime/" + path.name] = path
        for name, path in snapshots.items():
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(path.read_bytes())
        _atomic_json(output / "setup.json", setup)

        @contextmanager
        def session(expected):
            if control.faulted:
                raise ProtocolError("No new session after an uncertain transaction")
            control.session_id = str(uuid.uuid4())
            details = {"session": control.session_id, "stage": control.stage}
            record["sessions"].append(details)
            wire = RecordedWire(factory(resource), control)
            instrument = None
            try:
                wire.open()
                instrument = WorkflowInstrument(wire, control, expected)
                identity = instrument.identify()
                identity_data = asdict(identity)
                identity_data["raw"] = identity.raw.hex()
                details["identity"] = identity_data
                if "adapter_target_preparation" in record:
                    record["adapter_target_preparation"]["subsequent_instrument_identity"] = (
                        identity_data
                    )
                if (
                    setup.get("expected_firmware")
                    and identity.firmware != setup["expected_firmware"]
                ):
                    raise ProtocolError("Unexpected instrument firmware; identity mismatch")
                yield instrument, wire
            finally:
                try:
                    if instrument is not None:
                        instrument.close()
                finally:
                    wire.close()
                    if instrument is not None:
                        details["cleanup"] = instrument.cleanup
                    details["local_return"] = getattr(wire, "local_return", None)
                    details["read_deadline_cleanup"] = getattr(wire, "read_deadline_cleanup", None)

        def probe(instrument):
            instrument.configure_absolute("W")
            value = instrument.acquire()
            control.event("setup_probe", value_W=str(value.value), raw_hex=value.raw.hex())
            return instrument.read_status()

        def switch(on):
            with session(on) as (instrument, _):
                control.activated |= on
                control.off_attempted |= not on
                control.change_pending = True
                instrument.command("OC1" if on else "OC0", confirmed=True)
                if on:
                    control.wait(20)
                probe(instrument)

        def capture(stage, expected, duration=None):
            control.begin(stage)
            with session(expected) as (instrument, _):
                collect(
                    instrument,
                    output / "stages" / f"{stage}.csv",
                    count=None if duration else 3,
                    duration=duration,
                    interval=1,
                    unit="W",
                    simulation=False,
                    clock=clock,
                    sleep=control.wait,
                    utcnow=utcnow,
                    context={
                        "workflow_id": record["workflow_id"],
                        "workflow_run_id": record["run_id"],
                        "stage_id": stage,
                        "mode": "physical",
                        "resource": resource,
                        "meter_serial": setup["meter_serial"],
                        "sensor_serial": setup["sensor_serial"],
                    },
                )
            with session(expected) as (instrument, _):
                probe(instrument)
            control.done()

        try:
            control.begin("S00")
            if setup.get("select_adapter_target") is True:
                try:
                    record["adapter_target_preparation"] = SELECT_TARGET(
                        resource,
                        setup["adapter_target_address"],
                        deadline=control.deadline(clock() + 20),
                        event=control.event,
                    )
                    control.checkpoint()
                except BaseException:
                    control.faulted = True
                    raise
            with session(False) as (instrument, _):
                probe(instrument)
            control.done()
            capture("S10", False)
            control.begin("S20")
            switch(True)
            control.done()
            capture("S30", True)
            capture("S40", True, duration=300)
            control.begin("S50")
            switch(False)
            control.done()
            capture("S60", False)
            # Independent free-run check: no fresh trigger in this final session.
            with session(False) as (instrument, _):
                status = instrument.read_status()
                display = instrument.query("OD").value
                control.event("free_run_display", text=display, standby=status.standby)
                if (
                    status.standby
                    or "TRIGGER" in display.upper()
                    or not any(c.isdigit() for c in display)
                ):
                    raise ProtocolError("Final free-run/numeric display check failed")
            record["status"] = "completed"
        except BaseException as exc:
            if not isinstance(exc, (Exception, KeyboardInterrupt)):
                raise
            record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            record["stages"][control.stage].update(
                status=record["status"],
                error=f"{type(exc).__name__}: {exc}",
                end_s=clock() - control.started,
            )
            # Complete parsed instrument errors/policy mismatches can be healthy.
            # Failed/uncertain transfers never lead to another cleanup transaction.
            if (
                control.activated
                and not control.off_attempted
                and not control.faulted
                and (control.change_pending or control.last_source is not False)
            ):
                try:
                    control.begin("S50", cleanup=True)  # No disk write before source-off.
                    switch(False)
                    record["emergency_cleanup"] = "reference off verified"
                except BaseException as cleanup:
                    record["emergency_cleanup"] = f"failed: {type(cleanup).__name__}: {cleanup}"
            for item in record["stages"].values():
                if item["status"] == "pending":
                    item.update(status="skipped", error="prior stage did not complete")
        record["stages"]["S70"] = {"status": "running", "start_s": clock() - control.started}
        control.checkpoint()
        analysis = {
            "mode": "physical",
            "integrity": "pass",
            "measurement_criteria": "not_evaluated",
            "stages": {},
        }
        for path in sorted((output / "stages").glob("*.csv")):
            try:
                analysis["stages"][path.stem] = INSPECT(path, mode="physical")
            except Exception as error:
                analysis["integrity"] = "fail"
                analysis.setdefault("errors", []).append(
                    f"{path.name}: {type(error).__name__}: {error}"
                )
                record["status"] = "failed"

        def mean(stage):
            value = analysis["stages"].get(stage, {}).get("metrics", {}).get("mean_W")
            return Decimal(value) if value is not None else None

        comparisons = {}
        with localcontext() as context:
            context.prec = 34
            for label, a, b in (
                ("short_to_sustained_mean_change_W", "S30", "S40"),
                ("baseline_mean_change_W", "S10", "S60"),
            ):
                before, after = mean(a), mean(b)
                comparisons[label] = (
                    str(after - before) if before is not None and after is not None else None
                )
            sustained = mean("S40")
            comparisons["nominal_delta_W"] = (
                str(sustained - Decimal(".001")) if sustained is not None else None
            )
            comparisons["nominal_delta_percent"] = (
                str(100 * (sustained - Decimal(".001")) / Decimal(".001"))
                if sustained is not None
                else None
            )
        analysis["comparisons"] = comparisons
        record.update(
            elapsed_s=clock() - control.started,
            finished_utc=utcnow().isoformat(),
            final_state=control.state(),
        )
        record["stages"]["S70"].update(status="completed", end_s=clock() - control.started)
        _atomic_json(output / "analysis.json", analysis)
        _atomic_json(output / "trace.json", {"mode": "physical", "events": control.trace})
        with (output / "report.md").open("x", encoding="utf-8") as handle:
            handle.write(physical_report(record, analysis))
        inventory = {
            str(path.relative_to(output)): {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in output.rglob("*")
            if path.is_file() and path.name not in ("workflow.json", "artifacts.json")
        }
        final = (json.dumps(record, indent=2, allow_nan=False) + "\n").encode()
        inventory["workflow.json"] = {
            "bytes": len(final),
            "sha256": hashlib.sha256(final).hexdigest(),
        }
        _atomic_json(output / "artifacts.json", {"mode": "physical", "artifacts": inventory})
        _atomic_json(output / "workflow.json", record)
        export_wf01(output, sidecar_path(output))
        return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--confirm-prepared-reference", action="store_true")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    setup = json.loads(args.setup.read_text())
    validate_setup(args.resource, setup, args.confirm_prepared_reference)
    if args.child:
        result = execute(args.output, args.resource, setup, confirmed=True)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "output": str(args.output),
                    "final_state": result["final_state"],
                }
            ),
            flush=True,
        )
        return 0 if result["status"] == "completed" else 1
    # Separate supervisor: signal the runner at 870 s, kill its owned group by 900 s.
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--child"],
        start_new_session=True,
    )
    try:
        try:
            return child.wait(timeout=870)
        except subprocess.TimeoutExpired:
            child.send_signal(signal.SIGINT)
            try:
                child.wait(timeout=28)
            except subprocess.TimeoutExpired:
                pass
            print(
                "WF-01 outer deadline: inspect checkpoint and source state; no automatic retry",
                file=sys.stderr,
            )
            return 124
    finally:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait(timeout=1)


if __name__ == "__main__":
    raise SystemExit(main())
