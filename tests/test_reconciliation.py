"""Real bounded worker/lease lifecycle with fake instruments only."""

import fcntl
import hashlib
import json
import multiprocessing
import os
import time
from dataclasses import dataclass

import pytest

from hp437b import reconciliation as rec
from hp437b.simulation import status_fixture

IDN = b"HEWLETT-PACKARD,437B,,1.9\r\n"
TARGET = rec.Target("FAKE::REFERENCE-BENCH", "FAKE-ADAPTER-001", IDN)


class FakeWire:
    capabilities = frozenset({"write", "read", "eom", "go_to_local"})

    def __init__(self, scenario, target, trace):
        self.scenario, self.trace = scenario, trace
        self.metadata = dict(resource=target, adapter_identity=TARGET.adapter_identity)
        self.pending = None
        if scenario == "adapter_changed":
            self.metadata["adapter_identity"] = "OTHER-ADAPTER"
        if scenario == "resource_changed":
            self.metadata["resource"] = "FAKE::OTHER"
        if scenario == "no_local":
            self.capabilities -= {"go_to_local"}
        self.event("construct")

    def event(self, name, **fields):
        with self.trace.open("a") as handle:
            handle.write(json.dumps(dict(event=name, pid=os.getpid(), **fields)) + "\n")

    def open(self, timeout):
        self.event("open", timeout=timeout)
        if self.scenario == "absent":
            raise FileNotFoundError("Adapter absent")
        if self.scenario == "permission":
            raise PermissionError("Access denied")
        if self.scenario == "hang_open":
            time.sleep(20)
        if self.scenario == "crash":
            os._exit(19)

    def write(self, data, deadline):
        assert time.monotonic() < deadline
        self.event("write", command=data.decode())
        assert data in (b"*IDN?", b"SM", b"TR3")
        self.pending = data

    def read(self, deadline):
        self.event("read")
        if self.scenario == "hang_read":
            time.sleep(20)
        if self.scenario == "late_reply":
            time.sleep(1.2)
        if self.scenario == "missing_during_read":
            raise FileNotFoundError("Device vanished during command")
        if self.pending == b"*IDN?":
            if self.scenario == "wrong_model":
                return b"OTHER,MODEL,,1.0\r\n"
            if self.scenario == "firmware_changed":
                return b"HEWLETT-PACKARD,437B,,1.8\r\n"
            if self.scenario == "serial_changed":
                return b"HEWLETT-PACKARD,437B,OTHER,1.9\r\n"
            return IDN
        assert self.pending == b"SM"
        if self.scenario == "malformed_status":
            return b"MALFORMED\r\n"
        status = bytearray(status_fixture(logarithmic=False))
        if self.scenario == "source_on":
            status[16] = ord("1")
        if self.scenario == "instrument_error":
            status[1] = ord("1")
        return bytes(status)

    def return_local(self, deadline):
        assert time.monotonic() < deadline
        self.event("local")
        if self.scenario == "local_failed":
            raise OSError("Local return failed")
        return {"status": "failed" if self.scenario == "local_rejected" else "accepted"}

    def close(self):
        self.event("close")
        if self.scenario == "hang_close":
            time.sleep(20)
        if self.scenario == "close_failed":
            raise OSError("Close failed")
        if self.scenario == "lingering_after_receipt":
            # A normal probe receipt is not enough: the process must really exit.
            import atexit

            atexit.register(time.sleep, 20)


@dataclass
class Factory:
    trace: object
    scenarios: tuple = ("healthy",)
    simulation = True

    def __call__(self, resource, attempt):
        return FakeWire(
            self.scenarios[min(attempt - 1, len(self.scenarios) - 1)], resource, self.trace
        )


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run(tmp_path, scenarios=("healthy",), **kwargs):
    trace = tmp_path / "trace.jsonl"
    result = rec.run_simulated(
        tmp_path / "reconciliation",
        target=TARGET,
        factory=Factory(trace, scenarios),
        lock_root=tmp_path / "locks",
        failed_run_id="failed-original-run",
        prior_worker_stopped=kwargs.pop("prior_worker_stopped", True),
        **kwargs,
    )
    saved = json.loads((tmp_path / "reconciliation/reconciliation.json").read_text())
    assert saved == result and not result["workflow_resumed"]
    assert result["mode"] == "simulation" and not result["physical_identity_verified"]
    assert result["front_panel_confirmation"] == "not_provided"
    assert all(attempt["worker"]["stopped"] for attempt in result["attempts"])
    return result, events(trace)


