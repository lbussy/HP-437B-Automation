"""One ZERO decision: freshness, pending-operation discipline, and failure bounds."""

import json
import time
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from test_diagnostics_lifecycle import SERIAL, TARGET, events, run
from test_serial_poll_probe import Adapter

from hp437b import diagnostics_physical as dp
from hp437b import diagnostics_zero as zero
from hp437b import reconciliation_physical as phy
from hp437b.errors import ProtocolError, StateUncertain
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

        scenario, trace = self.scenario, self.trace
        state = dict(polls=0, tag=0, zero=False, done=False, byte=0)

        def event(kind, **values):
            with trace.open("a") as f:
                f.write(json.dumps(dict(event=kind, **values)) + "\n")

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
                if request == 7:
                    return bytes.fromhex("010000010401000000000000000107070000000000000000")
                if request == 128:
                    state["polls"] += 1
                    state["tag"] = value
                    assert value == state["polls"] + 1
                    n = state["polls"]
                    byte = 2 if n == 1 else 0  # Deliberately stale prior completion consumed first.
                    if n == 2 and scenario == "unclear_baseline":
                        byte = 2
                    if state["zero"] and not state["done"]:
                        if scenario in ("hung", "cancel"):
                            event("pending")
                            time.sleep(30 if scenario == "hung" else 0.3)
                        if scenario == "native_error":
                            raise TimeoutError("synthetic native failure")
                        if n >= 4 or scenario == "immediate":
                            byte = 2
                            state["done"] = True
                        if scenario == "error_and_done":
                            byte = 10
                    if scenario == "stale_tag" and state["zero"]:
                        return bytes([1, value - 1, 2])
                    state["byte"] = byte
                    return bytes([1, value, byte])
                assert request == 0xA1
                return b"\x01"

        class Interrupt:
            bEndpointAddress, bmAttributes, wMaxPacketSize = 0x81, 3, 8

            def read(self, size, *, timeout):
                return bytes([0x80 | state["tag"], state["byte"]])

        device = Device()
        interface = SimpleNamespace(usb_dev=device, usb_intf=descriptor, usb_intr_in=Interrupt())

        class Handle:
            session = 42

            def __init__(self):
                self.visalib = self

            def write_raw(self, raw):
                code = raw.decode()
                event("write", command=code)
                self.pending = code
                assert code in ("*IDN?", "SM", "*ESE?", "*SRE?", "CS", "ZE", "TR1", "TR3")
                assert not state["zero"] or state["done"] or code == "ZE", (
                    "ASCII while ZERO pending"
                )
                if code == "ZE":
                    assert not state["zero"]
                    state["zero"] = True
                    if scenario == "partial_zero":
                        return 1
                return len(raw)

            def read(self, session, size):
                code = self.pending
                if code == "*IDN?":
                    raw = TARGET.expected_idn
                elif code in ("*ESE?", "*SRE?"):
                    raw = b"004\r\n" if scenario == "mask" else b"000\r\n"
                elif code == "TR1":
                    raw = b"-2.0000E-08\r\n"
                else:
                    assert code == "SM"
                    raw = bytearray(status_fixture(logarithmic=False))
                    if scenario == "source_on":
                        raw[16] = ord("1")
                    if state["done"]:
                        raw[18] = (
                            ord("1")
                            if getattr(self, "triggered", False) or scenario == "standby"
                            else ord("0")
                        )
                    raw = bytes(raw)
                if code == "TR1":
                    self.triggered = True
                return raw, StatusCode.success

            def close(self):
                event("close")

        class Manager:
            def __init__(self, backend):
                self.visalib = SimpleNamespace(sessions={42: SimpleNamespace(interface=interface)})

            def open_resource(self, selected, *, open_timeout):
                return Handle()

            def close(self):
                event("manager_close")

        usb.core.find = lambda **kwargs: [device]
        usb.util.dispose_resources = lambda dev: None
        pyvisa.ResourceManager = Manager
        phy.importlib.metadata.version = lambda name: phy.PINS[name]
        return dp._DiagnosticBridge(resource)


def zero_run(tmp_path, scenario="healthy", **overrides):
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=False,
        supervised_zero=True,
        confirmed_zero=True,
        prepared=dict.fromkeys((*dp.PREPARED, "no_rf_input"), True),
        work_s=45,
        total_s=50,
        _factory_override=Backend(tmp_path / "trace.jsonl", scenario),
    )
    args.update(overrides)
    return run(tmp_path, **args)


