"""Fail-closed startup for inspected offline QA paths, including Python children.

This is an accident guard, not containment of hostile Python/native code.
Explicit test doubles may replace the blocked entry points.
"""

import os
import sys


def deny(*args, **kwargs):
    raise RuntimeError("HP437B offline QA forbids hardware access")


def audit(event, args):
    if event == "ctypes.dlopen":
        deny()
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = os.fsdecode(args[0])
        if path.startswith("/dev/") and path not in ("/dev/null", "/dev/urandom", "/dev/random"):
            deny()


try:
    os.environ.pop("HP437B_OFFLINE_GUARD", None)
    import ctypes.util  # noqa: F401 - initialize runtime/C support before native-load guard

    sys.addaudithook(audit)
    import pyvisa
    import pyvisa.highlevel
    import usb.backend.libusb0
    import usb.backend.libusb1
    import usb.backend.openusb
    import usb.core

    pyvisa.ResourceManager = deny
    pyvisa.highlevel.ResourceManager = deny
    pyvisa.highlevel.open_visa_library = deny
    usb.core.find = deny
    usb.core.Device.__init__ = deny
    usb.core.Device.read = deny
    usb.core.Device.write = deny
    usb.core.Device.ctrl_transfer = deny
    usb.backend.libusb0.get_backend = deny
    usb.backend.libusb1.get_backend = deny
    usb.backend.openusb.get_backend = deny
    # Serial is not a dependency. If present, prohibit its public constructor.
    try:
        import serial
    except ImportError:
        pass
    else:
        serial.Serial = deny
        serial.serial_for_url = deny
    os.environ["HP437B_OFFLINE_GUARD"] = "active"
except BaseException:
    # Python normally prints sitecustomize errors and continues: fail closed instead.
    import traceback

    traceback.print_exc()
    os.write(2, b"Offline QA startup guard failed\n")
    os._exit(86)
