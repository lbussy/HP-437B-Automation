"""The authenticated, bench-only WsprryPi GPIO qualification owner boundary."""

import json
import os
import re
import secrets
import select
import subprocess
import time
from contextlib import ExitStack, contextmanager
from decimal import Decimal

from . import provenance as p
from . import reporting as r
from .sensor_correction import PROFILE, SENSOR_SERIAL, correction

HOST = "wspr1.local"
SSH_ALIAS = "wspr1"
CONTRACT = "wsprrypi.gpio-qualification-owner.v1"
TONE_MS = 50_000
OP_S = 3
# Round the observed 9.31 s cold request up to 10 s, reserve two more
# seconds for connection variance, and add the owner's 3 s matrix budget.
REVIEW_OP_S = 10 + 2 + 3
# SSH authentication can take 8.94 s on this bench. Establish each lane
# before run preparation, within the existing cold connection allowance.
MASTER_S = REVIEW_OP_S - 3
MAX_MESSAGE = 65_536
SSH_OPTIONS = (
    "/usr/bin/ssh",
    "-T",
    "-oBatchMode=yes",
    "-oStrictHostKeyChecking=yes",
    "-oClearAllForwardings=yes",
    "-oPermitLocalCommand=no",
    "-oConnectionAttempts=1",
    "-oConnectTimeout=2",
)
OWNER_COMMAND = (
    "/usr/bin/sudo",
    "-n",
    "--",
    "/usr/local/libexec/wsprrypi-gpio-qualification-owner",
)
SSH = (*SSH_OPTIONS, "-oControlMaster=no", "-oControlPath=none", SSH_ALIAS, *OWNER_COMMAND)
CAPABILITIES = [
    "read-only-native-admission",
    "exclusive-run-and-bank-lease",
    "isolated-drive-instances",
    "cutoff-before-output-enable",
    "independent-identified-stop",
    "durable-local-recovery",
]
CURRENT_CAPABILITIES = [*CAPABILITIES, "identified-reservation"]
MUX = {4: "ALT0", 20: "ALT5"}
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


def route(gpio):
    p.require(type(gpio) is int and gpio in MUX, "Select GPIO4/ALT0 or GPIO20/ALT5")
    return {"profile": "bcm2835", "gpio": gpio, "mux": MUX[gpio]}


def target(value, gpio=None):
    expected = TARGET if gpio is None else {**TARGET, **route(gpio)}
    identities = ("device", "boot", "revision", "executable", "station", "capabilities")
    clock = (
        ()
        if gpio is None
        else ("clock_policy", "ppm_millionths", "correction", "correction_provenance")
    )
    p._keys(value, (*expected, *identities, *clock))
    p.require(
        r.encoded({key: value[key] for key in expected}) == r.encoded(expected)
        and value["capabilities"] == (CAPABILITIES if gpio is None else CURRENT_CAPABILITIES),
        "Expected the reviewed BCM2835 route and the inactive, disabled normal unit",
    )
    for field, pattern in (
        ("device", HEX),
        ("boot", HEX),
        ("revision", REV),
        ("executable", HASH),
        ("station", HASH),
        *((("correction", HASH),) if gpio is not None else ()),
    ):
        p.require(
            isinstance(value[field], str) and pattern.fullmatch(value[field]),
            f"Invalid WsprryPi {field} identity",
        )
    if gpio is not None:
        p.require(
            value["clock_policy"] in ("uncalibrated", "selected")
            and type(value["ppm_millionths"]) is int
            and abs(value["ppm_millionths"]) <= 200_000_000
            and (value["clock_policy"] != "uncalibrated" or value["ppm_millionths"] == 0)
            and isinstance(value["correction_provenance"], str)
            and 0 < len(value["correction_provenance"]) <= 200,
            "Invalid reviewed BCM2835 correction",
        )
    return value


