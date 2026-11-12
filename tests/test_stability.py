"""Independent WF-02 numerical oracles, sealed-data joins, and fake-only workflows."""

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest

from hp437b import provenance as p
from hp437b import stability as s
from hp437b import stability_simulation as sim
from hp437b.workflow_report import _seal


def point(t, value):
    return {
        "elapsed_s": t,
        "value_W": str(value) if value is not None else None,
        "status": "ok" if value is not None else "failed",
    }


def criteria(limit="3", samples=1, gap="60"):
    return {
        "source": "Fictional test specification revision 1",
        "decision_rule": "inclusive-no-guard-band",
        "max_abs_endpoint_drift_percent": limit,
        "min_samples_per_bin": samples,
        "max_gap_s": gap,
    }


def test_catalogue_oracle_and_actual_time_regression():
    fixture = json.loads(
        (
            Path(__file__).parents[1] / "docs/workflows/examples/transmitter-test-catalog-v1.json"
        ).read_text()
    )["examples"][0]
    points = [
        point(t, v)
        for t, v in zip(fixture["elapsed_seconds"], fixture["sensor_power_W"], strict=True)
    ]
    result = s.analyze(points, duration_s=240, bin_s=60, criteria=criteria())
    m = result["metrics"]
    assert D(m["mean_W"]) == D("0.001015")
    assert D(m["endpoint_change_percent"]) == 3
    assert D(m["slope_W_per_minute"]) == D("0.00001")
    assert result["acceptance"]["outcome"] == "pass"  # inclusive boundary
    result = s.analyze(points, duration_s=240, bin_s=60, criteria=criteria("2.999"))
    assert result["acceptance"]["outcome"] == "fail"
    # Not the sample index: doubling receipt times halves the slope.
    result = s.analyze(
        [
            point(t * 2, v)
            for t, v in zip(fixture["elapsed_seconds"], fixture["sensor_power_W"], strict=True)
        ],
        duration_s=480,
        bin_s=120,
    )
    assert D(result["metrics"]["slope_W_per_minute"]) == D("0.000005")


@pytest.mark.parametrize(
    "points,reason",
    [
        ([], "absent"),
        ([point(60, "0.001"), point(120, "0.002")], "absent"),
        ([point(0, "0"), point(180, "0.001")], "nonpositive"),
        ([point(0, "-0.001"), point(180, "0.001")], "nonpositive"),
    ],
)
def test_missing_and_nonpositive_endpoint_are_not_zero_or_pass(points, reason):
    result = s.analyze(points, duration_s=240, bin_s=60, criteria=criteria())
    assert result["metrics"]["endpoint_change_percent"] is None
    assert reason in result["unavailable_reasons"]["percent"]
    assert result["acceptance"]["outcome"] == "not_evaluated"


def test_coverage_failures_even_with_zero_drift_and_failed_execution():
    points = [point(t, "0.001") for t in (0, 60, 120, 180)]
    for kwargs in (
        {"execution": "failed"},
        {"execution": "interrupted"},
        {"criteria": criteria(samples=2)},
        {"criteria": criteria(gap="59")},
    ):
        result = s.analyze(points, duration_s=240, bin_s=60, **({"criteria": criteria()} | kwargs))
        assert result["acceptance"]["outcome"] == "not_evaluated"
    result = s.analyze(points + [point(200, None)], duration_s=240, bin_s=60, criteria=criteria())
    assert (
        result["coverage"]["nonvalid"] == 1 and result["acceptance"]["outcome"] == "not_evaluated"
    )
    assert s.analyze(points, duration_s=240, bin_s=60)["acceptance"]["outcome"] == "not_evaluated"


def test_endpoint_boundaries_and_late_receipts_are_explicit():
    result = s.analyze(
        [
            point(0, "0.001"),
            point(60, "0.002"),
            point(120, "0.003"),
            point(180, "0.004"),
            point(240, "0.005"),
            point(241, "0.006"),
        ],
        duration_s=240,
        bin_s=60,
        criteria=criteria("999"),
    )
    assert [b["count"] for b in result["bins"]] == [1, 1, 1, 2]
    assert result["coverage"]["receipts_after_window"] == 1
    assert result["acceptance"]["outcome"] == "not_evaluated"
    assert D(result["metrics"]["last_bin_mean_W"]) == D("0.0045")


