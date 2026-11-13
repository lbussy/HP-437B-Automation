"""Report-only operator recovery: native readers, immutable sources, and isolated attempts."""

import fcntl
import json
import uuid

import pytest
import test_operator_ui as ui_tests
import test_physical_workflow as wf1
import test_repeatability_physical as wf3
import test_stability_physical as wf2

from hp437b import operator_jobs as jobs
from hp437b import report_delivery, report_recovery
from hp437b import reporting as r

pytest.importorskip("reportlab")


@pytest.fixture
def manager(tmp_path):
    obj = jobs.Jobs(tmp_path / "runs", plots=False)
    try:
        yield obj
    finally:
        obj.close()


@pytest.fixture(params=[("WF-01", wf1), ("WF-02", wf2), ("WF-03", wf3)])
def source(manager, request, monkeypatch):
    kind, module = request.param
    path = manager.root / uuid.uuid4().hex
    path.mkdir()
    module.harness.__wrapped__(monkeypatch).run(path / "capture")
    jobs.atomic(
        path / "request.json",
        dict(
            schema="hp437b.operator-request.v1",
            job_id=path.name,
            mode="physical",
            profile=dict(dut=dict(name="Internal POWER REF"), profile_id="saved", operator=None),
            workflows=[kind],
            operator=None,
            plots=False,
            started_utc="2026-11-12T00:00:00+00:00",
        ),
    )
    jobs.atomic(
        path / "state.json",
        dict(
            job_id=path.name,
            phase="failed",
            current=None,
            index=1,
            total=1,
            results=[],
            outcome="completed",
            error="Original report failed",
        ),
    )
    return path


def snapshot(path):
    return {
        str(p.relative_to(path)): r.digest(p.read_bytes())
        for p in path.rglob("*")
        if p.is_file() and p.name != ".capture.lock"
    }


def test_native_report_recovery_without_bench_config_or_confirmation(manager, source):
    # An original report failure and pending front-panel attestation do not require reacquisition.
    assert manager.reference_config is None and manager.pending_reference() == source.name
    (source / "report").mkdir()
    (source / "report/original.txt").write_text("Retain the original report, even if incomplete")
    original = snapshot(source)
    request = manager.regenerate_reports(source.name)
    result = ui_tests.wait(manager, request["job_id"])
    assert result["phase"] == "finished" and result["mode"] == "report_recovery"
    assert (
        result["source_job_id"] == source.name and result["pdf_ready"] and result["package_ready"]
    )
    assert manager.pending_reference() == source.name and not result["front_panel_confirmed"]
    saved = manager.root / result["job_id"]
    assert not (saved / "capture").exists()
    assert report_delivery.verify(saved / "report.zip")["mode"] == "physical"
    assert snapshot(source) == original
    assert manager.artifact(result["job_id"], "report.pdf")[0].startswith(b"%PDF")
    assert manager.state()["report_sources"][0]["job_id"] == source.name
    with pytest.raises(ValueError):
        manager.regenerate_reports(result["job_id"])


def test_input_and_busy_guards(manager, source):
    for name in ["../escape", "bad", [], None]:
        with pytest.raises(ValueError):
            manager.regenerate_reports(name)
    state = jobs.read(source / "state.json")
    jobs.atomic(source / "state.json", {**state, "phase": "running"})
    with pytest.raises(ValueError, match="close"):
        manager.regenerate_reports(source.name)
    jobs.atomic(source / "state.json", state)
    inventory = source / "capture/artifacts.json"
    inventory.unlink()
    with pytest.raises((ValueError, OSError)):
        manager.regenerate_reports(source.name)
    assert len(list(manager.root.glob("*/request.json"))) == 1


def test_tampered_source_and_capture_lock_refused(manager, source):
    req = jobs.read(source / "request.json")
    digest = report_recovery.inspect(source, req)
    before = snapshot(source)
    with (source / ".capture.lock").open("a+b") as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="still owns"):
            report_recovery.publish(source, manager.root / "blocked", req, digest, plots=False)
    assert snapshot(source) == before
    with pytest.raises(ValueError, match="changed"):
        report_recovery.publish(source, manager.root / "changed", req, "0" * 64, plots=False)
    capture = source / "capture"
    actual = source / "saved"
    capture.rename(actual)
    capture.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        report_recovery.inspect(source, req)


