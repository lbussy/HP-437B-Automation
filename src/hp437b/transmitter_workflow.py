"""DUT-CTRL-01 fake external-transmitter capture, provenance, and reporting.

The CLI constructs explicit fakes only. Saved-run reporting replays control
receipts without invoking a device or reacquiring a measurement.
"""

import argparse
import csv
import html
import sys
import uuid
from decimal import Decimal as D
from pathlib import Path

from . import dut_control as c
from . import dut_simulation as fake
from . import protocol, report_context, report_identity, report_sheet
from . import provenance as p
from . import reporting as r
from .errors import ProtocolError
from .instrument import Instrument
from .logger import collect
from .power_setting import factor, text
from .workflow_report import _seal, preflight

WORKFLOW = "external-transmitter-single-point-v1"
SCHEMA = "hp437b.external-transmitter-capture.v1"
STAGES = ("baseline-before", "settling", "plateau", "baseline-after")
PROFILE = {"baseline-before": 3, "settling": 20, "plateau": 30, "baseline-after": 3}


def validate_criteria(criteria):
    if criteria is None:
        return
    p._keys(
        criteria,
        (
            "source",
            "target_W",
            "max_abs_error_percent",
            "min_samples",
            "max_gap_s",
            "decision_rule",
        ),
    )
    text(criteria["source"], 240)
    p.require(
        D("1e-20") <= r.number(criteria["target_W"]) <= 10000
        and r.number(criteria["max_abs_error_percent"]) >= 0,
        "Invalid target/error limit",
    )
    p.require(
        type(criteria["min_samples"]) is int
        and 1 <= criteria["min_samples"] <= 30
        and 0 < r.number(criteria["max_gap_s"]) <= 30,
        "Invalid coverage criterion",
    )
    p.require(criteria["decision_rule"] == "inclusive-no-guard-band", "Unsupported decision rule")


def status_ok(raw):
    status = protocol.status(bytes.fromhex(raw))
    p.require(
        status.unit == "W"
        and not any(
            (
                status.reference_on,
                status.relative,
                status.offset_on,
                status.duty_on,
                status.measurement_error,
                status.entry_error,
            )
        ),
        "Meter units/correction/reference state mismatch",
    )


class StageInstrument(Instrument):
    def __init__(self, wire, controls):
        super().__init__(wire, timeout=10)
        self.controls = controls

    def read_status(self):
        value = super().read_status()
        status_ok(value.raw.hex())
        return value

    def acquire(self, trigger="TR2"):
        self.controls.check_budget()
        value = super().acquire(trigger)
        self.controls.check_budget()
        if value.error_code:
            raise ProtocolError("Complete instrument error; capture stopped")
        if value.value is not None and value.value > D(self.controls.plan["sensor_limit_W"]):
            raise ProtocolError("Complete sample exceeds supplied sensor operating ceiling")
        return value


