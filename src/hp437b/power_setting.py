"""WF-04: bounded synthetic power-setting sweeps and offline deterministic reports.

This module models an external transmitter; it cannot open an instrument, key
real RF, or change POWER REF. Synthetic source acknowledgements are not physical
observations. No physical-control backend is implemented here.
"""

import argparse
import csv
import html
import io
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path

from . import provenance as p
from . import report_context, report_identity, report_sheet
from . import reporting as r
from .workflow_report import _seal, preflight

WORKFLOW = "output-power-versus-setting-v1"
SCHEMA = "hp437b.power-setting-capture.v1"
PROFILE = {
    "baseline_count": 3,
    "settling_s": 20,
    "plateau_s": 30,
    "interval_s": 1,
    "whole_run_ceiling_s": 900,
}
SCENARIOS = (
    "nominal",
    "compressed",
    "nonmonotonic",
    "missing-target",
    "missing-loss",
    "sensor-plane",
    "zero-output",
    "timeout",
    "malformed",
    "instrument-error",
    "cancel",
    "source-off-failure",
    "ack-mismatch",
    "missing-point",
)
COLUMNS = ("run_id", "point_id", "stage", "sequence", "elapsed_s", "value_W", "status")


def text(value, maximum=120):
    p.require(
        isinstance(value, str)
        and 0 < len(value.strip()) <= maximum
        and not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "Invalid single-line text",
    )
    return value


def validate_plan(plan):
    p._keys(
        plan,
        (
            "schema",
            "name",
            "frequency_Hz",
            "signal_mode",
            "measurement_plane",
            "fixture_description",
            "points",
        ),
    )
    p.require(plan["schema"] == "hp437b.power-setting-plan.v1", "Unsupported plan")
    text(plan["name"])
    text(plan["signal_mode"], 60)
    text(plan["fixture_description"], 240)
    p.require(
        type(plan["frequency_Hz"]) is int and 100000 <= plan["frequency_Hz"] <= 4200000000,
        "Declared frequency outside synthetic sensor profile",
    )
    p.require(plan["measurement_plane"] in ("DUT_output", "sensor_input"), "Invalid plane")
    p.require(
        isinstance(plan["points"], list) and 1 <= len(plan["points"]) <= 5, "Request 1–5 points"
    )
    for i, point in enumerate(plan["points"], 1):
        p._keys(
            point,
            (
                "point_id",
                "setting",
                "target_W",
                "synthetic_DUT_W",
                "simulation_loss_dB",
                "fixture_loss_dB",
            ),
        )
        p.require(point["point_id"] == f"P{i:02d}", "Point IDs must retain requested order")
        text(point["setting"], 60)
        for key in ("simulation_loss_dB", "fixture_loss_dB"):
            if key == "simulation_loss_dB" or point[key] is not None:
                p.require(0 <= r.number(point[key]) <= 100, "Invalid loss")
        truth = r.number(point["synthetic_DUT_W"])
        p.require(truth == 0 or D("1e-20") <= truth <= 10000, "Invalid synthetic source power")
        p.require(
            truth / factor(point["simulation_loss_dB"]) <= D("0.1"),
            "Synthetic sensor input exceeds profile",
        )
        if point["target_W"] is not None:
            p.require(D("1e-20") <= r.number(point["target_W"]) <= 10000, "Target must be positive")
    return plan


def factor(loss):
    with localcontext() as ctx:
        ctx.prec = 34
        return D(10) ** (r.number(loss) / 10)


def validate_criteria(criteria, plan=None):
    if criteria is None:
        return
    required = {
        "source",
        "decision_rule",
        "max_abs_error_percent",
        "min_samples_per_point",
        "max_gap_s",
    }
    p.require(
        isinstance(criteria, dict)
        and required <= set(criteria) <= required | {"point_limits_percent"},
        "Unsupported criteria fields",
    )
    overrides = criteria.get("point_limits_percent", {})
    p.require(isinstance(overrides, dict) and len(overrides) <= 5, "Invalid point limits")
    ids = (
        {point["point_id"] for point in plan["points"]}
        if plan
        else {f"P{i:02d}" for i in range(1, 6)}
    )
    p.require(set(overrides) <= ids, "Limits reference an unrequested point")
    for value in overrides.values():
        p.require(r.number(value) >= 0, "Negative point error limit")
    text(criteria["source"], 240)
    p.require(criteria["decision_rule"] == "inclusive-no-guard-band", "Unsupported decision rule")
    p.require(r.number(criteria["max_abs_error_percent"]) >= 0, "Negative error limit")
    p.require(
        type(criteria["min_samples_per_point"]) is int
        and 1 <= criteria["min_samples_per_point"] <= 30,
        "Invalid minimum samples",
    )
    p.require(0 < r.number(criteria["max_gap_s"]) <= 30, "Invalid gap limit")


