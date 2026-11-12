"""WF-06 synthetic supply-voltage sensitivity and offline deterministic reports.

No supply driver, transmitter control, instrument connection, or DC efficiency
measurement is implemented. All acknowledgements and samples are virtual.
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
from .power_setting import COLUMNS, PROFILE, factor, text
from .workflow_report import _seal, preflight

WORKFLOW = "supply-voltage-sensitivity-v1"
SCHEMA = "hp437b.supply-sensitivity-capture.v1"
SCENARIOS = (
    "nominal",
    "droop",
    "observed-offset",
    "repeated-anchor",
    "missing-nominal",
    "missing-readback",
    "unsafe-readback",
    "same-voltage",
    "missing-loss",
    "sensor-plane",
    "zero-nominal",
    "timeout",
    "malformed",
    "instrument-error",
    "cancel",
    "missing-point",
    "source-off-failure",
    "supply-control-failure",
    "current-limit-mismatch",
    "restore-failure",
    "restore-mismatch",
    "restore-unverified",
)


def validate_plan(plan):
    p._keys(
        plan,
        (
            "schema",
            "name",
            "frequency_Hz",
            "power_setting",
            "signal_mode",
            "measurement_plane",
            "fixture_description",
            "fixture_loss_dB",
            "fixture_source",
            "simulation_loss_dB",
            "supply",
            "points",
        ),
    )
    p.require(plan["schema"] == "hp437b.supply-sensitivity-plan.v1", "Unsupported plan")
    for key in ("name", "power_setting", "signal_mode"):
        text(plan[key], 120 if key == "name" else 60)
    text(plan["fixture_description"], 240)
    p.require(
        type(plan["frequency_Hz"]) is int and 100000 <= plan["frequency_Hz"] <= 4200000000,
        "Invalid declared fixed frequency",
    )
    p.require(
        plan["measurement_plane"] in ("DUT_output", "sensor_input"), "Invalid measurement plane"
    )
    for key in ("fixture_loss_dB", "simulation_loss_dB"):
        if key == "simulation_loss_dB" or plan[key] is not None:
            p.require(0 <= r.number(plan[key]) <= 100, "Invalid fixture loss")
    if plan["fixture_loss_dB"] is None:
        p.require(plan["fixture_source"] is None, "Unknown loss must retain unknown source")
    else:
        text(plan["fixture_source"], 240)
    supply = plan["supply"]
    p._keys(
        supply,
        (
            "minimum_V",
            "maximum_V",
            "current_limit_A",
            "restore_V",
            "nominal_V",
            "nominal_point_id",
            "tolerance_V",
            "observation_location",
        ),
    )
    low, high = r.number(supply["minimum_V"]), r.number(supply["maximum_V"])
    p.require(D(".1") <= low <= high <= 100, "Invalid declared supply envelope")
    p.require(
        D(".01") <= r.number(supply["current_limit_A"]) <= 100, "Invalid declared current limit"
    )
    p.require(0 <= r.number(supply["tolerance_V"]) <= 1, "Invalid voltage tolerance")
    for key in ("restore_V", "nominal_V"):
        p.require(
            low <= r.number(supply[key]) <= high, "Nominal/restoration voltage outside envelope"
        )
    text(supply["observation_location"], 120)
    p.require(
        isinstance(plan["points"], list) and 1 <= len(plan["points"]) <= 5, "Request 1–5 points"
    )
    for i, point in enumerate(plan["points"], 1):
        p._keys(point, ("point_id", "requested_V", "synthetic_observed_V", "synthetic_DUT_W"))
        p.require(point["point_id"] == f"P{i:02d}", "Point IDs must retain requested order")
        p.require(
            low <= r.number(point["requested_V"]) <= high,
            "Requested voltage outside declared envelope",
        )
        if point["synthetic_observed_V"] is not None:
            p.require(
                0 <= r.number(point["synthetic_observed_V"]) <= 1000, "Invalid synthetic readback"
            )
        truth = r.number(point["synthetic_DUT_W"])
        p.require(truth == 0 or D("1e-20") <= truth <= 10000, "Invalid synthetic source power")
        sensor = truth / factor(plan["simulation_loss_dB"])
        p.require(
            sensor == 0 or D("1e-30") <= sensor <= D(".1"), "Synthetic sensor input outside profile"
        )
    nominal = supply["nominal_point_id"]
    p.require(
        nominal is None or nominal in [point["point_id"] for point in plan["points"]],
        "Unknown nominal point",
    )
    if nominal is not None:
        point = next(point for point in plan["points"] if point["point_id"] == nominal)
        p.require(
            D(point["requested_V"]) == D(supply["nominal_V"]),
            "Nominal point request differs from nominal voltage",
        )
    return plan


def validate_criteria(criteria, plan=None):
    if criteria is None:
        return
    required = {"source", "decision_rule", "min_samples_per_point", "max_gap_s"}
    optional = {"max_abs_change_percent", "point_limits_percent", "max_abs_secant_W_per_V"}
    p.require(
        isinstance(criteria, dict) and required <= set(criteria) <= required | optional,
        "Unsupported criteria",
    )
    p.require(
        "max_abs_change_percent" in criteria or "max_abs_secant_W_per_V" in criteria,
        "Supply a change or secant limit",
    )
    text(criteria["source"], 240)
    p.require(criteria["decision_rule"] == "inclusive-no-guard-band", "Unsupported decision rule")
    for key in ("max_abs_change_percent", "max_abs_secant_W_per_V"):
        if key in criteria:
            p.require(r.number(criteria[key]) >= 0, "Negative criterion limit")
    overrides = criteria.get("point_limits_percent", {})
    p.require(
        isinstance(overrides, dict)
        and len(overrides) <= 5
        and (not overrides or "max_abs_change_percent" in criteria),
        "Invalid point limits",
    )
    ids = (
        {point["point_id"] for point in plan["points"]}
        if plan
        else {f"P{i:02d}" for i in range(1, 6)}
    )
    p.require(set(overrides) <= ids, "Limit references an unrequested point")
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
    points = [
        dict(
            point_id=f"P{i:02d}",
            requested_V=str(voltage),
            synthetic_observed_V=str(voltage),
            synthetic_DUT_W="5",
        )
        for i, voltage in enumerate((11, 12, 13), 1)
    ]
    if scenario in ("droop", "observed-offset", "repeated-anchor", "sensor-plane"):
        for point, power in zip(points, ("4.5", "5", "5.2"), strict=True):
            point["synthetic_DUT_W"] = power
    if scenario == "observed-offset":
        for point, voltage in zip(points, ("10.98", "12.02", "13.01"), strict=True):
            point["synthetic_observed_V"] = voltage
    if scenario == "repeated-anchor":
        points += [
            dict(
                point_id="P04", requested_V="12", synthetic_observed_V="12", synthetic_DUT_W="4.9"
            ),
            dict(
                point_id="P05", requested_V="11", synthetic_observed_V="11", synthetic_DUT_W="4.4"
            ),
        ]
    if scenario == "same-voltage":
        for point in points:
            point["requested_V"] = point["synthetic_observed_V"] = "12"
    if scenario == "missing-readback":
        points[1]["synthetic_observed_V"] = None
    if scenario == "unsafe-readback":
        points[1]["synthetic_observed_V"] = "15"
    if scenario == "zero-nominal":
        points[1]["synthetic_DUT_W"] = "0"
    return validate_plan(
        dict(
            schema="hp437b.supply-sensitivity-plan.v1",
            name="Fictional transmitter",
            frequency_Hz=14000000,
            power_setting="Nominal output (fixed)",
            signal_mode="Continuous carrier (synthetic)",
            measurement_plane="sensor_input" if scenario == "sensor-plane" else "DUT_output",
            fixture_description="Fictional fixed fixture; no physical RF",
            fixture_loss_dB=None if scenario == "missing-loss" else "30",
            fixture_source=None
            if scenario == "missing-loss"
            else "Fictional fixture table r1; fixed frequency",
            simulation_loss_dB="30",
            supply=dict(
                minimum_V="10",
                maximum_V="14",
                current_limit_A="2",
                restore_V="12",
                nominal_V="12",
                nominal_point_id=None if scenario == "missing-nominal" else "P02",
                tolerance_V="0.1",
                observation_location="DUT supply terminals (synthetic)",
            ),
            points=points,
        )
    )


def voltage_ok(observed, requested, supply):
    return (
        observed is not None
        and D(supply["minimum_V"]) <= D(observed) <= D(supply["maximum_V"])
        and abs(D(observed) - D(requested)) <= D(supply["tolerance_V"])
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
        setup=None,
        restoration=None,
        points=[],
        final_state=None,
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "starting.json").write_bytes(r.encoded(capture))
    rows, events, elapsed = [], [], 0
    supply = plan["supply"]
    source, healthy = False, True

    def event(operation, point_id=None, **fields):
        events.append(dict(elapsed_s=elapsed, operation=operation, point_id=point_id, **fields))

    def sample(stage, pid, value, status="ok"):
        nonlocal elapsed
        rows.append(
            dict(
                run_id=run_id,
                point_id=pid,
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
        sample("baseline-before", "", D("-2e-8"))
    current = (
        str(D(supply["current_limit_A"]) / 2)
        if scenario == "current-limit-mismatch"
        else supply["current_limit_A"]
    )
    setup_ok = D(current) == D(supply["current_limit_A"])
    capture["setup"] = dict(
        status="verified" if setup_ok else "failed",
        current_limit_ack_A=current,
        reason="" if setup_ok else "Synthetic current-limit readback mismatch",
    )
    event("current_limit_ack", amperes=current)
    capture["status"] = "completed" if setup_ok else "failed"
    healthy = setup_ok
    for i, point in enumerate(plan["points"]):
        pid = point["point_id"]
        result = dict(
            point_id=pid,
            status="skipped",
            voltage_command_ack=False,
            observed_V=None,
            source_on_ack=False,
            source_off_ack=False,
            communication_uncertain=False,
            reason="Not reached",
        )
        capture["points"].append(result)
        if capture["status"] != "completed":
            continue
        if i == 1 and scenario == "missing-point":
            capture["status"] = "interrupted"
            result["reason"] = "Synthetic stop before point"
            continue
        p.require(
            source is False and healthy,
            "Voltage changes require known source off and healthy control",
        )
        if i == 1 and scenario == "supply-control-failure":
            event("voltage_command_failed", pid, requested_V=point["requested_V"])
            result.update(status="failed", reason="Synthetic supply write failure; no retry")
            capture["status"], healthy = "failed", False
            continue
        result["voltage_command_ack"] = True
        event("voltage_command_ack", pid, requested_V=point["requested_V"])
        result["observed_V"] = point["synthetic_observed_V"]
        event("voltage_readback", pid, observed_V=result["observed_V"])
        if not voltage_ok(result["observed_V"], point["requested_V"], supply):
            result.update(
                status="failed", reason="Missing, out-of-envelope, or mismatched voltage readback"
            )
            capture["status"] = "failed"
            continue
        source = True
        result["source_on_ack"] = True
        event("source_on_ack", pid, acknowledged=True)
        value = D(format(D(point["synthetic_DUT_W"]) / factor(plan["simulation_loss_dB"]), ".4E"))
        for _ in range(20):
            sample("settling", pid, value)
        result.update(status="completed", reason="")
        for j in range(30):
            if (
                i == 1
                and j == 3
                and scenario in ("timeout", "malformed", "instrument-error", "cancel")
            ):
                status = "interrupted" if scenario == "cancel" else "failed"
                sample("plateau", pid, value, status)
                result.update(
                    status=status, reason=f"Synthetic {scenario}; not a native backend fault"
                )
                capture["status"] = status
                if scenario in ("timeout", "malformed"):
                    source, healthy = None, False
                    result["communication_uncertain"] = True
                    event("communication_uncertain", pid)
                break
            sample("plateau", pid, value)
        if source is not None:
            event("source_off_attempt", pid)
            if i == 1 and scenario == "source-off-failure":
                source, healthy = None, False
                result.update(status="failed", reason="Synthetic source-off failure; no retry")
                capture["status"] = "failed"
            else:
                source = False
                result["source_off_ack"] = True
                event("source_off_ack", pid, acknowledged=True)
    restore = dict(
        status="unknown",
        attempted=False,
        command_ack=False,
        requested_V=supply["restore_V"],
        observed_V=None,
        reason="Control/source state uncertain; no restoration commands",
    )
    if healthy and source is False:
        restore["attempted"] = True
        event("restore_attempt", requested_V=supply["restore_V"])
        if scenario == "restore-failure":
            restore.update(status="failed", reason="Synthetic restoration write failure; no retry")
            event("restore_failed")
        else:
            restore["command_ack"] = True
            observed = (
                None
                if scenario == "restore-unverified"
                else str(D(supply["restore_V"]) - D(".5"))
                if scenario == "restore-mismatch"
                else supply["restore_V"]
            )
            restore["observed_V"] = observed
            event("restore_readback", observed_V=observed)
            ok = voltage_ok(observed, supply["restore_V"], supply)
            restore.update(
                status="verified" if ok else "failed",
                reason="" if ok else "Missing/mismatched restoration readback; no retry",
            )
        if restore["status"] != "verified":
            capture["status"] = "failed"
    capture["restoration"] = restore
    if capture["status"] == "completed":
        for _ in range(3):
            sample("baseline-after", "", D("-2e-8"))
    capture["finished_utc"] = (start + timedelta(seconds=elapsed)).isoformat()
    capture["final_state"] = dict(
        external_source_off=True if source is False else None,
        supply_restored=True if restore["status"] == "verified" else None,
        meter_reference_off=True,
        hardware_opened=False,
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    (output / "samples.csv").write_text(stream.getvalue(), encoding="utf-8", newline="")
    (output / "workflow.json").write_bytes(r.encoded(capture))
    (output / "trace.json").write_bytes(r.encoded(events))
    _seal(
        output,
        dict(schema="hp437b.supply-sensitivity-inventory.v1", mode="synthetic", run_id=run_id),
    )
    if report_output is not None:
        publish(output, report_output, plots=plots)
    return capture


def load(source):
    """Verify saved sample joins and replay only the recorded virtual state machine."""
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
            "setup",
            "restoration",
            "points",
            "final_state",
        ),
    )
    p.require(
        capture["schema"] == SCHEMA
        and capture["workflow_id"] == WORKFLOW
        and capture["mode"] == "synthetic"
        and capture["simulation"] is True,
        "Unsupported capture/mode",
    )
    uuid.UUID(capture["run_id"])
    p.require(
        inventory.get("schema") == "hp437b.supply-sensitivity-inventory.v1"
        and inventory.get("run_id") == capture["run_id"],
        "Inventory/run mismatch",
    )
    p.require(
        bundle.json("starting.json")
        == {
            **capture,
            "status": "running",
            "finished_utc": None,
            "setup": None,
            "restoration": None,
            "points": [],
            "final_state": None,
        },
        "Starting/final metadata mismatch",
    )
    validate_plan(capture["plan"])
    validate_criteria(capture["criteria"], capture["plan"])
    report_context.validate_operator(capture["operator"])
    p.require(
        capture["profile"] == PROFILE and capture["scenario"] in SCENARIOS,
        "Unsupported profile/scenario",
    )
    p.require(capture["status"] in ("completed", "failed", "interrupted"), "Unfinalized capture")
    span = (
        r.timestamp(capture["finished_utc"]) - r.timestamp(capture["started_utc"])
    ).total_seconds()
    p.require(0 <= span <= PROFILE["whole_run_ceiling_s"], "Invalid virtual duration")
    reader = csv.DictReader(io.StringIO(bundle.read("samples.csv").decode("utf-8")))
    p.require(reader.fieldnames == list(COLUMNS), "Invalid sample columns/units")
    rows = list(reader)
    p.require(3 <= len(rows) <= 256 and span == len(rows), "Invalid sample count/duration")
    for index, row in enumerate(rows):
        p.require(None not in row and None not in row.values(), "Malformed CSV row")
        p.require(
            row["run_id"] == capture["run_id"]
            and row["sequence"] == str(index + 1)
            and row["elapsed_s"] == str(index),
            "Sample/run/time join mismatch",
        )
        p.require(
            row["stage"] in ("baseline-before", "baseline-after", "settling", "plateau")
            and row["status"] in ("ok", "failed", "interrupted"),
            "Invalid sample phase/status",
        )
        if row["status"] == "ok":
            value = r.number(row["value_W"])
            p.require(value == 0 or D("1e-30") <= abs(value) <= D(".1"), "Invalid sensor watts")
        else:
            p.require(row["value_W"] == "", "Failed row contains a power value")
    p.require(
        all(
            row["stage"] == "baseline-before" and row["point_id"] == "" and row["status"] == "ok"
            for row in rows[:3]
        ),
        "Missing signed pre-RF zero",
    )
    plan, setup = capture["plan"], capture["setup"]
    supply = plan["supply"]
    p._keys(setup, ("status", "current_limit_ack_A", "reason"))
    current = r.number(setup["current_limit_ack_A"])
    p.require(0 < current <= 100, "Invalid current-limit acknowledgement")
    healthy = current == D(supply["current_limit_A"])
    p.require(
        setup["status"] == ("verified" if healthy else "failed"), "Current-limit status mismatch"
    )
    text(setup["reason"] or "Verified", 240)
    p.require(healthy or bool(setup["reason"]), "Missing setup failure reason")
    p.require(
        isinstance(capture["points"], list) and len(capture["points"]) == len(plan["points"]),
        "Missing requested points",
    )
    events = [
        dict(elapsed_s=0, operation="source_off_ack", point_id=None, acknowledged=True),
        dict(
            elapsed_s=3,
            operation="current_limit_ack",
            point_id=None,
            amperes=setup["current_limit_ack_A"],
        ),
    ]
    cursor, source_off, stopped = 3, True, not healthy

    def event(operation, pid=None, **fields):
        events.append(dict(elapsed_s=cursor, operation=operation, point_id=pid, **fields))

    for point, outcome in zip(plan["points"], capture["points"], strict=True):
        p._keys(
            outcome,
            (
                "point_id",
                "status",
                "voltage_command_ack",
                "observed_V",
                "source_on_ack",
                "source_off_ack",
                "communication_uncertain",
                "reason",
            ),
        )
        pid, status = point["point_id"], outcome["status"]
        p.require(
            outcome["point_id"] == pid
            and status in ("completed", "failed", "interrupted", "skipped"),
            "Invalid point join/status",
        )
        text(outcome["reason"] or "Completed", 240)
        p.require(status == "completed" or bool(outcome["reason"]), "Missing failure/skip reason")
        for key in (
            "voltage_command_ack",
            "source_on_ack",
            "source_off_ack",
            "communication_uncertain",
        ):
            p.require(type(outcome[key]) is bool, "Invalid acknowledgement type")
        if outcome["observed_V"] is not None:
            p.require(0 <= r.number(outcome["observed_V"]) <= 1000, "Invalid observed voltage")
        group = []
        while cursor < len(rows) and rows[cursor]["point_id"] == pid:
            group.append(rows[cursor])
            cursor += 1
        receipt_end = cursor
        cursor -= len(group)
        if stopped or status == "skipped":
            p.require(
                status == "skipped"
                and not group
                and outcome["observed_V"] is None
                and not any(
                    outcome[key]
                    for key in (
                        "voltage_command_ack",
                        "source_on_ack",
                        "source_off_ack",
                        "communication_uncertain",
                    )
                ),
                "Progression after failure/skipped point",
            )
        elif not outcome["voltage_command_ack"]:
            p.require(
                status == "failed"
                and not group
                and outcome["observed_V"] is None
                and not outcome["source_on_ack"]
                and not outcome["source_off_ack"]
                and not outcome["communication_uncertain"],
                "Invalid failed voltage command",
            )
            event("voltage_command_failed", pid, requested_V=point["requested_V"])
            healthy = False
        else:
            p.require(
                source_off is True and healthy,
                "Voltage changed without known source off/healthy control",
            )
            event("voltage_command_ack", pid, requested_V=point["requested_V"])
            event("voltage_readback", pid, observed_V=outcome["observed_V"])
            if not voltage_ok(outcome["observed_V"], point["requested_V"], supply):
                p.require(
                    status == "failed"
                    and not group
                    and not outcome["source_on_ack"]
                    and not outcome["source_off_ack"]
                    and not outcome["communication_uncertain"],
                    "RF captured without supported voltage",
                )
            else:
                p.require(
                    outcome["source_on_ack"] and 21 <= len(group) <= 50,
                    "Missing source acknowledgement/samples",
                )
                p.require(
                    all(row["stage"] == "settling" and row["status"] == "ok" for row in group[:20])
                    and all(row["stage"] == "plateau" for row in group[20:])
                    and all(row["status"] == "ok" for row in group[:-1]),
                    "Invalid point phases/post-failure samples",
                )
                event("source_on_ack", pid, acknowledged=True)
                cursor = receipt_end
                if outcome["communication_uncertain"]:
                    p.require(
                        status == "failed"
                        and group[-1]["status"] == "failed"
                        and not outcome["source_off_ack"],
                        "Invalid uncertainty state",
                    )
                    event("communication_uncertain", pid)
                    source_off, healthy = None, False
                else:
                    event("source_off_attempt", pid)
                    if outcome["source_off_ack"]:
                        event("source_off_ack", pid, acknowledged=True)
                        source_off = True
                    else:
                        p.require(status == "failed", "Incomplete source-off state")
                        source_off, healthy = None, False
                if status == "completed":
                    p.require(
                        len(group) == 50
                        and all(row["status"] == "ok" for row in group)
                        and outcome["source_off_ack"],
                        "Incomplete point marked completed",
                    )
                elif status == "interrupted":
                    p.require(group[-1]["status"] == "interrupted", "Missing interruption row")
                else:
                    p.require(
                        group[-1]["status"] == "failed" or not outcome["source_off_ack"],
                        "Missing failure evidence",
                    )
        cursor = receipt_end
        if status != "completed":
            stopped = True
    restore = capture["restoration"]
    p._keys(restore, ("status", "attempted", "command_ack", "requested_V", "observed_V", "reason"))
    p.require(
        type(restore["attempted"]) is bool
        and type(restore["command_ack"]) is bool
        and restore["requested_V"] == supply["restore_V"],
        "Invalid restoration target/flags",
    )
    if restore["observed_V"] is not None:
        p.require(0 <= r.number(restore["observed_V"]) <= 1000, "Invalid restoration readback")
    allowed = healthy and source_off is True
    p.require(
        restore["attempted"] is allowed,
        "Restoration attempted after uncertain control or omitted while healthy",
    )
    if allowed:
        event("restore_attempt", requested_V=supply["restore_V"])
        if restore["command_ack"]:
            event("restore_readback", observed_V=restore["observed_V"])
            restored = voltage_ok(restore["observed_V"], supply["restore_V"], supply)
        else:
            p.require(
                restore["observed_V"] is None,
                "Restoration readback without command acknowledgement",
            )
            event("restore_failed")
            restored = False
        p.require(
            restore["status"] == ("verified" if restored else "failed"),
            "Restoration status mismatch",
        )
    else:
        p.require(
            restore["status"] == "unknown"
            and not restore["command_ack"]
            and restore["observed_V"] is None,
            "Unknown restoration incorrectly asserted",
        )
        restored = False
    text(restore["reason"] or "Verified", 240)
    p.require(restored or bool(restore["reason"]), "Missing restoration limitation reason")
    failed = (
        setup["status"] == "failed"
        or any(point["status"] == "failed" for point in capture["points"])
        or restore["status"] == "failed"
    )
    incomplete = any(point["status"] != "completed" for point in capture["points"])
    expected_status = "failed" if failed else "interrupted" if incomplete else "completed"
    p.require(capture["status"] == expected_status, "Execution/point/restoration mismatch")
    tail = rows[cursor:]
    p.require(
        (
            expected_status == "completed"
            and len(tail) == 3
            and all(
                row["point_id"] == "" and row["stage"] == "baseline-after" and row["status"] == "ok"
                for row in tail
            )
        )
        or (expected_status != "completed" and not tail),
        "Invalid final baseline",
    )
    p._keys(
        capture["final_state"],
        ("external_source_off", "supply_restored", "meter_reference_off", "hardware_opened"),
    )
    final = capture["final_state"]
    p.require(
        final["meter_reference_off"] is True
        and final["hardware_opened"] is False
        and (final["external_source_off"] is None or final["external_source_off"] is True)
        and (final["supply_restored"] is None or final["supply_restored"] is True),
        "Invalid final-state types",
    )
    p.require(
        capture["final_state"]
        == dict(
            external_source_off=source_off,
            supply_restored=True if restored else None,
            meter_reference_off=True,
            hardware_opened=False,
        ),
        "Final source/supply state mismatch",
    )
    p.require(
        bundle.json("trace.json") == events,
        "Source/supply trace mismatch, retry, or post-fault command",
    )
    return capture, rows, bundle


def analyze(capture, rows):
    """Compare RF power with an explicit nominal point and observed endpoints."""
    plan, criteria = capture["plan"], capture["criteria"]
    results = []
    with localcontext() as ctx:
        ctx.prec = 34
        for point, outcome in zip(plan["points"], capture["points"], strict=True):
            samples = [
                row
                for row in rows
                if row["point_id"] == point["point_id"]
                and row["stage"] == "plateau"
                and row["status"] == "ok"
            ]
            values = [D(row["value_W"]) for row in samples]
            mean = sum(values) / len(values) if values else None
            loss = factor(plan["fixture_loss_dB"]) if plan["fixture_loss_dB"] is not None else None
            dut = mean * loss if mean is not None and loss is not None else None
            measured = dut if plan["measurement_plane"] == "DUT_output" else mean
            gaps = [
                D(b["elapsed_s"]) - D(a["elapsed_s"])
                for a, b in zip(samples, samples[1:], strict=False)
            ]
            gap = max(gaps) if gaps else None
            observed = outcome["observed_V"]
            reason = (
                "Incomplete point"
                if outcome["status"] != "completed"
                else "Observed voltage unavailable/unsupported"
                if not voltage_ok(observed, point["requested_V"], plan["supply"])
                else "Fixture loss or RF samples unavailable at comparison plane"
                if measured is None
                else "Nonpositive power or mean outside nominal sensor range"
                if measured <= 0 or not D(".000001") <= mean <= D(".1")
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
            result = dict(
                point_id=point["point_id"],
                requested_V=point["requested_V"],
                observed_V=observed,
                voltage_error_V=str(D(observed) - D(point["requested_V"]))
                if observed is not None
                else None,
                status=outcome["status"],
                valid_samples=len(values),
                sensor_mean_W=mean,
                DUT_mean_W=dut,
                measured_W=measured,
                sensor_min_W=min(values) if values else None,
                sensor_max_W=max(values) if values else None,
                DUT_min_W=min(values) * loss if values and loss is not None else None,
                DUT_max_W=max(values) * loss if values and loss is not None else None,
                max_gap_s=gap,
                coverage_eligible=reason is None,
                coverage_reason=reason,
            )
            results.append(
                {
                    key: str(value) if isinstance(value, D) else value
                    for key, value in result.items()
                }
            )
        nominal_id = plan["supply"]["nominal_point_id"]
        nominal = next((row for row in results if row["point_id"] == nominal_id), None)
        nominal_mean = (
            D(nominal["measured_W"]) if nominal and nominal["measured_W"] is not None else None
        )
        nominal_ok = (
            nominal is not None
            and nominal["coverage_eligible"]
            and nominal_mean is not None
            and nominal_mean > 0
        )
        nominal_reason = (
            "Nominal point not declared"
            if nominal_id is None
            else "Nominal point incomplete/ineligible or nonpositive"
            if not nominal_ok
            else None
        )
        for row in results:
            measured = D(row["measured_W"]) if row["measured_W"] is not None else None
            delta = (
                measured - nominal_mean
                if measured is not None and nominal_mean is not None
                else None
            )
            percent = 100 * delta / nominal_mean if delta is not None and nominal_ok else None
            row.update(
                change_W=str(delta) if delta is not None else None,
                change_percent=str(percent) if percent is not None else None,
                acceptance="NOT EVALUATED",
                reason=row["coverage_reason"]
                or nominal_reason
                or "No per-point change criterion supplied",
            )
            if (
                criteria is not None
                and "max_abs_change_percent" in criteria
                and row["coverage_eligible"]
                and nominal_ok
            ):
                limit = D(
                    criteria.get("point_limits_percent", {}).get(
                        row["point_id"], criteria["max_abs_change_percent"]
                    )
                )
                row["acceptance"] = "PASS" if abs(percent) <= limit else "FAIL"
                row["reason"] = None
        eligible = [row for row in results if row["coverage_eligible"]]
        lower = min(eligible, key=lambda row: D(row["observed_V"]), default=None)
        upper = max(eligible, key=lambda row: D(row["observed_V"]), default=None)
        distinct = lower is not None and D(lower["observed_V"]) < D(upper["observed_V"])
        secant = (
            (D(upper["measured_W"]) - D(lower["measured_W"]))
            / (D(upper["observed_V"]) - D(lower["observed_V"]))
            if distinct
            else None
        )
        full_points = len(eligible) == len(results)
        full = (
            full_points
            and capture["status"] == "completed"
            and capture["restoration"]["status"] == "verified"
        )
        secant_acceptance = "NOT EVALUATED"
        if (
            criteria is not None
            and "max_abs_secant_W_per_V" in criteria
            and full
            and secant is not None
        ):
            secant_acceptance = (
                "PASS" if abs(secant) <= D(criteria["max_abs_secant_W_per_V"]) else "FAIL"
            )
        decisions = []
        if criteria is not None:
            if "max_abs_change_percent" in criteria:
                decisions += [row["acceptance"] for row in results]
            if "max_abs_secant_W_per_V" in criteria:
                decisions.append(secant_acceptance)
        acceptance = "NOT EVALUATED"
        if full and decisions and all(value in ("PASS", "FAIL") for value in decisions):
            acceptance = "FAIL" if "FAIL" in decisions else "PASS"
    baseline = [D(row["value_W"]) for row in rows if row["stage"] == "baseline-before"]
    return dict(
        schema="hp437b.supply-sensitivity-results.v1",
        workflow_id=WORKFLOW,
        run_id=capture["run_id"],
        mode="synthetic",
        execution=capture["status"],
        measurement_plane=plan["measurement_plane"],
        points=results,
        completed_points=sum(row["status"] == "completed" for row in results),
        requested_points=len(results),
        eligible_points=len(eligible),
        full_point_coverage=full_points,
        full_coverage=full,
        zero_mean_W=str(sum(baseline) / len(baseline)),
        nominal_point_id=nominal_id,
        nominal_mean_W=str(nominal_mean) if nominal_mean is not None else None,
        nominal_requested_V=nominal["requested_V"] if nominal else None,
        nominal_observed_V=nominal["observed_V"] if nominal else None,
        nominal_eligible=nominal_ok,
        nominal_reason=nominal_reason,
        secant_W_per_V=str(secant) if secant is not None else None,
        secant_lower_point_id=lower["point_id"] if distinct else None,
        secant_upper_point_id=upper["point_id"] if distinct else None,
        secant_scope="all requested eligible points; first observed endpoint on ties"
        if full_points
        else "available eligible points only; incomplete coverage",
        secant_unavailable_reason="Two distinct eligible observed voltages required"
        if secant is None
        else None,
        secant_acceptance=secant_acceptance,
        restoration=capture["restoration"],
        final_state=capture["final_state"],
        acceptance=acceptance,
        criteria=criteria,
    )


def provenance(capture, bundle):
    def fact(value, pointer):
        return p.fact(
            value, basis="supplied", refs=[dict(evidence_id="workflow.json", pointer=pointer)]
        )

    roles = ("source", "meter", "sensor", "fixture", "power_supply", "voltage_observer")
    ids = ["synthetic:wf06:" + role for role in roles]
    devices = [
        p.equipment(
            identity,
            role,
            {
                "identity": p.fact(
                    note="Fictional equipment; no physical identity or calibration claim"
                )
            },
        )
        for identity, role in zip(ids, roles, strict=True)
    ]
    subject = p.dut(
        "synthetic:wf06:dut",
        "external_device",
        ids,
        {
            "name": fact(capture["plan"]["name"], "/plan/name"),
            "fixed_frequency_Hz": fact(capture["plan"]["frequency_Hz"], "/plan/frequency_Hz"),
            "power_setting": fact(capture["plan"]["power_setting"], "/plan/power_setting"),
            "signal_mode": fact(capture["plan"]["signal_mode"], "/plan/signal_mode"),
            "supply_profile": fact(capture["plan"]["supply"], "/plan/supply"),
            "voltage_plan": fact(capture["plan"]["points"], "/plan/points"),
            "fixture_loss_dB": fact(capture["plan"]["fixture_loss_dB"], "/plan/fixture_loss_dB")
            if capture["plan"]["fixture_loss_dB"] is not None
            else p.fact(note="Fixture loss unknown"),
            "fixture_source": fact(capture["plan"]["fixture_source"], "/plan/fixture_source")
            if capture["plan"]["fixture_source"]
            else p.fact(note="Fixture source unknown"),
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
            else p.fact(note="Criteria not supplied"),
        },
        subject,
        devices,
        list(bundle.entries.values()),
    )


def render(capture, result, producer, *, plots):
    def fmt(value):
        return "—" if value is None else "0" if D(value) == 0 else report_sheet._n(value)

    def e(value):
        return html.escape(str(value))

    plan, supply = capture["plan"], capture["plan"]["supply"]
    meta = [
        ("Transmitter", plan["name"]),
        ("Test", "Supply-voltage sensitivity"),
        ("Operator", capture["operator"] or "Not recorded"),
        (
            "When",
            r.timestamp(capture["started_utc"]).astimezone(UTC).strftime("%d %b %Y, %H:%M:%S UTC"),
        ),
        (
            "Fixed RF conditions",
            f"{fmt(D(plan['frequency_Hz']) / 1000000)} MHz (declared); {plan['power_setting']}; {plan['signal_mode']}",
        ),
        ("Measurement plane", result["measurement_plane"].replace("_", " ")),
        (
            "Supply profile",
            f"{fmt(supply['minimum_V'])}–{fmt(supply['maximum_V'])} V; {fmt(supply['current_limit_A'])} A current-limit setting",
        ),
    ]
    summary = f"Execution: {result['execution']}; {result['completed_points']}/{result['requested_points']} points complete. Acceptance: {result['acceptance']}."
    limitation = ""
    if capture["status"] != "completed":
        cause = (
            capture["setup"]["reason"]
            if capture["setup"]["status"] == "failed"
            else next(
                (point["reason"] for point in capture["points"] if point["status"] != "completed"),
                capture["restoration"]["reason"],
            )
        )
        limitation = "Run limitation: " + report_sheet._short(cause, 200)
        if capture["setup"]["status"] == "failed":
            limitation += (
                " ("
                + fmt(capture["setup"]["current_limit_ack_A"])
                + " A acknowledged; "
                + fmt(supply["current_limit_A"])
                + " A requested)."
            )
    zero = f"Pre-RF zero: {fmt(D(result['zero_mean_W']) * 1000000)} µW (3 source-off samples; no subtraction)."
    nominal = (
        f"Nominal reference: {result['nominal_point_id']}; {fmt(result['nominal_requested_V'])} V requested, {fmt(result['nominal_observed_V'])} V observed; {fmt(result['nominal_mean_W'])} W."
        if result["nominal_eligible"]
        else "Nominal reference unavailable: " + result["nominal_reason"] + "."
    )
    secant = (
        f"Observed endpoint secant: {fmt(result['secant_W_per_V'])} W/V"
        + (
            f" ({result['secant_lower_point_id']} → {result['secant_upper_point_id']})"
            if result["secant_W_per_V"] is not None
            else " (two distinct eligible voltages required)"
        )
        + f"; {result['eligible_points']}/{result['requested_points']} eligible points."
    )
    restore = capture["restoration"]
    restoration = (
        f"Supply restoration: {restore['status'].upper()}; {fmt(restore['requested_V'])} V requested, {fmt(restore['observed_V'])} V observed. RF source: "
        + (
            "off acknowledged (synthetic)."
            if capture["final_state"]["external_source_off"]
            else "UNKNOWN (synthetic)."
        )
    )
    headings = ["Point", "Request V", "Observed V", "RF power W", "Change %", "Valid", "State"]
    table = [
        [
            row["point_id"],
            fmt(row["requested_V"]),
            fmt(row["observed_V"]),
            fmt(row["measured_W"]),
            fmt(row["change_percent"]),
            str(row["valid_samples"]) + "/30",
            row["status"],
        ]
        for row in result["points"]
    ]
    limits = "Acceptance limits not supplied."
    if capture["criteria"] is not None:
        c = capture["criteria"]
        selected = []
        if "max_abs_change_percent" in c:
            selected.append("|change| ≤ " + fmt(c["max_abs_change_percent"]) + "%")
        if "max_abs_secant_W_per_V" in c:
            selected.append("|secant| ≤ " + fmt(c["max_abs_secant_W_per_V"]) + " W/V")
        limits = (
            "Criteria: "
            + "; ".join(selected)
            + ". "
            + report_sheet._short(c["source"], 90)
            + "; inclusive, no guard band."
            + (" Point overrides: appendix." if c.get("point_limits_percent") else "")
        )
    notes = (
        "Voltages are synthetic readbacks at "
        + supply["observation_location"]
        + ". RF sensor factor is already represented; supplied fixture loss is applied once at DUT output. Change is relative to the declared nominal point; repeated points retain history. Endpoint secant is not a universal regulator slope or DC-to-RF efficiency."
    )
    footer = [
        "Equipment: fictional transmitter, HP 437B, 8482A, fixture, supply, and voltage observer.",
        report_sheet.producer_note(producer),
        "Record: " + capture["run_id"],
    ]
    headers = "".join("<th>" + e(cell) + "</th>" for cell in headings)
    body = "".join(
        "<tr>" + "".join("<td>" + e(cell) + "</td>" for cell in row) + "</tr>" for row in table
    )
    metadata = "<br>".join("<strong>" + e(key) + ":</strong> " + e(value) for key, value in meta)
    sheet = f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>RF Output Power Test</title><style>{report_sheet.STYLE}table{{width:100%;border-collapse:collapse}}td,th{{padding:5px 3px;text-align:left;border-bottom:1px solid #ddd;overflow-wrap:anywhere}}img{{width:100%;max-height:42mm;object-fit:contain}}footer{{break-inside:avoid}}p{{margin:7px 0}}@media print{{body{{font-size:10pt}}td,th{{font-size:9pt;padding:4px 2px}}h1{{margin-bottom:8px}}}}</style><body><main class="sheet"><h1>RF Output Power Test</h1><p><strong>SYNTHETIC - fictional transmitter and measurements; no physical RF</strong></p><p>{metadata}</p><p><strong>{e(summary)}</strong></p>{"<p>" + e(limitation) + "</p>" if limitation else ""}<p>{e(zero)}<br>{e(nominal)}<br>{e(secant)}</p><p><strong>{e(restoration)}</strong></p><table><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>{'<img src="supply-sensitivity.svg" alt="Measured RF power versus observed supply voltage">' if plots else ""}<p>{e(limits)}</p><p>{e(notes)}</p><p>Unavailable values are —. Full readbacks, range/coverage reasons, criteria, and restoration evidence: appendix.html.</p><footer>{"".join("<p>" + e(line) + "</p>" for line in footer)}<p>Evidence and limitations: appendix.html; results.json; provenance.json.</p></footer></main></body></html>"""
    md = (
        "# RF Output Power Test\n\nSYNTHETIC - fictional transmitter and measurements.\n\n"
        + "\n\n".join(report_sheet._markdown(key + ": " + str(value)) for key, value in meta)
        + "\n\n"
        + "\n\n".join(
            report_sheet._markdown(line)
            for line in (summary, limitation, zero, nominal, secant, restoration)
        )
        + "\n\n"
    )
    md += (
        "| "
        + " | ".join(headings)
        + " |\n| "
        + " | ".join("---" for _ in headings)
        + " |\n"
        + "\n".join(
            "| " + " | ".join(report_sheet._markdown(cell) for cell in row) + " |" for row in table
        )
        + "\n\n"
    )
    md += (
        "\n\n".join(report_sheet._markdown(line) for line in (limits, notes, *footer))
        + "\n\nFull evidence: appendix.html.\n"
    )
    return sheet, md


