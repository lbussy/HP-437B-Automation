"""One bounded USBGpib session with TR1 and numeric CAL FAC verification."""

import re
import time
from decimal import Decimal
from functools import partial

from . import diagnostics_physical as diagnostics
from . import provenance as p
from .errors import ProtocolError
from .instrument import Instrument
from .reconciliation_physical import PhysicalTarget, _matching_usb
from .sensor_correction import SENSOR_SERIAL
from .transport import VisaTransport

METER_SERIAL = "3125U22346"
ADAPTER = "HEWLETT-PACKARD_437B_2.0"
RESOURCE = f"USB0::0x03EB::0x2065::{ADAPTER}::0::INSTR"
IDN = b"HEWLETT-PACKARD,437B,,2.0"
TARGET = PhysicalTarget(RESOURCE, ADAPTER, IDN)
LIMIT_W = Decimal("0.1")
BASELINE_W = Decimal("0.000005")
FLOOR_W = Decimal("0.000001")


def zero(output, lock_root, run, cancelled):
    result = diagnostics.run_physical(
        output,
        target=TARGET,
        confirmed=True,
        prior_worker_stopped=True,
        prepared={
            **dict.fromkeys(diagnostics.PREPARED, True),
            "no_rf_input": True,
            "warmed_up": True,
        },
        equipment={"meter_serial": METER_SERIAL, "sensor_serial": SENSOR_SERIAL},
        workflow_lock_root=lock_root,
        supervised_zero=True,
        confirmed_zero=True,
        work_s=45,
        total_s=50,
        cancelled=cancelled,
        _pi_sweep_run=run,
    )
    p.require(
        result["status"] == "completed"
        and result["zero_assessment"]["accepted_full_case"]
        and result["transport_closed"],
        "Supervised ZERO or its closure is unconfirmed",
    )


def healthy(status):
    return (
        status.unit == "W"
        and not status.logarithmic
        and status.range_code in range(11, 16)
        and status.filter_code in range(10, 20)
        and not any(
            (
                status.reference_on,
                status.entry_error,
                status.measurement_error,
                status.offset_on,
                status.duty_on,
                status.relative,
            )
        )
    )


def factor_matches(raw, receipt):
    match = re.fullmatch(rb"\s*CAL\s*FAC\s*(\d{1,3}\.\d)\s*%\s*", raw)
    return bool(
        match and Decimal(match[1].decode()) == Decimal(receipt["commanded_factor_percent"])
    )


class Meter:
    """Preserve raw frames while the source supervisor owns independent Stop."""

    def __init__(self, *, transport=VisaTransport, match=_matching_usb, clock=time.monotonic_ns):
        self.clock, self.match = clock, match
        self.transport = transport(RESOURCE)
        self.instrument = Instrument(self.transport, timeout=2)
        self.opened = False

    def _limit(self, deadline):
        remaining = (deadline - self.clock()) / 10**9
        if remaining <= 0:
            raise TimeoutError("Meter operation deadline expired")
        self.instrument.timeout = min(2, remaining)

    def open(self, deadline):
        TARGET.validate()
        self._limit(deadline)
        self.transport.open(self.instrument.timeout, preflight=partial(self.match, ADAPTER))
        self._limit(deadline)
        identity = self.instrument.identify().raw
        p.require(identity.rstrip(b"\r\n") == IDN, "HP 437B identity changed")
        self._limit(deadline)
        status = self.instrument.read_status()
        p.require(
            not any(
                (
                    status.reference_on,
                    status.entry_error,
                    status.measurement_error,
                    status.offset_on,
                    status.duty_on,
                )
            ),
            "Meter is not prepared with POWER REF and corrections off",
        )
        self._limit(deadline)
        self.instrument.command("RL0")
        self._limit(deadline)
        self.instrument.command("LN")
        self.opened = True
        return identity.hex()

    def factor(self, receipt, deadline, evidence):
        meter = self.instrument
        self._limit(deadline)
        meter.command("KB", receipt["commanded_factor_percent"])
        self._limit(deadline)
        with meter._operation() as end:
            meter._write(b"KBOD", end)
            raw = meter._read(end)
        evidence["display_hex"] = raw.hex()
        self._limit(deadline)
        meter.command("EX")
        p.require(factor_matches(raw, receipt), "CAL FAC numeric readback differs from certificate")
        self._limit(deadline)
        status = meter.read_status()
        evidence["status_hex"] = status.raw.hex()
        p.require(healthy(status), "CAL FAC status is unconfirmed")

    def read(self, deadline, evidence, maximum=LIMIT_W):
        meter = self.instrument
        self._limit(deadline)
        try:
            reading = meter.acquire("TR1")
        except BaseException:
            evidence["raw_hex"] = meter.last_raw.hex()
            # An invalid frame leaves stream synchrony unproved.
            meter._uncertain = True
            raise
        evidence["raw_hex"] = reading.raw.hex()
        if reading.error_code or reading.value is None:
            raise ProtocolError("Meter returned an instrument error")
        p.require(reading.value <= maximum, "Meter reading exceeds the reviewed indication bound")
        self._limit(deadline)
        status = meter.read_status()
        evidence["status_hex"] = status.raw.hex()
        p.require(healthy(status), "Meter status is outside the prepared sweep conditions")
        return reading.value

    def can_read(self):
        return self.opened and not self.instrument._uncertain

    def close(self):
        self.instrument.timeout = 2
        self.instrument.close()
        return self.instrument.cleanup