@pytest.mark.parametrize("scenario", ["healthy", "immediate", "standby"])
def test_one_new_ZERO_after_stale_cache_and_clear_baseline(tmp_path, scenario):
    r, t = zero_run(tmp_path, scenario)
    assert r["status"] == "completed" and r["zero_assessment"]["accepted_full_case"]
    assert r["zero_assessment"]["completion_indication_observed"]
    assert (
        r["zero_assessment"]["clear_baseline_observed"]
        and r["zero_assessment"]["post_clear_observed"]
    )
    assert not r["zero_assessment"]["zero_automation_qualified"]
    assert r["transport_closed"] and r["local_return"]["status"] == "accepted"
    writes = [e["command"] for e in t if e["event"] == "write"]
    assert writes == ["*IDN?", "SM", "*ESE?", "*SRE?", "CS", "ZE", "CS", "SM", "TR1", "SM", "TR3"]
    tags = [e["tag"] for e in t if e["event"] == "control" and e["request"] == 128]
    assert tags == list(range(2, 2 + len(tags)))
    assert r["queries"][3]["value"]["adapter_status_byte"] == 2  # Not attributed to this ZERO.
    assert all(q["accepted_before_deadline"] for q in r["queries"])


@pytest.mark.parametrize("scenario", ["mask", "source_on", "unclear_baseline"])
def test_preconditions_or_unclear_baseline_never_start_ZERO(tmp_path, scenario):
    r, t = zero_run(tmp_path, scenario)
    assert r["status"] in ("observation_stop", "query_failed")
    assert not any(e.get("command") == "ZE" for e in t)
    assert not r["zero_assessment"]["completion_indication_observed"]


@pytest.mark.parametrize(
    "scenario", ["partial_zero", "native_error", "stale_tag", "error_and_done"]
)
def test_failure_after_ZERO_sends_no_ascii_cleanup_or_second_ZERO(tmp_path, scenario):
    r, t = zero_run(tmp_path, scenario)
    assert r["status"] == "query_failed" and not r["zero_assessment"]["accepted_full_case"]
    writes = [e["command"] for e in t if e["event"] == "write"]
    assert writes.count("ZE") == 1 and writes[-1] == "ZE"
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in t)
    assert r["zero_assessment"]["zero_may_have_started"]


@pytest.mark.parametrize("scenario", ["hung", "cancel"])
def test_cancel_or_hung_native_call_is_disposed_without_aborting_ZERO_with_ascii(
    tmp_path, scenario
):
    trace = tmp_path / "trace.jsonl"
    r, t = zero_run(
        tmp_path, scenario, cancelled=lambda: any(e["event"] == "pending" for e in events(trace))
    )
    assert r["status"] == "cancelled" and r["worker"]["stopped"]
    assert not r["zero_assessment"]["accepted_full_case"]
    assert not r["zero_assessment"]["completion_indication_observed"]
    assert [e["command"] for e in t if e["event"] == "write"][-1] == "ZE"


@pytest.mark.parametrize(
    "args",
    [
        {"confirmed_zero": False},
        {"include_latched_reads": True},
        {"serial_poll_probe": True},
        {"work_s": 20, "total_s": 25},
        {"prepared": dict.fromkeys(dp.PREPARED, True)},
    ],
)
def test_explicit_ZERO_preparation_and_budget_guards(tmp_path, args):
    with pytest.raises(ValueError):
        zero_run(tmp_path, **args)
    assert not (tmp_path / "trace.jsonl").exists()


def test_poll_session_has_distinct_tags_sticky_failure_and_no_wrap(monkeypatch):
    a = Adapter()
    a.probe(monkeypatch)
    p = zero.PollSession(a.interface, lambda: False)
    assert p.poll(110)["tag"] == 2
    # Fixed fake reply with old tag must be rejected by the next transaction.
    with pytest.raises(ProtocolError):
        p.poll(110)
    n = len(a.calls)
    with pytest.raises(StateUncertain):
        p.poll(110)
    assert len(a.calls) == n
    p = zero.PollSession(a.interface, lambda: False)
    p.tag = 128
    with pytest.raises(StateUncertain):
        p.poll(110)
    assert len(a.calls) == n


def test_zero_deadline_and_never_complete_do_not_issue_followup(monkeypatch, scripted):
    from hp437b.instrument import Instrument

    clock = [100.0]
    monkeypatch.setattr(zero.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        zero.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    wire = scripted(
        [
            ("write", b"SM"),
            ("read", status_fixture(logarithmic=False)),
            ("write", b"*ESE?"),
            ("read", b"000\r\n"),
            ("write", b"*SRE?"),
            ("read", b"000\r\n"),
            ("write", b"CS"),
            ("write", b"ZE"),
        ]
    )
    samples = []

    def poll(deadline, *, cancelled):
        v = dict(
            tag=2 + len(samples),
            adapter_status_byte=0,
            capabilities_hex="",
            control_hex="010200",
            interrupt_hex="8200",
        )
        samples.append(v)
        wire.zero_poll_receipt = v
        return v

    wire.zero_poll = poll
    wire.zero_poll_receipt = None
    wire.captured_raw = b""
    rows = zero.plan()
    status, a = zero.collect(
        Instrument(wire),
        wire,
        rows,
        100,
        deadline=145,
        before_step=lambda _: None,
        after_step=lambda: None,
        on_row=lambda _: None,
        stop=SimpleNamespace(is_set=lambda: False),
    )
    assert status == "query_failed" and not a["completion_indication_observed"]
    assert len(samples) <= 62 and wire.calls[-1] == ("write", b"ZE")
    assert clock[0] <= 130.01
