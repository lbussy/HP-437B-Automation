"""Reusable bounded external-DUT control contracts and fake-only orchestration.

Acknowledgements, state readbacks, and voltage observations are distinct. Drivers
must honor the supplied absolute monotonic deadline; post-return checks cannot
interrupt an uncooperative driver. No physical driver is provided or admitted.
"""

import math
from contextlib import contextmanager
from decimal import Decimal as D
from typing import Protocol

from . import provenance as p
from . import reporting as r
from .power_setting import factor, text

PHASES = ("preflight", "configure", "activate", "verify", "deactivate", "restore")


class Transmitter(Protocol):
    simulation: bool

    def identify(self, *, deadline: float) -> dict: ...
    def status(self, *, deadline: float) -> dict: ...
    def configure(self, *, frequency_Hz: int, power_setting: str, deadline: float) -> bool: ...
    def set_rf(self, *, on: bool, deadline: float) -> bool: ...


class Supply(Protocol):
    simulation: bool

    def identify(self, *, deadline: float) -> dict: ...
    def status(self, *, deadline: float) -> dict: ...
    def set_current_limit(self, *, amperes: str, deadline: float) -> bool: ...
    def set_voltage(self, *, volts: str, deadline: float) -> bool: ...


class VoltageObserver(Protocol):
    simulation: bool

    def identify(self, *, deadline: float) -> dict: ...
    def measure(self, *, deadline: float) -> dict: ...


class ControlFailure(ValueError):
    """A failed control condition; no implicit retry is permitted."""


class DriverFailure(ControlFailure):
    """A failed/uncertain transfer (also used by saved-transcript replay)."""


class StageFailure(ControlFailure):
    def __init__(self, message, *, uncertain=False, interrupted=False):
        super().__init__(message)
        self.uncertain, self.interrupted = uncertain, interrupted


def default_plan():
    return dict(
        schema="hp437b.external-dut-plan.v1",
        dut_name="Fictional RF transmitter",
        assets={
            role: dict(asset_id="synthetic:dut01:" + role, model=model, serial=serial)
            for role, model, serial in (
                ("transmitter", "FAKE-TX", "SIM-TX-01"),
                ("supply", "FAKE-PSU", "SIM-PSU-01"),
                ("observer", "FAKE-VOLTMETER", "SIM-VM-01"),
            )
        },
        frequency_Hz=14000000,
        power_setting="Nominal output (declared)",
        signal_mode="Continuous carrier (synthetic)",
        measurement_plane="DUT_output",
        max_RF_W="10",
        sensor_limit_W="0.1",
        fixture=dict(
            asset_id="synthetic:dut01:fixture",
            input_limit_W="20",
            minimum_loss_dB="30",
            loss_dB="30",
            correction_source="Fictional fixture specification r1",
        ),
        supply=dict(
            minimum_V="10",
            maximum_V="14",
            condition_V="13",
            current_limit_A="2",
            restore_V="12",
            restore_current_limit_A="1.5",
            tolerance_V="0.1",
            observation_location="DUT DC input (synthetic)",
        ),
        timing=dict(operation_s=5, whole_run_s=120, max_RF_on_s=60),
    )