def default_plan(scenario="nominal"):
    p.require(scenario in SCENARIOS, "Unknown scenario")
    points = [
        dict(
            point_id=f"P{i:02d}",
            setting=setting,
            target_W=str(power),
            synthetic_DUT_W=str(power),
            simulation_loss_dB="30",
            fixture_loss_dB="30",
        )
        for i, (setting, power) in enumerate((("Low", 1), ("Medium", 5), ("High", 10)), 1)
    ]
    if scenario == "compressed":
        points[1]["synthetic_DUT_W"], points[2]["synthetic_DUT_W"] = "4.8", "9.5"
    if scenario == "nonmonotonic":
        points[2]["synthetic_DUT_W"] = "4"
    if scenario == "missing-target":
        points[1]["target_W"] = None
    if scenario == "missing-loss":
        points[1]["fixture_loss_dB"] = None
    if scenario == "zero-output":
        points[1]["synthetic_DUT_W"] = "0"
    if scenario == "sensor-plane":
        for point in points:
            point["target_W"] = str(D(point["target_W"]) / 1000)
    return validate_plan(
        dict(
            schema="hp437b.power-setting-plan.v1",
            name="Fictional transmitter",
            frequency_Hz=50000000,
            signal_mode="Continuous carrier (synthetic)",
            measurement_plane="sensor_input" if scenario == "sensor-plane" else "DUT_output",
            fixture_description="Fictional 30 dB fixture; no physical RF",
            points=points,
        )
    )


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
    """Generate virtual receipt samples, source acknowledgements, and sealed evidence."""
    p.require(scenario in SCENARIOS, "Unknown scenario")
    p.require(
        plan is None or scenario == "nominal", "Custom plans require nominal (no injected fault)"
    )
    plan = validate_plan(default_plan(scenario) if plan is None else plan)
    validate_criteria(criteria, plan)
    operator = report_context.resolve_operator(operator)["value"]
    output = Path(output).resolve()
    p.require(not output.exists() and not p.sidecar_path(output).exists(), "Capture output exists")
    if report_output is not None:
        preflight(output, report_output, plots=plots)
    run_id, start = str(uuid.uuid4()), datetime.now(UTC)
    capture = dict(
        schema=SCHEMA,
        workflow_id=WORKFLOW,
        mode="synthetic",
        simulation=True,
        run_id=run_id,
        started_utc=start.isoformat(),
        finished_utc=None,
        profile=PROFILE,
        plan=plan,
        criteria=criteria,
        operator=operator,
        software=report_identity.identify(),
        scenario=scenario,
        status="running",
        points=[],
        final_state=None,
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "starting.json").write_bytes(r.encoded(capture))
    rows, events, elapsed = [], [], 0
    source = False

    def event(operation, point_id=None, **fields):
        events.append(dict(elapsed_s=elapsed, operation=operation, point_id=point_id, **fields))

    def sample(stage, point_id, value, status="ok"):
        nonlocal elapsed
        rows.append(
            dict(
                run_id=run_id,
                point_id=point_id,
                stage=stage,
                sequence=len(rows) + 1,
                elapsed_s=elapsed,
                value_W=str(value) if status == "ok" else "",
                status=status,
            )
        )
        elapsed += 1

    event("source_off_ack", acknowledged=True)
    for _ in range(3):
        sample("baseline-before", "", D("-0.00000002"))
    capture["status"] = "completed"
    for i, point in enumerate(plan["points"]):
        pid = point["point_id"]
        result = dict(
            point_id=pid,
            status="skipped",
            setting_ack=None,
            source_on_ack=False,
            source_off_ack=False,
            reason="Not reached",
        )
        capture["points"].append(result)
        if capture["status"] != "completed":
            continue
        if i == 1 and scenario == "missing-point":
            capture["status"] = "interrupted"
            result["reason"] = "Synthetic stop before point"
            continue
        p.require(source is False, "Setting changes require acknowledged unkeyed source")
        ack = "Different setting" if i == 1 and scenario == "ack-mismatch" else point["setting"]
        result["setting_ack"] = ack
        event("setting_ack", pid, setting=ack, frequency_Hz=plan["frequency_Hz"])
        if ack != point["setting"]:
            result.update(status="failed", reason="Setting acknowledgement mismatch")
            capture["status"] = "failed"
            continue
        source = True
        result["source_on_ack"] = True
        event("source_on_ack", pid, acknowledged=True)
        sensor = D(point["synthetic_DUT_W"]) / factor(point["simulation_loss_dB"])
        # Synthetic receipt precision matches a five-significant-digit power frame.
        sensor = D(format(sensor, ".4E"))
        for _ in range(20):
            sample("settling", pid, sensor)
        result.update(status="completed", reason="")
        for j in range(30):
            if (
                i == 1
                and j == 3
                and scenario in ("timeout", "malformed", "instrument-error", "cancel")
            ):
                status = "interrupted" if scenario == "cancel" else "failed"
                sample("plateau", pid, sensor, status)
                result.update(status=status, reason=f"Synthetic {scenario}; not a backend fault")
                capture["status"] = status
                if scenario in ("timeout", "malformed"):
                    source = None
                    event("communication_uncertain", pid)
                break
            sample("plateau", pid, sensor)
        if source is not None:
            event("source_off_attempt", pid)
            if i == 1 and scenario == "source-off-failure":
                source = None
                result.update(status="failed", reason="Synthetic source-off failure; no retry")
                capture["status"] = "failed"
            else:
                source = False
                result["source_off_ack"] = True
                event("source_off_ack", pid, acknowledged=True)
    if capture["status"] == "completed":
        for _ in range(3):
            sample("baseline-after", "", D("-0.00000002"))
    capture["finished_utc"] = (start + timedelta(seconds=elapsed)).isoformat()
    capture["final_state"] = {
        "external_source_off": True if source is False else None,
        "meter_reference_off": True,
        "hardware_opened": False,
    }
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    (output / "samples.csv").write_text(stream.getvalue(), newline="", encoding="utf-8")
    (output / "workflow.json").write_bytes(r.encoded(capture))
    (output / "trace.json").write_bytes(r.encoded(events))
    _seal(
        output,
        {"schema": "hp437b.power-setting-inventory.v1", "mode": "synthetic", "run_id": run_id},
    )
    if report_output is not None:
        publish(output, report_output, plots=plots)
    return capture


