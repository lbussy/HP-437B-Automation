"""LP2 binary preservation through the actual bridge, with injected USB/VISA only."""

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_diagnostics_lifecycle import RESOURCE, SERIAL, TARGET, events, run

from hp437b import diagnostics_physical as dp
from hp437b import diagnostics_snapshot as snapshot
from hp437b import reconciliation_physical as phy
from hp437b.simulation import status_fixture

# Embedded NUL, CR/LF, high-bit bytes, and terminal CR/LF are payload, not delimiters.
FRAME = b"@2" + bytes(range(50)) + b"\x00\xff\x80\r\nZ\r\n"


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
            with trace.open("a") as handle:
                handle.write(json.dumps(dict(event=kind, **values)) + "\n")

        interface = SimpleNamespace(
            bInterfaceNumber=0, bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1
        )

        class Device:
            idVendor, idProduct = 0x03EB, 0x2065
            serial_number, manufacturer, product = SERIAL, "XyphroLabs", "GpibUsb"

            def get_active_configuration(self):
                return [interface]

            def ctrl_transfer(self, kind, request, value, index, size, *, timeout):
                event("control", request=request)
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
                self.pending = raw.decode()
                assert self.pending in ("*IDN?", "SM", "LP2", "TR1", "TR3")
                counts[self.pending] = counts.get(self.pending, 0) + 1
                event("write", command=self.pending, timeout=self.timeout)
                if scenario == "partial_write" and self.pending == "LP2":
                    return 2
                return len(raw)

            def read(self, session, size):
                assert (
                    self.read_termination is None
                    and self.write_termination is None
                    and self.send_end
                )
                code = self.pending
                event("read", command=code, size=size)
                if code == "*IDN?":
                    return TARGET.expected_idn, StatusCode.success
                if code == "SM":
                    raw = bytearray(status_fixture(logarithmic=False))
                    if "TR1" in counts or scenario == "standby_before":
                        raw[18] = ord("1")
                    if scenario == "source_on" or (
                        scenario == "source_after" and counts[code] == 2
                    ):
                        raw[16] = ord("1")
                    if scenario == "entry_error":
                        raw[2:4] = b"82"
                    if scenario == "changed_flags" and counts[code] == 2:
                        raw[24] = ord("1")
                    return bytes(raw), StatusCode.success
                if code == "TR1":
                    if scenario == "acquisition_malformed":
                        return b"BAD\r\n", StatusCode.success
                    if scenario == "acquisition_error":
                        return b"9.0001E+40\r\n", StatusCode.success
                    return b"-5.0000E-08\r\n", StatusCode.success
                assert code == "LP2"
                if scenario in ("late", "hung", "crash"):
                    event("pending")
                    if scenario == "crash":
                        os._exit(19)
                    time.sleep(0.3 if scenario == "late" else 30)
                raw = {
                    "short": FRAME[:-1],
                    "long": FRAME + b"X",
                    "prefix": b"XX" + FRAME[2:],
                    "oversized": b"X" * 4097,
                }.get(scenario, FRAME)
                status = (
                    StatusCode.success_max_count_read
                    if scenario == "incomplete_eom"
                    else StatusCode.success
                )
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
                            interface=SimpleNamespace(usb_dev=device, usb_intf=interface)
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


def snapshot_run(tmp_path, scenario="healthy", **overrides):
    trace = tmp_path / "trace.jsonl"
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=False,
        lp2_snapshot=True,
        _factory_override=Backend(trace, scenario),
    )
    args.update(overrides)
    return run(tmp_path, **args)


def test_success_preserves_every_byte_and_acquires_only_after_complete_binary_read(tmp_path):
    result, trace = snapshot_run(tmp_path)
    assert result["status"] == "completed" and result["transport_closed"]
    assert result["snapshot_assessment"]["accepted_full_case"]
    path = tmp_path / "result/snapshot.bin"
    assert len(FRAME) == 60 and path.read_bytes() == FRAME
    assert result["snapshot_artifact"]["sha256"] == hashlib.sha256(FRAME).hexdigest()
    assert result["snapshot_artifact"]["length"] == 60
    rows = result["queries"]
    assert len(rows) == 4
    assert all(row["status"] == "completed" and row["accepted_before_deadline"] for row in rows)
    assert bytes.fromhex(rows[1]["raw_hex"]) == FRAME
    assert rows[3]["value"]["standby"] is True  # TR1 documented post-read state.
    assert rows[2]["value"] == dict(value="-5.0000E-8", unit="W", error_code=None)
    io = [(e["event"], e["command"]) for e in trace if e["event"] in ("write", "read")]
    assert io == [
        (kind, code) for code in ("*IDN?", "SM", "LP2", "TR1", "SM") for kind in ("write", "read")
    ] + [("write", "TR3")]
    assert result["local_return"]["status"] == "accepted"


