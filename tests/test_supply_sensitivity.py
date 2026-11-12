"""WF-06 voltage bounds, observed-point arithmetic, restoration, and reporting."""

import copy
import html
import json
from decimal import Decimal as D

import pytest

from hp437b import provenance as p
from hp437b import reporting as r
from hp437b import supply_sensitivity as w
from hp437b.workflow_report import _seal


def run(tmp_path, scenario="nominal", **kwargs):
    source = tmp_path / "capture"
    w.simulate(source, scenario=scenario, **kwargs)
    capture, rows, bundle = w.load(source)
    return source, capture, rows, bundle, w.analyze(capture, rows)


def limits(**extra):
    return dict(
        source="Fictional transmitter specification r1",
        decision_rule="inclusive-no-guard-band",
        min_samples_per_point=30,
        max_gap_s="1",
        **extra,
    )


@pytest.mark.parametrize("scenario", w.SCENARIOS)
def test_scenarios(tmp_path, scenario):
    source, capture, rows, bundle, result = run(tmp_path, scenario)
    interrupted = scenario in ("cancel", "missing-point")
    failed = scenario in (
        "missing-readback",
        "unsafe-readback",
        "timeout",
        "malformed",
        "instrument-error",
        "source-off-failure",
        "supply-control-failure",
        "current-limit-mismatch",
        "restore-failure",
        "restore-mismatch",
        "restore-unverified",
    )
    assert result["execution"] == (
        "failed" if failed else "interrupted" if interrupted else "completed"
    )
    count = 5 if scenario == "repeated-anchor" else 3
    assert result["requested_points"] == count
    assert result["zero_mean_W"] == "-2E-8" and result["acceptance"] == "NOT EVALUATED"
    assert len(rows) <= 256
    assert capture["final_state"]["hardware_opened"] is False
    assert capture["final_state"]["meter_reference_off"] is True
    if scenario.startswith("restore-"):
        assert result["completed_points"] == 3 and result["full_point_coverage"] is True
        assert result["restoration"]["status"] == "failed" and not result["full_coverage"]
    elif scenario == "current-limit-mismatch":
        assert result["completed_points"] == 0
        assert all(row["status"] == "skipped" for row in result["points"])
    else:
        assert result["completed_points"] == (1 if failed or interrupted else count)
    trace = bundle.json("trace.json")
    if scenario in ("timeout", "malformed"):
        assert trace[-1]["operation"] == "communication_uncertain"
        assert capture["final_state"]["external_source_off"] is None
    if scenario in (
        "timeout",
        "malformed",
        "source-off-failure",
        "supply-control-failure",
        "current-limit-mismatch",
    ):
        assert not result["restoration"]["attempted"]
        assert result["restoration"]["status"] == "unknown"
    else:
        assert sum(event["operation"] == "restore_attempt" for event in trace) == 1
    if scenario in ("missing-readback", "unsafe-readback", "supply-control-failure"):
        assert not capture["points"][1]["source_on_ack"]
    p.verify(w.provenance(capture, bundle), source)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    report = tmp_path / "report"
    assert w.publish(source, report, plots=False) == result
    assert before == {path.name: path.read_bytes() for path in source.iterdir()}
    sheet = (report / "report.html").read_text()
    assert "RF Output Power Test" in sheet and "SYNTHETIC" in sheet
    assert "Supply-voltage sensitivity" in sheet and "Pre-RF zero:" in sheet
    assert "Supply restoration:" in sheet and "Observed V" in sheet
    if result["execution"] != "completed":
        assert "Run limitation:" in sheet
    assert sheet.index("Equipment:") < sheet.index("Report Harness:") < sheet.index("Record:")
    assert "Operator:" in html.unescape((report / "report.md").read_text())
    assert (report / "artifacts.json").exists()


