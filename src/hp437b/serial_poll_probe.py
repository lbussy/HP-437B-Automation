"""One-shot USB488 investigation; deliberately not a Transport capability.

No discovery, device opening, normal-logger hook, zero/CAL, or recovery here.
Reuse only an idle, exclusively owned pinned-backend interface in a supervised
worker. Native calls still need an outer process deadline/disposal boundary.
"""

import math
import time
from copy import deepcopy

from .errors import CapabilityUnavailable, OperationTimeout, ProtocolError, StateUncertain

PROFILE = "xyphro-usb488-serial-poll-probe-v1"
TAG = 2  # Tag 1 is reserved for unsolicited SRQ notifications on this adapter.
NATIVE_MS = 2000


def _milliseconds(deadline):
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        raise ValueError("Finite monotonic deadline required")
    if not math.isfinite(deadline):
        raise ValueError("Finite monotonic deadline required")
    left = deadline - time.monotonic()
    # Round down: do not grant a native call more than the remaining budget.
    if left < 0.001:
        raise OperationTimeout("Serial-poll probe deadline expired; no further I/O")
    return math.floor(min(NATIVE_MS / 1000, left) * 1000)


class SerialPollProbe:
    """Single attempt, including failed negotiation; never retry on this object.

    A valid USB reply is only adapter-reported status, not proof that its GPIB
    transaction succeeded or that the byte is fresh (firmware can merge cache).
    A physical caller must raw-close/dispose after any failure, not send cleanup.
    """

    def __init__(self, interface, *, cancelled=None):
        if cancelled is not None and not callable(cancelled):
            raise ValueError("Cancellation check must be callable")
        self._cancelled = cancelled or (lambda: False)
        self._interface = interface
        self._used = False
        self._receipt = dict(
            schema="hp437b.serial-poll-probe.v1",
            profile=PROFILE,
            status="not_attempted",
            stage=None,
            tag=TAG,
            native_dispatched=False,
            poll_dispatched=False,
            instrument_poll_success_verified=False,
            freshness_verified=False,
            procedure_completion_verified=False,
            evidence_limit="Adapter can mask GPIB timeout and merge cached SRQ bits",
        )

    @property
    def receipt(self):
        return deepcopy(self._receipt)

    def _check(self, deadline):
        if self._cancelled():
            raise OperationTimeout("Serial-poll probe cancelled; no further I/O")
        return _milliseconds(deadline)

    def _control(self, stage, request, value, index, length, deadline):
        timeout = self._check(deadline)
        self._receipt.update(stage=stage, native_dispatched=True)
        if request == 128:
            self._receipt["poll_dispatched"] = True
        raw = bytes(
            self._interface.usb_dev.ctrl_transfer(
                0xA1, request, value, index, length, timeout=timeout
            )
        )
        self._receipt[stage + "_hex"] = raw.hex()
        self._check(deadline)  # A late native return is never accepted.
        return raw

    def poll_once(self, deadline, *, confirmed_source_off_idle=False):
        if self._used:
            raise StateUncertain("One-shot probe already used; no retry or reconnect")
        if confirmed_source_off_idle is not True:
            raise ValueError("Explicit supervised source-off/idle confirmation required")
        self._check(deadline)
        self._used = True
        self._receipt.update(status="in_progress", stage="descriptor_preflight")
        try:
            interface = self._interface
            device = getattr(interface, "usb_dev", None)
            descriptor = getattr(interface, "usb_intf", None)
            if (getattr(device, "idVendor", None), getattr(device, "idProduct", None)) != (
                0x03EB,
                0x2065,
            ):
                raise CapabilityUnavailable("Only the selected XyphroLabs USBGpib profile")
            if (
                getattr(descriptor, "bInterfaceClass", None),
                getattr(descriptor, "bInterfaceSubClass", None),
                getattr(descriptor, "bInterfaceProtocol", None),
            ) != (0xFE, 3, 1):
                raise CapabilityUnavailable("USB488 interface required")
            index = getattr(descriptor, "bInterfaceNumber", None)
            if type(index) is not int or not 0 <= index <= 255:
                raise CapabilityUnavailable("Actual USB interface number required")
            endpoint = getattr(interface, "usb_intr_in", None)
            address = getattr(endpoint, "bEndpointAddress", None)
            attributes = getattr(endpoint, "bmAttributes", None)
            packet = getattr(endpoint, "wMaxPacketSize", None)
            if (
                type(address) is not int
                or not 0x81 <= address <= 0x8F
                or type(attributes) is not int
                or attributes & 3 != 3
                or type(packet) is not int
                or packet < 2
                or not callable(getattr(endpoint, "read", None))
            ):
                raise CapabilityUnavailable(
                    "Actual interrupt-IN endpoint required; no bulk fallback"
                )
            self._receipt.update(interface=index, interrupt_endpoint=address)
            caps = self._control("capabilities", 7, 0, index, 24, deadline)
            if len(caps) != 24 or caps[0] != 1:
                raise ProtocolError("Malformed GET_CAPABILITIES reply")
            if caps[12:14] != b"\x00\x01" or not caps[14] & 4:
                raise CapabilityUnavailable("USB488 1.0 status-byte path not advertised")
            control = self._control("control", 128, TAG, index, 3, deadline)
            if len(control) != 3 or control[0] != 1 or control[1] != TAG:
                raise ProtocolError("Malformed/rejected READ_STATUS_BYTE control response")
            timeout = self._check(deadline)
            self._receipt["stage"] = "interrupt"
            interrupt = bytes(endpoint.read(2, timeout=timeout))
            self._receipt["interrupt_hex"] = interrupt.hex()
            self._check(deadline)
            if len(interrupt) != 2 or interrupt[0] != 0x80 | TAG:
                raise ProtocolError("Unexpected interrupt/tag; no drain or retry")
            if interrupt[1] != control[2] or control[2] > 127:
                raise ProtocolError("Inconsistent or invalid HP 437B status byte")
            self._receipt.update(
                status="adapter_reply_validated",
                stage="finished",
                adapter_status_byte=interrupt[1],
            )
            return self.receipt
        except BaseException as exc:
            self._receipt.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            raise
