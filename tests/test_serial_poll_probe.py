"""Independent USB endpoint doubles; no USB/VISA/native library is opened."""

from types import SimpleNamespace

import pytest

from hp437b import serial_poll_probe as poll
from hp437b.errors import CapabilityUnavailable, OperationTimeout, ProtocolError, StateUncertain
from hp437b.instrument import Instrument


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class Adapter:
    def __init__(self, *, caps=None, control=b"\x01\x02\x00", interrupt=b"\x82\x00"):
        self.calls = []
        self.caps = (
            caps
            if caps is not None
            else bytes.fromhex("010000010401000000000000000107070000000000000000")
        )
        self.control, self.interrupt = control, interrupt
        self.delays = {}
        self.clock = Clock()
        self.interface = SimpleNamespace(
            usb_dev=SimpleNamespace(idVendor=0x03EB, idProduct=0x2065, ctrl_transfer=self.transfer),
            usb_intf=SimpleNamespace(
                bInterfaceClass=0xFE,
                bInterfaceSubClass=3,
                bInterfaceProtocol=1,
                bInterfaceNumber=4,
            ),
            usb_intr_in=SimpleNamespace(
                bEndpointAddress=0x83,
                bmAttributes=3,
                wMaxPacketSize=8,
                read=self.read,
            ),
        )

    def reply(self, stage, value):
        self.clock.now += self.delays.get(stage, 0)
        if isinstance(value, BaseException):
            raise value
        return value

    def transfer(self, kind, request, value, index, length, *, timeout):
        self.calls.append((kind, request, value, index, length, timeout))
        if request == 7:
            return self.reply("caps", self.caps)
        assert request == 128  # No ASCII, bulk read, clear, trigger, REN, or GTL.
        return self.reply("control", self.control)

    def read(self, length, *, timeout):
        self.calls.append(("interrupt", length, timeout))
        return self.reply("interrupt", self.interrupt)

    def probe(self, monkeypatch, deadline=110):
        monkeypatch.setattr(poll.time, "monotonic", self.clock)
        probe = poll.SerialPollProbe(self.interface)
        return probe, lambda: probe.poll_once(deadline, confirmed_source_off_idle=True)


def test_quiet_zero_is_adapter_evidence_only_and_no_io_at_construction(monkeypatch):
    a = Adapter()
    probe, run = a.probe(monkeypatch)
    assert a.calls == []
    result = run()
    assert result["adapter_status_byte"] == 0
    assert result["status"] == "adapter_reply_validated"
    assert not result["instrument_poll_success_verified"]
    assert not result["freshness_verified"] and not result["procedure_completion_verified"]
    assert a.calls == [
        (0xA1, 7, 0, 4, 24, 2000),
        (0xA1, 128, 2, 4, 3, 2000),
        ("interrupt", 2, 2000),
    ]
    assert result["control_hex"] == "010200" and result["interrupt_hex"] == "8200"
    result["status"] = "tampered"
    assert probe.receipt["status"] == "adapter_reply_validated"
    with pytest.raises(StateUncertain):
        run()
    assert len(a.calls) == 3


@pytest.mark.parametrize("value", [1, 2, 8, 64, 127])
def test_nonzero_byte_still_does_not_unlock_zero_cal_or_claim_freshness(monkeypatch, value):
    a = Adapter(control=bytes([1, 2, value]), interrupt=bytes([0x82, value]))
    _, run = a.probe(monkeypatch)
    r = run()
    assert r["adapter_status_byte"] == value and not r["procedure_completion_verified"]
    assert not hasattr(poll.SerialPollProbe, "serial_poll")