def test_catalogue_oracle_and_inclusive_limits(tmp_path):
    result = run(
        tmp_path,
        "droop",
        criteria=limits(max_abs_change_percent="10", max_abs_secant_W_per_V=".35"),
    )[-1]
    assert [D(row["measured_W"]) for row in result["points"]] == [D("4.5"), D(5), D("5.2")]
    assert [D(row["change_percent"]) for row in result["points"]] == [-10, 0, 4]
    assert D(result["secant_W_per_V"]) == D(".35")
    assert result["nominal_point_id"] == "P02" and D(result["nominal_mean_W"]) == 5
    assert result["secant_lower_point_id"] == "P01" and result["secant_upper_point_id"] == "P03"
    assert result["acceptance"] == "PASS"


def test_limit_failures_and_overrides(tmp_path):
    _, capture, rows, _, _ = run(
        tmp_path,
        "droop",
        criteria=limits(max_abs_change_percent="10", max_abs_secant_W_per_V=".34"),
    )
    assert w.analyze(capture, rows)["acceptance"] == "FAIL"
    capture["criteria"]["max_abs_secant_W_per_V"] = ".35"
    capture["criteria"]["point_limits_percent"] = {"P03": "3"}
    assert w.analyze(capture, rows)["acceptance"] == "FAIL"


def test_secant_uses_observed_not_requested_voltage(tmp_path):
    result = run(tmp_path, "observed-offset")[-1]
    assert float(result["secant_W_per_V"]) == pytest.approx(0.7 / 2.03)
    assert D(result["nominal_observed_V"]) == D("12.02")
    assert [D(row["change_percent"]) for row in result["points"]] == [-10, 0, 4]


def test_repeated_points_keep_history_and_first_endpoint(tmp_path):
    result = run(tmp_path, "repeated-anchor")[-1]
    assert [row["requested_V"] for row in result["points"]] == ["11", "12", "13", "12", "11"]
    assert D(result["points"][3]["change_percent"]) == -2
    assert D(result["points"][4]["change_percent"]) == -12
    assert D(result["secant_W_per_V"]) == D(".35")
    assert result["secant_lower_point_id"] == "P01"


def test_missing_nominal_is_not_inferred(tmp_path):
    result = run(tmp_path, "missing-nominal", criteria=limits(max_abs_change_percent="100"))[-1]
    assert result["nominal_point_id"] is None and result["nominal_mean_W"] is None
    assert all(row["change_percent"] is None for row in result["points"])
    assert result["acceptance"] == "NOT EVALUATED"


def test_secant_only_can_evaluate_without_nominal(tmp_path):
    result = run(tmp_path, "missing-nominal", criteria=limits(max_abs_secant_W_per_V="0"))[-1]
    assert result["acceptance"] == "PASS" and D(result["secant_W_per_V"]) == 0


def test_same_voltage_has_no_secant(tmp_path):
    result = run(tmp_path, "same-voltage", criteria=limits(max_abs_secant_W_per_V="100"))[-1]
    assert result["secant_W_per_V"] is None and result["secant_unavailable_reason"]
    assert result["acceptance"] == "NOT EVALUATED"


def test_zero_nominal_does_not_divide_by_zero(tmp_path):
    result = run(tmp_path, "zero-nominal", criteria=limits(max_abs_change_percent="100"))[-1]
    assert result["nominal_eligible"] is False
    assert all(row["change_percent"] is None for row in result["points"])
    assert result["acceptance"] == "NOT EVALUATED"


@pytest.mark.parametrize(
    "scenario",
    (
        "restore-failure",
        "restore-mismatch",
        "restore-unverified",
        "source-off-failure",
        "timeout",
        "cancel",
        "missing-point",
        "missing-readback",
        "current-limit-mismatch",
    ),
)
def test_failed_or_incomplete_run_cannot_pass(tmp_path, scenario):
    result = run(
        tmp_path,
        scenario,
        criteria=limits(max_abs_change_percent="100", max_abs_secant_W_per_V="100"),
    )[-1]
    assert result["acceptance"] == "NOT EVALUATED"


def test_sensor_plane_avoids_fixture_multiplication(tmp_path):
    result = run(tmp_path, "sensor-plane")[-1]
    assert [D(row["measured_W"]) for row in result["points"]] == [D(".0045"), D(".005"), D(".0052")]
    assert D(result["secant_W_per_V"]) == D(".00035")