def simulate(
    output,
    *,
    scenario="nominal",
    plan=None,
    criteria=None,
    operator=None,
    report_output=None,
    plots=True,
):
    p.require(scenario in fake.SCENARIOS, "Unknown external-DUT scenario")
    plan = c.validate_plan(c.default_plan() if plan is None else plan)
    # Keep caller configuration untouched; missing correction is an explicit fixture variant.
    plan = p._json(r.encoded(plan))
    if scenario == "missing-loss":
        plan["fixture"].update(loss_dB=None, correction_source=None)
    if scenario == "sensor-plane":
        plan["measurement_plane"] = "sensor_input"
    model_power = D("4.8") if scenario == "low-output" else D("5")
    p.require(
        model_power <= D(plan["max_RF_W"])
        and model_power / factor("30") <= D(plan["sensor_limit_W"])
        and D(plan["fixture"]["minimum_loss_dB"]) <= 30,
        "Fixed fake RF model conflicts with declared operating bounds",
    )
    validate_criteria(criteria)
    operator = report_context.resolve_operator(operator)["value"]
    output = Path(output).resolve()
    p.require(
        not output.exists() and not p.sidecar_path(output).exists(), "Capture output already exists"
    )
    if report_output is not None:
        preflight(output, report_output, plots=plots)
    bench = fake.Bench(plan, scenario)
    controls = c.Controls(
        plan,
        fake.FakeTransmitter(bench),
        fake.FakeSupply(bench),
        fake.FakeObserver(bench),
        clock=lambda: bench.now,
    )
    bench.controls = controls
    record = dict(
        schema=SCHEMA,
        workflow_id=WORKFLOW,
        mode="synthetic",
        simulation=True,
        run_id=str(uuid.uuid4()),
        scenario=scenario,
        profile=dict(PROFILE),
        plan=plan,
        criteria=criteria,
        operator=operator,
        software=report_identity.identify(),
        started_utc=bench.utc().isoformat(),
        finished_utc=None,
        status="running",
        outcome=None,
        stages={stage: dict(status="skipped", reason="Not reached") for stage in STAGES},
        final_state=None,
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "stages").mkdir()
    (output / "starting.json").write_bytes(r.encoded(record))

    def capture(stage):
        controls.check_budget()
        bench.stage, bench.reads = stage, 0
        item = record["stages"][stage]
        item.update(
            status="running",
            start_s=bench.now,
            control_event_count=len(controls.events),
            expected_rf=controls.rf,
        )
        instrument = StageInstrument(fake.Wire(bench), controls)
        origin = bench.now + 0.02
        try:
            collect(
                instrument,
                output / "stages" / (stage + ".csv"),
                count=3 if stage.startswith("baseline") else None,
                duration=PROFILE[stage] if not stage.startswith("baseline") else None,
                interval=1,
                unit="W",
                simulation=True,
                clock=lambda: round(bench.now - origin, 6),
                sleep=bench.sleep,
                utcnow=bench.utc,
                context=dict(
                    workflow_id=WORKFLOW,
                    workflow_run_id=record["run_id"],
                    stage_id=stage,
                    mode="synthetic",
                    source_asset_id=plan["assets"]["transmitter"]["asset_id"],
                ),
            )
            item["status"] = "completed"
        except (Exception, KeyboardInterrupt) as exc:
            item.update(
                status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                error=type(exc).__name__ + ": " + str(exc),
            )
            raise c.StageFailure(
                item["error"],
                uncertain=instrument._uncertain,
                interrupted=isinstance(exc, KeyboardInterrupt),
            ) from exc
        finally:
            # collect normally closes; reservation can fail before its cleanup block.
            instrument.close()
            item.update(end_s=bench.now, uncertain=instrument._uncertain)

    outcome = c.execute(controls, capture)
    record.update(
        status=outcome["status"],
        outcome=outcome,
        finished_utc=bench.utc().isoformat(),
        final_state={
            **controls.summary(),
            "meter_local": ("local" if bench.local else "unverified")
            if any(event["operation"] == "session_open" for event in bench.trace)
            else "not_opened",
            "power_ref_controlled": False,
        },
    )
    (output / "workflow.json").write_bytes(r.encoded(record))
    (output / "controls.json").write_bytes(
        r.encoded(
            dict(
                events=controls.events,
                order=controls.order,
                phases=controls.phases,
                summary=controls.summary(),
            )
        )
    )
    (output / "meter-trace.json").write_bytes(r.encoded(bench.trace))
    for stage, item in record["stages"].items():
        if item["status"] != "skipped":
            csv_path = output / "stages" / (stage + ".csv")
            session_path = output / "stages" / (stage + ".csv.session.json")
            if not csv_path.is_file() or not session_path.is_file():
                raise OSError(
                    "Capture log reservation/finalization incomplete; cleanup evidence retained without success inventory"
                )
            metadata = p._json(session_path.read_bytes())
            p.require(
                metadata.get("status") in ("completed", "failed", "interrupted"),
                "Unfinalized logger metadata; no successful capture inventory",
            )
    _seal(
        output,
        dict(
            schema="hp437b.external-transmitter-inventory.v1",
            mode="synthetic",
            run_id=record["run_id"],
        ),
    )
    if report_output is not None:
        publish(output, report_output, plots=plots)
    return record


class ReplayClock:
    def __init__(self):
        self.now = 0.0


