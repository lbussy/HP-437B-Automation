"""Hardware-free canaries: no actual device/library is used as a control."""

import os
import sys

assert os.environ.get("HP437B_OFFLINE_GUARD") == "active", "Use offline_qa.py"

import ctypes  # noqa: E402
import multiprocessing  # noqa: E402
import subprocess  # noqa: E402

import pyvisa  # noqa: E402
import usb.backend.libusb0  # noqa: E402
import usb.backend.libusb1  # noqa: E402
import usb.backend.openusb  # noqa: E402
import usb.core  # noqa: E402


def check():
    reached = []

    def sentinel(*args, **kwargs):
        reached.append(True)
        raise AssertionError("Sentinel must never be reached")

    attempts = [
        lambda: pyvisa.ResourceManager(sentinel),
        lambda: pyvisa.highlevel.open_visa_library(sentinel),
        lambda: usb.core.find(custom_match=sentinel),
        lambda: usb.core.Device(sentinel),
        lambda: usb.backend.libusb1.get_backend(find_library=sentinel),
        lambda: usb.backend.libusb0.get_backend(find_library=sentinel),
        lambda: usb.backend.openusb.get_backend(find_library=sentinel),
        lambda: usb.core.Device.read(sentinel, sentinel),
        lambda: usb.core.Device.write(sentinel, sentinel, sentinel),
        lambda: usb.core.Device.ctrl_transfer(sentinel, sentinel, sentinel),
        lambda: ctypes.CDLL("offline-sentinel-never-load"),
    ]
    for attempt in attempts:
        try:
            attempt()
        except RuntimeError as exc:
            assert "forbids hardware" in str(exc)
        else:
            raise AssertionError("Hardware guard missing")
    assert not reached


def child(pipe):
    check()
    pipe.send(os.environ["HP437B_OFFLINE_GUARD"])
    pipe.close()


def main():
    check()
    if "--child" in sys.argv:
        return
    subprocess.run([sys.executable, __file__, "--child"], check=True, timeout=10)
    context = multiprocessing.get_context("spawn")
    parent, other = context.Pipe()
    worker = context.Process(target=child, args=(other,))
    worker.start()
    other.close()
    try:
        assert parent.poll(10), "Spawned canary did not reply"
        assert parent.recv() == "active"
        worker.join(5)
        assert worker.exitcode == 0
    finally:
        if worker.is_alive():
            worker.kill()
            worker.join(5)
        parent.close()
        worker.close()
    print("Guard canaries passed: parent, exec, spawn; eleven denial paths each")


if __name__ == "__main__":
    main()
