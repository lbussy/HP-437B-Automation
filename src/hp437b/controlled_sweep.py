"""WF-04–WF-06 controlled fake sweeps over shared DUT-CTRL-01 sessions.

Legacy fixture captures remain independently readable. Each point stores original
production logger files and replayable control receipts; this module derives the
existing analysis inputs from those samples, never from simulation truth.
"""

import csv
import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from . import dut_control as c
from . import dut_simulation as f
from . import provenance as p
from . import report_context, report_identity
from . import reporting as r
from . import transmitter_workflow as tx
from .workflow_report import _seal, preflight

SCHEMA = "hp437b.controlled-sweep.v1"
BACKEND = "dut-ctrl01-fake"
FAULTS = (
    *(case for case in f.SCENARIOS if case not in ("missing-loss", "sensor-plane")),
    "factor-mismatch",
)
ALIASES = {
    "timeout": "meter-timeout",
    "malformed": "meter-malformed",
    "instrument-error": "instrument-error",
    "cancel": "cancel",
    "source-off-failure": "source-off-failure",
    "ack-mismatch": "setting-mismatch",
    "frequency-mismatch": "frequency-mismatch",
    "frequency-unverified": "frequency-unverified",
    "factor-mismatch": "factor-mismatch",
    "supply-control-failure": "supply-control-failure",
    "current-limit-mismatch": "current-mismatch",
    "restore-failure": "restore-failure",
    "restore-mismatch": "restore-mismatch",
    "restore-unverified": "restore-unverified",
}


def module(kind):
    from . import frequency_sweep, power_setting, supply_sensitivity

    p.require(kind in ("WF-04", "WF-05", "WF-06"), "Unknown controlled workflow")
    return {"WF-04": power_setting, "WF-05": frequency_sweep, "WF-06": supply_sensitivity}[kind]


def specification(kind, plan, point, *, factor_fault=False):
    """Translate a declared point into bounded control and separate fake-model inputs."""
    control = c.default_plan()
    control["dut_name"] = plan["name"]
    control["signal_mode"] = plan["signal_mode"]
    control["measurement_plane"] = "sensor_input"  # parent applies point corrections once
    control["frequency_Hz"] = point["frequency_Hz"] if kind == "WF-05" else plan["frequency_Hz"]
    control["power_setting"] = point["setting"] if kind == "WF-04" else plan["power_setting"]
    namespace = {
        "WF-04": "synthetic:wf04:",
        "WF-05": "synthetic:wf05:",
        "WF-06": "synthetic:wf06:",
    }[kind]
    for role, asset in control["assets"].items():
        asset["asset_id"] = namespace + (
            {"transmitter": "source", "supply": "power_supply", "observer": "voltage_observer"}[
                role
            ]
            if kind == "WF-06"
            else role
        )
    control["fixture"]["asset_id"] = namespace + "fixture"
    model = f.default_model()
    model["source_W"] = point["synthetic_DUT_W"]
    model["loss_dB"] = (
        plan["simulation_loss_dB"] if kind == "WF-06" else point["simulation_loss_dB"]
    )
    control["max_RF_W"] = str(max(D(".000001"), D(model["source_W"])))
    control["fixture"].update(
        input_limit_W=control["max_RF_W"],
        minimum_loss_dB=model["loss_dB"],
        loss_dB=model["loss_dB"],
    )
    if kind == "WF-05":
        model.update(
            response_percent=point["simulation_sensor_factor_percent"],
            sensor_factor_percent=point["sensor_factor_percent"],
            factor_applied_in=point["factor_applied_in"],
        )
        expected = (
            point["sensor_factor_percent"] if point["factor_applied_in"] == "meter" else "100"
        )
        model["factor_readback_percent"] = (
            str(D(expected) - 1 if D(expected) > 1 else D(expected) + 1)
            if factor_fault
            else expected
        )
    if kind == "WF-06":
        supply = plan["supply"]
        control["supply"].update(
            **{
                key: supply[key]
                for key in (
                    "minimum_V",
                    "maximum_V",
                    "current_limit_A",
                    "restore_V",
                    "tolerance_V",
                    "observation_location",
                )
            },
            condition_V=point["requested_V"],
            restore_current_limit_A=supply["current_limit_A"],
        )
        model.update(
            condition_observed_V=point["synthetic_observed_V"],
            missing_voltage=point["synthetic_observed_V"] is None,
        )
    c.validate_plan(control)
    f.validate_model(model, control)
    return control, model