def test_missing_loss_is_not_filled_from_model(tmp_path):
    result = run(tmp_path, "missing-loss")[-1]
    assert all(
        row["measured_W"] is None and row["sensor_mean_W"] is not None for row in result["points"]
    )
    assert result["secant_W_per_V"] is None


def test_sensor_plane_without_fixture_loss(tmp_path):
    plan = w.default_plan("sensor-plane")
    plan["fixture_loss_dB"] = plan["fixture_source"] = None
    result = run(tmp_path, plan=plan)[-1]
    assert D(result["secant_W_per_V"]) == D(".00035")


def test_no_model_truth_substitution(tmp_path):
    _, capture, rows, _, original = run(tmp_path)
    capture["plan"]["simulation_loss_dB"] = "99"
    for point in capture["plan"]["points"]:
        point["synthetic_DUT_W"] = "9999"
        point["synthetic_observed_V"] = "99"
    assert w.analyze(capture, rows) == original


@pytest.mark.parametrize(
    "mutation",
    (
        "low-request",
        "high-request",
        "bad-restore",
        "bad-nominal",
        "unknown-nominal",
        "wrong-nominal",
        "bad-envelope",
        "bad-current",
        "bad-tolerance",
        "bad-loss",
        "bad-source",
        "bad-frequency",
        "too-many",
        "bad-id",
        "nonfinite",
    ),
)
def test_invalid_plan_before_any_output_or_actor(tmp_path, mutation):
    plan = copy.deepcopy(w.default_plan())
    supply = plan["supply"]
    if mutation == "low-request":
        plan["points"][0]["requested_V"] = "9.99"
    elif mutation == "high-request":
        plan["points"][0]["requested_V"] = "14.01"
    elif mutation == "bad-restore":
        supply["restore_V"] = "15"
    elif mutation == "bad-nominal":
        supply["nominal_V"] = "9"
    elif mutation == "unknown-nominal":
        supply["nominal_point_id"] = "P05"
    elif mutation == "wrong-nominal":
        supply["nominal_point_id"] = "P01"
    elif mutation == "bad-envelope":
        supply["minimum_V"] = "15"
    elif mutation == "bad-current":
        supply["current_limit_A"] = "0"
    elif mutation == "bad-tolerance":
        supply["tolerance_V"] = "-1"
    elif mutation == "bad-loss":
        plan["fixture_loss_dB"] = "NaN"
    elif mutation == "bad-source":
        plan["fixture_source"] = None
    elif mutation == "bad-frequency":
        plan["frequency_Hz"] = True
    elif mutation == "too-many":
        plan["points"] *= 2
    elif mutation == "bad-id":
        plan["points"][1]["point_id"] = "P01"
    else:
        plan["points"][0]["requested_V"] = "Infinity"
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", plan=plan)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("mutation", ("no-limit", "negative", "count", "gap", "point", "rule"))
def test_bad_criteria_before_output(tmp_path, mutation):
    criteria = limits(max_abs_change_percent="10")
    if mutation == "no-limit":
        criteria.pop("max_abs_change_percent")
    elif mutation == "negative":
        criteria["max_abs_change_percent"] = "-1"
    elif mutation == "count":
        criteria["min_samples_per_point"] = True
    elif mutation == "gap":
        criteria["max_gap_s"] = "0"
    elif mutation == "point":
        criteria["point_limits_percent"] = {"P05": "1"}
    else:
        criteria["decision_rule"] = "invented"
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", criteria=criteria)
    assert not (tmp_path / "absent").exists()


