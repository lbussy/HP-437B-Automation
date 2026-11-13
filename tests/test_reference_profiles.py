"""Reference profiles reuse immutable selections/criteria without changing acquisition."""

import copy
import json

import pytest
import test_operator_ui as ui_tests
import test_report_recovery as recovery_tests

from hp437b import acceptance_review as a
from hp437b import operator_jobs as jobs
from hp437b import reference_profiles as profiles
from hp437b import report_delivery

manager = recovery_tests.manager
source = recovery_tests.source


def document(kinds=None, limits=False):
    kinds = kinds or ["WF-01"]
    return dict(
        schema=profiles.SCHEMA,
        profile_id="fictional-reference-check",
        revision=1,
        description="Illustrative software check only; not DUT specifications",
        subject="Internal POWER REF",
        operator="Profile operator",
        workflows=kinds,
        criteria=dict(
            schema=a.SCHEMA,
            source="Illustrative software checks, not DUT specifications" if limits else None,
            decision_rule=a.RULE,
            workflows={
                k: dict(mean_min_mW="0.5", mean_max_mW="1.5", min_valid_samples=1, max_gap_s="500")
                if limits
                else {}
                for k in kinds
            },
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "subject",
        "extra",
        "revision",
        "boolean",
        "order",
        "empty",
        "limits",
        "unattributed",
        "resource",
    ],
)
def test_invalid_profile_rejected_before_storage(manager, change):
    doc = document()
    if change == "schema":
        doc["schema"] = "unknown"
    if change == "subject":
        doc["subject"] = "A radio"
    if change == "extra":
        doc["dut"] = {}
    if change == "revision":
        doc["revision"] = 0
    if change == "boolean":
        doc["revision"] = True
    if change == "order":
        doc["workflows"] = ["WF-03", "WF-01"]
    if change == "empty":
        doc["workflows"] = []
    if change == "limits":
        doc["criteria"]["workflows"]["WF-02"] = {}
    if change == "unattributed":
        doc["criteria"]["workflows"]["WF-01"] = dict(mean_min_mW="1")
    if change == "resource":
        doc["resource"] = "USB::anything"
    with pytest.raises((ValueError, TypeError)):
        manager.save_reference_profile(doc)
    assert list(manager.reference_profile_root.iterdir()) == []


def test_revisions_content_addressed_and_detached(manager):
    doc = document()
    key = manager.save_reference_profile(doc)
    assert manager.save_reference_profile(copy.deepcopy(doc)) == key
    doc["description"] = "Changed"
    with pytest.raises(ValueError, match="increment"):
        manager.save_reference_profile(doc)
    assert manager.reference_profile(key)["description"] != "Changed"
    doc["revision"] = 2
    key2 = manager.save_reference_profile(doc)
    assert key2 != key and len(manager.state()["reference_profiles"]) == 2
    binding = profiles.bind(doc, "before_capture")
    binding["profile"]["description"] = "Tampered"
    with pytest.raises(ValueError, match="hash"):
        profiles.validate_binding(binding, doc["workflows"], doc["criteria"])


def test_simulated_profile_runs_and_automatically_assesses(manager):
    key = manager.save_reference_profile(document(limits=True))
    job = manager.start_reference_profile(key, "synthetic", None, {})
    result = ui_tests.wait(manager, job["job_id"])
    assert result["phase"] == "finished", result
    assert result["outcome"] == "completed" and result["assessment_outcome"] == "Pass"
    assert result["assessment_ready"] and result["operator"] == "Profile operator"
    path = manager.root / job["job_id"]
    meta = jobs.read(path / "assessment/metadata.json")
    assert meta["test_profile"]["selected"] == "before_capture"
    assert meta["test_profile"]["profile_sha256"] == key
    assert a.validate_pair(path / "capture", path / "assessment")
    assert report_delivery.verify(path / "assessment.zip")["mode"] == "synthetic"
    assert manager.artifact(job["job_id"], "assessment/report.pdf")[0].startswith(b"%PDF")
    assert manager.artifact(job["job_id"], "assessment/package.zip")[0].startswith(b"PK")
    assert jobs.read(path / "capture/reference-suite.json")["operator"] == "Profile operator"
    # Later profile revisions cannot rewrite this run or its sealed assessment.
    doc = document(limits=True)
    doc["revision"] = 2
    doc["operator"] = "Later operator"
    manager.save_reference_profile(doc)
    assert jobs.read(path / "assessment/metadata.json") == meta
    from pypdf import PdfReader

    reader = PdfReader(path / "assessment/report.pdf")
    assert len(reader.pages) == 1
    assert "selected before capture" in reader.pages[0].extract_text()


