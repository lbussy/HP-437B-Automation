from collections import deque

import pytest

from hp437b.instrument import Instrument
from hp437b.transport import remaining


class Scripted:
    """Independent ordered byte conversation, with no physical I/O."""

    capabilities = frozenset({"read", "write", "eom"})

    def __init__(self, steps=()):
        self.steps = deque(steps)
        self.calls = []
        self.closed = False

    def _step(self, operation, value=None):
        self.calls.append((operation, value))
        expected, result = self.steps.popleft()
        assert operation == expected
        if operation == "write":
            assert value == result
            return None
        if isinstance(result, BaseException):
            raise result
        return result

    def write(self, data, deadline):
        remaining(deadline)
        self._step("write", data)

    def read(self, deadline):
        remaining(deadline)
        return self._step("read")

    def close(self):
        self.closed = True


@pytest.fixture
def scripted():
    return Scripted


@pytest.fixture
def absolute(scripted):
    transport = scripted([("write", b"RL0"), ("write", b"LG")])
    instrument = Instrument(transport)
    instrument.configure_absolute()
    return instrument, transport