@pytest.mark.parametrize(
    "scenario", ["short", "long", "prefix", "oversized", "incomplete_eom", "partial_write"]
)
def test_bad_snapshot_is_retained_as_raw_evidence_without_export_retry_or_followup(
    tmp_path, scenario
):
    result, trace = snapshot_run(tmp_path, scenario)
    assert result["status"] == "query_failed" and result["transport_closed"]
    assert not (tmp_path / "result/snapshot.bin").exists()
    assert result["queries"][1]["status"] == "failed"
    expected = {
        "short": FRAME[:-1],
        "long": FRAME + b"X",
        "prefix": b"XX" + FRAME[2:],
        "oversized": b"X" * 4097,
        "incomplete_eom": FRAME,
        "partial_write": b"",
    }[scenario]
    assert result["queries"][1]["raw_hex"] == expected.hex()
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes == ["*IDN?", "SM", "LP2"]
    assert sum(e["event"] == "read" and e["command"] == "LP2" for e in trace) == (
        0 if scenario == "partial_write" else 1
    )


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("acquisition_malformed", "query_failed"),
        ("acquisition_error", "observation_stop"),
        ("changed_flags", "observation_stop"),
        ("source_after", "observation_stop"),
    ],
)
def test_valid_snapshot_survives_failed_followup_without_claiming_full_case(
    tmp_path, scenario, status
):
    result, trace = snapshot_run(tmp_path, scenario)
    assert result["status"] == status and not result["snapshot_assessment"]["accepted_full_case"]
    assert (tmp_path / "result/snapshot.bin").read_bytes() == FRAME
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert ("TR3" in writes) == (status == "observation_stop")
    if scenario in ("acquisition_error", "acquisition_malformed"):
        assert writes.count("SM") == 1


@pytest.mark.parametrize("scenario", ["source_on", "entry_error", "standby_before"])
def test_nonquiet_baseline_prevents_snapshot_or_trigger(tmp_path, scenario):
    result, trace = snapshot_run(tmp_path, scenario)
    assert result["status"] == "observation_stop"
    assert not (tmp_path / "result/snapshot.bin").exists()
    assert [e["command"] for e in trace if e["event"] == "write"] == ["*IDN?", "SM", "TR3"]


@pytest.mark.parametrize("scenario", ["late", "hung", "crash"])
def test_cancel_late_hung_or_crashed_snapshot_is_never_published(tmp_path, scenario):
    path = tmp_path / "trace.jsonl"
    args = (
        dict(cancelled=lambda: any(e["event"] == "pending" for e in events(path)))
        if scenario == "late"
        else dict(work_s=1, total_s=5)
    )
    result, trace = snapshot_run(tmp_path, scenario, **args)
    assert result["status"] in ("cancelled", "deadline", "worker_failed")
    assert not (tmp_path / "result/snapshot.bin").exists()
    assert not any(e.get("command") in ("TR1", "TR3") for e in trace)


@pytest.mark.parametrize(
    "overrides",
    [
        {"lp2_snapshot": 1},
        {"lifecycle": True},
        {"numeric_entry": True},
        {"err_selection": True},
        {"include_latched_reads": True},
        {"confirmed_error_fixtures": True},
    ],
)
def test_profile_selection_guards_precede_usb_and_output(tmp_path, overrides):
    with pytest.raises(ValueError):
        snapshot_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


@pytest.mark.parametrize(
    "flags",
    [
        ["--lp2-snapshot", "--lifecycle"],
        ["--lp2-snapshot", "--numeric-entry"],
        ["--lp2-snapshot", "--include-latched-reads"],
        ["--lp2-snapshot", "--confirm-fixed-error-fixtures"],
        ["--lp2-snapshot"],
    ],
)
def test_cli_conflicts_or_missing_supervision_fail_before_setup(flags):
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
            *flags,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 2 and "Traceback" not in result.stderr


def test_plan_no_fixture_no_restore_and_unique_step_ids():
    rows = snapshot.plan()
    assert len(rows) == 4 == len({row["step_id"] for row in rows})
    assert [row["command"] for row in rows] == ["SM", "LP2", "TR1", "SM"]


def test_artifact_write_failure_cannot_claim_completed_case(tmp_path, monkeypatch):
    original = Path.replace

    def fail_snapshot(path, target):
        if path.name == "snapshot.bin.part":
            raise OSError("synthetic artifact failure")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", fail_snapshot)
    result, trace = snapshot_run(tmp_path)
    assert result["status"] == "artifact_failed"
    assert not result["snapshot_assessment"]["accepted_full_case"]
    assert result["transport_closed"] and result["worker"]["exitcode"] == 0
    assert "synthetic artifact failure" in result["artifact_error"]
    assert not (tmp_path / "result/snapshot.bin").exists()
    assert (tmp_path / "result/snapshot.bin.part").read_bytes() == FRAME