def _last(events, device, operation, phase=None):
    return next(
        (
            event
            for event in reversed(events)
            if event["device"] == device
            and event["operation"] == operation
            and event["status"] == "returned"
            and (phase is None or event["phase"] == phase)
        ),
        None,
    )


def projection(kind, record, children, bundle):
    """Build versioned analysis inputs from checked child sessions and readbacks."""
    points = []
    rows = []
    by_id = {item[0]: item for item in children}
    completed = (
        len(children) == len(record["plan"]["points"])
        and all(child[1]["status"] == "completed" for child in children)
        and record["stop_before"] is None
    )
    status = (
        "completed"
        if completed
        else "failed"
        if any(child[1]["status"] == "failed" for child in children)
        else "interrupted"
    )
    first = children[0] if children else None
    last = children[-1] if children else None

    def append_stage(pid, child, stage):
        path = "points/" + pid + "/stages/" + stage + ".csv"
        if stage not in child[2]:
            return
        for row in csv.DictReader(io.StringIO(bundle.read(path).decode("utf-8"))):
            rows.append(
                dict(
                    run_id=record["run_id"],
                    point_id="" if stage.startswith("baseline") else pid,
                    stage=stage,
                    sequence=len(rows) + 1,
                    elapsed_s=str(
                        (
                            r.timestamp(row["received_utc"]) - r.timestamp(record["started_utc"])
                        ).total_seconds()
                    ),
                    value_W=row["value"],
                    status=row["status"],
                )
            )

    if first:
        append_stage(first[0], first, "baseline-before")
    for point in record["plan"]["points"]:
        pid = point["point_id"]
        child = by_id.get(pid)
        if child is None:
            state = dict(
                point_id=pid,
                status="skipped",
                source_on_ack=False,
                source_off_ack=False,
                reason="Not reached",
            )
            if kind == "WF-04":
                state["setting_ack"] = None
            if kind == "WF-05":
                state.update(frequency_ack_Hz=None, factor_ack_percent=None)
            if kind == "WF-06":
                state.update(
                    voltage_command_ack=False, observed_V=None, communication_uncertain=False
                )
        else:
            _, capture, stages, controls = child
            events = controls["events"]
            configured = _last(events, "transmitter", "status", "configure")
            reply = configured["reply"] if configured else {}
            on = controls["phases"]["activate"]["status"] == "completed"
            off = controls["phases"]["deactivate"]["status"] == "completed"
            point_status = capture["status"]
            if kind == "WF-06" and stages.get("plateau", {}).get("outcome") == "completed" and off:
                point_status = "completed"
            state = dict(
                point_id=pid,
                status=point_status,
                source_on_ack=on,
                source_off_ack=off,
                reason=capture["outcome"]["error"]
                or "; ".join(capture["outcome"]["cleanup_errors"]),
            )
            if kind == "WF-04":
                state["setting_ack"] = reply.get("power_setting")
            if kind == "WF-05":
                state.update(
                    frequency_ack_Hz=reply.get("frequency_Hz"),
                    factor_ack_percent=capture["meter_preparation"]["observed_percent"]
                    if capture["meter_preparation"]
                    else None,
                )
            if kind == "WF-06":
                voltage = _last(events, "observer", "measure", "verify") or _last(
                    events, "observer", "measure", "configure"
                )
                command = _last(events, "supply", "set_voltage", "configure")
                state.update(
                    voltage_command_ack=command is not None and command["reply"] is True,
                    observed_V=voltage["reply"]["volts"] if voltage else None,
                    communication_uncertain=any(
                        item.get("uncertain", False) for item in capture["stages"].values()
                    ),
                )
            append_stage(pid, child, "settling")
            append_stage(pid, child, "plateau")
        points.append(state)
    if completed and last:
        append_stage(last[0], last, "baseline-after")
    summary = (
        last[1]["final_state"]
        if last
        else dict(
            rf_state="unknown", supply_restored=False, observed_V=None, current_limit_ack_A=None
        )
    )
    final = dict(
        external_source_off=True if summary["rf_state"] == "off" else None,
        rf_state=summary["rf_state"],
        supply_restored=summary["supply_restored"],
        meter_reference_off=True,
        hardware_opened=False,
    )
    derived = dict(
        points=points,
        status=status,
        final_state=final,
        control_summary=dict(
            attempted_points=len(children),
            completed_sessions=sum(child[1]["status"] == "completed" for child in children),
            rf_state=summary["rf_state"],
            supply_restored=summary["supply_restored"],
            last_observed_V=summary["observed_V"],
            last_current_limit_A=summary["current_limit_ack_A"],
        ),
    )
    if kind == "WF-06":
        current = _last(first[3]["events"], "supply", "status", "configure") if first else None
        configured = current is not None and D(current["reply"]["current_limit_A"]) == D(
            record["plan"]["supply"]["current_limit_A"]
        )
        derived["setup"] = dict(
            status="verified" if configured else "failed",
            current_limit_ack_A=current["reply"]["current_limit_A"] if current else None,
            reason=""
            if configured
            else (first[1]["outcome"]["error"] if first else "No condition executed"),
        )
        phase = last[3]["phases"]["restore"] if last else {"status": "skipped"}
        observed = _last(last[3]["events"], "observer", "measure", "restore") if last else None
        ack = _last(last[3]["events"], "supply", "set_voltage", "restore") if last else None
        derived["restoration"] = dict(
            status="verified"
            if summary["supply_restored"]
            else "failed"
            if phase["status"] == "failed"
            else "unknown",
            attempted=phase["status"] != "skipped",
            command_ack=ack is not None and ack["reply"] is True,
            requested_V=record["plan"]["supply"]["restore_V"],
            observed_V=observed["reply"]["volts"] if observed else None,
            reason=phase.get("reason", "")
            if phase["status"] != "skipped"
            else "Unqualified source/control state; no restoration",
        )
    return derived, rows


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    from .power_setting import COLUMNS

    writer = csv.DictWriter(stream, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def validate_suite_context(context):
    p._keys(context, ("schema", "suite_id", "index", "initial_hardware"))
    p.require(context["schema"] == "hp437b.suite-context.v1", "Invalid suite context schema")
    uuid.UUID(context["suite_id"])
    p.require(type(context["index"]) is int and 1 <= context["index"] <= 3, "Invalid suite index")
    state = context["initial_hardware"]
    p._keys(state, ("rf", "frequency", "setting", "voltage", "current", "meter_factor_percent"))
    p.require(
        type(state["rf"]) is bool
        and type(state["frequency"]) is int
        and 0 <= state["frequency"] <= 4200000000,
        "Invalid suite fake state",
    )
    module("WF-04").text(state["setting"])
    p.require(
        0 <= r.number(state["voltage"]) <= 1000
        and 0 < r.number(state["current"]) <= 100
        and 1 <= r.number(state["meter_factor_percent"]) <= 150,
        "Invalid suite fake numeric state",
    )


def run(
    kind,
    output,
    *,
    scenario="nominal",
    plan=None,
    criteria=None,
    operator=None,
    report_output=None,
    plots=True,
    fault=None,
    fault_point=None,
    stop_before=None,
    test_profile=None,
    suite_context=None,
    hardware=None,
    epoch=None,
):
    w = module(kind)
    p.require(scenario in w.SCENARIOS, "Unknown workflow scenario")
    p.require(plan is None or scenario == "nominal", "Custom plans require nominal scenario")
    plan = w.validate_plan(w.default_plan(scenario) if plan is None else plan)
    w.validate_criteria(criteria, plan)
    operator = report_context.resolve_operator(operator)["value"]
    fault = ALIASES.get(scenario, "nominal") if fault is None else fault
    p.require(
        fault in FAULTS and (fault != "factor-mismatch" or kind == "WF-05"),
        "Unknown/unsupported control fault",
    )
    ids = [point["point_id"] for point in plan["points"]]
    fault_point = fault_point or ids[min(1, len(ids) - 1)]
    if scenario in ("missing-point", "missing-band"):
        stop_before = stop_before or fault_point
    p.require(
        fault_point in ids and (stop_before is None or stop_before in ids),
        "Fault/stop point is not requested",
    )
    for point in plan["points"]:
        specification(
            kind,
            plan,
            point,
            factor_fault=fault == "factor-mismatch" and point["point_id"] == fault_point,
        )
    if test_profile is not None:
        from . import test_profiles

        entry = test_profiles.validate_binding(test_profile, kind)
        p.require(
            entry["plan"] == plan
            and entry["criteria"] == criteria
            and test_profile["operator"]["value"] == operator,
            "Profile differs from requested capture",
        )
        p.require(scenario == "nominal", "Profile plans require nominal scenario")
    if suite_context is not None:
        validate_suite_context(suite_context)
        p.require(
            test_profile is not None
            and type(hardware) is f.Hardware
            and hardware.snapshot() == suite_context["initial_hardware"],
            "Suite requires a bound profile and matching in-memory hardware",
        )
        p.require(
            isinstance(epoch, datetime) and epoch.utcoffset() is not None,
            "Suite requires a UTC timeline",
        )
    else:
        p.require(hardware is None and epoch is None, "Shared state requires suite context")
    output = Path(output).resolve()
    p.require(not output.exists() and not p.sidecar_path(output).exists(), "Capture output exists")
    if report_output is not None:
        preflight(output, report_output, plots=plots)
    started = epoch if suite_context is not None else datetime.now(UTC)
    record = dict(
        schema=SCHEMA,
        backend=BACKEND,
        workflow_kind=kind,
        workflow_id=w.WORKFLOW,
        mode="synthetic",
        simulation=True,
        run_id=str(uuid.uuid4()),
        scenario=scenario,
        fault=fault,
        fault_point=fault_point,
        stop_before=stop_before,
        plan=p._json(r.encoded(plan)),
        criteria=criteria,
        operator=operator,
        profile=dict(w.PROFILE),
        software=report_identity.identify(),
        started_utc=started.isoformat(),
        finished_utc=None,
        status="running",
        children=[],
        points=[],
        final_state=None,
        control_summary=None,
    )
    if suite_context is not None:
        record["suite_context"] = p._json(r.encoded(suite_context))
    if test_profile is not None:
        record["test_profile"] = dict(
            path="test-profile.json", sha256=r.digest(r.encoded(test_profile))
        )
    output.mkdir(parents=True, exist_ok=False)
    if test_profile is not None:
        (output / "test-profile.json").write_bytes(r.encoded(test_profile))
    (output / "points").mkdir()
    (output / "starting.json").write_bytes(r.encoded(record))
    epoch = started
    children = []
    for point in plan["points"]:
        pid = point["point_id"]
        if stop_before == pid:
            break
        active = fault if pid == fault_point else "nominal"
        control, model = specification(kind, plan, point, factor_fault=active == "factor-mismatch")
        if hardware is None:
            hardware = f.Hardware(
                False,
                1000000,
                "Initial state (synthetic)",
                control["supply"]["restore_V"],
                control["supply"]["restore_current_limit_A"],
            )
        if active == "initial-on":
            hardware.rf = True  # explicit injected boundary fault
        child_path = output / "points" / pid
        child = tx.simulate(
            child_path,
            scenario="nominal" if active == "factor-mismatch" else active,
            plan=control,
            model=model,
            hardware=hardware,
            epoch=epoch,
            parent_context=dict(run_id=record["run_id"], point_id=pid, workflow_id=w.WORKFLOW),
            operator=operator,
        )
        checked, stages, child_bundle = tx.load(child_path)
        controls = child_bundle.json("controls.json")
        children.append((pid, checked, stages, controls))
        record["children"].append(dict(point_id=pid, path="points/" + pid, run_id=child["run_id"]))
        epoch = r.timestamp(child["finished_utc"])
        if child["status"] != "completed":
            break
    record["finished_utc"] = epoch.isoformat()
    # Projection reads only actual checked logger files; it never uses model powers.
    bundle = p.Bundle(output)
    derived, rows = projection(kind, record, children, bundle)
    record.update(derived)
    (output / "workflow.json").write_bytes(r.encoded(record))
    (output / "samples.csv").write_bytes(csv_bytes(rows))
    _seal(output, dict(schema=SCHEMA, mode="synthetic", run_id=record["run_id"]))
    if report_output is not None:
        w.publish(output, report_output, plots=plots)
    return record


def load(kind, source):
    w = module(kind)
    bundle = p.Bundle(source)
    inv = bundle.inventory("artifacts.json", "synthetic")
    record = bundle.json("workflow.json")
    p.require(
        record["schema"] == SCHEMA
        and record["backend"] == BACKEND
        and record["workflow_kind"] == kind
        and record["workflow_id"] == w.WORKFLOW
        and record["mode"] == "synthetic"
        and record["simulation"] is True,
        "Wrong controlled workflow/mode",
    )
    uuid.UUID(record["run_id"])
    p.require(
        inv.get("schema") == SCHEMA and inv.get("run_id") == record["run_id"],
        "Controlled inventory/run mismatch",
    )
    w.validate_plan(record["plan"])
    w.validate_criteria(record["criteria"], record["plan"])
    report_context.validate_operator(record["operator"])
    p.require(
        record["profile"] == w.PROFILE
        and record["scenario"] in w.SCENARIOS
        and record["fault"] in FAULTS,
        "Unsupported controlled profile",
    )
    ids = [point["point_id"] for point in record["plan"]["points"]]
    p.require(
        record["fault_point"] in ids
        and (record["stop_before"] is None or record["stop_before"] in ids),
        "Invalid controlled point selector",
    )
    initial = {key: value for key, value in record.items() if key not in ("setup", "restoration")}
    initial.update(
        finished_utc=None,
        status="running",
        children=[],
        points=[],
        final_state=None,
        control_summary=None,
    )
    p.require(bundle.json("starting.json") == initial, "Controlled starting/final mismatch")
    base_keys = (
        "schema",
        "backend",
        "workflow_kind",
        "workflow_id",
        "mode",
        "simulation",
        "run_id",
        "scenario",
        "fault",
        "fault_point",
        "stop_before",
        "plan",
        "criteria",
        "operator",
        "profile",
        "software",
        "started_utc",
        "finished_utc",
        "status",
        "children",
        "points",
        "final_state",
        "control_summary",
    )
    p._keys(
        record,
        base_keys
        + (("setup", "restoration") if kind == "WF-06" else ())
        + (("test_profile",) if "test_profile" in record else ())
        + (("suite_context",) if "suite_context" in record else ()),
    )
    if "suite_context" in record:
        validate_suite_context(record["suite_context"])
        p.require("test_profile" in record, "Suite child requires a profile binding")
    if "test_profile" in record:
        from . import test_profiles

        ref = record["test_profile"]
        p._keys(ref, ("path", "sha256"))
        p.require(
            ref["path"] == "test-profile.json"
            and ref["sha256"] == r.digest(bundle.read(ref["path"])),
            "Profile binding file/hash mismatch",
        )
        binding = bundle.json(ref["path"])
        entry = test_profiles.validate_binding(binding, kind)
        p.require(
            entry["plan"] == record["plan"]
            and entry["criteria"] == record["criteria"]
            and binding["operator"]["value"] == record["operator"]
            and record["scenario"] == "nominal",
            "Saved profile differs from capture",
        )
    else:
        p.require("test-profile.json" not in bundle.entries, "Unbound profile snapshot")
    p.require(
        isinstance(record["children"], list) and len(record["children"]) <= len(ids),
        "Invalid child count",
    )
    children = []
    child_ids, session_ids = set(), set()
    epoch = r.timestamp(record["started_utc"])
    last_state = None
    halted = False
    for index, child_ref in enumerate(record["children"]):
        pid = ids[index]
        p._keys(child_ref, ("point_id", "path", "run_id"))
        p.require(
            not halted
            and pid != record["stop_before"]
            and child_ref["point_id"] == pid
            and child_ref["path"] == "points/" + pid,
            "Out-of-order, repeated, post-fault, or skipped child",
        )
        active = record["fault"] if pid == record["fault_point"] else "nominal"
        control, model = specification(
            kind,
            record["plan"],
            record["plan"]["points"][index],
            factor_fault=active == "factor-mismatch",
        )
        child, stages, child_bundle = tx.load(Path(source) / child_ref["path"])
        p.require(
            child["schema"] == tx.MODEL_SCHEMA
            and child["run_id"] == child_ref["run_id"]
            and child["parent_context"]
            == dict(run_id=record["run_id"], point_id=pid, workflow_id=w.WORKFLOW),
            "Child/source/run context mismatch",
        )
        p.require(
            child["plan"] == control
            and child["simulation_model"] == model
            and child["scenario"] == ("nominal" if active == "factor-mismatch" else active)
            and child["operator"] == record["operator"]
            and child["criteria"] is None,
            "Child condition/model mismatch",
        )
        p.require(child["run_id"] not in child_ids, "Duplicate child run identity")
        child_ids.add(child["run_id"])
        for name in child_bundle.entries:
            if name.endswith(".csv.session.json"):
                sid = child_bundle.json(name)["session_id"]
                p.require(sid not in session_ids, "Duplicate meter session identity across points")
                session_ids.add(sid)
        expected = (
            last_state
            or record.get("suite_context", {}).get("initial_hardware")
            or f.Hardware(
                False,
                1000000,
                "Initial state (synthetic)",
                control["supply"]["restore_V"],
                control["supply"]["restore_current_limit_A"],
            ).snapshot()
        )
        expected = dict(expected)
        if active == "initial-on":
            expected["rf"] = True
        p.require(
            child["initial_hardware"] == expected and r.timestamp(child["started_utc"]) == epoch,
            "Fake hardware reset or overlapping/reordered point timeline",
        )
        last_state = child["final_hardware"]
        epoch = r.timestamp(child["finished_utc"])
        children.append((pid, child, stages, child_bundle.json("controls.json")))
        halted = child["status"] != "completed"
    expected_count = (
        len(ids)
        if not halted and record["stop_before"] is None
        else ids.index(record["stop_before"])
        if not halted
        else len(children)
    )
    p.require(
        len(children) == expected_count
        and r.timestamp(record["finished_utc"]) == epoch
        and 0 <= (epoch - r.timestamp(record["started_utc"])).total_seconds() <= 900,
        "Missing child or sweep budget/timeline mismatch",
    )
    known = {"points/" + pid + "/" for pid, *_ in children}
    p.require(
        all(
            not path.startswith("points/") or any(path.startswith(prefix) for prefix in known)
            for path in bundle.entries
        ),
        "Unrequested/post-fault hidden point evidence",
    )
    derived, rows = projection(kind, record, children, bundle)
    p.require(
        all(r.encoded(record[key]) == r.encoded(value) for key, value in derived.items())
        and bundle.read("samples.csv") == csv_bytes(rows),
        "Analysis projection differs from original controls/logger evidence",
    )
    return record, rows, bundle


def augment_provenance(record, bundle, legacy):
    """Keep workflow facts and add the actual simulated control identities/readbacks."""
    devices = {item["equipment_id"]: item for item in legacy["equipment"]}
    for child in record["children"][:1]:
        root = child["path"]
        manifest = bundle.json(root + "/workflow.json")
        controls = bundle.json(root + "/controls.json")
        for role, asset in manifest["plan"]["assets"].items():
            item = devices.setdefault(asset["asset_id"], p.equipment(asset["asset_id"], role, {}))
            item["facts"]["configured_identity"] = p.fact(
                asset,
                basis="supplied",
                refs=[dict(evidence_id=root + "/workflow.json", pointer="/plan/assets/" + role)],
            )
            observed = next(
                (
                    (i, event["reply"])
                    for i, event in enumerate(controls["events"])
                    if event["device"] == role
                    and event["operation"] == "identify"
                    and event["status"] == "returned"
                ),
                None,
            )
            if observed:
                item["facts"]["reported_identity"] = p.fact(
                    observed[1],
                    basis="observed",
                    refs=[
                        dict(
                            evidence_id=root + "/controls.json",
                            pointer=f"/events/{observed[0]}/reply",
                        )
                    ],
                    note="Simulated readback; no physical identity claim",
                )
    legacy["equipment"] = list(devices.values())
    legacy["dut"]["equipment_refs"] = list(devices)
    legacy["run"]["facts"]["control_backend"] = p.fact(
        record["backend"],
        basis="supplied",
        refs=[dict(evidence_id="workflow.json", pointer="/backend")],
    )
    legacy["run"]["facts"]["control_sessions"] = p.fact(
        record["children"],
        basis="supplied",
        refs=[dict(evidence_id="workflow.json", pointer="/children")],
    )
    if "test_profile" in record:
        binding = bundle.json("test-profile.json")
        legacy["dut"]["facts"]["profile_identity"] = p.fact(
            binding["profile"]["dut"],
            basis="supplied",
            refs=[dict(evidence_id="test-profile.json", pointer="/profile/dut")],
        )
        legacy["run"]["facts"]["test_profile"] = p.fact(
            binding,
            basis="supplied",
            refs=[dict(evidence_id="test-profile.json", pointer="")],
            note="Validated fake-only profile snapshot; hash detects changes, not authenticity",
        )
    p.validate(legacy)
    return legacy


def annotate_report(output, capture):
    if capture.get("backend") != BACKEND:
        return
    summary = capture["control_summary"]
    line = (
        f"Shared DUT-CTRL-01 controls: {summary['completed_sessions']}/{len(capture['plan']['points'])} sessions completed; RF state {summary['rf_state'].upper()}; supply restoration "
        + ("VERIFIED" if summary["supply_restored"] else "UNVERIFIED")
        + ". Intermediate per-point baselines and all control/logger evidence remain in the capture bundle."
    )
    import html

    page = output / "report.html"
    page.write_text(
        page.read_text().replace("<footer>", "<p>" + html.escape(line) + "</p><footer>", 1),
        encoding="utf-8",
    )
    md = output / "report.md"
    md.write_text(md.read_text() + "\n\n" + line + "\n", encoding="utf-8")
