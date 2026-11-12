"""WF-02 physical integration via explicit fake adapters; no USB or RF."""

import json
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

import hp437b.instrument as instrument_module
import hp437b.transport as transport_module
from hp437b import stability as s
from hp437b import stability_simulation as sim
from hp437b.errors import OperationTimeout

ROOT = Path(__file__).parents[1]
MODULE = run_path(str(ROOT / "tools/run_stability_reference.py"))
RESOURCE = "USB0::0x1::0x2::SYNTHETIC::INSTR"


def setup():
    return {
        **dict.fromkeys(MODULE["FOUNDATION"]["PREPARED"], True),
        "meter_serial": "FAKE-METER",
        "sensor_serial": "FAKE-SENSOR",
        "known_issues": ["Injected test transport; no actual bench measurement"],
        "expected_firmware": "1.9",
    }


@pytest.fixture
def harness(monkeypatch):
    b = sim.Bench("constant")
    b.epoch = datetime(2026, 11, 12, tzinfo=UTC)

    def clock():
        return round(b.now, 6)

    fake_time = SimpleNamespace(monotonic=clock, sleep=b.sleep)
    monkeypatch.setattr(instrument_module, "time", fake_time)
    monkeypatch.setattr(transport_module, "time", fake_time)
    controllers = []
    original = MODULE["Controller"]

    class Observed(original):
        def __init__(self, *args):
            super().__init__(*args)
            controllers.append(self)

        def begin(self, stage, **kwargs):
            b.stage = stage
            super().begin(stage, **kwargs)

    monkeypatch.setitem(MODULE["execute"].__globals__, "Controller", Observed)
    wires = []

    class Fake(sim.Wire):
        def open(self, timeout):
            assert 0 < timeout <= 10
            if b.scenario == "open-failure":
                raise OSError("injected open failure")

        def write(self, data, deadline):
            if data == b"OD":
                assert self.pending is None
                self.pending = data
                return
            if data == b"OC0" and b.scenario == "still-on":
                b.event("write", raw_hex=data.hex())
                return
            return super().write(data, deadline)

        def read(self, deadline):
            if self.pending == b"OD":
                self.pending = None
                return b"-0.020uW\r\n"
            return super().read(deadline)

        def close(self):
            super().close()
            if b.stage == "source-on" and b.scenario == "close-failure":
                raise OSError("injected close failure")

    def factory(resource):
        assert resource == RESOURCE
        b.reads = 0
        wire = Fake(b)
        wires.append(wire)
        return wire

    def run(path, scenario="constant", setup_override=None, **kwargs):
        b.scenario = scenario
        return MODULE["execute"](
            path,
            RESOURCE,
            setup_override or setup(),
            confirmed=True,
            factory=factory,
            clock=clock,
            sleep=b.sleep,
            utcnow=b.utc,
            **kwargs,
        )

    return SimpleNamespace(run=run, bench=b, wires=wires, controllers=controllers)


def test_complete_physical_path_report_and_provenance_with_fakes(tmp_path, harness):
    capture, report = tmp_path / "capture", tmp_path / "report"
    result = harness.run(capture, report_output=report, plots=False)
    assert result["status"] == "completed"
    assert result["final_state"]["source"] == "off"
    assert result["final_state"]["front_panel_confirmation"] == "pending"
    assert result["free_run_check"]["passed"]
    assert all(w.closed for w in harness.wires)
    record, analysis, provenance, bundle = s.load(capture)
    assert record == result and s.p.verify(provenance, capture)
    assert analysis["mode"] == "physical" and analysis["coverage"]["bins_present"] == 6
    assert 1799 <= analysis["coverage"]["valid"] <= 1801
    assert analysis["metrics"]["endpoint_change_percent"] == "0"
    assert "instrument_sessions" in provenance["run"]["facts"]
    assert provenance["run"]["mode"] == "physical"
    page = (report / "report.html").read_text()
    assert "SYNTHETIC" not in page and "(virtual)" not in page and "Fictional" not in page
    assert "FAKE-METER" in page and "Injected test transport" in page
    assert s.p.Bundle(report).inventory("artifacts.json", "physical")["mode"] == "physical"
    writes = [e.get("raw_hex") for e in harness.bench.trace if e["operation"] == "write"]
    assert writes.count(b"OC1".hex()) == 1 and writes.count(b"OC0".hex()) == 1


