"""Physical runner integration through explicit fakes; never actual hardware."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

import hp437b.instrument as instrument_module
import hp437b.transport as transport_module
from hp437b.errors import OperationTimeout

ROOT = Path(__file__).parents[1]
MODULE = run_path(str(ROOT / "tools/run_power_reference.py"))
SYNTHETIC = run_path(str(ROOT / "tools/exercise_workflow.py"))
RESOURCE = "USB0::0x1::0x2::SYNTHETIC::INSTR"


def setup():
    return {
        **dict.fromkeys(MODULE["PREPARED"], True),
        "meter_serial": "SYNTHETIC-437B-001",
        "sensor_serial": "SYNTHETIC-8482A-001",
        "known_issues": ["unit-test injected transport"],
        "expected_firmware": "1.9",
    }


@pytest.fixture
def harness(monkeypatch):
    bench = SYNTHETIC["Bench"]("nominal")

    def clock():
        return bench.now

    fake_time = SimpleNamespace(monotonic=clock, sleep=bench.sleep)
    monkeypatch.setattr(instrument_module, "time", fake_time)
    monkeypatch.setattr(transport_module, "time", fake_time)
    controllers = []
    original = MODULE["Controller"]

    class Observed(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            controllers.append(self)

    monkeypatch.setitem(MODULE["execute"].__globals__, "Controller", Observed)
    wires = []
    fail_off_status = False

    class Fake(SYNTHETIC["FakeWire"]):
        def open(self, timeout):
            assert timeout <= 10

        def close(self):
            super().close()
            if bench.scenario == "close-error" and bench.role == "S20":
                raise OSError("injected close failure")

        def write(self, data, deadline):
            if data == b"OD":
                assert self.pending is None
                self.pending = data
                return
            if fail_off_status and data == b"OC0":
                bench.event("write", raw_hex=data.hex())
                return  # Complete write, but source stays on: never retry.
            super().write(data, deadline)

        def read(self, deadline):
            if self.pending == b"OD":
                self.pending = None
                return b"-0.050uW\r\n"
            return super().read(deadline)

    def factory(resource):
        assert resource == RESOURCE
        bench.role, bench.reads = controllers[-1].stage, 0
        wire = Fake(bench)
        wires.append(wire)
        return wire

    def run(output, scenario="nominal", **options):
        nonlocal fail_off_status
        fail_off_status = scenario == "off-not-applied"
        bench.scenario = scenario
        return MODULE["execute"](
            output,
            RESOURCE,
            setup(),
            confirmed=True,
            factory=factory,
            clock=clock,
            sleep=bench.sleep,
            utcnow=lambda: datetime(2026, 11, 12, tzinfo=UTC) + timedelta(seconds=bench.now),
            **options,
        )

    return SimpleNamespace(run=run, bench=bench, wires=wires, controllers=controllers)


def test_full_physical_path_with_fake_adapter(tmp_path, harness):
    out = tmp_path / "bundle"
    result = harness.run(out)
    assert result["status"] == "completed"
    assert result["final_state"]["source"] == "off"
    assert "GTL accepted" in result["final_state"]["local"]
    assert all(item["status"] == "completed" for item in result["stages"].values())
    assert all(wire.closed for wire in harness.wires)
    analysis = json.loads((out / "analysis.json").read_text())
    assert analysis["mode"] == "physical" and analysis["integrity"] == "pass"
    from hp437b.provenance import load, sidecar_path, verify

    provenance = load(sidecar_path(out) / "provenance.json")
    assert provenance["run"]["mode"] == "physical"
    assert verify(provenance, out)
    assert analysis["stages"]["S40"]["valid"] == 300
    assert analysis["stages"]["S40"]["metrics"]["mean_W"] == "0.00098800"
    for name, metadata in json.loads((out / "artifacts.json").read_text())["artifacts"].items():
        data = (out / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
    report = (out / "report.md").read_text()
    assert (
        "PHYSICAL RUN" in report and "not evaluated" in report and "fictional meter" not in report
    )
    trace = json.loads((out / "trace.json").read_text())["events"]
    assert (
        sum(e.get("raw_hex") == b"OC1".hex() for e in trace if e["operation"] == "write_start") == 1
    )
    assert (
        sum(e.get("raw_hex") == b"OC0".hex() for e in trace if e["operation"] == "write_start") == 1
    )
    assert any(e["operation"] == "free_run_display" for e in trace)


@pytest.mark.parametrize(
    "scenario,status,source",
    [
        ("malformed", "failed", "unknown"),
        ("timeout", "failed", "unknown"),
        ("cancel", "interrupted", "off"),
        ("instrument-error", "failed", "off"),
        ("source-off-failure", "failed", "unknown"),
        ("off-not-applied", "failed", "on"),
    ],
)
def test_physical_runner_failure_cleanup_and_no_retry(tmp_path, harness, scenario, status, source):
    out = tmp_path / "bundle"
    result = harness.run(out, scenario)
    assert result["status"] == status
    assert result["final_state"]["source"] == source
    assert result["stages"]["S60"]["status"] == "skipped"
    events = json.loads((out / "trace.json").read_text())["events"]
    writes = [event for event in events if event["operation"] == "write_start"]
    if scenario in ("source-off-failure", "off-not-applied"):
        assert sum(e["raw_hex"] == b"OC0".hex() for e in writes) == 1
    if scenario in ("malformed", "timeout"):
        assert not any(e["raw_hex"] == b"OC0".hex() for e in writes)
        first_error = next(
            i
            for i, e in enumerate(events)
            if e["operation"] == "read_error" or e.get("raw_hex") == b"MALFORMED\r\n".hex()
        )
        assert not any(
            e["operation"] in ("write_start", "open_start", "go_to_local_start")
            for e in events[first_error + 1 :]
        )
    assert (out / "report.md").exists()
    assert all(wire.closed for wire in harness.wires)


def test_setup_and_existing_output_guards_before_factory(tmp_path):
    calls = []
    with pytest.raises(ValueError):
        MODULE["execute"](tmp_path / "new", RESOURCE, setup(), factory=lambda *a: calls.append(a))
    assert not (tmp_path / "new").exists() and not calls
    with pytest.raises(FileExistsError):
        MODULE["execute"](
            tmp_path, RESOURCE, setup(), confirmed=True, factory=lambda *a: calls.append(a)
        )
    assert not calls


def test_stage_deadline_caps_operation_and_wait(tmp_path):
    now = [100.0]
    record = {"stages": {s: {"status": "pending"} for s in MODULE["LIMITS"]}}
    control = MODULE["Controller"](
        tmp_path,
        record,
        lambda: now[0],
        lambda amount: now.__setitem__(0, now[0] + amount),
        lambda: datetime(2026, 11, 12, tzinfo=UTC),
    )
    control.begin("S20")
    assert control.deadline(1000) == 160
    with pytest.raises(OperationTimeout):
        control.wait(60)
    now[0] = 161
    with pytest.raises(OperationTimeout):
        control.deadline(200)


def test_ownership_prevents_second_runner():
    with MODULE["ownership"](RESOURCE), pytest.raises(RuntimeError, match="owns"):
        with MODULE["ownership"](RESOURCE):
            pytest.fail("should not acquire ownership twice")


def test_initial_reference_on_is_refused_without_adoption(tmp_path, harness):
    harness.bench.source = True
    result = harness.run(tmp_path / "bundle")
    assert result["status"] == "failed"
    assert result["stages"]["S00"]["status"] == "failed"
    assert result["final_state"]["source"] == "on"
    writes = [e.get("raw_hex") for e in harness.bench.trace if e["operation"] == "write"]
    assert b"OC0".hex() not in writes and b"OC1".hex() not in writes


def test_close_failure_does_not_reopen_for_blind_source_off(tmp_path, harness):
    result = harness.run(tmp_path / "bundle", "close-error")
    assert result["status"] == "failed" and result["final_state"]["source"] == "unknown"
    assert not any(e.get("raw_hex") == b"OC0".hex() for e in harness.bench.trace)
    assert result["stages"]["S30"]["status"] == "skipped"
