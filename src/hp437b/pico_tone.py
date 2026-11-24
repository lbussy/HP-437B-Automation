"""Authenticated native Pico Test Tone through an existing UMP1 USB host."""

import json
import re
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import provenance as p
from .live_sweep_review import Admission, Target
from .live_sweep_window import Job, Observation

CONTROL = "/api/control/v1/"
TONE = CONTROL + "test-tone/"
CONTRACT = "Wsprry-Control/1"
DRIVES = (2, 4, 8, 12)

# The USB host runs the original owner's already-installed UMP1 implementation.
# The helper is sent over stdin/argv, so nothing is installed on the USB host.
_USB_CALL = r"""
import hashlib, importlib.util, json, signal, sys
from pathlib import Path
path, digest, serial, device = sys.argv[1:]
payload = json.load(sys.stdin)
if payload.get('short_status'):
    # An SSH client timeout alone can leave the remote process holding the USB
    # lock. Bound read-only RF status on the USB host as well.
    def status_timeout(*_):
        raise TimeoutError('Pico USB tone status deadline expired')

    signal.signal(signal.SIGALRM, status_timeout)
    signal.setitimer(signal.ITIMER_REAL, 2.0)
path = Path(path)
if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
    raise RuntimeError('USB helper digest changed')
spec = importlib.util.spec_from_file_location('owner_usb', path)
installer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)
with installer.device_lock(serial):
    with installer.Management(installer.selected(serial, 'application')) as wire:
        target = wire.hello['target']
        if target['device_id'] != device or payload['target'] not in (None, target):
            raise RuntimeError('USB device/boot binding mismatch')
        replies = []
        for row in payload['requests']:
            answer = wire.exchange(row)
            if answer['delivery_required'] is not True:
                raise RuntimeError('Missing UMP delivery acknowledgment')
            ack = wire.exchange(dict(operation='ack'), repeat=True)
            if (ack['status'] != 200 or ack['delivery_required'] is not False or
                json.loads(ack['body']) != {'acknowledged': True}):
                raise RuntimeError('UMP response acknowledgment failed')
            replies.append([answer['status'], answer['etag'], json.loads(answer['body'])])
        print(json.dumps([target, replies], separators=(',', ':')))
"""


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _decimal_string(value):
    p.require(
        isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,19}", value),
        "Expected an exact unsigned decimal string from Pico",
    )
    parsed = int(value)
    p.require(parsed < 2**64, "Pico integer exceeds its wire range")
    return parsed


