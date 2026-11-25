"""The authenticated, bench-only WsprryPi GPIO20 owner boundary."""

import re
import subprocess
import time
from decimal import Decimal

from . import provenance as p
from . import reporting as r
from .sensor_correction import PROFILE, SENSOR_SERIAL, correction

HOST = "wspr1.local"
CONTRACT = "wsprrypi.pi1-gpio20-owner.v1"
TONE_MS = 50_000
OP_S = 3
SSH = (
    "/usr/bin/ssh",
    "-T",
    "-oBatchMode=yes",
    "-oStrictHostKeyChecking=yes",
    "-oControlMaster=no",
    "-oControlPath=none",
    "-oClearAllForwardings=yes",
    "-oPermitLocalCommand=no",
    "-oConnectionAttempts=1",
    "-oConnectTimeout=2",
    HOST,
    "/usr/local/libexec/wsprrypi-pi1-gpio20-owner",
)
CAPABILITIES = [
    "read-only-native-admission",
    "exclusive-run-and-bank-lease",
    "isolated-drive-instances",
    "cutoff-before-output-enable",
    "independent-identified-stop",
    "durable-local-recovery",
]
TARGET = {
    "host": HOST,
    "model": "Raspberry Pi Model A+",
    "backend": "bcm2835",
    "gpio": 20,
    "clock": "GPCLK0",
    "service_active": "inactive",
    "service_enabled": "disabled",
    "service_pid": 0,
}
HEX = re.compile(r"[0-9a-f]{32}")
REV = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")


def target(value):
    p._keys(value, (*TARGET, "device", "boot", "revision", "executable", "station", "capabilities"))
    p.require(
        r.encoded({key: value[key] for key in TARGET}) == r.encoded(TARGET)
        and value["capabilities"] == CAPABILITIES,
        "Expected the qualified BCM2835 GPIO20 owner and the inactive, disabled normal unit",
    )
    for field, pattern in (
        ("device", HEX),
        ("boot", HEX),
        ("revision", REV),
        ("executable", HASH),
        ("station", HASH),
    ):
        p.require(
            isinstance(value[field], str) and pattern.fullmatch(value[field]),
            f"Invalid WsprryPi {field} identity",
        )
    return value


def admission(value, point, *, permit_refusal=False):
    p._keys(
        value,
        (
            "carrier_hz",
            "drive_code",
            "ppm_millionths",
            "policy",
            "lower_nhz",
            "upper_nhz",
            "deadline_ms",
            "plan",
            "refusal",
        ),
    )
    p.require(
        type(value["carrier_hz"]) is int
        and value["carrier_hz"] == point.carrier_hz
        and type(value["drive_code"]) is int
        and value["drive_code"] == point.drive_ma // 2 - 1
        and type(value["ppm_millionths"]) is int
        and abs(value["ppm_millionths"]) <= 200_000_000
        and value["policy"] in ("uncalibrated", "selected")
        and (value["policy"] != "uncalibrated" or value["ppm_millionths"] == 0),
        "Owner changed the requested carrier, drive, or clock selection",
    )
    if value["refusal"] is not None:
        p.require(
            permit_refusal
            and isinstance(value["refusal"], str)
            and 0 < len(value["refusal"]) <= 250
            and all(
                value[key] is None for key in ("lower_nhz", "upper_nhz", "deadline_ms", "plan")
            ),
            "Owner refused the native point",
        )
        return value
    requested = point.carrier_hz * 10**9
    lo, hi = value["lower_nhz"], value["upper_nhz"]
    p.require(
        type(lo) is int
        and type(hi) is int
        and requested - 10**9 <= lo <= hi <= requested + 10**9
        and type(value["deadline_ms"]) is int
        and TONE_MS <= value["deadline_ms"] <= 60_000
        and isinstance(value["plan"], str)
        and HASH.fullmatch(value["plan"]),
        "Invalid native plan, realization tolerance, or cutoff",
    )
    nominal = Decimal(
        correction(PROFILE, SENSOR_SERIAL, point.carrier_hz)["commanded_factor_percent"]
    )
    # Both outer whole-Hz values and any interior certificate knots cover the
    # extrema of the piecewise-linear correction over the admitted interval.
    from .sensor_correction import TABLE

    frequencies = (lo // 10**9, -(-hi // 10**9))
    frequencies += tuple(hz for hz, _ in TABLE if lo <= hz * 10**9 <= hi)
    for hz in frequencies:
        applied = correction(PROFILE, SENSOR_SERIAL, hz)["commanded_factor_percent"]
        p.require(Decimal(applied) == nominal, "Owner realization crosses a CAL FAC step")
    return value


def bank(value):
    p._keys(value, ("drive", "hysteresis", "slew"))
    p.require(
        type(value["drive"]) is int
        and 0 <= value["drive"] <= 7
        and type(value["hysteresis"]) is bool
        and type(value["slew"]) is bool,
        "Invalid BCM2835 GPIO0–27 pad readback",
    )
    return value


def native_off(value):
    return all(
        value[key] is expected if type(expected) is bool else value[key] == expected
        for key, expected in (
            ("gpclk_enabled", False),
            ("gpclk_busy", False),
            ("gpio_input", True),
            ("mux", "INPUT"),
            ("owned", False),
        )
    )


class Owner:
    """One bounded SSH exec per request, with no multiplexing or legacy fallback."""

    def __init__(self, *, command=subprocess.run, clock=time.monotonic_ns):
        self.command, self.clock = command, clock

    def call(self, operation, fields, deadline):
        request = {"contract": CONTRACT, "operation": operation, **fields}
        remaining = min(OP_S, (deadline - self.clock()) / 10**9)
        if remaining <= 0:
            raise TimeoutError("WsprryPi owner deadline expired")
        try:
            reply = self.command(
                SSH,
                input=r.encoded(request),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=remaining,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"WsprryPi owner {operation} timed out") from exc
        if reply.returncode:
            raise OSError(
                f"WsprryPi owner {operation} unavailable or refused (SSH {reply.returncode})"
            )
        p.require(self.clock() < deadline, "WsprryPi owner replied after its deadline")
        envelope = p._json(reply.stdout)
        p._keys(envelope, ("contract", "operation", "request_sha256", "receipt"))
        p.require(
            envelope["contract"] == CONTRACT
            and envelope["operation"] == operation
            and envelope["request_sha256"] == r.digest(r.encoded(request))
            and isinstance(envelope["receipt"], dict),
            "Missing the bench-specific WsprryPi owner contract",
        )
        return envelope["receipt"]