def test_partial_publication_failure_new_attempt_preserves_original(manager, source, monkeypatch):
    original = snapshot(source)
    # Run the report worker in-process to inject a publication failure after output creation.
    import subprocess

    popen = subprocess.Popen

    def spawn(command, *args, **kwargs):
        if command[1:3] == ["-m", "hp437b.operator_jobs"]:
            return type("Done", (), {"poll": lambda _: 0})()
        return popen(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spawn)
    first = manager.regenerate_reports(source.name)

    def fail(source_job, output, *args, **kwargs):
        output.mkdir()
        (output / "partial.txt").write_text("failed report output")
        raise OSError("disk error while creating report")

    with monkeypatch.context() as scope:
        scope.setattr(report_recovery, "publish", fail)
        with pytest.raises(OSError):
            jobs.worker(manager.root / first["job_id"])
    manager.state()
    assert manager.get(first["job_id"])["phase"] == "failed"
    second = manager.regenerate_reports(source.name)
    jobs.worker(manager.root / second["job_id"])
    manager.state()
    assert manager.get(second["job_id"])["phase"] == "finished"
    assert second["job_id"] != first["job_id"]
    assert (
        manager.root / first["job_id"] / "report/partial.txt"
    ).read_text() == "failed report output"
    assert snapshot(source) == original


def test_http_recovery_auth_and_exact_body(manager, source):
    import urllib.error

    generator = ui_tests.http_server.__wrapped__()
    create = next(generator)
    try:
        _, _, request, _, _ = create(manager)
        with pytest.raises(urllib.error.HTTPError):
            request(
                "/api/report-recovery",
                dict(source_job_id=source.name),
                {"Origin": "http://elsewhere"},
            )
        with pytest.raises(urllib.error.HTTPError):
            request("/api/report-recovery", dict(source_job_id=source.name, resource="USB0::evil"))
        with request("/api/report-recovery", dict(source_job_id=source.name)) as response:
            started = json.loads(response.read())
        assert ui_tests.wait(manager, started["job_id"])["phase"] == "finished"
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


@pytest.mark.parametrize("interrupted", [False, True])
def test_combined_capture_recovery_retains_execution_and_selection(
    manager, monkeypatch, interrupted
):
    from hp437b import reference_suite as suite

    path = manager.root / uuid.uuid4().hex
    path.mkdir()
    request = dict(
        schema="hp437b.operator-request.v1",
        job_id=path.name,
        mode="reference_suite",
        meter_mode="synthetic",
        reference_config=None,
        prepared_setup=None,
        profile=dict(dut=dict(name="Simulated POWER REF"), profile_id="saved", operator=None),
        workflows=list(suite.KINDS),
        operator=None,
        plots=False,
        started_utc="2026-11-12T00:00:00+00:00",
    )

    def capture(target, kind):
        suite.fake_capture(target, kind)
        if interrupted:
            (path / "cancel.requested").touch()

    with monkeypatch.context() as scope:
        scope.setattr(suite, "publish", lambda *a, **k: None)
        suite.run(path, request, lambda **kw: None, capture=capture)
    jobs.atomic(path / "request.json", request)
    jobs.atomic(
        path / "state.json",
        dict(
            job_id=path.name,
            phase="failed",
            current=None,
            index=0,
            total=3,
            results=[],
            outcome="interrupted" if interrupted else "completed",
            error="Report failed",
        ),
    )
    before = snapshot(path)
    job = manager.regenerate_reports(path.name)
    result = ui_tests.wait(manager, job["job_id"])
    assert result["phase"] == "finished", result
    report = manager.root / job["job_id"] / "report"
    values = json.loads((report / "results.json").read_text())
    assert values["execution"] == ("interrupted" if interrupted else "completed")
    assert values["requested_workflows"] == list(suite.KINDS)
    assert len(values["children"]) == (1 if interrupted else 3)
    assert report_delivery.verify(report.with_suffix(".zip"))["mode"] == "synthetic"
    assert before == snapshot(path)
    assert (path / "cancel.requested").exists() is interrupted


def test_report_attempt_is_single_active_job_and_operator_stays_unknown(
    manager, source, monkeypatch
):
    monkeypatch.setenv("HP437B_OPERATOR", "Different report machine operator")
    job = manager.regenerate_reports(source.name)
    with pytest.raises(ValueError, match="active"):
        manager.regenerate_reports(source.name)
    assert ui_tests.wait(manager, job["job_id"])["phase"] == "finished"
    values = json.loads((manager.root / job["job_id"] / "report/results.json").read_text())
    assert values.get("operator") is None
