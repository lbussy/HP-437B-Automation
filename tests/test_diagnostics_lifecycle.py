"""Independent stateful hypotheses, never claims about actual meter semantics."""

import json
import os
import subprocess
import sys
import time
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from hp437b import diagnostics_lifecycle as life
from hp437b import diagnostics_physical as dp
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture

SERIAL = "HEWLETT-PACKARD_437B_1.9"
RESOURCE = f"USB0::1003::8293::{SERIAL}::0::INSTR"
TARGET = phy.PhysicalTarget(RESOURCE, SERIAL, b"HEWLETT-PACKARD,437B,,1.9\r\n")


class Model:
    def __init__(self, mode, sticky, scenario):
        self.mode, self.sticky, self.scenario = mode, sticky, scenario
        self.events = 32 if scenario == "preexisting_event" else 128
        self.errors = deque([55] if scenario == "preexisting_error" else [])
        self.last = self.active = 0
        self.reference = False
        self.logarithmic = False
        self.pending = None
        self.counts = Counter()

    def write(self, command):
        self.counts[command] += 1
        if command in ("QX", "FR-3GZ"):
            if self.scenario == "fixture_ignored":
                return
            code, event = (91, 32) if command == "QX" else (82, 16)
            self.events |= event
            self.errors.append(code)
            self.last, self.active = code, code
            if self.scenario == "changed_units" and command == "FR-3GZ":
                self.logarithmic = True
            if self.scenario == "unexpected_source_on" and command == "FR-3GZ":
                self.reference = True
        else:
            assert command in ("*IDN?", "*ESE?", "*SRE?", "*STB?", "*ESR?", "ERR?", "SM", "TR3")
            self.pending = command

    def read(self):
        code, self.pending = self.pending, None
        if code == "*IDN?":
            return TARGET.expected_idn
        if code == "*ESR?":
            value = self.events
            if not self.sticky:
                self.events = 0
        elif code == "ERR?":
            if self.scenario == "entry_errors_invisible":
                value = 0
            elif self.mode == "latest_sticky":
                value = self.last
            elif self.mode == "latest_consuming":
                value = self.errors.pop() if self.errors else 0
                self.errors.clear()
            elif self.mode == "lifo":
                value = self.errors.pop() if self.errors else 0
            else:
                value = self.errors.popleft() if self.errors else 0
        elif code == "SM":
            raw = bytearray(status_fixture(logarithmic=self.logarithmic))
            raw[2:4] = f"{self.active:02d}".encode()
            raw[16] = ord("1") if self.reference else ord("0")
            if self.scenario != "status_does_not_clear":
                self.active = 0
            return bytes(raw)
        else:
            value = 32 if code == "*ESE?" and self.scenario == "nonzero_mask" else 0
        return f"{value:03d}\r\n".encode()


@dataclass
class Backend:
    trace: Path
    mode: str = "fifo"
    sticky: bool = False
    scenario: str = "healthy"
    simulation = True

    def __call__(self, resource):
        import pyvisa
        import usb.core
        import usb.util
        from pyvisa.constants import StatusCode

        model = Model(self.mode, self.sticky, self.scenario)
        trace, scenario = self.trace, self.scenario

        def event(kind, **fields):
            with trace.open("a") as handle:
                handle.write(json.dumps(dict(event=kind, **fields)) + "\n")

        descriptor = SimpleNamespace(
            bInterfaceNumber=0, bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1
        )

        class Device:
            idVendor, idProduct = 0x03EB, 0x2065
            serial_number, manufacturer, product = SERIAL, "XyphroLabs", "GpibUsb"

            def get_active_configuration(self):
                return [descriptor]

            def ctrl_transfer(self, kind, request, value, index, size, *, timeout):
                event("control", request=request, timeout=timeout)
                if request == 7:
                    caps = bytearray(24)
                    caps[0], caps[14] = 1, 2
                    return caps
                assert request == 0xA1
                return b"\x01"

        device = Device()

        class Handle:
            session = 42

            def __init__(self):
                self.visalib = self

            def write_raw(self, raw):
                code = raw.decode()
                event("write", command=code, timeout=self.timeout)
                model.write(code)
                if scenario == "partial_fixture" and code == "QX":
                    return 1
                return len(raw)

            def read(self, session, size):
                code = model.pending
                event("read", command=code)
                raw = model.read()
                status = StatusCode.success
                if code == "*ESR?" and model.counts[code] == 5:
                    if scenario == "malformed":
                        raw = b"BROKEN\r\n"
                    elif scenario == "partial_reply":
                        raw, status = b"000", StatusCode.success_max_count_read
                    elif scenario in ("late", "hung"):
                        event("pending")
                        time.sleep(0.3 if scenario == "late" else 30)
                    elif scenario == "crash":
                        os._exit(19)
                return raw, status

            def close(self):
                event("close")

        class Manager:
            def __init__(self, backend):
                assert backend == "@py"
                event("open")
                self.visalib = SimpleNamespace(
                    sessions={
                        42: SimpleNamespace(
                            interface=SimpleNamespace(usb_dev=device, usb_intf=descriptor)
                        )
                    }
                )

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


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def run(tmp_path, *, mode="fifo", sticky=False, scenario="healthy", **overrides):
    trace = tmp_path / "trace.jsonl"
    args = dict(
        target=TARGET,
        prepared=dict.fromkeys(dp.PREPARED, True),
        equipment=dict(meter_serial="SYNTHETIC", sensor_serial="SYNTHETIC"),
        confirmed=True,
        prior_worker_stopped=True,
        workflow_lock_root=tmp_path / "locks",
        lifecycle=True,
        confirmed_error_fixtures=True,
        _factory_override=Backend(trace, mode, sticky, scenario),
    )
    args.update(overrides)
    result = dp.run_physical(tmp_path / "result", **args)
    assert result == json.loads((tmp_path / "result/diagnostics.json").read_text())
    assert result["evidence_origin"] == "injected_fake"
    assert result["worker"]["stopped"]
    return result, events(trace)


