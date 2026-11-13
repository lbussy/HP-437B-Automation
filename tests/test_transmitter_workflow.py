"""DUT-CTRL-01 logger integration, saved-control replay, and report evidence."""

import copy
import html
import json
from decimal import Decimal as D

import pytest

from hp437b import dut_control as c
from hp437b import dut_simulation as f
from hp437b import provenance as p
from hp437b import reporting as r
from hp437b import transmitter_workflow as w
from hp437b.workflow_report import _seal


def limits(error="5", target="5"):
    return dict(
        source="Fictional DUT specification r1",
        target_W=target,
        max_abs_error_percent=error,
        min_samples=30,
        max_gap_s="1",
        decision_rule="inclusive-no-guard-band",
    )


def run(tmp_path, scenario="nominal", **kwargs):
    path = tmp_path / "capture"
    w.simulate(path, scenario=scenario, **kwargs)
    record, stages, bundle = w.load(path)
    return path, record, stages, bundle, w.analyze(record, stages)


@pytest.mark.parametrize("scenario", f.SCENARIOS)
def test_all_scenarios(tmp_path, scenario):
    source, record, stages, bundle, result = run(tmp_path, scenario)
    successful = scenario in ("nominal", "low-output", "missing-loss", "sensor-plane")
    assert record["status"] == (
        "completed" if successful else "interrupted" if scenario == "cancel" else "failed"
    )
    assert (
        result["source_kind"] == "external_transmitter" and result["acceptance"] == "NOT EVALUATED"
    )
    assert result["requested_samples"] == 30
    assert record["final_state"]["power_ref_controlled"] is False
    meter = bundle.json("meter-trace.json")
    assert not any(event.get("raw_hex") in (b"OC0".hex(), b"OC1".hex()) for event in meter)
    controls = bundle.json("controls.json")
    off = [
        event
        for event in controls["events"]
        if event["operation"] == "set_rf" and event["request"].get("on") is False
    ]
    assert len(off) <= 1
    if scenario in ("meter-timeout", "meter-malformed"):
        assert record["final_state"]["rf_state"] == "unknown" and record["final_state"]["blocked"]
        assert controls["order"][-1] == "verify"
        assert stages["plateau"]["valid"] == 3 and stages["plateau"]["nonvalid"] == 1
        assert not any(
            event["stage"] == "plateau" and event.get("raw_hex") == b"TR3".hex() for event in meter
        )
    if scenario in ("identity-mismatch", "initial-on"):
        assert not stages and record["final_state"]["meter_local"] == "not_opened"
    if scenario == "source-still-on":
        assert record["final_state"]["rf_state"] == "on"
    if scenario in ("restore-mismatch", "restore-failure", "source-off-failure", "source-still-on"):
        assert result["valid_samples"] == 30 and not record["final_state"]["supply_restored"]
    if scenario in ("instrument-error", "sensor-overrange", "cancel"):
        assert (
            record["final_state"]["supply_restored"] and record["final_state"]["rf_state"] == "off"
        )
    provenance = w.provenance(record, bundle)
    p.verify(provenance, source)
    assert provenance["dut"]["kind"] == "external_device"
    before = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    report = tmp_path / "report"
    assert w.publish(source, report, plots=False) == result
    assert before == {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    sheet = (report / "report.html").read_text()
    assert "RF Output Power Test" in sheet and "SYNTHETIC" in sheet and "Pre-RF zero:" in sheet
    assert sheet.index("Equipment:") < sheet.index("Report Harness:") < sheet.index("Record:")
    assert "Transmitter:" in html.unescape((report / "report.md").read_text())
    assert (report / "artifacts.json").exists()


def test_real_logger_and_corrected_power_oracle(tmp_path):
    _, record, stages, bundle, result = run(tmp_path, criteria=limits("0"))
    assert [stages[stage]["valid"] for stage in w.STAGES] == [3, 20, 30, 3]
    assert sum(stage["valid"] for stage in stages.values()) == 56
    assert D(result["sensor_mean_W"]) == D(".005") and D(result["measured_W"]) == 5
    assert D(result["zero_mean_W"]) == D("-2e-8") and D(result["error_percent"]) == 0
    assert result["acceptance"] == "PASS"
    session = bundle.json("stages/plateau.csv.session.json")
    assert session["instrument_cleanup"]["sequence"] == "TR3 then USB488 GTL"
    assert session["instrument"]["serial"] == "SYNTHETIC-DUT01"
    assert (
        record["final_state"]["observed_V"] == "12"
        and record["final_state"]["current_limit_ack_A"] == "1.5"
    )


def test_low_output_thresholds(tmp_path):
    _, record, stages, _, result = run(tmp_path, "low-output", criteria=limits("4"))
    assert D(result["measured_W"]) == D("4.8") and D(result["error_percent"]) == -4
    assert result["acceptance"] == "PASS"
    record["criteria"]["max_abs_error_percent"] = "3.9"
    assert w.analyze(record, stages)["acceptance"] == "FAIL"


@pytest.mark.parametrize(
    "scenario",
    (
        "restore-failure",
        "source-off-failure",
        "meter-timeout",
        "cancel",
        "frequency-mismatch",
        "sensor-overrange",
    ),
)
def test_incomplete_control_or_capture_cannot_pass(tmp_path, scenario):
    assert run(tmp_path, scenario, criteria=limits("100"))[-1]["acceptance"] == "NOT EVALUATED"


def test_missing_loss_and_sensor_plane(tmp_path):
    _, record, stages, _, result = run(tmp_path, "missing-loss", criteria=limits())
    assert result["measured_W"] is None and D(result["sensor_mean_W"]) == D(".005")
    record["plan"]["measurement_plane"] = "sensor_input"
    record["criteria"] = limits("0", ".005")
    assert w.analyze(record, stages)["acceptance"] == "PASS"


def test_inconsistent_upstream_correction_cannot_pass_bound(tmp_path):
    plan = c.default_plan()
    plan["fixture"]["loss_dB"] = "40"
    result = run(tmp_path, plan=plan, criteria=limits("100", "50"))[-1]
    assert result["acceptance"] == "NOT EVALUATED"


@pytest.mark.parametrize(
    "mutation",
    (
        "max-power",
        "sensor-limit",
        "fixture-rating",
        "minimum-loss",
        "correction",
        "voltage",
        "restore",
        "current",
        "identity",
        "reserved-id",
        "deadline",
        "on-budget",
        "frequency",
    ),
)
def test_bad_plan_before_capture_allocation(tmp_path, mutation):
    plan = copy.deepcopy(c.default_plan())
    if mutation == "max-power":
        plan["max_RF_W"] = "0"
    elif mutation == "sensor-limit":
        plan["sensor_limit_W"] = ".001"
    elif mutation == "fixture-rating":
        plan["fixture"]["input_limit_W"] = "1"
    elif mutation == "minimum-loss":
        plan["fixture"]["minimum_loss_dB"] = "0"
    elif mutation == "correction":
        plan["fixture"]["loss_dB"] = "20"
    elif mutation == "voltage":
        plan["supply"]["condition_V"] = "15"
    elif mutation == "restore":
        plan["supply"]["restore_V"] = "0"
    elif mutation == "current":
        plan["supply"]["current_limit_A"] = "NaN"
    elif mutation == "identity":
        plan["assets"]["supply"]["asset_id"] = plan["assets"]["transmitter"]["asset_id"]
    elif mutation == "reserved-id":
        plan["assets"]["transmitter"]["asset_id"] = "synthetic:dut01:meter"
    elif mutation == "deadline":
        plan["timing"]["operation_s"] = True
    elif mutation == "on-budget":
        plan["timing"]["max_RF_on_s"] = 5
    else:
        plan["frequency_Hz"] = True
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", plan=plan)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("mutation", ("target", "error", "samples", "gap", "rule"))
def test_bad_criteria_before_capture(tmp_path, mutation):
    criteria = limits()
    key, value = {
        "target": ("target_W", "0"),
        "error": ("max_abs_error_percent", "-1"),
        "samples": ("min_samples", True),
        "gap": ("max_gap_s", "0"),
        "rule": ("decision_rule", "invented"),
    }[mutation]
    criteria[key] = value
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", criteria=criteria)
    assert not (tmp_path / "absent").exists()


def reseal(source):
    (source / "artifacts.json").unlink()
    record = json.loads((source / "workflow.json").read_bytes())
    initial = {
        **record,
        "finished_utc": None,
        "status": "running",
        "outcome": None,
        "stages": {stage: dict(status="skipped", reason="Not reached") for stage in w.STAGES},
        "final_state": None,
    }
    (source / "starting.json").write_bytes(r.encoded(initial))
    _seal(
        source,
        dict(
            schema="hp437b.external-transmitter-inventory.v1",
            mode="synthetic",
            run_id=record["run_id"],
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "hash",
        "context",
        "units",
        "raw-value",
        "session-id",
        "control-request",
        "control-reply",
        "late-control",
        "extra-off",
        "power-ref",
        "final-type",
        "wrong-source",
        "source-kind",
        "trace-frame",
    ),
)
def test_corrupt_or_resealed_evidence_rejected(tmp_path, mutation):
    source, *_ = run(tmp_path)
    if mutation == "hash":
        with (source / "stages/plateau.csv").open("a") as handle:
            handle.write("garbage")
    elif mutation in ("context", "units", "session-id"):
        path = source / "stages/plateau.csv.session.json"
        data = json.loads(path.read_bytes())
        if mutation == "context":
            data["context"]["workflow_run_id"] = str(w.uuid.uuid4())
        elif mutation == "units":
            data["settings"]["unit"] = "dBm"
        else:
            data["session_id"] = str(w.uuid.uuid4())
        path.write_bytes(r.encoded(data))
    elif mutation == "raw-value":
        path = source / "stages/plateau.csv"
        path.write_text(path.read_text().replace("0.005", "0.006", 1))
    elif mutation in ("control-request", "control-reply", "late-control", "extra-off"):
        path = source / "controls.json"
        data = json.loads(path.read_bytes())
        if mutation == "control-request":
            event = next(event for event in data["events"] if event["operation"] == "set_rf")
            event["request"]["on"] = 1
        elif mutation == "control-reply":
            data["events"][0]["reply"]["serial"] = "OTHER"
        elif mutation == "late-control":
            data["events"][0]["end_s"] = 99
        else:
            data["events"].append(copy.deepcopy(data["events"][-1]))
        path.write_bytes(r.encoded(data))
    elif mutation in ("power-ref", "trace-frame"):
        path = source / "meter-trace.json"
        data = json.loads(path.read_bytes())
        next(
            event
            for event in data
            if event["operation"] == ("write" if mutation == "power-ref" else "read")
        )["raw_hex"] = (b"OC1" if mutation == "power-ref" else b"OTHER").hex()
        path.write_bytes(r.encoded(data))
    else:
        path = source / "workflow.json"
        data = json.loads(path.read_bytes())
        if mutation == "final-type":
            data["final_state"]["supply_restored"] = 1
        elif mutation == "wrong-source":
            data["plan"]["assets"]["transmitter"]["serial"] = "OTHER"
        else:
            data["workflow_id"] = "power-reference-v1"
        path.write_bytes(r.encoded(data))
    if mutation != "hash":
        reseal(source)
    with pytest.raises((ValueError, KeyError)):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()


def test_publication_failure_no_control_or_reacquisition(tmp_path, monkeypatch):
    source, *_ = run(tmp_path)
    before = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    original = w._seal

    def fail(*args):
        raise OSError("Synthetic report storage failure")

    monkeypatch.setattr(w, "_seal", fail)
    with pytest.raises(OSError):
        w.publish(source, tmp_path / "failed", plots=False)
    assert (tmp_path / "failed/failure.json").exists() and not (
        tmp_path / "failed/artifacts.json"
    ).exists()
    assert before == {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(w, "_seal", original)
    w.publish(source, tmp_path / "fresh", plots=False)


def test_cli_paths_and_escaped_operator(tmp_path):
    path = tmp_path / "capture"
    assert (
        w.main(
            [
                "synthetic",
                "--output",
                str(path),
                "--operator",
                "<Operator & Name>",
                "--report-output",
                str(tmp_path / "report"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert "&lt;Operator &amp; Name&gt;" in (tmp_path / "report/report.html").read_text()
    assert w.main(["report", "--bundle", str(path), "--output", str(path), "--no-plots"]) == 2
    assert (
        w.main(
            [
                "synthetic",
                "--output",
                str(tmp_path / "failure"),
                "--scenario",
                "source-off-failure",
                "--no-plots",
            ]
        )
        == 1
    )
    for target in (path, path / "nested", path.parent):
        with pytest.raises(ValueError):
            w.publish(path, target, plots=False)
    (path / "stages/plateau.csv").unlink()
    (path / "stages/plateau.csv").symlink_to(tmp_path / "outside")
    with pytest.raises((ValueError, OSError)):
        w.load(path)


@pytest.mark.parametrize("scenario", ("nominal", "initial-on", "meter-timeout"))
def test_optional_plots(tmp_path, scenario):
    pytest.importorskip("matplotlib")
    source, *_ = run(tmp_path, scenario)
    report = tmp_path / "plot"
    w.publish(source, report)
    assert (report / "transmitter-power.png").read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (report / "transmitter-power.svg").read_text()


def test_capture_reservation_failure_closes_and_cleans_without_success_inventory(
    tmp_path, monkeypatch
):
    original = w.collect

    def fail_during_active_stage(instrument, *args, **kwargs):
        if instrument.transport.bench.stage == "settling":
            raise OSError("Synthetic CSV reservation failure")
        return original(instrument, *args, **kwargs)

    monkeypatch.setattr(w, "collect", fail_during_active_stage)
    source = tmp_path / "unsealed"
    with pytest.raises(OSError):
        w.simulate(source)
    record = json.loads((source / "workflow.json").read_bytes())
    assert record["status"] == "failed"
    assert record["final_state"]["rf_state"] == "off" and record["final_state"]["supply_restored"]
    assert not (source / "artifacts.json").exists()
    trace = json.loads((source / "meter-trace.json").read_bytes())
    assert sum(event["operation"] == "session_open" for event in trace) == sum(
        event["operation"] == "session_close" for event in trace
    )


def test_forged_failure_cannot_mask_saved_stage_validation_error(tmp_path):
    from datetime import timedelta

    source, record, *_ = run(tmp_path)
    bench = f.Bench(record["plan"], "nominal")
    controls = c.Controls(
        record["plan"],
        f.FakeTransmitter(bench),
        f.FakeSupply(bench),
        f.FakeObserver(bench),
        clock=lambda: bench.now,
    )
    bench.controls = controls

    def invalid_stage(stage):
        raise p.ProvenanceError("Missing/falsely skipped stage")

    outcome = c.execute(controls, invalid_stage)
    for path in (source / "stages").iterdir():
        path.unlink()
    record.update(
        status="failed",
        outcome=outcome,
        stages={stage: dict(status="skipped", reason="Not reached") for stage in w.STAGES},
        finished_utc=(
            r.timestamp(record["started_utc"]) + timedelta(seconds=bench.now)
        ).isoformat(),
        final_state={
            **controls.summary(),
            "meter_local": "not_opened",
            "power_ref_controlled": False,
        },
    )
    (source / "workflow.json").write_bytes(r.encoded(record))
    (source / "controls.json").write_bytes(
        r.encoded(
            dict(
                events=controls.events,
                order=controls.order,
                phases=controls.phases,
                summary=controls.summary(),
            )
        )
    )
    (source / "meter-trace.json").write_bytes(r.encoded([]))
    reseal(source)
    with pytest.raises(ValueError):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()