def load(source):
    """Verify inventory and semantic joins before using any saved values."""
    bundle = p.Bundle(source)
    inventory = bundle.inventory("artifacts.json", "synthetic")
    capture = bundle.json("workflow.json")
    p._keys(
        capture,
        (
            "schema",
            "workflow_id",
            "mode",
            "simulation",
            "run_id",
            "started_utc",
            "finished_utc",
            "profile",
            "plan",
            "criteria",
            "operator",
            "software",
            "scenario",
            "status",
            "points",
            "final_state",
        ),
    )
    p.require(
        inventory.get("schema") == "hp437b.power-setting-inventory.v1"
        and inventory.get("run_id") == capture["run_id"],
        "Inventory/run mismatch",
    )
    starting = bundle.json("starting.json")
    expected_start = {
        **capture,
        "status": "running",
        "finished_utc": None,
        "points": [],
        "final_state": None,
    }
    p.require(starting == expected_start, "Starting/final metadata mismatch")
    p.require(
        capture["schema"] == SCHEMA
        and capture["workflow_id"] == WORKFLOW
        and capture["mode"] == "synthetic"
        and capture["simulation"] is True,
        "Unsupported capture/mode",
    )
    uuid.UUID(capture["run_id"])
    validate_plan(capture["plan"])
    validate_criteria(capture["criteria"], capture["plan"])
    report_context.validate_operator(capture["operator"])
    p.require(
        capture["profile"] == PROFILE and capture["scenario"] in SCENARIOS, "Unsupported profile"
    )
    p.require(capture["status"] in ("completed", "failed", "interrupted"), "Unfinished capture")
    span = (
        r.timestamp(capture["finished_utc"]) - r.timestamp(capture["started_utc"])
    ).total_seconds()
    p.require(0 <= span <= PROFILE["whole_run_ceiling_s"], "Invalid run time")
    p.require(len(capture["points"]) == len(capture["plan"]["points"]), "Missing requested point")
    reader = csv.DictReader(io.StringIO(bundle.read("samples.csv").decode("utf-8")))
    p.require(reader.fieldnames == list(COLUMNS), "Invalid sample columns")
    rows = list(reader)
    p.require(3 <= len(rows) <= 256 and span == len(rows), "Invalid sample count/time")
    for index, row in enumerate(rows):
        p.require(None not in row and None not in row.values(), "Malformed sample row")
        p.require(
            row["run_id"] == capture["run_id"]
            and row["sequence"] == str(index + 1)
            and row["elapsed_s"] == str(index),
            "Sample/run/time join failed",
        )
        p.require(
            row["stage"] in ("baseline-before", "baseline-after", "settling", "plateau")
            and row["status"] in ("ok", "failed", "interrupted"),
            "Invalid sample state",
        )
        if row["status"] == "ok":
            p.require(
                (
                    r.number(row["value_W"]) == 0
                    or D("1e-30") <= abs(r.number(row["value_W"])) <= D("0.1")
                ),
                "Invalid synthetic sensor value",
            )
        else:
            p.require(row["value_W"] == "", "Failed row carries a value")
    # Verify exact ordered baseline/point stages, counts, acknowledgements, and stop policy.
    p.require(
        all(
            row["stage"] == "baseline-before" and row["point_id"] == "" and row["status"] == "ok"
            for row in rows[:3]
        ),
        "Missing pre-RF zero",
    )
    offset, stopped = 3, False
    for _i, (point, outcome) in enumerate(
        zip(capture["plan"]["points"], capture["points"], strict=True)
    ):
        pid = point["point_id"]
        p._keys(
            outcome,
            ("point_id", "status", "setting_ack", "source_on_ack", "source_off_ack", "reason"),
        )
        p.require(
            outcome["point_id"] == pid
            and outcome["status"] in ("completed", "failed", "interrupted", "skipped"),
            "Invalid point join",
        )
        text(outcome["reason"] or "Completed", 240)
        p.require(
            outcome["status"] == "completed" or bool(outcome["reason"]),
            "Missing failure/skip reason",
        )
        for key in ("source_on_ack", "source_off_ack"):
            p.require(type(outcome[key]) is bool, "Invalid acknowledgement type")
        group = []
        while offset < len(rows) and rows[offset]["point_id"] == pid:
            group.append(rows[offset])
            offset += 1
        p.require(
            not stopped
            or (
                outcome["status"] == "skipped"
                and not group
                and outcome["setting_ack"] is None
                and not outcome["source_on_ack"]
                and not outcome["source_off_ack"]
            ),
            "Progression after failed point",
        )
        if outcome["source_on_ack"]:
            p.require(
                outcome["setting_ack"] == point["setting"] and 21 <= len(group) <= 50,
                "Missing setting acknowledgement/samples",
            )
            p.require(
                all(row["stage"] == "settling" and row["status"] == "ok" for row in group[:20])
                and all(row["stage"] == "plateau" for row in group[20:]),
                "Invalid point phases",
            )
            p.require(all(row["status"] == "ok" for row in group[:-1]), "Samples after failure")
        else:
            p.require(
                not group and not outcome["source_off_ack"],
                "Samples without source acknowledgement",
            )
        if outcome["status"] == "completed":
            p.require(
                len(group) == 50
                and all(row["status"] == "ok" for row in group)
                and outcome["source_off_ack"],
                "Incomplete point marked completed",
            )
        else:
            p.require(
                outcome["status"] != "skipped" or (not group and outcome["setting_ack"] is None),
                "Skipped point contains capture/control evidence",
            )
            p.require(
                not outcome["source_off_ack"] or outcome["source_on_ack"],
                "Off acknowledgement without source-on",
            )
            stopped = True
    failed = any(point["status"] == "failed" for point in capture["points"])
    interrupted = any(point["status"] in ("interrupted", "skipped") for point in capture["points"])
    p.require(
        capture["status"]
        == ("failed" if failed else "interrupted" if interrupted else "completed"),
        "Point/execution outcome mismatch",
    )
    tail = rows[offset:]
    complete = all(point["status"] == "completed" for point in capture["points"])
    p.require((capture["status"] == "completed") == complete, "Execution/coverage mismatch")
    p.require(
        (
            complete
            and len(tail) == 3
            and all(
                row["stage"] == "baseline-after" and row["point_id"] == "" and row["status"] == "ok"
                for row in tail
            )
        )
        or (not complete and not tail),
        "Invalid post-RF baseline",
    )
    final = capture["final_state"]
    p._keys(final, ("external_source_off", "meter_reference_off", "hardware_opened"))
    p.require(
        final["meter_reference_off"] is True
        and final["hardware_opened"] is False
        and (final["external_source_off"] is None or final["external_source_off"] is True),
        "Invalid synthetic final state",
    )
    p.require(
        not complete or final["external_source_off"] is True, "Completed with unknown source state"
    )
    events = bundle.json("trace.json")
    p.require(isinstance(events, list) and len(events) <= 40, "Invalid source trace")
    # Source actor has no meter command interface, and cannot key while state is unknown.
    state, selected, previous = None, None, -1
    for event in events:
        t = event["elapsed_s"]
        p.require(type(t) is int and previous <= t <= span, "Invalid source event time")
        previous = t
        op, pid = event["operation"], event["point_id"]
        p.require(
            pid is None or pid in [point["point_id"] for point in capture["points"]],
            "Invalid event point",
        )
        if op == "source_off_ack":
            p.require(event["acknowledged"] is True, "Invalid off acknowledgement")
            state = False
        elif op == "setting_ack":
            p.require(state is False, "Setting changed while source not known off")
            selected = pid
        elif op == "source_on_ack":
            p.require(
                state is False and selected == pid and event["acknowledged"] is True,
                "Invalid source key sequence",
            )
            state = True
        elif op == "source_off_attempt":
            p.require(state is True, "Retry/invalid source-off action")
            state = None
        elif op == "communication_uncertain":
            state = None
        else:
            raise p.ProvenanceError("Unknown source operation")
    p.require(
        (state is False) == (final["external_source_off"] is True), "Trace/final state mismatch"
    )
    expected_events = [
        {"elapsed_s": 0, "operation": "source_off_ack", "point_id": None, "acknowledged": True}
    ]
    cursor = 3
    for point, outcome in zip(capture["plan"]["points"], capture["points"], strict=True):
        pid = point["point_id"]

        def append(operation, pid=pid, **fields):
            expected_events.append(
                dict(elapsed_s=cursor, operation=operation, point_id=pid, **fields)  # noqa: B023
            )

        if outcome["setting_ack"] is not None:
            append(
                "setting_ack",
                setting=outcome["setting_ack"],
                frequency_Hz=capture["plan"]["frequency_Hz"],
            )
        if outcome["source_on_ack"]:
            append("source_on_ack", acknowledged=True)
            group = [row for row in rows if row["point_id"] == pid]
            cursor += len(group)
            if capture["scenario"] in ("timeout", "malformed") and outcome["status"] == "failed":
                append("communication_uncertain")
            else:
                append("source_off_attempt")
                if outcome["source_off_ack"]:
                    append("source_off_ack", acknowledged=True)
    p.require(events == expected_events, "Source trace/point acknowledgement mismatch")
    return capture, rows, bundle


