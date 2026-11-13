"""Physical entry point and actual bridge exercised only through injected backend fakes."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from hp437b import reconciliation as rec
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture

SERIAL = "HEWLETT-PACKARD_437B_1.9"
RESOURCE = f"USB0::1003::8293::{SERIAL}::0::INSTR"
IDN = b"HEWLETT-PACKARD,437B,,1.9\r\n"
TARGET = phy.PhysicalTarget(RESOURCE, SERIAL, IDN)
EQUIPMENT = dict(meter_serial="SYNTHETIC-METER", sensor_serial="SYNTHETIC-SENSOR")
PREPARED = dict.fromkeys(phy.PREPARED, True)


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@dataclass
class BackendFactory:
    trace: Path
    scenario: str = "healthy"
    simulation = True

    def __call__(self, resource, attempt):
        # These replacements are local to the spawned child and explicit under offline QA.
        import pyvisa
        import usb.core
        import usb.util

        trace, scenario = self.trace, self.scenario

        def event(operation, **details):
            with trace.open("a") as handle:
                handle.write(
                    json.dumps(dict(operation=operation, pid=os.getpid(), **details)) + "\n"
                )

        class Device:
            idVendor, idProduct = 0x03EB, 0x2065
            serial_number, manufacturer, product = SERIAL, "XyphroLabs", "GpibUsb"

            def get_active_configuration(self):
                return [interface]

            def ctrl_transfer(self, kind, request, value, index, size, *, timeout):
                event("control", request=request, timeout=timeout)
                assert (kind, value, index) == (0xA1, 0, 0)
                if request == 7:
                    caps = bytearray(24)
                    caps[0], caps[14] = 1, 2
                    if scenario == "unsupported_local":
                        caps[14] = 0
                    return caps
                assert request == 0xA1 and size == 1
                return b"\x80" if scenario == "local_rejected" else b"\x01"

        interface = SimpleNamespace(
            bInterfaceNumber=0, bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1
        )
        device = Device()
        if scenario == "descriptor_changed":
            device.product = "OTHER"
        if scenario == "interface_changed":
            interface.bInterfaceProtocol = 0

        def find(**kwargs):
            event("find", attempt=attempt)
            if scenario == "permission":
                raise usb.core.USBError("Access denied", error_code=-3, errno=13)
            if scenario == "absent" or (scenario == "absent_then_healthy" and attempt == 1):
                return []
            return [device, device] if scenario == "duplicate" else [device]

        class Handle:
            session = 42
            pending = None

            def __init__(self):
                self.visalib = self

            def write_raw(self, data):
                self.pending = data
                event("write", command=data.decode(), timeout=self.timeout)
                assert data in (b"*IDN?", b"SM", b"TR3")
                return len(data) - 1 if scenario == "partial_write" else len(data)

            def read(self, session, size):
                from pyvisa.constants import StatusCode

                event("read", timeout=self.timeout)
                if scenario == "read_hang":
                    time.sleep(30)
                if self.pending == b"SM" and scenario in ("abort", "late_after_cancel"):
                    event("native_pending")
                    time.sleep(0.3)
                    event("native_finished")
                    if scenario == "abort":
                        raise TimeoutError("Simulated native abort completed")
                if self.pending == b"*IDN?":
                    raw = b"HEWLETT-PACKARD,437B,,1.8\r\n" if scenario == "id_changed" else IDN
                else:
                    assert self.pending == b"SM"
                    status = bytearray(status_fixture(logarithmic=False))
                    if scenario == "source_on":
                        status[16] = ord("1")
                    raw = b"INVALID\r\n" if scenario == "malformed" else bytes(status)
                if scenario == "oversize":
                    raw = b"x" * 4097
                return (
                    raw,
                    StatusCode.success_max_count_read
                    if scenario == "incomplete"
                    else StatusCode.success,
                )

            def close(self):
                event("handle_close")
                if scenario == "close_failed":
                    raise OSError("Handle close failed")

        class Manager:
            def __init__(self, backend):
                assert backend == "@py"
                event("manager")
                opened = Device()
                if scenario == "opened_changed":
                    opened.serial_number = "DIFFERENT"
                self.visalib = SimpleNamespace(
                    sessions={
                        42: SimpleNamespace(
                            interface=SimpleNamespace(usb_dev=opened, usb_intf=interface)
                        )
                    }
                )

            def open_resource(self, selected, *, open_timeout):
                assert selected == resource
                event("open", timeout=open_timeout)
                return Handle()

            def close(self):
                event("manager_close")

        usb.core.find = find
        usb.util.dispose_resources = lambda dev: event("dispose_descriptor")
        pyvisa.ResourceManager = Manager
        phy.importlib.metadata.version = lambda name: (
            "0.0" if scenario == "versions_changed" else phy.PINS[name]
        )
        return phy._Bridge(resource)


def run(tmp_path, scenario="healthy", **overrides):
    trace = tmp_path / "trace.jsonl"
    args = dict(
        target=TARGET,
        prepared=PREPARED,
        equipment=EQUIPMENT,
        confirmed=True,
        prior_worker_stopped=True,
        workflow_lock_root=tmp_path / "locks",
        failed_run_id="synthetic-failed-run",
        _factory=BackendFactory(trace, scenario),
    )
    args.update(overrides)
    result = phy.run_physical(tmp_path / "result", **args)
    assert result == json.loads((tmp_path / "result/reconciliation.json").read_text())
    assert result["mode"] == "physical" and result["context"]["evidence_origin"] == "injected_fake"
    assert not result["workflow_resumed"] and not result["physical_identity_verified"]
    assert result["front_panel_confirmation"] == "not_provided"
    assert all(attempt["worker"]["stopped"] for attempt in result["attempts"])
    return result, events(trace)


def test_actual_bridge_protocol_and_native_timeouts_through_spawned_fakes(tmp_path):
    result, trace = run(tmp_path)
    assert result["status"] == "communication_reconciled"
    assert [e["command"] for e in trace if e["operation"] == "write"] == ["*IDN?", "SM", "TR3"]
    assert all(0 < e["timeout"] <= 2000 for e in trace if "timeout" in e)
    assert result["attempts"][0]["transport"]["versions"] == phy.PINS
    assert (
        trace[-2:][0]["operation"] == "handle_close" and trace[-1]["operation"] == "manager_close"
    )
    assert next(i for i, e in enumerate(trace) if e["operation"] == "dispose_descriptor") < next(
        i for i, e in enumerate(trace) if e["operation"] == "manager"
    )


@pytest.mark.parametrize(
    "scenario,reason",
    [
        ("permission", "access_denied"),
        ("descriptor_changed", "probe_failed"),
        ("interface_changed", "probe_failed"),
        ("duplicate", "probe_failed"),
        ("opened_changed", "probe_failed"),
        ("versions_changed", "probe_failed"),
        ("unsupported_local", "probe_failed"),
        ("id_changed", "instrument_identity_changed"),
        ("malformed", "probe_failed"),
        ("source_on", "reference_on"),
        ("partial_write", "probe_failed"),
        ("incomplete", "probe_failed"),
        ("oversize", "probe_failed"),
        ("local_rejected", "probe_failed"),
        ("close_failed", "close_failed"),
    ],
)
def test_backend_and_policy_failures_stop_without_reset_source_write_or_retry(
    tmp_path, scenario, reason
):
    result, trace = run(
        tmp_path, scenario, policy=rec.Policy(max_attempts=2, total_s=30, attempt_s=10)
    )
    assert result["status"] == "operator_recovery_needed" and result["reason"] == reason
    assert len(result["attempts"]) == 1
    assert not any(e.get("command") in ("OC0", "OC1", "TR2", "PR", "*CLS") for e in trace)
    if scenario in (
        "descriptor_changed",
        "interface_changed",
        "duplicate",
        "opened_changed",
        "versions_changed",
        "unsupported_local",
    ):
        assert not any(e["operation"] == "write" for e in trace)


def test_absence_can_be_retried_only_after_normal_disposal(tmp_path):
    result, trace = run(
        tmp_path, "absent_then_healthy", policy=rec.Policy(max_attempts=2, total_s=30, attempt_s=10)
    )
    assert result["status"] == "communication_reconciled" and len(result["attempts"]) == 2
    assert result["attempts"][0]["reason"] == "adapter_absent"
    assert not result["attempts"][0]["worker"]["forced"]
    assert sum(e["operation"] == "open" for e in trace) == 1


@pytest.mark.parametrize("scenario", ["abort", "late_after_cancel"])
def test_cancel_allows_native_completion_but_no_further_commands_or_late_success(
    tmp_path, scenario
):
    trace = tmp_path / "trace.jsonl"
    result, trace = run(
        tmp_path,
        scenario,
        cancelled=lambda: any(e["operation"] == "native_pending" for e in events(trace)),
    )
    assert result["status"] == "cancelled" and not result["attempts"][0]["worker"]["forced"]
    assert any(e["operation"] == "native_finished" for e in trace)
    assert [e["command"] for e in trace if e["operation"] == "write"] == ["*IDN?", "SM"]
    assert result["attempts"][0]["shutdown_grace"]["budget_s"] == 3


def test_uncooperative_native_read_is_bounded_and_no_retry_follows(tmp_path):
    start = time.monotonic()
    result, _ = run(
        tmp_path, "read_hang", policy=rec.Policy(max_attempts=2, total_s=12, attempt_s=6)
    )
    assert result["status"] == "operator_recovery_needed" and result["reason"] == "attempt_deadline"
    assert len(result["attempts"]) == 1 and result["attempts"][0]["worker"]["forced"]
    assert time.monotonic() - start < 12.75


def test_shared_workflow_lock_prevents_physical_factory_io(tmp_path):
    import fcntl

    root = tmp_path / "locks"
    root.mkdir()
    path = root / (hashlib.sha256(RESOURCE.encode()).hexdigest() + ".lock")
    with path.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, trace = run(tmp_path)
    assert result["reason"] == "ownership_busy" and not result["attempts"] and not trace


@pytest.mark.parametrize(
    "overrides",
    [
        dict(confirmed=False),
        dict(prepared={}),
        dict(equipment={}),
        dict(target=phy.PhysicalTarget("USB0::1::2::OTHER::0::INSTR", "OTHER", IDN)),
        dict(policy=rec.Policy(total_s=5, attempt_s=4)),
        dict(_factory=object()),
    ],
)
def test_preparation_profile_and_policy_guards_precede_open(tmp_path, overrides):
    with pytest.raises(ValueError):
        run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


def test_prior_worker_guard_prevents_open_even_with_valid_physical_preparation(tmp_path):
    result, trace = run(tmp_path, prior_worker_stopped=False)
    assert result["reason"] == "prior_worker_not_stopped" and not trace


def test_parent_cancellation_protects_native_worker_from_keyboard_interrupt(tmp_path):
    trace = tmp_path / "trace.jsonl"
    sent = False

    def cancelled():
        nonlocal sent
        pending = [e for e in events(trace) if e["operation"] == "native_pending"]
        if pending and not sent:
            os.kill(pending[0]["pid"], signal.SIGINT)
            sent = True
        return sent

    result, observed = run(tmp_path, "abort", cancelled=cancelled)
    assert sent and result["status"] == "cancelled"
    assert any(e["operation"] == "native_finished" for e in observed)
    assert not result["attempts"][0]["worker"]["forced"]


def test_standalone_help_and_missing_confirmation_cannot_open_hardware(tmp_path):
    root = Path(__file__).parents[1]
    tool = root / "tools/reconcile_meter.py"
    help_result = subprocess.run(
        [sys.executable, str(tool), "--help"], capture_output=True, text=True
    )
    assert help_result.returncode == 0 and "confirm-supervised" in help_result.stdout
    rejected = subprocess.run(
        [
            sys.executable,
            str(tool),
            "--resource",
            RESOURCE,
            "--setup",
            str(tmp_path / "missing.json"),
            "--output",
            str(tmp_path / "out"),
            "--failed-run-id",
            "fake",
        ],
        capture_output=True,
        text=True,
    )
    assert rejected.returncode == 2 and "Fresh supervised setup confirmation" in rejected.stderr
    assert not list(tmp_path.iterdir())
