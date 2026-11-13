"""Guided point authorization, native capture integrity, and local orchestration API."""

import json
import threading
import time
import urllib.error
from datetime import UTC, datetime

import pytest
import test_operator_ui as ui_tests

from hp437b import guided_report as reports
from hp437b import guided_sweep as g
from hp437b import operator_jobs as jobs
from hp437b import report_delivery as delivery
from hp437b import reporting as r
from hp437b.simulation import DemoTransport
from hp437b.workflow_report import _seal


class Gate:
    def __init__(self, *, stop_after=None, mismatch=False):
        self.confirmed = []
        self.stop_after = stop_after
        self.mismatch = mismatch

    def cancelled(self):
        return self.stop_after is not None and len(self.confirmed) >= self.stop_after

    def confirm(self, point, token):
        value = dict(
            **point,
            token=token,
            operator="Bench operator",
            confirmed_utc=datetime.now(UTC).isoformat(),
            frequency_confirmed=True,
            drive_confirmed=True,
        )
        if self.mismatch:
            value["drive"] = "Wrong setting"
        self.confirmed.append(value)
        return value


def quick_plan():
    return {
        **g.example(),
        "frequencies": ["20m"],
        "drives": ["2 mA", "4 mA"],
        "samples": 1,
        "settling_s": 0,
        "interval_s": 0.1,
    }


def config():
    return dict(
        resource="USB0::0x03eb::0x2065::TEST::INSTR",
        meter_serial="TEST meter",
        sensor_serial="TEST sensor",
        known_issues=["Injected transport; no physical evidence"],
        fixture="Fictional test fixture",
    )


def run(tmp_path, plan=None, **kwargs):
    source = tmp_path / "capture"
    result = g.run(source, plan or quick_plan(), kwargs.pop("gate", Gate()), **kwargs)
    return source, result


def test_17_bands_five_labels_and_both_orders():
    plan = g.example()
    plan["drives"].append("Custom label")
    a = g.points(plan)
    assert len(a) == 85 and len(set(x["point_id"] for x in a)) == 85
    assert a[0]["frequency"] == a[4]["frequency"] == "2200m"
    assert a[5]["frequency"] == "630m"
    plan["order"] = "drive"
    b = g.points(plan)
    assert b[0]["drive"] == b[16]["drive"] == "2 mA"
    assert b[17]["drive"] == "4 mA"
    assert {(x["frequency"], x["drive"]) for x in a} == {(x["frequency"], x["drive"]) for x in b}


@pytest.mark.parametrize(
    "key,value",
    [
        ("samples", True),
        ("samples", 0),
        ("samples", 1001),
        ("settling_s", float("nan")),
        ("interval_s", 0),
        ("timeout_s", 31),
        ("frequencies", ["20m", "20m"]),
        ("drives", [str(i) for i in range(17)]),
        ("name", "name\nline"),
        ("series", "automatic"),
    ],
)
def test_invalid_plan_does_not_allocate_or_capture(tmp_path, key, value):
    plan = {**quick_plan(), key: value}
    with pytest.raises(ValueError):
        run(tmp_path, plan)
    assert not (tmp_path / "capture").exists()


def test_single_axis_requires_fixed_other_axis():
    with pytest.raises(ValueError):
        g.validate({**quick_plan(), "series": "frequency"})
    assert len(g.points({**quick_plan(), "series": "drive"})) == 2


