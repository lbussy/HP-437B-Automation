from types import SimpleNamespace

import pytest

from hp437b.errors import CapabilityUnavailable, TransportError
from hp437b.usb488 import go_to_local, local_profile, release_remote_enable


def adapter(*, supported=True, capability_reply=None, local_reply=b"\x01"):
    calls = []
    caps = bytearray(24)
    caps[0] = 1
    caps[14] = 7 if supported else 5

    def transfer(kind, request, value, index, length, *, timeout):
        calls.append((kind, request, value, index, length, timeout))
        if request == 7:
            return caps if capability_reply is None else capability_reply
        assert request in (0xA0, 0xA1)
        return local_reply

    interface = SimpleNamespace(
        usb_dev=SimpleNamespace(idVendor=0x03EB, idProduct=0x2065, ctrl_transfer=transfer),
        usb_intf=SimpleNamespace(
            bInterfaceClass=0xFE, bInterfaceSubClass=3, bInterfaceProtocol=1, bInterfaceNumber=4
        ),
    )
    return interface, calls


def test_negotiation_and_gtl_use_actual_interface_and_exact_status():
    interface, calls = adapter()
    result = go_to_local(interface, 125)
    assert result["status"] == "accepted" and result["response_hex"] == "01"
    assert result["interface"] == 4
    assert calls == [(0xA1, 7, 0, 4, 24, 125), (0xA1, 0xA1, 0, 4, 1, 125)]


@pytest.mark.parametrize("reply", [b"\x01", b"", b"\x80"])
def test_ren_release_uses_control_endpoint_only_and_requires_acceptance(reply):
    interface, calls = adapter(local_reply=reply)
    if reply == b"\x01":
        assert release_remote_enable(interface.usb_dev, interface.usb_intf, 125) == {
            "status": "accepted",
            "interface": 4,
            "response_hex": "01",
        }
    else:
        with pytest.raises(TransportError, match="REN release failed"):
            release_remote_enable(interface.usb_dev, interface.usb_intf, 125)
    assert calls == [(0xA1, 7, 0, 4, 24, 125), (0xA1, 0xA0, 0, 4, 1, 125)]


def test_unrecognized_adapter_or_missing_capability_never_sends_gtl():
    interface, calls = adapter()
    interface.usb_dev.idVendor = 1
    assert local_profile(interface, 100) is None
    assert calls == []
    interface, calls = adapter(supported=False)
    with pytest.raises(CapabilityUnavailable):
        go_to_local(interface, 100)
    assert [c[1] for c in calls] == [7]


@pytest.mark.parametrize("reply", [b"", b"\x01" * 23, b"\x80" + b"\x00" * 23])
def test_bad_capabilities_stop_before_local_request(reply):
    interface, calls = adapter(capability_reply=reply)
    with pytest.raises(TransportError, match="GET_CAPABILITIES"):
        go_to_local(interface, 100)
    assert [c[1] for c in calls] == [7]


@pytest.mark.parametrize("reply", [b"", b"\x80", b"\x01\x01"])
def test_local_rejection_or_malformed_status_cannot_pass(reply):
    interface, _ = adapter(local_reply=reply)
    with pytest.raises(TransportError, match="GO_TO_LOCAL"):
        go_to_local(interface, 100)
