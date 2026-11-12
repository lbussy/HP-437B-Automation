"""Whole-pipeline acceptance: real synthetic workflow, provenance, analysis, and report."""

import copy
import json
from pathlib import Path
from runpy import run_path

import pytest

from hp437b import provenance as p
from hp437b import reporting as r

ROOT = Path(__file__).parents[1]
PIPELINE = run_path(str(ROOT / "tools/accept_pipeline.py"))
WORKFLOW = run_path(str(ROOT / "tools/exercise_workflow.py"))["run"]


@pytest.fixture
def nominal(tmp_path):
    source = tmp_path / "capture"
    WORKFLOW(source)
    return source, p.sidecar_path(source) / "provenance.json"


@pytest.mark.parametrize("scenario", list(PIPELINE["ORACLES"]))
def test_full_fresh_scenario_pipeline(tmp_path, scenario):
    source = tmp_path / "capture"
    WORKFLOW(source, scenario)
    provenance = p.sidecar_path(source) / "provenance.json"
    result = PIPELINE["exercise_case"](
        source,
        provenance,
        tmp_path / "accepted",
        expected=PIPELINE["ORACLES"][scenario],
        plots=False,
    )
    assert result["mode"] == "synthetic"
    assert result["analysis_kind"] == "scripted_interface_fixture"
    report = tmp_path / "accepted/report"
    facts = json.loads((report / "analysis-packet.json").read_text())["facts"]
    assert facts["workflow/final_state"]["value"]["source"] == result["source"]
    if scenario in ("malformed", "timeout"):
        assert result["source"] == "unknown" and result["nonvalid"] == 1
    if scenario == "source-off-failure":
        assert result["execution"] == "failed" and result["s40_valid"] == 300
        assert facts["comparison/baseline_after_minus_before_W"]["value"] is None


def test_full_campaign_has_only_completed_acceptance_manifest(tmp_path):
    output = tmp_path / "campaign"
    result = PIPELINE["campaign"](output, plots=False)
    assert result["acceptance"] == "passed" and result["hardware_io"] is False
    assert len(result["cases"]) == 7
    p.Bundle(output).inventory("artifacts.json", "offline-acceptance")
    with pytest.raises(p.ProvenanceError, match="already exists"):
        PIPELINE["campaign"](output, plots=False)


def test_plotted_whole_pipeline(nominal, tmp_path):
    pytest.importorskip("matplotlib")
    result = PIPELINE["exercise_case"](
        *nominal, tmp_path / "plotted", expected=PIPELINE["ORACLES"]["nominal"], plots=True
    )
    assert result["valid"] == 309


@pytest.mark.parametrize("mutation", ["cross-run", "dangling-ref", "verdict", "extra-command"])
def test_analysis_handoff_failure_never_publishes(nominal, tmp_path, mutation):
    source, provenance = nominal
    _, _, packet = r.prepare(source, provenance)
    analysis = PIPELINE["fixture_analysis"](packet)
    if mutation == "cross-run":
        analysis["run_id"] = "another-run"
    elif mutation == "dangling-ref":
        analysis["findings"][0]["refs"] = ["made-up/metric"]
    elif mutation == "verdict":
        analysis["findings"][0]["kind"] = "pass"
    else:
        analysis["execute"] = "OC1"
    path = tmp_path / "response" / "agent.json"
    path.parent.mkdir()
    path.write_bytes(r.encoded(analysis))
    before = PIPELINE["snapshot"](source)
    output = tmp_path / "rejected"
    with pytest.raises(p.ProvenanceError):
        PIPELINE["exercise_case"](source, provenance, output, analysis=path, plots=False)
    assert not (output / "case.json").exists() and not (output / "report/artifacts.json").exists()
    assert PIPELINE["snapshot"](source) == before


