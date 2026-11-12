"""Scoped USBGpib V2.4 volatile target selection; no instrument commands.

Primary source: xyphro/UsbGpib commit 88a13830eea3e2d8bf9f6e33123cc1523f42c70a,
README Multi-device support and miniparser.c parser_finalize (RAM gpib_addr only).
No autoid/string/termination/EEPROM setting, reset, or general bus API is exposed.
"""

import math
import struct
import time

from hp437b.errors import OperationTimeout, ProtocolError


def select_target(resource, address, *, deadline, event, find=None):
    if isinstance(address, bool) or not isinstance(address, int) or not 1 <= address <= 30:
        raise ValueError("Adapter target address must be an integer 1..30")
    parts = resource.split("::")
    if len(parts) not in (5, 6) or int(parts[1], 0) != 0x03EB or int(parts[2], 0) != 0x2065:
        raise ValueError("Only the named USBGpib vendor/product profile is supported")
    if len(parts) == 6 and parts[4] != "0":
        raise ValueError("Only the reviewed USB interface zero is supported")
    import usb.core
    import usb.util
    from pyvisa_py.protocols.usbtmc import BulkInMessage, BulkOutMessage

    def require(condition, message):
        if not condition:
            raise ProtocolError(message)

    def milliseconds():
        left = deadline - time.monotonic()
        if left <= 0:
            raise OperationTimeout("Adapter target preparation deadline expired")
        return max(1, math.ceil(min(left, 10) * 1000))

    devices = list((find or usb.core.find)(find_all=True, idVendor=0x03EB, idProduct=0x2065))
    matched = [d for d in devices if d.serial_number == parts[3]]
    require(len(matched) == 1, "Expected exactly the named USB adapter serial")
    device = matched[0]
    claimed = False
    try:
        interfaces = list(device.get_active_configuration())
        require(len(interfaces) == 1, "Unexpected USB interfaces")
        interface = interfaces[0]
        require(
            (
                interface.bInterfaceNumber,
                interface.bInterfaceClass,
                interface.bInterfaceSubClass,
                interface.bInterfaceProtocol,
            )
            == (0, 0xFE, 3, 1),
            "Unexpected USB488 interface",
        )
        inputs = [e for e in interface if e.bmAttributes & 3 == 2 and e.bEndpointAddress & 0x80]
        outputs = [
            e for e in interface if e.bmAttributes & 3 == 2 and not e.bEndpointAddress & 0x80
        ]
        require(len(inputs) == len(outputs) == 1, "Expected one bulk endpoint each way")
        receive, send = inputs[0], outputs[0]
        usb.util.claim_interface(device, 0)
        claimed = True

        def internal(payload, tag):
            pulse = bytes(device.ctrl_transfer(0xA1, 0x40, 0, 0, 1, timeout=milliseconds()))
            event("adapter_internal_pulse", reply_hex=pulse.hex())
            require(pulse == b"\x01", "Pulse rejected; internal command not sent")
            frame = BulkOutMessage.build_array(tag, True, payload)
            count = send.write(frame, timeout=milliseconds())
            event(
                "adapter_internal_write",
                payload_hex=payload.hex(),
                frame_hex=bytes(frame).hex(),
                count=count,
            )
            require(count == len(frame), "Incomplete adapter-internal transfer; stop without retry")

        internal(b"!ver?", 1)
        request = BulkInMessage.build_array(2, 64, None)
        require(
            send.write(request, timeout=milliseconds()) == len(request),
            "Incomplete firmware reply request",
        )
        raw = bytes(receive.read(128, timeout=milliseconds()))
        event("adapter_firmware_reply", raw_hex=raw.hex())
        require(len(raw) >= 12 and raw[:4] == b"\x02\x02\xfd\0", "Wrong firmware USBTMC reply")
        size = struct.unpack_from("<I", raw, 4)[0]
        require(
            0 < size <= 64 and raw[8:12] == b"\x01\0\0\0" and 12 + size <= len(raw) <= 15 + size,
            "Malformed firmware reply",
        )
        firmware = raw[12 : 12 + size].decode("ascii")
        require(firmware == "V2.4", "Target helper is reviewed for adapter V2.4 only")
        internal(f"!addr {address}".encode("ascii"), 3)
        return {
            "firmware": firmware,
            "usb_serial": parts[3],
            "primary_address": address,
            "setting": "volatile RAM target; no EEPROM write",
            "selection_transfer": "complete; subsequent instrument identity must verify target",
            "source_commit": "88a13830eea3e2d8bf9f6e33123cc1523f42c70a",
        }
    finally:
        try:
            if claimed:
                usb.util.release_interface(device, 0)
        finally:
            usb.util.dispose_resources(device)
