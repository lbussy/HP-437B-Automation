import multiprocessing
import time

import pytest

from hp437b.errors import OperationTimeout, TransportError
from hp437b.transport import VisaTransport


def fake_worker(pipe, mode):
    operation, payload, milliseconds = pipe.recv()
    if mode == "hang":
        time.sleep(5)
    elif mode in {"late_error", "late_ok", "late_disconnect"}:
        time.sleep(milliseconds / 1000 + 0.08)
        if mode == "late_disconnect":
            pipe.close()
            return
        pipe.send(("error", "VisaIOError: timeout") if mode == "late_error" else ("ok", b"late"))
        # Remain alive until parent disposal, rather than closing the pipe early.
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
    assert transport.read_deadline_cleanup["status"] == "worker_still_busy"
    assert 0.9 <= transport.read_deadline_cleanup["elapsed_s"] < 1.5
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
    assert transport.read_deadline_cleanup is None
    transport.close()
    transport = connected("disconnect")
    try:
        with pytest.raises(TransportError):
            transport.read(time.monotonic() + 2)
    finally:
        transport.close()


@pytest.mark.parametrize(
    ("mode", "status"),
    [
        ("late_error", "worker_error_received"),
        ("late_ok", "late_result_discarded"),
        ("late_disconnect", "worker_disconnected"),
    ],
)
def test_expired_read_remains_failed_while_backend_finishes(mode, status, monkeypatch):
    transport = connected(mode)
    sent = []
    send = transport._pipe.send

    def record(message):
        sent.append(message)
        send(message)

    monkeypatch.setattr(transport._pipe, "send", record)
    start = time.monotonic()
    with pytest.raises(OperationTimeout, match="read deadline expired"):
        transport.read(start + 0.2)
    assert transport.read_deadline_cleanup["status"] == status
    assert transport.read_deadline_cleanup["budget_s"] == 1.0
    if mode == "late_error":
        assert transport.read_deadline_cleanup["worker_error"] == "VisaIOError: timeout"
    assert transport._pipe is None and transport._process is None
    assert len(sent) == 1 and sent[0][:2] == ("read", None)
    assert 0 < sent[0][2] <= 200  # The native read budget was not shortened or extended.
    assert time.monotonic() - start < 2


def test_non_read_deadline_keeps_immediate_worker_disposal():
    transport = connected("hang")
    start = time.monotonic()
    with pytest.raises(OperationTimeout):
        transport.write(b"SM", start + 0.15)
    assert transport.read_deadline_cleanup is None
    assert transport._process is None
    assert time.monotonic() - start < 1


def test_read_deadline_before_dispatch_does_not_wait_for_backend():
    transport = connected("hang")
    start = time.monotonic()
    with pytest.raises(OperationTimeout):
        transport.read(start - 1)
    assert transport.read_deadline_cleanup is None
    assert transport._process is None and time.monotonic() - start < 1


def test_read_deadline_expiring_just_after_dispatch_still_allows_shutdown(monkeypatch):
    import hp437b.transport as module

    transport = connected("late_error")
    calls = 0

    def expire_after_send(deadline):
        nonlocal calls
        calls += 1
        if calls == 1:
            return 0.2
        raise OperationTimeout("Read deadline expired after dispatch")

    monkeypatch.setattr(module, "remaining", expire_after_send)
    with pytest.raises(OperationTimeout):
        transport.read(time.monotonic() + 0.2)
    assert transport.read_deadline_cleanup["status"] == "worker_error_received"
    assert transport._process is None


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