def test_no_criteria_is_not_evaluated_and_operator_override(manager):
    key = manager.save_reference_profile(document())
    result = ui_tests.wait(
        manager, manager.start_reference_profile(key, "synthetic", "Override", {})["job_id"]
    )
    assert result["phase"] == "finished" and result["assessment_outcome"] == "Not evaluated"
    assert result["operator"] == "Override"


def test_saved_profile_assessment_preserves_originals(manager, source):
    kind = jobs.read(source / "request.json")["workflows"][0]
    key = manager.save_reference_profile(document([kind], limits=True))
    before = recovery_tests.snapshot(source)
    job = ui_tests.wait(
        manager, manager.assess_reference_profile(source.name, key, "Saved assessor")["job_id"]
    )
    assert job["phase"] == "finished", job
    output = manager.root / job["job_id"] / "report"
    meta = jobs.read(output / "metadata.json")
    assert (
        meta["test_profile"]["selected"] == "post_capture" and meta["assessor"] == "Saved assessor"
    )
    assert a.validate_pair(source / "capture", output)
    assert recovery_tests.snapshot(source) == before
    key2 = manager.save_reference_profile(
        {**document([kind]), "profile_id": "different", "workflows": ["WF-01", "WF-02", "WF-03"]}
    )
    with pytest.raises(ValueError, match="workflow selection"):
        manager.assess_reference_profile(source.name, key2, None)


def test_physical_requires_existing_configuration_and_fresh_preparation(manager):
    key = manager.save_reference_profile(document())
    with pytest.raises(ValueError, match="not enabled"):
        manager.start_reference_profile(key, "physical", None, {})
    with pytest.raises(ValueError, match="source"):
        manager.start_reference_profile(key, None, None, {})
    assert not [x for x in manager.root.iterdir() if jobs.ID.fullmatch(x.name)]


def test_profile_http_origin_and_strict_requests(manager):
    generator = ui_tests.http_server.__wrapped__()
    create = next(generator)
    try:
        _, _, request, _, _ = create(manager)
        result = json.load(request("/api/reference-profiles", dict(profile=document())))
        key = result["key"]
        result = json.load(
            request(
                "/api/reference-profile-run",
                dict(profile_key=key, meter_mode="synthetic", operator=None, prepared={}),
            )
        )
        assert ui_tests.wait(manager, result["job_id"])["assessment_outcome"] == "Not evaluated"
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def queued(manager, monkeypatch, doc):
    class Process:
        def __init__(self, *args, **kwargs):
            pass

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    with monkeypatch.context() as patch:
        patch.setattr(jobs.subprocess, "Popen", Process)
        key = manager.save_reference_profile(doc)
        job = manager.start_reference_profile(key, "synthetic", None, {})
    manager.process = None
    manager.active_id = None
    if manager.log:
        manager.log.close()
        manager.log = None
    return manager.root / job["job_id"]


def test_combined_profile_and_portable_snapshot(manager):
    doc = document(["WF-01", "WF-02", "WF-03"], limits=True)
    key = manager.save_reference_profile(doc)
    result = ui_tests.wait(
        manager, manager.start_reference_profile(key, "synthetic", None, {})["job_id"]
    )
    assert result["phase"] == "finished", result
    assert result["outcome"] == "completed" and result["assessment_ready"]
    assert result["assessment_outcome"] == "Pass"
    path = manager.root / result["job_id"]
    meta = jobs.read(path / "assessment/metadata.json")
    assert meta["test_profile"]["profile"] == profiles.validate(doc)
    assert report_delivery.verify(path / "assessment.zip")["mode"] == "synthetic"
    from pypdf import PdfReader

    assert len(PdfReader(path / "assessment/report.pdf").pages) == 1


def test_assessment_failure_keeps_capture_and_allows_report_only_retry(manager, monkeypatch):
    path = queued(manager, monkeypatch, document(limits=True))
    original = a.publish
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise OSError("Injected assessment disk failure")

    monkeypatch.setattr(a, "publish", fail)
    jobs.worker(path)
    result = manager.get(path.name)
    assert result["phase"] == "finished" and result["outcome"] == "completed"
    assert result["pdf_ready"] and not result["assessment_ready"]
    assert "disk failure" in result["assessment_error"] and calls == [1]
    before = recovery_tests.snapshot(path / "capture")
    monkeypatch.setattr(a, "publish", original)
    key = jobs.read(path / "request.json")["test_profile"]["profile_sha256"]
    retry = ui_tests.wait(manager, manager.assess_reference_profile(path.name, key, None)["job_id"])
    assert retry["assessment_outcome"] == "Pass"
    assert before == recovery_tests.snapshot(path / "capture")


