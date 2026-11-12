"""WF-05 synthetic orchestration, frequency corrections, and publication."""

import copy
import html
import json
import math
from decimal import Decimal as D

import pytest

from hp437b import frequency_sweep as w
from hp437b import provenance as p
from hp437b import reporting as r
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
    assert result["requested_points"] == 5
    assert result["zero_mean_W"] == "-2E-8"
    assert result["acceptance"] == "NOT EVALUATED"
    assert result["points"][0]["valid_samples"] == 30
    assert len(rows) <= 256
    assert capture["final_state"]["hardware_opened"] is False
    assert capture["final_state"]["meter_reference_off"] is True
    failed = scenario in (
        "timeout",
        "malformed",
        "instrument-error",
        "source-off-failure",
        "frequency-mismatch",
        "frequency-unverified",
        "factor-mismatch",
    )
    interrupted = scenario in ("cancel", "missing-band")
    assert result["execution"] == (
        "failed" if failed else "interrupted" if interrupted else "completed"
    )
    assert result["completed_points"] == (1 if failed or interrupted else 5)
    if failed or interrupted:
        assert all(row["status"] == "skipped" for row in result["points"][2:])
    trace = bundle.json("trace.json")
    if scenario in ("timeout", "malformed"):
        assert trace[-1]["operation"] == "communication_uncertain"
        assert capture["final_state"]["external_source_off"] is None
    if scenario == "source-off-failure":
        assert trace[-1]["operation"] == "source_off_attempt"
    if scenario in ("frequency-unverified", "frequency-mismatch", "factor-mismatch"):
        assert not capture["points"][1]["source_on_ack"]
        assert capture["final_state"]["external_source_off"] is True
    p.verify(w.provenance(capture, bundle), source)
    before = {path.name: path.read_bytes() for path in source.iterdir()}
    report = tmp_path / "report"
    assert w.publish(source, report, plots=False) == result
    assert before == {path.name: path.read_bytes() for path in source.iterdir()}
    sheet = (report / "report.html").read_text()
    assert "RF Output Power Test" in sheet and "SYNTHETIC" in sheet
    assert "Pre-RF zero:" in sheet and "Output power versus frequency" in sheet
    assert sheet.index("Equipment:") < sheet.index("Report Harness:") < sheet.index("Record:")
    assert "Final external source:" in sheet
    assert "CF %" in sheet and "Loss dB" in sheet
    assert (report / "artifacts.json").exists()
    md = html.unescape((report / "report.md").read_text())
    assert "Operator:" in md and "Pre-RF zero:" in md and "Report Harness:" in md


def test_catalogue_oracle(tmp_path):
    result = run(tmp_path, "band-droop")[-1]
    assert [D(point["measured_W"]) for point in result["points"]] == [
        D("4.8"),
        D(5),
        D("5.1"),
        D("4.9"),
        D("4.7"),
    ]
    assert [D(point["error_percent"]) for point in result["points"]] == [-4, 0, 2, -2, -6]
    assert float(result["observed_spread_dB"]) == pytest.approx(
        10 * math.log10(5.1 / 4.7), abs=1e-12
    )
    assert result["worst_error_point_id"] == "P05"
    assert D(result["observed_DUT_min_W"]) == D("4.7")
    assert D(result["observed_DUT_max_W"]) == D("5.1")


@pytest.mark.parametrize("scenario", ("unequal-corrections", "meter-corrected"))
def test_correction_once_at_exact_frequency(tmp_path, scenario):
    _, capture, _, _, result = run(
        tmp_path, scenario, criteria=limits(max_abs_error_percent="0", max_spread_dB="0")
    )
    assert [D(point["measured_W"]) for point in result["points"]] == [5] * 5
    assert [D(point["sensor_min_W"]) for point in result["points"]] == [
        D(point["sensor_mean_W"]) for point in result["points"]
    ]
    assert result["acceptance"] == "PASS"
    assert D(result["points"][1]["sensor_mean_W"]) == D(".0005")
    assert D(result["points"][1]["indicated_mean_W"]) == D(
        ".000485" if scenario == "unequal-corrections" else ".0005"
    )
    assert capture["points"][1]["factor_ack_percent"] == (
        "100" if scenario == "unequal-corrections" else "97"
    )


def test_sensor_plane_without_loss(tmp_path):
    plan = w.default_plan("sensor-plane")
    plan["points"][1]["fixture_loss_dB"] = plan["points"][1]["fixture_source"] = None
    result = run(tmp_path, plan=plan, criteria=limits(max_abs_error_percent="0"))[-1]
    assert result["acceptance"] == "PASS"
    assert result["points"][1]["DUT_mean_W"] is None
    assert result["DUT_eligible_points"] == 4 and "incomplete" in result["DUT_spread_scope"]
    assert D(result["points"][1]["measured_W"]) == D(".005")


