"""WF-05: bounded synthetic frequency sweeps and offline deterministic reports.

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

WORKFLOW = "output-power-versus-frequency-v1"
SCHEMA = "hp437b.frequency-sweep-capture.v1"
PROFILE = {
    "baseline_count": 3,
    "settling_s": 20,
    "plateau_s": 30,
    "interval_s": 1,
    "whole_run_ceiling_s": 900,
}
SCENARIOS = (
    "nominal",
    "band-droop",
    "unequal-corrections",
    "meter-corrected",
    "repeated-anchor",
    "missing-target",
    "missing-loss",
    "missing-factor",
    "sensor-plane",
    "zero-output",
    "timeout",
    "malformed",
    "instrument-error",
    "cancel",
    "source-off-failure",
    "frequency-mismatch",
    "frequency-unverified",
    "factor-mismatch",
    "missing-band",
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
            "power_setting",
            "signal_mode",
            "measurement_plane",
            "fixture_description",
            "points",
        ),
    )
    p.require(plan["schema"] == "hp437b.frequency-sweep-plan.v1", "Unsupported plan")
    text(plan["name"])
    text(plan["power_setting"], 60)
    text(plan["signal_mode"], 60)
    text(plan["fixture_description"], 240)
    p.require(plan["measurement_plane"] in ("DUT_output", "sensor_input"), "Invalid plane")
    p.require(
        isinstance(plan["points"], list) and 1 <= len(plan["points"]) <= 5, "Request 1–5 points"
    )
    for i, point in enumerate(plan["points"], 1):
        p._keys(
            point,
            (
                "point_id",
                "frequency_Hz",
                "target_W",
                "synthetic_DUT_W",
                "simulation_loss_dB",
                "simulation_sensor_factor_percent",
                "fixture_loss_dB",
                "fixture_source",
                "sensor_factor_percent",
                "factor_source",
                "factor_applied_in",
            ),
        )
        p.require(point["point_id"] == f"P{i:02d}", "Point IDs must retain requested order")
        p.require(
            type(point["frequency_Hz"]) is int and 100000 <= point["frequency_Hz"] <= 4200000000,
            "Frequency must be explicitly declared within 100 kHz–4.2 GHz",
        )
        for key in ("simulation_loss_dB", "fixture_loss_dB"):
            if key == "simulation_loss_dB" or point[key] is not None:
                p.require(0 <= r.number(point[key]) <= 100, "Invalid loss")
        for key in ("simulation_sensor_factor_percent", "sensor_factor_percent"):
            if key == "simulation_sensor_factor_percent" or point[key] is not None:
                p.require(
                    1 <= r.number(point[key]) <= 150, "Synthetic factor outside 1–150% profile"
                )
        for value, source in (
            ("fixture_loss_dB", "fixture_source"),
            ("sensor_factor_percent", "factor_source"),
        ):
            if point[value] is None:
                p.require(point[source] is None, "Unknown correction must retain unknown source")
            else:
                text(point[source], 240)
        p.require(
            point["factor_applied_in"] in ("analysis", "meter"),
            "Declare where the sensor factor is applied",
        )
        p.require(
            point["factor_applied_in"] != "meter" or point["sensor_factor_percent"] is not None,
            "Meter-applied factor requires a known expected factor",
        )
        truth = r.number(point["synthetic_DUT_W"])
        p.require(truth == 0 or D("1e-20") <= truth <= 10000, "Invalid synthetic source power")
        incident = truth / factor(point["simulation_loss_dB"])
        response = incident * D(point["simulation_sensor_factor_percent"]) / 100
        indicated = (
            response * 100 / D(point["sensor_factor_percent"])
            if point["factor_applied_in"] == "meter"
            else response
        )
        p.require(
            indicated == 0 or D("1e-30") <= indicated <= D(".1"),
            "Synthetic indication outside finite CSV profile",
        )
        p.require(
            incident <= D(".1") and response <= D(".1"),
            "Synthetic sensor input/response exceeds profile",
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
    required = {"source", "decision_rule", "min_samples_per_point", "max_gap_s"}
    optional = {"max_abs_error_percent", "point_limits_percent", "max_spread_dB"}
    p.require(
        isinstance(criteria, dict) and required <= set(criteria) <= required | optional,
        "Unsupported criteria fields",
    )
    p.require(
        "max_abs_error_percent" in criteria or "max_spread_dB" in criteria,
        "Supply an error or spread limit",
    )
    text(criteria["source"], 240)
    p.require(criteria["decision_rule"] == "inclusive-no-guard-band", "Unsupported decision rule")
    for key in ("max_abs_error_percent", "max_spread_dB"):
        if key in criteria:
            p.require(r.number(criteria[key]) >= 0, "Negative limit")
    overrides = criteria.get("point_limits_percent", {})
    p.require(
        isinstance(overrides, dict)
        and len(overrides) <= 5
        and (not overrides or "max_abs_error_percent" in criteria),
        "Invalid point limits",
    )
    ids = (
        {point["point_id"] for point in plan["points"]}
        if plan
        else {f"P{i:02d}" for i in range(1, 6)}
    )
    p.require(set(overrides) <= ids, "Limits reference an unrequested point")
    for value in overrides.values():
        p.require(r.number(value) >= 0, "Negative point limit")
    p.require(
        type(criteria["min_samples_per_point"]) is int
        and 1 <= criteria["min_samples_per_point"] <= 30,
        "Invalid sample minimum",
    )
    p.require(0 < r.number(criteria["max_gap_s"]) <= 30, "Invalid gap limit")


def default_plan(scenario="nominal"):
    p.require(scenario in SCENARIOS, "Unknown scenario")
    points = []
    for i, frequency in enumerate((1800000, 3500000, 7000000, 14000000, 28000000), 1):
        points.append(
            dict(
                point_id=f"P{i:02d}",
                frequency_Hz=frequency,
                target_W="5",
                synthetic_DUT_W="5",
                simulation_loss_dB="30",
                simulation_sensor_factor_percent="100",
                fixture_loss_dB="30",
                fixture_source="Fictional fixture table r1; exact point",
                sensor_factor_percent="100",
                factor_source="Fictional sensor table r1; exact point",
                factor_applied_in="analysis",
            )
        )
    if scenario == "band-droop":
        for point, power in zip(points, ("4.8", "5", "5.1", "4.9", "4.7"), strict=True):
            point["synthetic_DUT_W"] = power
    if scenario in ("unequal-corrections", "meter-corrected", "factor-mismatch"):
        for i, point in enumerate(points):
            point["sensor_factor_percent"] = point["simulation_sensor_factor_percent"] = str(98 - i)
            point["fixture_loss_dB"] = point["simulation_loss_dB"] = "40" if i % 2 else "30"
            if scenario != "unequal-corrections":
                point["factor_applied_in"] = "meter"
    if scenario == "repeated-anchor":
        points[-1] = {**points[0], "point_id": "P05", "synthetic_DUT_W": "4.9"}
    if scenario == "missing-factor":
        points[1]["sensor_factor_percent"] = points[1]["factor_source"] = None
    if scenario == "missing-loss":
        points[1]["fixture_loss_dB"] = points[1]["fixture_source"] = None
    if scenario == "missing-target":
        points[1]["target_W"] = None
    if scenario == "zero-output":
        points[1]["synthetic_DUT_W"] = "0"
    if scenario == "sensor-plane":
        for point in points:
            point["target_W"] = ".005"
    return validate_plan(
        dict(
            schema="hp437b.frequency-sweep-plan.v1",
            name="Fictional transmitter",
            power_setting="Nominal output (fixed)",
            signal_mode="Continuous carrier (synthetic)",
            measurement_plane="sensor_input" if scenario == "sensor-plane" else "DUT_output",
            fixture_description="Fictional frequency-dependent fixture; no physical RF",
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
    pdf=False,
    package=False,
):
    """Generate virtual receipt samples, source acknowledgements, and sealed evidence."""
    p.require(scenario in SCENARIOS, "Unknown scenario")
    p.require(
        plan is None or scenario == "nominal", "Custom plans require nominal (no injected fault)"
    )
    plan = validate_plan(default_plan(scenario) if plan is None else plan)
    validate_criteria(criteria, plan)
    operator = report_context.resolve_operator(operator)["value"]
    pdf = pdf or package
    p.require(not pdf or report_output is not None, "PDF/package delivery requires report output")
    output = Path(output).resolve()
    p.require(not output.exists() and not p.sidecar_path(output).exists(), "Capture output exists")
    if report_output is not None:
        preflight(output, report_output, plots=plots)
        from .report_delivery import preflight_delivery

        preflight_delivery(output, report_output, pdf=pdf, package=package)
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
            frequency_ack_Hz=None,
            factor_ack_percent=None,
            source_on_ack=False,
            source_off_ack=False,
            reason="Not reached",
        )
        capture["points"].append(result)
        if capture["status"] != "completed":
            continue
        if i == 1 and scenario == "missing-band":
            capture["status"] = "interrupted"
            result["reason"] = "Synthetic stop before point"
            continue
        p.require(source is False, "Frequency changes require acknowledged unkeyed source")
        ack = (
            point["frequency_Hz"] + 1000000
            if i == 1 and scenario == "frequency-mismatch"
            else None
            if i == 1 and scenario == "frequency-unverified"
            else point["frequency_Hz"]
        )
        result["frequency_ack_Hz"] = ack
        event(
            "frequency_ack_Hz",
            pid,
            frequency_Hz=ack,
            power_setting=plan["power_setting"],
            signal_mode=plan["signal_mode"],
        )
        if ack != point["frequency_Hz"]:
            result.update(
                status="failed", reason="Synthetic frequency acknowledgement missing/mismatched"
            )
            capture["status"] = "failed"
            continue
        expected_factor = (
            point["sensor_factor_percent"] if point["factor_applied_in"] == "meter" else "100"
        )
        factor_ack = (
            str(D(expected_factor) - 1)
            if i == 1 and scenario == "factor-mismatch"
            else expected_factor
        )
        result["factor_ack_percent"] = factor_ack
        event("meter_factor_ack", pid, percent=factor_ack)
        if D(factor_ack) != D(expected_factor):
            result.update(status="failed", reason="Synthetic meter factor readback mismatch")
            capture["status"] = "failed"
            continue
        source = True
        result["source_on_ack"] = True
        event("source_on_ack", pid, acknowledged=True)
        sensor = D(point["synthetic_DUT_W"]) / factor(point["simulation_loss_dB"])
        sensor *= D(point["simulation_sensor_factor_percent"]) / D(factor_ack)
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
        {"schema": "hp437b.frequency-sweep-inventory.v1", "mode": "synthetic", "run_id": run_id},
    )
    if report_output is not None:
        publish(output, report_output, plots=plots, pdf=pdf, package=package)
    return capture


def load(source):
    """Verify inventory and semantic joins before using any saved values."""
    bundle = p.Bundle(source)
    inventory = bundle.inventory("artifacts.json", "synthetic")
    capture = bundle.json("workflow.json")
    from . import controlled_sweep

    if capture.get("schema") == controlled_sweep.SCHEMA:
        return controlled_sweep.load("WF-05", source)
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
        inventory.get("schema") == "hp437b.frequency-sweep-inventory.v1"
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
            (
                "point_id",
                "status",
                "frequency_ack_Hz",
                "factor_ack_percent",
                "source_on_ack",
                "source_off_ack",
                "reason",
            ),
        )
        p.require(
            outcome["point_id"] == pid
            and outcome["status"] in ("completed", "failed", "interrupted", "skipped"),
            "Invalid point join",
        )
        p.require(
            outcome["frequency_ack_Hz"] is None or type(outcome["frequency_ack_Hz"]) is int,
            "Invalid frequency acknowledgement type",
        )
        if outcome["factor_ack_percent"] is not None:
            p.require(
                1 <= r.number(outcome["factor_ack_percent"]) <= 150, "Invalid factor readback"
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
                and outcome["frequency_ack_Hz"] is None
                and outcome["factor_ack_percent"] is None
                and not outcome["source_on_ack"]
                and not outcome["source_off_ack"]
            ),
            "Progression after failed point",
        )
        if outcome["source_on_ack"]:
            p.require(
                outcome["frequency_ack_Hz"] == point["frequency_Hz"]
                and outcome["factor_ack_percent"] is not None
                and D(outcome["factor_ack_percent"])
                == D(
                    point["sensor_factor_percent"]
                    if point["factor_applied_in"] == "meter"
                    else "100"
                )
                and 21 <= len(group) <= 50,
                "Missing frequency acknowledgement/samples",
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
                outcome["status"] != "skipped"
                or (not group and outcome["frequency_ack_Hz"] is None),
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
        elif op == "frequency_ack_Hz":
            p.require(state is False, "Frequency changed while source not known off")
            selected = pid
        elif op == "meter_factor_ack":
            p.require(
                state is False and selected == pid, "Factor changed while source not known off"
            )
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

        if outcome["status"] != "skipped":
            append(
                "frequency_ack_Hz",
                frequency_Hz=outcome["frequency_ack_Hz"],
                power_setting=capture["plan"]["power_setting"],
                signal_mode=capture["plan"]["signal_mode"],
            )
        if outcome["factor_ack_percent"] is not None:
            append("meter_factor_ack", percent=outcome["factor_ack_percent"])
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


def correct_sensor(value, point):
    """Convert unity-factor indications once; already corrected readings pass through."""
    if value is None or point["sensor_factor_percent"] is None:
        return None
    return (
        value * 100 / D(point["sensor_factor_percent"])
        if point["factor_applied_in"] == "analysis"
        else value
    )


def analyze(capture, rows):
    """Correct saved indicated watts once, at exact supplied frequency points."""
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
            indicated = sum(values) / len(values) if values else None
            cf = point["sensor_factor_percent"]
            sensor = correct_sensor(indicated, point)
            dut = (
                sensor * factor(point["fixture_loss_dB"])
                if sensor is not None and point["fixture_loss_dB"] is not None
                else None
            )
            measured = dut if capture["plan"]["measurement_plane"] == "DUT_output" else sensor
            target = None if point["target_W"] is None else D(point["target_W"])
            error = measured - target if measured is not None and target is not None else None
            percent = 100 * error / target if error is not None else None
            db = 10 * (measured / target).log10() if error is not None and measured > 0 else None
            gaps = [
                D(b["elapsed_s"]) - D(a["elapsed_s"])
                for a, b in zip(samples, samples[1:], strict=False)
            ]
            gap = max(gaps) if gaps else None
            reason = (
                "Incomplete point"
                if outcome["status"] != "completed"
                else "Sensor factor unavailable"
                if sensor is None
                else "Fixture loss unavailable at DUT plane"
                if measured is None
                else "Nonpositive power or mean outside nominal sensor range"
                if measured <= 0 or not D(".000001") <= sensor <= D(".1")
                else None
            )
            if (
                criteria is not None
                and reason is None
                and (
                    len(values) < criteria["min_samples_per_point"]
                    or gap is None
                    or gap > D(criteria["max_gap_s"])
                )
            ):
                reason = "Insufficient sample/timing coverage"
            coverage_reason = reason
            acceptance = "NOT EVALUATED"
            if criteria is not None and "max_abs_error_percent" in criteria and reason is None:
                if target is None:
                    reason = "Target not supplied"
                else:
                    limit = D(
                        criteria.get("point_limits_percent", {}).get(
                            point["point_id"], criteria["max_abs_error_percent"]
                        )
                    )
                    acceptance = "PASS" if abs(percent) <= limit else "FAIL"
            elif reason is None:
                reason = (
                    "Target not supplied"
                    if target is None
                    else "No per-point error criterion supplied"
                )
            result = dict(
                point_id=point["point_id"],
                frequency_Hz=point["frequency_Hz"],
                frequency_ack_Hz=outcome["frequency_ack_Hz"],
                status=outcome["status"],
                valid_samples=len(values),
                indicated_mean_W=indicated,
                sensor_mean_W=sensor,
                DUT_mean_W=dut,
                measured_W=measured,
                target_W=target,
                error_W=error,
                error_percent=percent,
                error_dB=db,
                sensor_factor_percent=cf,
                factor_applied_in=point["factor_applied_in"],
                meter_factor_ack_percent=outcome["factor_ack_percent"],
                fixture_loss_dB=point["fixture_loss_dB"],
                indicated_min_W=min(values) if values else None,
                indicated_max_W=max(values) if values else None,
                sensor_min_W=correct_sensor(min(values), point)
                if values and cf is not None
                else None,
                sensor_max_W=correct_sensor(max(values), point)
                if values and cf is not None
                else None,
                DUT_min_W=correct_sensor(min(values), point) * factor(point["fixture_loss_dB"])
                if values and cf is not None and point["fixture_loss_dB"] is not None
                else None,
                DUT_max_W=correct_sensor(max(values), point) * factor(point["fixture_loss_dB"])
                if values and cf is not None and point["fixture_loss_dB"] is not None
                else None,
                max_gap_s=gap,
                coverage_eligible=coverage_reason is None,
                coverage_reason=coverage_reason,
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
        observed = [row for row in results if row["coverage_eligible"]]
        measured = [D(row["measured_W"]) for row in observed]
        duties = [
            D(row["DUT_mean_W"])
            for row in observed
            if row["DUT_mean_W"] is not None and D(row["DUT_mean_W"]) > 0
        ]
        spread = 10 * (max(measured) / min(measured)).log10() if len(measured) >= 2 else None
        dut_spread = 10 * (max(duties) / min(duties)).log10() if len(duties) >= 2 else None
        full = capture["status"] == "completed" and len(observed) == len(results)
        spread_acceptance = "NOT EVALUATED"
        if criteria is not None and "max_spread_dB" in criteria and full and spread is not None:
            spread_acceptance = "PASS" if spread <= D(criteria["max_spread_dB"]) else "FAIL"
        decisions = []
        if criteria is not None:
            if "max_abs_error_percent" in criteria:
                decisions.extend(row["acceptance"] for row in results)
            if "max_spread_dB" in criteria:
                decisions.append(spread_acceptance)
        overall = "NOT EVALUATED"
        if full and decisions and all(value in ("PASS", "FAIL") for value in decisions):
            overall = "FAIL" if "FAIL" in decisions else "PASS"
        worst = max(
            (
                row
                for row in results
                if row["status"] == "completed" and row["error_percent"] is not None
            ),
            key=lambda row: abs(D(row["error_percent"])),
            default=None,
        )
    baseline = [D(row["value_W"]) for row in rows if row["stage"] == "baseline-before"]
    return dict(
        schema="hp437b.frequency-sweep-results.v1",
        workflow_id=WORKFLOW,
        run_id=capture["run_id"],
        mode="synthetic",
        execution=capture["status"],
        measurement_plane=capture["plan"]["measurement_plane"],
        points=results,
        completed_points=sum(row["status"] == "completed" for row in results),
        requested_points=len(results),
        eligible_points=len(observed),
        full_coverage=full,
        zero_mean_W=str(sum(baseline) / len(baseline)) if baseline else None,
        zero_samples=len(baseline),
        observed_min_W=str(min(measured)) if measured else None,
        observed_max_W=str(max(measured)) if measured else None,
        observed_spread_dB=str(spread) if spread is not None else None,
        observed_DUT_min_W=str(min(duties)) if duties else None,
        observed_DUT_max_W=str(max(duties)) if duties else None,
        observed_DUT_spread_dB=str(dut_spread) if dut_spread is not None else None,
        DUT_eligible_points=len(duties),
        DUT_spread_scope="all requested points"
        if full and len(duties) == len(results)
        else "available eligible DUT points only; incomplete coverage",
        DUT_spread_unavailable_reason="At least two completed, positive, eligible DUT points required"
        if dut_spread is None
        else None,
        spread_scope="all requested points"
        if full
        else "available eligible points only; incomplete coverage",
        spread_unavailable_reason="At least two completed, positive, eligible points required"
        if spread is None
        else None,
        spread_acceptance=spread_acceptance,
        worst_error_point_id=worst["point_id"] if worst else None,
        worst_abs_error_percent=str(abs(D(worst["error_percent"]))) if worst else None,
        acceptance=overall,
        criteria=criteria,
    )


def _fixture_provenance(capture, bundle):
    def fact(value, pointer):
        return p.fact(
            value, basis="supplied", refs=[{"evidence_id": "workflow.json", "pointer": pointer}]
        )

    ids = ["synthetic:wf05:" + role for role in ("transmitter", "meter", "sensor", "fixture")]
    devices = [
        p.equipment(
            identity, role, {"identity": p.fact(note="Fictional equipment; no physical identity")}
        )
        for identity, role in zip(ids, ("source", "meter", "sensor", "fixture"), strict=True)
    ]
    subject = p.dut(
        "synthetic:wf05:dut",
        "external_device",
        ids,
        {
            "name": fact(capture["plan"]["name"], "/plan/name"),
            "power_setting": fact(capture["plan"]["power_setting"], "/plan/power_setting"),
            "signal_mode": fact(capture["plan"]["signal_mode"], "/plan/signal_mode"),
            "frequency_correction_plan": fact(capture["plan"]["points"], "/plan/points"),
            "fixture_description": fact(
                capture["plan"]["fixture_description"], "/plan/fixture_description"
            ),
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
            "measurement_plane": fact(
                capture["plan"]["measurement_plane"], "/plan/measurement_plane"
            ),
            "criteria": fact(capture["criteria"], "/criteria")
            if capture["criteria"] is not None
            else p.fact(note="Acceptance criteria not supplied"),
        },
        subject,
        devices,
        list(bundle.entries.values()),
    )


def provenance(capture, bundle):
    result = _fixture_provenance(capture, bundle)
    if capture.get("backend") == "dut-ctrl01-fake":
        from .controlled_sweep import augment_provenance

        return augment_provenance(capture, bundle, result)
    return result


def controlled(output, **kwargs):
    """Capture ordered points with shared fake DUT controls and the existing logger."""
    from .controlled_sweep import run

    return run("WF-05", output, **kwargs)


def publish(source, output, *, plots=True, pdf=False, package=False):
    from . import pdf_reports, report_delivery

    pdf = pdf or package
    source, output = preflight(source, output, plots=plots)
    report_delivery.preflight_delivery(source, output, pdf=pdf, package=package)
    capture, rows, bundle = load(source)
    result = analyze(capture, rows)
    record = provenance(capture, bundle)
    p.verify(record, source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        producer = report_identity.identify()
        for name, obj in (
            ("results.json", result),
            ("provenance.json", record),
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
            for key, marker, label in (
                ("target_W", "o", "Target"),
                ("measured_W", "x", "Measured"),
            ):
                selected = [
                    row
                    for row in result["points"]
                    if row[key] is not None and (key == "target_W" or row["status"] == "completed")
                ]
                axis.scatter(
                    [row["frequency_Hz"] / 1e6 for row in selected],
                    [float(row[key]) for row in selected],
                    marker=marker,
                    label=label,
                )
            axis.set_xlabel("Declared frequency (MHz); repeated points retained")
            axis.set_ylabel("Power (W)")
            axis.set_title(result["measurement_plane"].replace("_", " ") + " plane")
            axis.grid(axis="y", alpha=0.2)
            fig.legend(
                *axis.get_legend_handles_labels(), loc="outside upper right", ncols=2, frameon=False
            )
            for extension in ("png", "svg"):
                fig.savefig(output / ("frequency-sweep." + extension), dpi=150)
            plt.close(fig)
        sheet, markdown = render(capture, result, producer, plots=plots)
        (output / "report.html").write_text(sheet, encoding="utf-8")
        (output / "report.md").write_text(markdown, encoding="utf-8")
        appendix = dict(
            capture=capture,
            results=result,
            provenance=record,
            limitations=[
                "Synthetic only; no hardware/backend qualification",
                "Exact supplied point corrections only; no interpolation",
                "No uncertainty, frequency-accuracy, spectral-purity, or all-band extrapolation claim",
                "POWER REF is fixed; physical transmitter tuning/control remains DUT-CTRL-01",
            ],
        )
        (output / "appendix.html").write_text(
            '<!doctype html><meta charset="utf-8"><title>WF-05 evidence</title><h1>Technical appendix</h1><pre>'
            + html.escape(r.encoded(appendix).decode())
            + "</pre>",
            encoding="utf-8",
        )
        from .controlled_sweep import annotate_report

        annotate_report(output, capture)
        if pdf:
            pdf_reports.workflow(output, capture, result, producer, "WF-05")
        p.verify(record, source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
            "Capture changed during publication",
        )
        _seal(
            output,
            {
                "schema": "hp437b.frequency-sweep-report.v1",
                "mode": "synthetic",
                "run_id": capture["run_id"],
            },
        )
    except BaseException as exc:
        (output / "failure.json").write_bytes(r.encoded({"status": "failed", "error": str(exc)}))
        raise
    if package:
        report_delivery.package(source, output)
    return result


def render(capture, result, producer, *, plots):
    def fmt(value):
        return "—" if value is None else "0" if D(value) == 0 else report_sheet._n(value)

    def e(value):
        return html.escape(str(value))

    meta = [
        ("Transmitter", capture["plan"]["name"]),
        ("Test", "Output power versus frequency"),
        ("Operator", capture["operator"] or "Not recorded"),
        (
            "When",
            r.timestamp(capture["started_utc"]).astimezone(UTC).strftime("%d %b %Y, %H:%M:%S UTC"),
        ),
        ("Power setting", capture["plan"]["power_setting"]),
        ("Signal", capture["plan"]["signal_mode"]),
        ("Measurement plane", result["measurement_plane"].replace("_", " ")),
    ]
    table = []
    for row in result["points"]:
        table.append(
            [
                row["point_id"] + " · " + fmt(D(row["frequency_Hz"]) / 1000000),
                (
                    fmt(row["sensor_factor_percent"])
                    + (" A" if row["factor_applied_in"] == "analysis" else " M")
                )
                if row["sensor_factor_percent"] is not None
                else "—",
                fmt(row["fixture_loss_dB"]),
                fmt(row["target_W"]),
                fmt(row["measured_W"]),
                fmt(row["error_percent"]),
                str(row["valid_samples"]) + "/30",
                row["status"],
            ]
        )
    headings = [
        "Point / MHz",
        "CF %",
        "Loss dB",
        "Target W",
        "Measured W",
        "Error %",
        "Valid",
        "State",
    ]
    limits = "Acceptance limits not supplied."
    if capture["criteria"] is not None:
        criteria = capture["criteria"]
        selected = []
        if "max_abs_error_percent" in criteria:
            selected.append("|error| ≤ " + fmt(criteria["max_abs_error_percent"]) + "%")
        if "max_spread_dB" in criteria:
            selected.append("spread ≤ " + fmt(criteria["max_spread_dB"]) + " dB")
        limits = (
            "Criteria: "
            + "; ".join(selected)
            + ". "
            + report_sheet._short(criteria["source"], 100)
            + "; inclusive, no guard band."
        )
        if criteria.get("point_limits_percent"):
            limits += " Point-specific overrides: see appendix."
    final = (
        "off acknowledged (synthetic)"
        if capture["final_state"]["external_source_off"]
        else "ON (synthetic); source-off readback failed"
        if capture["final_state"].get("rf_state") == "on"
        else "UNKNOWN (synthetic); recovery not asserted"
    )
    summary = f"Execution: {result['execution']}; {result['completed_points']}/{result['requested_points']} points complete. Acceptance: {result['acceptance']}."
    zero = f"Pre-RF zero: {fmt(D(result['zero_mean_W']) * 1000000 if result['zero_mean_W'] is not None else None)} µW ({result['zero_samples']} source-off samples; no subtraction)."
    spread = f"Observed spread: {fmt(result['observed_spread_dB'])} dB ({result['eligible_points']}/{result['requested_points']} eligible points)."
    worst = (
        "Worst observed target error: "
        + fmt(result["worst_abs_error_percent"])
        + "%"
        + (" at " + result["worst_error_point_id"] if result["worst_error_point_id"] else "")
        + "."
    )
    notes = "CF: A = analysis, M = meter. Frequency is declared and synthetically acknowledged, not independently measured. CF is applied once: in analysis from unity-factor indications, or already in the meter with matching readback. Supplied fixture loss is then applied once for DUT output; no interpolation. Partial or missing points cannot establish complete coverage."
    footer = [
        "Equipment: fictional transmitter, HP 437B, 8482A, and fixture.",
        report_sheet.producer_note(producer),
        "Record: " + capture["run_id"],
    ]
    headers = "".join("<th>" + e(cell) + "</th>" for cell in headings)
    body = "".join(
        "<tr>" + "".join("<td>" + e(cell) + "</td>" for cell in row) + "</tr>" for row in table
    )
    metadata = "<br>".join("<strong>" + e(key) + ":</strong> " + e(value) for key, value in meta)
    sheet = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>RF Output Power Test</title>
<style>{report_sheet.STYLE}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:5px 3px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}}img{{width:100%;max-height:44mm;object-fit:contain}}footer{{break-inside:avoid}}p{{margin:7px 0}}@media print{{body{{font-size:10pt}}td,th{{font-size:8.5pt;padding:4px 2px}}h1{{margin-bottom:8px}}}}</style><body><main class="sheet">
<h1>RF Output Power Test</h1><p><strong>SYNTHETIC - fictional transmitter and measurements; no physical RF</strong></p><p>{metadata}</p>
<p><strong>{e(summary)}</strong><br>Final external source: {e(final)}.</p><p>{e(zero)}</p><p><strong>{e(spread)}</strong> {e(worst)}</p>
<table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>
{'<img src="frequency-sweep.svg" alt="Target and measured power at declared frequency points">' if plots else ""}
<p>{e(limits)}</p><p>{e(notes)}</p><p>Unavailable values are shown as —. Per-point factors, their application location/readback, sources, full ranges, reasons, and decision details are retained in appendix.html.</p>
<footer>{"".join("<p>" + e(line) + "</p>" for line in footer)}<p>Evidence and limitations: appendix.html; results.json; provenance.json.</p></footer></main></body></html>"""
    md = "# RF Output Power Test\n\nSYNTHETIC - fictional transmitter and measurements.\n\n"
    md += (
        "\n\n".join(report_sheet._markdown(key + ": " + str(value)) for key, value in meta) + "\n\n"
    )
    md += (
        "\n\n".join(
            report_sheet._markdown(value)
            for value in (summary, "Final external source: " + final, zero, spread, worst)
        )
        + "\n\n"
    )
    md += "| " + " | ".join(headings) + " |\n| " + " | ".join("---" for _ in headings) + " |\n"
    md += (
        "\n".join(
            "| " + " | ".join(report_sheet._markdown(cell) for cell in row) + " |" for row in table
        )
        + "\n\n"
    )
    md += (
        "\n\n".join(report_sheet._markdown(line) for line in (limits, notes, *footer))
        + "\n\nFull evidence: appendix.html.\n"
    )
    return sheet, md


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("synthetic")
    run.add_argument("--scenario", choices=SCENARIOS, default="nominal")
    run.add_argument("--plan", type=Path)
    run.add_argument("--criteria", type=Path)
    run.add_argument("--operator")
    run.add_argument("--report-output", type=Path)
    controlled_run = commands.add_parser(
        "controlled", help="Shared fake DUT-CTRL-01 capture-to-report"
    )
    controlled_run.add_argument("--scenario", choices=SCENARIOS, default="nominal")
    controlled_run.add_argument("--plan", type=Path)
    controlled_run.add_argument("--criteria", type=Path)
    controlled_run.add_argument("--operator")
    controlled_run.add_argument("--report-output", type=Path)
    from .controlled_sweep import FAULTS

    controlled_run.add_argument("--fault", choices=FAULTS)
    controlled_run.add_argument("--fault-point")
    controlled_run.add_argument("--stop-before")
    report = commands.add_parser("report")
    report.add_argument("--bundle", required=True, type=Path)
    for sub in (run, controlled_run, report):
        sub.add_argument("--output", required=True, type=Path)
        sub.add_argument("--no-plots", action="store_true")
        sub.add_argument("--pdf", action="store_true")
        sub.add_argument("--package", action="store_true", help="PDFs and a sibling portable ZIP")
    args = parser.parse_args(argv)
    try:
        if args.command in ("synthetic", "controlled"):
            runner = controlled if args.command == "controlled" else simulate
            capture = runner(
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
                pdf=args.pdf,
                package=args.package,
                **(
                    dict(
                        fault=args.fault, fault_point=args.fault_point, stop_before=args.stop_before
                    )
                    if args.command == "controlled"
                    else {}
                ),
            )
            if args.pdf or args.package:
                from .report_delivery import announce

                announce(args.report_output, pdf=args.pdf, package=args.package)
            return 0 if capture["status"] == "completed" else 1
        publish(
            args.bundle, args.output, plots=not args.no_plots, pdf=args.pdf, package=args.package
        )
        if args.pdf or args.package:
            from .report_delivery import announce

            announce(args.output, pdf=args.pdf, package=args.package)
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        print(f"WF-05: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
