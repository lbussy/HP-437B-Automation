"""Physical WF-03 integration through explicit fake adapters; no USB or RF."""

import json
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

import hp437b.instrument as instrument_module
import hp437b.transport as transport_module
from hp437b import repeatability as w
from hp437b import repeatability_simulation as sim
from hp437b.errors import OperationTimeout
from hp437b.workflow_report import _seal

ROOT = Path(__file__).parents[1]
MODULE = run_path(str(ROOT / "tools/run_cycle_reference.py"))
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
    b = sim.Bench("repeatable")
    b.epoch = datetime(2026, 11, 12, tzinfo=UTC)

    def clock():
        return round(b.now, 6)

    fake_time = SimpleNamespace(monotonic=clock, sleep=b.sleep)
    monkeypatch.setattr(instrument_module, "time", fake_time)
    monkeypatch.setattr(transport_module, "time", fake_time)
    original = MODULE["Controller"]
    controllers = []
    wires = []

    class Observed(original):
        def __init__(self, *args):
            super().__init__(*args)
            controllers.append(self)

        def start_cycle(self, cycle):
            b.cycle = cycle["cycle_id"]
            super().start_cycle(cycle)

        def begin(self, stage, *args, **kwargs):
            b.stage = stage
            super().begin(stage, *args, **kwargs)

    monkeypatch.setitem(MODULE["execute"].__globals__, "Controller", Observed)

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
            return super().write(data, deadline)

        def read(self, deadline):
            if self.pending == b"OD":
                self.pending = None
                return b"-0.020uW\r\n"
            return super().read(deadline)

        def close(self):
            super().close()
            if b.stage == "C02-source-on" and b.scenario == "close-failure":
                raise OSError("injected close failure")

    def factory(resource):
        assert resource == RESOURCE
        b.reads = 0
        wire = Fake(b)
        wires.append(wire)
        return wire

    def run(path, scenario="repeatable", **kwargs):
        b.scenario = scenario
        b.source = scenario == "initial-on"
        return MODULE["execute"](
            path,
            RESOURCE,
            setup(),
            confirmed=True,
            factory=factory,
            clock=clock,
            sleep=b.sleep,
            utcnow=b.utc,
            **kwargs,
        )

    return SimpleNamespace(run=run, bench=b, wires=wires, controllers=controllers)


def test_full_five_cycles_and_compatible_report_provenance(tmp_path, harness):
    capture, report = tmp_path / "capture", tmp_path / "report"
    record = harness.run(capture, report_output=report, plots=False)
    assert record["status"] == "completed" and record["final_state"]["source"] == "off"
    assert (
        record["final_state"]["front_panel_confirmation"] == "pending"
        and record["free_run_check"]["passed"]
    )
    assert all(c["status"] == "completed" for c in record["cycles"]) and all(
        wire.closed for wire in harness.wires
    )
    original, result, provenance, _ = w.load(capture)
    assert original == record and result["completed_cycles"] == result["requested_cycles"] == 5
    assert result["metrics"]["cycle_spread_percent"] == "0" and w.p.verify(provenance, capture)
    assert all(29 <= cycle["valid"] <= 31 for cycle in result["cycles"])
    assert (
        provenance["run"]["mode"] == "physical"
        and "instrument_sessions" in provenance["run"]["facts"]
    )
    page = (report / "report.html").read_text()
    assert "SYNTHETIC" not in page and "(virtual)" not in page and "Fictional" not in page
    assert "FAKE-METER" in page and "Injected test transport" in page
    assert w.p.Bundle(report).inventory("artifacts.json", "physical")["mode"] == "physical"
    writes = [e.get("raw_hex") for e in harness.bench.trace if e["operation"] == "write"]
    assert writes.count(b"OC1".hex()) == writes.count(b"OC0".hex()) == 5
    for cycle in record["cycles"]:
        assert cycle["off_wait"]["end_s"] - cycle["off_wait"]["start_s"] >= 19.999999


