"""Preparation actions use accepted runners; fakes never discover hardware."""

import json
import urllib.error
from pathlib import Path

import pytest
import test_operator_ui as ui
from test_diagnostics_zero import Backend

from hp437b import operator_jobs as jobs
from hp437b import operator_preparation as prep
from hp437b import reconciliation as rec


@pytest.fixture
def manager(tmp_path):
    pytest.importorskip("reportlab")
    m = jobs.Jobs(tmp_path / "runs", plots=False)
    try:
        yield m
    finally:
        m.close()


def config(tmp_path):
    return dict(
        resource="USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.9::0::INSTR",
        expected_idn="HEWLETT-PACKARD,437B,,1.9",
        meter_serial="FAKE-METER",
        sensor_serial="FAKE-SENSOR",
        workflow_lock_root=str(tmp_path / "locks"),
        known_issues=["Synthetic equipment"],
    )


def args(action="ZERO", mode="synthetic"):
    return dict(
        action=action,
        meter_mode=mode,
        operator="Test operator",
        prepared=dict.fromkeys(prep.keys(action), True) if mode == "physical" else {},
        reference_factor="99" if action == "CAL" else None,
        factor_source="Synthetic label" if action == "CAL" else None,
    )


@pytest.mark.parametrize("action", ["ZERO", "CAL"])
def test_native_simulated_ui_worker_receipts_no_hardware_or_rf_reports(manager, action):
    job = manager.start_preparation(**args(action))
    result = ui.wait(manager, job["job_id"])
    assert result["outcome"] == "completed" and result["preparation_ready"]
    assert not result["pdf_ready"] and not result["package_ready"]
    assert manager.pending_reference() is None
    raw, _, _ = manager.artifact(job["job_id"], "preparation/receipt.json")
    receipt = json.loads(raw)
    assert receipt["evidence_origin"] == "injected_fake" and receipt["transport_closed"]
    assert receipt["local_return"]["simulation"] and receipt["local_return"]["status"] == "accepted"
    assert all(q["status"] == "completed" for q in receipt["queries"])
    assert result["preparation_summary"]["mode"] == "synthetic"
    html, _, _ = manager.artifact(job["job_id"], "preparation/receipt.html")
    assert b"simulation" in html.lower() or b"synthetic" in html.lower()
    assert manager.history(0, "preparation")["total"] == 1
    assert manager.history(0, "measurements")["total"] == 0
    with pytest.raises(ValueError):
        manager.run_details(job["job_id"])
    with pytest.raises(ValueError):
        manager.regenerate_reports(job["job_id"])
    with pytest.raises(ValueError):
        manager.confirm_reference(job["job_id"], None, True)
    path = manager.root / job["job_id"] / "capture/diagnostics.json"
    path.write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="changed"):
        manager.artifact(job["job_id"], "preparation/receipt.json")


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "RESET"},
        {"meter_mode": "remote"},
        {"prepared": {"reference_off": True}},
        {"meter_mode": "physical", "prepared": dict.fromkeys(prep.keys("ZERO"), True)},
        {"action": "CAL", "reference_factor": None, "factor_source": "label"},
        {"action": "CAL", "reference_factor": "99.05", "factor_source": "label"},
        {"action": "CAL", "reference_factor": True, "factor_source": "label"},
        {"action": "CAL", "reference_factor": "99", "factor_source": ""},
        {"reference_factor": "99"},
    ],
)
def test_bad_requests_never_create_job_or_open_meter(manager, overrides):
    original = set(manager.root.iterdir())
    with pytest.raises((ValueError, TypeError)):
        manager.start_preparation(**{**args(), **overrides})
    assert set(manager.root.iterdir()) == original and manager.process is None


