"""Adapter target initialization framing and pulse gate, entirely fake USB."""

import struct
import time
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest
import usb.util

from hp437b.errors import ProtocolError

SELECT = run_path(str(Path(__file__).parents[1] / "tools/usbgpib_target.py"))["select_target"]
RESOURCE = "USB0::0x03EB::0x2065::SYNTHETIC::0::INSTR"


@pytest.mark.parametrize(
    "pulse,version,expected",
    [(b"\x01", b"V2.4", True), (b"\x80", b"V2.4", False), (b"\x01", b"V9.9", False)],
)
def test_internal_target_selection_only_after_pulse_and_version(
    monkeypatch, pulse, version, expected
):
    frames = []
    released = []

    def write(data, timeout):
        frames.append(bytes(data))
        return len(data)

    receive = SimpleNamespace(
        bEndpointAddress=0x81,
        bmAttributes=2,
        read=lambda *a, **kw: (
            b"\x02\x02\xfd\0" + struct.pack("<I", len(version)) + b"\x01\0\0\0" + version
        ),
    )
    send = SimpleNamespace(bEndpointAddress=2, bmAttributes=2, write=write)

    class Interface:
        bInterfaceNumber, bInterfaceClass, bInterfaceSubClass, bInterfaceProtocol = 0, 0xFE, 3, 1

        def __iter__(self):
            return iter([receive, send])

    device = SimpleNamespace(
        serial_number="SYNTHETIC",
        get_active_configuration=lambda: [Interface()],
        ctrl_transfer=lambda *a, **kw: pulse,
    )
    monkeypatch.setattr(usb.util, "claim_interface", lambda *a: None)
    monkeypatch.setattr(usb.util, "release_interface", lambda *a: released.append("release"))
    monkeypatch.setattr(usb.util, "dispose_resources", lambda *a: released.append("dispose"))
    arguments = dict(
        deadline=time.monotonic() + 10, event=lambda *a, **kw: None, find=lambda **kw: [device]
    )
    if expected:
        result = SELECT(RESOURCE, 13, **arguments)
        assert result["primary_address"] == 13 and result["firmware"] == "V2.4"
        assert frames[-1] == b"\x01\x03\xfc\0\x08\0\0\0\x01\0\0\0!addr 13"
    else:
        with pytest.raises(ProtocolError):
            SELECT(RESOURCE, 13, **arguments)
        assert not any(b"!addr" in f for f in frames)
    assert released == ["release", "dispose"]


@pytest.mark.parametrize("value", [True, 0, 31, "13"])
def test_bad_address_refused_before_discovery(value):
    with pytest.raises(ValueError):
        SELECT(
            RESOURCE,
            value,
            deadline=time.monotonic() + 1,
            event=lambda *a, **kw: None,
            find=lambda **kw: pytest.fail("must not discover"),
        )