def test_healthy_probe_has_no_measurement_source_or_resume_actions(tmp_path):
    original = tmp_path / "failed-capture.csv"
    original.write_bytes(b"retained failed evidence\n")
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    result, trace = run(tmp_path)
    assert result["status"] == "communication_reconciled" and len(result["attempts"]) == 1
    assert result["attempts"][0]["meter_serial_observed"] is None
    assert [event["command"] for event in trace if event["event"] == "write"] == [
        "*IDN?",
        "SM",
        "TR3",
    ]
    assert [event["event"] for event in trace][-2:] == ["local", "close"]
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before


def test_only_absence_before_commands_is_retried(tmp_path):
    result, trace = run(tmp_path, ("absent", "healthy"))
    assert result["status"] == "communication_reconciled"
    assert [attempt["reason"] for attempt in result["attempts"]] == ["adapter_absent", "verified"]
    assert len({event["pid"] for event in trace}) == 2
    first = trace[0]["pid"]
    assert not any(event["event"] == "write" for event in trace if event["pid"] == first)


def test_attempt_limit_leaves_failed_source_run_untouched(tmp_path):
    result, trace = run(tmp_path, ("absent",), policy=rec.Policy(max_attempts=3, retry_delay_s=0))
    assert (
        result["status"] == "operator_recovery_needed" and result["reason"] == "attempts_exhausted"
    )
    assert len(result["attempts"]) == 3
    assert not any(event["event"] == "write" for event in trace)


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("permission", "access_denied"),
        ("adapter_changed", "adapter_identity_changed"),
        ("resource_changed", "adapter_identity_changed"),
        ("firmware_changed", "instrument_identity_changed"),
        ("serial_changed", "instrument_identity_changed"),
        ("wrong_model", "probe_failed"),
        ("malformed_status", "probe_failed"),
        ("source_on", "reference_on"),
        ("instrument_error", "instrument_error"),
        ("no_local", "probe_failed"),
        ("local_failed", "probe_failed"),
        ("local_rejected", "local_return_failed"),
        ("close_failed", "close_failed"),
        ("crash", "worker_failed"),
    ],
)
def test_failed_gates_never_retry_or_activate_reference(tmp_path, scenario, reason):
    result, trace = run(tmp_path, (scenario, "healthy"))
    assert result["status"] == "operator_recovery_needed" and result["reason"] == reason
    assert len(result["attempts"]) == 1
    commands = [event["command"] for event in trace if event["event"] == "write"]
    assert not any(command in commands for command in ("OC0", "OC1", "TR2", "PR", "*CLS"))
    if scenario in ("adapter_changed", "resource_changed", "permission"):
        assert not commands
    if scenario in ("firmware_changed", "serial_changed", "wrong_model"):
        assert commands == ["*IDN?"]
    if scenario in ("source_on", "instrument_error", "malformed_status"):
        assert commands == ["*IDN?", "SM"]


@pytest.mark.parametrize("scenario", ["hang_open", "hang_read", "hang_close"])
def test_hung_operation_is_contained_by_real_parent_deadline(tmp_path, scenario):
    start = time.monotonic()
    result, _ = run(tmp_path, (scenario,), policy=rec.Policy(total_s=3, attempt_s=0.8))
    assert result["reason"] == "attempt_deadline" and result["status"] == "operator_recovery_needed"
    assert len(result["attempts"]) == 1 and result["attempts"][0]["worker"]["forced"]
    assert time.monotonic() - start < 3.75


def test_total_deadline_bounds_backoff_and_prevents_next_attempt(tmp_path):
    result, _ = run(
        tmp_path, ("absent",), policy=rec.Policy(total_s=2, attempt_s=2, retry_delay_s=5)
    )
    assert result["reason"] == "total_deadline" and len(result["attempts"]) == 1
    assert result["elapsed_s"] < 2.75


def test_cancellation_before_start_opens_nothing(tmp_path):
    result, trace = run(tmp_path, cancelled=lambda: True)
    assert result["status"] == "cancelled" and not result["attempts"] and not trace


def test_cancellation_during_blocked_io_disposes_worker_without_next_attempt(tmp_path):
    trace = tmp_path / "trace.jsonl"
    result, _ = run(
        tmp_path,
        ("hang_read",),
        cancelled=lambda: any(event["event"] == "read" for event in events(trace)),
    )
    assert result["status"] == "cancelled" and len(result["attempts"]) == 1
    assert result["attempts"][0]["worker"]["forced"]