def test_bad_confirmation_never_opens_meter(tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("Capture before valid authorization")

    source, result = run(tmp_path, gate=Gate(mismatch=True), capture=forbidden)
    assert result["execution"] == "failed" and result["completed_points"] == 0
    assert not list(source.glob("*/samples.csv"))
    assert result["points"][1]["status"] == "skipped"


def test_cancel_waiting_never_captures(tmp_path):
    path = tmp_path / "job"
    path.mkdir()
    event = threading.Event()
    gate = g.FileGate(path, lambda **kw: event.set())
    result = []
    thread = threading.Thread(
        target=lambda: result.append(g.run(path / "capture", quick_plan(), gate))
    )
    thread.start()
    assert event.wait(3)
    assert not list(path.glob("capture/*/samples.csv"))
    (path / "cancel.requested").touch()
    thread.join(3)
    assert not thread.is_alive() and result[0]["execution"] == "interrupted"
    assert result[0]["completed_points"] == 0


def test_native_logger_at_every_confirmed_point_and_partial_stop(tmp_path):
    source, result = run(tmp_path)
    assert result["completed_points"] == 2 and result["acceptance"] == "NOT EVALUATED"
    assert all(x["mean_W"] == "0.0000010000" for x in result["points"])
    for folder in source.glob("P*"):
        session = json.loads((folder / "samples.csv.session.json").read_text())
        confirmation = json.loads((folder / "confirmation.json").read_text())
        assert session["context"]["confirmation"] == confirmation
        assert session["simulation"] is True
    partial, result = run(tmp_path / "partial", gate=Gate(stop_after=2))
    assert result["execution"] == "interrupted" and result["completed_points"] == 1
    assert g.load(partial)[1] == result


def test_full_85_point_native_capture(tmp_path):
    plan = {
        **quick_plan(),
        "frequencies": g.BANDS,
        "drives": ["2 mA", "4 mA", "8 mA", "12 mA", "Custom"],
    }
    _, result = run(tmp_path, plan)
    assert result["completed_points"] == result["requested_points"] == 85


def test_physical_requires_fresh_setup_before_allocation(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, mode="physical", config=config(), prepared={})
    assert not (tmp_path / "capture").exists()


def test_injected_physical_path_closes_meter_and_retains_mode(tmp_path):
    wires = []

    class Wire(DemoTransport):
        def open(self, timeout):
            pass

    def capture(*args, **kwargs):
        wire = Wire()
        wires.append(wire)
        return g.capture_point(*args, **kwargs, transport_factory=lambda: wire)

    _, result = run(
        tmp_path,
        mode="physical",
        config=config(),
        prepared=dict.fromkeys(g.PREPARED, True),
        capture=capture,
    )
    assert result["mode"] == "physical" and result["completed_points"] == 2
    assert all(wire.closed for wire in wires)


def test_capture_failure_stops_later_points_and_preserves_reportable_rows(tmp_path):
    calls = []

    class Wire(DemoTransport):
        def read(self, deadline):
            if self.pending == b"TR2" and len(calls) > 1:
                raise TimeoutError("Injected meter timeout")
            calls.append(self.pending)
            return super().read(deadline)

    wire = Wire()

    def capture(*args, **kwargs):
        return g.capture_point(*args, **kwargs, transport_factory=lambda: wire)

    source, result = run(tmp_path, capture=capture)
    assert result["execution"] == "failed" and result["completed_points"] == 0
    assert result["points"][1]["status"] == "skipped" and wire.closed
    assert (source / "P001/samples.csv.session.json").exists()


@pytest.mark.parametrize("mutation", ["label", "receipt", "row", "extra"])
def test_resealed_semantic_corruption_rejected(tmp_path, mutation):
    source, _ = run(tmp_path)
    if mutation == "label":
        target = source / "workflow.json"
        value = json.loads(target.read_text())
        value["points"][0]["drive"] = "Changed"
        target.write_bytes(r.encoded(value))
    elif mutation == "receipt":
        target = source / "P001/confirmation.json"
        value = json.loads(target.read_text())
        value["token"] = "old-token"
        target.write_bytes(r.encoded(value))
    elif mutation == "row":
        target = source / "P001/samples.csv"
        target.write_text(target.read_text().replace(",W,ok,", ",dBm,ok,"))
    else:
        (source / "unlisted.txt").write_text("extra")
        with pytest.raises(ValueError):
            g.load(source)
        return
    (source / "artifacts.json").unlink()
    record = json.loads((source / "workflow.json").read_text())
    _seal(source, dict(schema=g.SCHEMA, mode=record["mode"], run_id=record["run_id"]))
    with pytest.raises(ValueError):
        g.load(source)


@pytest.mark.parametrize("stop", [False, True])
def test_pdf_portable_report_and_reimport_immutable(tmp_path, stop):
    pytest.importorskip("reportlab")
    source, result = run(tmp_path, gate=Gate(stop_after=1 if stop else None))
    before = {str(p): r.digest(p.read_bytes()) for p in source.rglob("*") if p.is_file()}
    output = tmp_path / "report"
    assert reports.publish(source, output, plot=False) == result
    assert reports.validate_pair(source, output) == result["run_id"]
    assert delivery.verify(tmp_path / "report.zip")["mode"] == "synthetic"
    assert before == {str(p): r.digest(p.read_bytes()) for p in source.rglob("*") if p.is_file()}
    from pypdf import PdfReader

    reader = PdfReader(output / "report.pdf")
    assert len(reader.pages) == 1 and "operator-guided" in reader.pages[0].extract_text()
    (output / "results.json").write_text("{}")
    with pytest.raises(ValueError):
        delivery.package(source, output, tmp_path / "changed.zip")


@pytest.fixture
def local_http_server():
    yield from ui_tests.http_server.__wrapped__()


def wait_phase(manager, job_id, expected):
    end = time.monotonic() + 15
    while time.monotonic() < end:
        manager.state()
        job = manager.get(job_id)
        if job["phase"] in expected:
            return job
        time.sleep(0.02)
    raise AssertionError(manager.get(job_id))


def test_external_api_confirmation_replay_reload_and_cancel(tmp_path, local_http_server):
    pytest.importorskip("reportlab")
    manager = jobs.Jobs(tmp_path / "jobs", plots=False)
    try:
        _, _, request, _, _ = local_http_server(manager)
        with request(
            "/api/guided",
            dict(plan=quick_plan(), operator="Tester", meter_mode="synthetic", prepared={}),
        ) as response:
            job_id = json.load(response)["job_id"]
        job = wait_phase(manager, job_id, {"waiting"})
        assert not list((manager.root / job_id).glob("capture/*/samples.csv"))
        original = job["prompt"]
        wrong = {
            **original,
            "operator": "Tester",
            "drive": "Wrong",
            "frequency_confirmed": True,
            "drive_confirmed": True,
        }
        with pytest.raises(urllib.error.HTTPError) as bad:
            request("/api/guided-confirm", dict(job_id=job_id, confirmation=wrong))
        assert bad.value.code == 400
        value = {
            **original,
            "operator": "Tester",
            "frequency_confirmed": True,
            "drive_confirmed": True,
        }
        with request("/api/guided-confirm", dict(job_id=job_id, confirmation=value)):
            pass
        # Wait for the *next* token, not the previous waiting state.
        end = time.monotonic() + 10
        while time.monotonic() < end:
            job = wait_phase(manager, job_id, {"waiting", "failed"})
            if job.get("prompt", {}).get("token") != original["token"]:
                break
            time.sleep(0.02)
        assert job["prompt"]["point_id"] == "P002" and job["index"] == 1
        with request("/api/state") as response:
            assert json.load(response)["active_id"] == job_id
        with pytest.raises(urllib.error.HTTPError) as replay:
            request("/api/guided-confirm", dict(job_id=job_id, confirmation=value))
        assert replay.value.code == 400
        with request("/api/cancel", dict(job_id=job_id)):
            pass
        final = wait_phase(manager, job_id, {"finished", "failed"})
        assert final["phase"] == "finished", final
        assert final["outcome"] == "interrupted" and final["pdf_ready"]
        with request(f"/artifacts/{job_id}/report.html") as response:
            assert b"Tester" in response.read()
    finally:
        manager.close()


def test_external_client_drives_same_confirmation_api(tmp_path, local_http_server):
    from hp437b.guided_client import Client

    pytest.importorskip("reportlab")
    manager = jobs.Jobs(tmp_path / "client", plots=False)
    try:
        server, _, _, _, _ = local_http_server(manager)
        client = Client(f"http://127.0.0.1:{server.server_port}")
        plan = {**quick_plan(), "drives": ["Custom"]}
        job = client.start(plan, operator="External operator")
        job = wait_phase(manager, job["job_id"], {"waiting"})
        assert client.state()["active_id"] == job["job_id"]
        client.confirm(job["job_id"], job["prompt"], operator="External operator")
        final = wait_phase(manager, job["job_id"], {"finished", "failed"})
        assert final["phase"] == "finished" and final["outcome"] == "completed", final
    finally:
        manager.close()


def test_stop_during_capture_retains_partial_samples_and_closes(tmp_path):
    gate = Gate()
    wire = DemoTransport()
    original = wire.read
    calls = []

    def read(deadline):
        reply = original(deadline)
        if wire.pending is None and reply.startswith(b"+1."):
            calls.append(reply)
            if len(calls) == 2:  # Setup probe, then first recorded sample.
                gate.stop_after = 1
        return reply

    wire.read = read

    def capture(*args, **kwargs):
        return g.capture_point(*args, **kwargs, transport_factory=lambda: wire)

    source, result = run(tmp_path, {**quick_plan(), "samples": 3}, gate=gate, capture=capture)
    assert result["execution"] == "interrupted" and result["completed_points"] == 0
    assert result["points"][0]["samples"] == 1 and wire.closed
    assert result["points"][1]["status"] == "skipped"
    assert g.load(source)[1] == result


def test_physical_report_label_and_portable_readme(tmp_path):
    import zipfile

    pytest.importorskip("reportlab")

    class Wire(DemoTransport):
        def open(self, timeout):
            pass

    def capture(*args, **kwargs):
        return g.capture_point(*args, **kwargs, transport_factory=Wire)

    source, _ = run(
        tmp_path,
        mode="physical",
        config=config(),
        prepared=dict.fromkeys(g.PREPARED, True),
        capture=capture,
    )
    reports.publish(source, tmp_path / "report", plot=False)
    with zipfile.ZipFile(tmp_path / "report.zip") as package:
        readme = package.read("START-HERE.txt")
        assert b"operator-guided radio" in readme and b"POWER REF measurements" not in readme
    from pypdf import PdfReader

    text = PdfReader(tmp_path / "report/report.pdf").pages[0].extract_text()
    assert "Recorded measurements" in text and "POWER REF - recorded" not in text


def test_plot_report_handles_partial_and_both_axes(tmp_path):
    pytest.importorskip("matplotlib")
    pytest.importorskip("reportlab")
    plan = {**quick_plan(), "frequencies": ["2200m", "2m"]}
    source, _ = run(tmp_path, plan, gate=Gate(stop_after=3))
    reports.publish(source, tmp_path / "report", plot=True)
    for axis in ("frequency", "drive"):
        assert (tmp_path / "report" / (axis + ".svg")).is_file()
        assert (tmp_path / "report" / (axis + ".png")).is_file()


def test_physical_job_pins_launch_configuration_and_requires_new_preparation(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    launches = []

    class Process:
        def __init__(self, command, **kwargs):
            launches.append(command)

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    manager = jobs.Jobs(tmp_path / "jobs", plots=False, sweep_config=config())
    monkeypatch.setattr(jobs.subprocess, "Popen", Process)
    try:
        with pytest.raises(ValueError, match="prepared"):
            manager.start_guided(quick_plan(), "Test", "physical", {})
        assert not launches
        job = manager.start_guided(
            quick_plan(), "Test", "physical", dict.fromkeys(g.PREPARED, True)
        )
        request = jobs.read(manager.root / job["job_id"] / "request.json")
        assert request["sweep_config"] == config() and request["meter_mode"] == "physical"
        assert request["prepared"] == dict.fromkeys(g.PREPARED, True)
        assert len(launches) == 1
        with pytest.raises(ValueError, match="already active"):
            manager.start_guided(quick_plan(), "Test", "synthetic", {})
    finally:
        manager.close()
