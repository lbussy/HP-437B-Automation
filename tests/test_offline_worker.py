"""OQ-06 actual worker dispatch with entirely explicit fake VISA resources."""

from types import SimpleNamespace

import pytest

from hp437b.transport import _worker


@pytest.mark.parametrize(
    "case", ["partial_write", "oversized_read", "incomplete_read", "native_error"]
)
def test_worker_rejects_failed_transfer_and_closes(monkeypatch, case):
    import pyvisa
    from pyvisa.constants import StatusCode

    closed = []

    def read(session, size):
        assert size == 61
        if case == "native_error":
            raise OSError("synthetic native timeout")
        return (
            (b"X" * 61, StatusCode.success)
            if case == "oversized_read"
            else (b"partial", StatusCode.success_max_count_read)
        )

    handle = SimpleNamespace(
        session=42,
        write_raw=lambda data: len(data) - 1,
        close=lambda: closed.append("resource"),
        visalib=SimpleNamespace(read=read),
    )
    manager = SimpleNamespace(
        open_resource=lambda *a, **kw: handle, close=lambda: closed.append("manager")
    )
    monkeypatch.setattr(pyvisa, "ResourceManager", lambda backend: manager)
    operation = "write" if case == "partial_write" else "read"
    messages = iter(
        [
            ("open", None, 100),
            (operation, b"SM" if operation == "write" else None, 50),
            ("close", None, 10),
        ]
    )
    replies = []
    pipe = SimpleNamespace(
        recv=lambda: next(messages), send=replies.append, close=lambda: closed.append("pipe")
    )
    _worker(pipe, "USB0::0x1::0x2::SYNTHETIC::INSTR", 60)
    assert replies[0][0] == "ok" and replies[1][0] == "error"
    assert len(replies) == 2 and closed == ["resource", "manager", "pipe"]
    reason = {
        "partial_write": "Partial command",
        "oversized_read": "Oversized/incomplete",
        "incomplete_read": "Oversized/incomplete",
        "native_error": "synthetic native timeout",
    }[case]
    assert reason in replies[1][1]
