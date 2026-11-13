"""Bounded communication reconciliation; never resumes a failed test.

run_simulated retains its fake-only boundary. The separately gated physical
bridge shares this engine; normal logging and its transport are unchanged.
"""

import fcntl
import hashlib
import json
import math
import multiprocessing
import signal
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import protocol
from .instrument import Instrument
from .logger import _atomic_json

DISPOSAL_S = 0.75


@dataclass(frozen=True)
class Policy:
    max_attempts: int = 2
    total_s: float = 12.0
    attempt_s: float = 4.0
    retry_delay_s: float = 0.25

    def validate(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be 1..5")
        for name, lower, upper in (
            ("total_s", 2, 120),
            ("attempt_s", 0.1, 30),
            ("retry_delay_s", 0, 5),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not lower <= value <= upper
            ):
                raise ValueError(f"{name} must be finite in {lower}..{upper}")


@dataclass(frozen=True)
class Target:
    resource: str
    adapter_identity: str
    expected_idn: bytes

    def validate(self):
        if (
            not isinstance(self.resource, str)
            or not self.resource.startswith("FAKE::")
            or len(self.resource) > 256
            or any(c.isspace() for c in self.resource)
        ):
            raise ValueError("Only an explicit FAKE:: simulated resource is supported")
        if (
            not isinstance(self.adapter_identity, str)
            or not self.adapter_identity.strip()
            or len(self.adapter_identity) > 256
        ):
            raise ValueError("Record the expected simulated adapter identity")
        if not isinstance(self.expected_idn, bytes) or len(self.expected_idn) > 256:
            raise ValueError("Record the expected bounded identification bytes")
        protocol.identification(self.expected_idn)


@contextmanager
def _lease(path):
    if path.is_symlink():
        raise ValueError("Symlink reconciliation locks are unsupported")
    with path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _identity(value):
    return value.manufacturer, value.model, value.serial, value.firmware


def _probe(pipe, target, factory, attempt, deadline, worker_lock, stop=None):
    """Child owns its lease through close, including if the parent disappears."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # Parent owns cancellation and bounded disposal.
    result = {"reason": "probe_failed", "retryable": False, "stage": "ownership"}
    wire = None

    def stage(name):
        result["stage"] = name
        pipe.send_bytes(json.dumps({"stage": name}).encode())
        if stop is not None and stop.is_set():
            raise InterruptedError("Reconciliation stopped; no further commands")
        if time.monotonic() >= deadline:
            raise TimeoutError("Reconciliation attempt expired")

    try:
        with _lease(Path(worker_lock)):
            try:
                stage("constructing")
                wire = factory(target.resource, attempt)
                stage("opening")
                wire.open(timeout=max(0.001, deadline - time.monotonic()))
                stage("adapter_identity")
                metadata = wire.metadata
                result["transport"] = dict(metadata)
                if (
                    metadata.get("resource") != target.resource
                    or metadata.get("adapter_identity") != target.adapter_identity
                ):
                    result["reason"] = "adapter_identity_changed"
                else:
                    instrument = Instrument(wire, timeout=max(0.001, deadline - time.monotonic()))
                    stage("instrument_identity")
                    observed = instrument.identify()
                    result["identification_raw_hex"] = observed.raw.hex()
                    result["meter_serial_observed"] = observed.serial or None
                    if _identity(observed) != _identity(
                        protocol.identification(target.expected_idn)
                    ):
                        result["reason"] = "instrument_identity_changed"
                    else:
                        stage("source_status")
                        instrument.timeout = max(0.001, deadline - time.monotonic())
                        status = instrument.read_status()
                        result["status_raw_hex"] = status.raw.hex()
                        result["reference_on"] = status.reference_on
                        if status.reference_on:
                            result["reason"] = "reference_on"
                        elif status.measurement_error or status.entry_error:
                            result["reason"] = "instrument_error"
                        else:
                            stage("free_run")
                            instrument.timeout = max(0.001, deadline - time.monotonic())
                            instrument.command("TR3")
                            stage("local_return")
                            instrument.timeout = max(0.001, deadline - time.monotonic())
                            local = instrument.bus("G008")
                            if not isinstance(local, dict) or local.get("status") != "accepted":
                                result["reason"] = "local_return_failed"
                            else:
                                result.update(reason="verified", local_return="accepted")
            except FileNotFoundError as exc:
                result.update(
                    reason="adapter_absent"
                    if result["stage"] in ("constructing", "opening")
                    else "probe_failed",
                    retryable=result["stage"] in ("constructing", "opening"),
                    error=str(exc)[:1000],
                )
            except PermissionError as exc:
                result.update(reason="access_denied", error=str(exc)[:1000])
            except Exception as exc:
                result.update(reason="probe_failed", error=f"{type(exc).__name__}: {exc}"[:1000])
            finally:
                if wire is not None:
                    try:
                        result["stage"] = "closing"
                        try:
                            pipe.send_bytes(json.dumps({"stage": "closing"}).encode())
                        finally:
                            wire.close()  # Raw close only, even after expiry/cancellation.
                    except Exception as exc:
                        result.update(
                            reason="close_failed",
                            retryable=False,
                            error=f"{type(exc).__name__}: {exc}"[:1000],
                        )
    except BlockingIOError:
        result.update(reason="worker_still_active", retryable=False)
    except Exception as exc:
        result.update(
            reason="probe_failed", retryable=False, error=f"{type(exc).__name__}: {exc}"[:1000]
        )
    try:
        pipe.send_bytes(json.dumps({"result": result}).encode())
    finally:
        pipe.close()


def _dispose(process, end):
    if process.pid is None:
        process.close()
        return {"stopped": True, "exitcode": None, "forced": False}
    process.join(timeout=max(0, min(0.25, end - time.monotonic())))
    forced = process.is_alive()
    if forced:
        process.terminate()
        process.join(timeout=max(0, min(0.25, end - time.monotonic())))
    if process.is_alive():
        process.kill()
        process.join(timeout=max(0, min(0.25, end - time.monotonic())))
    stopped = not process.is_alive()
    value = {"stopped": stopped, "exitcode": process.exitcode, "forced": forced}
    if stopped:
        process.close()
    return value


def _attempt(target, factory, number, deadline, end, worker_lock, cancelled, shutdown_grace_s=0):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    stop = context.Event()
    process = context.Process(
        target=_probe, args=(child, target, factory, number, deadline, str(worker_lock), stop)
    )
    process.daemon = True
    record = {"number": number, "reason": "worker_failed", "retryable": False, "stage": "starting"}
    started = time.monotonic()
    try:
        process.start()
        child.close()
        while True:
            if cancelled():
                record["reason"] = "cancelled"
                stop.set()
                break
            left = deadline - time.monotonic()
            if left <= 0:
                record["reason"] = "attempt_deadline"
                stop.set()
                break
            if parent.poll(min(0.02, left)):
                message = json.loads(parent.recv_bytes(8192))
                if time.monotonic() >= deadline:
                    record["reason"] = "attempt_deadline"  # Never accept late results.
                    stop.set()
                    break
                if "result" in message:
                    record.update(message["result"])
                    break
                record["stage"] = message["stage"]
    except Exception as exc:
        record.update(
            reason="worker_failed", retryable=False, error=f"{type(exc).__name__}: {exc}"[:1000]
        )
    finally:
        child.close()
        grace_started = time.monotonic()
        if shutdown_grace_s and process.pid is not None:
            process.join(timeout=max(0, min(shutdown_grace_s, end - DISPOSAL_S - time.monotonic())))
        record["shutdown_grace"] = {
            "budget_s": shutdown_grace_s,
            "elapsed_s": time.monotonic() - grace_started,
        }
        parent.close()
        record["worker"] = _dispose(process, end)
        record["elapsed_s"] = time.monotonic() - started
    if not record["worker"]["stopped"]:
        record.update(reason="worker_not_stopped", retryable=False)
    elif record["worker"]["forced"] or record["worker"]["exitcode"] != 0:
        # A receipt cannot release another attempt until the child exits normally.
        record["retryable"] = False
        if record["reason"] in ("verified", "adapter_absent"):
            record["reason"] = "worker_failed"
    return record


def _run(
    output,
    *,
    target,
    factory,
    lock_root,
    failed_run_id,
    prior_worker_stopped,
    policy=None,
    cancelled=lambda: False,
    mode="simulation",
    worker_lock_path=None,
    shutdown_grace_s=0,
    context=None,
):
    """Write a new reconciliation receipt from explicit fakes; failed data is never opened.

    The factory must be spawn-picklable, declare simulation=True, and return a
    transport with open/close and resource/adapter_identity metadata. Only absent
    adapters before command dispatch are retried. Existing UI attestations stay intact.
    """
    target.validate()
    policy = policy if policy is not None else Policy()
    policy.validate()
    if not isinstance(failed_run_id, str) or not failed_run_id.strip() or len(failed_run_id) > 256:
        raise ValueError("Record the failed run identity")
    if type(prior_worker_stopped) is not bool:
        raise ValueError("prior_worker_stopped must be an explicit boolean")
    started = time.monotonic()
    end = started + policy.total_s
    work_end = end - DISPOSAL_S - shutdown_grace_s
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    path = output / "reconciliation.json"
    result = dict(
        schema="hp437b.reconciliation.v1",
        mode=mode,
        failed_run_id=failed_run_id,
        started_utc=datetime.now(UTC).isoformat(),
        policy=asdict(policy),
        target=dict(
            resource=target.resource,
            adapter_identity=target.adapter_identity,
            identification_raw_hex=target.expected_idn.hex(),
        ),
        status="operator_recovery_needed",
        reason="prior_worker_not_stopped",
        attempts=[],
        prior_worker_stopped=prior_worker_stopped,
        workflow_resumed=False,
        front_panel_confirmation="not_provided",
        physical_identity_verified=False,
        context=context or {},
    )
    _atomic_json(path, result)  # Reserve/persist before launching a child.
    try:
        if cancelled():
            result.update(status="cancelled", reason="cancelled")
        elif prior_worker_stopped:
            root = Path(lock_root)
            root.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(target.resource.encode()).hexdigest()
            worker_lock = (
                Path(worker_lock_path)
                if worker_lock_path is not None
                else root / (key + ".worker.lock")
            )
            try:
                with _lease(root / (key + ".supervisor.lock")):
                    with _lease(worker_lock):
                        pass  # Check orphan ownership before launching; child holds its own lease.
                    for number in range(1, policy.max_attempts + 1):
                        if cancelled():
                            result.update(status="cancelled", reason="cancelled")
                            break
                        if time.monotonic() >= work_end:
                            result["reason"] = "total_deadline"
                            break
                        attempt = _attempt(
                            target,
                            factory,
                            number,
                            min(work_end, time.monotonic() + policy.attempt_s),
                            end,
                            worker_lock,
                            cancelled,
                            shutdown_grace_s,
                        )
                        result["attempts"].append(attempt)
                        result["reason"] = attempt["reason"]
                        _atomic_json(path, result)
                        if time.monotonic() >= end:
                            result["reason"] = "total_deadline"
                            break
                        if attempt["reason"] == "cancelled" or cancelled():
                            result.update(status="cancelled", reason="cancelled")
                            break
                        if attempt["reason"] == "verified":
                            result.update(status="communication_reconciled", reason="verified")
                            break
                        if not attempt["retryable"]:
                            break
                        if number == policy.max_attempts:
                            result["reason"] = "attempts_exhausted"
                            break
                        wake = min(work_end, time.monotonic() + policy.retry_delay_s)
                        while time.monotonic() < wake and not cancelled():
                            time.sleep(max(0, min(0.02, wake - time.monotonic())))
            except BlockingIOError:
                result["reason"] = "ownership_busy"
    finally:
        result.update(
            finished_utc=datetime.now(UTC).isoformat(), elapsed_s=time.monotonic() - started
        )
        _atomic_json(path, result)
    return result


def run_simulated(
    output,
    *,
    target,
    factory,
    lock_root,
    failed_run_id,
    prior_worker_stopped,
    policy=None,
    cancelled=lambda: False,
):
    """Fake-only entry point; physical resources and factories remain rejected."""
    if type(target) is not Target or getattr(factory, "simulation", None) is not True:
        raise ValueError("An explicitly simulated target and factory are required")
    return _run(
        output,
        target=target,
        factory=factory,
        lock_root=lock_root,
        failed_run_id=failed_run_id,
        prior_worker_stopped=prior_worker_stopped,
        policy=policy,
        cancelled=cancelled,
    )
