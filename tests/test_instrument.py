import threading
import time

import pytest

from hp437b.errors import (
    CapabilityUnavailable,
    OperationTimeout,
    ProtocolError,
    StateUncertain,
    TransportError,
)
from hp437b.instrument import BUS_GUARDS, Instrument


def test_trigger_read_order_and_units(absolute):
    device, wire = absolute
    wire.steps.extend([("write", b"TR2"), ("read", b"-3.0000E+01\r\n")])
    assert device.acquire().unit == "dBm"
    assert wire.calls[-2:] == [("write", b"TR2"), ("read", None)]
    assert not wire.steps


def test_close_returns_local_once_only_when_state_is_known(scripted):
    class LocalWire(scripted):
        capabilities = scripted.capabilities | {"go_to_local"}

        def return_local(self, deadline):
            assert deadline > time.monotonic()
            self.calls.append(("local", None))

    wire = LocalWire()
    device = Instrument(wire)
    device.close()
    device.close()
    assert wire.calls == [("local", None)] and wire.closed

    wire = LocalWire([("write", b"*IDN?"), ("read", b"BROKEN\r\n")])
    device = Instrument(wire)
    with pytest.raises(ProtocolError):
        device.identify()
    device.close()
    assert all(call[0] != "local" for call in wire.calls) and wire.closed


def test_local_failure_still_closes_and_is_not_retried(scripted):
    class LocalFailure(scripted):
        capabilities = scripted.capabilities | {"go_to_local"}

        def return_local(self, deadline):
            self.calls.append(("local", None))
            raise TransportError("GTL rejected")

    wire = LocalFailure()
    device = Instrument(wire)
    with pytest.raises(TransportError, match="GTL rejected"):
        device.close()
    device.close()
    assert wire.calls == [("local", None)] and wire.closed


def test_ordinary_read_has_no_implicit_trigger(absolute):
    device, wire = absolute
    wire.steps.append(("read", b"+1.0000E+00\r\n"))
    assert device.acquire(None).value == 1
    assert wire.calls[-1] == ("read", None)


def test_unit_and_confirmation_guards_before_io(scripted):
    wire = scripted()
    device = Instrument(wire)
    with pytest.raises(StateUncertain):
        device.acquire()
    for code in ("RC", "ST", "PR", "OC1", "RF2"):
        with pytest.raises(ValueError):
            device.command(code, 2)
    with pytest.raises(CapabilityUnavailable):
        device.zero(confirmed=True)
    with pytest.raises(CapabilityUnavailable):
        device.command("SN0", "BAD")
    assert wire.calls == []


@pytest.mark.parametrize("capability", list(BUS_GUARDS))
def test_bus_guards_before_io(capability, scripted):
    wire = scripted()
    with pytest.raises(CapabilityUnavailable):
        Instrument(wire).bus(capability)
    assert wire.calls == []


@pytest.mark.parametrize(
    "failure", [OperationTimeout("timed out"), KeyboardInterrupt(), OSError("unplugged")]
)
def test_failed_acquisition_taints_and_recovery_is_explicit(failure, absolute):
    device, wire = absolute
    wire.steps.extend([("write", b"TR2"), ("read", failure)])
    with pytest.raises(type(failure)):
        device.acquire()
    count = len(wire.calls)
    with pytest.raises(StateUncertain):
        device.query("*STB?")
    assert len(wire.calls) == count
    with pytest.raises(ValueError):
        device.acknowledge_external_recovery()
    device.acknowledge_external_recovery(confirmed=True)
    with pytest.raises(StateUncertain):
        device.acquire()  # Units must be established again.


def test_bad_reply_preserved_and_no_automatic_retry(absolute):
    device, wire = absolute
    wire.steps.extend([("write", b"TR2"), ("read", b"BROKEN\r\n")])
    with pytest.raises(ProtocolError):
        device.acquire()
    assert device.last_raw == b"BROKEN\r\n" and not wire.steps