def analyze(capture, rows):
    """Use recorded sensor values and supplied losses, never synthetic source truth."""
    results = []
    criteria = capture["criteria"]
    with localcontext() as ctx:
        ctx.prec = 34
        for point, outcome in zip(capture["plan"]["points"], capture["points"], strict=True):
            samples = [
                row
                for row in rows
                if row["point_id"] == point["point_id"]
                and row["stage"] == "plateau"
                and row["status"] == "ok"
            ]
            values = [D(row["value_W"]) for row in samples]
            mean = sum(values) / len(values) if values else None
            dut = (
                mean * factor(point["fixture_loss_dB"])
                if mean is not None and point["fixture_loss_dB"] is not None
                else None
            )
            measured = dut if capture["plan"]["measurement_plane"] == "DUT_output" else mean
            target = None if point["target_W"] is None else D(point["target_W"])
            error = measured - target if measured is not None and target is not None else None
            percent = 100 * error / target if error is not None else None
            db = 10 * (measured / target).log10() if error is not None and measured > 0 else None
            gaps = [
                D(b["elapsed_s"]) - D(a["elapsed_s"])
                for a, b in zip(samples, samples[1:], strict=False)
            ]
            maximum_gap = max(gaps) if gaps else None
            reason = (
                "Incomplete point"
                if outcome["status"] != "completed"
                else "Missing fixture loss or sensor samples"
                if measured is None
                else "Target not supplied"
                if target is None
                else "Mean outside nominal sensor measurement range"
                if mean is None or not D("0.000001") <= mean <= D("0.1")
                else None
            )
            acceptance = "NOT EVALUATED"
            if criteria is not None and reason is None:
                if (
                    len(values) < criteria["min_samples_per_point"]
                    or maximum_gap is None
                    or maximum_gap > D(criteria["max_gap_s"])
                ):
                    reason = "Insufficient sample/timing coverage"
                else:
                    acceptance = (
                        "PASS"
                        if abs(percent)
                        <= D(
                            criteria.get("point_limits_percent", {}).get(
                                point["point_id"], criteria["max_abs_error_percent"]
                            )
                        )
                        else "FAIL"
                    )
            if criteria is None and reason is None:
                reason = "Acceptance limits not supplied"
            result = dict(
                point_id=point["point_id"],
                setting=point["setting"],
                status=outcome["status"],
                valid_samples=len(values),
                sensor_mean_W=mean,
                DUT_mean_W=dut,
                measured_W=measured,
                target_W=target,
                error_W=error,
                error_percent=percent,
                error_dB=db,
                sensor_min_W=min(values) if values else None,
                sensor_max_W=max(values) if values else None,
                max_gap_s=maximum_gap,
                acceptance=acceptance,
                reason=reason,
                dB_unavailable_reason="Nonpositive/missing mean or target" if db is None else None,
            )
            results.append(
                {
                    key: str(value) if isinstance(value, D) else value
                    for key, value in result.items()
                }
            )
    overall = "NOT EVALUATED"
    if capture["status"] == "completed" and all(
        row["acceptance"] in ("PASS", "FAIL") for row in results
    ):
        overall = "FAIL" if any(row["acceptance"] == "FAIL" for row in results) else "PASS"
    baseline = [D(row["value_W"]) for row in rows if row["stage"] == "baseline-before"]
    return dict(
        schema="hp437b.power-setting-results.v1",
        workflow_id=WORKFLOW,
        run_id=capture["run_id"],
        mode="synthetic",
        execution=capture["status"],
        measurement_plane=capture["plan"]["measurement_plane"],
        points=results,
        completed_points=sum(row["status"] == "completed" for row in results),
        requested_points=len(results),
        zero_mean_W=str(sum(baseline) / len(baseline)),
        acceptance=overall,
        criteria=criteria,
    )


