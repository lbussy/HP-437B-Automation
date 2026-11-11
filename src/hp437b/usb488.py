"""Narrow USB488 local-return extension for the pinned @py USB session.

Original project code. Protocol evidence and version-scoped backend access are
documented in docs/validation/AUTOMATIC-LOCAL.md. No device is opened here.
"""

from .errors import CapabilityUnavailable, TransportError

PROFILE = "xyphro-usb488-gtl-v1"


def session_interface(manager, handle):
    """Reuse the existing PyVISA-py 0.8.1 session; never claim a second handle."""
    sessions = getattr(getattr(manager, "visalib", None), "sessions", {})
    return getattr(sessions.get(handle.session), "interface", None)


def local_profile(interface, timeout_ms):
    """Negotiate only the identified adapter and its actual USBTMC interface."""
    device = getattr(interface, "usb_dev", None)
    descriptor = getattr(interface, "usb_intf", None)
    if (getattr(device, "idVendor", None), getattr(device, "idProduct", None)) != (
        0x03EB,
        0x2065,
    ):
        return None
    if (
        getattr(descriptor, "bInterfaceClass", None),
        getattr(descriptor, "bInterfaceSubClass", None),
        getattr(descriptor, "bInterfaceProtocol", None),
    ) != (0xFE, 3, 1):
        raise CapabilityUnavailable("Local return requires the adapter's USBTMC interface")
    # Class/interface IN, GET_CAPABILITIES; use bInterfaceNumber, not endpoint 0.
    raw = bytes(
        device.ctrl_transfer(0xA1, 7, 0, descriptor.bInterfaceNumber, 24, timeout=timeout_ms)
    )
    if len(raw) != 24 or raw[0] != 1:
        raise TransportError("Invalid USB488 GET_CAPABILITIES reply")
    if not raw[14] & 2:
        return None
    return {
        "profile": PROFILE,
        "interface": descriptor.bInterfaceNumber,
        "capabilities_hex": raw.hex(),
    }


def go_to_local(interface, timeout_ms):
    """Request GTL, checking exact reply; acceptance is not physical proof."""
    profile = local_profile(interface, timeout_ms)
    if profile is None:
        raise CapabilityUnavailable("Adapter does not advertise the qualified local-return path")
    raw = bytes(
        interface.usb_dev.ctrl_transfer(0xA1, 0xA1, 0, profile["interface"], 1, timeout=timeout_ms)
    )
    if raw != b"\x01":
        raise TransportError(f"USB488 GO_TO_LOCAL failed: {raw.hex()}")
    return {**profile, "status": "accepted", "response_hex": raw.hex()}