class RecordedEndpoint:
    simulation = True

    def __init__(self, role, clock, events, cursor):
        self.role, self.clock, self.events, self.cursor = role, clock, events, cursor

    def __getattr__(self, operation):
        p.require(
            operation
            in (
                "identify",
                "status",
                "configure",
                "set_rf",
                "set_current_limit",
                "set_voltage",
                "measure",
            ),
            "Unknown recorded control operation",
        )

        def replay(*, deadline, **request):
            index = self.cursor[0]
            p.require(index < len(self.events), "Missing control receipt")
            item = self.events[index]
            p.require(
                item["device"] == self.role
                and item["operation"] == operation
                and r.encoded(item["request"]) == r.encoded(request),
                "Control receipt/request/role mismatch",
            )
            p.require(
                item["start_s"] == self.clock.now
                and abs(item["deadline_s"] - deadline) < 1e-8
                and item["end_s"] >= item["start_s"],
                "Control receipt timing/deadline mismatch",
            )
            self.clock.now = item["end_s"]
            self.cursor[0] += 1
            if item["status"] == "error":
                raise c.DriverFailure(item["error"])
            p.require(item["status"] == "returned", "Invalid control receipt status")
            return item["reply"]

        return replay


def load(source):
    """Verify source bytes, logger sessions, and fixed orchestration via receipt replay."""
    bundle = p.Bundle(source)
    inventory = bundle.inventory("artifacts.json", "synthetic")
    record = bundle.json("workflow.json")
    p._keys(
        record,
        (
            "schema",
            "workflow_id",
            "mode",
            "simulation",
            "run_id",
            "scenario",
            "profile",
            "plan",
            "criteria",
            "operator",
            "software",
            "started_utc",
            "finished_utc",
            "status",
            "outcome",
            "stages",
            "final_state",
        ),
    )
    p.require(
        record["schema"] == SCHEMA
        and record["workflow_id"] == WORKFLOW
        and record["mode"] == "synthetic"
        and record["simulation"] is True,
        "Unsupported external-transmitter capture",
    )
    uuid.UUID(record["run_id"])
    p.require(
        inventory.get("schema") == "hp437b.external-transmitter-inventory.v1"
        and inventory.get("run_id") == record["run_id"],
        "Inventory/run mismatch",
    )
    p.require(
        record["profile"] == PROFILE and record["scenario"] in fake.SCENARIOS,
        "Unsupported finite profile",
    )
    c.validate_plan(record["plan"])
    validate_criteria(record["criteria"])
    report_context.validate_operator(record["operator"])
    initial = {
        **record,
        "finished_utc": None,
        "status": "running",
        "outcome": None,
        "stages": {stage: dict(status="skipped", reason="Not reached") for stage in STAGES},
        "final_state": None,
    }
    p.require(bundle.json("starting.json") == initial, "Starting/final record mismatch")
    started, finished = r.timestamp(record["started_utc"]), r.timestamp(record["finished_utc"])
    span = (finished - started).total_seconds()
    p.require(
        0 <= span <= record["plan"]["timing"]["whole_run_s"], "Invalid bounded capture duration"
    )
    control_record = bundle.json("controls.json")
    p._keys(control_record, ("events", "order", "phases", "summary"))
    events = control_record["events"]
    p.require(isinstance(events, list) and len(events) <= 48, "Invalid control receipt count")
    for item in events:
        p.require(
            isinstance(item, dict)
            and type(item.get("start_s")) in (int, float)
            and type(item.get("end_s")) in (int, float)
            and 0 <= item["start_s"] <= item["end_s"] <= span,
            "Invalid control receipt interval",
        )
    clock, cursor = ReplayClock(), [0]
    controls = c.Controls(
        record["plan"],
        *(
            RecordedEndpoint(role, clock, events, cursor)
            for role in ("transmitter", "supply", "observer")
        ),
        clock=lambda: clock.now,
    )
    stages, attempted, session_ids = {}, [], set()
    p._keys(record["stages"], STAGES)

    def saved_stage(stage):
        controls.check_budget()
        item = record["stages"][stage]
        p.require(
            item["status"] in ("completed", "failed", "interrupted")
            and type(item["uncertain"]) is bool,
            "Missing/falsely skipped stage",
        )
        p.require(
            item["start_s"] == clock.now
            and item["control_event_count"] == len(controls.events)
            and item["expected_rf"] == controls.rf,
            "Capture/control condition join mismatch",
        )
        p.require(
            controls.rf == ("off" if stage.startswith("baseline") else "on"),
            "Capture without supported RF state",
        )
        p.require(
            item["start_s"] <= item["end_s"] <= span
            and item["end_s"] - item["start_s"] <= PROFILE[stage] + 10,
            "Invalid stage duration",
        )
        metadata = bundle.json("stages/" + stage + ".csv.session.json")
        context = dict(
            workflow_id=WORKFLOW,
            workflow_run_id=record["run_id"],
            stage_id=stage,
            mode="synthetic",
            source_asset_id=record["plan"]["assets"]["transmitter"]["asset_id"],
        )
        p.require(
            metadata.get("context") == context and metadata["session_id"] not in session_ids,
            "Session context/source/run mismatch",
        )
        session_ids.add(metadata["session_id"])
        settings = metadata["settings"]
        p.require(
            settings
            == dict(
                unit="W",
                interval_s=1,
                count=3 if stage.startswith("baseline") else None,
                duration_s=None if stage.startswith("baseline") else PROFILE[stage],
                operation_timeout_s=10,
            ),
            "Unsupported logger settings",
        )
        p.require(
            metadata["instrument"]["serial"] == "SYNTHETIC-DUT01"
            and metadata["transport"].get("simulation") is True,
            "Wrong meter/mode",
        )
        status_ok(metadata["initial_status_raw_hex"])
        parsed = r.stage_result(
            bundle.read("stages/" + stage + ".csv"), metadata, "synthetic", stage, item["status"]
        )
        p.require(
            parsed["session_status"] == item["status"] and parsed["attempted"] <= PROFILE[stage],
            "Stage/session state mismatch",
        )
        if item["status"] == "completed":
            p.require(
                parsed["valid"] == PROFILE[stage] and not item["uncertain"],
                "Incomplete completed stage",
            )
        p.require(
            all(point["status"] == "ok" for point in parsed["points"][:-1]),
            "Samples after first fault",
        )
        p.require(
            abs((r.timestamp(metadata["started_utc"]) - started).total_seconds() - item["start_s"])
            < 1e-6
            and abs(
                (r.timestamp(metadata["finished_utc"]) - started).total_seconds() - item["end_s"]
            )
            < 1e-6,
            "Session/capture UTC mismatch",
        )
        if item["uncertain"]:
            p.require(
                metadata.get("instrument_cleanup") is None and metadata.get("local_return") is None,
                "Uncertain session claims healthy cleanup",
            )
        else:
            p.require(
                metadata.get("instrument_cleanup", {}).get("status") == "accepted"
                and metadata.get("local_return", {}).get("status") == "accepted",
                "Missing healthy free-run/local cleanup",
            )
        stages[stage] = parsed
        attempted.append(stage)
        clock.now = item["end_s"]
        if item["status"] != "completed":
            raise c.StageFailure(
                item["error"],
                uncertain=item["uncertain"],
                interrupted=item["status"] == "interrupted",
            )

    invalid_stage = []

    def checked_stage(stage):
        try:
            return saved_stage(stage)
        except c.StageFailure:
            raise
        except Exception as exc:
            invalid_stage.append(str(exc))
            raise

    outcome = c.execute(controls, checked_stage)
    p.require(not invalid_stage, "Invalid saved stage evidence: " + "; ".join(invalid_stage))
    # A parser failure must not be swallowed as an expected workflow failure.
    p.require(
        outcome == record["outcome"] and outcome["status"] == record["status"],
        "Replay outcome differs from saved execution",
    )
    p.require(
        cursor[0] == len(events) and r.encoded(controls.events) == r.encoded(events),
        "Extra/missing/post-fault control operations",
    )
    p.require(
        r.encoded(
            dict(
                events=controls.events,
                order=controls.order,
                phases=controls.phases,
                summary=controls.summary(),
            )
        )
        == r.encoded(control_record),
        "Control phase/state replay mismatch",
    )
    for stage in STAGES:
        if stage not in attempted:
            p.require(
                record["stages"][stage] == dict(status="skipped", reason="Not reached")
                and "stages/" + stage + ".csv" not in bundle.entries,
                "Skipped stage contains hidden capture data",
            )
    p.require(abs(clock.now - span) < 1e-6, "Execution end time mismatch")
    trace = bundle.json("meter-trace.json")
    p.require(isinstance(trace, list) and len(trace) <= 500, "Invalid meter trace")
    previous = 0
    for event in trace:
        p.require(
            event["mode"] == "synthetic"
            and event["stage"] in attempted
            and previous <= event["elapsed_s"] <= span,
            "Meter trace stage/time mismatch",
        )
        previous = event["elapsed_s"]
        if event["operation"] == "write":
            p.require(
                bytes.fromhex(event["raw_hex"]) in (b"*IDN?", b"RL0", b"LN", b"TR2", b"SM", b"TR3"),
                "Forbidden meter command (including POWER REF)",
            )
    for stage in attempted:
        stage_trace = [event for event in trace if event["stage"] == stage]
        p.require(
            stage_trace
            and stage_trace[0]["operation"] == "session_open"
            and stage_trace[-1]["operation"] == "session_close",
            "Meter session boundary mismatch",
        )
        metadata = bundle.json("stages/" + stage + ".csv.session.json")
        csv_rows = list(
            csv.DictReader(bundle.read("stages/" + stage + ".csv").decode("utf-8").splitlines())
        )
        expected = [
            ("session_open", None),
            ("write", b"*IDN?".hex()),
            ("read", metadata["instrument"]["raw"]),
            ("write", b"RL0".hex()),
            ("write", b"LN".hex()),
            ("write", b"TR2".hex()),
            ("read", metadata["setup_measurement_raw_hex"]),
            ("write", b"SM".hex()),
            ("read", metadata["initial_status_raw_hex"]),
        ]
        for row in csv_rows:
            expected.append(("write", b"TR2".hex()))
            terminal = stage_trace[len(expected)] if len(expected) < len(stage_trace) else {}
            if (
                terminal.get("operation") == "read_error"
                and row["status"] != "ok"
                and record["stages"][stage]["uncertain"]
            ):
                text(terminal.get("reason"), 240)
                expected.append(("read_error", None))
            else:
                expected.append(("read", row["raw_hex"]))
        if not record["stages"][stage]["uncertain"]:
            expected.extend([("write", b"TR3".hex()), ("go_to_local", None)])
        expected.append(("session_close", None))
        p.require(
            [(event["operation"], event.get("raw_hex")) for event in stage_trace] == expected,
            "Meter trace/CSV/setup/cleanup join mismatch",
        )
    expected_local = (
        "unverified"
        if any(record["stages"][stage].get("uncertain", False) for stage in attempted)
        else "local"
    )
    if not attempted:
        expected_local = "not_opened"
    p.require(
        r.encoded(record["final_state"])
        == r.encoded(
            {**controls.summary(), "meter_local": expected_local, "power_ref_controlled": False}
        )
        and record["final_state"]["power_ref_controlled"] is False,
        "Final state mismatch",
    )
    return record, stages, bundle