def provenance(capture, bundle):
    def fact(value, pointer):
        return p.fact(
            value, basis="supplied", refs=[{"evidence_id": "workflow.json", "pointer": pointer}]
        )

    ids = ["synthetic:wf04:" + role for role in ("transmitter", "meter", "sensor", "fixture")]
    devices = [
        p.equipment(
            identity, role, {"identity": p.fact(note="Fictional equipment; no physical identity")}
        )
        for identity, role in zip(ids, ("source", "meter", "sensor", "fixture"), strict=True)
    ]
    subject = p.dut(
        "synthetic:wf04:dut",
        "external_device",
        ids,
        {
            "name": fact(capture["plan"]["name"], "/plan/name"),
            "frequency_Hz": fact(capture["plan"]["frequency_Hz"], "/plan/frequency_Hz"),
            "signal_mode": fact(capture["plan"]["signal_mode"], "/plan/signal_mode"),
            "fixture_description": fact(
                capture["plan"]["fixture_description"], "/plan/fixture_description"
            ),
            "power_setting_plan": fact(capture["plan"]["points"], "/plan/points"),
        },
    )
    return p.record(
        capture["run_id"],
        "synthetic",
        WORKFLOW,
        {
            "operator": fact(capture["operator"], "/operator")
            if capture["operator"]
            else p.fact(note="Operator not supplied"),
            "criteria": fact(capture["criteria"], "/criteria")
            if capture["criteria"] is not None
            else p.fact(note="Acceptance criteria not supplied"),
            "measurement_plane": fact(
                capture["plan"]["measurement_plane"], "/plan/measurement_plane"
            ),
        },
        subject,
        devices,
        list(bundle.entries.values()),
    )


