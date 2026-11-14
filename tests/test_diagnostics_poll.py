"""Full spawned diagnostic worker/real bridge with only injected USB/VISA fakes."""

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from test_diagnostics_lifecycle import RESOURCE, SERIAL, TARGET, events, run

from hp437b import diagnostics_physical as dp
from hp437b import diagnostics_poll as polling
from hp437b import reconciliation as rec
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture


@dataclass
class Backend:
    trace: object
    scenario: str = "healthy"
    simulation = True

    def __call__(self, resource):
        import pyvisa
        import usb.core
        import usb.util
        from pyvisa.constants import StatusCode

        trace, scenario = self.trace, self.scenario
        counts = {}

        def event(kind, **values):
            with trace.open("a") as f:
                f.write(json.dumps(dict(event=kind, **values)) + "\n")

        def native(stage):
            event("native", stage=stage)
            if scenario in (stage + "_hung", stage + "_late", stage + "_crash"):
                event("pending", stage=stage)
                if scenario.endswith("crash"):
                    os._exit(19)
                time.sleep(0.3 if scenario.endswith("late") else 30)
            if scenario == stage + "_timeout":
                raise TimeoutError("synthetic native timeout")

        descriptor = SimpleNamespace(
            bInterfaceNumber=0, bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1
        )

        class Device:
            idVendor, idProduct = 0x03EB, 0x2065
            serial_number, manufacturer, product = SERIAL, "XyphroLabs", "GpibUsb"

            def get_active_configuration(self):
                return [descriptor]

            def ctrl_transfer(self, kind, request, value, index, size, *, timeout):
                event("control", request=request, tag=value, timeout=timeout)
                assert kind == 0xA1 and index == 0 and 0 < timeout <= 2000
                if request == 7:
                    counts["caps"] = counts.get("caps", 0) + 1
                    if counts["caps"] == 2:
                        native("caps")
                    caps = bytearray.fromhex("010000010401000000000000000107070000000000000000")
                    if counts["caps"] == 2 and scenario == "caps_unsupported":
                        caps[14] = 2
                    return caps
                if request == 128:
                    assert value == 2 and size == 3
                    native("poll")
                    return {
                        "bad_control": b"\x80\x02\x00",
                        "short_control": b"\x01\x02",
                        "tag_control": b"\x01\x03\x00",
                        "nonzero": b"\x01\x02\x02",
                    }.get(scenario, b"\x01\x02\x00")
                assert request == 0xA1
                return b"\x80" if scenario == "local_rejected" else b"\x01"

        class Interrupt:
            bEndpointAddress, bmAttributes, wMaxPacketSize = 0x83, 3, 8

            def read(self, size, *, timeout):
                event("interrupt", size=size, timeout=timeout)
                assert size == 2 and 0 < timeout <= 2000
                native("interrupt")
                return {
                    "bad_interrupt": b"\x82",
                    "unsolicited": b"\x81\x40",
                    "mismatch": b"\x82\x01",
                    "nonzero": b"\x82\x02",
                }.get(scenario, b"\x82\x00")

        device = Device()
        interface = SimpleNamespace(
            usb_dev=device,
            usb_intf=descriptor,
            usb_intr_in=None if scenario == "no_endpoint" else Interrupt(),
        )

        class Handle:
            session = 42

            def __init__(self):
                self.visalib = self

            def write_raw(self, raw):
                self.pending = raw.decode()
                counts[self.pending] = counts.get(self.pending, 0) + 1
                event("write", command=self.pending)
                assert self.pending in ("*IDN?", "SM", "*SRE?", "*STB?", "TR1", "TR3")
                return len(raw)

            def read(self, session, size):
                code = self.pending
                event("read", command=code)
                if code == "*IDN?":
                    return TARGET.expected_idn, StatusCode.success
                if code == "*SRE?":
                    return (
                        b"004\r\n" if scenario == "mask_nonzero" else b"000\r\n"
                    ), StatusCode.success
                if code == "*STB?":
                    # Different values across the poll are permitted, not compared for equality.
                    if scenario == "post_stb_malformed" and counts[code] == 2:
                        return b"BAD\r\n", StatusCode.success
                    return (b"001\r\n" if counts[code] == 1 else b"000\r\n"), StatusCode.success
                if code == "TR1":
                    return {
                        "measurement_error": b"9.0001E+40\r\n",
                        "measurement_bad": b"BAD\r\n",
                    }.get(scenario, b"-5.0000E-08\r\n"), StatusCode.success
                assert code == "SM"
                raw = bytearray(status_fixture(logarithmic=False))
                if counts[code] == 1:
                    if scenario == "source_on":
                        raw[16] = ord("1")
                    if scenario == "standby":
                        raw[18] = ord("1")
                    if scenario == "entry_error":
                        raw[2:4] = b"82"
                else:
                    raw[18] = ord("1")
                    if scenario == "source_after":
                        raw[16] = ord("1")
                    if scenario == "flags_changed":
                        raw[24] = ord("1")
                return bytes(raw), StatusCode.success

            def close(self):
                event("close")
                if scenario == "lease_check":
                    key = hashlib.sha256(resource.encode()).hexdigest()
                    with pytest.raises(BlockingIOError):
                        with rec._lease(trace.parent / "locks" / (key + ".lock")):
                            pass
                    event("lease_held_through_close")
                if scenario == "close_error":
                    raise OSError("synthetic close failure")

        class Manager:
            def __init__(self, backend):
                assert backend == "@py"
                event("open")
                self.visalib = SimpleNamespace(sessions={42: SimpleNamespace(interface=interface)})

            def open_resource(self, selected, *, open_timeout):
                assert selected == resource
                return Handle()

            def close(self):
                event("manager_close")

        usb.core.find = lambda **kwargs: [device]
        usb.util.dispose_resources = lambda dev: None
        pyvisa.ResourceManager = Manager
        phy.importlib.metadata.version = lambda name: phy.PINS[name]
        return dp._DiagnosticBridge(resource)