def analyze(record, stages):
    plateau = stages.get("plateau")
    base = stages.get("baseline-before")
    metrics = plateau["metrics"] if plateau else {}
    sensor = D(metrics["mean_W"]) if metrics.get("mean_W") is not None else None
    loss = record["plan"]["fixture"]["loss_dB"]
    multiplier = factor(loss) if loss is not None else None
    measured = sensor * multiplier if sensor is not None and multiplier is not None else None
    if record["plan"]["measurement_plane"] == "sensor_input":
        measured = sensor
    points = plateau["points"] if plateau else []
    valid = [point for point in points if point["status"] == "ok"]
    gaps = [
        D(str(b["elapsed_s"])) - D(str(a["elapsed_s"]))
        for a, b in zip(valid, valid[1:], strict=False)
    ]
    gap = max(gaps) if gaps else None
    eligible = (
        record["status"] == "completed"
        and len(valid) == 30
        and sensor is not None
        and D(".000001") <= sensor <= D(record["plan"]["sensor_limit_W"])
        and measured is not None
        and measured > 0
        and (
            record["plan"]["measurement_plane"] != "DUT_output"
            or measured <= D(record["plan"]["max_RF_W"])
        )
    )
    criteria = record["criteria"]
    target = D(criteria["target_W"]) if criteria else None
    error = (
        100 * (measured - target) / target if measured is not None and target is not None else None
    )
    acceptance = "NOT EVALUATED"
    reason = (
        "Execution/control cleanup incomplete"
        if record["status"] != "completed"
        else "Corrected output unavailable or ineligible"
        if not eligible
        else "Acceptance criteria not supplied"
        if criteria is None
        else None
    )
    if criteria is not None and eligible:
        if len(valid) < criteria["min_samples"] or gap is None or gap > D(criteria["max_gap_s"]):
            reason = "Insufficient sample/timing coverage"
        else:
            acceptance = "PASS" if abs(error) <= D(criteria["max_abs_error_percent"]) else "FAIL"
    return dict(
        schema="hp437b.external-transmitter-results.v1",
        workflow_id=WORKFLOW,
        run_id=record["run_id"],
        mode="synthetic",
        source_kind="external_transmitter",
        execution=record["status"],
        measurement_plane=record["plan"]["measurement_plane"],
        sensor_mean_W=str(sensor) if sensor is not None else None,
        measured_W=str(measured) if measured is not None else None,
        sensor_metrics=metrics,
        valid_samples=len(valid),
        requested_samples=30,
        nonvalid_samples=plateau["nonvalid"] if plateau else 0,
        max_gap_s=str(gap) if gap is not None else None,
        zero_mean_W=base["metrics"]["mean_W"] if base else None,
        target_W=str(target) if target is not None else None,
        error_percent=str(error) if error is not None else None,
        acceptance=acceptance,
        acceptance_reason=reason,
        criteria=criteria,
        stages=stages,
        final_state=record["final_state"],
    )