@pytest.mark.parametrize(
    "action,scenario",
    [("ZERO", "healthy"), ("CAL", "healthy"), ("CAL", "followup_timeout"), ("CAL", "native_error")],
)
def test_injected_bench_runner_retains_failure_and_local_state(tmp_path, action, scenario):
    pytest.importorskip("reportlab")
    c = config(tmp_path)
    m = jobs.Jobs(tmp_path / "runs", plots=False, preparation_config=c)
    path = m.root / ("a" * 32)
    path.mkdir()
    request = dict(
        mode="meter_preparation",
        job_id=path.name,
        profile=dict(
            dut=dict(name="Meter preparation"), profile_id="meter-preparation", operator=None
        ),
        workflows=[action],
        meter_mode="physical",
        operator=None,
        plots=False,
        started_utc="2026-11-14T00:00:00+00:00",
        preparation_config=c,
        prepared=args(action, "physical")["prepared"],
        reference_factor="99" if action == "CAL" else None,
        factor_source="Synthetic label" if action == "CAL" else None,
    )
    jobs.atomic(path / "request.json", request)
    jobs.atomic(
        path / "state.json",
        dict(job_id=path.name, phase="starting", current=action, results=[], outcome=None),
    )

    def emit(**values):
        s = jobs.read(path / "state.json")
        s.update(values)
        jobs.atomic(path / "state.json", s)

    try:
        prep.run(
            path,
            request,
            emit,
            factory=Backend(tmp_path / "trace.jsonl", scenario, calibration=action == "CAL"),
        )
        result = m.get(path.name)
        receipt = json.loads((path / "capture/diagnostics.json").read_text())
        assert receipt["evidence_origin"] == "injected_fake"
        assert result["outcome"] == ("completed" if scenario == "healthy" else "query_failed")
        assert m.pending_reference() == path.name
        with pytest.raises(ValueError, match="prior"):
            m.start_preparation(**args())
        if scenario == "followup_timeout":
            assert receipt["cal_failed_read_shutdown"]["status"] == "accepted"
        if scenario == "native_error":
            assert receipt.get("local_return") is None
        # An orphaned native worker's resource lease prevents premature attestation.
        lock = Path(c["workflow_lock_root"]) / (jobs.r.digest(c["resource"].encode()) + ".lock")
        with rec._lease(lock):
            with pytest.raises(BlockingIOError):
                m.confirm_reference(path.name, None, True)
        final = m.confirm_reference(path.name, "Observer", True)
        assert final["front_panel_confirmed"] and m.pending_reference() is None
        att = jobs.read(path / "operator-confirmation.json")
        assert att["preparation_receipt_sha256"] == jobs.r.digest(
            (path / "capture/diagnostics.json").read_bytes()
        )
        assert "preparation_receipt_sha256" not in receipt
    finally:
        m.close()


def test_cancel_before_runner_never_starts_zero(tmp_path):
    path = tmp_path / "job"
    path.mkdir()
    (path / "cancel.requested").touch()
    request = dict(
        workflows=["ZERO"],
        meter_mode="synthetic",
        prepared={},
        reference_factor=None,
        factor_source=None,
        operator=None,
        started_utc="now",
    )
    out = {}
    prep.run(path, request, lambda **kw: out.update(kw))
    assert out["outcome"] == "cancelled"
    receipt = jobs.read(path / "capture/diagnostics.json")
    assert receipt["worker"]["stopped"] and not receipt["zero_assessment"]["zero_may_have_started"]


def test_http_explicit_start_and_strict_fields(manager):
    fixture = ui.http_server.__wrapped__()
    serve = next(fixture)
    try:
        _, _, request, _, _ = serve(manager)
        with request("/api/preparation", args()) as response:
            job = json.load(response)
        result = ui.wait(manager, job["job_id"])
        assert result["preparation_ready"]
        with pytest.raises(urllib.error.HTTPError):
            request("/api/preparation", {**args(), "resource": "USB0::other"})
    finally:
        try:
            next(fixture)
        except StopIteration:
            pass


def test_explicit_physical_request_snapshots_context_without_opening(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    c = config(tmp_path)
    m = jobs.Jobs(tmp_path / "runs", plots=False, preparation_config=c)
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
        for missing in prep.keys("CAL"):
            request = args("CAL", "physical")
            request["prepared"][missing] = False
            with pytest.raises(ValueError):
                m.start_preparation(**request)
        assert launches == []
        job = m.start_preparation(**args("CAL", "physical"))
        saved = jobs.read(m.root / job["job_id"] / "request.json")
        assert saved["preparation_config"] == c and saved["reference_factor"] == "99"
        assert saved["started_utc"] and saved["prepared"]["adjustment_confirmed"]
        assert launches[0][1]["pass_fds"] and "shell" not in launches[0][1]
        with pytest.raises(ValueError, match="active"):
            m.start_preparation(**args())
        with pytest.raises(ValueError, match="closed"):
            m.confirm_reference(job["job_id"], None, True)
        m.cancel(job["job_id"])
        assert (m.root / job["job_id"] / "cancel.requested").is_file()
    finally:
        m.close()