@pytest.mark.parametrize(
    "field,value",
    [
        ("idVendor", 1),
        ("idProduct", 1),
        ("bInterfaceClass", 0),
        ("bInterfaceSubClass", 1),
        ("bInterfaceProtocol", 0),
        ("bInterfaceNumber", None),
        ("bInterfaceNumber", True),
        ("bEndpointAddress", 0x03),
        ("bEndpointAddress", 0x80),
        ("bmAttributes", 2),
        ("wMaxPacketSize", 1),
    ],
)
def test_profile_rejection_has_no_native_traffic(monkeypatch, field, value):
    a = Adapter()
    target = (
        a.interface.usb_dev
        if field.startswith("id")
        else (a.interface.usb_intf if field.startswith("bInterface") else a.interface.usb_intr_in)
    )
    setattr(target, field, value)
    p, run = a.probe(monkeypatch)
    with pytest.raises(CapabilityUnavailable):
        run()
    assert a.calls == [] and p.receipt["status"] == "failed"
    with pytest.raises(StateUncertain):
        run()


def test_missing_interrupt_never_falls_back_to_control_or_bulk(monkeypatch):
    a = Adapter()
    a.interface.usb_intr_in = None
    _, run = a.probe(monkeypatch)
    with pytest.raises(CapabilityUnavailable):
        run()
    assert a.calls == []


@pytest.mark.parametrize("caps", [b"", b"\x01" * 23, b"\x01" * 25, b"\x80" + b"\x00" * 23])
def test_capability_framing_stops_before_poll(monkeypatch, caps):
    a = Adapter(caps=caps)
    p, run = a.probe(monkeypatch)
    with pytest.raises(ProtocolError):
        run()
    assert len(a.calls) == 1 and not p.receipt["poll_dispatched"]


@pytest.mark.parametrize("offset,value", [(12, 1), (13, 0), (14, 3)])
def test_missing_usb488_10_or_capability_stops_before_poll(monkeypatch, offset, value):
    a = Adapter()
    caps = bytearray(a.caps)
    caps[offset] = value
    a.caps = bytes(caps)
    _, run = a.probe(monkeypatch)
    with pytest.raises(CapabilityUnavailable):
        run()
    assert len(a.calls) == 1


@pytest.mark.parametrize(
    "control", [b"", b"\x01\x02", b"\x01\x02\x00\x00", b"\x80\x02\x00", b"\x01\x03\x00"]
)
def test_bad_control_has_no_interrupt_read_and_retains_raw(monkeypatch, control):
    a = Adapter(control=control)
    p, run = a.probe(monkeypatch)
    with pytest.raises(ProtocolError):
        run()
    assert len(a.calls) == 2 and p.receipt["control_hex"] == control.hex()
    assert "adapter_status_byte" not in p.receipt


@pytest.mark.parametrize(
    "interrupt", [b"", b"\x82", b"\x82\x00\x00", b"\x02\x00", b"\x83\x00", b"\x81\x40", b"\x82\x01"]
)
def test_bad_or_unsolicited_notification_is_not_drained_or_retried(monkeypatch, interrupt):
    a = Adapter(interrupt=interrupt)
    p, run = a.probe(monkeypatch)
    with pytest.raises(ProtocolError):
        run()
    assert len(a.calls) == 3 and p.receipt["interrupt_hex"] == interrupt.hex()
    with pytest.raises(StateUncertain):
        run()
    assert len(a.calls) == 3


def test_meter_bit7_is_rejected_even_when_both_usb_replies_agree(monkeypatch):
    a = Adapter(control=b"\x01\x02\x80", interrupt=b"\x82\x80")
    _, run = a.probe(monkeypatch)
    with pytest.raises(ProtocolError):
        run()


@pytest.mark.parametrize("stage", ["caps", "control", "interrupt"])
def test_native_failure_or_late_return_stops_with_no_further_io(monkeypatch, stage):
    for late in (False, True):
        a = Adapter()
        if late:
            a.delays[stage] = 2
        else:
            setattr(a, stage, TimeoutError("synthetic native timeout"))
        p, run = a.probe(monkeypatch, deadline=101)
        with pytest.raises((TimeoutError, OperationTimeout)):
            run()
        assert len(a.calls) == {"caps": 1, "control": 2, "interrupt": 3}[stage]
        assert p.receipt["status"] == "failed" and "adapter_status_byte" not in p.receipt
        with pytest.raises(StateUncertain):
            run()