def provenance(record, bundle):
    def supplied(value, pointer):
        return p.fact(
            value, basis="supplied", refs=[dict(evidence_id="workflow.json", pointer=pointer)]
        )

    controls = bundle.json("controls.json")
    devices = []
    for role, asset in record["plan"]["assets"].items():
        facts = {
            key: supplied(value, "/plan/assets/" + role + "/" + key) for key, value in asset.items()
        }
        returned = next(
            (
                (i, event["reply"])
                for i, event in enumerate(controls["events"])
                if event["device"] == role
                and event["operation"] == "identify"
                and event["status"] == "returned"
            ),
            None,
        )
        facts["reported_identity"] = (
            p.fact(
                returned[1],
                basis="observed",
                refs=[dict(evidence_id="controls.json", pointer=f"/events/{returned[0]}/reply")],
                note="Simulated identity readback, not a physical observation",
            )
            if returned
            else p.fact(note="Identity was not read")
        )
        devices.append(p.equipment(asset["asset_id"], role, facts))
    for role, name in (
        ("meter", "HP 437B (explicit fake)"),
        ("sensor", "8482A (fictional calibrated-input model)"),
        ("fixture", "Fictional RF fixture"),
    ):
        devices.append(
            p.equipment(
                record["plan"]["fixture"]["asset_id"]
                if role == "fixture"
                else "synthetic:dut01:" + role,
                role,
                {"identity": p.fact(note=name + "; no physical identity/calibration claim")},
            )
        )
    subject = p.dut(
        record["plan"]["assets"]["transmitter"]["asset_id"],
        "external_device",
        [device["equipment_id"] for device in devices],
        dict(
            name=supplied(record["plan"]["dut_name"], "/plan/dut_name"),
            frequency_Hz=supplied(record["plan"]["frequency_Hz"], "/plan/frequency_Hz"),
            power_setting=supplied(record["plan"]["power_setting"], "/plan/power_setting"),
            fixture=supplied(record["plan"]["fixture"], "/plan/fixture"),
            supply_profile=supplied(record["plan"]["supply"], "/plan/supply"),
        ),
    )
    return p.record(
        record["run_id"],
        "synthetic",
        WORKFLOW,
        dict(
            operator=supplied(record["operator"], "/operator")
            if record["operator"]
            else p.fact(note="Operator not supplied"),
            measurement_plane=supplied(
                record["plan"]["measurement_plane"], "/plan/measurement_plane"
            ),
        ),
        subject,
        devices,
        list(bundle.entries.values()),
    )


