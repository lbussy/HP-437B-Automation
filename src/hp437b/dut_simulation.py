"""Explicit fake external controls and fake GPIB meter; no discovery or I/O."""

from datetime import UTC, datetime
from decimal import Decimal as D

from . import dut_control as c
from . import stability_simulation as base
from .errors import OperationTimeout
from .power_setting import factor

SCENARIOS = (
    "nominal",
    "low-output",
    "missing-loss",
    "sensor-plane",
    "identity-mismatch",
    "initial-on",
    "current-mismatch",
    "voltage-missing",
    "frequency-mismatch",
    "key-rejected",
    "source-still-on",
    "source-off-failure",
    "restore-mismatch",
    "restore-failure",
    "observer-timeout",
    "late-reply",
    "meter-timeout",
    "meter-malformed",
    "instrument-error",
    "cancel",
    "sensor-overrange",
)


class Bench(base.Bench):
    def __init__(self, plan, scenario):
        super().__init__(scenario)
        self.epoch = datetime.now(UTC)
        self.plan = plan
        self.rf = scenario == "initial-on"
        self.frequency = 1000000
        self.setting = "Initial state (synthetic)"
        self.voltage = plan["supply"]["restore_V"]
        self.current = plan["supply"]["restore_current_limit_A"]
        self.controls = None
        self.source = False  # meter POWER REF is always off, independent of RF

    def advance(self, seconds):
        self.now = round(self.now + seconds, 6)

    def sleep(self, seconds):
        if self.stage == "plateau" and self.scenario == "cancel" and self.reads == 4:
            raise KeyboardInterrupt("Synthetic between-read cancellation")
        self.advance(seconds)


class FakeBase:
    simulation = True

    def __init__(self, bench, role):
        self.bench, self.role = bench, role

    def tick(self, deadline):
        self.bench.advance(0.01)

    def identify(self, *, deadline):
        self.tick(deadline)
        value = {**self.bench.plan["assets"][self.role], "simulation": True}
        if self.role == "transmitter" and self.bench.scenario == "identity-mismatch":
            value["serial"] = "OTHER-SYNTHETIC-ASSET"
        return value


class FakeTransmitter(FakeBase):
    def __init__(self, bench):
        super().__init__(bench, "transmitter")

    def status(self, *, deadline):
        self.tick(deadline)
        return dict(
            rf_on=self.bench.rf, frequency_Hz=self.bench.frequency, power_setting=self.bench.setting
        )

    def configure(self, *, frequency_Hz, power_setting, deadline):
        self.tick(deadline)
        if self.bench.scenario == "late-reply":
            self.bench.advance(6)
        self.bench.frequency = (
            frequency_Hz + 1 if self.bench.scenario == "frequency-mismatch" else frequency_Hz
        )
        self.bench.setting = power_setting
        return True

    def set_rf(self, *, on, deadline):
        self.tick(deadline)
        if on and self.bench.scenario == "key-rejected":
            return False
        if not on and self.bench.scenario == "source-off-failure":
            raise c.DriverFailure("Synthetic failed source-off transfer")
        if on or self.bench.scenario != "source-still-on":
            self.bench.rf = on
        return True


class FakeSupply(FakeBase):
    def __init__(self, bench):
        super().__init__(bench, "supply")

    def status(self, *, deadline):
        self.tick(deadline)
        return dict(current_limit_A=self.bench.current, output_enabled=True)

    def set_current_limit(self, *, amperes, deadline):
        self.tick(deadline)
        self.bench.current = (
            "0.5"
            if self.bench.scenario == "current-mismatch"
            and self.bench.controls.order[-1] == "configure"
            else amperes
        )
        return True

    def set_voltage(self, *, volts, deadline):
        self.tick(deadline)
        restore = self.bench.controls.order[-1] == "restore"
        if restore and self.bench.scenario == "restore-failure":
            raise c.DriverFailure("Synthetic failed restoration transfer")
        self.bench.voltage = (
            str(D(volts) - D(".5"))
            if restore and self.bench.scenario == "restore-mismatch"
            else volts
        )
        return True


class FakeObserver(FakeBase):
    def __init__(self, bench):
        super().__init__(bench, "observer")

    def measure(self, *, deadline):
        self.tick(deadline)
        configure = self.bench.controls.order[-1] == "configure"
        if configure and self.bench.scenario == "observer-timeout":
            raise c.DriverFailure("Synthetic voltage-observer timeout")
        return dict(
            volts=None
            if configure and self.bench.scenario == "voltage-missing"
            else self.bench.voltage,
            location=self.bench.plan["supply"]["observation_location"],
        )


class Wire(base.Wire):
    metadata = {"transport": "DUT-CTRL-01 explicit fake", "hardware": "none", "simulation": True}

    def write(self, data, deadline):
        if data in (b"OC0", b"OC1"):
            raise AssertionError("External transmitter workflow must never control POWER REF")
        super().write(data, deadline)

    def read(self, deadline):
        b = self.bench
        if self.pending == b"*IDN?":
            self.pending = None
            raw = b"HEWLETT-PACKARD,437B,SYNTHETIC-DUT01,1.9\r\n"
        elif self.pending == b"TR2":
            self.pending = None
            b.reads += 1
            b.advance(0.02)
            if b.stage == "plateau" and b.reads == 5:
                if b.scenario == "meter-timeout":
                    b.event("read_error", reason="Synthetic timeout; not a native USB timeout")
                    raise OperationTimeout("Synthetic meter timeout")
                if b.scenario == "meter-malformed":
                    raw = b"MALFORMED\r\n"
                    b.event("read", raw_hex=raw.hex())
                    return raw
                if b.scenario == "instrument-error":
                    raw = b"+9.0031E+40\r\n"
                    b.event("read", raw_hex=raw.hex())
                    return raw
            power = D("4.8") if b.scenario == "low-output" else D("5")
            value = power / factor("30") if b.rf else D("-2e-8")
            if b.rf and b.stage == "plateau" and b.reads == 5 and b.scenario == "sensor-overrange":
                value = D(".2")
            mantissa, exponent = format(value, "+.4E").split("E")
            raw = (mantissa + "E" + f"{int(exponent):+03d}" + "\r\n").encode("ascii")
        else:
            return super().read(deadline)
        b.event("read", raw_hex=raw.hex())
        return raw
