import multiprocessing
import time

import pytest

from hp437b.errors import OperationTimeout, TransportError
from hp437b.transport import VisaTransport


def fake_worker(pipe, mode):
    operation, payload, milliseconds = pipe.recv()
    if mode == "hang":
        time.sleep(5)
    elif mode == "disconnect":
        pipe.close()
    else:
        pipe.send(("ok", b"reply"))
        pipe.close()


def connected(mode):
    """Use a real IPC worker but no VISA, USB, or device access."""
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    transport = VisaTransport("USB0::0x1::0x2::TEST::INSTR")
    transport._pipe = parent
    transport._process = context.Process(target=fake_worker, args=(child, mode))
    transport._process.start()
    child.close()
    return transport


def test_construction_and_bad_settings_are_io_free():
    transport = VisaTransport("USB0::0x1::0x2::TEST::INSTR")
    assert transport._process is None
    with pytest.raises(TransportError):
        transport.read(time.monotonic() + 1)
    for name in ("GPIB0::13::INSTR", "USB0::X::INSTR\n", "USB0::bad resource::INSTR"):
        with pytest.raises(ValueError):
            VisaTransport(name)
    transport.close()


def test_real_ipc_deadline_terminates_worker():
    transport = connected("hang")
    process = transport._process
    start = time.monotonic()
    with pytest.raises(OperationTimeout):
        transport.read(start + 0.15)
    assert time.monotonic() - start < 2.0
    assert transport._pipe is None and transport._process is None
    assert process._closed
    transport.close()


def test_local_rpc_timeout_is_bounded_and_recorded_without_retry():
    transport = connected("hang")
    transport.capabilities |= {"go_to_local"}
    start = time.monotonic()
    with pytest.raises(OperationTimeout):
        transport.return_local(start + 0.15)
    assert time.monotonic() - start < 2
    assert transport.local_return["status"] == "failed"
    assert transport._process is None
    transport.close()


def test_ipc_success_and_worker_disconnect():
    transport = connected("ok")
    assert transport.read(time.monotonic() + 2) == b"reply"
    transport.close()
    transport = connected("disconnect")
    try:
        with pytest.raises(TransportError):
            transport.read(time.monotonic() + 2)
    finally:
        transport.close()


def test_worker_calls_real_visa_contract_with_fake_resource(monkeypatch):
    import pyvisa
    from pyvisa.constants import StatusCode

    from hp437b.transport import _worker

    calls = []

    class Handle:
        session = 42

        def __init__(self):
            self.visalib = self

        def write_raw(self, data):
            calls.append(("write_raw", data))
            return len(data)

        def read(self, session, size):
            calls.append(("read", session, size))
            return b"@2" + bytes(range(58)), StatusCode.success

        def close(self):
            calls.append(("close_resource",))

    handle = Handle()

    class Manager:
        def open_resource(self, resource, **kwargs):
            calls.append(("open", resource, kwargs))
            return handle

        def close(self):
            calls.append(("close_manager",))

    def manager(backend):
        assert backend == "@py"
        return Manager()

    monkeypatch.setattr(pyvisa, "ResourceManager", manager)

    class Pipe:
        def __init__(self):
            self.steps = iter(
                [
                    ("open", None, 100),
                    ("write", b"LP2", 50),
                    ("read", None, 40),
                    ("close", None, 10),
                ]
            )
            self.replies = []

        def recv(self):
            return next(self.steps)

        def send(self, message):
            self.replies.append(message)

        def close(self):
            pass

    pipe = Pipe()
    _worker(pipe, "USB0::1::2::S::INSTR", 4096)
    assert [reply[0] for reply in pipe.replies] == ["ok", "ok", "ok"]
    assert pipe.replies[-1][1] == b"@2" + bytes(range(58))
    assert ("read", 42, 4097) in calls and calls[-2:] == [("close_resource",), ("close_manager",)]
    assert handle.read_termination is None and handle.write_termination is None
    assert handle.send_end is True
