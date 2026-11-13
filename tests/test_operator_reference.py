"""POWER REF UI integration through existing injected transports; no physical I/O."""

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
from hp437b import reference_report as reports
from hp437b import report_delivery as delivery
from hp437b import reporting as r

ROOT = Path(__file__).parents[1]


@pytest.fixture
def local_http_server():
    yield from ui_tests.http_server.__wrapped__()


@pytest.fixture(params=[("WF-01", wf1), ("WF-02", wf2), ("WF-03", wf3)])
def native(request, monkeypatch):
    kind, module = request.param
    return kind, module, module.harness.__wrapped__(monkeypatch)


def test_native_reference_delivery_and_immutable_capture(tmp_path, native):
    pytest.importorskip("reportlab")
    kind, module, harness = native
    source = tmp_path / "capture"
    harness.run(source)
    before = {
        str(path.relative_to(source)): r.digest(path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "report"
    result = reports.publish(source, output, kind, plots=False, operator="Operator test")
    assert result["execution"] == "completed" and result["acceptance"] == "NOT EVALUATED"
    assert delivery.verify(tmp_path / "report.zip")["mode"] == "physical"
    assert before == {
        str(path.relative_to(source)): r.digest(path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }
    assert reports.validate_pair(source, output) == result["run_id"]
    assert "SYNTHETIC - fictional" not in (output / "report.html").read_text()
    from pypdf import PdfReader

    reader = PdfReader(output / "report.pdf")
    text = reader.pages[0].extract_text()
    assert len(reader.pages) == 1 and "POWER REF" in text and "Pre-RF zero" in text
    assert "SYNTHETIC -" not in text and "Operator test" in text
    (output / "results.json").write_text("{}")
    with pytest.raises(ValueError):
        delivery.package(source, output, tmp_path / "changed.zip")


def test_stage_boundary_cancellation_uses_native_cleanup(tmp_path, native):
    kind, module, harness = native
    original = module.MODULE["execute"].__globals__["Controller"]

    # A request after an RF-on capture/settling stage uses healthy source-off cleanup.
    class RequestAfterBaseline(original):
        def done(self):
            super().done()
            if self.stage in ("S30", "settling") or self.stage.endswith("-plateau"):
                (tmp_path / "cancel.requested").touch()

    module.MODULE["execute"].__globals__["Controller"] = RequestAfterBaseline
    try:
        with ref.observing(module.MODULE, tmp_path):
            result = harness.run(tmp_path / "capture")
        assert result["status"] == "interrupted"
        assert result["final_state"]["source"] == "off"
        assert all(wire.closed for wire in harness.wires)
    finally:
        module.MODULE["execute"].__globals__["Controller"] = original


def test_configuration_and_confirmation_do_not_open_devices(
    tmp_path, monkeypatch, local_http_server
):
    pytest.importorskip("reportlab")
    setup = tmp_path / "setup.json"
    setup.write_text(json.dumps(wf2.setup()))
    config = ref.configuration(ROOT, setup, wf2.RESOURCE, sys.executable)
    manager = jobs.Jobs(tmp_path / "runs", plots=False, reference_config=config)
    try:
        assert manager.state()["reference"]["sensor_serial"] == "FAKE-SENSOR"
        before = set(manager.root.iterdir())
        for kind, prepared in [
            ("WF-99", dict.fromkeys(ref.PREPARED, True)),
            ("WF-01", {}),
            ("WF-02", dict.fromkeys(ref.PREPARED, False)),
        ]:
            with pytest.raises(ValueError):
                manager.start_reference(kind, None, prepared)
        assert set(manager.root.iterdir()) == before
        job_id = "d" * 32
        path = manager.root / job_id
        path.mkdir()
        jobs.atomic(
            path / "request.json",
            dict(
                mode="physical",
                job_id=job_id,
                profile=dict(
                    dut=dict(name="Internal POWER REF"), profile_id="reference", operator=None
                ),
                workflows=["WF-01"],
                operator=None,
                started_utc="2026-11-13T00:00:00+00:00",
            ),
        )
        jobs.atomic(
            path / "state.json",
            dict(job_id=job_id, phase="failed", current=None, results=[], outcome=None),
        )
        with pytest.raises(ValueError, match="prior physical"):
            manager.start_reference("WF-01", None, dict.fromkeys(ref.PREPARED, True))
        with pytest.raises(ValueError):
            manager.confirm_reference(job_id, "Test", False)
        _, _, request, _, _ = local_http_server(manager)
        with request(
            "/api/reference-confirm", dict(job_id=job_id, operator="Test", confirmed=True)
        ) as response:
            assert json.load(response)["front_panel_confirmed"]
        assert (path / "operator-confirmation.json").is_file()
        with pytest.raises(ValueError):
            manager.confirm_reference(job_id, None, True)
    finally:
        manager.close()


def test_worker_bridge_reports_only_after_native_closure(tmp_path, native, monkeypatch):
    pytest.importorskip("reportlab")
    kind, module, harness = native
    request = dict(workflows=[kind], plots=False, operator="Bridge operator")
    events = []

    def completed(path, request, **kwargs):
        harness.run(path / "capture")
        assert all(wire.closed for wire in harness.wires)

    monkeypatch.setattr(ref, "supervise", completed)
    ref.run(tmp_path, request, lambda **event: events.append(event))
    assert [item["phase"] for item in events] == ["running", "reporting", "finished"]
    assert events[1]["final_state"]["source"] == "off"
    assert delivery.verify(tmp_path / "report.zip")["mode"] == "physical"


def test_existing_capture_lock_prevents_false_front_panel_confirmation(tmp_path):
    import fcntl

    pytest.importorskip("reportlab")
    manager = jobs.Jobs(tmp_path / "runs", plots=False)
    job_id = "a" * 32
    path = manager.root / job_id
    path.mkdir()
    jobs.atomic(
        path / "request.json",
        dict(
            mode="physical",
            job_id=job_id,
            profile=dict(dut=dict(name="POWER REF"), profile_id="reference", operator=None),
            workflows=["WF-01"],
            operator=None,
            started_utc="2026-11-13T00:00:00+00:00",
        ),
    )
    jobs.atomic(
        path / "state.json",
        dict(job_id=job_id, phase="failed", current=None, results=[], outcome=None),
    )
    try:
        with (path / ".capture.lock").open("a+b") as guard:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with pytest.raises(ValueError, match="still owns"):
                manager.confirm_reference(job_id, None, True)
        assert manager.confirm_reference(job_id, None, True)["front_panel_confirmed"]
    finally:
        manager.close()


def test_physical_start_snapshots_fresh_preparation_and_pins_process(
    tmp_path, monkeypatch, local_http_server
):
    pytest.importorskip("reportlab")
    setup = tmp_path / "setup.json"
    setup.write_text(json.dumps(wf2.setup()))
    config = ref.configuration(ROOT, setup, wf2.RESOURCE, sys.executable)
    manager = jobs.Jobs(tmp_path / "runs", plots=False, reference_config=config)
    launches = []

    class Process:
        def __init__(self, command, **kwargs):
            launches.append((command, kwargs))

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    try:
        _, _, request, _, _ = local_http_server(manager)
        with request(
            "/api/reference",
            dict(
                workflow="WF-01",
                operator="Fresh operator",
                prepared=dict.fromkeys(ref.PREPARED, True),
            ),
        ) as response:
            result = json.load(response)
        assert result["active"] and result["mode"] == "physical"
        path = manager.root / result["job_id"]
        saved = jobs.read(path / "request.json")
        assert (
            saved["prepared_setup"]["confirmation_origin"]
            == "Operator freshly confirmed each setup item in the local UI"
        )
        assert saved["prepared_setup"]["operator"] == "Fresh operator"
        assert saved["reference_config"]["resource"] == wf2.RESOURCE
        assert launches[0][0][:3] == [sys.executable, "-m", "hp437b.operator_jobs"]
        assert launches[0][1]["pass_fds"] and "shell" not in launches[0][1]
        with pytest.raises(ValueError):
            manager.confirm_reference(result["job_id"], None, True)
        manager.cancel(result["job_id"])
        assert (path / "cancel.requested").is_file()
    finally:
        manager.close()