def validate_plan(plan):
    p._keys(
        plan,
        (
            "schema",
            "dut_name",
            "assets",
            "frequency_Hz",
            "power_setting",
            "signal_mode",
            "measurement_plane",
            "max_RF_W",
            "sensor_limit_W",
            "fixture",
            "supply",
            "timing",
        ),
    )
    p.require(plan["schema"] == "hp437b.external-dut-plan.v1", "Unsupported external-DUT plan")
    for key in ("dut_name", "power_setting", "signal_mode"):
        text(plan[key], 120)
    p.require(
        type(plan["frequency_Hz"]) is int and 100000 <= plan["frequency_Hz"] <= 4200000000,
        "Invalid fixed frequency",
    )
    p.require(
        plan["measurement_plane"] in ("DUT_output", "sensor_input"), "Invalid comparison plane"
    )
    p._keys(plan["assets"], ("transmitter", "supply", "observer"))
    ids = []
    for asset in plan["assets"].values():
        p._keys(asset, ("asset_id", "model", "serial"))
        for value in asset.values():
            text(value, 120)
        ids.append(asset["asset_id"])
    p.require(
        len(set(ids)) == 3 and not set(ids) & {"synthetic:dut01:meter", "synthetic:dut01:sensor"},
        "Control identities must be distinct from each other and meter/sensor",
    )
    fixture = plan["fixture"]
    p._keys(
        fixture, ("asset_id", "input_limit_W", "minimum_loss_dB", "loss_dB", "correction_source")
    )
    text(fixture["asset_id"])
    p.require(
        fixture["asset_id"] not in ids + ["synthetic:dut01:meter", "synthetic:dut01:sensor"],
        "Fixture identity overlaps control identity",
    )
    p.require(D(".000001") <= r.number(plan["max_RF_W"]) <= 10000, "Invalid declared RF bound")
    p.require(
        D(".000001") <= r.number(plan["sensor_limit_W"]) <= D(".1"),
        "Invalid synthetic sensor operating ceiling",
    )
    p.require(
        r.number(plan["max_RF_W"]) <= r.number(fixture["input_limit_W"]) <= 10000,
        "RF bound exceeds fixture input rating",
    )
    p.require(0 <= r.number(fixture["minimum_loss_dB"]) <= 100, "Invalid minimum path loss")
    p.require(
        D(plan["max_RF_W"]) / factor(fixture["minimum_loss_dB"]) <= D(plan["sensor_limit_W"]),
        "Worst-case RF exceeds sensor operating ceiling",
    )
    if fixture["loss_dB"] is None:
        p.require(
            fixture["correction_source"] is None, "Unknown correction must retain unknown source"
        )
    else:
        p.require(
            D(fixture["minimum_loss_dB"]) <= r.number(fixture["loss_dB"]) <= 100,
            "Correction conflicts with minimum loss bound",
        )
        text(fixture["correction_source"], 240)
    supply = plan["supply"]
    p._keys(
        supply,
        (
            "minimum_V",
            "maximum_V",
            "condition_V",
            "current_limit_A",
            "restore_V",
            "restore_current_limit_A",
            "tolerance_V",
            "observation_location",
        ),
    )
    low, high = r.number(supply["minimum_V"]), r.number(supply["maximum_V"])
    p.require(D(".1") <= low <= high <= 100, "Invalid supply envelope")
    for key in ("condition_V", "restore_V"):
        p.require(
            low <= r.number(supply[key]) <= high, "Requested/restoration voltage outside envelope"
        )
    for key in ("current_limit_A", "restore_current_limit_A"):
        p.require(D(".01") <= r.number(supply[key]) <= 100, "Invalid current-limit setting")
    p.require(0 <= r.number(supply["tolerance_V"]) <= 1, "Invalid voltage tolerance")
    text(supply["observation_location"], 120)
    p._keys(plan["timing"], ("operation_s", "whole_run_s", "max_RF_on_s"))
    for key, low, high in (
        ("operation_s", 1, 10),
        ("whole_run_s", 90, 300),
        ("max_RF_on_s", 55, 90),
    ):
        p.require(
            type(plan["timing"][key]) is int and low <= plan["timing"][key] <= high,
            "Invalid bounded timing profile",
        )
    return plan


