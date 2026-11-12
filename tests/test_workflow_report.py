"""Human-started deterministic publication; no AI or hardware handoff."""

import json
import subprocess
import sys
from pathlib import Path
from runpy import run_path

import pytest

from hp437b import provenance as p
from hp437b import workflow_report as w

ROOT = Path(__file__).parents[1]
SYNTHETIC = run_path(str(ROOT / "tools/exercise_workflow.py"))


def tree(root):
    return {str(f.relative_to(root)): f.read_bytes() for f in root.rglob("*") if f.is_file()}


@pytest.mark.parametrize("scenario", SYNTHETIC["SCENARIOS"])
def test_deterministic_job_preserves_capture_and_execution(tmp_path, scenario, monkeypatch):
    source, output = tmp_path / "capture", tmp_path / "published"
    capture = SYNTHETIC["run"](source, scenario)
    before = tree(source)
    sidecar_before = tree(p.sidecar_path(source))
    # Only bounded local Git identity queries may run; no model/provider process.
    original_popen = subprocess.Popen

    def local_git_only(args, *positional, **kwargs):
        assert args[0] == "git", "unexpected publication/provider subprocess"
        return original_popen(args, *positional, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", local_git_only)
    result = w.publish(source, output, plots=False)
    assert result["execution"] == capture["status"]
    assert result["analysis"] == "deterministic_only"
    assert result["report_status"] == "completed"
    assert result["measurement_criteria"] == "not_evaluated"
    assert tree(source) == before and tree(p.sidecar_path(source)) == sidecar_before
    assert not (output / "report/agent-analysis.json").exists()
    report_manifest = json.loads((output / "report/artifacts.json").read_text())
    assert report_manifest["agent_analysis"] == "not_supplied"
    assert (output / "report/report.html").is_file()
    p.Bundle(output).inventory("artifacts.json", capture["mode"])


@pytest.mark.parametrize(
    "target", ["source", "child", "parent", "sidecar", "sidecar-child", "existing"]
)
def test_report_output_guards_before_capture(tmp_path, target):
    source = tmp_path / "capture"
    options = {
        "source": source,
        "child": source / "report",
        "parent": tmp_path,
        "sidecar": p.sidecar_path(source),
        "sidecar-child": p.sidecar_path(source) / "nested",
        "existing": tmp_path / "precious",
    }
    (tmp_path / "precious").mkdir()
    with pytest.raises(p.ProvenanceError):
        w.preflight(source, options[target], plots=False)
    assert not source.exists()


def test_missing_plot_dependency_fails_preflight(tmp_path, monkeypatch):
    monkeypatch.setattr(w.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(p.ProvenanceError, match="reports extra"):
        w.preflight(tmp_path / "source", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_storage_failure_does_not_retry_or_publish_job(tmp_path, monkeypatch):
    source, output = tmp_path / "capture", tmp_path / "published"
    SYNTHETIC["run"](source)
    before = tree(source)
    calls = []

    def fail(*args, **kwargs):
        calls.append(True)
        raise OSError("injected report write failure")

    monkeypatch.setattr(w.r, "export", fail)
    with pytest.raises(OSError):
        w.publish(source, output, plots=False)
    assert calls == [True] and tree(source) == before
    assert not (output / "artifacts.json").exists()
    assert not (output / "job.json").exists()
    assert json.loads((output / "failure.json").read_text())["report_status"] == "failed"


def test_unsealed_capture_fails_without_output(tmp_path):
    source = tmp_path / "capture"
    source.mkdir()
    (source / "workflow.json").write_text('{"status":"running"}')
    with pytest.raises(p.ProvenanceError):
        w.publish(source, tmp_path / "never-published", plots=False)
    assert not (tmp_path / "never-published").exists()


@pytest.mark.parametrize("scenario,code", [("nominal", 0), ("timeout", 1), ("cancel", 1)])
def test_single_command_synthetic_capture_to_report(tmp_path, scenario, code):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/exercise_workflow.py"),
            "--output",
            str(tmp_path / "capture"),
            "--scenario",
            scenario,
            "--report-output",
            str(tmp_path / "published"),
            "--report-no-plots",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == code, result.stderr
    summary = json.loads((tmp_path / "published/job.json").read_text())
    assert summary["execution"] == (
        "completed"
        if scenario == "nominal"
        else "interrupted"
        if scenario == "cancel"
        else "failed"
    )
    assert (tmp_path / "published/report/report.html").exists()


def test_saved_bundle_cli_and_output_conflict(tmp_path):
    source, output = tmp_path / "capture", tmp_path / "published"
    SYNTHETIC["run"](source)
    args = ["--bundle", str(source), "--output", str(output), "--no-plots"]
    assert w.main(args) == 0
    assert w.main(args) == 2
    assert json.loads((output / "job.json").read_text())["analysis"] == "deterministic_only"


def test_existing_report_output_prevents_any_synthetic_capture(tmp_path):
    output, source = tmp_path / "precious", tmp_path / "capture"
    output.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/exercise_workflow.py"),
            "--output",
            str(source),
            "--report-output",
            str(output),
            "--report-no-plots",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0 and not source.exists()


def test_plotted_deterministic_job(tmp_path):
    pytest.importorskip("matplotlib")
    source, output = tmp_path / "capture", tmp_path / "published"
    SYNTHETIC["run"](source)
    w.publish(source, output)
    assert (output / "report/power.png").read_bytes().startswith(b"\x89PNG")
    assert "<svg" in (output / "report/power.svg").read_text()
