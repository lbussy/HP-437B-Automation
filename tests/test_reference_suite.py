"""Reference-suite orchestration over synthetic captures and injected native runners."""

import json
import sys
from pathlib import Path

import pytest
import test_operator_ui as ui_tests
import test_physical_workflow as wf1
import test_repeatability_physical as wf3
import test_stability_physical as wf2

from hp437b import operator_jobs as jobs
from hp437b import operator_reference as ref
from hp437b import reference_suite as s
from hp437b import report_delivery as delivery
from hp437b import reporting as r
from hp437b.workflow_report import _seal


def request(mode="synthetic", kinds=None):
    return dict(
        workflows=kinds or list(s.KINDS),
        meter_mode=mode,
        operator="Suite operator",
        plots=False,
        reference_config=None,
        prepared_setup=None,
    )


def execute(tmp_path, req=None, **kwargs):
    path = tmp_path / "job"
    path.mkdir()
    result = s.run(path, req or request(), lambda **event: None, **kwargs)
    return path, result


def reseal(source):
    record = json.loads((source / "reference-suite.json").read_text())
    (source / "artifacts.json").unlink()
    _seal(source, dict(schema=s.SCHEMA, run_id=record["run_id"], mode=record["mode"]))


@pytest.mark.parametrize(
    "kinds", [[], ["WF-04"], ["WF-02", "WF-01"], ["WF-01", "WF-01"], "WF-01", [True]]
)
def test_selection_rejected_before_output(kinds):
    with pytest.raises(ValueError):
        s.selection(kinds)


def test_three_fake_workflows_report_package_and_source_preservation(tmp_path):
    pytest.importorskip("reportlab")
    path, result = execute(tmp_path)
    assert result["execution"] == "completed" and len(result["children"]) == 3
    assert all(x["safe_to_advance"] for x in result["children"])
    assert delivery.verify(path / "report.zip")["mode"] == "synthetic"
    from pypdf import PdfReader

    reader = PdfReader(path / "report/report.pdf")
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "SYNTHETIC" in text and "POWER REF suite" in text and "Pre-RF zero" in text
    source = path / "capture"
    before = {
        str(p.relative_to(source)): r.digest(p.read_bytes())
        for p in source.rglob("*")
        if p.is_file()
    }
    s.publish(source, path / "again", plots=False)
    assert s.validate_pair(source, path / "again") == result["run_id"]
    assert before == {
        str(p.relative_to(source)): r.digest(p.read_bytes())
        for p in source.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError):
        s.publish(source, path / "again", plots=False)
    (path / "report/results.json").write_text("{}")
    with pytest.raises(ValueError):
        delivery.package(source, path / "report", path / "changed.zip")


def test_base_fake_capture_and_guards_without_optional_report_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "publish", lambda *a, **k: None)
    _, result = execute(tmp_path)
    assert result["execution"] == "completed" and len(result["children"]) == 3


@pytest.mark.parametrize("after", [0, 1, 2, 3])
def test_cancellation_stops_before_next_workflow_and_preserves_denominator(
    tmp_path, monkeypatch, after
):
    monkeypatch.setattr(s, "publish", lambda *a, **k: None)
    path = tmp_path / "job"
    path.mkdir()
    calls = []
    if after == 0:
        (path / "cancel.requested").touch()

    def capture(target, kind):
        calls.append(kind)
        s.fake_capture(target, kind)
        if len(calls) == after:
            (path / "cancel.requested").touch()

    result = s.run(path, request(), lambda **event: None, capture=capture)
    assert calls == list(s.KINDS)[:after] and len(result["requested_workflows"]) == 3
    assert result["execution"] == ("completed" if after == 3 else "interrupted")
    assert all(x["safe_to_advance"] for x in result["children"])


def test_failed_child_stops_later_capture(tmp_path, monkeypatch):
    from hp437b import stability_simulation

    monkeypatch.setattr(s, "publish", lambda *a, **k: None)
    calls = []

    def capture(target, kind):
        calls.append(kind)
        if kind == "WF-02":
            stability_simulation.run(target, "source-off-failure")
        else:
            s.fake_capture(target, kind)

    _, result = execute(tmp_path, capture=capture)
    assert calls == ["WF-01", "WF-02"] and result["execution"] == "failed"
    assert not result["children"][-1]["safe_to_advance"]
    assert result["final_state"]["source"] == "unknown"


def test_unsealed_child_failure_keeps_partial_files_outside_sealed_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "publish", lambda *a, **k: None)

    def capture(target, kind):
        target.mkdir()
        (target / "partial.csv").write_text("partial")
        raise TimeoutError("uncertain read; no retry")

    path, result = execute(tmp_path, capture=capture)
    assert result["execution"] == "failed" and not result["children"]
    assert (path / "unfinished/WF-01/partial.csv").read_text() == "partial"
    assert result["final_state"]["source"] == "unknown"


@pytest.mark.parametrize("mutation", ["hash", "summary", "order", "mode", "final"])
def test_resealed_summary_or_identity_tampering_rejected(tmp_path, monkeypatch, mutation):
    monkeypatch.setattr(s, "publish", lambda *a, **k: None)
    path, _ = execute(tmp_path)
    source = path / "capture"
    f = source / "reference-suite.json"
    v = json.loads(f.read_text())
    if mutation == "hash":
        v["children"][0]["capture_inventory_sha256"] = "0" * 64
    if mutation == "summary":
        v["children"][0]["rows"][0][1] = "invented zero"
    if mutation == "order":
        v["children"].reverse()
    if mutation == "mode":
        v["mode"] = "physical"
    if mutation == "final":
        v["final_state"]["source"] = "on"
    f.write_bytes(r.encoded(v))
    reseal(source)
    with pytest.raises(ValueError):
        s.load(source)


