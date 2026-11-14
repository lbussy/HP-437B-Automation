"""Independent stateful controls and raw bridge fakes; not a model of RF accuracy."""

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from test_diagnostics_lifecycle import RESOURCE, SERIAL, TARGET, events, run

from hp437b import diagnostics_acquisition as settings
from hp437b import diagnostics_physical as dp
from hp437b import reconciliation_physical as phy
from hp437b.instrument import Instrument
from hp437b.simulation import status_fixture


class Model:
    capabilities = frozenset({"write", "read", "eom"})

    def __init__(self, original=2, scenario="healthy", clock=time):
        self.clock = clock
        self.ready_at = 0
        self.resolution = original
        self.filter = 17
        self.range = 11
        self.reference = self.standby = False
        self.scenario = scenario
        self.writes = []
        if scenario == "manual_baseline":
            self.filter = 2
        if scenario == "source_before":
            self.reference = True
        self.cached = self.status()

    def status(self):
        raw = bytearray(status_fixture(logarithmic=False))
        raw[6:8] = f"{self.range:02d}".encode()
        raw[10:12] = f"{self.filter:02d}".encode()
        raw[16], raw[18] = (
            ord("1") if self.reference else ord("0"),
            ord("1") if self.standby else ord("0"),
        )
        return bytes(raw)

    def write(self, raw, deadline=None):
        self.pending = raw
        self.writes.append(raw)
        if raw == b"OC1":
            self.reference = True
        elif raw == b"OC0":
            if self.scenario != "off_ignored":
                self.reference = False
        elif raw == b"FA":
            if self.scenario != "fa_ignored":
                self.filter = 10 + self.resolution
        elif raw == b"FH":
            self.filter %= 10
        elif raw == b"RA":
            self.range = 14 if self.reference else 11
        elif raw == b"RH":
            self.range %= 10
        elif raw in (b"TR0", b"TR1", b"TR2"):
            self.standby = not (self.scenario == "trigger_ignored" and self.reference)
        elif raw == b"TR3":
            self.standby = False
            self.ready_at = self.clock.monotonic() + 0.005
        elif match := re.fullmatch(rb"RE([123])EN", raw):
            if self.scenario not in ("resolution_ignored", "remote_value_ignored"):
                self.resolution = int(match[1])
                if self.scenario == "remote_wrong_filter":
                    self.filter = 5
                elif self.scenario not in (
                    "remote_keeps_manual",
                    "old_timeout",
                    "remote_value_ignored",
                ):
                    self.filter = 10 + self.resolution
        elif match := re.fullmatch(rb"FM(1|4)EN", raw):
            self.filter = 0 if match[1] == b"1" else 2
            if self.scenario == "wrong_filter" and match[1] == b"4":
                self.filter = 0
        elif raw == b"RM5EN":
            self.range = 5
        else:
            assert raw in (b"*IDN?", b"SM")

    def read(self, deadline=None):
        if self.pending == b"*IDN?":
            return TARGET.expected_idn
        if self.pending == b"SM":
            if (
                not self.standby
                and self.clock.monotonic() >= self.ready_at
                and not (self.scenario == "stale_restore" and b"OC0" in self.writes)
            ):
                self.cached = self.status()
            return self.cached
        assert self.pending in (b"TR1", b"TR2", b"TR3")
        if self.scenario == "old_timeout" and self.pending == b"TR1" and b"OC0" in self.writes:
            raise TimeoutError(
                "synthetic source/range/filter transition blocks immediate trigger reply"
            )
        # Triggered measurements or continuous free-run refresh the cached status.
        self.cached = self.status()
        return b"+9.8900E-04\r\n" if self.reference else b"-5.0000E-08\r\n"


