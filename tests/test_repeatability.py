"""WF-03 independent equal-cycle oracles and fake-only pipeline acceptance."""

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal as D
from pathlib import Path

import pytest

from hp437b import repeatability as w
from hp437b import repeatability_simulation as sim
from hp437b.workflow_report import _seal


def criteria(limit="2", samples=1, gap="2"):
    return {
        "source": "Fictional test specification revision 1",
        "decision_rule": "inclusive-no-guard-band",
        "max_cycle_spread_percent": limit,
        "min_samples_per_cycle": samples,
        "max_gap_s": gap,
    }


def cycle(index, values, status="completed", times=None):
    times = times if times is not None else list(range(len(values)))
    return {
        "cycle_id": f"C{index:02d}",
        "status": status,
        "points": [
            {
                "elapsed_s": t,
                "value_W": str(v) if v is not None else None,
                "status": "ok" if v is not None else "failed",
            }
            for t, v in zip(times, values, strict=True)
        ],
    }


def test_catalogue_oracle_and_equal_weighting_not_pooled_samples():
    root = Path(__file__).parents[1]
    fixture = json.loads(
        (root / "docs/workflows/examples/transmitter-test-catalog-v1.json").read_text()
    )["examples"][1]
    result = w.analyze([cycle(i, v) for i, v in enumerate(fixture["cycles_sensor_power_W"], 1)])
    assert [D(c["mean_W"]) for c in result["cycles"]] == [
        D(str(v)) for v in fixture["expected"]["cycle_means_W"]
    ]
    assert D(result["metrics"]["equal_cycle_mean_W"]) == D("0.001")
    assert D(result["metrics"]["cycle_spread_W"]) == D("0.00002")
    assert D(result["metrics"]["cycle_spread_percent"]) == 2
    assert D(result["metrics"]["cycle_sample_sd_W"]) == D("0.00001")
    result = w.analyze([cycle(1, ["0.001"]), cycle(2, ["0.003"] * 9)])
    assert D(result["metrics"]["equal_cycle_mean_W"]) == D("0.002")
    assert D(result["metrics"]["equal_cycle_mean_W"]) != D("0.0028")


def test_supplied_inclusive_threshold_and_coverage_boundaries():
    cycles = [cycle(1, ["0.00099"], times=[0]), cycle(2, ["0.00101"], times=[0])]
    assert w.analyze(cycles, criteria=criteria(gap="30"))["acceptance"]["outcome"] == "pass"
    assert (
        w.analyze(cycles, criteria=criteria("1.999", gap="30"))["acceptance"]["outcome"] == "fail"
    )
    for kwargs in (
        {"execution": "failed"},
        {"execution": "interrupted"},
        {"criteria": criteria(samples=2, gap="30")},
        {"criteria": criteria(gap="29.9")},
    ):
        result = w.analyze(cycles, **({"criteria": criteria(gap="30")} | kwargs))
        assert result["acceptance"]["outcome"] == "not_evaluated"
    assert w.analyze(cycles)["acceptance"]["outcome"] == "not_evaluated"


def test_partial_and_skipped_cycles_stay_visible_and_are_not_aggregated():
    result = w.analyze(
        [cycle(1, ["0.001"]), cycle(2, ["0.009"], "failed"), cycle(3, [], "skipped")],
        execution="failed",
        criteria=criteria(gap="30"),
    )
    assert result["requested_cycles"] == 3 and result["completed_cycles"] == 1
    assert (
        result["cycles"][1]["mean_W"] == "0.009"
        and not result["cycles"][1]["included_in_aggregate"]
    )
    assert result["cycles"][2]["mean_W"] is None
    assert D(result["metrics"]["equal_cycle_mean_W"]) == D("0.001")
    assert (
        result["metrics"]["cycle_spread_W"] is None
        and result["metrics"]["cycle_sample_sd_W"] is None
    )
    assert result["acceptance"]["outcome"] == "not_evaluated"


@pytest.mark.parametrize("values", [["0", "0"], ["-0.001", "-0.001"]])
def test_nonpositive_mean_keeps_percentage_undefined(values):
    result = w.analyze([cycle(1, [values[0]]), cycle(2, [values[1]])], criteria=criteria(gap="30"))
    assert D(result["metrics"]["cycle_spread_W"]) == 0
    assert result["metrics"]["cycle_spread_percent"] is None
    assert result["acceptance"]["outcome"] == "not_evaluated"


