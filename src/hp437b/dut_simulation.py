"""Explicit fake external controls and fake GPIB meter; no discovery or I/O."""

from dataclasses import asdict, dataclass
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
    "setting-mismatch",
    "frequency-unverified",
    "supply-control-failure",
    "restore-unverified",
)


@dataclass
class Hardware:
    rf: bool
    frequency: int
    setting: str
    voltage: str
    current: str
    meter_factor_percent: str = "100"

    def snapshot(self):
        return asdict(self)


def default_model():
    return dict(
        source_W="5",
        loss_dB="30",
        response_percent="100",
        sensor_factor_percent="100",
        factor_applied_in="meter",
        factor_readback_percent="100",
        condition_observed_V=None,
        missing_voltage=False,
    )


def validate_model(model, plan):
    c.p._keys(
        model,
        (
            "source_W",
            "loss_dB",
            "response_percent",
            "sensor_factor_percent",
            "factor_applied_in",
            "factor_readback_percent",
            "condition_observed_V",
            "missing_voltage",
        ),
    )
    power = c.r.number(model["source_W"])
    c.p.require(
        power == 0 or D("1e-20") <= power <= D(plan["max_RF_W"]),
        "Fake RF model exceeds declared source bound",
    )
    loss = c.r.number(model["loss_dB"])
    c.p.require(
        D(plan["fixture"]["minimum_loss_dB"]) <= loss <= 100,
        "Fake loss conflicts with minimum attenuation",
    )
    for key in ("response_percent", "factor_readback_percent"):
        c.p.require(1 <= c.r.number(model[key]) <= 150, "Invalid model factor")
    c.p.require(
        model["factor_applied_in"] in ("analysis", "meter"), "Invalid factor application location"
    )
    if model["sensor_factor_percent"] is not None:
        c.p.require(
            1 <= c.r.number(model["sensor_factor_percent"]) <= 150, "Invalid supplied sensor factor"
        )
    c.p.require(
        model["factor_applied_in"] != "meter" or model["sensor_factor_percent"] is not None,
        "Unknown meter-applied factor",
    )
    if model["condition_observed_V"] is not None:
        c.p.require(
            0 <= c.r.number(model["condition_observed_V"]) <= 1000, "Invalid model voltage readback"
        )
    c.p.require(type(model["missing_voltage"]) is bool, "Invalid voltage availability flag")
    incident = power / factor(model["loss_dB"])
    indication = incident * D(model["response_percent"]) / D(model["factor_readback_percent"])
    c.p.require(
        incident <= D(plan["sensor_limit_W"]) and indication <= D(plan["sensor_limit_W"]),
        "Fake sensor input/indication exceeds ceiling",
    )
    return model


class Bench(base.Bench):
    def __init__(self, plan, scenario, *, model=None, hardware=None, epoch=None):
        super().__init__(scenario)
        self.epoch = epoch if epoch is not None else datetime.now(UTC)
        self.plan = plan
        self.model = default_model() if model is None else validate_model(model, plan)
        self.hardware = (
            hardware
            if hardware is not None
            else Hardware(
                scenario == "initial-on",
                1000000,
                "Initial state (synthetic)",
                plan["supply"]["restore_V"],
                plan["supply"]["restore_current_limit_A"],
            )
        )
        self.controls = None
        self.source = False  # meter POWER REF is always off, independent of RF

    rf = property(
        lambda self: self.hardware.rf, lambda self, value: setattr(self.hardware, "rf", value)
    )
    frequency = property(
        lambda self: self.hardware.frequency,
        lambda self, value: setattr(self.hardware, "frequency", value),
    )
    setting = property(
        lambda self: self.hardware.setting,
        lambda self, value: setattr(self.hardware, "setting", value),
    )
    voltage = property(
        lambda self: self.hardware.voltage,
        lambda self, value: setattr(self.hardware, "voltage", value),
    )
    current = property(
        lambda self: self.hardware.current,
        lambda self, value: setattr(self.hardware, "current", value),
    )

    def prepare_meter(self):
        c.p.require(
            self.controls.rf == "off" and self.rf is False,
            "Factor preparation requires freshly verified RF off",
        )
        expected = (
            self.model["sensor_factor_percent"]
            if self.model["factor_applied_in"] == "meter"
            else "100"
        )
        self.hardware.meter_factor_percent = self.model["factor_readback_percent"]
        self.advance(0.01)
        return dict(expected_percent=expected, observed_percent=self.hardware.meter_factor_percent)

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
            rf_on=self.bench.rf,
            frequency_Hz=None
            if self.bench.scenario == "frequency-unverified"
            and self.bench.controls.order[-1] == "configure"
            else self.bench.frequency,
            power_setting=self.bench.setting,
        )

    def configure(self, *, frequency_Hz, power_setting, deadline):
        self.tick(deadline)
        if self.bench.scenario == "late-reply":
            self.bench.advance(6)
        self.bench.frequency = (
            frequency_Hz + 1 if self.bench.scenario == "frequency-mismatch" else frequency_Hz
        )
        self.bench.setting = (
            "Wrong setting" if self.bench.scenario == "setting-mismatch" else power_setting
        )
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
            ("0.5" if D(amperes) != D("0.5") else "0.25")
            if self.bench.scenario == "current-mismatch"
            and self.bench.controls.order[-1] == "configure"
            else amperes
        )
        return True

    def set_voltage(self, *, volts, deadline):
        self.tick(deadline)
        restore = self.bench.controls.order[-1] == "restore"
        if not restore and self.bench.scenario == "supply-control-failure":
            raise c.DriverFailure("Synthetic supply write failure")
        if restore and self.bench.scenario == "restore-failure":
            raise c.DriverFailure("Synthetic failed restoration transfer")
        self.bench.voltage = (
            str(D(volts) - D(".5"))
            if restore and self.bench.scenario == "restore-mismatch"
            else (
                self.bench.model["condition_observed_V"]
                if not restore and self.bench.model["condition_observed_V"] is not None
                else volts
            )
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
            if (
                configure
                and (
                    self.bench.scenario == "voltage-missing" or self.bench.model["missing_voltage"]
                )
            )
            or (
                self.bench.controls.order[-1] == "restore"
                and self.bench.scenario == "restore-unverified"
            )
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
            power = D(b.model["source_W"]) * (D(".96") if b.scenario == "low-output" else D(1))
            value = (
                power
                / factor(b.model["loss_dB"])
                * D(b.model["response_percent"])
                / D(b.hardware.meter_factor_percent)
                if b.rf
                else D("-2e-8")
            )
            if b.rf and b.stage == "plateau" and b.reads == 5 and b.scenario == "sensor-overrange":
                value = D(".2")
            mantissa, exponent = format(value, "+.4E").split("E")
            raw = (mantissa + "E" + f"{int(exponent):+03d}" + "\r\n").encode("ascii")
        else:
            return super().read(deadline)
        b.event("read", raw_hex=raw.hex())
        return raw