def publish(source, output, *, plots=True):
    source, output = preflight(source, output, plots=plots)
    capture, rows, bundle = load(source)
    result = analyze(capture, rows)
    record = provenance(capture, bundle)
    p.verify(record, source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "results.json").write_bytes(r.encoded(result))
        (output / "provenance.json").write_bytes(r.encoded(record))
        producer = report_identity.identify()
        (output / "metadata.json").write_bytes(
            r.encoded(
                dict(
                    producer=producer,
                    capture_inventory_sha256=source_hash,
                    analysis="deterministic_only",
                    mode="synthetic",
                )
            )
        )
        if plots:
            import matplotlib

            matplotlib.use("Agg")
            from matplotlib import pyplot as plt

            fig, axis = plt.subplots(figsize=(7.5, 2.25), layout="constrained")
            for key, marker, label in (
                ("target_W", "o", "Target"),
                ("measured_W", "x", "Measured"),
            ):
                points = [
                    (i, float(row[key]))
                    for i, row in enumerate(result["points"])
                    if row[key] is not None and (key == "target_W" or row["status"] == "completed")
                ]
                axis.scatter(
                    [x for x, _ in points], [y for _, y in points], marker=marker, label=label
                )
            axis.set_xticks(
                range(len(result["points"])), [row["point_id"] for row in result["points"]]
            )
            axis.set_xlabel("Requested setting (point IDs in table)")
            axis.set_ylabel("Power (W)")
            axis.set_title("Declared " + result["measurement_plane"].replace("_", " ") + " plane")
            axis.grid(axis="y", alpha=0.2)
            axis.legend()
            for extension in ("png", "svg"):
                fig.savefig(output / ("power-setting." + extension), dpi=150)
            plt.close(fig)

        def e(value):
            return html.escape(str(value))

        def fmt(value):
            return "—" if value is None else "0" if D(value) == 0 else report_sheet._n(value)

        table = "".join(
            "<tr>"
            + "".join(
                f"<td>{e(value)}</td>"
                for value in (
                    row["point_id"] + " · " + row["setting"],
                    fmt(row["target_W"]),
                    fmt(row["measured_W"]),
                    fmt(row["error_percent"]),
                    fmt(row["error_dB"]),
                    str(row["valid_samples"]) + "/30",
                    row["status"],
                )
            )
            + "</tr>"
            for row in result["points"]
        )
        harness = report_sheet.producer_note(producer)
        criteria_note = (
            "Acceptance limits not supplied."
            if capture["criteria"] is None
            else f"Criterion: |error| ≤ {capture['criteria']['max_abs_error_percent']}%; "
            f"{capture['criteria']['source']}; inclusive, no guard band."
            + (
                " Point-specific limits: see appendix."
                if capture["criteria"].get("point_limits_percent")
                else ""
            )
        )
        sheet = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>RF Output Power Test</title>