@dataclass
class Backend:
    trace: object
    original: int = 2
    scenario: str = "healthy"
    settings_settle_s = 0.01
    settings_restore_refresh_s = 0.02
    simulation = True

    def __call__(self, resource):
        import pyvisa
        import usb.core
        import usb.util
        from pyvisa.constants import StatusCode

        model = Model(self.original, self.scenario)
        trace, scenario = self.trace, self.scenario

        def event(kind, **fields):
            with trace.open("a") as handle:
                handle.write(json.dumps(dict(event=kind, **fields)) + "\n")

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
                event("write", command=raw.decode(), timeout=self.timeout)
                model.write(raw)
                if (scenario == "partial_write" and raw == b"FM4EN") or (
                    scenario == "restore_partial" and raw == b"OC0"
                ):
                    return len(raw) - 1
                return len(raw)

            def read(self, session, size):
                event("read", command=model.pending.decode())
                if scenario == "late_restore" and model.pending == b"SM" and b"OC0" in model.writes:
                    event("pending")
                    time.sleep(0.3)
                if model.reference and model.pending == b"TR2":
                    if scenario in ("late", "hung"):
                        event("pending")
                        time.sleep(30 if scenario == "hung" else 0.3)
                    if scenario == "malformed":
                        return b"BAD\r\n", StatusCode.success
                    if scenario == "incomplete":
                        return b"+9.8900", StatusCode.success_max_count_read
                    if scenario == "sentinel":
                        return b"9.0001E+40\r\n", StatusCode.success
                return model.read(), StatusCode.success

            def close(self):
                event(
                    "close",
                    reference=model.reference,
                    resolution=model.resolution,
                    filter=model.filter,
                    range=model.range,
                )

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


def setting_run(tmp_path, *, scenario="healthy", original=2, **overrides):
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=False,
        acquisition_settings=True,
        confirmed_reference_control=True,
        original_resolution=original,
        work_s=60,
        total_s=65,
        prepared=dict.fromkeys((*dp.PREPARED, "direct_reference_path", "warmed_up"), True),
        _factory_override=Backend(tmp_path / "trace.jsonl", original, scenario),
    )
    args.update(overrides)
    return run(tmp_path, **args)


@pytest.mark.parametrize("original", [1, 2, 3])
def test_real_bridge_fakes_complete_selected_cases_restore_original_and_switch_off(
    tmp_path, original
):
    result, trace = setting_run(tmp_path, original=original)
    assert result["status"] == "completed" and result["transport_closed"]
    assessment = result["acquisition_settings_assessment"]
    assert assessment["accepted_full_case"] and assessment["auto_modes_reference_off_verified"]
    assert assessment["restoration_attempted"] and not assessment["reference_may_be_on"]
    assert assessment["resolution_usb_verified"] is False
    close = next(e for e in trace if e["event"] == "close")
    assert close["reference"] is False and close["resolution"] == original
    assert close["filter"] >= 10 and close["range"] >= 11
    assert all(
        r["status"] == "completed" and r["accepted_before_deadline"] for r in result["queries"]
    )
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes.count("OC1") == writes.count("OC0") == 1
    assert writes[-6:] == [f"RE{original}EN", "RA", "FA", "TR3", "SM", "TR3"]
    assert not set(writes) & {"PR", "*CLS", "CS", "ZE", "CL", "LP2", "QX", "FR-3GZ"}
    # Every triggered reply is consumed before a later command can select ASCII output.
    io = [(e["event"], e["command"]) for e in trace if e["event"] in ("write", "read")]
    for i, (kind, code) in enumerate(io[:-1]):
        if kind == "write" and code in ("TR1", "TR2"):
            assert io[i + 1] == ("read", code)


@pytest.mark.parametrize("scenario", ["manual_baseline", "source_before"])
def test_baseline_gate_makes_no_source_or_setting_writes(tmp_path, scenario):
    result, trace = setting_run(tmp_path, scenario=scenario)
    assert result["status"] == "observation_stop"
    assert not result["acquisition_settings_assessment"]["restoration_attempted"]
    assert [e["command"] for e in trace if e["event"] == "write"] == ["*IDN?", "SM", "TR3"]
    if scenario == "source_before":
        assert result["acquisition_settings_assessment"]["reference_may_be_on"]


@pytest.mark.parametrize("scenario", ["wrong_filter", "trigger_ignored", "sentinel", "off_ignored"])
def test_healthy_observation_stop_attempts_only_bounded_known_restoration(tmp_path, scenario):
    result, trace = setting_run(tmp_path, scenario=scenario)
    assert result["status"] == "observation_stop"
    a = result["acquisition_settings_assessment"]
    assert a["restoration_attempted"] and not a["accepted_full_case"]
    assert a["auto_modes_reference_off_verified"] is (scenario != "off_ignored")
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes.count("OC1") == 1 and writes.count("OC0") == 1
    assert (
        any(r["status"] == "not_attempted" for r in result["queries"]) or scenario == "off_ignored"
    )


