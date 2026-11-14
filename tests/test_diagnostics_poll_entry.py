"""Competing entry-latch/cache models through the actual isolated worker."""

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
from hp437b import diagnostics_poll_entry as entry
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture


@dataclass
class Backend:
    trace: object
    scenario: str = "clears"
    simulation = True

    def __call__(self, resource):
        import pyvisa
        import usb.core
        import usb.util
        from pyvisa.constants import StatusCode

        scenario, trace = self.scenario, self.trace
        counts = {}
        state = dict(entry=0, esr=0, stb=0, poll=0, injected=False, polled=False)

        def event(kind, **values):
            with trace.open("a") as f:
                f.write(json.dumps(dict(event=kind, **values)) + "\n")

        def native(stage):
            event("native", stage=stage)
            if scenario == stage + "_crash":
                os._exit(19)
            if scenario in (stage + "_late", stage + "_hung"):
                event("pending")
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
                event("control", request=request, tag=value)
                assert kind == 0xA1 and index == 0 and 0 < timeout <= 2000
                if request == 7:
                    counts["caps"] = counts.get("caps", 0) + 1
                    if counts["caps"] == 2:
                        native("caps")
                    return bytes.fromhex("010000010401000000000000000107070000000000000000")
                if request == 128:
                    assert value == 2
                    native("poll")
                    state["poll"] = 0 if scenario == "zero_poll" else 4
                    if scenario == "bad_control":
                        return b"\x01\x03\x04"
                    # Cached/hidden-error world returns identical bit 4 but does not
                    # establish a fresh GPIB poll. Host interpretation must stay bounded.
                    state["polled"] = True
                    state["stb"] = 4 if scenario in ("remains", "cached", "buffered") else 0
                    if scenario == "poll_clears_SM":
                        state["entry"] = 0
                    return bytes([1, 2, state["poll"]])
                assert request == 0xA1
                return b"\x80" if scenario == "local_rejected" else b"\x01"

        class Interrupt:
            bEndpointAddress, bmAttributes, wMaxPacketSize = 0x81, 3, 8

            def read(self, size, *, timeout):
                event("interrupt")
                native("interrupt")
                if scenario == "unsolicited":
                    return b"\x81\x40"
                return bytes([0x82, state["poll"]])

        device = Device()
        interface = SimpleNamespace(usb_dev=device, usb_intf=descriptor, usb_intr_in=Interrupt())

        class Handle:
            session = 42

            def __init__(self):
                self.visalib = self

            def write_raw(self, raw):
                code = raw.decode()
                self.pending = code
                counts[code] = counts.get(code, 0) + 1
                event("write", command=code)
                assert code in (
                    "*IDN?",
                    "SM",
                    "*ESE?",
                    "*SRE?",
                    "*ESR?",
                    "*STB?",
                    "FR-3GZ",
                    "TR1",
                    "TR3",
                )
                if code == "FR-3GZ":
                    state["injected"] = True
                    if scenario != "ignored_fixture":
                        state.update(entry=82, esr=16, stb=4)
                    if scenario == "partial_fixture":
                        return len(raw) - 1
                return len(raw)

            def read(self, session, size):
                code = self.pending
                event("read", command=code)
                if code == "*IDN?":
                    raw = TARGET.expected_idn
                elif code in ("*ESE?", "*SRE?"):
                    raw = b"004\r\n" if scenario == "nonzero_" + code[1:4] else b"000\r\n"
                elif code == "*ESR?":
                    v = state["esr"]
                    state["esr"] = 0
                    if scenario == "preexisting_event" and not state["injected"]:
                        v = 32
                    if scenario == "missing_execution" and state["injected"]:
                        v = 0
                    raw = f"{v:03d}\r\n".encode()
                elif code == "*STB?":
                    v = state["stb"]
                    if scenario == "transient_before" and counts[code] == 3:
                        v = 0
                    if scenario == "unexpected_after" and state["polled"] and counts.get("SM") == 1:
                        v = 8
                    if scenario == "buffered" and state["polled"]:
                        state["stb"] = 0
                    raw = f"{v:03d}\r\n".encode()
                    if scenario == "malformed_before" and counts[code] == 2:
                        raw = b"BAD\r\n"
                elif code == "TR1":
                    raw = (
                        b"9.0001E+40\r\n" if scenario == "measurement_error" else b"-5.0000E-08\r\n"
                    )
                else:
                    assert code == "SM"
                    raw = bytearray(status_fixture(logarithmic=False))
                    error = state["entry"]
                    state["entry"] = state["stb"] = 0
                    if scenario == "persistent_entry" and state["injected"]:
                        error = 82
                    if scenario == "source_on" and counts[code] == 1:
                        raw[16] = ord("1")
                    if scenario == "flags_changed" and state["injected"]:
                        raw[24] = ord("1")
                    if counts.get("TR1"):
                        raw[18] = ord("1")
                    raw[2:4] = f"{error:02d}".encode()
                    raw = bytes(raw)
                return raw, StatusCode.success

            def close(self):
                event("close")

        class Manager:
            def __init__(self, backend):
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