def publish(source, output, *, plots=True):
    source, output = preflight(source, output, plots=plots)
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
            selected = [
                row
                for row in result["points"]
                if row["status"] == "completed"
                and row["observed_V"] is not None
                and row["measured_W"] is not None
            ]
            axis.scatter(
                [float(row["observed_V"]) for row in selected],
                [float(row["measured_W"]) for row in selected],
                marker="x",
                label="RF output",
            )
            if result["nominal_eligible"]:
                axis.scatter(
                    [float(result["nominal_observed_V"])],
                    [float(result["nominal_mean_W"])],
                    marker="o",
                    facecolors="none",
                    edgecolors="tab:orange",
                    s=70,
                    label="Nominal reference",
                )
            axis.set_xlabel("Observed DUT supply voltage (V)")
            axis.set_ylabel("RF power (W)")
            axis.set_title(result["measurement_plane"].replace("_", " ") + " plane")
            axis.grid(axis="y", alpha=0.2)
            if not selected:
                axis.text(
                    0.5,
                    0.5,
                    "No completed RF points with observed voltage",
                    ha="center",
                    va="center",
                    transform=axis.transAxes,
                )
                axis.set_xticks([])
                axis.set_yticks([])
            fig.legend(
                *axis.get_legend_handles_labels(), loc="outside upper right", ncols=2, frameon=False
            )
            for extension in ("png", "svg"):
                fig.savefig(output / ("supply-sensitivity." + extension), dpi=150)
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
                "No actual supply/current/voltage-observer control or RF keying",
                "No universal regulator slope, DC input power, efficiency, or uncertainty verdict",
                "Physical supply/voltage observation/restoration remains DUT-CTRL-01",
            ],
        )
        (output / "appendix.html").write_text(
            '<!doctype html><meta charset="utf-8"><title>WF-06 evidence</title><h1>Technical appendix</h1><pre>'
            + html.escape(r.encoded(appendix).decode())
            + "</pre>",
            encoding="utf-8",
        )
        p.verify(record, source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
            "Capture changed during publication",
        )
        _seal(
            output,
            dict(
                schema="hp437b.supply-sensitivity-report.v1",
                mode="synthetic",
                run_id=capture["run_id"],
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
        print(f"WF-06: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
