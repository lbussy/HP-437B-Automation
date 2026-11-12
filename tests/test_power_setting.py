"""WF-04 independent arithmetic, bounded simulation, and evidence integrity."""

import copy
import json
from decimal import Decimal as D

import pytest

from hp437b import power_setting as w
from hp437b import provenance as p
from hp437b import reporting as r
from hp437b.workflow_report import _seal


def run(tmp_path, scenario="nominal", **kwargs):
    source = tmp_path / "capture"
    w.simulate(source, scenario=scenario, **kwargs)
    capture, rows, bundle = w.load(source)
    return source, capture, rows, bundle, w.analyze(capture, rows)


def criteria(limit="5"):
    return dict(
        source="Fictional DUT specification r1",
        decision_rule="inclusive-no-guard-band",
        max_abs_error_percent=limit,
        min_samples_per_point=30,
        max_gap_s="1",
    )


@pytest.mark.parametrize("scenario", w.SCENARIOS)
def test_scenarios(tmp_path, scenario):
    source, capture, rows, bundle, result = run(tmp_path, scenario)
    assert result["requested_points"] == 3
    assert result["zero_mean_W"] == "-2E-8"
    assert result["acceptance"] == "NOT EVALUATED"
    assert capture["final_state"]["meter_reference_off"] is True
    assert capture["final_state"]["hardware_opened"] is False
    assert len(rows) <= 156
    assert result["points"][0]["valid_samples"] == 30
    p.verify(w.provenance(capture, bundle), source)
    failed = scenario in (
        "timeout",
        "malformed",
        "instrument-error",
        "source-off-failure",
        "ack-mismatch",
    )
    interrupted = scenario in ("cancel", "missing-point")
    assert result["execution"] == (
        "failed" if failed else "interrupted" if interrupted else "completed"
    )
    assert result["completed_points"] == (1 if failed or interrupted else 3)
    events = bundle.json("trace.json")
    if scenario in ("timeout", "malformed"):
        assert events[-1]["operation"] == "communication_uncertain"
        assert capture["final_state"]["external_source_off"] is None
    if scenario == "source-off-failure":
        assert events[-1]["operation"] == "source_off_attempt"
        assert capture["final_state"]["external_source_off"] is None
    if failed or interrupted:
        assert result["points"][2]["status"] == "skipped"
    report = tmp_path / "report"
    assert w.publish(source, report, plots=False) == result
    assert (report / "artifacts.json").exists()
    sheet = (report / "report.html").read_text()
    assert "RF Output Power Test" in sheet and "SYNTHETIC" in sheet
    assert "Pre-RF zero:" in sheet
    assert sheet.index("Equipment:") < sheet.index("Report Harness:") < sheet.index("Record:")
    assert sheet.count("Report Harness:") == 1
    markdown = (report / "report.md").read_text()
    assert "Pre-RF zero:" in markdown and "Operator:" in markdown and "Final source:" in markdown
    assert "Report Harness:" in markdown and "Record:" in markdown


def test_catalogue_oracle(tmp_path):
    _, _, _, _, result = run(tmp_path, "compressed", criteria=criteria())
    assert [D(row["measured_W"]) for row in result["points"]] == [D(1), D("4.8"), D("9.5")]
    assert [D(row["error_percent"]) for row in result["points"]] == [D(0), D(-4), D(-5)]
    assert float(result["points"][2]["error_dB"]) == pytest.approx(-0.2227639471)
    assert result["acceptance"] == "PASS"  # inclusive -5% boundary


def test_fails_limit(tmp_path):
    assert run(tmp_path, "compressed", criteria=criteria("4"))[-1]["acceptance"] == "FAIL"


@pytest.mark.parametrize(
    "scenario", ("missing-loss", "missing-target", "timeout", "source-off-failure", "zero-output")
)
def test_cannot_pass_incomplete_or_ineligible(tmp_path, scenario):
    result = run(tmp_path, scenario, criteria=criteria("100"))[-1]
    assert result["acceptance"] == "NOT EVALUATED"
    assert result["points"][1]["reason"]