def probe_run(tmp_path, scenario="healthy", **overrides):
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=False,
        serial_poll_probe=True,
        _factory_override=Backend(tmp_path / "trace.jsonl", scenario),
    )
    args.update(overrides)
    return run(tmp_path, **args)


def writes(trace):
    return [e["command"] for e in trace if e["event"] == "write"]


@pytest.mark.parametrize("scenario", ["healthy", "nonzero"])
def test_one_poll_and_followup_complete_but_no_end_to_end_support_claim(tmp_path, scenario):
    r, t = probe_run(tmp_path, scenario)
    assert r["status"] == "completed" and r["serial_poll_assessment"]["accepted_full_case"]
    assert not r["serial_poll_assessment"]["instrument_poll_success_verified"]
    assert not r["serial_poll_assessment"]["procedure_completion_verified"]
    assert r["front_panel_confirmation"] == "not_provided"
    assert len(r["queries"]) == 7 and all(q["accepted_before_deadline"] for q in r["queries"])
    p = r["queries"][3]
    assert p["poll_receipt"]["status"] == "adapter_reply_validated"
    assert p["value"]["adapter_status_byte"] == (2 if scenario == "nonzero" else 0)
    assert p["visa_read_status"] is None
    assert writes(t) == ["*IDN?", "SM", "*SRE?", "*STB?", "*STB?", "TR1", "SM", "TR3"]
    assert len([e for e in t if e["event"] == "control" and e["request"] == 128]) == 1
    assert r["transport_closed"] and r["local_return"]["status"] == "accepted"


@pytest.mark.parametrize("scenario", ["source_on", "standby", "entry_error", "mask_nonzero"])
def test_baseline_gate_never_polls_or_changes_mask(tmp_path, scenario):
    r, t = probe_run(tmp_path, scenario)
    assert r["status"] == "observation_stop"
    assert not r["serial_poll_assessment"]["accepted_full_case"]
    assert not any(e["event"] == "control" and e["request"] == 128 for e in t)
    assert "*STB?" not in writes(t) and "TR1" not in writes(t)


@pytest.mark.parametrize(
    "scenario",
    [
        "no_endpoint",
        "caps_unsupported",
        "bad_control",
        "short_control",
        "tag_control",
        "bad_interrupt",
        "unsolicited",
        "mismatch",
        "caps_timeout",
        "poll_timeout",
        "interrupt_timeout",
    ],
)
def test_failed_poll_raw_close_without_queries_cleanup_retry_or_reconnect(tmp_path, scenario):
    r, t = probe_run(tmp_path, scenario)
    assert r["status"] == "query_failed" and r["transport_closed"]
    assert not r["serial_poll_assessment"]["accepted_full_case"]
    assert writes(t) == ["*IDN?", "SM", "*SRE?", "*STB?"]
    assert sum(e["event"] == "open" for e in t) == 1
    assert sum(e["event"] == "control" and e["request"] == 128 for e in t) <= 1
    assert r["queries"][3]["status"] == "failed" and r["queries"][4]["status"] == "not_attempted"
    assert r["queries"][3]["poll_receipt"]["status"] == "failed"
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in t)
    if scenario == "unsolicited":
        assert r["queries"][3]["poll_receipt"]["interrupt_hex"] == "8140"


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("measurement_error", "observation_stop"),
        ("source_after", "observation_stop"),
        ("flags_changed", "observation_stop"),
        ("post_stb_malformed", "query_failed"),
        ("measurement_bad", "query_failed"),
        ("local_rejected", "cleanup_failed"),
        ("close_error", "cleanup_failed"),
    ],
)
def test_followup_and_cleanup_failures_cannot_claim_full_case(tmp_path, scenario, status):
    r, t = probe_run(tmp_path, scenario)
    assert r["status"] == status and not r["serial_poll_assessment"]["accepted_full_case"]
    assert r["queries"][3]["value"]["status"] == "adapter_reply_validated"
    assert writes(t).count("*STB?") == 2
    if status == "query_failed":
        assert "TR3" not in writes(t)