def entry_run(tmp_path, scenario="clears", **overrides):
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=True,
        serial_poll_entry_error=True,
        numeric_original_settings=dict(frequency="0.0500GZ", cal_factor="100.0%"),
        _factory_override=Backend(tmp_path / "trace.jsonl", scenario),
    )
    args.update(overrides)
    return run(tmp_path, **args)


def writes(trace):
    return [e["command"] for e in trace if e["event"] == "write"]


@pytest.mark.parametrize(
    "scenario,observation",
    [
        ("clears", "entry_bit_absent_on_both_post_poll_ASCII_reads"),
        ("poll_clears_SM", "entry_bit_absent_on_both_post_poll_ASCII_reads"),
        ("remains", "entry_bit_present_on_both_post_poll_ASCII_reads"),
        ("buffered", "entry_bit_present_then_absent_after_poll"),
        ("cached", "entry_bit_present_on_both_post_poll_ASCII_reads"),
    ],
)
def test_competing_latch_and_cache_worlds_record_observation_without_freshness_claim(
    tmp_path, scenario, observation
):
    r, t = entry_run(tmp_path, scenario)
    a = r["serial_poll_assessment"]
    assert r["status"] == "completed" and a["accepted_full_case"]
    assert a["entry_bit_observation"] == observation and a["nonzero_entry_poll_observed"]
    assert a["quiet_cleanup_verified"] and not a["numeric_settings_verified"]
    assert not a["instrument_poll_success_verified"] and not a["freshness_verified"]
    assert not a["procedure_completion_verified"]
    assert len(r["queries"]) == 21 and all(q["accepted_before_deadline"] for q in r["queries"])
    assert writes(t).count("FR-3GZ") == 1
    assert sum(e["event"] == "control" and e["request"] == 128 for e in t) == 1
    assert r["transport_closed"] and r["local_return"]["status"] == "accepted"
    assert r["front_panel_confirmation"] == "not_provided"


@pytest.mark.parametrize(
    "scenario", ["source_on", "nonzero_ESE", "nonzero_SRE", "preexisting_event"]
)
def test_nonquiet_baseline_has_no_fixture_or_poll(tmp_path, scenario):
    r, t = entry_run(tmp_path, scenario)
    assert r["status"] == "observation_stop"
    assert "FR-3GZ" not in writes(t)
    assert not any(e["event"] == "control" and e["request"] == 128 for e in t)


@pytest.mark.parametrize("scenario", ["ignored_fixture", "transient_before"])
def test_entry_bit_must_survive_two_ASCII_reads_before_poll(tmp_path, scenario):
    r, t = entry_run(tmp_path, scenario)
    assert r["status"] == "observation_stop"
    assert not any(e["event"] == "control" and e["request"] == 128 for e in t)
    assert writes(t).count("FR-3GZ") == 1 and "TR3" in writes(t)
    assert r["serial_poll_assessment"]["quiet_cleanup_verified"]


