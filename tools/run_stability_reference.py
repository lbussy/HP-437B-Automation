"""Supervised physical WF-02 POWER REF runner; normal logging is unchanged.

Fixed 30-minute plateau. Requires explicit Mac resource/setup/prepared confirmation.
The parent supervisor signals at 2070 seconds and disposes its group by 2100.
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
from hp437b import report_context, report_identity
from hp437b import reporting as r
from hp437b import stability as s
from hp437b.errors import OperationTimeout, ProtocolError
from hp437b.logger import _atomic_json, collect
from hp437b.transport import VisaTransport
from hp437b.workflow_report import _seal, preflight

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = run_path(str(ROOT / "tools/run_power_reference.py"))
LIMITS = {
    "preflight": 60,
    "baseline-before": 90,
    "source-on": 30,
    "settling": 60,
    "plateau": 1840,
    "source-off": 20,
    "baseline-after": 90,
    "free-run": 20,
}


class Controller(FOUNDATION["Controller"]):
    def __init__(self, *args):
        super().__init__(*args)
        self.end = self.started + s.PROFILE["whole_run_ceiling_s"]
        self.work_end = self.end - 90
        self.stage = "preflight"

    def begin(self, stage, *, cleanup=False):
        self.stage = stage
        self.stage_end = min(
            self.clock() + (20 if cleanup else LIMITS[stage]),
            self.end - 30 if cleanup else self.work_end,
        )
        if self.stage_end <= self.clock():
            raise OperationTimeout("WF-02 has no remaining stage budget")
        if not cleanup:
            table = self.record["stages"] if stage in s.STAGES else self.record["control_stages"]
            table[stage] = {
                "status": "running",
                "start_s": self.clock() - self.started,
                "window_offset_s": 0,
            }
            self.checkpoint()

    def done(self):
        table = self.record["stages"] if self.stage in s.STAGES else self.record["control_stages"]
        table[self.stage].update(status="completed", end_s=self.clock() - self.started)
        self.checkpoint()

    def deadline(self, requested):
        cap = min(requested, self.stage_end)
        if self.clock() >= cap:
            raise OperationTimeout("WF-02 stage deadline expired")
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
    s.validate_criteria(criteria)
    setup = p._json(r.encoded(setup))  # Own a finite JSON snapshot, not mutable caller state.
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
            "schema": s.SCHEMA,
            "workflow_id": s.WORKFLOW,
            "mode": "physical",
            "simulation": False,
            "run_id": str(uuid.uuid4()),
            "status": "running",
            "started_utc": utcnow().isoformat(),
            "resource": resource,
            "setup": setup,
            "profile": dict(s.PROFILE),
            "criteria": criteria,
            "operator": operator,
            "subject": "POWER REF output (internal reference source)",
            "equipment": {
                "source": "HP 437B internal POWER REF; nominal 50 MHz/1 mW",
                "meter": "HP 437B S/N " + setup["meter_serial"],
                "sensor": "HP 8482A S/N " + setup["sensor_serial"],
                "adapter": setup.get("adapter", {}).get("model", "Not recorded"),
            },
            "software": {
                **report_identity.identify(),
                "python": platform.python_version(),
                "dependencies": {name: version(name) for name in ("PyVISA", "PyVISA-py", "PyUSB")},
                "runner_sha256": r.digest(Path(__file__).read_bytes()),
                "analysis_sha256": r.digest(Path(s.__file__).read_bytes()),
            },
            "stages": {stage: {"status": "pending"} for stage in s.STAGES},
            "control_stages": {
                stage: {"status": "pending"} for stage in LIMITS if stage not in s.STAGES
            },
            "sessions": [],
        }
        c = Controller(output, record, clock, sleep, utcnow)
        c.checkpoint()
        (output / "starting.json").write_bytes(r.encoded(record))
        for name, source in (
            ("runner-source.txt", Path(__file__)),
            ("control-source.txt", ROOT / "tools/run_power_reference.py"),
            ("adapter-source.txt", ROOT / "tools/usbgpib_target.py"),
            ("analysis-source.txt", Path(s.__file__)),
            ("definition.md", ROOT / "docs/workflows/WF-02-PHYSICAL.md"),
            ("LICENSE", ROOT / "LICENSE"),
            ("THIRD_PARTY_NOTICES.md", ROOT / "THIRD_PARTY_NOTICES.md"),
        ):
            (output / name).write_bytes(source.read_bytes())
        _atomic_json(output / "setup.json", setup)

        @contextmanager
        def session(expected):
            if c.faulted:
                raise ProtocolError("No new session after uncertain WF-02 I/O")
            c.session_id = str(uuid.uuid4())
            details = {"session": c.session_id, "stage": c.stage}
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
                    raise ProtocolError("WF-02 instrument identity/firmware mismatch")
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

        def switch(on):
            with session(on) as instrument:
                c.activated |= on
                c.off_attempted |= not on
                c.change_pending = True
                instrument.command("OC1" if on else "OC0", confirmed=True)
                probe(instrument)

        def capture(stage, on, duration=None):
            c.begin(stage)
            if duration is not None and c.stage_end - clock() < duration + 30:
                raise OperationTimeout(
                    "Insufficient budget for full acquisition window and closure"
                )
            with session(on) as instrument:
                collect(
                    instrument,
                    output / "stages" / (stage + ".csv"),
                    count=None if duration else 3,
                    duration=duration,
                    interval=1,
                    unit="W",
                    simulation=False,
                    clock=clock,
                    sleep=c.wait,
                    utcnow=utcnow,
                    context={
                        "workflow_id": s.WORKFLOW,
                        "workflow_run_id": record["run_id"],
                        "stage_id": stage,
                        "mode": "physical",
                        "resource": resource,
                        "meter_serial": setup["meter_serial"],
                        "sensor_serial": setup["sensor_serial"],
                    },
                )
            with session(on) as instrument:
                record["stages"][stage]["final_status_raw_hex"] = probe(instrument).raw.hex()
            c.done()

        try:
            c.begin("preflight")
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
                probe(instrument)
            c.done()
            capture("baseline-before", False)
            c.begin("source-on")
            switch(True)
            c.done()
            capture("settling", True, duration=20)
            capture("plateau", True, duration=1800)
            c.begin("source-off")
            switch(False)
            c.done()
            capture("baseline-after", False)
            c.begin("free-run")
            with session(False) as instrument:
                status = instrument.read_status()
                display = instrument.query("OD").value
                c.event("free_run_display", text=display, standby=status.standby)
                if (
                    status.standby
                    or "TRIGGER" in display.upper()
                    or not any(char.isdigit() for char in display)
                ):
                    raise ProtocolError("Final free-run/numeric display check failed")
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
            table = record["stages"] if c.stage in s.STAGES else record["control_stages"]
            table[c.stage].update(
                status=record["status"], error=record["error"], end_s=clock() - c.started
            )
            if (
                c.activated
                and not c.off_attempted
                and not c.faulted
                and (c.change_pending or c.last_source is not False)
            ):
                try:
                    c.begin("source-off", cleanup=True)
                    switch(False)
                    record["emergency_cleanup"] = "reference off verified"
                except (Exception, KeyboardInterrupt) as cleanup:
                    record["emergency_cleanup"] = f"failed: {type(cleanup).__name__}: {cleanup}"
            for table in (record["stages"], record["control_stages"]):
                for item in table.values():
                    if item["status"] == "pending":
                        item.update(status="skipped", reason="Prior stage/control did not complete")
        record.update(
            finished_utc=utcnow().isoformat(), elapsed_s=clock() - c.started, final_state=c.state()
        )
        c.checkpoint()
        p.require(clock() <= c.end, "WF-02 outer budget exhausted before capture sealing")
        _seal(
            output,
            {
                "schema": "hp437b.stability-export.v1",
                "mode": "physical",
                "run_id": record["run_id"],
            },
        )
        s.load(output)
    if report_output is not None:
        s.publish(output, report_output, plots=plots, operator=operator)
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
    setup["operator"] = report_context.resolve_operator(args.operator, setup.get("operator"))[
        "value"
    ]
    if setup["operator"] is None:
        del setup["operator"]
    FOUNDATION["validate_setup"](args.resource, setup, args.confirm_prepared_reference)
    if args.report_output is not None:
        preflight(args.output, args.report_output, plots=not args.report_no_plots)
    if args.child:
        result = execute(
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
                    "status": result["status"],
                    "output": str(args.output),
                    "final_state": result["final_state"],
                }
            ).decode(),
            flush=True,
        )
        return 0 if result["status"] == "completed" else 1
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--child"],
        start_new_session=True,
    )
    try:
        try:
            return child.wait(timeout=2070)
        except subprocess.TimeoutExpired:
            child.send_signal(signal.SIGINT)
            try:
                child.wait(timeout=28)
            except subprocess.TimeoutExpired:
                pass
            print(
                "WF-02 outer deadline: inspect checkpoint/source state; no automatic retry",
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
