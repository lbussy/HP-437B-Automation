"""Explicit logger demo only: synthetic data, not a model of meter accuracy/timing."""

from .transport import remaining


def status_fixture(*, logarithmic: bool = True) -> bytes:
    return (
        "00000011001000"
        + ("1" if logarithmic else "0")
        + "A000200000"
        + ("1" if logarithmic else "0")
    ).encode("ascii") + b"\r\n"


class DemoTransport:
    capabilities = frozenset({"write", "read", "eom"})
    metadata = {"transport": "synthetic demo", "hardware": "none"}

    def __init__(self):
        self.logarithmic = True
        self.pending = None
        self.closed = False

    def write(self, data: bytes, deadline: float):
        remaining(deadline)
        if self.closed:
            raise RuntimeError("Demo closed")
        if data == b"LG":
            self.logarithmic = True
        elif data == b"LN":
            self.logarithmic = False
        elif data in (b"*IDN?", b"SM", b"TR2"):
            self.pending = data
        elif data != b"RL0":
            raise ValueError("Demo supports only the basic logger conversation")

    def read(self, deadline: float) -> bytes:
        remaining(deadline)
        code, self.pending = self.pending, None
        if code == b"*IDN?":
            return b"HEWLETT-PACKARD,437B,,1.9\r\n"
        if code == b"SM":
            return status_fixture(logarithmic=self.logarithmic)
        if code == b"TR2":
            return b"-3.0000E+01\r\n" if self.logarithmic else b"+1.0000E-06\r\n"
        raise ValueError("No synthetic reply queued")

    def close(self):
        self.closed = True