@pytest.mark.parametrize("scenario", ["zero_poll", "unexpected_after", "missing_execution"])
def test_inconclusive_or_unexpected_observations_still_verify_known_read_cleanup(
    tmp_path, scenario
):
    r, t = entry_run(tmp_path, scenario)
    assert (
        r["status"] == "observation_stop" and not r["serial_poll_assessment"]["accepted_full_case"]
    )
    assert r["serial_poll_assessment"]["quiet_cleanup_verified"]
    assert writes(t).count("FR-3GZ") == 1 and "TR3" in writes(t)


@pytest.mark.parametrize("scenario", ["persistent_entry", "flags_changed", "measurement_error"])
def test_unquiet_cleanup_stops_remaining_capture(tmp_path, scenario):
    r, t = entry_run(tmp_path, scenario)
    assert r["status"] == "observation_stop"
    assert not r["serial_poll_assessment"]["quiet_cleanup_verified"]
    assert not r["serial_poll_assessment"]["accepted_full_case"]
    if scenario != "measurement_error":
        assert "TR1" not in writes(t)


@pytest.mark.parametrize(
    "scenario",
    [
        "partial_fixture",
        "malformed_before",
        "bad_control",
        "unsolicited",
        "poll_timeout",
        "interrupt_timeout",
        "caps_timeout",
    ],
)
def test_uncertain_transfer_never_runs_latch_cleanup_or_retry(tmp_path, scenario):
    r, t = entry_run(tmp_path, scenario)
    assert r["status"] == "query_failed" and r["transport_closed"]
    assert not r["serial_poll_assessment"]["quiet_cleanup_verified"]
    assert writes(t).count("FR-3GZ") == 1 and "TR3" not in writes(t)
    assert writes(t).count("SM") == 1 and "TR1" not in writes(t)
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in t)


@pytest.mark.parametrize("stage", ["caps", "poll", "interrupt"])
@pytest.mark.parametrize("fault", ["late", "hung", "crash"])
def test_cancel_deadline_and_crash_never_accept_nonzero_or_start_cleanup(tmp_path, stage, fault):
    path = tmp_path / "trace.jsonl"
    args = (
        dict(cancelled=lambda: any(e["event"] == "pending" for e in events(path)))
        if fault == "late"
        else dict(work_s=1, total_s=5)
    )
    start = time.monotonic()
    r, t = entry_run(tmp_path, stage + "_" + fault, **args)
    assert time.monotonic() - start < 6
    assert r["status"] in ("cancelled", "deadline", "worker_failed")
    assert r["worker"]["stopped"]
    assert not r["serial_poll_assessment"]["nonzero_entry_poll_observed"]
    assert not r["serial_poll_assessment"]["quiet_cleanup_verified"]
    assert "TR3" not in writes(t) and writes(t).count("SM") == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"serial_poll_probe": True},
        {"numeric_entry": True},
        {"confirmed_error_fixtures": False},
        {"numeric_original_settings": None},
        {"numeric_original_settings": dict(frequency="", cal_factor="100%")},
        {"include_latched_reads": True},
        {"serial_poll_entry_error": 1},
        {"confirmed_reference_control": True},
    ],
)
def test_context_and_selection_guards_precede_open(tmp_path, overrides):
    with pytest.raises(ValueError):
        entry_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


@pytest.mark.parametrize(
    "flags",
    [
        ["--serial-poll-entry-error"],
        ["--serial-poll-entry-error", "--serial-poll-probe"],
        ["--serial-poll-entry-error", "--include-latched-reads"],
    ],
)
def test_cli_guards_precede_setup(flags):
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


def test_fixed_plan_contains_only_one_invalid_fixture_and_one_poll():
    rows = entry.plan()
    assert len(rows) == len({r["step_id"] for r in rows}) == 21
    assert [r["fixture_hex"] for r in rows if r["kind"] == "stimulus"] == [b"FR-3GZ".hex()]
    assert sum(r["kind"] == "poll" for r in rows) == 1
    assert not {"CS", "*CLS", "QX", "OC1", "OC0", "FR", "CF", "*ESE", "*SRE"} & {
        r["command"] for r in rows
    }