@pytest.mark.parametrize(
    "scenario,key", (("missing-factor", "sensor_mean_W"), ("missing-loss", "DUT_mean_W"))
)
def test_no_unknown_correction_substitution(tmp_path, scenario, key):
    result = run(tmp_path, scenario, criteria=limits(max_spread_dB="100"))[-1]
    assert result["points"][1][key] is None
    assert result["points"][1]["measured_W"] is None
    assert result["acceptance"] == "NOT EVALUATED" and not result["full_coverage"]
    assert result["eligible_points"] == 4
    assert D(result["observed_spread_dB"]) == 0
    assert "incomplete" in result["spread_scope"]


def test_spread_without_targets_is_valid(tmp_path):
    result = run(tmp_path, "missing-target", criteria=limits(max_spread_dB="0"))[-1]
    assert result["acceptance"] == "PASS"
    assert result["points"][1]["error_percent"] is None


def test_error_limit_requires_targets(tmp_path):
    assert (
        run(tmp_path, "missing-target", criteria=limits(max_abs_error_percent="100"))[-1][
            "acceptance"
        ]
        == "NOT EVALUATED"
    )


def test_droop_verdicts(tmp_path):
    result = run(
        tmp_path, "band-droop", criteria=limits(max_abs_error_percent="6", max_spread_dB=".4")
    )[-1]
    assert result["acceptance"] == "PASS"
    assert w.analyze(*w.load(tmp_path / "capture")[:2])["acceptance"] == "PASS"
    capture, rows, _ = w.load(tmp_path / "capture")
    capture["criteria"]["max_spread_dB"] = ".3"
    assert w.analyze(capture, rows)["acceptance"] == "FAIL"
    capture["criteria"]["max_spread_dB"] = ".4"
    capture["criteria"]["point_limits_percent"] = {"P05": "5"}
    assert w.analyze(capture, rows)["acceptance"] == "FAIL"


@pytest.mark.parametrize(
    "scenario", ("timeout", "cancel", "missing-band", "frequency-unverified", "zero-output")
)
def test_incomplete_or_nonpositive_cannot_pass_band_criterion(tmp_path, scenario):
    result = run(tmp_path, scenario, criteria=limits(max_spread_dB="100"))[-1]
    assert result["acceptance"] == "NOT EVALUATED"
    if scenario == "zero-output":
        assert result["points"][1]["error_dB"] is None
        assert D(result["points"][1]["error_percent"]) == -100
        assert (
            result["worst_error_point_id"] == "P02" and D(result["worst_abs_error_percent"]) == 100
        )


def test_repeated_anchor_order_preserved(tmp_path):
    result = run(tmp_path, "repeated-anchor")[-1]
    assert [row["frequency_Hz"] for row in result["points"]] == [
        1800000,
        3500000,
        7000000,
        14000000,
        1800000,
    ]
    assert D(result["points"][0]["measured_W"]) == 5
    assert D(result["points"][4]["measured_W"]) == D("4.9")


def test_independent_model_truth_is_not_analysis_input(tmp_path):
    _, capture, rows, _, original = run(tmp_path)
    for point in capture["plan"]["points"]:
        point["synthetic_DUT_W"] = "9999"
        point["simulation_loss_dB"] = "99"
        point["simulation_sensor_factor_percent"] = "1"
    assert w.analyze(capture, rows) == original