def reseal(source):
    capture = json.loads((source / "workflow.json").read_bytes())
    (source / "starting.json").write_bytes(
        r.encoded(
            {
                **capture,
                "status": "running",
                "finished_utc": None,
                "setup": None,
                "restoration": None,
                "points": [],
                "final_state": None,
            }
        )
    )
    (source / "artifacts.json").unlink()
    _seal(
        source,
        dict(
            schema="hp437b.supply-sensitivity-inventory.v1",
            mode="synthetic",
            run_id=capture["run_id"],
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "hash",
        "units",
        "cross-run",
        "sequence",
        "current-limit",
        "readback",
        "command-ack",
        "trace",
        "restore",
        "mode",
        "final-type",
        "nominal-reference",
    ),
)
def test_hash_and_resealed_semantic_corruption(tmp_path, mutation):
    source, *_ = run(tmp_path)
    if mutation in ("hash", "units", "cross-run", "sequence"):
        path = source / "samples.csv"
        data = path.read_text()
        if mutation == "hash":
            data += "garbage"
        elif mutation == "units":
            data = data.replace("value_W", "value_dBm", 1)
        elif mutation == "cross-run":
            data = data.replace(data.splitlines()[1].split(",")[0], str(w.uuid.uuid4()), 1)
        else:
            data = data.replace(",P01,settling,", ",P02,settling,", 1)
        path.write_text(data)
    else:
        path = source / ("trace.json" if mutation == "trace" else "workflow.json")
        data = json.loads(path.read_bytes())
        if mutation == "current-limit":
            data["setup"]["current_limit_ack_A"] = "1"
        elif mutation == "readback":
            data["points"][1]["observed_V"] = None
        elif mutation == "command-ack":
            data["points"][1]["voltage_command_ack"] = False
        elif mutation == "trace":
            data.insert(-1, dict(data[-1]))
        elif mutation == "restore":
            data["restoration"]["observed_V"] = "11"
        elif mutation == "mode":
            data["mode"] = "physical"
        elif mutation == "final-type":
            data["final_state"]["supply_restored"] = 1
        else:
            data["plan"]["supply"]["nominal_point_id"] = "P01"
        path.write_bytes(r.encoded(data))
    if mutation != "hash":
        reseal(source)
    with pytest.raises((ValueError, KeyError)):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()


def test_storage_failure_and_reimport_preserve_source(tmp_path, monkeypatch):
    source, *_ = run(tmp_path, "droop")
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    original = w._seal

    def fail(*args):
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr(w, "_seal", fail)
    with pytest.raises(OSError):
        w.publish(source, tmp_path / "failed", plots=False)
    assert (tmp_path / "failed/failure.json").exists() and not (
        tmp_path / "failed/artifacts.json"
    ).exists()
    assert before == {path.name: path.read_bytes() for path in source.iterdir()}
    monkeypatch.setattr(w, "_seal", original)
    w.publish(source, tmp_path / "fresh", plots=False)


def test_paths_and_cli(tmp_path):
    source, *_ = run(tmp_path)
    for target in (source, source / "nested", source.parent):
        with pytest.raises(ValueError):
            w.publish(source, target, plots=False)
    assert (
        w.main(
            [
                "report",
                "--bundle",
                str(source),
                "--output",
                str(tmp_path / "cli-report"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        w.main(
            [
                "synthetic",
                "--scenario",
                "restore-failure",
                "--output",
                str(tmp_path / "failure"),
                "--no-plots",
            ]
        )
        == 1
    )
    assert w.main(["report", "--bundle", str(source), "--output", str(source), "--no-plots"]) == 2
    (source / "samples.csv").unlink()
    (source / "samples.csv").symlink_to(tmp_path / "outside")
    with pytest.raises((ValueError, OSError)):
        w.load(source)


def test_gap_blocks_comparison(tmp_path):
    _, capture, rows, _, _ = run(tmp_path, criteria=limits(max_abs_change_percent="100"))
    samples = [row for row in rows if row["point_id"] == "P03" and row["stage"] == "plateau"]
    for row in samples[15:]:
        row["elapsed_s"] = str(int(row["elapsed_s"]) + 2)
    assert w.analyze(capture, rows)["acceptance"] == "NOT EVALUATED"


@pytest.mark.parametrize("scenario", ("droop", "current-limit-mismatch"))
def test_optional_plots(tmp_path, scenario):
    pytest.importorskip("matplotlib")
    source, *_ = run(tmp_path, scenario)
    report = tmp_path / "plot"
    w.publish(source, report)
    assert (report / "supply-sensitivity.png").read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (report / "supply-sensitivity.svg").read_text()