@dataclass(frozen=True)
class UsbHost:
    host: str
    installer_path: str
    installer_sha256: str
    serial: str
    device_id: str

    @classmethod
    def from_file(cls, path):
        with Path(path).open("rb") as config:
            body = config.read(4097)
        p.require(len(body) <= 4096, "Pico USB configuration exceeds 4 KiB")
        fields = p._json(body)
        p._keys(fields, ("host", "installer_path", "installer_sha256", "serial", "device_id"))
        return cls(**fields)

    def __post_init__(self):
        p.require(
            isinstance(self.host, str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", self.host),
            "Select an existing local SSH host alias",
        )
        p.require(
            isinstance(self.installer_path, str)
            and self.installer_path.startswith("/")
            and self.installer_path.endswith("/usb_installer.py")
            and re.fullmatch(r"[A-Za-z0-9_./-]+", self.installer_path)
            and ".." not in self.installer_path.split("/")
            and isinstance(self.installer_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", self.installer_sha256),
            "Pin the existing owner USB helper",
        )
        p.require(
            isinstance(self.serial, str)
            and re.fullmatch(r"[0-9A-F]{16}", self.serial)
            and _id(self.device_id),
            "Configure an exact Pico USB serial and device ID",
        )


def request(method, path, body=None, revision=""):
    return dict(
        operation="request",
        method=method,
        path=path,
        body="" if body is None else json.dumps(body, separators=(",", ":")),
        if_match=revision,
    )


class UsbLink:
    def __init__(self, config):
        self.config = config
        self._lock = threading.Lock()

    def exchange(self, requests, deadline_ns, *, target=None):
        config = self.config
        read_only = all(
            row["method"] == "GET" or (row["method"] == "POST" and row["path"] == TONE + "review")
            for row in requests
        )
        remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
        if remaining <= 0 or not self._lock.acquire(timeout=remaining):
            raise TimeoutError("Pico USB access deadline expired")
        try:
            remote = shlex.join(
                [
                    "python3",
                    "-B",
                    "-c",
                    _USB_CALL,
                    config.installer_path,
                    config.installer_sha256,
                    config.serial,
                    config.device_id,
                ]
            )
            command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=4", config.host, remote]
            remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
            if remaining <= 0:
                raise TimeoutError("Pico USB access deadline expired")
            short_status = (
                remaining <= 3
                and len(requests) == 1
                and requests[0]["method"] == "GET"
                and requests[0]["path"].startswith(TONE + "status?")
            )
            payload = json.dumps(
                dict(
                    target=target,
                    requests=requests,
                    **({"short_status": True} if short_status else {}),
                )
            ).encode()
            result = subprocess.run(
                command, input=payload, capture_output=True, timeout=remaining, check=False
            )
            if (
                result.returncode
                and read_only
                and time.monotonic_ns() + 1_000_000_000 < deadline_ns
            ):
                time.sleep(0.25)
                remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
                if remaining > 0:
                    result = subprocess.run(
                        command, input=payload, capture_output=True, timeout=remaining, check=False
                    )
            if result.returncode != 0:
                route = "SSH transport" if result.returncode == 255 else "USB bridge"
                raise ValueError(f"Pico {route} request failed or its reply is unknown")
            identity, replies = p._json(result.stdout)
            p.require(
                identity.get("device_id") == config.device_id
                and identity.get("scope") == "member"
                and _id(identity.get("boot_id"))
                and (target is None or target == identity)
                and len(replies) == len(requests),
                "USB reply target or count mismatch",
            )
            return identity, replies
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("Pico USB deadline expired; request outcome may be unknown") from exc
        finally:
            self._lock.release()


@dataclass(frozen=True)
class Tone:
    job: Job
    request_id: str
    revision: str
    carrier_hz: int
    drive_ma: int
    duration_ms: int
    hard_end_ns: int


def tone_descriptor(caps, engine, drives, minimum_ms):
    """Check the advertised engine, routes, and duration limits."""
    feature = caps.get("test_tone", {})
    p.require(
        feature.get("available") is True
        and feature.get("schema") == "test-tone"
        and feature.get("carrier_units") == "Hz"
        and feature.get("carrier_reference") == "absolute"
        and feature.get("duration_units") == "ms"
        and all(feature.get(op) == TONE + op for op in ("review", "start", "status", "stop")),
        "Pico Test Tone capability is unavailable",
    )
    engines = feature.get("engines")
    if engines is None and engine == "pio-dma-gp2":
        p.require(
            feature.get("engine", engine) == engine and feature.get("drive_ma") == list(drives),
            "Pico did not advertise the direct GP2 Test Tone",
        )
        return False
    p.require(
        isinstance(engines, dict)
        and feature.get("active_engine") == engine
        and isinstance(engines.get(engine), dict)
        and engines[engine].get("drive_ma") == list(drives)
        and type(feature.get("minimum_duration_ms")) is int
        and feature["minimum_duration_ms"] == minimum_ms
        and type(feature.get("maximum_duration_ms")) is int
        and minimum_ms <= feature["maximum_duration_ms"] <= 120_000,
        "Pico did not advertise the requested Test Tone engine and bounds",
    )
    return True


class PicoTone:
    engine = "pio-dma-gp2"
    drives = DRIVES
    minimum_ms = 1

    def __init__(self, link, target_id):
        self.link, self.target_id = link, target_id
        self.tone = None
        self.terminal_receipt = None
        self.engine_assertion = False
        self._pending_request = None
        self._request_ids = set()

    def _binding(self, target):
        return dict(scope="member", device_id=target.device_id, boot_id=target.boot_id)

    def snapshot(self, target_id, *, deadline_ns=None):
        p.require(target_id == self.target_id, "Wrong configured Pico target")
        identity, replies = self.link.exchange(
            [
                request("GET", CONTROL + names)
                for names in ("capabilities", "status", "message-schedule", "gpio-drive")
            ],
            deadline_ns or time.monotonic_ns() + 12_000_000_000,
        )
        for index, (status, _, body) in enumerate(replies):
            p.require(
                status == 200
                and body.get("contract") == CONTRACT
                and (index < 2 or body.get("target") == identity),
                "Pico capability or state reply is unavailable",
            )
        caps, radio, messages, gpio = (row[2] for row in replies)
        self.engine_assertion = tone_descriptor(caps, self.engine, self.drives, self.minimum_ms)
        p.require(
            gpio.get("execution_engine") == self.engine
            and gpio.get("rf_gp") == 2
            and gpio.get("storage_healthy") is True
            and gpio.get("application_error") is None,
            "Pico did not advertise the required direct GP2 Test Tone",
        )
        job = radio["job"]
        wspr = radio["standalone"]
        saved_message = messages["saved"]
        return Target(
            target_id=target_id,
            device_id=identity["device_id"],
            boot_id=identity["boot_id"],
            revision=replies[-1][1],
            owner="pico",
            output="GP2",
            profile="pico-gpio",
            saved_drive_ma=gpio["saved"],
            active_drive_ma=gpio["boot_active"],
            idle=job["state"] in ("empty", "complete", "aborted", "missed")
            and job["owner_id"] is None,
            output_inactive=job["output_active"] is False,
            restart_pending=gpio["pending_restart"],
            schedules_inhibited=wspr.get("enabled") is False
            and (saved_message is None or saved_message.get("enabled") is False),
        )

    def change_drive(self, target, drive, deadline_ns):
        """Save a scoped drive value, then verify an explicit restart on the same member."""
        p.require(
            drive in DRIVES
            and target.saved_drive_ma == target.active_drive_ma
            and not target.restart_pending
            and target.idle
            and target.output_inactive
            and target.schedules_inhibited
            and drive != target.active_drive_ma,
            "Pico drive transition requires a known idle boot and a different supported drive",
        )
        binding = self._binding(target)
        path = CONTROL + "gpio-drive"
        _, ((code, revision, saved),) = self.link.exchange(
            [
                request(
                    "PUT",
                    path,
                    dict(
                        contract=CONTRACT, schema="gpio-drive", target=binding, gpio_drive_ma=drive
                    ),
                    target.revision,
                )
            ],
            min(deadline_ns, time.monotonic_ns() + 12_000_000_000),
            target=binding,
        )
        p.require(
            code == 200
            and saved.get("contract") == CONTRACT
            and saved.get("schema") == "gpio-drive"
            and saved.get("target") == binding
            and saved.get("saved") == drive
            and saved.get("boot_active") == target.active_drive_ma
            and saved.get("pending_restart") is True
            and bool(revision),
            "Pico drive save is unconfirmed; no restart was issued",
        )
        try:
            _, ((code, _, reply),) = self.link.exchange(
                [request("POST", CONTROL + "restart", dict(contract=CONTRACT), revision)],
                min(deadline_ns, time.monotonic_ns() + 12_000_000_000),
                target=binding,
            )
        except (OSError, ValueError):
            # Disconnect after a delivered restart is possible. Resolve by reading the boot.
            pass
        else:
            p.require(
                code == 202 and reply.get("restart_requested") is True,
                "Pico refused the explicit restart",
            )
        while time.monotonic_ns() < deadline_ns:
            try:
                new = self.snapshot(
                    target.target_id,
                    deadline_ns=min(deadline_ns, time.monotonic_ns() + 8_000_000_000),
                )
            except (OSError, ValueError):
                time.sleep(0.4)
                continue
            if new.boot_id != target.boot_id:
                p.require(
                    new.device_id == target.device_id
                    and new.output == target.output
                    and new.profile == target.profile
                    and new.active_drive_ma == new.saved_drive_ma == drive
                    and new.idle
                    and new.output_inactive
                    and new.schedules_inhibited
                    and not new.restart_pending,
                    "Pico post-restart drive or RF state did not verify",
                )
                return new
            time.sleep(0.4)
        raise TimeoutError("Pico did not verify a new boot and requested drive before the deadline")

    def _call(self, method, operation, target, deadline_ns, *, body=None, revision=""):
        binding = self._binding(target)
        if body is not None:
            body = {**body, "target": binding, "contract": CONTRACT}
        _, (reply,) = self.link.exchange(
            [request(method, TONE + operation, body, revision)], deadline_ns, target=binding
        )
        code, _, response = reply
        p.require(
            response.get("contract") == CONTRACT,
            "Pico reply lacks the negotiated Control/1 contract",
        )
        if code not in (200, 202):
            # A closed owner refusal can be surfaced without dumping device data.
            error = response.get("error", response.get("receipt", "request_refused"))
            label = (
                error
                if isinstance(error, str) and re.fullmatch(r"[a-z0-9_]{1,64}", error)
                else "request_refused"
            )
            raise ValueError(f"Pico {operation.split('?')[0]} returned {code} ({label})")
        p.require(response.get("target") == binding, "Pico operation target changed")
        return response

    def _tone_fields(self, point, duration_ms, drive_key):
        p.require(
            type(point.drive_ma) is int
            and point.drive_ma in self.drives
            and type(point.carrier_hz) is int
            and point.carrier_hz > 0
            and type(duration_ms) is int
            and self.minimum_ms <= duration_ms <= 120_000,
            "Invalid Pico tone carrier, drive, or duration",
        )
        body = dict(carrier_hz=point.carrier_hz, duration_ms=duration_ms)
        body[drive_key] = point.drive_ma
        if self.engine_assertion:
            body["engine"] = self.engine
        return body

    def _matches_engine(self, row, target):
        return row.get("rf_pin") == 2 and (
            not self.engine_assertion
            or (row.get("engine") == self.engine and row.get("synthesis_readback") is None)
        )

    def assess(self, target, point, duration_ms, *, deadline_ns=None):
        result = self._call(
            "POST",
            "review",
            target,
            deadline_ns or time.monotonic_ns() + 8_000_000_000,
            body=dict(
                schema="test-tone-review",
                tone=self._tone_fields(point, duration_ms, "proposed_drive_ma"),
            ),
        )
        self._check_assessment(result, target, point)
        return result

    def assess_many(self, target, points, duration_ms):
        """Review an entire matrix in one read-only USB session."""
        p.require(1 <= len(points) <= 104, "Review one bounded Pico matrix")
        binding = self._binding(target)
        rows = [
            request(
                "POST",
                TONE + "review",
                dict(
                    contract=CONTRACT,
                    schema="test-tone-review",
                    target=binding,
                    tone=self._tone_fields(point, duration_ms, "proposed_drive_ma"),
                ),
            )
            for point in points
        ]
        _, replies = self.link.exchange(rows, time.monotonic_ns() + 40_000_000_000, target=binding)
        result = []
        for point, (status, _, body) in zip(points, replies, strict=True):
            p.require(
                status == 200
                and body.get("contract") == CONTRACT
                and body.get("target") == binding,
                "Pico matrix review lost target binding",
            )
            self._check_assessment(body, target, point)
            result.append(body)
        return result

    def _check_assessment(self, result, target, point):
        p.require(
            result.get("schema") == "test-tone-review"
            and result.get("admission") in ("ready", "requires_restart", "refused")
            and result["assessment_revision"] == target.revision
            and result["proposed_drive_ma"] == point.drive_ma
            and self._matches_engine(result, target)
            and result["boot_drive_ma"] == target.active_drive_ma
            and result["saved_drive_ma"] == target.saved_drive_ma,
            "Pico review does not match the recorded point and revision",
        )
        if result.get("admission") != "refused":
            p.require(
                _decimal_string(result["realization"]["requested_nhz"]) == point.carrier_hz * 10**9,
                "Pico review changed the absolute requested carrier",
            )

    def admit(self, target, point, duration_ms):
        return self._admission(target, point, self.assess(target, point, duration_ms))

    def admit_many(self, target, points, duration_ms):
        rows = self.assess_many(target, points, duration_ms)
        return tuple(
            self._admission(target, point, row) for point, row in zip(points, rows, strict=True)
        )

    def _admission(self, target, point, row):
        if row["admission"] == "refused":
            reasons = row["reasons"]
            p.require(
                isinstance(reasons, list)
                and all(
                    isinstance(item, str) and re.fullmatch(r"[a-z0-9_]{1,64}", item)
                    for item in reasons
                ),
                "Malformed Pico refusal",
            )
            return Admission(point, target, "; ".join(reasons) or "pico_refused")
        value = row["realization"]
        nominal = _decimal_string(value["programmed_nhz"])
        bound = _decimal_string(value["quantization_bound_nhz"])
        lo = (nominal - bound) // 10**9
        hi = (nominal + bound + 10**9 - 1) // 10**9
        return Admission(point, target, None, row["maximum_duration_ms"], (lo, hi))

    def _status(self, target, selector, value, deadline_ns):
        p.require(selector in ("job_id", "request_id") and _id(value), "Invalid Pico tone selector")
        return self._call(
            "GET",
            f"status?device_id={target.device_id}&boot_id={target.boot_id}&{selector}={value}",
            target,
            deadline_ns,
        )

    def _accepted_job(self, reply, target, point, duration_ms, request_id, revision):
        row = reply.get("job")
        p.require(
            reply.get("schema") == "test-tone-status"
            and reply.get("receipt") == "known"
            and isinstance(row, dict)
            and row.get("request_id") == request_id
            and _id(row.get("job_id"))
            and row.get("carrier_hz") == point.carrier_hz
            and row.get("duration_ms") == duration_ms
            and row.get("boot_drive_ma") == point.drive_ma
            and self._matches_engine(row, target)
            and (not self.engine_assertion or row.get("admission_revision") == revision)
            and row.get("phase") in ("accepted", "running", "terminal")
            and isinstance(row.get("control_revision"), str)
            and bool(row["control_revision"]),
            "Pico started or reported a different tone",
        )
        return row

    def start(self, target, point, duration_ms, request_id, assessed):
        fields = self._tone_fields(point, duration_ms, "expected_drive_ma")
        self._check_assessment(assessed, target, point)
        p.require(
            _id(request_id)
            and request_id not in self._request_ids
            and (self._pending_request is None or self.terminal_receipt is not None),
            "Require a fresh Pico tone request and positively closed prior job",
        )
        p.require(
            assessed["admission"] == "ready"
            and assessed["assessment_revision"] == target.revision
            and assessed["proposed_drive_ma"] == point.drive_ma
            and assessed["boot_drive_ma"] == point.drive_ma
            and duration_ms <= assessed["maximum_duration_ms"],
            "Pico needs a fresh ready review for the current boot drive",
        )
        started = time.monotonic_ns()
        hard_end = started + duration_ms * 1_000_000
        self.tone = self.terminal_receipt = None
        self.accepted_receipt = None
        self._pending_request = request_id
        self._request_ids.add(request_id)
        self.last_stop_receipt = None
        try:
            reply = self._call(
                "POST",
                "start",
                target,
                started + 8_000_000_000,
                revision=assessed["assessment_revision"],
                body=dict(
                    schema="test-tone-start",
                    request_id=request_id,
                    tone=fields,
                ),
            )
            row = self._accepted_job(
                reply, target, point, duration_ms, request_id, assessed["assessment_revision"]
            )
        except (ValueError, OSError):
            # Resolve the original request only. An absent retained receipt is unknown.
            reply = self._status(
                target,
                "request_id",
                request_id,
                time.monotonic_ns() + 6_000_000_000,
            )
            row = self._accepted_job(
                reply, target, point, duration_ms, request_id, assessed["assessment_revision"]
            )
        self._tone_target = target
        self.accepted_receipt = reply
        self.tone = Tone(
            Job(target.target_id, target.device_id, target.boot_id, row["job_id"]),
            request_id,
            row["control_revision"],
            point.carrier_hz,
            point.drive_ma,
            duration_ms,
            hard_end,
        )
        return self.tone

    def _check_job(self, reply, job):
        row = reply["job"]
        p.require(
            reply.get("schema") == "test-tone-status"
            and reply.get("receipt") == "known"
            and self.tone is not None
            and self.tone.job == job
            and row["job_id"] == job.job_id
            and row["request_id"] == self.tone.request_id
            and row["carrier_hz"] == self.tone.carrier_hz
            and row["duration_ms"] == self.tone.duration_ms
            and row["boot_drive_ma"] == self.tone.drive_ma
            and self._matches_engine(row, self._tone_target)
            and (
                not self.engine_assertion
                or row.get("admission_revision")
                == self.accepted_receipt["job"]["admission_revision"]
            )
            and (row["phase"] == "terminal" or row["control_revision"] == self.tone.revision),
            "Pico status is not bound to the active tone",
        )
        return row

    def observe(self, job, deadline_ns):
        reply = self._status(job, "job_id", job.job_id, deadline_ns)
        row = self._check_job(reply, job)
        running = row["phase"] == "running" and reply["current"]["output_active"] is True
        if running:
            self._check_running(reply, row)
        return self._observation(job, reply, running, row["output_inactive_confirmed"])

    def _check_running(self, reply, row):
        pad = row["pad_readback"]
        p.require(
            pad["stage"] == "verified"
            and reply["current"]["owned"] is True
            and row["output_inactive_confirmed"] is False
            and pad["rf_pin"] == 2
            and pad["drive_ma"] == self.tone.drive_ma
            and _decimal_string(pad["epoch"]) > 0
            and _decimal_string(pad["observed_monotonic_ns"])
            <= _decimal_string(reply["observation_monotonic_ns"]),
            "Pico SDK pad readback does not verify this running tone",
        )

    def _observation(self, job, reply, active, inactive):
        row = reply["job"]
        return Observation(
            job,
            time.monotonic_ns(),
            active,
            inactive,
            row["carrier_hz"] if row["phase"] != "terminal" else None,
            row["boot_drive_ma"] if active and row["phase"] == "running" else None,
        )

    def _stop_context_matches(self, reply):
        return True

    def stop(self, job, deadline_ns):
        p.require(self.tone is not None and self.tone.job == job, "Refuse Stop for a foreign job")
        now = time.monotonic_ns()
        deadline_ns = min(deadline_ns, now + 8_000_000_000)
        try:
            reply = self._call(
                "POST",
                "stop",
                job,
                min(deadline_ns - 2_000_000_000, now + 5_000_000_000),
                revision=self.tone.revision,
                body=dict(schema="test-tone-stop", job_id=job.job_id),
            )
        except (ValueError, OSError):
            reply = self._status(job, "job_id", job.job_id, deadline_ns)
        self.last_stop_receipt = reply
        row = self._check_job(reply, job)
        inactive = (
            row["phase"] == "terminal"
            and self._stop_context_matches(reply)
            and row["output_inactive_confirmed"] is True
            and row["recovery_required"] is False
            and reply["current"]["output_active"] is False
            and reply["current"]["owned"] is False
        )
        if inactive:
            self.terminal_receipt = reply
        return self._observation(job, reply, not inactive, inactive)
