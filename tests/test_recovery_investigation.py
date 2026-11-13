"""Offline recovery investigation: real boundaries, injected conversations, no supervisor change."""

import csv
import hashlib
import json

import pytest
import test_physical_workflow as wf1

from hp437b import operator_jobs as jobs
from hp437b import protocol
from hp437b.errors import OperationTimeout, ProtocolError, StateUncertain
from hp437b.instrument import Instrument
from hp437b.logger import collect
from hp437b.simulation import status_fixture

IDENTITY = b"HEWLETT-PACKARD,437B,,1.9\r\n"
VALUE = b"+1.0000E-06\r\n"
SETUP = [
    ("write", b"*IDN?"),
    ("read", IDENTITY),
    ("write", b"RL0"),
    ("write", b"LN"),
    ("write", b"TR2"),
    ("read", VALUE),
    ("write", b"SM"),
    ("read", status_fixture(logarithmic=False)),
]


def hashes(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "failure",
    [OperationTimeout("expired read"), OSError("USB disappeared"), b"MALFORMED\r\n"],
    ids=["timeout", "disconnect", "malformed"],
)
def test_fresh_session_keeps_partial_run_failed_and_immutable(tmp_path, scripted, failure):
    """Reconciliation is a new session, never a retry that rewrites the failed run."""
    original = tmp_path / "original"
    original.mkdir()
    wire = scripted(
        SETUP + [("write", b"TR2"), ("read", VALUE), ("write", b"TR2"), ("read", failure)]
    )
    device = Instrument(wire)
    with pytest.raises((OperationTimeout, OSError, ProtocolError)):
        collect(device, original / "capture.csv", count=3, interval=0, unit="W", simulation=True)
    assert wire.closed and not wire.steps
    calls = list(wire.calls)
    with pytest.raises(StateUncertain):
        device.identify()
    device.close()
    assert wire.calls == calls  # No cleanup/retry traffic after the failed transaction.
    with (original / "capture.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    metadata = json.loads((original / "capture.csv.session.json").read_text())
    assert [row["status"] for row in rows] == ["ok", "failed"]
    assert rows[1]["value"] == "" and metadata["status"] == "failed"
    assert rows[1]["raw_hex"] == (failure.hex() if isinstance(failure, bytes) else "")
    before = hashes(original)

    class LocalWire(scripted):
        capabilities = scripted.capabilities | {"go_to_local"}

        def return_local(self, deadline):
            self._step("local")
            return {"status": "accepted"}

    fresh_wire = LocalWire(
        SETUP + [("write", b"TR2"), ("read", VALUE), ("write", b"TR3"), ("local", None)]
    )
    fresh = collect(
        Instrument(fresh_wire),
        tmp_path / "fresh.csv",
        count=1,
        interval=0,
        unit="W",
        simulation=True,
    )
    assert fresh["status"] == "completed" and fresh["session_id"] != metadata["session_id"]
    assert fresh["instrument_cleanup"]["status"] == "accepted"
    assert fresh_wire.closed and not fresh_wire.steps
    assert hashes(original) == before
    assert all(value != b"OC1" for operation, value in wire.calls + fresh_wire.calls)


@pytest.mark.parametrize("failure", [FileNotFoundError("absent"), PermissionError("denied")])
def test_unavailable_fresh_connection_stops_without_discovery_or_retry(tmp_path, scripted, failure):
    wire = scripted()
    opens = []

    def connect():
        opens.append("selected adapter")
        raise failure

    with pytest.raises(type(failure)):
        collect(
            Instrument(wire),
            tmp_path / "unavailable.csv",
            count=1,
            interval=0,
            simulation=True,
            connect=connect,
        )
    saved = json.loads((tmp_path / "unavailable.csv.session.json").read_text())
    assert opens == ["selected adapter"] and wire.calls == [] and wire.closed
    assert saved["status"] == "failed" and saved["rows"] == 0


@pytest.mark.parametrize("reply", [b"ACME,OTHER,,1.0\r\n", b"HEWLETT-PACKARD,437B,,1.8\r\n"])
def test_identification_limits_are_explicit(scripted, reply):
    """Syntax guards reject another model; expected firmware matching belongs above the API."""
    wire = scripted([("write", b"*IDN?"), ("read", reply)])
    device = Instrument(wire)
    try:
        if reply.startswith(b"ACME"):
            with pytest.raises(ProtocolError):
                device.identify()
        else:
            identity = device.identify()
            assert identity.firmware != "1.9" and identity.serial == ""
    finally:
        device.close()
    assert len(wire.calls) == 2 and wire.closed


def test_generic_logger_does_not_decide_reference_recovery_policy(tmp_path, scripted):
    """A successful connection is not proof the reference is off or a test may resume."""
    source_on = bytearray(status_fixture(logarithmic=False))
    source_on[16] = ord("1")
    steps = SETUP[:-1] + [("read", bytes(source_on)), ("write", b"TR2"), ("read", VALUE)]
    wire = scripted(steps)
    result = collect(
        Instrument(wire), tmp_path / "source-on.csv", count=1, interval=0, unit="W", simulation=True
    )
    assert result["status"] == "completed"
    assert protocol.status(bytes.fromhex(result["initial_status_raw_hex"])).reference_on
    assert not any(value in (b"OC0", b"OC1") for operation, value in wire.calls)


@pytest.fixture
def physical(monkeypatch):
    return wf1.harness.__wrapped__(monkeypatch)


@pytest.mark.parametrize("fault", ["timeout", "malformed"])
def test_fault_with_reference_on_cannot_be_hidden_by_fresh_workflow(tmp_path, physical, fault):
    original = tmp_path / "original"
    failed = physical.run(original, fault)
    assert failed["status"] == "failed" and failed["final_state"]["source"] == "unknown"
    assert physical.bench.source is True  # Known only to the simulator, not the failed client.
    assert all(wire.closed for wire in physical.wires)
    before = hashes(original)

    # Simulate a backend able to open again, with the source still on.
    blocked = physical.run(tmp_path / "fresh-still-on", "nominal")
    assert blocked["status"] == "failed" and blocked["stages"]["S00"]["status"] == "failed"
    assert blocked["final_state"]["source"] == "on"
    assert blocked["stages"]["S20"]["status"] == "skipped"
    assert hashes(original) == before

    # Explicit external reconciliation in the simulator, not a software recovery claim.
    physical.bench.source = False
    restored = physical.run(tmp_path / "after-external-reconciliation", "nominal")
    assert restored["status"] == "completed" and restored["final_state"]["source"] == "off"
    assert all(wire.closed for wire in physical.wires) and hashes(original) == before


@pytest.mark.parametrize("phase", jobs.ACTIVE)
@pytest.mark.parametrize("mode", ["physical", "reference_suite", "report_recovery"])
def test_service_restart_preserves_evidence_and_never_relaunches(
    tmp_path, monkeypatch, phase, mode
):
    pytest.importorskip("reportlab")
    root = tmp_path / "jobs"
    job = root / ("a" * 32)
    capture = job / "capture"
    capture.mkdir(parents=True)
    (capture / "partial.csv").write_bytes(b"synthetic retained evidence\n")
    jobs.atomic(job / "request.json", dict(mode=mode, workflows=["WF-01"]))
    jobs.atomic(job / "state.json", dict(phase=phase, current="WF-01", index=1, total=3))
    before = hashes(capture)
    request = (job / "request.json").read_bytes()

    def forbidden_launch(*args, **kwargs):
        pytest.fail("Restart must not launch a worker")

    monkeypatch.setattr(jobs.subprocess, "Popen", forbidden_launch)
    manager = jobs.Jobs(root, plots=False)
    try:
        state = jobs.read(job / "state.json")
        assert state["phase"] == "failed" and "No test was restarted" in state["error"]
        assert manager.process is None and manager.active_id is None
        assert hashes(capture) == before and (job / "request.json").read_bytes() == request
        assert not (job / "operator-confirmation.json").exists()
    finally:
        manager.close()