def test_prior_worker_not_disposed_opens_nothing(tmp_path):
    result, trace = run(tmp_path, prior_worker_stopped=False)
    assert result["reason"] == "prior_worker_not_stopped" and not result["attempts"] and not trace


@pytest.mark.parametrize("lease", ["supervisor", "worker"])
def test_held_ownership_leases_prevent_any_factory_call(tmp_path, lease):
    locks = tmp_path / "locks"
    locks.mkdir()
    key = hashlib.sha256(TARGET.resource.encode()).hexdigest()
    with (locks / f"{key}.{lease}.lock").open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, trace = run(tmp_path)
    assert result["reason"] == "ownership_busy" and not result["attempts"] and not trace


@pytest.mark.parametrize(
    "policy",
    [
        rec.Policy(max_attempts=True),
        rec.Policy(max_attempts=0),
        rec.Policy(max_attempts=6),
        rec.Policy(total_s=float("nan")),
        rec.Policy(total_s=1),
        rec.Policy(attempt_s=float("inf")),
        rec.Policy(attempt_s=0),
        rec.Policy(retry_delay_s=-1),
    ],
)
def test_invalid_policy_never_creates_output_or_opens(tmp_path, policy):
    with pytest.raises(ValueError):
        run(tmp_path, policy=policy)
    assert not (tmp_path / "reconciliation").exists() and not (tmp_path / "trace.jsonl").exists()


def test_real_resources_and_unspecified_factories_are_rejected(tmp_path):
    for target, factory in [
        (
            rec.Target("USB0::0x03eb::0x2065::REAL::INSTR", TARGET.adapter_identity, IDN),
            Factory(tmp_path / "trace"),
        ),
        (TARGET, lambda resource, attempt: None),
    ]:
        with pytest.raises(ValueError):
            rec.run_simulated(
                tmp_path / "result",
                target=target,
                factory=factory,
                lock_root=tmp_path / "locks",
                failed_run_id="failed",
                prior_worker_stopped=True,
            )
    assert not list(tmp_path.iterdir())


def test_existing_output_is_never_overwritten_or_connected(tmp_path):
    output = tmp_path / "reconciliation"
    output.mkdir()
    precious = output / "reconciliation.json"
    precious.write_text("original")
    with pytest.raises(FileExistsError):
        run(tmp_path)
    assert precious.read_text() == "original" and not (tmp_path / "trace.jsonl").exists()


def test_receipt_from_worker_that_does_not_exit_is_not_accepted(tmp_path):
    result, _ = run(tmp_path, ("lingering_after_receipt",))
    assert result["status"] == "operator_recovery_needed" and result["reason"] == "worker_failed"
    assert result["attempts"][0]["worker"]["forced"] and len(result["attempts"]) == 1


def test_late_valid_reply_is_never_accepted(tmp_path):
    result, _ = run(tmp_path, ("late_reply",), policy=rec.Policy(total_s=3, attempt_s=0.8))
    assert result["status"] == "operator_recovery_needed" and result["reason"] == "attempt_deadline"
    assert len(result["attempts"]) == 1


def test_absence_exception_after_command_dispatch_is_not_retried(tmp_path):
    result, trace = run(tmp_path, ("missing_during_read", "healthy"))
    assert result["status"] == "operator_recovery_needed" and result["reason"] == "probe_failed"
    assert len(result["attempts"]) == 1
    assert [event["command"] for event in trace if event["event"] == "write"] == ["*IDN?"]


def test_cancellation_during_backoff_prevents_second_open(tmp_path):
    receipt = tmp_path / "reconciliation/reconciliation.json"

    def cancelled():
        if not receipt.exists():
            return False
        return bool(json.loads(receipt.read_text())["attempts"])

    result, _ = run(tmp_path, ("absent", "healthy"), cancelled=cancelled)
    assert result["status"] == "cancelled" and len(result["attempts"]) == 1


def hold_worker_lease(path, pipe):
    with rec._lease(path):
        pipe.send("held")
        time.sleep(20)


def test_previous_child_ownership_survives_its_supervisor(tmp_path):
    locks = tmp_path / "locks"
    locks.mkdir()
    key = hashlib.sha256(TARGET.resource.encode()).hexdigest()
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=hold_worker_lease, args=(locks / f"{key}.worker.lock", child))
    process.start()
    child.close()
    try:
        assert parent.poll(5) and parent.recv() == "held"
        result, trace = run(tmp_path)
        assert result["reason"] == "ownership_busy" and not trace and not result["attempts"]
    finally:
        parent.close()
        process.terminate()
        process.join(3)
        assert not process.is_alive()
        process.close()