def test_missing_loss_no_truth_leak(tmp_path):
    result = run(tmp_path, "missing-loss")[-1]["points"][1]
    assert D(result["sensor_mean_W"]) == D(".005")
    assert result["DUT_mean_W"] is None and result["measured_W"] is None
    assert result["error_percent"] is None


def test_sensor_plane_never_applies_fixture_to_comparison(tmp_path):
    row = run(tmp_path, "sensor-plane")[-1]["points"][1]
    assert D(row["measured_W"]) == D(".005")
    assert D(row["DUT_mean_W"]) == 5
    assert D(row["error_percent"]) == 0


def test_zero_output_db_unavailable(tmp_path):
    row = run(tmp_path, "zero-output")[-1]["points"][1]
    assert D(row["error_percent"]) == -100
    assert row["error_dB"] is None and row["dB_unavailable_reason"]


def test_targets_are_not_inferred_from_labels(tmp_path):
    row = run(tmp_path, "missing-target")[-1]["points"][1]
    assert D(row["measured_W"]) == 5
    assert row["error_percent"] is None and row["target_W"] is None


def test_nonmonotonic_preserves_order(tmp_path):
    result = run(tmp_path, "nonmonotonic")[-1]
    assert [row["setting"] for row in result["points"]] == ["Low", "Medium", "High"]
    assert [D(row["measured_W"]) for row in result["points"]] == [1, 5, 4]


@pytest.mark.parametrize(
    "mutation", ("too-many", "id", "loss", "power", "frequency", "plane", "target", "html")
)
def test_invalid_plan_precedes_output(tmp_path, mutation):
    plan = copy.deepcopy(w.default_plan())
    if mutation == "too-many":
        plan["points"] *= 2
    elif mutation == "id":
        plan["points"][1]["point_id"] = "P01"
    elif mutation == "loss":
        plan["points"][0]["fixture_loss_dB"] = "NaN"
    elif mutation == "power":
        plan["points"][0]["simulation_loss_dB"] = "0"
    elif mutation == "frequency":
        plan["frequency_Hz"] = True
    elif mutation == "plane":
        plan["measurement_plane"] = "unknown"
    elif mutation == "target":
        plan["points"][0]["target_W"] = "0"
    else:
        plan["name"] = "two\nlines"
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", plan=plan)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize(
    "key,value",
    (
        ("max_abs_error_percent", "-1"),
        ("min_samples_per_point", True),
        ("max_gap_s", "0"),
        ("decision_rule", "invented"),
    ),
)
def test_invalid_criteria(tmp_path, key, value):
    limits = criteria()
    limits[key] = value
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", criteria=limits)
    assert not (tmp_path / "absent").exists()


def reseal(source):
    (source / "artifacts.json").unlink()
    capture = json.loads((source / "workflow.json").read_bytes())
    (source / "starting.json").write_bytes(
        r.encoded(
            {
                **capture,
                "status": "running",
                "finished_utc": None,
                "points": [],
                "final_state": None,
            }
        )
    )
    _seal(
        source,
        {
            "schema": "hp437b.power-setting-inventory.v1",
            "mode": "synthetic",
            "run_id": capture["run_id"],
        },
    )


@pytest.mark.parametrize(
    "mutation", ("hash", "cross-run", "units", "order", "ack", "trace", "final", "mode")
)
def test_corruption_and_resealed_semantic_forgery(tmp_path, mutation):
    source, *_ = run(tmp_path)
    if mutation in ("hash", "cross-run", "units", "order"):
        path = source / "samples.csv"
        data = path.read_text()
        if mutation == "hash":
            data += "garbage"
        elif mutation == "cross-run":
            data = data.replace(data.splitlines()[1].split(",")[0], str(w.uuid.uuid4()), 1)
        elif mutation == "units":
            data = data.replace("value_W", "value_dBm", 1)
        else:
            data = data.replace(",P01,settling,", ",P02,settling,", 1)
        path.write_text(data)
    else:
        path = source / ("trace.json" if mutation == "trace" else "workflow.json")
        data = json.loads(path.read_bytes())
        if mutation == "trace":
            data[1]["setting"] = "Wrong setting"
        elif mutation == "ack":
            data["points"][1]["setting_ack"] = "Wrong setting"
        elif mutation == "final":
            data["final_state"]["external_source_off"] = None
        else:
            data["mode"] = "physical"
        path.write_bytes(r.encoded(data))
    if mutation != "hash":
        reseal(source)
    with pytest.raises((ValueError, KeyError)):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()