@pytest.mark.parametrize(
    "scenario,status,source",
    [
        ("timeout", "failed", "unknown"),
        ("malformed", "failed", "unknown"),
        ("cancel", "interrupted", "off"),
        ("source-off-failure", "failed", "unknown"),
        ("still-on", "failed", "on"),
        ("close-failure", "failed", "unknown"),
        ("open-failure", "failed", "unknown"),
    ],
)
def test_faults_preserve_partial_reports_and_shutdown_policy(
    tmp_path, harness, scenario, status, source
):
    capture = tmp_path / "capture"
    result = harness.run(capture, scenario, report_output=tmp_path / "report", plots=False)
    assert result["status"] == status and result["final_state"]["source"] == source
    analysis = json.loads((tmp_path / "report/results.json").read_text())
    assert analysis["acceptance"]["outcome"] == "not_evaluated"
    if scenario in ("timeout", "malformed", "close-failure", "open-failure"):
        writes = [e.get("raw_hex") for e in harness.bench.trace if e["operation"] == "write"]
        assert b"OC0".hex() not in writes
    if scenario in ("timeout", "malformed"):
        events = json.loads((capture / "trace.json").read_text())["events"]
        index = next(
            i
            for i, e in enumerate(events)
            if e["operation"] == "read_error" or e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(
            e["operation"] in ("write_start", "open_start", "go_to_local_start")
            for e in events[index + 1 :]
        )
    assert all(w.closed for w in harness.wires)


def test_initial_on_is_not_adopted_or_switched_off(tmp_path, harness):
    harness.bench.source = True
    result = harness.run(tmp_path / "capture")
    assert result["status"] == "failed" and result["final_state"]["source"] == "on"
    writes = [e.get("raw_hex") for e in harness.bench.trace if e["operation"] == "write"]
    assert b"OC1".hex() not in writes and b"OC0".hex() not in writes


def test_report_failure_keeps_capture_closed_sealed_and_reusable(tmp_path, harness, monkeypatch):
    original = s.publish

    def failure(*args, **kwargs):
        assert all(w.closed for w in harness.wires)
        raise OSError("injected report failure")

    monkeypatch.setattr(s, "publish", failure)
    with pytest.raises(OSError, match="report failure"):
        harness.run(tmp_path / "capture", report_output=tmp_path / "report", plots=False)
    assert s.load(tmp_path / "capture")[0]["status"] == "completed"
    monkeypatch.setattr(s, "publish", original)
    s.publish(tmp_path / "capture", tmp_path / "new-report", plots=False)


def test_guards_prevent_factory_before_prepared_confirmation(tmp_path):
    calls = []
    with pytest.raises(ValueError):
        MODULE["execute"](
            tmp_path / "capture", RESOURCE, setup(), factory=lambda *a: calls.append(a)
        )
    assert not calls and not (tmp_path / "capture").exists()
    with pytest.raises(ValueError):
        MODULE["execute"](
            tmp_path / "capture",
            RESOURCE,
            setup(),
            confirmed=True,
            factory=lambda *a: calls.append(a),
            report_output=tmp_path / "capture/report",
            plots=False,
        )
    assert not calls and not (tmp_path / "capture").exists()


def test_shared_resource_ownership():
    with MODULE["FOUNDATION"]["ownership"](RESOURCE), pytest.raises(RuntimeError):
        with MODULE["FOUNDATION"]["ownership"](RESOURCE):
            pytest.fail("A second workflow must not take the same resource lock")


def test_stage_and_whole_run_deadlines(tmp_path):
    now = [100.0]
    record = {"stages": {stage: {"status": "pending"} for stage in s.STAGES}, "control_stages": {}}
    c = MODULE["Controller"](
        tmp_path,
        record,
        lambda: now[0],
        lambda seconds: None,
        lambda: datetime(2026, 11, 12, tzinfo=UTC),
    )
    c.begin("plateau")
    assert c.deadline(9999) == 1940
    with pytest.raises(OperationTimeout):
        c.wait(1840)
    now[0] = c.work_end + 1
    with pytest.raises(OperationTimeout):
        c.begin("plateau")