def test_native_runner_supervision_and_closure_between_all_children(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    setup = wf2.setup()
    req = request("physical")
    req.update(
        prepared_setup=setup,
        reference_config=dict(
            root=str(Path(__file__).parents[1]),
            python=sys.executable,
            resource=wf2.RESOURCE,
            setup=setup,
        ),
    )
    calls = []

    def supervise(step, child, *, lock_fd, extra_fds):
        import fcntl

        assert extra_fds and (step / "cancel.requested").is_symlink()
        with (step.parents[1] / ".capture.lock").open("a+b") as guard:
            with pytest.raises(BlockingIOError):
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        kind = child["workflows"][0]
        calls.append(kind)
        module = {"WF-01": wf1, "WF-02": wf2, "WF-03": wf3}[kind]
        harness = module.harness.__wrapped__(monkeypatch)
        harness.run(step / "capture", **({} if kind == "WF-03" else {"setup_override": setup}))
        assert all(w.closed for w in harness.wires)

    monkeypatch.setattr(ref, "supervise", supervise)
    path, result = execute(tmp_path, req)
    assert calls == list(s.KINDS) and result["execution"] == "completed"
    assert all(c["safe_to_advance"] for c in result["children"])
    assert delivery.verify(path / "report.zip")["mode"] == "physical"
    assert "SYNTHETIC" not in (path / "report/report.html").read_text()


def test_report_failure_does_not_reacquire_and_allows_saved_retry(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    calls = []
    original = s.publish

    def fail(*a, **k):
        raise OSError("injected report storage failure")

    monkeypatch.setattr(s, "publish", fail)

    def capture(target, kind):
        calls.append(kind)
        s.fake_capture(target, kind)

    with pytest.raises(OSError):
        execute(tmp_path, capture=capture)
    source = tmp_path / "job/capture"
    assert s.load(source)[1]["execution"] == "completed" and calls == list(s.KINDS)
    original(source, tmp_path / "retry", plots=False)
    assert calls == list(s.KINDS) and delivery.verify(tmp_path / "retry.zip")["mode"] == "synthetic"


def test_suite_http_start_selection_and_fake_preparation_guards(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    manager = jobs.Jobs(tmp_path / "jobs", plots=False)

    class Process:
        def __init__(self, *a, **k):
            pass

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    server_gen = ui_tests.http_server.__wrapped__()
    create = next(server_gen)
    try:
        _, _, send, _, _ = create(manager)
        with pytest.raises(ValueError):
            manager.start_reference_suite(["WF-03", "WF-01"], "synthetic", None, {})
        with pytest.raises(ValueError):
            manager.start_reference_suite(
                ["WF-01"], "physical", None, dict.fromkeys(ref.PREPARED, True)
            )
        with send(
            "/api/reference-suite",
            dict(workflows=list(s.KINDS), meter_mode="synthetic", operator="Test", prepared={}),
        ) as response:
            job = json.load(response)
        assert (
            job["mode"] == "reference_suite"
            and job["meter_mode"] == "synthetic"
            and job["total"] == 3
        )
        saved = jobs.read(manager.root / job["job_id"] / "request.json")
        assert saved["reference_config"] is None and saved["prepared_setup"] is None
        manager.cancel(job["job_id"])
    finally:
        server_gen.close()
        manager.close()


def test_physical_suite_fresh_start_and_separate_confirmation_lock(tmp_path, monkeypatch):
    import fcntl

    pytest.importorskip("reportlab")
    setup = tmp_path / "setup.json"
    setup.write_text(json.dumps(wf2.setup()))
    config = ref.configuration(Path(__file__).parents[1], setup, wf2.RESOURCE, sys.executable)
    manager = jobs.Jobs(tmp_path / "jobs", plots=False, reference_config=config)

    class Process:
        def __init__(self, *a, **k):
            pass

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    try:
        with pytest.raises(ValueError):
            manager.start_reference_suite(["WF-01"], "physical", None, {})
        job = manager.start_reference_suite(
            ["WF-01", "WF-02"], "physical", "Test", dict.fromkeys(ref.PREPARED, True)
        )
        assert (
            job["mode"] == "reference_suite"
            and job["meter_mode"] == "physical"
            and job["total"] == 2
        )
        assert manager.pending_reference() == job["job_id"]
        path = manager.root / job["job_id"]
        saved = jobs.read(path / "request.json")
        assert (
            saved["prepared_setup"]["operator"] == "Test"
            and saved["prepared_setup"]["prepared_record_utc"]
        )
        with pytest.raises(ValueError):
            manager.confirm_reference(job["job_id"], None, True)
        manager.process = None
        manager.active_id = None
        state = jobs.read(path / "state.json")
        state["phase"] = "failed"
        jobs.atomic(path / "state.json", state)
        with (path / ".capture.lock").open("a+b") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(ValueError, match="still owns"):
                manager.confirm_reference(job["job_id"], None, True)
        assert manager.confirm_reference(job["job_id"], "Test", True)["front_panel_confirmed"]
    finally:
        manager.close()