def test_report_failure_preserves_capture_and_can_retry(tmp_path, monkeypatch):
    source, *_ = run(tmp_path)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    original = w._seal

    def fail(*args):
        raise OSError("Simulated disk failure")

    monkeypatch.setattr(w, "_seal", fail)
    with pytest.raises(OSError):
        w.publish(source, tmp_path / "failed-report", plots=False)
    assert not (tmp_path / "failed-report/artifacts.json").exists()
    assert (tmp_path / "failed-report/failure.json").exists()
    assert before == {path.name: path.read_bytes() for path in source.iterdir()}
    monkeypatch.setattr(w, "_seal", original)
    w.publish(source, tmp_path / "fresh-report", plots=False)


def test_path_guards(tmp_path):
    source, *_ = run(tmp_path)
    for target in (source, source / "report", source.parent):
        with pytest.raises(ValueError):
            w.publish(source, target, plots=False)
    (source / "samples.csv").unlink()
    (source / "samples.csv").symlink_to(tmp_path / "outside")
    with pytest.raises((ValueError, OSError)):
        w.load(source)


def test_cli_and_custom_plan(tmp_path):
    plan = w.default_plan()
    plan["name"] = "<Fictional & source>"
    plan["points"] = [plan["points"][0]]
    filename = tmp_path / "plan.json"
    filename.write_bytes(r.encoded(plan))
    source, report = tmp_path / "one", tmp_path / "report"
    assert (
        w.main(
            [
                "synthetic",
                "--plan",
                str(filename),
                "--output",
                str(source),
                "--report-output",
                str(report),
                "--operator",
                "Bench operator",
                "--no-plots",
            ]
        )
        == 0
    )
    assert "&lt;Fictional &amp; source&gt;" in (report / "report.html").read_text()
    assert "Bench operator" in (report / "report.html").read_text()
    assert w.main(["report", "--bundle", str(source), "--output", str(report), "--no-plots"]) == 2
    assert (
        w.main(
            [
                "synthetic",
                "--scenario",
                "cancel",
                "--output",
                str(tmp_path / "cancel"),
                "--no-plots",
            ]
        )
        == 1
    )


def test_optional_plots(tmp_path):
    pytest.importorskip("matplotlib")
    source, *_ = run(tmp_path)
    report = tmp_path / "plotted"
    w.publish(source, report)
    assert (report / "power-setting.png").read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (report / "power-setting.svg").read_text()


def test_per_point_tolerances_and_unknown_point(tmp_path):
    limits = criteria("5")
    limits["point_limits_percent"] = {"P03": "4"}
    result = run(tmp_path, "compressed", criteria=limits)[-1]
    assert result["acceptance"] == "FAIL"
    assert [point["acceptance"] for point in result["points"]] == ["PASS", "PASS", "FAIL"]
    limits["point_limits_percent"] = {"P04": "4"}
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", criteria=limits)
    assert not (tmp_path / "absent").exists()


def test_five_ordered_points_and_repeated_anchor(tmp_path):
    plan = w.default_plan()
    plan["points"].extend([copy.deepcopy(plan["points"][0]), copy.deepcopy(plan["points"][1])])
    for i, point in enumerate(plan["points"], 1):
        point["point_id"] = f"P{i:02d}"
    _, capture, rows, _, result = run(tmp_path, plan=plan)
    assert len(rows) == 256
    assert result["requested_points"] == result["completed_points"] == 5
    assert result["points"][3]["setting"] == "Low"
    assert capture["plan"]["points"] == plan["points"]


def test_analysis_does_not_consult_simulator_truth(tmp_path):
    _, capture, rows, _, original = run(tmp_path)
    capture["plan"]["points"][1]["synthetic_DUT_W"] = "8000"
    capture["plan"]["points"][1]["simulation_loss_dB"] = "99"
    assert w.analyze(capture, rows) == original