def test_plan_has_unique_steps_and_only_two_fixed_invalid_writes():
    rows = life.plan()
    assert len(rows) == 69 and len({r["step_id"] for r in rows}) == 69
    assert {r["fixture_hex"] for r in rows if r["kind"] == "stimulus"} == {
        b"QX".hex(),
        b"FR-3GZ".hex(),
    }
    assert {r["command"] for r in rows if r["kind"] == "query"} == {
        "*ESE?",
        "*SRE?",
        "*STB?",
        "*ESR?",
        "ERR?",
        "SM",
    }


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("fifo", "fifo_like_two_error_signature"),
        ("lifo", "lifo_like_two_error_signature"),
        ("latest_sticky", "latest_error_sticky_signature"),
        ("latest_consuming", "latest_only_consuming_or_single_slot_signature"),
    ],
)
@pytest.mark.parametrize("sticky", [False, True])
def test_stateful_hypotheses_are_recorded_without_hardcoded_fifo_or_clear(
    mode, expected, sticky, tmp_path
):
    result, trace = run(tmp_path, mode=mode, sticky=sticky)
    assert result["status"] == "completed" and result["transport_closed"]
    assert result["lifecycle_assessment"]["accepted_full_case"] is True
    assert len(result["queries"]) == 69
    assert all(
        r["status"] == "completed" and r["accepted_before_deadline"] for r in result["queries"]
    )
    assert result["lifecycle_assessment"]["error_selection_observation"] == expected
    expected_event = (
        "command_bit_persists_across_three_reads"
        if sticky
        else "command_bit_cleared_on_subsequent_reads"
    )
    assert result["lifecycle_assessment"]["event_read_observation"] == expected_event
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes.count("QX") == 4 and writes.count("FR-3GZ") == 3
    assert writes[-1] == "TR3"
    assert not set(writes) & {"OC0", "OC1", "PR", "*CLS", "CS", "ZE", "CL", "*ESE", "*SRE"}
    ids = {r["step_id"]: r for r in result["queries"]}
    assert ids["event.*ESR?.1"]["value"] & 32
    assert ids["event.*ESR?.2"]["value"] != ids["event.*ESR?.1"]["value"] or sticky


@pytest.mark.parametrize(
    "scenario,phase",
    [
        ("nonzero_mask", "baseline"),
        ("preexisting_error", "baseline"),
        ("preexisting_event", "baseline"),
        ("fixture_ignored", "event"),
        ("entry_errors_invisible", "single_a"),
        ("unexpected_source_on", "single_b"),
        ("changed_units", "single_b"),
        ("status_does_not_clear", "event"),
    ],
)
def test_observation_gate_stops_new_stimuli_without_claiming_pass_or_restoring_by_preset(
    tmp_path, scenario, phase
):
    result, trace = run(tmp_path, scenario=scenario)
    assert result["status"] == "observation_stop"
    assert result["lifecycle_assessment"]["accepted_full_case"] is False
    assert result["lifecycle_assessment"]["stopped_after_phase"] == phase
    assert result["transport_closed"] and result["local_return"]["status"] == "accepted"
    writes = [e["command"] for e in trace if e["event"] == "write"]
    if phase == "baseline":
        assert "QX" not in writes and "FR-3GZ" not in writes
    if phase in ("event", "single_a"):
        assert "FR-3GZ" not in writes
    assert any(r["status"] == "not_attempted" for r in result["queries"])
    assert not set(writes) & {"OC0", "OC1", "PR", "*CLS", "CS"}