@pytest.mark.parametrize(
    "mutation",
    (
        "unknown-frequency",
        "out-of-range",
        "bool-frequency",
        "missing-source",
        "bad-factor",
        "bad-loss",
        "bad-plane",
        "too-many",
        "duplicate-id",
        "bad-placement",
        "unknown-meter-factor",
        "sensor-overload",
    ),
)
def test_bad_plan_before_allocation(tmp_path, mutation):
    plan = copy.deepcopy(w.default_plan())
    point = plan["points"][1]
    if mutation == "unknown-frequency":
        point["frequency_Hz"] = None
    elif mutation == "out-of-range":
        point["frequency_Hz"] = 4200000001
    elif mutation == "bool-frequency":
        point["frequency_Hz"] = True
    elif mutation == "missing-source":
        point["factor_source"] = None
    elif mutation == "bad-factor":
        point["sensor_factor_percent"] = "0"
    elif mutation == "bad-loss":
        point["fixture_loss_dB"] = "NaN"
    elif mutation == "bad-plane":
        plan["measurement_plane"] = "unknown"
    elif mutation == "too-many":
        plan["points"].append(dict(point))
    elif mutation == "duplicate-id":
        point["point_id"] = "P01"
    elif mutation == "bad-placement":
        point["factor_applied_in"] = "both"
    elif mutation == "unknown-meter-factor":
        point["sensor_factor_percent"] = point["factor_source"] = None
        point["factor_applied_in"] = "meter"
    else:
        point["simulation_loss_dB"] = "0"
    with pytest.raises(ValueError):
        w.simulate(tmp_path / "absent", plan=plan)
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize(
    "mutation", ("no-limit", "negative", "zero-gap", "bad-count", "unknown-point", "bad-rule")
)
def test_bad_criteria_before_allocation(tmp_path, mutation):
    criteria = limits(max_spread_dB="1")
    if mutation == "no-limit":
        criteria.pop("max_spread_dB")
    elif mutation == "negative":
        criteria["max_spread_dB"] = "-1"
    elif mutation == "zero-gap":
        criteria["max_gap_s"] = "0"
    elif mutation == "bad-count":
        criteria["min_samples_per_point"] = True
    elif mutation == "unknown-point":
        criteria.update(max_abs_error_percent="1", point_limits_percent={"P06": "1"})
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
                "points": [],
                "final_state": None,
            }
        )
    )
    (source / "artifacts.json").unlink()
    _seal(
        source,
        dict(
            schema="hp437b.frequency-sweep-inventory.v1", mode="synthetic", run_id=capture["run_id"]
        ),
    )


@pytest.mark.parametrize(
    "mutation",
    (
        "hash",
        "frequency-ack",
        "factor-ack",
        "trace",
        "cross-run",
        "units",
        "sequence",
        "mode",
        "final-state",
        "correction-source",
    ),
)
def test_corrupt_and_resealed_semantic_inputs(tmp_path, mutation):
    source, *_ = run(tmp_path)
    if mutation in ("hash", "cross-run", "units", "sequence"):
        path = source / "samples.csv"
        data = path.read_text()
        if mutation == "hash":
            data += "bad"
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
        if mutation == "frequency-ack":
            data["points"][1]["frequency_ack_Hz"] = 1
        elif mutation == "factor-ack":
            data["points"][1]["factor_ack_percent"] = "99"
        elif mutation == "trace":
            data[1]["power_setting"] = "Changed setting"
        elif mutation == "mode":
            data["mode"] = "physical"
        elif mutation == "final-state":
            data["final_state"]["external_source_off"] = None
        else:
            data["plan"]["points"][1]["factor_source"] = None
        path.write_bytes(r.encoded(data))
    if mutation != "hash":
        reseal(source)
    with pytest.raises((ValueError, KeyError)):
        w.publish(source, tmp_path / "absent", plots=False)
    assert not (tmp_path / "absent").exists()


def test_storage_failure_no_capture_retry(tmp_path, monkeypatch):
    source, *_ = run(tmp_path)
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
                "timeout",
                "--output",
                str(tmp_path / "timeout"),
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


def test_optional_plots(tmp_path):
    pytest.importorskip("matplotlib")
    source, *_ = run(tmp_path, "repeated-anchor")
    report = tmp_path / "plotted"
    w.publish(source, report)
    assert (report / "frequency-sweep.png").read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (report / "frequency-sweep.svg").read_text()


def test_one_point_has_no_band_spread(tmp_path):
    plan = w.default_plan()
    plan["points"] = plan["points"][:1]
    result = run(tmp_path, plan=plan, criteria=limits(max_spread_dB="1"))[-1]
    assert result["full_coverage"] is True
    assert result["observed_spread_dB"] is None
    assert result["spread_unavailable_reason"]
    assert result["acceptance"] == "NOT EVALUATED"


def test_unusual_metadata_is_escaped(tmp_path):
    plan = w.default_plan()
    plan["name"] = "<Fictional & source>"
    source, *_ = run(tmp_path, plan=plan, operator="Bench operator")
    w.publish(source, tmp_path / "report", plots=False)
    sheet = (tmp_path / "report/report.html").read_text()
    assert "&lt;Fictional &amp; source&gt;" in sheet and "Bench operator" in sheet


def test_gap_prevents_coverage_claim(tmp_path):
    _, capture, rows, _, _ = run(tmp_path, criteria=limits(max_spread_dB="1"))
    plateau = [row for row in rows if row["point_id"] == "P03" and row["stage"] == "plateau"]
    for row in plateau[15:]:
        row["elapsed_s"] = str(int(row["elapsed_s"]) + 2)
    result = w.analyze(capture, rows)
    assert result["points"][2]["coverage_eligible"] is False
    assert result["acceptance"] == "NOT EVALUATED"