def test_cancelled_profile_is_not_evaluated_and_later_tests_do_not_run(manager, monkeypatch):
    path = queued(manager, monkeypatch, document(["WF-01", "WF-02", "WF-03"], limits=True))
    (path / "cancel.requested").touch()
    jobs.worker(path)
    result = manager.get(path.name)
    assert result["outcome"] == "interrupted" and result["assessment_outcome"] == "Not evaluated"
    assert not list((path / "capture/captures").iterdir())
    assert jobs.read(path / "assessment/results.json")["outcome"] == "Not evaluated"


@pytest.mark.parametrize("mutation", ["hash", "timing", "criteria", "workflow"])
def test_changed_snapshot_refused_before_capture(manager, monkeypatch, mutation):
    path = queued(manager, monkeypatch, document(limits=True))
    request = jobs.read(path / "request.json")
    binding = request["test_profile"]
    if mutation == "hash":
        binding["profile_sha256"] = "0" * 64
    if mutation == "timing":
        binding["selected"] = "unknown"
    if mutation == "criteria":
        binding["profile"]["criteria"]["source"] = "Other"
    if mutation == "workflow":
        request["workflows"] = ["WF-02"]
    jobs.atomic(path / "request.json", request)
    with pytest.raises(ValueError):
        jobs.worker(path)
    assert manager.get(path.name)["phase"] == "failed"
    assert not (path / "capture").exists()


def test_http_rejects_cross_origin_and_extra_controls(manager):
    import urllib.error

    generator = ui_tests.http_server.__wrapped__()
    create = next(generator)
    try:
        _, _, request, _, _ = create(manager)
        with pytest.raises(urllib.error.HTTPError):
            request(
                "/api/reference-profiles",
                dict(profile=document()),
                headers={"Origin": "http://evil.example"},
            )
        assert not manager.reference_catalog()[0]
        with pytest.raises(urllib.error.HTTPError):
            request("/api/reference-profiles", dict(profile=document(), resource="USB"))
        assert not manager.reference_catalog()[0]
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_profile_physical_launch_uses_existing_runner_and_keeps_final_confirmation(
    manager, monkeypatch
):
    import sys
    from pathlib import Path

    import test_physical_workflow as wf1
    import test_stability_physical as wf2

    from hp437b import operator_reference as ref

    setup = wf2.setup()
    manager.reference_config = dict(
        root=str(Path(__file__).parents[1]),
        python=sys.executable,
        resource=wf2.RESOURCE,
        setup=setup,
    )

    class Process:
        def __init__(self, *args, **kwargs):
            pass

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    key = manager.save_reference_profile(document(limits=True))
    with pytest.raises(ValueError, match="Fresh prepared"):
        manager.start_reference_profile(key, "physical", None, {})
    with monkeypatch.context() as patch:
        patch.setattr(jobs.subprocess, "Popen", Process)
        started = manager.start_reference_profile(
            key, "physical", None, dict.fromkeys(ref.PREPARED, True)
        )
    manager.process = None
    manager.active_id = None
    if manager.log:
        manager.log.close()
        manager.log = None
    path = manager.root / started["job_id"]
    calls = []

    def supervise(step, request, **kwargs):
        calls.append(request["workflows"])
        harness = wf1.harness.__wrapped__(monkeypatch)
        harness.run(step / "capture", setup_override=setup)
        assert all(w.closed for w in harness.wires)

    monkeypatch.setattr(ref, "supervise", supervise)
    jobs.worker(path)
    result = manager.get(path.name)
    assert calls == [["WF-01"]] and result["phase"] == "finished"
    assert result["assessment_outcome"] == "Pass" and result["assessment_ready"]
    assert not result["front_panel_confirmed"] and manager.pending_reference() == path.name
    assert report_delivery.verify(path / "assessment.zip")["mode"] == "physical"
    with pytest.raises(ValueError, match="front-panel"):
        manager.start_reference_profile(key, "physical", None, dict.fromkeys(ref.PREPARED, True))