def test_calibration_serial_poll_is_not_ascii_query(scripted):
    class Polling(scripted):
        capabilities = frozenset({"read", "write", "serial_poll"})

        def serial_poll(self, deadline):
            assert deadline > time.monotonic()
            return self._step("poll")

    wire = Polling([("write", b"CSCL98.5EN"), ("poll", 0), ("poll", 2)])
    device = Instrument(wire)
    device.calibrate("98.5", confirmed=True)
    assert wire.calls == [("write", b"CSCL98.5EN"), ("poll", None), ("poll", None)]


def test_concurrent_query_waits_for_acquisition(absolute):
    device, wire = absolute
    entered, release = threading.Event(), threading.Event()
    original = wire.read

    def held(deadline):
        entered.set()
        assert release.wait(2)
        return original(deadline)

    wire.steps.extend(
        [("write", b"TR2"), ("read", b"-3.0000E+01\r\n"), ("write", b"*STB?"), ("read", b"000\r\n")]
    )
    wire.read = held
    failures = []

    def call(fn):
        try:
            fn()
        except BaseException as exc:
            failures.append(exc)

    acquire = threading.Thread(target=call, args=(device.acquire,))
    query = threading.Thread(target=call, args=(lambda: device.query("*STB?"),))
    acquire.start()
    assert entered.wait(2)
    query.start()
    time.sleep(0.02)
    assert wire.calls[-1] == ("write", b"TR2")
    release.set()
    acquire.join(2)
    query.join(2)
    assert not acquire.is_alive() and not query.is_alive() and not failures and not wire.steps


def test_dd_firmware_guard_and_recall_unit_invalidation(scripted):
    wire = scripted(
        [
            ("write", b"*IDN?"),
            ("read", b"HEWLETT-PACKARD,437B,,1.9\r\n"),
            ("write", b"DD"),
            ("write", b"RC2EN"),
        ]
    )
    device = Instrument(wire)
    with pytest.raises(CapabilityUnavailable):
        device.command("DD")
    device.identify()
    device.command("DD")
    device.command("RC", 2, confirmed=True)
    with pytest.raises(StateUncertain):
        _ = device.unit


@pytest.mark.parametrize(
    "code,raw,expected",
    [
        ("*STB?", b"012\r\n", 12),
        ("*ESE?", b"032\r\n", 32),
        ("*ESR?", b"128\r\n", 128),
        ("*SRE?", b"004\r\n", 4),
        ("ERR?", b"091\r\n", 91),
        ("OD", b"REF CF 100.0%\r\n", "REF CF 100.0%"),
        ("LP2", b"@2" + bytes(range(58)), b"@2" + bytes(range(58))),
    ],
)
def test_all_query_parsing_paths(scripted, code, raw, expected):
    wire = scripted([("write", code.encode()), ("read", raw)])
    reply = Instrument(wire).query(code)
    assert reply.raw == raw and reply.value == expected and not wire.steps


def test_polling_capability_requires_method_before_any_write(scripted):
    wire = scripted()
    wire.capabilities = frozenset({"serial_poll"})
    with pytest.raises(CapabilityUnavailable):
        Instrument(wire).zero(confirmed=True)
    assert wire.calls == []


def test_serial_poll_cannot_succeed_after_operation_deadline(scripted):
    class LatePoll(scripted):
        capabilities = frozenset({"serial_poll"})

        def serial_poll(self, deadline):
            time.sleep(0.02)
            return 2

    wire = LatePoll([("write", b"CSZE")])
    with pytest.raises(OperationTimeout):
        Instrument(wire, timeout=0.005).zero(confirmed=True)


def test_context_tokens_cannot_be_sent_as_free_standing_operations(scripted):
    wire = scripted()
    for code in ("EN", "UP", "DN", "RT", "LT", "HZ", "PCT", "%"):
        with pytest.raises(ValueError):
            Instrument(wire).command(code)
    assert wire.calls == []