@pytest.mark.parametrize(
    "change",
    [
        {"decision_rule": "invented"},
        {"max_gap_s": "NaN"},
        {"max_abs_endpoint_drift_percent": "-1"},
        {"min_samples_per_bin": True},
        {"source": ""},
        {"unknown": "field"},
    ],
)
def test_criteria_fail_before_output_allocation(tmp_path, change):
    output = tmp_path / "capture"
    with pytest.raises(ValueError):
        sim.run(output, criteria=criteria() | change)
    assert not output.exists()


@pytest.mark.parametrize(
    "scenario,status,source",
    [
        (v, "completed", "off")
        for v in ("constant", "ramp", "step", "irregular", "excess-drift", "nonpositive")
    ]
    + [(v, "interrupted", "off") for v in ("missing-first", "missing-last", "cancel")]
    + [(v, "failed", "unknown") for v in ("timeout", "malformed", "source-off-failure")],
)
def test_all_scenarios_use_real_collect_and_preserve_outcomes(tmp_path, scenario, status, source):
    capture = tmp_path / "capture"
    record = sim.run(capture, scenario, operator="Test Operator")
    assert record["status"] == status and record["final_state"]["source"] == source
    assert record["virtual_duration_s"] <= 2100
    original, result, provenance, bundle = s.load(capture)
    assert original == record and p.verify(provenance, capture)
    assert provenance["run"]["workflow_id"] == s.WORKFLOW
    assert result["acceptance"]["outcome"] == "not_evaluated"
    assert result["stages"]["baseline-before"]["valid"] == 3
    assert D(result["stages"]["baseline-before"]["metrics"]["mean_W"]) == D("-0.00000002")
    if status == "completed":
        assert result["coverage"]["bins_present"] == 6
        assert result["stages"]["settling"]["valid"] == 20  # excluded from plateau results
        assert record["final_state"]["local"] == "true"
    if scenario == "constant":
        assert result["coverage"]["valid"] == 1800
        assert D(result["metrics"]["mean_W"]) == D("0.001")
        assert D(result["metrics"]["endpoint_change_percent"]) == 0
        assert D(result["metrics"]["slope_W_per_minute"]) == 0
    if scenario in ("ramp", "irregular"):
        assert abs(D(result["metrics"]["slope_W_per_minute"]) - D("0.0000006")) < D("1e-11")
    if scenario.startswith("missing-"):
        assert result["coverage"]["bins_present"] == 5
        assert result["metrics"]["endpoint_change_percent"] is None
    if scenario in ("timeout", "malformed"):
        assert result["coverage"]["valid"] == 2 and result["coverage"]["nonvalid"] == 1
        trace = json.loads((capture / "trace.json").read_text())["events"]
        index = next(
            i
            for i, e in enumerate(trace)
            if e["operation"] == "read_error" or e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(e["operation"] == "write" for e in trace[index + 1 :])
    assert (
        bundle.entries["workflow.json"]["sha256"]
        == hashlib.sha256((capture / "workflow.json").read_bytes()).hexdigest()
    )


def snapshot(root):
    return {f.relative_to(root).as_posix(): f.read_bytes() for f in root.rglob("*") if f.is_file()}


def test_report_provenance_operator_source_preservation_and_no_handoff(tmp_path, monkeypatch):
    capture, output = tmp_path / "capture", tmp_path / "report"
    sim.run(capture, "ramp", operator="Captured Operator")
    before = snapshot(capture)
    monkeypatch.setenv("HP437B_OPERATOR", "Environment Operator")
    result = s.publish(capture, output, plots=False)
    assert snapshot(capture) == before
    assert result["execution"] == "completed"
    page = (output / "report.html").read_text()
    assert "<title>RF Output Power Test</title>" in page
    for word in (
        "SYNTHETIC",
        "Sustained output stability",
        "RF-off baseline",
        "Endpoint change",
        "Sampled drift slope",
        "Captured Operator",
        "NOT EVALUATED",
    ):
        assert word in page
    assert (
        page.index("Equipment traceability") < page.index("Report Harness") < page.index("Record:")
    )
    inventory = p.Bundle(output).inventory("artifacts.json", "synthetic")
    assert inventory["analysis"] == "deterministic_only"
    assert inventory["report_producer"]["commit"]
    assert not any("agent" in name for name in inventory["artifacts"])
    with pytest.raises(ValueError, match="already exists"):
        s.publish(capture, output, plots=False)


def reseal(capture, edit):
    path = capture / "workflow.json"
    record = json.loads(path.read_text())
    edit(record)
    path.write_text(json.dumps(record))
    (capture / "artifacts.json").unlink()
    _seal(
        capture,
        {"schema": "hp437b.stability-export.v1", "mode": "synthetic", "run_id": record["run_id"]},
    )


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r.update(mode="physical"),
        lambda r: r.update(workflow_id="power-reference-v1"),
        lambda r: r.update(status="running"),
        lambda r: r["final_state"].update(source="unknown"),
        lambda r: r["stages"]["plateau"].update(status="skipped"),
    ],
)
def test_resealed_semantic_forgeries_rejected_before_report_output(tmp_path, edit):
    capture = tmp_path / "capture"
    sim.run(capture)
    reseal(capture, edit)
    with pytest.raises(ValueError):
        s.publish(capture, tmp_path / "report", plots=False)
    assert not (tmp_path / "report").exists()