def test_each_native_call_gets_only_remaining_budget(monkeypatch):
    a = Adapter()
    a.delays = dict(caps=0.3, control=0.3)
    _, run = a.probe(monkeypatch, deadline=101)
    run()
    budgets = [call[-1] for call in a.calls]
    assert 999 <= budgets[0] <= 1000 and 699 <= budgets[1] <= 700
    assert 399 <= budgets[2] <= 400


@pytest.mark.parametrize("deadline", [float("inf"), float("nan"), True, None, 99, 100])
def test_invalid_or_expired_deadline_never_dispatches(monkeypatch, deadline):
    a = Adapter()
    _, run = a.probe(monkeypatch, deadline=deadline)
    with pytest.raises((ValueError, OperationTimeout)):
        run()
    assert a.calls == []


def test_confirmation_is_explicit_and_does_not_consume_probe(monkeypatch):
    a = Adapter()
    p, run = a.probe(monkeypatch)
    with pytest.raises(ValueError):
        p.poll_once(110)
    assert a.calls == []
    run()


def test_firmware_timeout_countermodel_is_indistinguishable_from_quiet_poll(monkeypatch):
    # Independent worlds: firmware reports success+zero for both a quiet meter
    # and a failed internal GPIB poll. The host receives identical USB evidence.
    quiet, failed_bus = Adapter(), Adapter()
    p, q = quiet.probe(monkeypatch)
    qr = q()
    p, f = failed_bus.probe(monkeypatch)
    fr = f()
    assert qr == fr and not fr["instrument_poll_success_verified"]


def test_production_transport_and_zero_cal_guard_are_unchanged(scripted):
    wire = scripted()
    instrument = Instrument(wire)
    with pytest.raises(CapabilityUnavailable, match="serial polling"):
        instrument.zero(confirmed=True)
    with pytest.raises(CapabilityUnavailable, match="serial polling"):
        instrument.calibrate(99, confirmed=True)
    assert wire.calls == []


@pytest.mark.parametrize("cancel_after", [0, 1, 2, 3])
def test_cancellation_before_or_after_native_calls_never_sends_next(monkeypatch, cancel_after):
    a = Adapter()
    a.probe(monkeypatch)
    p = poll.SerialPollProbe(a.interface, cancelled=lambda: len(a.calls) >= cancel_after)
    with pytest.raises(OperationTimeout, match="cancelled"):
        p.poll_once(110, confirmed_source_off_idle=True)
    assert len(a.calls) == cancel_after
    assert "adapter_status_byte" not in p.receipt
    if cancel_after:
        with pytest.raises(StateUncertain):
            p.poll_once(110, confirmed_source_off_idle=True)


def test_cached_completion_bit_is_not_fresh_operation_completion(monkeypatch):
    a = Adapter(control=b"\x01\x02\x02", interrupt=b"\x82\x02")
    _, run = a.probe(monkeypatch)
    r = run()
    assert r["adapter_status_byte"] & 2
    assert not r["freshness_verified"] and not r["procedure_completion_verified"]


def test_system_exit_after_dispatch_is_failed_and_no_retry(monkeypatch):
    a = Adapter(control=SystemExit("synthetic interruption"))
    p, run = a.probe(monkeypatch)
    with pytest.raises(SystemExit):
        run()
    assert len(a.calls) == 2 and p.receipt["status"] == "failed"
    with pytest.raises(StateUncertain):
        run()


def test_large_finite_deadline_still_caps_each_native_call(monkeypatch):
    a = Adapter()
    _, run = a.probe(monkeypatch, deadline=1e308)
    run()
    assert all(call[-1] == 2000 for call in a.calls)
