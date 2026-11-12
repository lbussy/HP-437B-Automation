"""Supervised WF-03 five-cycle POWER REF runner; normal logging is unchanged.

Explicit prepared Mac setup only. No fault injection, retries, or source fallback.
Parent signals at 870 s and disposes its owned process group by about 900 s.
"""

import argparse
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
from importlib.metadata import version
from pathlib import Path
from runpy import run_path

from hp437b import provenance as p
from hp437b import repeatability as w
from hp437b import report_context, report_identity
from hp437b import reporting as r
from hp437b.errors import OperationTimeout, ProtocolError
from hp437b.logger import _atomic_json, collect
from hp437b.transport import VisaTransport
from hp437b.workflow_report import _seal, preflight

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = run_path(str(ROOT / "tools/run_power_reference.py"))


class Controller(FOUNDATION["Controller"]):
    def __init__(self, *args):
        super().__init__(*args)
        self.end = self.started + 900
        self.work_end = self.end - 90
        self.cycle_id = None
        self.cycle_end = self.work_end
        self.active = None

    def event(self, operation, **data):
        super().event(operation, cycle_id=self.cycle_id, **data)

    def start_cycle(self, cycle):
        self.cycle_id = cycle["cycle_id"]
        self.stage = self.cycle_id + "-cycle"
        self.active = cycle
        cycle.update(status="running", start_s=self.clock() - self.started)
        self.cycle_end = min(self.clock() + 180, self.work_end)
        if self.cycle_end - self.clock() < 150:
            raise OperationTimeout("Insufficient budget for another complete WF-03 cycle")
        self.activated = False
        self.off_attempted = False
        self.checkpoint()

    def begin(self, stage, entry, seconds, *, cleanup=False):
        self.stage, self.active = stage, entry
        self.stage_end = min(
            self.clock() + seconds, self.end - 30 if cleanup else min(self.work_end, self.cycle_end)
        )
        if not cleanup:
            entry.update(status="running", start_s=self.clock() - self.started)
        if self.stage_end <= self.clock():
            raise OperationTimeout("WF-03 has no remaining stage budget")
        if not cleanup:
            self.checkpoint()

    def done(self):
        self.active.update(status="completed", end_s=self.clock() - self.started)
        self.checkpoint()

    def deadline(self, requested):
        cap = min(requested, self.stage_end)
        if self.clock() >= cap:
            raise OperationTimeout("WF-03 stage deadline expired")
        return cap


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
    report_output=None,
    plots=True,
    criteria=None,
):
    FOUNDATION["validate_setup"](resource, setup, confirmed)
    p.require(
        all(isinstance(note, str) for note in setup["known_issues"]),
        "Known equipment issues must be strings",
    )
    w.validate_criteria(criteria)
    setup = p._json(r.encoded(setup))
    operator = report_context.resolve_operator(recorded=setup.get("operator"))["value"]
    if report_output is not None:
        _, report_output = preflight(output, report_output, plots=plots)
    output = Path(output).resolve()
    p.require(
        not output.exists() and not p.sidecar_path(output).exists(),
        "Capture/sidecar output already exists",
    )
    with FOUNDATION["ownership"](resource):
        output.mkdir(parents=True, exist_ok=False)
        (output / "stages").mkdir()
        record = {
            "schema": w.SCHEMA,
            "workflow_id": w.WORKFLOW,
            "mode": "physical",
            "simulation": False,
            "run_id": str(uuid.uuid4()),
            "status": "running",
            "started_utc": utcnow().isoformat(),
            "resource": resource,
            "setup": setup,
            "profile": dict(w.PROFILE),
            "criteria": criteria,
            "operator": operator,
            "subject": "POWER REF output (internal reference source)",
            "equipment": {
                "source": "HP 437B S/N "
                + setup["meter_serial"]
                + " internal POWER REF; nominal 50 MHz/1 mW",
                "meter": "HP 437B S/N " + setup["meter_serial"],
                "sensor": "HP 8482A S/N " + setup["sensor_serial"],
                "adapter": setup.get("adapter", {}).get("model", "Not recorded"),
            },
            "software": {
                **report_identity.identify(),
                "python": platform.python_version(),
                "dependencies": {name: version(name) for name in ("PyVISA", "PyVISA-py", "PyUSB")},
                "runner_sha256": r.digest(Path(__file__).read_bytes()),
                "analysis_sha256": r.digest(Path(w.__file__).read_bytes()),
            },
            "preflight": {"status": "pending"},
            "free_run": {"status": "pending"},
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
            "sessions": [],
        }
        c = Controller(output, record, clock, sleep, utcnow)
        c.checkpoint()
        (output / "starting.json").write_bytes(r.encoded(record))
        for name, path in (
            ("runner-source.txt", Path(__file__)),
            ("control-source.txt", ROOT / "tools/run_power_reference.py"),
            ("adapter-source.txt", ROOT / "tools/usbgpib_target.py"),
            ("analysis-source.txt", Path(w.__file__)),
            ("definition.md", ROOT / "docs/workflows/WF-03-PHYSICAL.md"),
            ("LICENSE", ROOT / "LICENSE"),
            ("THIRD_PARTY_NOTICES.md", ROOT / "THIRD_PARTY_NOTICES.md"),
        ):
            (output / name).write_bytes(path.read_bytes())
        _atomic_json(output / "setup.json", setup)
        active = None

        @contextmanager
        def session(expected):
            if c.faulted:
                raise ProtocolError("No new session after uncertain WF-03 I/O")
            c.session_id = str(uuid.uuid4())
            details = {"session": c.session_id, "stage": c.stage, "cycle_id": c.cycle_id}
            record["sessions"].append(details)
            wire = FOUNDATION["RecordedWire"](factory(resource), c)
            instrument = None
            try:
                wire.open()
                instrument = FOUNDATION["WorkflowInstrument"](wire, c, expected)
                identity = instrument.identify()
                details["identity"] = {**asdict(identity), "raw": identity.raw.hex()}
                if identity.model != "437B" or (
                    setup.get("expected_firmware")
                    and identity.firmware != setup["expected_firmware"]
                ):
                    raise ProtocolError("WF-03 instrument identity/firmware mismatch")
                yield instrument
            finally:
                try:
                    if instrument is not None:
                        instrument.close()
                finally:
                    wire.close()
                    details.update(
                        cleanup=getattr(instrument, "cleanup", None),
                        local_return=getattr(wire, "local_return", None),
                        read_deadline_cleanup=getattr(wire, "read_deadline_cleanup", None),
                    )

        def probe(instrument):
            instrument.configure_absolute("W")
            value = instrument.acquire()
            c.event("setup_probe", value_W=str(value.value), raw_hex=value.raw.hex())
            return instrument.read_status()

        def switch(on, entry, *, cleanup=False):
            c.begin(
                c.cycle_id + ("-source-on" if on else "-source-off"),
                entry,
                30 if on else 20,
                cleanup=cleanup,
            )
            with session(on) as instrument:
                c.activated |= on
                c.off_attempted |= not on
                c.change_pending = True
                instrument.command("OC1" if on else "OC0", confirmed=True)
                entry["status_raw_hex"] = probe(instrument).raw.hex()
            if cleanup:
                entry.update(status="completed", end_s=clock() - c.started)
            else:
                c.done()

        def capture(stage, on, duration=None):
            entry = record["stages"][stage]
            c.begin(stage, entry, 90 if duration is None else 60 if duration == 20 else 70)
            if duration is not None and c.stage_end - clock() < duration + 30:
                raise OperationTimeout("Insufficient WF-03 acquisition/closure budget")
            with session(on) as instrument:
                collect(
                    instrument,
                    output / "stages" / f"{stage}.csv",
                    count=None if duration else 3,
                    duration=duration,
                    interval=1,
                    unit="W",
                    simulation=False,
                    clock=clock,
                    sleep=c.wait,
                    utcnow=utcnow,
                    context={
                        "workflow_id": w.WORKFLOW,
                        "workflow_run_id": record["run_id"],
                        "stage_id": stage,
                        "cycle_id": c.cycle_id,
                        "mode": "physical",
                        "resource": resource,
                        "meter_serial": setup["meter_serial"],
                        "sensor_serial": setup["sensor_serial"],
                    },
                )
            with session(on) as instrument:
                entry["final_status_raw_hex"] = probe(instrument).raw.hex()
            c.done()

        try:
            c.begin("preflight", record["preflight"], 60)
            if setup.get("select_adapter_target") is True:
                try:
                    record["adapter_target_preparation"] = FOUNDATION["SELECT_TARGET"](
                        resource,
                        setup["adapter_target_address"],
                        deadline=c.deadline(clock() + 20),
                        event=c.event,
                    )
                    c.checkpoint()
                except BaseException:
                    c.faulted = True
                    raise
            with session(False) as instrument:
                record["preflight"]["status_raw_hex"] = probe(instrument).raw.hex()
            c.done()
            capture("baseline-before", False)
            for active in record["cycles"]:
                c.start_cycle(active)
                cid = c.cycle_id
                switch(True, active["source_on"])
                capture(cid + "-settling", True, 20)
                capture(cid + "-plateau", True, 30)
                switch(False, active["source_off"])
                c.begin(cid + "-off-wait", active["off_wait"], 30)
                c.wait(20)
                active["off_wait"]["duration_s"] = 20
                c.done()
                capture(cid + "-off-baseline", False)
                active.update(status="completed", end_s=clock() - c.started)
                c.checkpoint()
            c.cycle_id = None
            c.cycle_end = c.work_end
            active = None
            c.begin("free-run", record["free_run"], 20)
            with session(False) as instrument:
                status = instrument.read_status()
                display = instrument.query("OD").value
                c.event("free_run_display", text=display, standby=status.standby)
                if (
                    status.standby
                    or "TRIGGER" in display.upper()
                    or not any(char.isdigit() for char in display)
                ):
                    raise ProtocolError("WF-03 final free-run/numeric display check failed")
            record["free_run_check"] = {
                "passed": True,
                "display": display,
                "standby": status.standby,
            }
            c.done()
            record["status"] = "completed"
        except (Exception, KeyboardInterrupt) as exc:
            record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            if c.active is not None:
                c.active.update(
                    status=record["status"], error=record["error"], end_s=clock() - c.started
                )
            if active is not None:
                active.update(
                    status=record["status"], error=record["error"], end_s=clock() - c.started
                )
            if (
                c.activated
                and not c.off_attempted
                and not c.faulted
                and (c.change_pending or c.last_source is not False)
            ):
                entry = record["emergency_cleanup"] = {"status": "running"}
                try:
                    switch(False, entry, cleanup=True)
                except (Exception, KeyboardInterrupt) as cleanup:
                    entry.update(status="failed", error=f"{type(cleanup).__name__}: {cleanup}")
            for item in (record["preflight"], record["free_run"], *record["stages"].values()):
                if item["status"] == "pending":
                    item.update(status="skipped", reason="Earlier stage/control did not complete")
            for cycle in record["cycles"]:
                if cycle["status"] == "pending":
                    cycle.update(status="skipped", reason="Earlier cycle did not complete")
                for key in ("source_on", "source_off", "off_wait"):
                    if cycle[key]["status"] == "pending":
                        cycle[key].update(status="skipped", reason="Cycle did not complete")
        record.update(
            finished_utc=utcnow().isoformat(), elapsed_s=clock() - c.started, final_state=c.state()
        )
        c.checkpoint()
        p.require(clock() <= c.end, "WF-03 outer budget exhausted before capture sealing")
        _seal(
            output,
            {
                "schema": "hp437b.repeatability-export.v1",
                "mode": "physical",
                "run_id": record["run_id"],
            },
        )
        w.load(output)
    if report_output is not None:
        w.publish(output, report_output, plots=plots, operator=operator)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resource", required=True)
    parser.add_argument("--setup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--confirm-prepared-reference", action="store_true")
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--report-no-plots", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.report_no_plots and args.report_output is None:
        parser.error("--report-no-plots requires --report-output")
    setup = p._json(args.setup.read_bytes())
    operator = report_context.resolve_operator(args.operator, setup.get("operator"))["value"]
    if operator is not None:
        setup["operator"] = operator
    FOUNDATION["validate_setup"](args.resource, setup, args.confirm_prepared_reference)
    if args.report_output is not None:
        preflight(args.output, args.report_output, plots=not args.report_no_plots)
    if args.child:
        record = execute(
            args.output,
            args.resource,
            setup,
            confirmed=args.confirm_prepared_reference,
            report_output=args.report_output,
            plots=not args.report_no_plots,
        )
        print(
            r.encoded(
                {
                    "status": record["status"],
                    "output": str(args.output),
                    "final_state": record["final_state"],
                }
            ).decode(),
            flush=True,
        )
        return 0 if record["status"] == "completed" else 1
    arguments = sys.argv[1:] if argv is None else argv
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *arguments, "--child"],
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
                "WF-03 outer deadline: inspect checkpoint/source state; no automatic retry",
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
