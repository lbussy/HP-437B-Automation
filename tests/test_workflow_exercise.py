"""End-to-end synthetic workflow checks; no physical transport path exists."""

import csv
import hashlib
import json
from pathlib import Path
from runpy import run_path

import pytest

MODULE = run_path(str(Path(__file__).parents[1] / "tools/exercise_workflow.py"))
run = MODULE["run"]


@pytest.mark.parametrize("scenario,expected_count", [("nominal", 300), ("slow", 120)])
def test_complete_synthetic_bundle_and_actual_sampling(tmp_path, scenario, expected_count):
    output = tmp_path / "bundle"
    record = run(output, scenario)
    assert record["status"] == "completed"
    assert all(stage["status"] == "completed" for stage in record["stages"].values())
    assert record["final_state"]["source"] == "off" and record["final_state"]["local"] == "true"
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["integrity"] == "pass"
    assert analysis["stages"]["S40"]["valid"] == expected_count
    assert analysis["stages"]["S40"]["median_receipt_spacing_s"] == (
        2.5 if scenario == "slow" else 1
    )
    assert analysis["stages"]["S40"]["metrics"]["mean_W"] == "0.00098800"
    for stage in ("S10", "S30", "S60"):
        assert analysis["stages"][stage]["valid"] == 3
    inventory = json.loads((output / "artifacts.json").read_text())
    for relative, metadata in inventory["artifacts"].items():
        data = (output / relative).read_bytes()
        assert len(data) == metadata["bytes"]
        assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
    report = (output / "report.md").read_text()
    assert "SYNTHETIC" in report and "not evaluated" in report
    assert "-1.200" in report or "-1.2" in report


@pytest.mark.parametrize(
    "scenario,status,source,valid,nonvalid",
    [
        ("malformed", "failed", "unknown", 2, 1),
        ("timeout", "failed", "unknown", 2, 1),
        ("instrument-error", "failed", "off", 2, 1),
        ("cancel", "interrupted", "off", 2, 0),
        ("source-off-failure", "failed", "unknown", 300, 0),
    ],
)
def test_failure_preserves_partial_evidence_and_cleanup_policy(
    tmp_path, scenario, status, source, valid, nonvalid
):
    output = tmp_path / "bundle"
    record = run(output, scenario)
    assert record["status"] == status and record["final_state"]["source"] == source
    assert record["stages"]["S60"]["status"] == "skipped"
    analysis = json.loads((output / "analysis.json").read_text())
    assert analysis["stages"]["S40"]["valid"] == valid
    assert analysis["stages"]["S40"]["nonvalid"] == nonvalid
    trace = json.loads((output / "trace.json").read_text())["events"]
    if scenario == "malformed":
        fault_index = next(
            i for i, e in enumerate(trace) if e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(e["operation"] == "write" for e in trace[fault_index + 1 :])
        with (output / "stages/S40.csv").open() as handle:
            rows = list(csv.DictReader(handle))
        assert rows[-1]["raw_hex"] == b"MALFORMED\r\n".hex() and rows[-1]["status"] == "failed"
    if scenario == "timeout":
        fault_index = next(i for i, e in enumerate(trace) if e["operation"] == "read_error")
        assert not any(e["operation"] == "write" for e in trace[fault_index + 1 :])
    if scenario in ("cancel", "instrument-error"):
        assert sum(e.get("raw_hex") == b"OC0".hex() for e in trace) == 1
    assert (output / "report.md").exists()


def test_existing_output_is_refused_without_overwriting(tmp_path):
    (tmp_path / "precious.txt").write_text("keep")
    with pytest.raises(FileExistsError):
        run(tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / "precious.txt"]
    assert (tmp_path / "precious.txt").read_text() == "keep"


def test_corrupt_valid_row_is_not_silently_used(tmp_path):
    output = tmp_path / "bundle"
    run(output)
    path = output / "stages/S40.csv"
    path.write_text(path.read_text().replace("0.00098700", "0.00012300", 1))
    with pytest.raises(AssertionError):
        MODULE["inspect_stage"](path)


def test_report_storage_failure_does_not_leave_completed_manifest(tmp_path, monkeypatch):
    original = Path.open

    def fail_report(self, *args, **kwargs):
        if self.name == "report.md":
            raise OSError("injected report storage failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_report)
    output = tmp_path / "bundle"
    with pytest.raises(OSError, match="injected report"):
        run(output)
    assert not (output / "workflow.json").exists()
    assert json.loads((output / "starting.json").read_text())["status"] == "running"