def render(record, result, producer, *, plots):
    def fmt(value):
        return "—" if value is None else "0" if D(value) == 0 else report_sheet._n(value)

    def esc(value):
        return html.escape(str(value))

    plan = record["plan"]
    supply = plan["supply"]
    meta = [
        ("Transmitter", plan["dut_name"] + " | " + plan["assets"]["transmitter"]["serial"]),
        ("Test", "External transmitter output power (single condition)"),
        ("Operator", record["operator"] or "Not recorded"),
        ("When", r.timestamp(record["started_utc"]).strftime("%d %b %Y, %H:%M:%S UTC")),
        (
            "RF conditions",
            f"{fmt(D(plan['frequency_Hz']) / 1000000)} MHz (declared); {plan['power_setting']}",
        ),
        (
            "Supply condition",
            fmt(supply["condition_V"])
            + " V; "
            + fmt(supply["current_limit_A"])
            + " A current-limit setting",
        ),
        ("Measurement plane", plan["measurement_plane"].replace("_", " ")),
    ]
    summary = f"Execution: {result['execution']}. Acceptance: {result['acceptance']}."
    limitation = record["outcome"]["error"] or "; ".join(record["outcome"]["cleanup_errors"])
    zero = (
        "Pre-RF zero: "
        + fmt(D(result["zero_mean_W"]) * 1000000 if result["zero_mean_W"] is not None else None)
        + " µW (source-off indication; no subtraction)."
    )
    output = (
        "RF output: "
        + fmt(result["measured_W"])
        + " W; "
        + str(result["valid_samples"])
        + "/30 valid plateau samples."
    )
    final = result["final_state"]
    cleanup = (
        "Final RF state: "
        + final["rf_state"].upper()
        + ". Supply restoration: "
        + ("VERIFIED" if final["supply_restored"] else "UNVERIFIED")
        + "; last observed "
        + fmt(final["observed_V"])
        + " V and "
        + fmt(final["current_limit_ack_A"])
        + " A current-limit readback."
    )
    criterion = "Acceptance criteria not supplied."
    if result["criteria"]:
        criterion = (
            "Target "
            + fmt(result["target_W"])
            + " W; error "
            + fmt(result["error_percent"])
            + "%; allowed |error| ≤ "
            + fmt(result["criteria"]["max_abs_error_percent"])
            + "%. Inclusive, no guard band."
        )
    reason = result["acceptance_reason"]
    reason_html = (
        "<p>" + esc(reason) + "</p>"
        if reason and reason.rstrip(".") != criterion.rstrip(".")
        else ""
    )
    notes = "All identities, RF samples, and control readbacks are simulated. Frequency/setting readback is not an independent RF frequency measurement. Supplied fixture loss is applied once; sensor calibration is already represented. POWER REF is never controlled. Partial results cannot pass; no failed control is retried."
    footer = [
        "Equipment: fictional TX, HP 437B, 8482A, fixture, supply, and voltage observer.",
        report_sheet.producer_note(producer),
        "Record: " + record["run_id"],
    ]
    metadata = "<br>".join(
        "<strong>" + esc(key) + ":</strong> " + esc(value) for key, value in meta
    )
    sheet = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>RF Output Power Test</title><style>{report_sheet.STYLE}p{{margin:8px 0}}img{{width:100%;max-height:45mm;object-fit:contain}}footer{{break-inside:avoid}}@media print{{body{{font-size:10pt}}h1{{margin-bottom:8px}}}}</style><body><main class="sheet"><h1>RF Output Power Test</h1><p><strong>SYNTHETIC - fictional transmitter and measurements; no physical RF</strong></p><p>{metadata}</p><p><strong>{esc(summary)}</strong></p>{"<p>Run limitation: " + esc(limitation) + "</p>" if limitation else ""}<p>{esc(zero)}</p><p><strong>{esc(output)}</strong></p><p>{esc(cleanup)}</p>{'<img src="transmitter-power.svg" alt="RF plateau power over elapsed time">' if plots else ""}<p>{esc(criterion)}</p>{reason_html}<p>{esc(notes)}</p><footer>{"".join("<p>" + esc(line) + "</p>" for line in footer)}<p>Full controls, sample ranges, timing, provenance, and limitations: appendix.html; results.json; provenance.json.</p></footer></main></body></html>"""
    md = (
        "# RF Output Power Test\n\nSYNTHETIC - fictional transmitter and measurements.\n\n"
        + "\n\n".join(report_sheet._markdown(key + ": " + str(value)) for key, value in meta)
        + "\n\n"
        + "\n\n".join(
            report_sheet._markdown(line)
            for line in (
                summary,
                limitation or "",
                zero,
                output,
                cleanup,
                criterion,
                notes,
                *footer,
            )
        )
        + "\n\nFull evidence: appendix.html.\n"
    )
    return sheet, md


def publish(source, output, *, plots=True):
    source, output = preflight(source, output, plots=plots)
    record, stages, bundle = load(source)
    result = analyze(record, stages)
    prov = provenance(record, bundle)
    p.verify(prov, source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        producer = report_identity.identify()
        for name, obj in (
            ("results.json", result),
            ("provenance.json", prov),
            (
                "metadata.json",
                dict(
                    producer=producer,
                    capture_inventory_sha256=source_hash,
                    analysis="deterministic_only",
                    mode="synthetic",
                ),
            ),
        ):
            (output / name).write_bytes(r.encoded(obj))
        if plots:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt

            fig, axis = plt.subplots(figsize=(7.5, 2.25), layout="constrained")
            points = result["stages"].get("plateau", {}).get("points", [])
            loss = record["plan"]["fixture"]["loss_dB"]
            multiplier = factor(loss) if loss is not None else None
            if record["plan"]["measurement_plane"] == "sensor_input":
                multiplier = D(1)
            valid = (
                [point for point in points if point["status"] == "ok"]
                if multiplier is not None
                else []
            )
            if valid:
                axis.plot(
                    [point["elapsed_s"] for point in valid],
                    [float(D(point["value_W"]) * multiplier) for point in valid],
                    marker=".",
                    linewidth=1,
                )
            else:
                axis.text(
                    0.5,
                    0.5,
                    "No supported plateau power at comparison plane",
                    ha="center",
                    va="center",
                    transform=axis.transAxes,
                )
                axis.set_xticks([])
                axis.set_yticks([])
            axis.set_xlabel("Plateau receipt elapsed time (s)")
            axis.set_ylabel("Power (W)")
            axis.set_title(result["measurement_plane"].replace("_", " ") + " plane")
            axis.grid(axis="y", alpha=0.2)
            for extension in ("png", "svg"):
                fig.savefig(output / ("transmitter-power." + extension), dpi=150)
            plt.close(fig)
        sheet, md = render(record, result, producer, plots=plots)
        (output / "report.html").write_text(sheet, encoding="utf-8")
        (output / "report.md").write_text(md, encoding="utf-8")
        appendix = dict(
            capture=record,
            controls=bundle.json("controls.json"),
            results=result,
            provenance=prov,
            limitations=[
                "Explicit fake controls and fake meter; no physical driver support",
                "Cooperative driver deadlines, not a preemptive hardware timeout guarantee",
                "State readbacks do not prove RF absence or actual current compliance",
                "No physical RF accuracy, uncertainty, or calibration verdict",
            ],
        )
        (output / "appendix.html").write_text(
            '<!doctype html><meta charset="utf-8"><title>DUT-CTRL-01 evidence</title><h1>Technical appendix</h1><pre>'
            + html.escape(r.encoded(appendix).decode())
            + "</pre>",
            encoding="utf-8",
        )
        p.verify(prov, source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
            "Capture changed during report publication",
        )
        _seal(
            output,
            dict(
                schema="hp437b.external-transmitter-report.v1",
                mode="synthetic",
                run_id=record["run_id"],
            ),
        )
    except BaseException as exc:
        (output / "failure.json").write_bytes(r.encoded(dict(status="failed", error=str(exc))))
        raise
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("synthetic")
    run.add_argument("--scenario", choices=fake.SCENARIOS, default="nominal")
    run.add_argument("--plan", type=Path)
    run.add_argument("--criteria", type=Path)
    run.add_argument("--operator")
    run.add_argument("--report-output", type=Path)
    report = commands.add_parser("report")
    report.add_argument("--bundle", required=True, type=Path)
    for sub in (run, report):
        sub.add_argument("--output", required=True, type=Path)
        sub.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "synthetic":
            capture = simulate(
                args.output,
                scenario=args.scenario,
                plan=p._json(p.Bundle(args.plan.parent).read(args.plan.name))
                if args.plan
                else None,
                criteria=p._json(p.Bundle(args.criteria.parent).read(args.criteria.name))
                if args.criteria
                else None,
                operator=args.operator,
                report_output=args.report_output,
                plots=not args.no_plots,
            )
            return 0 if capture["status"] == "completed" else 1
        publish(args.bundle, args.output, plots=not args.no_plots)
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        print(f"DUT-CTRL-01: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
