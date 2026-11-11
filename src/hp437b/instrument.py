"""Serialized source-backed operations; no automatic preset, zero, or reference activation."""

import math
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from . import protocol
from .commands import encode, specification
from .errors import CapabilityUnavailable, ProtocolError, StateUncertain
from .transport import Transport, remaining


@dataclass(frozen=True)
class Reply:
    raw: bytes
    value: object


BUS_GUARDS = {
    "G001": "A09: explicit address control is adapter-managed; deferred",
    "G005": "A09: raw UNL deferred",
    "G006": "A09: raw UNT deferred",
    "G007": "A09: explicit REN deferred (automatic initialization is separate)",
    "G008": "A09: local control deferred",
    "G009": "A09: lockout deferred",
    "G010": "A09: clear lockout deferred",
    "G011": "A09: device clear deferred",
    "G012": "A09: universal clear deferred",
    "G013": "A09: GET deferred",
    "G014": "A09: SRQ events deferred",
    "G015": "A09: serial poll deferred",
    "G016": "A09: explicit SPD deferred",
    "G017": "A09: parallel poll deferred",
    "G018": "A09: parallel poll unconfigure deferred",
    "G019": "A09: IFC deferred",
    "G020": "C0: instrument controller-role exclusion",
}


class Instrument:
    def __init__(self, transport: Transport, *, timeout: float = 10.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Finite positive operation timeout required")
        self.transport = transport
        self.timeout = timeout
        self._lock = threading.RLock()
        self._uncertain = False
        self._closed = False
        self._log = self._relative = None
        self.last_raw = b""
        self.firmware: tuple[int, ...] | None = None

    @property
    def unit(self):
        if self._log is None or self._relative is None:
            raise StateUncertain("Establish units using SM or explicit scale and REL selection")
        return ("dB" if self._log else "%") if self._relative else ("dBm" if self._log else "W")

    @contextmanager
    def _operation(self):
        with self._lock:
            if self._closed or self._uncertain:
                raise StateUncertain(
                    "Connection closed/uncertain; explicitly reconcile before reuse"
                )
            self.last_raw = b""
            deadline = time.monotonic() + self.timeout
            try:
                yield deadline
            except BaseException:
                self._uncertain = True
                self._log = self._relative = None
                raise

    def _write(self, data, deadline):
        remaining(deadline)
        self.transport.write(data, deadline)
        remaining(deadline)

    def _read(self, deadline):
        remaining(deadline)
        data = self.transport.read(deadline)
        if not isinstance(data, bytes):
            raise ProtocolError("Transport must return bytes")
        self.last_raw = data
        remaining(deadline)
        return data

    def query(self, code: str) -> Reply:
        spec = specification(code)
        if spec.kind != "Q":
            raise ValueError("Use a documented query/output selection")
        payload = encode(code)
        with self._operation() as deadline:
            self._write(payload, deadline)
            raw = self._read(deadline)
            if code == "*IDN?":
                value = protocol.identification(raw)
                self.firmware = tuple(map(int, value.firmware.split(".")))
            elif code == "SM":
                value = protocol.status(raw)
                self._log, self._relative = value.logarithmic, value.relative
            elif code == "LP2":
                value = protocol.snapshot(raw)
            elif code == "OD":
                value = protocol.ascii_payload(raw)
            else:
                value = protocol.byte_value(raw, 127 if code == "*STB?" else 255)
            return Reply(raw, value)

    def identify(self) -> protocol.Identification:
        return self.query("*IDN?").value

    def read_status(self) -> protocol.Status:
        return self.query("SM").value

    def command(self, code: str, value=None, *, confirmed: bool = False, **kwargs) -> None:
        spec = specification(code)
        if spec.kind != "W" or code in ("CL", "ZE", "TR1", "TR2", "DN", "UP", "LT", "RT"):
            raise ValueError("Use the complete query, acquisition, calibration, or zero operation")
        if code in ("PR", "RC", "ST", "OC1") or code.startswith("RF"):
            if confirmed is not True:
                raise ValueError(
                    f"{code} changes reference/configuration/storage; explicitly confirm"
                )
        payload = encode(code, value, **kwargs)
        with self._lock:
            if code == "DD" and (self.firmware is None or self.firmware < (1, 5)):
                raise CapabilityUnavailable("C017: DD requires identified firmware 1.5+; A07")
            with self._operation() as deadline:
                self._write(payload, deadline)
                if code in ("LG", "LN"):
                    self._log = code == "LG"
                elif code in ("RL0", "RL1", "RL2"):
                    self._relative = code != "RL0"
                elif code == "PR":
                    self._log, self._relative = True, False
                elif code == "RC":
                    self._log = self._relative = None

    def configure_absolute(self, unit: str = "dBm") -> None:
        if unit not in ("dBm", "W"):
            raise ValueError("Absolute units must be dBm or W")
        with self._lock:
            self.command("RL0")
            self.command("LG" if unit == "dBm" else "LN")

    def acquire(self, trigger: str | None = "TR2") -> protocol.Measurement:
        if trigger not in (None, "TR1", "TR2"):
            raise ValueError("Use TR1, TR2, or None for an ordinary read")
        with self._lock:
            unit = self.unit
            with self._operation() as deadline:
                if trigger:
                    self._write(encode(trigger), deadline)
                # No ASCII status queries until the triggered reply has been consumed.
                return protocol.measurement(self._read(deadline), unit)

    def _cal_zero(self, code: str, value=None, *, confirmed: bool = False):
        if confirmed is not True:
            raise ValueError("Confirm prepared reference/no-RF path before calibration/zero")
        payload = encode(code, value)
        if "serial_poll" not in self.transport.capabilities or not callable(
            getattr(self.transport, "serial_poll", None)
        ):
            raise CapabilityUnavailable("A09: calibration/zero completion requires serial polling")
        with self._operation() as deadline:
            self._write(b"CS" + payload, deadline)
            while True:
                remaining(deadline)
                status = self.transport.serial_poll(deadline)
                remaining(deadline)
                if (
                    isinstance(status, bool)
                    or not isinstance(status, int)
                    or not 0 <= status <= 127
                ):
                    raise ProtocolError("Invalid serial-poll status")
                if status & 8:
                    raise ProtocolError("Instrument reported measurement error during cal/zero")
                if status & 2:
                    return
                time.sleep(min(0.01, remaining(deadline)))

    def zero(self, *, confirmed: bool = False):
        self._cal_zero("ZE", confirmed=confirmed)

    def calibrate(self, reference_factor, *, confirmed: bool = False):
        self._cal_zero("CL", reference_factor, confirmed=confirmed)

    def bus(self, capability_id: str):
        if capability_id not in BUS_GUARDS:
            raise ValueError(
                "Use acquire/command/transport for G002/G003/G004; unknown ID rejected"
            )
        raise CapabilityUnavailable(f"{capability_id}: {BUS_GUARDS[capability_id]}")

    def acknowledge_external_recovery(self, *, confirmed: bool = False):
        """Operator has restored the device/stream and reopened the transport if necessary."""
        if confirmed is not True:
            raise ValueError("Confirm device/stream reconciliation explicitly")
        with self._lock:
            if self._closed:
                raise StateUncertain("Create a new Instrument after close")
            self._uncertain = False
            self._log = self._relative = None
            self.firmware = None

    def close(self):
        with self._lock:
            self._closed = True
            self.transport.close()
