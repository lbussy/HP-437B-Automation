"""Configured operator names are supplied attribution, never inferred identities."""

import json
import subprocess
import sys
from pathlib import Path
from runpy import run_path

import pytest

from hp437b import provenance as p
from hp437b import report_context as c
from hp437b import workflow_report as w

ROOT = Path(__file__).parents[1]
RUN = run_path(str(ROOT / "tools/exercise_workflow.py"))["run"]


@pytest.mark.parametrize(
    "argument,recorded,environment,name,origin",
    [
        ("  Alice Smith  ", "Bob", "Carol", "Alice Smith", "argument"),
        (None, "Bob", "Carol", "Bob", "capture"),
        (None, None, "Carol", "Carol", "environment"),
        (None, None, None, None, "not_recorded"),
    ],
)
def test_operator_precedence_and_honest_unknown(
    monkeypatch, argument, recorded, environment, name, origin
):
    if environment is None:
        monkeypatch.delenv("HP437B_OPERATOR", raising=False)
    else:
        monkeypatch.setenv("HP437B_OPERATOR", environment)
    context = c.resolve_operator(argument, recorded)
    assert context["value"] == name and context["origin"] == origin
    assert context["basis"] == ("unknown" if name is None else "supplied")


@pytest.mark.parametrize("value", ["", "  ", "a\nb", "a\tb", "x" * 121, False])
def test_invalid_operator_name_rejected(value):
    with pytest.raises(ValueError, match="Operator"):
        c.validate_operator(value)


def test_operator_capture_report_override_and_readonly_history(tmp_path, monkeypatch):
    monkeypatch.setenv("HP437B_OPERATOR", "Environment Name")
    source = tmp_path / "capture"
    RUN(source, operator="Capture Name")
    original = {str(f): f.read_bytes() for f in source.rglob("*") if f.is_file()}
    captured = p.load(p.sidecar_path(source) / "provenance.json")
    assert captured["run"]["facts"]["operator"]["value"] == "Capture Name"
    assert captured["run"]["facts"]["operator"]["basis"] == "supplied"
    for label, override, expected in (
        ("captured", None, "Capture Name"),
        ("override", "Report Assertion", "Report Assertion"),
    ):
        out = tmp_path / label
        job = w.publish(source, out, plots=False, operator=override)
        page = (out / "report/report.html").read_text()
        assert f"<th scope='row'>Operator</th><td>{expected}</td>" in page
        assert "PHYSICAL - recorded test" not in page
        assert job["operator"]["value"] == expected
        assert (
            p.load(out / "provenance/provenance.json")["run"]["facts"]["operator"]["value"]
            == "Capture Name"
        )
        report = json.loads((out / "report/artifacts.json").read_text())
        assert report["report_context"]["operator"]["value"] == expected
    assert original == {str(f): f.read_bytes() for f in source.rglob("*") if f.is_file()}


def test_single_command_records_configured_operator_before_capture(tmp_path, monkeypatch):
    monkeypatch.setenv("HP437B_OPERATOR", "Environment Operator")
    source, output = tmp_path / "capture", tmp_path / "report"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/exercise_workflow.py"),
            "--output",
            str(source),
            "--report-output",
            str(output),
            "--report-no-plots",
            "--operator",
            "CLI Operator",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((source / "workflow.json").read_text())["operator"] == "CLI Operator"
    assert json.loads((output / "job.json").read_text())["operator"]["origin"] == "capture"
    assert "CLI Operator" in (output / "report/report.html").read_text()


def test_invalid_operator_prevents_new_capture(tmp_path):
    source = tmp_path / "capture"
    with pytest.raises(ValueError):
        RUN(source, operator="bad\nname")
    assert not source.exists()