def test_csv_tamper_and_symlinks_rejected(tmp_path):
    capture = tmp_path / "capture"
    sim.run(capture)
    csv = capture / "stages/plateau.csv"
    original = csv.read_bytes()
    csv.write_bytes(original.replace(b"0.0010000", b"0.0090000", 1))
    with pytest.raises(ValueError, match="mismatch"):
        s.load(capture)
    csv.write_bytes(original)
    target = tmp_path / "foreign.csv"
    target.write_bytes(original)
    csv.unlink()
    csv.symlink_to(target)
    with pytest.raises(ValueError, match="Symlink"):
        s.load(capture)


def test_report_failure_preserves_sealed_capture_and_no_reacquisition(tmp_path, monkeypatch):
    original = Path.write_text

    def fail(self, *args, **kwargs):
        if self.name == "report.html":
            raise OSError("injected report storage failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail)
    capture, report = tmp_path / "capture", tmp_path / "report"
    with pytest.raises(OSError, match="injected"):
        sim.run(capture, report_output=report, plots=False)
    assert (capture / "artifacts.json").exists() and s.load(capture)[0]["status"] == "completed"
    assert not (report / "artifacts.json").exists()
    assert (report / "failure.json").exists()


def test_preflight_refuses_nested_or_existing_paths_before_capture(tmp_path):
    for report in (tmp_path / "capture", tmp_path / "capture/report", tmp_path):
        with pytest.raises(ValueError):
            sim.run(tmp_path / "capture", report_output=report, plots=False)
        assert not (tmp_path / "capture").exists()


def test_actual_cli_installed_module_and_saved_report(tmp_path):
    capture, report = tmp_path / "capture", tmp_path / "report"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hp437b.stability",
            "synthetic",
            "--scenario",
            "constant",
            "--output",
            str(capture),
            "--report-output",
            str(report),
            "--no-plots",
            "--operator",
            "CLI Operator",
        ],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["execution"] == "completed"
    assert "CLI Operator" in (report / "report.html").read_text()
    assert (
        s.main(
            [
                "report",
                "--bundle",
                str(capture),
                "--output",
                str(tmp_path / "re-report"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        s.main(
            [
                "synthetic",
                "--scenario",
                "timeout",
                "--output",
                str(tmp_path / "failure"),
                "--report-output",
                str(tmp_path / "failure-report"),
                "--no-plots",
            ]
        )
        == 1
    )


def test_plots_render_when_requested(tmp_path):
    pytest.importorskip("matplotlib")
    capture, report = tmp_path / "capture", tmp_path / "report"
    sim.run(capture, "step", report_output=report)
    assert (report / "power-trend.png").read_bytes().startswith(b"\x89PNG")
    assert b"<svg" in (report / "power-trend.svg").read_bytes()


@pytest.mark.parametrize(
    "scenario,outcome",
    [
        ("constant", "pass"),
        ("ramp", "pass"),
        ("excess-drift", "fail"),
        ("missing-last", "not_evaluated"),
        ("source-off-failure", "not_evaluated"),
    ],
)
def test_supplied_comparison_through_capture_provenance_and_report(tmp_path, scenario, outcome):
    capture, report = tmp_path / "capture", tmp_path / "report"
    sim.run(capture, scenario, criteria=criteria("3", gap="2"), report_output=report, plots=False)
    result = json.loads((report / "results.json").read_text())
    assert result["acceptance"]["outcome"] == outcome
    assert p.Bundle(report).inventory("artifacts.json", "synthetic")["acceptance"] == outcome


def test_resealed_session_join_mismatch_is_rejected(tmp_path):
    capture = tmp_path / "capture"
    sim.run(capture)
    path = capture / "stages/plateau.csv.session.json"
    data = json.loads(path.read_text())
    data["context"]["workflow_run_id"] = "wrong-run"
    path.write_text(json.dumps(data))
    reseal(capture, lambda record: None)
    with pytest.raises(ValueError, match="join mismatch"):
        s.load(capture)