def test_late_receipt_blocks_passing_comparison_and_bad_points_are_rejected():
    result = w.analyze(
        [cycle(1, ["0.001"], times=[30.1]), cycle(2, ["0.001"], times=[1])],
        criteria=criteria(gap="30"),
    )
    assert result["cycles"][0]["receipts_after_window"] == 1
    assert result["acceptance"]["outcome"] == "not_evaluated"
    for bad in (
        [cycle(1, ["NaN"])],
        [cycle(1, ["0.001", "0.001"], times=[2, 1])],
        [cycle(1, [None])],
        [cycle(1, ["0.001"], "skipped")],
    ):
        with pytest.raises(ValueError):
            w.analyze(bad)


@pytest.mark.parametrize(
    "change",
    [
        {"max_cycle_spread_percent": "-1"},
        {"max_gap_s": "NaN"},
        {"min_samples_per_cycle": True},
        {"source": ""},
        {"decision_rule": "invented"},
        {"extra": "field"},
    ],
)
def test_invalid_criteria_before_capture(tmp_path, change):
    with pytest.raises(ValueError):
        sim.run(tmp_path / "capture", criteria=criteria() | change)
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize(
    "scenario,status,completed,source",
    [
        ("repeatable", "completed", 5, "off"),
        ("shifted", "completed", 5, "off"),
        ("unequal-counts", "completed", 5, "off"),
        ("nonpositive", "completed", 5, "off"),
        ("partial-cycle", "interrupted", 2, "off"),
        ("missing-cycle", "interrupted", 2, "off"),
        ("cancel", "interrupted", 1, "off"),
        ("timeout", "failed", 1, "unknown"),
        ("malformed", "failed", 1, "unknown"),
        ("instrument-error", "failed", 1, "off"),
        ("source-off-failure", "failed", 1, "unknown"),
        ("still-on", "failed", 1, "on"),
        ("source-mismatch", "failed", 1, "off"),
        ("initial-on", "failed", 0, "on"),
    ],
)
def test_synthetic_scenarios_capture_outcomes_provenance_and_shutdown(
    tmp_path, scenario, status, completed, source
):
    capture = tmp_path / "capture"
    record = sim.run(capture, scenario, operator="Test Operator")
    assert record["status"] == status and record["final_state"]["source"] == source
    assert record["virtual_duration_s"] <= 900
    original, result, provenance, bundle = w.load(capture)
    assert original == record and w.p.verify(provenance, capture)
    assert result["requested_cycles"] == 5 and result["completed_cycles"] == completed
    assert len(result["cycles"]) == 5 and result["acceptance"]["outcome"] == "not_evaluated"
    assert provenance["run"]["workflow_id"] == w.WORKFLOW
    assert provenance["dut"]["dut_id"] == "synthetic:wf03:reference"
    if scenario != "initial-on":
        assert result["stages"]["baseline-before"]["valid"] == 3
        assert D(result["stages"]["baseline-before"]["metrics"]["mean_W"]) == D("-0.00000002")
    if status == "completed":
        assert all(c["included_in_aggregate"] for c in result["cycles"])
        assert record["final_state"]["local"] == "true"
        assert all(result["stages"][f"{cid}-settling"]["valid"] == 20 for cid in w.CYCLES)
        assert all(result["stages"][f"{cid}-off-baseline"]["valid"] == 3 for cid in w.CYCLES)
    if scenario == "repeatable":
        assert [c["valid"] for c in result["cycles"]] == [30] * 5
        assert (
            D(result["metrics"]["equal_cycle_mean_W"]) == D("0.001")
            and D(result["metrics"]["cycle_spread_percent"]) == 0
        )
    if scenario in ("shifted", "unequal-counts"):
        assert D(result["metrics"]["equal_cycle_mean_W"]) == D("0.001")
        assert D(result["metrics"]["cycle_spread_percent"]) == 2
        if scenario == "unequal-counts":
            assert [c["valid"] for c in result["cycles"]] == [30, 15, 30, 30, 30]
    if scenario == "source-off-failure":
        assert result["cycles"][1]["valid"] == 30 and result["cycles"][1]["mean_W"] is not None
        assert not result["cycles"][1]["included_in_aggregate"]
    trace = json.loads((capture / "trace.json").read_text())["events"]
    writes = [e for e in trace if e["operation"] == "write"]
    if scenario in ("timeout", "malformed"):
        index = next(
            i
            for i, e in enumerate(trace)
            if e["operation"] == "read_error" or e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(
            e["operation"] in ("write", "session_open", "go_to_local") for e in trace[index + 1 :]
        )
    if scenario in ("source-off-failure", "still-on"):
        assert sum(e.get("raw_hex") == b"OC0".hex() and e["cycle_id"] == "C02" for e in writes) == 1
    if scenario == "initial-on":
        assert not any(e.get("raw_hex") in (b"OC0".hex(), b"OC1".hex()) for e in writes)
    assert (
        bundle.entries["workflow.json"]["sha256"]
        == hashlib.sha256((capture / "workflow.json").read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "scenario,limit,outcome",
    [
        ("shifted", "2", "pass"),
        ("shifted", "1.99", "fail"),
        ("partial-cycle", "2", "not_evaluated"),
        ("source-off-failure", "2", "not_evaluated"),
        ("unequal-counts", "2", "pass"),
    ],
)
def test_criteria_across_capture_and_report(tmp_path, scenario, limit, outcome):
    sim.run(
        tmp_path / "capture",
        scenario,
        criteria=criteria(limit),
        report_output=tmp_path / "report",
        plots=False,
    )
    result = json.loads((tmp_path / "report/results.json").read_text())
    assert result["acceptance"]["outcome"] == outcome
    assert (
        w.p.Bundle(tmp_path / "report").inventory("artifacts.json", "synthetic")["acceptance"]
        == outcome
    )


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_report_source_preservation_operator_harness_and_completion_inventory(
    tmp_path, monkeypatch
):
    capture, report = tmp_path / "capture", tmp_path / "report"
    sim.run(capture, "shifted", operator="Captured Operator")
    before = snapshot(capture)
    monkeypatch.setenv("HP437B_OPERATOR", "Environment Operator")
    w.publish(capture, report, plots=False)
    assert snapshot(capture) == before
    page = (report / "report.html").read_text()
    for text in (
        "RF Output Power Test",
        "Transmission-cycle repeatability",
        "SYNTHETIC",
        "RF-off baseline",
        "Captured Operator",
        "NOT EVALUATED",
        "5 / 5",
    ):
        assert text in page
    assert (
        page.index("Equipment traceability") < page.index("Report Harness") < page.index("Record:")
    )
    inv = w.p.Bundle(report).inventory("artifacts.json", "synthetic")
    assert inv["report_producer"]["commit"] and inv["analysis"] == "deterministic_only"
    assert not any("agent" in name for name in inv["artifacts"])
    w.publish(capture, tmp_path / "override", plots=False, operator="<Explicit & Operator>")
    assert "&lt;Explicit &amp; Operator&gt;" in (tmp_path / "override/report.html").read_text()
    assert (
        json.loads((tmp_path / "override/report-context.json").read_text())["origin"] == "argument"
    )
    assert snapshot(capture) == before


def reseal(capture, edit):
    path = capture / "workflow.json"
    record = json.loads(path.read_text())
    edit(record)
    path.write_text(json.dumps(record))
    (capture / "artifacts.json").unlink()
    _seal(
        capture,
        {
            "schema": "hp437b.repeatability-export.v1",
            "mode": "synthetic",
            "run_id": record["run_id"],
        },
    )


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r.update(mode="physical"),
        lambda r: r.update(workflow_id="sustained-output-stability-v1"),
        lambda r: r.update(status="running"),
        lambda r: r["final_state"].update(source="on"),
        lambda r: r["cycles"][0]["source_off"].update(status="skipped"),
        lambda r: r["cycles"].reverse(),
        lambda r: r["stages"]["C01-plateau"].update(status="skipped"),
    ],
)
def test_resealed_semantic_mismatches_rejected_before_publication(tmp_path, edit):
    sim.run(tmp_path / "capture")
    reseal(tmp_path / "capture", edit)
    with pytest.raises(ValueError):
        w.publish(tmp_path / "capture", tmp_path / "report", plots=False)
    assert not (tmp_path / "report").exists()


