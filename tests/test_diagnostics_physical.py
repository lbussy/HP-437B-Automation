"""Real supervised runner/USB bridge with only explicitly injected backend fakes."""

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

from hp437b import diagnostics_physical as dp
from hp437b import reconciliation as rec
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture

SERIAL = "HEWLETT-PACKARD_437B_1.9"
RESOURCE = f"USB0::1003::8293::{SERIAL}::0::INSTR"
TARGET = phy.PhysicalTarget(RESOURCE, SERIAL, b"HEWLETT-PACKARD,437B,,1.9\r\n")
EQUIPMENT = dict(meter_serial="SYNTHETIC-METER", sensor_serial="SYNTHETIC-SENSOR")
PREPARED = dict.fromkeys(dp.PREPARED, True)


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@dataclass
class BackendFactory:
    trace: Path
    scenario: str = "healthy"
    simulation = True

    def __call__(self, resource):
        import pyvisa
        import usb.core
        import usb.util

        trace, scenario = self.trace, self.scenario

        def event(operation, **details):
            with trace.open("a") as handle:
                handle.write(
                    json.dumps(dict(operation=operation, pid=os.getpid(), **details)) + "\n"
                )

        interface = SimpleNamespace(
            bInterfaceNumber=0, bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1
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
                    caps[0], caps[14] = 1, 0 if scenario == "no_local" else 2
                    return caps
                assert request == 0xA1 and size == 1
                return b"\x80" if scenario == "local_rejected" else b"\x01"

        device = Device()
        if scenario == "descriptor_changed":
            device.product = "OTHER"
        if scenario == "interface_changed":
            interface.bInterfaceProtocol = 0

        def find(**kwargs):
            event("find")
            if scenario == "permission":
                raise usb.core.USBError("Access denied", error_code=-3, errno=13)
            if scenario == "absent":
                return []
            return [device, device] if scenario == "duplicate" else [device]

        class Handle:
            session = 42
            pending = None

            def __init__(self):
                self.visalib = self

            def write_raw(self, data):
                self.pending = data.decode()
                event("write", command=self.pending, timeout=self.timeout)
                assert self.pending in (
                    "*IDN?",
                    "*ESE?",
                    "*SRE?",
                    "*STB?",
                    "OD",
                    "ERR?",
                    "*ESR?",
                    "SM",
                    "TR3",
                )
                return (
                    len(data) - 1
                    if scenario == "partial_write" and self.pending == "*SRE?"
                    else len(data)
                )

            def read(self, session, size):
                from pyvisa.constants import StatusCode

                code = self.pending
                event("read", command=code, timeout=self.timeout)
                replies = {
                    "*IDN?": TARGET.expected_idn,
                    "*ESE?": b"000\r\n",
                    "*SRE?": b"004\r\n",
                    "*STB?": b"012\r\n",
                    "OD": b"-0.050 uW\r\n",
                    "ERR?": b"091\r\n",
                    "*ESR?": b"032\r\n",
                    "SM": status_fixture(logarithmic=False),
                }
                raw = replies[code]
                if code == "*IDN?" and scenario == "id_changed":
                    raw = b"HEWLETT-PACKARD,437B,,1.8\r\n"
                status = StatusCode.success
                if code == "*SRE?":
                    if scenario == "malformed":
                        raw = b"\xffBROKEN\r\n"
                    if scenario == "incomplete":
                        raw, status = b"004", StatusCode.success_max_count_read
                    if scenario == "oversize":
                        raw = b"x" * 4097
                    if scenario == "read_error":
                        raise TimeoutError("Simulated native abort complete")
                    if scenario in ("abort_after_cancel", "late_after_cancel"):
                        event("native_pending")
                        time.sleep(0.3)
                        event("native_finished")
                        if scenario == "abort_after_cancel":
                            raise TimeoutError("Simulated native abort complete")
                    if scenario == "late_after_deadline":
                        time.sleep(1.3)
                    if scenario == "child_sigint":
                        os.kill(os.getpid(), signal.SIGINT)
                    if scenario == "hung":
                        event("native_pending")
                        time.sleep(30)
                return raw, status

            def close(self):
                event("handle_close")
                if scenario == "lease_check":
                    root = trace.parent / "locks"
                    key = hashlib.sha256(resource.encode()).hexdigest()
                    for suffix in (".lock", ".diagnostics.lock"):
                        try:
                            with rec._lease(root / (key + suffix)):
                                raise AssertionError("Lease released before raw close")
                        except BlockingIOError:
                            event("lease_held", suffix=suffix)
                if scenario == "close_failed":
                    raise OSError("Handle close failed")

        class Manager:
            def __init__(self, backend):
                assert backend == "@py"
                event("manager")
                opened = Device()
                if scenario == "opened_changed":
                    opened.serial_number = "OTHER"
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
        return dp._DiagnosticBridge(resource)


def run(tmp_path, scenario="healthy", **overrides):
    trace = tmp_path / "trace.jsonl"
    options = dict(
        target=TARGET,
        prepared=PREPARED,
        equipment=EQUIPMENT,
        confirmed=True,
        prior_worker_stopped=True,
        workflow_lock_root=tmp_path / "locks",
        _factory_override=BackendFactory(trace, scenario),
    )
    options.update(overrides)
    result = dp.run_physical(tmp_path / "result", **options)
    assert result == json.loads((tmp_path / "result/diagnostics.json").read_text())
    assert result["evidence_origin"] == "injected_fake"
    assert not result["physical_identity_verified"]
    assert result["front_panel_confirmation"] == "not_provided"
    assert result["worker"]["stopped"]
    return result, events(trace)


def writes(trace):
    return [event["command"] for event in trace if event["operation"] == "write"]


def test_actual_bridge_basic_diagnostics_without_sm_or_mask_setters(tmp_path):
    result, trace = run(tmp_path)
    assert result["status"] == "completed" and result["transport_closed"]
    assert writes(trace) == ["*IDN?", "*ESE?", "*SRE?", "*STB?", "OD", "TR3"]
    assert result["transport"]["versions"] == phy.PINS
    assert all(0 < e["timeout"] <= 2000 for e in trace if "timeout" in e)
    assert all(row["accepted_before_deadline"] for row in result["queries"])
    assert result["queries"][1]["value"] == 4
    assert result["queries"][1]["raw_hex"] == b"004\r\n".hex()
    assert result["local_return"]["status"] == "accepted"
    assert result["health_verdict"].startswith("Not evaluated")
    assert (
        trace[-2:][0]["operation"] == "handle_close" and trace[-1]["operation"] == "manager_close"
    )
    assert next(i for i, e in enumerate(trace) if e["operation"] == "dispose_descriptor") < next(
        i for i, e in enumerate(trace) if e["operation"] == "manager"
    )


def test_explicit_latch_option_puts_sm_last_and_keeps_error_values_without_health_pass(tmp_path):
    result, trace = run(tmp_path, include_latched_reads=True)
    assert result["status"] == "completed"
    assert writes(trace)[-4:] == ["ERR?", "*ESR?", "SM", "TR3"]
    assert result["queries"][-3]["value"] == 91
    assert result["queries"][-2]["value"] == 32
    assert result["queries"][-1]["value"]["reference_on"] is False


@pytest.mark.parametrize(
    "scenario",
    [
        "absent",
        "permission",
        "descriptor_changed",
        "interface_changed",
        "duplicate",
        "opened_changed",
        "versions_changed",
        "no_local",
        "id_changed",
    ],
)
def test_identity_access_and_backend_failures_do_not_start_diagnostics_or_retry(tmp_path, scenario):
    result, trace = run(tmp_path, scenario)
    assert result["status"] == "preflight_failed"
    assert not any(c in writes(trace) for c in ("*ESE?", "SM", "TR3"))
    assert sum(e["operation"] == "find" for e in trace) <= 1
    assert all(row["status"] == "not_attempted" for row in result["queries"])


@pytest.mark.parametrize(
    "scenario,raw",
    [
        ("malformed", b"\xffBROKEN\r\n"),
        ("incomplete", b"004"),
        ("oversize", b"x" * 4097),
        ("read_error", b""),
        ("partial_write", b""),
    ],
)
def test_query_failure_keeps_partial_raw_without_further_commands(tmp_path, scenario, raw):
    result, trace = run(tmp_path, scenario)
    assert result["status"] == "query_failed"
    assert writes(trace) == ["*IDN?", "*ESE?", "*SRE?"]
    assert result["queries"][1]["raw_hex"] == raw.hex()
    assert result["queries"][1]["status"] == "failed"
    assert result["queries"][2]["status"] == "not_attempted"
    assert result["transport_closed"]
    if scenario == "incomplete":
        assert result["queries"][1]["visa_read_status"] != 0


@pytest.mark.parametrize("scenario", ["local_rejected", "close_failed"])
def test_cleanup_failure_retains_queries_without_retries(tmp_path, scenario):
    result, trace = run(tmp_path, scenario)
    assert result["status"] == "cleanup_failed"
    assert all(row["status"] == "completed" for row in result["queries"])
    assert writes(trace).count("TR3") == 1
    assert sum(e["operation"] == "handle_close" for e in trace) == 1


@pytest.mark.parametrize("scenario", ["abort_after_cancel", "late_after_cancel"])
def test_cancellation_preserves_native_finish_and_close_but_rejects_late_success(
    tmp_path, scenario
):
    trace = tmp_path / "trace.jsonl"
    result, trace_events = run(
        tmp_path,
        scenario,
        cancelled=lambda: any(e["operation"] == "native_pending" for e in events(trace)),
    )
    assert result["status"] == "cancelled"
    assert result["transport_closed"] and not result["worker"]["forced"]
    assert result["queries"][1]["status"] == "failed"
    assert not result["queries"][1]["accepted_before_deadline"]
    assert writes(trace_events) == ["*IDN?", "*ESE?", "*SRE?"]
    assert any(e["operation"] == "native_finished" for e in trace_events)


def test_hung_native_call_has_bounded_disposal_and_unknown_transport_close(tmp_path):
    result, trace = run(tmp_path, "hung", work_s=1, total_s=5)
    assert result["status"] == "deadline" and result["worker"]["forced"]
    assert result["transport_closed"] is None
    assert result["elapsed_s"] < 5.5
    assert writes(trace) == ["*IDN?", "*ESE?", "*SRE?"]
    assert result["queries"][1]["status"] == "incomplete"


@pytest.mark.parametrize("shared", [True, False])
def test_shared_resource_or_diagnostics_lock_prevents_even_discovery(tmp_path, shared):
    root = tmp_path / "locks"
    root.mkdir()
    key = hashlib.sha256(RESOURCE.encode()).hexdigest()
    with rec._lease(root / (key + (".lock" if shared else ".diagnostics.lock"))):
        result, trace = run(tmp_path)
    assert result["status"] == "ownership_busy" and not trace
    assert result["worker"]["exitcode"] is None


@pytest.mark.parametrize(
    "options",
    [
        {"confirmed": False},
        {"prior_worker_stopped": False},
        {"prepared": {}},
        {"equipment": {}},
        {"include_latched_reads": 1},
        {"work_s": float("nan")},
        {"work_s": True},
        {"total_s": 5},
        {"target": "USB::ANY"},
        {"_factory_override": lambda *args: None},
    ],
)
def test_invalid_or_unconfirmed_request_does_not_reserve_output(tmp_path, options):
    with pytest.raises(ValueError):
        run(tmp_path, **options)
    assert not (tmp_path / "result").exists()
    assert not (tmp_path / "trace.jsonl").exists()


def test_cancelled_before_start_does_not_discover_or_write(tmp_path):
    result, trace = run(tmp_path, cancelled=lambda: True)
    assert result["status"] == "cancelled" and not trace


def test_output_is_not_overwritten(tmp_path):
    path = tmp_path / "result"
    path.mkdir()
    (path / "diagnostics.json").write_bytes(b"original")
    with pytest.raises(FileExistsError):
        run(tmp_path)
    assert (path / "diagnostics.json").read_bytes() == b"original"


@pytest.mark.parametrize(
    "arguments", [["--help"], ["--resource", RESOURCE, "--setup", "missing", "--output", "unused"]]
)
def test_standalone_help_and_missing_confirmations_are_hardware_free(arguments):
    result = subprocess.run(
        [sys.executable, "tools/diagnose_meter.py", *arguments],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == (0 if arguments == ["--help"] else 2)
    assert "offline QA forbids hardware" not in result.stderr


def test_late_deadline_reply_is_retained_but_cannot_complete_the_batch(tmp_path):
    result, trace = run(tmp_path, "late_after_deadline", work_s=1, total_s=5)
    assert result["status"] == "deadline"
    assert result["transport_closed"] and not result["worker"]["forced"]
    row = result["queries"][1]
    assert row["status"] == "failed" and row["raw_hex"] == b"004\r\n".hex()
    assert not row["accepted_before_deadline"]
    assert writes(trace) == ["*IDN?", "*ESE?", "*SRE?"]


def test_child_sigint_is_ignored_so_parent_remains_cancellation_owner(tmp_path):
    result, trace = run(tmp_path, "child_sigint")
    assert result["status"] == "completed"
    assert result["transport_closed"] and result["worker"]["exitcode"] == 0


def test_parent_and_worker_keep_their_leases_through_native_close(tmp_path):
    result, trace = run(tmp_path, "lease_check")
    assert result["status"] == "completed"
    assert {e["suffix"] for e in trace if e["operation"] == "lease_held"} == {
        ".lock",
        ".diagnostics.lock",
    }