@pytest.mark.parametrize("stage", ["caps", "poll", "interrupt"])
@pytest.mark.parametrize("fault", ["late", "hung", "crash"])
def test_late_cancelled_hung_and_crashed_native_calls_are_disposed(tmp_path, stage, fault):
    path = tmp_path / "trace.jsonl"
    args = (
        dict(cancelled=lambda: any(e["event"] == "pending" for e in events(path)))
        if fault == "late"
        else dict(work_s=1, total_s=5)
    )
    started = time.monotonic()
    r, t = probe_run(tmp_path, stage + "_" + fault, **args)
    assert time.monotonic() - started < 6
    assert r["status"] in ("cancelled", "deadline", "worker_failed")
    assert not r["serial_poll_assessment"]["accepted_full_case"]
    assert r["worker"]["stopped"] and "TR1" not in writes(t) and "TR3" not in writes(t)
    assert r["queries"][3]["status"] in ("failed", "incomplete")
    assert r["queries"][4]["status"] == "not_attempted"


@pytest.mark.parametrize(
    "overrides",
    [
        {"serial_poll_probe": 1},
        {"lifecycle": True},
        {"numeric_entry": True},
        {"lp2_snapshot": True},
        {"acquisition_settings": True},
        {"include_latched_reads": True},
        {"confirmed_error_fixtures": True},
        {"confirmed": False},
        {"prior_worker_stopped": False},
    ],
)
def test_selection_and_supervision_guards_precede_usb(tmp_path, overrides):
    with pytest.raises(ValueError):
        probe_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


@pytest.mark.parametrize(
    "flags",
    [
        ["--serial-poll-probe", "--lifecycle"],
        ["--serial-poll-probe", "--include-latched-reads"],
        ["--serial-poll-probe", "--confirm-reference-control"],
        ["--serial-poll-probe"],
    ],
)
def test_cli_missing_confirmation_or_conflict_precedes_setup(flags):
    r = subprocess.run(
        [
            sys.executable,
            "tools/diagnose_meter.py",
            "--resource",
            RESOURCE,
            "--setup",
            "missing",
            "--output",
            "unused",
            *flags,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_shared_lease_blocks_open(tmp_path):
    root = tmp_path / "locks"
    root.mkdir()
    key = hashlib.sha256(RESOURCE.encode()).hexdigest()
    with rec._lease(root / (key + ".lock")):
        r, t = probe_run(tmp_path)
    assert r["status"] == "ownership_busy" and t == []


def test_unique_fixed_plan_and_no_new_normal_capabilities():
    rows = polling.plan()
    assert len(rows) == len({r["step_id"] for r in rows}) == 7
    assert sum(r["kind"] == "poll" for r in rows) == 1
    assert "serial_poll" not in dp._DiagnosticBridge.capabilities


def test_child_lease_is_held_through_raw_close(tmp_path):
    r, t = probe_run(tmp_path, "lease_check")
    assert r["status"] == "completed"
    assert any(e["event"] == "lease_held_through_close" for e in t)


def test_bridge_refuses_second_poll_even_if_called_directly(monkeypatch):
    from test_serial_poll_probe import Adapter

    from hp437b.errors import StateUncertain

    a = Adapter()
    a.probe(monkeypatch)
    wire = dp._DiagnosticBridge(RESOURCE)
    wire.manager = SimpleNamespace(
        visalib=SimpleNamespace(sessions={42: SimpleNamespace(interface=a.interface)})
    )
    wire.handle = SimpleNamespace(session=42)
    wire.poll_once(110, cancelled=lambda: False)
    with pytest.raises(StateUncertain):
        wire.poll_once(110, cancelled=lambda: False)
    assert len(a.calls) == 3