@pytest.mark.parametrize(
    "scenario,raw",
    [("malformed", b"BROKEN\r\n"), ("partial_reply", b"000"), ("partial_fixture", b"")],
)
def test_failed_transfer_stops_without_later_reads_cleanup_or_raw_reply_loss(
    tmp_path, scenario, raw
):
    result, trace = run(tmp_path, scenario=scenario)
    assert result["status"] == "query_failed" and result["transport_closed"]
    failed = [r for r in result["queries"] if r["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["raw_hex"] == raw.hex()
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert "TR3" not in writes and "FR-3GZ" not in writes
    assert trace[-1]["event"] == "manager_close"


def test_cancel_during_repeated_read_preserves_unique_rows_and_discards_late_result(tmp_path):
    trace = tmp_path / "trace.jsonl"
    result, trace_events = run(
        tmp_path,
        scenario="late",
        cancelled=lambda: any(e["event"] == "pending" for e in events(trace)),
    )
    assert result["status"] == "cancelled" and not result["worker"]["forced"]
    assert result["lifecycle_assessment"]["accepted_full_case"] is False
    rows = {r["step_id"]: r for r in result["queries"]}
    assert rows["event.*ESR?.1"]["status"] == "completed"
    assert rows["event.*ESR?.2"]["status"] == "failed"
    assert not rows["event.*ESR?.2"]["accepted_before_deadline"]
    assert rows["event.*ESR?.3"]["status"] == "not_attempted"
    assert not any(e.get("command") in ("TR3", "FR-3GZ") for e in trace_events)


@pytest.mark.parametrize("scenario", ["hung", "crash"])
def test_nonreturning_or_crashed_worker_cannot_manufacture_success(tmp_path, scenario):
    result, trace = run(tmp_path, scenario=scenario, work_s=1, total_s=5)
    assert result["status"] in ("deadline", "worker_failed")
    assert result["transport_closed"] is None
    assert result["elapsed_s"] < 5.5
    assert not any(e.get("command") == "TR3" for e in trace)


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_error_fixtures": False},
        {"confirmed_error_fixtures": 1},
        {"lifecycle": False},
        {"lifecycle": 1},
        {"include_latched_reads": True},
    ],
)
def test_separate_error_fixture_confirmation_required_before_output_or_usb(tmp_path, overrides):
    with pytest.raises(ValueError):
        run(tmp_path, **overrides)
    assert not (tmp_path / "result").exists() and not (tmp_path / "trace.jsonl").exists()


def test_normal_command_codec_remains_unable_to_send_the_error_fixtures():
    from hp437b.commands import encode

    with pytest.raises(ValueError):
        encode("QX")
    with pytest.raises(ValueError):
        encode("FR", -3, unit="GZ")


@pytest.mark.parametrize(
    "args",
    [
        ["--lifecycle"],
        ["--confirm-fixed-error-fixtures"],
        ["--lifecycle", "--include-latched-reads", "--confirm-fixed-error-fixtures"],
    ],
)
def test_cli_misconfiguration_is_rejected_before_reading_setup(args):
    result = subprocess.run(
        [
            sys.executable,
            "tools/diagnose_meter.py",
            "--resource",
            RESOURCE,
            "--setup",
            "missing",
            "--output",
            "unused",
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2 and "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "code,phase,values,field",
    [
        ("*ESR?", "event", [32, 0, 32], "event_read_observation"),
        ("ERR?", "a_then_b", [91, 82, 82], "error_selection_observation"),
    ],
)
def test_unclassified_or_nonmonotonic_observations_stay_inconclusive(code, phase, values, field):
    rows = life.plan()
    selected = [r for r in rows if r["phase"] == phase and r["command"] == code]
    for row, value in zip(selected, values, strict=True):
        row.update(status="completed", value=value)
    assert life.assessment(rows)[field] == "inconclusive"