class Controls:
    """Reusable guarded phases over explicit transmitter/supply/observer objects."""

    def __init__(
        self, plan, transmitter: Transmitter, supply: Supply, observer: VoltageObserver, *, clock
    ):
        validate_plan(plan)
        self.plan, self.clock = plan, clock
        self.devices = dict(transmitter=transmitter, supply=supply, observer=observer)
        p.require(
            all(getattr(device, "simulation", None) is True for device in self.devices.values()),
            "This control foundation currently admits explicit simulations only",
        )
        self.started = clock()
        p.require(
            type(self.started) in (int, float) and math.isfinite(self.started),
            "Invalid control monotonic clock",
        )
        self.last_clock = self.started
        self.events = []
        self.order = []
        self.phases = {name: dict(status="skipped", reason="Not reached") for name in PHASES}
        self.rf = "unknown"
        self.blocked = False
        self.adopted = False
        self.owned_rf = False
        self.on_since = None
        self.voltage = None
        self.current = None
        self.restored = False

    def freeze(self):
        self.blocked = True
        if self.owned_rf and self.rf != "off":
            self.rf = "unknown"

    def check_budget(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < self.last_clock:
            self.freeze()
            raise ControlFailure("Invalid/nonmonotonic control clock")
        self.last_clock = now
        if self.blocked:
            raise ControlFailure("Controls blocked after uncertainty; no retry")
        if self.clock() - self.started >= self.plan["timing"]["whole_run_s"] or (
            self.on_since is not None
            and self.clock() - self.on_since >= self.plan["timing"]["max_RF_on_s"]
        ):
            self.freeze()
            raise ControlFailure("Workflow/RF-on virtual budget exhausted")

    @contextmanager
    def phase(self, name):
        if name in self.order:
            raise ControlFailure("Control phase may be attempted only once")
        self.check_budget()
        self.order.append(name)
        item = self.phases[name] = dict(
            status="running", start_s=self.clock(), event_begin=len(self.events)
        )
        try:
            yield
            item["status"] = "completed"
        except BaseException as exc:
            item.update(
                status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                reason=str(exc),
            )
            raise
        finally:
            item.update(end_s=self.clock(), event_end=len(self.events))

    def _call(self, device, operation, **request):
        self.check_budget()
        if len(self.events) >= 48:
            self.freeze()
            raise ControlFailure("Control operation ceiling exhausted")
        start = self.clock()
        deadline = min(
            start + self.plan["timing"]["operation_s"],
            self.started + self.plan["timing"]["whole_run_s"],
        )
        if self.on_since is not None:
            deadline = min(deadline, self.on_since + self.plan["timing"]["max_RF_on_s"])
        item = dict(
            phase=self.order[-1],
            device=device,
            operation=operation,
            request=request,
            start_s=start,
            deadline_s=deadline,
        )
        try:
            reply = getattr(self.devices[device], operation)(deadline=deadline, **request)
            item.update(status="returned", reply=reply)
        except BaseException as exc:
            message = (
                str(exc) if isinstance(exc, DriverFailure) else type(exc).__name__ + ": " + str(exc)
            )
            item.update(status="error", error=message)
            self.freeze()
            if device == "transmitter":
                self.rf = "unknown"
            raise DriverFailure(message) from exc
        finally:
            item["end_s"] = self.clock()
            self.events.append(item)
        if not math.isfinite(self.clock()) or self.clock() > deadline or self.clock() < start:
            self.freeze()
            if device == "transmitter":
                self.rf = "unknown"
            raise ControlFailure("Late/nonmonotonic control reply; state unqualified")
        try:
            self.validate_reply(device, operation, reply)
        except (ValueError, TypeError, KeyError) as exc:
            self.freeze()
            if device == "transmitter":
                self.rf = "unknown"
            raise ControlFailure("Malformed control reply: " + str(exc)) from exc
        return reply

    @staticmethod
    def validate_reply(device, operation, reply):
        if operation == "identify":
            p._keys(reply, ("asset_id", "model", "serial", "simulation"))
            for key in ("asset_id", "model", "serial"):
                text(reply[key], 120)
            p.require(reply["simulation"] is True, "Non-synthetic identity refused")
        elif operation == "status" and device == "transmitter":
            p._keys(reply, ("rf_on", "frequency_Hz", "power_setting"))
            p.require(
                type(reply["rf_on"]) is bool
                and type(reply["frequency_Hz"]) is int
                and 0 <= reply["frequency_Hz"] <= 4200000000,
                "Invalid transmitter state types",
            )
            text(reply["power_setting"], 120)
        elif operation == "status":
            p._keys(reply, ("current_limit_A", "output_enabled"))
            p.require(
                type(reply["output_enabled"]) is bool
                and 0 < r.number(reply["current_limit_A"]) <= 100,
                "Invalid supply state types",
            )
        elif operation == "measure":
            p._keys(reply, ("volts", "location"))
            text(reply["location"], 120)
            if reply["volts"] is not None:
                p.require(0 <= r.number(reply["volts"]) <= 1000, "Invalid voltage readback")
        else:
            p.require(type(reply) is bool, "Invalid acknowledgement type")

    def _acknowledge(self, device, operation, **request):
        if self._call(device, operation, **request) is not True:
            self.freeze()
            if device == "transmitter":
                self.rf = "unknown"
            raise ControlFailure("Command acknowledgement missing/rejected")

    def _transmitter_state(self, expected, *, condition=False):
        value = self._call("transmitter", "status")
        p._keys(value, ("rf_on", "frequency_Hz", "power_setting"))
        p.require(
            type(value["rf_on"]) is bool
            and type(value["frequency_Hz"]) is int
            and isinstance(value["power_setting"], str),
            "Malformed transmitter state",
        )
        self.rf = "on" if value["rf_on"] else "off"
        if self.rf != expected:
            raise ControlFailure("RF state readback does not match requested state")
        if condition and (
            value["frequency_Hz"] != self.plan["frequency_Hz"]
            or value["power_setting"] != self.plan["power_setting"]
        ):
            raise ControlFailure("Declared frequency/setting readback mismatch")

    def _supply_state(self, expected):
        value = self._call("supply", "status")
        p._keys(value, ("current_limit_A", "output_enabled"))
        self.current = value["current_limit_A"]
        if value["output_enabled"] is not True or r.number(value["current_limit_A"]) != D(expected):
            self.freeze()
            raise ControlFailure("Supply output/current-limit readback mismatch")

    def _observe(self, expected):
        value = self._call("observer", "measure")
        p._keys(value, ("volts", "location"))
        self.voltage = value["volts"]
        supply = self.plan["supply"]
        if value["location"] != supply["observation_location"] or value["volts"] is None:
            raise ControlFailure("Voltage observation missing or wrong location")
        volts = r.number(value["volts"])
        if not D(supply["minimum_V"]) <= volts <= D(supply["maximum_V"]) or abs(
            volts - D(expected)
        ) > D(supply["tolerance_V"]):
            raise ControlFailure("Observed voltage outside requested tolerance/envelope")

    def preflight(self):
        with self.phase("preflight"):
            for role in ("transmitter", "supply", "observer"):
                reply = self._call(role, "identify")
                if reply != {**self.plan["assets"][role], "simulation": True}:
                    raise ControlFailure("Control identity mismatch: " + role)
            self._transmitter_state("off")
            self._supply_state(self.plan["supply"]["restore_current_limit_A"])
            self._observe(self.plan["supply"]["restore_V"])
            self.adopted = True

    def configure(self):
        with self.phase("configure"):
            if not self.adopted or self.rf != "off":
                raise ControlFailure("Condition changes require adopted source-off setup")
            supply = self.plan["supply"]
            self.restored = False
            self._acknowledge("supply", "set_current_limit", amperes=supply["current_limit_A"])
            self._supply_state(supply["current_limit_A"])
            self._acknowledge("supply", "set_voltage", volts=supply["condition_V"])
            self._observe(supply["condition_V"])
            self._acknowledge(
                "transmitter",
                "configure",
                frequency_Hz=self.plan["frequency_Hz"],
                power_setting=self.plan["power_setting"],
            )
            self._transmitter_state("off", condition=True)

    def activate(self):
        with self.phase("activate"):
            if self.phases["configure"]["status"] != "completed" or self.rf != "off":
                raise ControlFailure("Keying requires verified source-off conditions")
            self.owned_rf = True
            self.on_since = self.clock()
            self._acknowledge("transmitter", "set_rf", on=True)
            self._transmitter_state("on", condition=True)

    def verify(self):
        with self.phase("verify"):
            self._transmitter_state("on", condition=True)
            self._observe(self.plan["supply"]["condition_V"])

    def deactivate(self):
        with self.phase("deactivate"):
            if not self.owned_rf:
                raise ControlFailure("Will not unkey an unowned source")
            self._acknowledge("transmitter", "set_rf", on=False)
            self._transmitter_state("off")
            self.on_since = None

    def restore(self):
        with self.phase("restore"):
            if not self.adopted or self.rf != "off":
                raise ControlFailure("Restoration requires adopted setup and verified RF off")
            supply = self.plan["supply"]
            self.restored = False
            self._acknowledge(
                "supply", "set_current_limit", amperes=supply["restore_current_limit_A"]
            )
            self._supply_state(supply["restore_current_limit_A"])
            self._acknowledge("supply", "set_voltage", volts=supply["restore_V"])
            self._observe(supply["restore_V"])
            self.restored = True

    def summary(self):
        return dict(
            rf_state=self.rf,
            supply_restored=self.restored,
            blocked=self.blocked,
            adopted=self.adopted,
            owned_rf=self.owned_rf,
            observed_V=self.voltage,
            current_limit_ack_A=self.current,
        )


def execute(controls, capture_stage):
    """Reusable single-condition sequence; callback owns capture or saved-data loading."""
    status, error = "completed", None
    try:
        controls.preflight()
        capture_stage("baseline-before")
        controls.configure()
        controls.activate()
        capture_stage("settling")
        controls.verify()
        capture_stage("plateau")
    except (Exception, KeyboardInterrupt) as exc:
        status = (
            "interrupted"
            if isinstance(exc, KeyboardInterrupt) or getattr(exc, "interrupted", False)
            else "failed"
        )
        error = str(exc)
        if getattr(exc, "uncertain", False):
            controls.freeze()
    cleanup = []
    if controls.owned_rf and not controls.blocked and "deactivate" not in controls.order:
        try:
            controls.deactivate()
        except (Exception, KeyboardInterrupt) as exc:
            cleanup.append(str(exc))
    if (
        controls.adopted
        and controls.rf == "off"
        and not controls.blocked
        and "restore" not in controls.order
    ):
        try:
            controls.restore()
        except (Exception, KeyboardInterrupt) as exc:
            cleanup.append(str(exc))
    if cleanup:
        status = "failed"
    if status == "completed":
        try:
            capture_stage("baseline-after")
        except (Exception, KeyboardInterrupt) as exc:
            status = (
                "interrupted"
                if isinstance(exc, KeyboardInterrupt) or getattr(exc, "interrupted", False)
                else "failed"
            )
            error = str(exc)
            if getattr(exc, "uncertain", False):
                controls.freeze()
    return dict(status=status, error=error, cleanup_errors=cleanup)