def test_supplied_draft_replayed_without_rebinding(nominal, tmp_path):
    source, provenance = nominal
    _, _, packet = r.prepare(source, provenance)
    agent = PIPELINE["fixture_analysis"](packet)
    path = tmp_path / "drafts/agent.json"
    path.parent.mkdir()
    path.write_bytes(r.encoded(agent))
    before = path.read_bytes()
    result = PIPELINE["exercise_case"](
        source, provenance, tmp_path / "replayed", analysis=path, plots=False
    )
    assert result["analysis_kind"] == "supplied_draft" and path.read_bytes() == before
    assert (tmp_path / "replayed/report/agent-analysis.json").read_bytes() == before


@pytest.mark.parametrize("boundary", ["workflow", "provenance", "report", "agent"])
def test_tampered_pipeline_graph_is_rejected(nominal, tmp_path, boundary):
    source, provenance = nominal
    output = tmp_path / "accepted"
    PIPELINE["exercise_case"](source, provenance, output, plots=False)
    if boundary == "workflow":
        path = source / "workflow.json"
        path.write_text(path.read_text().replace('"completed"', '"failed"', 1))
    elif boundary == "provenance":
        path = output / "imported-provenance/provenance.json"
        data = json.loads(path.read_text())
        data["run"]["run_id"] = "different"
        path.write_bytes(r.encoded(data))
    elif boundary == "report":
        path = output / "report/results.json"
        data = json.loads(path.read_text())
        data["stages"]["S40"]["valid"] = 0
        path.write_bytes(r.encoded(data))
    else:
        path = output / "report/agent-analysis.json"
        data = json.loads(path.read_text())
        data["packet_sha256"] = "0" * 64
        path.write_bytes(r.encoded(data))
    with pytest.raises(p.ProvenanceError):
        PIPELINE["verify_report"](
            source, output / "imported-provenance/provenance.json", output / "report", plots=False
        )


