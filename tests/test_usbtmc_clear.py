from types import SimpleNamespace

import pytest

from hp437b.errors import CapabilityUnavailable, OperationTimeout, TransportError
from hp437b.usbtmc_clear import clear_interface


def fixture(replies=(b"\x01", b"\x01\x00"), reads=()):
    calls = []
    replies, reads = iter(replies), iter(reads)

    def transfer(*args, **kwargs):
        calls.append(("control", args, kwargs))
        return next(replies)

    def read(size, **kwargs):
        calls.append(("drain", size, kwargs))
        return next(reads)

    interface = SimpleNamespace(
        usb_dev=SimpleNamespace(idVendor=0x03EB, idProduct=0x2065, ctrl_transfer=transfer),
        usb_intf=SimpleNamespace(
            bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1, bInterfaceNumber=4
        ),
        usb_recv_ep=SimpleNamespace(
            bEndpointAddress=0x82, bmAttributes=2, wMaxPacketSize=64, read=read
        ),
        usb_send_ep=SimpleNamespace(
            bEndpointAddress=3, bmAttributes=2, clear_halt=lambda: calls.append(("halt", 3))
        ),
    )
    return interface, calls


def test_exact_clear_sequence_actual_interface_and_no_bulk_program_write():
    i, calls = fixture()
    result = clear_interface(i)
    assert result["status"] == "clear_handshake_completed"
    assert result["interface"] == 4 and result["drained_bytes"] == 0
    assert [c[1] for c in calls[:2]] == [(0xA1, 5, 0, 4, 1), (0xA1, 6, 0, 4, 2)]
    assert all(0 < c[2]["timeout"] <= 10000 for c in calls[:2])
    assert calls[-1] == ("halt", 3)


@pytest.mark.parametrize("field", ["vendor", "class", "in_direction", "out_direction", "type"])
def test_wrong_identity_or_endpoints_stops_before_io(field):
    i, calls = fixture()
    if field == "vendor":
        i.usb_dev.idVendor = 1
    elif field == "class":
        i.usb_intf.bInterfaceClass = 0
    elif field == "in_direction":
        i.usb_recv_ep.bEndpointAddress = 2
    elif field == "out_direction":
        i.usb_send_ep.bEndpointAddress = 0x83
    else:
        i.usb_recv_ep.bmAttributes = 3
    with pytest.raises(CapabilityUnavailable):
        clear_interface(i)
    assert calls == []


@pytest.mark.parametrize("reply", [b"", b"\x01\x00", b"\x80"])
def test_invalid_initiate_never_polls_or_clears_halt(reply):
    i, calls = fixture((reply,))
    with pytest.raises(TransportError):
        clear_interface(i)
    assert len(calls) == 1


@pytest.mark.parametrize("reply", [b"\x01", b"\x01\x00\x00", b"\x80\x00", b"\x01\x01", b"\x02\x80"])
def test_invalid_completion_never_clears_halt(reply):
    i, calls = fixture((b"\x01", reply))
    with pytest.raises(TransportError):
        clear_interface(i)
    assert len(calls) == 2


def test_pending_fifo_is_drained_then_status_checked_before_halt():
    i, calls = fixture((b"\x01", b"\x02\x01", b"\x01\x00"), (b"old data",))
    result = clear_interface(i)
    assert result["drained_bytes"] == 8
    assert [c[0] for c in calls] == ["control", "control", "drain", "control", "halt"]


def test_polling_limit_even_when_clock_does_not_advance(monkeypatch):
    import hp437b.usbtmc_clear as module

    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    i, calls = fixture([b"\x01"] + [b"\x02\x00"] * 64)
    with pytest.raises(OperationTimeout, match="polling limit"):
        clear_interface(i)
    assert len(calls) == 65


def test_deadline_after_success_response_prevents_further_io(monkeypatch):
    import hp437b.usbtmc_clear as module

    clock = iter([0, 0, 11])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    i, calls = fixture()
    with pytest.raises(OperationTimeout):
        clear_interface(i)
    assert len(calls) == 1


def test_drain_budget_stops_without_followup_command():
    i, calls = fixture((b"\x01", b"\x02\x01"), [b"x" * 4096] * 16)
    with pytest.raises(TransportError, match="drain limit"):
        clear_interface(i)
    assert sum(c[0] == "drain" for c in calls) == 16
    assert not any(c[0] == "halt" for c in calls)
