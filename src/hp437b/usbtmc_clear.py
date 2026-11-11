"""Experimental, explicit USBTMC clear for the identified adapter interface.

No discovery/opening, reset, ASCII command, retry, or uncertainty acknowledgement
occurs here. Call only with exclusive ownership and a bounded outer worker.
Physical qualification and API release are tracked separately.
"""

import math
import time

from .errors import CapabilityUnavailable, OperationTimeout, TransportError


def clear_interface(interface, *, timeout: float = 10.0) -> dict:
    """Clear pending transfers, checking exact replies and bounded FIFO draining.

    On the source-inspected adapter this can send GPIB SDC/IFC. It is not a meter
    preset or proof of successful subsequent identification/acquisition/local.
    """
    if not math.isfinite(timeout) or not 0 < timeout <= 20:
        raise ValueError("Clear timeout must be finite and within 0..20 seconds")
    device, descriptor = interface.usb_dev, interface.usb_intf
    if (device.idVendor, device.idProduct) != (0x03EB, 0x2065):
        raise CapabilityUnavailable("Clear requires the identified XyphroLabs adapter")
    if (
        descriptor.bInterfaceClass,
        descriptor.bInterfaceSubClass,
        descriptor.bInterfaceProtocol,
    ) != (0xFE, 3, 1):
        raise CapabilityUnavailable("Clear requires the adapter USB488 interface")
    receive, send = interface.usb_recv_ep, interface.usb_send_ep
    if not (
        receive.bEndpointAddress & 0x80
        and not send.bEndpointAddress & 0x80
        and receive.bmAttributes & 3 == send.bmAttributes & 3 == 2
        and 0 < receive.wMaxPacketSize <= 1024
    ):
        raise CapabilityUnavailable("Clear requires valid bulk IN/OUT endpoints")
    deadline = time.monotonic() + timeout
    trace = []
    drained = 0

    def milliseconds():
        left = deadline - time.monotonic()
        if left <= 0:
            raise OperationTimeout("USBTMC clear deadline expired; no retry")
        return max(1, math.ceil(left * 1000))

    def control(request, length):
        raw = bytes(
            device.ctrl_transfer(
                0xA1, request, 0, descriptor.bInterfaceNumber, length, timeout=milliseconds()
            )
        )
        milliseconds()
        trace.append({"request": request, "reply_hex": raw.hex()})
        if len(raw) != length:
            raise TransportError("Malformed USBTMC clear reply length")
        return raw

    if control(5, 1) != b"\x01":
        raise TransportError("USBTMC INITIATE_CLEAR rejected; stop without retry")
    for _ in range(64):
        status, flags = control(6, 2)
        if flags & ~1:
            raise TransportError("Unexpected USBTMC clear flags")
        if status == 1:
            if flags:
                raise TransportError("USBTMC clear success still reports pending bulk data")
            milliseconds()
            send.clear_halt()
            milliseconds()
            return {
                "profile": "xyphro-usbtmc-clear-candidate-v1",
                "status": "clear_handshake_completed",
                "interface": descriptor.bInterfaceNumber,
                "bulk_out_endpoint": send.bEndpointAddress,
                "drained_bytes": drained,
                "trace": trace,
                "bulk_out_halt_cleared": True,
            }
        if status != 2:
            raise TransportError(f"USBTMC CHECK_CLEAR_STATUS rejected: {status:02x}")
        if flags:
            # Drain only explicitly indicated pending USB data, never parse it as
            # an instrument reply or send another trigger while clearing.
            while True:
                if drained >= 65536:
                    raise TransportError("USBTMC clear FIFO drain limit exceeded")
                raw = bytes(receive.read(min(4096, 65536 - drained), timeout=milliseconds()))
                milliseconds()
                if len(raw) > min(4096, 65536 - drained):
                    raise TransportError("USBTMC clear returned oversized drain data")
                drained += len(raw)
                if len(raw) < 4096:
                    break
        else:
            time.sleep(min(0.05, milliseconds() / 1000))
    raise OperationTimeout("USBTMC clear polling limit exceeded; no retry")