@pytest.mark.parametrize(
    "scenario,status,completed,source",
    [
        ("timeout", "failed", 1, "unknown"),
        ("malformed", "failed", 1, "unknown"),
        ("instrument-error", "failed", 1, "off"),
        ("cancel", "interrupted", 1, "off"),
        ("source-off-failure", "failed", 1, "unknown"),
        ("still-on", "failed", 1, "on"),
        ("source-mismatch", "failed", 1, "off"),
        ("close-failure", "failed", 1, "unknown"),
        ("open-failure", "failed", 0, "unknown"),
        ("initial-on", "failed", 0, "on"),
    ],
)
def test_failed_cycle_stop_cleanup_and_partial_reports(
    tmp_path, harness, scenario, status, completed, source
):
    capture, report = tmp_path / "capture", tmp_path / "report"
    record = harness.run(capture, scenario, report_output=report, plots=False)
    result = json.loads((report / "results.json").read_text())
    assert record["status"] == status and record["final_state"]["source"] == source
    assert result["completed_cycles"] == completed and result["requested_cycles"] == 5
    assert result["acceptance"]["outcome"] == "not_evaluated" and all(
        wire.closed for wire in harness.wires
    )
    if completed == 1:
        assert all(c["status"] == "skipped" for c in result["cycles"][2:])
    trace = json.loads((capture / "trace.json").read_text())["events"]
    if scenario in ("timeout", "malformed"):
        index = next(
            i
            for i, e in enumerate(trace)
            if e["operation"] == "read_error" or e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(
            e["operation"] in ("write_start", "open_start", "go_to_local_start")
            for e in trace[index + 1 :]
        )
    writes = [e for e in trace if e["operation"] == "write_start"]
    if scenario in ("source-off-failure", "still-on"):
        assert sum(e.get("raw_hex") == b"OC0".hex() and e["cycle_id"] == "C02" for e in writes) == 1
        assert (
            result["cycles"][1]["valid"] >= 29 and not result["cycles"][1]["included_in_aggregate"]
        )
    if scenario == "initial-on":
        assert not any(e.get("raw_hex") in (b"OC0".hex(), b"OC1".hex()) for e in writes)


def test_report_failure_after_capture_closure_does_not_reacquire(tmp_path, harness, monkeypatch):
    def fail(*args, **kwargs):
        assert all(wire.closed for wire in harness.wires)
        raise OSError("injected report failure")

    monkeypatch.setattr(w, "publish", fail)
    with pytest.raises(OSError, match="report failure"):
        harness.run(tmp_path / "capture", report_output=tmp_path / "report", plots=False)
    assert w.load(tmp_path / "capture")[0]["status"] == "completed"
    assert not (tmp_path / "report/artifacts.json").exists()


def test_prepared_output_guards_prevent_factory(tmp_path):
    calls = []
    with pytest.raises(ValueError):
        MODULE["execute"](
            tmp_path / "capture", RESOURCE, setup(), factory=lambda *a: calls.append(a)
        )
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


def test_shared_lock_and_stage_cycle_whole_deadlines(tmp_path):
    with MODULE["FOUNDATION"]["ownership"](RESOURCE), pytest.raises(RuntimeError):
        with MODULE["FOUNDATION"]["ownership"](RESOURCE):
            pytest.fail("Second workflow acquired the shared resource")
    now = [100.0]
    c = MODULE["Controller"](
        tmp_path,
        {},
        lambda: now[0],
        lambda seconds: None,
        lambda: datetime(2026, 11, 12, tzinfo=UTC),
    )
    cycle = {"cycle_id": "C01", "status": "pending"}
    c.start_cycle(cycle)
    entry = {"status": "pending"}
    c.begin("C01-plateau", entry, 70)
    assert c.deadline(999) == 170
    with pytest.raises(OperationTimeout):
        c.wait(70)
    now[0] = c.work_end - 149
    with pytest.raises(OperationTimeout):
        c.start_cycle({"cycle_id": "C02"})


def test_short_dwell_and_forged_free_run_rejected(tmp_path, harness):
    capture = tmp_path / "capture"
    harness.run(capture)
    original = json.loads((capture / "workflow.json").read_text())
    for field in ("dwell", "free-run"):
        record = json.loads(json.dumps(original))
        if field == "dwell":
            record["cycles"][0]["off_wait"]["end_s"] = (
                record["cycles"][0]["off_wait"]["start_s"] + 19
            )
        else:
            record["free_run_check"]["standby"] = True
        (capture / "workflow.json").write_text(json.dumps(record))
        (capture / "artifacts.json").unlink()
        _seal(
            capture,
            {
                "schema": "hp437b.repeatability-export.v1",
                "mode": "physical",
                "run_id": record["run_id"],
            },
        )
        with pytest.raises(ValueError):
            w.load(capture)