@pytest.mark.parametrize("scenario", ["malformed", "incomplete", "partial_write", "late"])
def test_uncertain_or_cancelled_source_on_session_sends_no_restoration_or_ascii_cleanup(
    tmp_path, scenario
):
    args = (
        dict(
            cancelled=lambda: any(e["event"] == "pending" for e in events(tmp_path / "trace.jsonl"))
        )
        if scenario == "late"
        else {}
    )
    result, trace = setting_run(tmp_path, scenario=scenario, **args)
    assert result["status"] == ("cancelled" if scenario == "late" else "query_failed")
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert "OC1" in writes and "OC0" not in writes and "TR3" not in writes
    assert result["acquisition_settings_assessment"]["reference_may_be_on"]
    assert not result["acquisition_settings_assessment"]["auto_modes_reference_off_verified"]
    assert result["transport_closed"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_reference_control": False},
        {"confirmed_reference_control": 1},
        {"original_resolution": None},
        {"original_resolution": True},
        {"original_resolution": 0},
        {"original_resolution": 4},
        {"lp2_snapshot": True},
        {"numeric_entry": True},
        {"err_selection": True},
        {"lifecycle": True},
        {"include_latched_reads": True},
        {"confirmed_error_fixtures": True},
        {"work_s": 20, "total_s": 25},
        {"prepared": dict.fromkeys(dp.PREPARED, True)},
        {"acquisition_settings": 1},
    ],
)
def test_reference_original_setup_profile_and_budget_guards_precede_output_or_usb(
    tmp_path, overrides
):
    with pytest.raises(ValueError):
        setting_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


class Clock:
    def __init__(self):
        self.now = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_soft_main_budget_preserves_known_restoration_window(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(settings, "time", clock)
    wire = Model(clock=clock)
    rows = settings.plan(2)

    def step(_):
        clock.now += 1

    status, a = settings.collect(
        Instrument(wire),
        rows,
        0,
        deadline=60,
        before_step=step,
        after_step=lambda: None,
        on_row=lambda r: None,
        raw_reply=lambda: b"",
    )
    assert (
        status == "observation_stop" and a["stop_reason"] == "main_budget_reserved_for_restoration"
    )
    assert a["restoration_attempted"] and a["auto_modes_reference_off_verified"]
    assert clock.now < 60 and wire.reference is False and wire.resolution == 2
    assert any(r["status"] == "not_attempted" for r in rows)


@pytest.mark.parametrize(
    "flags",
    [
        ["--acquisition-settings"],
        ["--confirm-reference-control"],
        ["--acquisition-settings", "--confirm-reference-control", "--lp2-snapshot"],
        ["--acquisition-settings", "--confirm-reference-control", "--include-latched-reads"],
    ],
)
def test_cli_bad_selection_is_rejected_before_setup(flags):
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


@pytest.mark.parametrize("scenario", ["late_restore", "restore_partial", "hung"])
def test_failed_late_or_missing_restoration_receipt_cannot_claim_source_off(tmp_path, scenario):
    args = (
        dict(
            cancelled=lambda: any(e["event"] == "pending" for e in events(tmp_path / "trace.jsonl"))
        )
        if scenario != "restore_partial"
        else {}
    )
    result, trace = setting_run(tmp_path, scenario=scenario, **args)
    assert result["status"] == ("query_failed" if scenario == "restore_partial" else "cancelled")
    a = result["acquisition_settings_assessment"]
    assert (
        a["reference_may_be_on"]
        and not a["auto_modes_reference_off_verified"]
        and not a["accepted_full_case"]
    )
    if scenario == "hung":
        assert result["worker"]["forced"]
    if scenario == "restore_partial":
        assert [e["command"] for e in trace if e["event"] == "write"][-1] == "OC0"


def test_cancel_during_reference_settle_sends_no_cleanup_writes(tmp_path):
    factory = Backend(tmp_path / "trace.jsonl")
    factory.settings_settle_s = 0.5
    result, trace = setting_run(
        tmp_path,
        _factory_override=factory,
        cancelled=lambda: any(e.get("command") == "OC1" for e in events(tmp_path / "trace.jsonl")),
    )
    assert result["status"] == "cancelled" and result["transport_closed"]
    assert [e["command"] for e in trace if e["event"] == "write"][-1] == "OC1"
    assert result["acquisition_settings_assessment"]["reference_may_be_on"]
