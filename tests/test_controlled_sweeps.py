"""WF-04–WF-06 share guarded fake controls, original logger files, and state history."""

import json
from decimal import Decimal as D

import pytest

from hp437b import controlled_sweep as s
from hp437b import provenance as p
from hp437b import reporting as r
from hp437b import transmitter_workflow as tx
from hp437b.workflow_report import _seal


def run(tmp_path, kind, **kwargs):
    w = s.module(kind)
    source = tmp_path / "capture"
    w.controlled(source, **kwargs)
    record, rows, bundle = w.load(source)
    return w, source, record, rows, bundle, w.analyze(record, rows)


def snapshot(source):
    return {
        path.relative_to(source).as_posix(): r.digest(path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
def test_actual_logger_shared_hardware_provenance_and_saved_report(tmp_path, kind):
    w, source, cap, rows, bundle, result = run(tmp_path, kind, operator="Synthetic test operator")
    assert cap["schema"] == s.SCHEMA and cap["backend"] == s.BACKEND
    assert result["execution"] == "completed" and result["acceptance"] == "NOT EVALUATED"
    n = len(cap["plan"]["points"])
    assert len(cap["children"]) == n and result["completed_points"] == n
    assert len(rows) == 6 + 50 * n
    previous = None
    sessions = set()
    for item in cap["children"]:
        child, stages, b = tx.load(source / item["path"])
        assert child["parent_context"] == dict(
            run_id=cap["run_id"], point_id=item["point_id"], workflow_id=w.WORKFLOW
        )
        assert [stages[stage]["valid"] for stage in tx.STAGES] == [3, 20, 30, 3]
        assert child["final_state"]["rf_state"] == "off" and child["final_state"]["supply_restored"]
        if previous:
            assert child["initial_hardware"] == previous["final_hardware"]
            assert child["started_utc"] == previous["finished_utc"]
        previous = child
        for name in b.entries:
            if name.endswith(".csv.session.json"):
                meta = b.json(name)
                assert meta["session_id"] not in sessions
                sessions.add(meta["session_id"])
                assert meta["instrument"]["serial"] == "SYNTHETIC-DUT01"
        assert not any(
            event.get("raw_hex") in (b"OC0".hex(), b"OC1".hex())
            for event in b.json("meter-trace.json")
        )
    assert cap["control_summary"]["completed_sessions"] == n
    prov = w.provenance(cap, bundle)
    p.verify(prov, source)
    assert any("reported_identity" in device["facts"] for device in prov["equipment"])
    assert any(device["role"] in ("supply", "power_supply") for device in prov["equipment"])
    before = snapshot(source)
    assert w.publish(source, tmp_path / "report", plots=False) == result
    assert snapshot(source) == before
    page = (tmp_path / "report/report.html").read_text()
    assert "Shared DUT-CTRL-01 controls" in page and "SYNTHETIC" in page
    assert page.index("Equipment:") < page.index("Report Harness:") < page.index("Record:")


@pytest.mark.parametrize(
    "kind,scenario,expected",
    (
        ("WF-04", "compressed", ["1", "4.8", "9.5"]),
        ("WF-05", "band-droop", ["4.8", "5", "5.1", "4.9", "4.7"]),
        ("WF-06", "droop", ["4.5", "5", "5.2"]),
    ),
)
def test_independent_numeric_oracles(tmp_path, kind, scenario, expected):
    result = run(tmp_path, kind, scenario=scenario)[-1]
    assert [D(point["measured_W"]) for point in result["points"]] == [
        D(value) for value in expected
    ]
    if kind == "WF-04":
        assert [D(point["error_percent"]) for point in result["points"]] == [0, -4, -5]
    if kind == "WF-05":
        assert float(result["observed_spread_dB"]) == pytest.approx(0.354723181622)
    if kind == "WF-06":
        assert D(result["secant_W_per_V"]) == D(".35")
        assert [D(point["change_percent"]) for point in result["points"]] == [-10, 0, 4]


@pytest.mark.parametrize("scenario", ("unequal-corrections", "meter-corrected"))
def test_factor_policy_and_off_state_preparation(tmp_path, scenario):
    _, source, cap, _, _, result = run(tmp_path, "WF-05", scenario=scenario)
    assert [D(row["measured_W"]) for row in result["points"]] == [5] * 5
    for ref in cap["children"]:
        child, _, _ = tx.load(source / ref["path"])
        prep = child["meter_preparation"]
        assert prep["status"] == "completed" and child["initial_hardware"]["rf"] is False
        assert child["final_hardware"]["meter_factor_percent"] == prep["observed_percent"]
    assert [row["factor_applied_in"] for row in result["points"]] == [
        "analysis" if scenario == "unequal-corrections" else "meter"
    ] * 5


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
@pytest.mark.parametrize(
    "fault",
    (
        "meter-timeout",
        "meter-malformed",
        "cancel",
        "source-off-failure",
        "source-still-on",
        "restore-failure",
        "supply-control-failure",
        "identity-mismatch",
        "late-reply",
    ),
)
def test_stop_on_fault_no_later_point_no_retry(tmp_path, kind, fault):
    w, source, cap, _, _, result = run(tmp_path, kind, fault=fault, fault_point="P02")
    assert cap["status"] == ("interrupted" if fault == "cancel" else "failed")
    assert result["acceptance"] == "NOT EVALUATED"
    assert len(cap["children"]) == 2 and not (source / "points/P03").exists()
    assert all(point["status"] == "skipped" for point in result["points"][2:])
    child, _, b = tx.load(source / "points/P02")
    events = b.json("controls.json")["events"]
    assert (
        sum(
            event["operation"] == "set_rf" and event["request"].get("on") is False
            for event in events
        )
        <= 1
    )
    assert b.json("controls.json")["order"].count("restore") <= 1
    if fault in ("meter-timeout", "meter-malformed"):
        assert child["final_state"]["blocked"] and child["final_state"]["rf_state"] == "unknown"
        assert b.json("controls.json")["order"][-1] == "verify"
    if fault == "source-still-on":
        assert cap["final_state"]["rf_state"] == "on"
    assert (
        w.publish(source, tmp_path / "failed-report", plots=False)["acceptance"] == "NOT EVALUATED"
    )


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
@pytest.mark.parametrize("how", ("stop", "initial-on"))
def test_no_initial_capture_does_not_invent_zero(tmp_path, kind, how):
    opts = dict(stop_before="P01") if how == "stop" else dict(fault="initial-on", fault_point="P01")
    w, source, cap, _, _, result = run(tmp_path, kind, **opts)
    assert result["zero_mean_W"] is None and result["zero_samples"] == 0
    assert result["completed_points"] == 0
    w.publish(source, tmp_path / "empty-report", plots=False)
    assert "0 source-off samples" in (tmp_path / "empty-report/report.html").read_text()
    if how == "initial-on":
        assert cap["final_state"]["rf_state"] == "on"


def test_observed_voltage_not_request_and_restoration_failure_coverage(tmp_path):
    _, _, _, _, _, result = run(
        tmp_path, "WF-06", scenario="observed-offset", fault="restore-failure", fault_point="P03"
    )
    assert result["completed_points"] == 3 and result["full_point_coverage"]
    assert result["execution"] == "failed" and result["acceptance"] == "NOT EVALUATED"
    assert float(result["secant_W_per_V"]) == pytest.approx(0.7 / 2.03)
    assert result["restoration"]["status"] == "failed"


def test_repeated_anchor_order_preserved(tmp_path):
    result = run(tmp_path, "WF-05", scenario="repeated-anchor")[-1]
    assert [row["frequency_Hz"] for row in result["points"]] == [
        1800000,
        3500000,
        7000000,
        14000000,
        1800000,
    ]
    assert D(result["points"][-1]["measured_W"]) == D("4.9")


@pytest.mark.parametrize(
    "scenario", ("missing-factor", "missing-loss", "missing-target", "factor-mismatch")
)
def test_missing_corrections_and_factor_fault_are_not_substituted(tmp_path, scenario):
    _, source, cap, _, _, result = run(tmp_path, "WF-05", scenario=scenario)
    row = result["points"][1]
    if scenario in ("missing-factor", "missing-loss"):
        assert row["measured_W"] is None
    if scenario == "missing-target":
        assert row["target_W"] is None and row["error_percent"] is None
    if scenario == "factor-mismatch":
        assert cap["status"] == "failed" and row["valid_samples"] == 0
        child, stages, _ = tx.load(source / "points/P02")
        assert not stages and child["meter_preparation"]["status"] == "failed"
        assert not child["final_state"]["owned_rf"]


def reseal(source):
    (source / "artifacts.json").unlink()
    cap = json.loads((source / "workflow.json").read_bytes())
    _seal(source, dict(schema=s.SCHEMA, mode="synthetic", run_id=cap["run_id"]))


@pytest.mark.parametrize(
    "mutation",
    (
        "derived-row",
        "projection",
        "order",
        "condition",
        "context",
        "state-reset",
        "hidden-child",
        "wrong-mode",
    ),
)
def test_controlled_import_rejects_resealed_inconsistency(tmp_path, mutation):
    w, source, _, _, _, _ = run(tmp_path, "WF-04")
    if mutation == "derived-row":
        path = source / "samples.csv"
        path.write_text(path.read_text().replace("0.005", "0.006", 1))
    elif mutation in ("projection", "order", "condition", "wrong-mode", "hidden-child"):
        path = source / "workflow.json"
        data = json.loads(path.read_bytes())
        if mutation == "projection":
            data["points"][0]["source_off_ack"] = False
        elif mutation == "order":
            data["children"].reverse()
        elif mutation == "condition":
            data["plan"]["points"][0]["setting"] = "OTHER"
        elif mutation == "wrong-mode":
            data["mode"] = "physical"
        else:
            (source / "points/P04").mkdir()
            (source / "points/P04/extra.json").write_text("{}")
        path.write_bytes(r.encoded(data))
    else:
        path = source / "points/P02/workflow.json"
        data = json.loads(path.read_bytes())
        if mutation == "context":
            data["parent_context"]["run_id"] = str(s.uuid.uuid4())
        else:
            data["initial_hardware"]["setting"] = "Initial state (synthetic)"
        path.write_bytes(r.encoded(data))
        # Preserve child's internal inventory so rejection tests semantic joins too.
        child_inv = path.parent / "artifacts.json"
        child_inv.unlink()
        _seal(
            path.parent,
            dict(
                schema="hp437b.external-transmitter-inventory.v1",
                mode="synthetic",
                run_id=data["run_id"],
            ),
        )
    reseal(source)
    with pytest.raises((ValueError, KeyError)):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
def test_bad_plan_and_fault_rejected_before_output(tmp_path, kind):
    plan = s.module(kind).default_plan()
    plan["points"][0]["point_id"] = "OTHER"
    with pytest.raises(ValueError):
        s.module(kind).controlled(tmp_path / "absent", plan=plan)
    assert not (tmp_path / "absent").exists()
    with pytest.raises(ValueError):
        s.module(kind).controlled(tmp_path / "absent", fault_point="P99")
    assert not (tmp_path / "absent").exists()


def test_publish_failure_preserves_native_evidence(tmp_path, monkeypatch):
    w, source, _, _, _, _ = run(tmp_path, "WF-04")
    before = snapshot(source)
    original = w._seal

    def fail(*args):
        raise OSError("Synthetic report storage failure")

    monkeypatch.setattr(w, "_seal", fail)
    with pytest.raises(OSError):
        w.publish(source, tmp_path / "failed", plots=False)
    assert snapshot(source) == before and not (tmp_path / "failed/artifacts.json").exists()
    monkeypatch.setattr(w, "_seal", original)
    w.publish(source, tmp_path / "retry-report", plots=False)
    assert snapshot(source) == before


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
def test_new_cli_and_legacy_reader(tmp_path, kind):
    w = s.module(kind)
    assert (
        w.main(
            [
                "controlled",
                "--output",
                str(tmp_path / "controlled"),
                "--report-output",
                str(tmp_path / "report"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        w.main(
            [
                "report",
                "--bundle",
                str(tmp_path / "controlled"),
                "--output",
                str(tmp_path / "rereport"),
                "--no-plots",
            ]
        )
        == 0
    )
    w.simulate(tmp_path / "legacy")
    cap, _, _ = w.load(tmp_path / "legacy")
    assert cap["schema"] == w.SCHEMA


@pytest.mark.parametrize("kind", ("WF-04", "WF-05", "WF-06"))
def test_optional_plots(tmp_path, kind):
    pytest.importorskip("matplotlib")
    w, source, _, _, _, _ = run(tmp_path, kind)
    w.publish(source, tmp_path / "plot")
    assert list((tmp_path / "plot").glob("*.png")) and list((tmp_path / "plot").glob("*.svg"))