<style>{report_sheet.STYLE} table{{width:100%;border-collapse:collapse}}td,th{{padding:5px;text-align:left;border-bottom:1px solid #ddd}}footer{{font-size:9pt;break-inside:avoid}}img{{width:100%;max-height:48mm;object-fit:contain}}td{{overflow-wrap:anywhere}}h1{{margin-bottom:8px}}p{{margin:7px 0}}@media print{{body{{font-size:10pt}}td,th{{padding:4px;font-size:9pt}}}}</style><body><main class="sheet">
<h1>RF Output Power Test</h1><p><strong>SYNTHETIC — fictional transmitter and measurements; no physical RF</strong></p>
<p><strong>Test:</strong> Output power versus setting<br><strong>Transmitter:</strong> {e(capture["plan"]["name"])}<br>
<strong>Operator:</strong> {e(capture["operator"] or "Not recorded")}<br><strong>When:</strong> {e(r.timestamp(capture["started_utc"]).astimezone(UTC).strftime("%d %b %Y, %H:%M:%S UTC"))}<br>
<strong>Frequency:</strong> {capture["plan"]["frequency_Hz"] / 1e6:g} MHz (declared)<br>
<strong>Signal:</strong> {e(capture["plan"]["signal_mode"])}<br>
<strong>Measurement plane:</strong> {e(result["measurement_plane"].replace("_", " "))}</p>
<p><strong>Execution:</strong> {e(result["execution"])}; {result["completed_points"]}/{result["requested_points"]} points complete.
<strong>Acceptance:</strong> {e(result["acceptance"])}</p>
<p><strong>Final external source:</strong> {"off acknowledged (synthetic)" if capture["final_state"]["external_source_off"] else "UNKNOWN (synthetic); recovery not asserted"}.</p>
<p><strong>Pre-RF zero:</strong> {fmt(D(result["zero_mean_W"]) * 1000000)} µW (3 source-off samples; no subtraction).</p>
<table><thead><tr><th>Setting</th><th>Target W</th><th>Measured W</th><th>Error %</th><th>Error dB</th><th>Valid</th><th>State</th></tr></thead><tbody>{table}</tbody></table>
{'<img src="power-setting.svg" alt="Target and measured power at each requested setting">' if plots else ""}
<p>{e(criteria_note)}</p><p>Missing values are unavailable, not zero. Partial-point values are descriptive only. See the technical appendix for point reasons and decision criteria.</p>
<p>Supplied fixture loss is applied once for the DUT output plane. Sensor-input comparisons use uncorrected sensor watts. Sensor calibration is assumed already represented. Frequency and setting acknowledgements are not independent measurements.</p>
<footer><p><strong>Equipment:</strong> Fictional transmitter, HP 437B, 8482A, and fixture. {e(capture["plan"]["fixture_description"])}</p>
<p>{e(harness)}</p><p><strong>Record:</strong> {e(capture["run_id"])}<br>Evidence and limitations: appendix.html; results.json; provenance.json.</p></footer></main></body></html>"""
        (output / "report.html").write_text(sheet, encoding="utf-8")
        appendix = dict(
            capture=capture,
            results=result,
            provenance=record,
            limitations=[
                "Synthetic only; no hardware/backend qualification",
                "No uncertainty or accuracy verdict",
                "POWER REF cannot supply a multi-level sweep",
                "External source shutdown requires a future qualified control path",
            ],
        )
        (output / "appendix.html").write_text(
            '<!doctype html><meta charset="utf-8"><title>WF-04 evidence</title><h1>Technical appendix</h1><pre>'
            + e(r.encoded(appendix).decode())
            + "</pre>",
            encoding="utf-8",
        )
        (output / "report.md").write_text(
            "# RF Output Power Test\n\nSYNTHETIC — Output power versus setting.\n\n"
            + "| Setting | Target W | Measured W | Error % | State |\n| --- | --- | --- | --- | --- |\n"
            + "\n".join(
                "| "
                + " | ".join(
                    report_sheet._markdown(str(value))
                    for value in (
                        row["setting"],
                        fmt(row["target_W"]),
                        fmt(row["measured_W"]),
                        fmt(row["error_percent"]),
                        row["status"],
                    )
                )
                + " |"
                for row in result["points"]
            )
            + f"\n\nTransmitter: {report_sheet._markdown(capture['plan']['name'])}. "
            + f"Operator: {report_sheet._markdown(capture['operator'] or 'Not recorded')}.\n\n"
            + f"When: {capture['started_utc']}. Declared frequency: {capture['plan']['frequency_Hz']} Hz. "
            + f"Signal: {report_sheet._markdown(capture['plan']['signal_mode'])}. "
            + f"Plane: {result['measurement_plane']}.\n\n"
            + f"Pre-RF zero: {fmt(D(result['zero_mean_W']) * 1000000)} µW (three samples; no subtraction).\n\n"
            + f"Execution: {result['execution']}; {result['completed_points']}/{result['requested_points']} points complete. "
            + f"Acceptance: {result['acceptance']}. "
            + (
                "Final source: off acknowledged (synthetic).\n\n"
                if capture["final_state"]["external_source_off"]
                else "Final source: UNKNOWN (synthetic).\n\n"
            )
            + f"{report_sheet._markdown(criteria_note)}\n\nEquipment: fictional transmitter, HP 437B, 8482A, and fixture.\n\n"
            + f"{report_sheet._markdown(harness)}\n\nRecord: {capture['run_id']}. Complete evidence: appendix.html.\n",
            encoding="utf-8",
        )
        p.verify(record, source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
            "Capture changed during publication",
        )
        _seal(
            output,
            {
                "schema": "hp437b.power-setting-report.v1",
                "mode": "synthetic",
                "run_id": capture["run_id"],
            },
        )
    except BaseException as exc:
        (output / "failure.json").write_bytes(r.encoded({"status": "failed", "error": str(exc)}))
        raise
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("synthetic")
    run.add_argument("--scenario", choices=SCENARIOS, default="nominal")
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
        print(f"WF-04: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