def admission(value, point, *, permit_refusal=False, source=None):
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
    if source is not None:
        p.require(
            value["policy"] == source["clock_policy"]
            and value["ppm_millionths"] == source["ppm_millionths"],
            "Native admission changed the reviewed clock selection",
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
        and (
            TONE_MS <= value["deadline_ms"] <= 60_000
            if source is None
            else value["deadline_ms"] == TONE_MS
        )
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


def native_off(value, *, current=False):
    return all(
        value[key] is expected if type(expected) is bool else value[key] == expected
        for key, expected in (
            ("gpclk_enabled", False),
            ("gpclk_busy", False),
            ("gpio_input", True),
            ("mux", "INPUT"),
            ("owned", False),
            *(
                (("other_gpio_input", True), ("dma_idle", True), ("pwm_idle", True))
                if current
                else ()
            ),
        )
    )


class RuntimeLane:
    """One framed request at a time over one authenticated SSH process."""

    def __init__(self, process, clock):
        self.process = process
        self.clock = clock
        self.buffer = bytearray()
        os.set_blocking(self.process.stdin.fileno(), False)
        os.set_blocking(self.process.stdout.fileno(), False)

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait(timeout=2)
        self.process.stdin.close()
        self.process.stdout.close()

    def remaining(self, end):
        remaining = (end - self.clock()) / 10**9
        if remaining <= 0:
            raise TimeoutError("WsprryPi runtime stream deadline expired")
        return remaining

    def read(self, end):
        descriptor = self.process.stdout.fileno()
        while b"\n" not in self.buffer:
            if not select.select([descriptor], [], [], self.remaining(end))[0]:
                raise TimeoutError("WsprryPi runtime stream did not reply")
            data = os.read(descriptor, 8192)
            if not data:
                raise OSError("WsprryPi runtime stream disconnected")
            self.buffer.extend(data)
            p.require(len(self.buffer) <= MAX_MESSAGE + 1, "Oversized runtime reply")
        p.require(
            self.buffer.endswith(b"\n") and self.buffer.count(b"\n") == 1,
            "Unexpected extra runtime data",
        )
        line = bytes(self.buffer[:-1])
        self.buffer.clear()
        return line

    def exchange(self, packet, end):
        descriptor = self.process.stdin.fileno()
        outgoing = memoryview(packet + b"\n")
        try:
            while outgoing:
                if not select.select([], [descriptor], [], self.remaining(end))[1]:
                    raise TimeoutError("WsprryPi runtime request did not write")
                outgoing = outgoing[os.write(descriptor, outgoing) :]
            return self.read(end)
        except BaseException:
            if self.process.poll() is None:
                self.process.kill()
            raise


class Owner:
    """Use separately authenticated runtime connections for control and Stop."""

    def __init__(self, *, command=subprocess.run, clock=time.monotonic_ns):
        self.command, self.clock = command, clock
        self.lanes = {}

    @contextmanager
    def runtime(self, deadline):
        if self.command is not subprocess.run:
            # An injected command stands in for SSH in RF-free tests.
            yield
            return
        p.require(not self.lanes, "WsprryPi runtime connections already open")
        with ExitStack() as stack:
            lanes = {}
            for name in ("control", "stop"):
                end = min(deadline, self.clock() + MASTER_S * 10**9)
                p.require(self.clock() < end, "No time left to authenticate runtime connection")
                process = subprocess.Popen(
                    (
                        *SSH_OPTIONS,
                        "-oControlMaster=no",
                        "-oControlPath=none",
                        SSH_ALIAS,
                        *OWNER_COMMAND,
                        "--runtime-stream",
                    ),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                lane = RuntimeLane(process, self.clock)
                stack.callback(lane.close)
                ready = lane.read(end)
                p.require(
                    ready == (CONTRACT + " ready").encode() and self.clock() < end,
                    f"WsprryPi {name} connection was late or did not negotiate",
                )
                lanes[name] = lane
            self.lanes = lanes
            try:
                yield
            finally:
                self.lanes = {}

    def _runtime_lane(self, operation, independent):
        if not self.lanes or operation == "review_matrix":
            return None
        return self.lanes["stop" if independent or operation == "stop" else "control"]

    def call(self, operation, fields, deadline, *, independent=False):
        request = {
            "contract": CONTRACT,
            "operation": operation,
            "call": secrets.token_hex(16),
            **fields,
        }
        lane = self._runtime_lane(operation, independent)
        packet = (
            json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            if lane
            else r.encoded(request)
        )
        p.require(len(packet) <= MAX_MESSAGE, "Qualification request exceeds the message limit")
        now = self.clock()
        budget_s = REVIEW_OP_S if operation == "review_matrix" else OP_S
        operation_deadline = min(deadline, now + budget_s * 10**9)
        remaining = (operation_deadline - now) / 10**9
        if remaining <= 0:
            raise TimeoutError("WsprryPi owner deadline expired")
        if lane:
            payload = lane.exchange(packet, operation_deadline)
        else:
            try:
                reply = self.command(
                    SSH,
                    input=packet,
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
            payload = reply.stdout
        p.require(self.clock() < operation_deadline, "WsprryPi owner replied after its deadline")
        p.require(
            0 < len(payload) <= MAX_MESSAGE + 1,
            "Qualification response exceeds the message limit or is empty",
        )
        envelope = p._json(payload)
        p._keys(envelope, ("contract", "operation", "call", "request_sha256", "receipt"))
        p.require(
            envelope["contract"] == CONTRACT
            and envelope["operation"] == operation
            and envelope["call"] == request["call"]
            and envelope["request_sha256"] == r.digest(packet)
            and isinstance(envelope["receipt"], dict),
            "Missing the bench-specific WsprryPi owner contract",
        )
        receipt = envelope["receipt"]
        if set(receipt) == {"phase", "reason"}:
            p.require(
                receipt["phase"] in ("refused", "unresolved")
                and isinstance(receipt["reason"], str)
                and 0 < len(receipt["reason"]) <= 240,
                "Malformed qualification refusal",
            )
            raise p.ProvenanceError(f"WsprryPi owner {operation}: {receipt['reason']}")
        return receipt