def test_hash_and_session_join_corruption_and_symlink_refusal(tmp_path):
    capture = tmp_path / "capture"
    sim.run(capture)
    csv = capture / "stages/C01-plateau.csv"
    original = csv.read_bytes()
    csv.write_bytes(original.replace(b"0.0010000", b"0.0090000", 1))
    with pytest.raises(ValueError, match="mismatch"):
        w.load(capture)
    csv.write_bytes(original)
    side = capture / "stages/C01-plateau.csv.session.json"
    data = json.loads(side.read_text())
    data["context"]["cycle_id"] = "C05"
    side.write_text(json.dumps(data))
    reseal(capture, lambda r: None)
    with pytest.raises(ValueError, match="join mismatch"):
        w.load(capture)
    data["context"]["cycle_id"] = "C01"
    side.write_text(json.dumps(data))
    reseal(capture, lambda r: None)
    target = tmp_path / "external.csv"
    target.write_bytes(original)
    csv.unlink()
    csv.symlink_to(target)
    with pytest.raises(ValueError, match="Symlink"):
        w.load(capture)


def test_output_conflicts_before_capture_and_existing_capture_preserved(tmp_path):
    for report in (tmp_path, tmp_path / "capture", tmp_path / "capture/report"):
        with pytest.raises(ValueError):
            sim.run(tmp_path / "capture", report_output=report, plots=False)
        assert not (tmp_path / "capture").exists()
    sim.run(tmp_path / "capture")
    before = snapshot(tmp_path / "capture")
    with pytest.raises(ValueError):
        sim.run(tmp_path / "capture")
    assert snapshot(tmp_path / "capture") == before