def test_injected_report_storage_failure_has_no_campaign_pass(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("injected acceptance storage failure")

    monkeypatch.setattr(r, "export", fail)
    output = tmp_path / "failed"
    with pytest.raises(OSError, match="storage failure"):
        PIPELINE["campaign"](output, plots=False)
    assert not (output / "artifacts.json").exists()
    assert not (output / "acceptance.json").exists()
    assert json.loads((output / "failure.json").read_text())["acceptance"] == "failed"


def test_retained_manifest_paths_and_input_overlap(nominal, tmp_path):
    source, provenance = nominal
    _, _, packet = r.prepare(source, provenance)
    draft = tmp_path / "drafts/agent.json"
    draft.parent.mkdir()
    draft.write_bytes(r.encoded(PIPELINE["fixture_analysis"](packet)))
    item = {
        "label": "prior-synthetic",
        "bundle": str(source),
        "provenance": str(provenance),
        "analysis": str(draft),
        "expected": list(PIPELINE["ORACLES"]["nominal"]),
    }
    manifest = tmp_path / "retained.json"
    manifest.write_bytes(r.encoded({"schema": "hp437b.retained-cases.v1", "cases": [item]}))
    with pytest.raises(p.ProvenanceError, match="overlaps"):
        PIPELINE["campaign"](source / "dont-write", retained=manifest, plots=False)
    assert not (source / "dont-write").exists()
    value = PIPELINE["campaign"](tmp_path / "with-retained", retained=manifest, plots=False)
    assert len(value["cases"]) == 8
    duplicate = copy.deepcopy(item)
    manifest.write_bytes(
        r.encoded({"schema": "hp437b.retained-cases.v1", "cases": [item, duplicate]})
    )
    with pytest.raises(p.ProvenanceError, match="label"):
        PIPELINE["load_cases"](manifest)


def test_acceptance_requires_guard_and_assertions(tmp_path, monkeypatch):
    monkeypatch.delenv("HP437B_OFFLINE_GUARD")
    with pytest.raises(p.ProvenanceError, match="offline_qa"):
        PIPELINE["campaign"](tmp_path / "never-created", plots=False)
    assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("mutation", ["mean", "mode", "packet-count", "agent-binding"])
def test_resealed_report_semantic_forgery_rejected(nominal, tmp_path, mutation):
    source, provenance = nominal
    output = tmp_path / "accepted"
    PIPELINE["exercise_case"](source, provenance, output, plots=False)
    report = output / "report"
    if mutation == "mean":
        path = report / "results.json"
        value = json.loads(path.read_text())
        value["stages"]["S40"]["metrics"]["mean_W"] = "0.001"
    elif mutation == "mode":
        path = report / "results.json"
        value = json.loads(path.read_text())
        value["mode"] = "physical"
    elif mutation == "packet-count":
        path = report / "analysis-packet.json"
        value = json.loads(path.read_text())
        value["facts"]["S40/valid"]["value"] = 1
        # Rebind the response as well, so independent semantic checks must catch it.
        agent_path = report / "agent-analysis.json"
        agent = json.loads(agent_path.read_text())
        agent["packet_sha256"] = r.digest(r.encoded(value))
        agent_path.write_bytes(r.encoded(agent))
    else:
        path = report / "agent-analysis.json"
        value = json.loads(path.read_text())
        value["packet_sha256"] = "0" * 64
    path.write_bytes(r.encoded(value))
    inventory = json.loads((report / "artifacts.json").read_text())
    for name in inventory["artifacts"]:
        data = (report / name).read_bytes()
        inventory["artifacts"][name] = {"sha256": r.digest(data), "bytes": len(data)}
    (report / "artifacts.json").write_bytes(r.encoded(inventory))
    with pytest.raises(p.ProvenanceError):
        PIPELINE["verify_report"](
            source, output / "imported-provenance/provenance.json", report, plots=False
        )


def test_bundle_code_remains_inert(nominal, tmp_path):
    source, provenance = nominal
    marker = tmp_path / "NEVER-CREATED"
    (source / "runner.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise RuntimeError('bundle code executed')\n"
    )
    inventory = json.loads((source / "artifacts.json").read_text())
    data = (source / "runner.py").read_bytes()
    inventory["artifacts"]["runner.py"] = {"sha256": r.digest(data), "bytes": len(data)}
    (source / "artifacts.json").write_bytes(r.encoded(inventory))
    fresh_provenance = tmp_path / "resealed-provenance"
    p.export_wf01(source, fresh_provenance)
    provenance = fresh_provenance / "provenance.json"
    result = PIPELINE["exercise_case"](source, provenance, tmp_path / "inert", plots=False)
    assert result["execution"] == "completed" and not marker.exists()


@pytest.mark.parametrize("scenario,exit_code", [("nominal", 0), ("timeout", 1)])
def test_cli_workflow_provenance_report_handoff(tmp_path, scenario, exit_code):
    import subprocess
    import sys

    source = tmp_path / "capture"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/exercise_workflow.py"),
            "--output",
            str(source),
            "--scenario",
            scenario,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == exit_code, completed.stderr
    provenance_dir = tmp_path / "cli-provenance"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hp437b.provenance",
            "--bundle",
            str(source),
            "--output",
            str(provenance_dir),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    provenance = provenance_dir / "provenance.json"
    _, _, packet = r.prepare(source, provenance)
    analysis = tmp_path / "agent.json"
    analysis.write_bytes(r.encoded(PIPELINE["fixture_analysis"](packet)))
    output = tmp_path / "cli-report"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "hp437b.reporting",
            "--bundle",
            str(source),
            "--provenance",
            str(provenance),
            "--output",
            str(output),
            "--analysis",
            str(analysis),
            "--no-plots",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    summary = PIPELINE["verify_report"](source, provenance, output, plots=False)
    assert summary["execution"] == PIPELINE["ORACLES"][scenario][0]


def test_input_provenance_inventory_is_required_and_checked(nominal, tmp_path):
    source, provenance = nominal
    provenance.write_bytes(provenance.read_bytes() + b"\n")
    with pytest.raises(p.ProvenanceError, match="mismatch"):
        PIPELINE["exercise_case"](source, provenance, tmp_path / "bad-input", plots=False)
    assert not (tmp_path / "bad-input").exists()