def test_report_storage_failure_retains_closed_capture_without_reacquisition(tmp_path, monkeypatch):
    original = Path.write_text

    def fail(self, *args, **kwargs):
        if self.name == "report.html":
            raise OSError("injected report failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail)
    with pytest.raises(OSError, match="report failure"):
        sim.run(tmp_path / "capture", report_output=tmp_path / "report", plots=False)
    assert w.load(tmp_path / "capture")[0]["status"] == "completed"
    assert (
        not (tmp_path / "report/artifacts.json").exists()
        and (tmp_path / "report/failure.json").exists()
    )


def test_capture_finalization_failure_leaves_unsealed_checkpoint(tmp_path, monkeypatch):
    original = Path.write_bytes

    def fail(self, *args, **kwargs):
        if self.name == "workflow.json":
            raise OSError("injected capture storage failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_bytes", fail)
    with pytest.raises(OSError, match="capture storage"):
        sim.run(tmp_path / "capture")
    assert not (tmp_path / "capture/artifacts.json").exists()
    assert json.loads((tmp_path / "capture/starting.json").read_text())["status"] == "running"


def test_actual_cli_and_saved_capture_commands(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hp437b.repeatability",
            "synthetic",
            "--scenario",
            "shifted",
            "--output",
            str(tmp_path / "capture"),
            "--report-output",
            str(tmp_path / "report"),
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
    assert json.loads(result.stdout)["completed_cycles"] == 5
    assert (
        w.main(
            [
                "report",
                "--bundle",
                str(tmp_path / "capture"),
                "--output",
                str(tmp_path / "re-report"),
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
                str(tmp_path / "failure"),
                "--report-output",
                str(tmp_path / "failure-report"),
                "--no-plots",
            ]
        )
        == 1
    )
    assert (
        w.main(
            [
                "synthetic",
                "--scenario",
                "unsupported",
                "--output",
                str(tmp_path / "bad"),
                "--report-output",
                str(tmp_path / "bad-report"),
                "--no-plots",
            ]
        )
        == 2
    )
    assert not (tmp_path / "bad").exists()


def test_optional_plots_are_real_png_and_svg(tmp_path):
    pytest.importorskip("matplotlib")
    sim.run(tmp_path / "capture", "partial-cycle", report_output=tmp_path / "report")
    assert (tmp_path / "report/cycle-means.png").read_bytes().startswith(b"\x89PNG")
    assert b"<svg" in (tmp_path / "report/cycle-means.svg").read_bytes()
