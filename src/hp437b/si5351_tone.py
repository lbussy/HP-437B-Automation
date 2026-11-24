"""Pico Si5351 Test Tone through the authenticated Control/1 USB transport."""

import time
from dataclasses import dataclass

from . import provenance as p
from . import reporting as r
from .live_sweep_review import Admission, Point, Target, _disposition
from .live_sweep_window import Observation
from .pico_tone import CONTRACT, CONTROL, PicoTone, _decimal_string, request, tone_descriptor
from .sweep_matrix import PROFILES

PROFILE_ID = "qrp-labs-rev6-25mhz-clk0"
REFERENCE_HZ = 25_000_000
OUTPUT = 0
ENGINE = "si5351"
DRIVES = PROFILES["si5351"][1]
SETTINGS_FIELDS = (
    "reference_hz",
    "reference_source",
    "crystal_load_pf",
    "address",
    "drive_ma",
    "transmit_output",
    "loopback_output",
    "loopback_input_gp",
    "rf_gate_gp",
    "rf_gate_active_high",
    "reference_use",
    "trusted_uncertainty_ppb",
    "manual_correction_ppb",
    "automatic_calibration",
)


@dataclass(frozen=True)
class Si5351Target(Target):
    source_profile_id: str
    reference_hz: int
    settings_sha256: str
    maximum_duration_ms: int


@dataclass(frozen=True)
class Si5351Observation(Observation):
    receipt: dict


def matches_synthesis(row):
    return (
        row.get("engine") == row.get("execution_engine") == ENGINE
        and row.get("profile_id") == PROFILE_ID
        and "rf_pin" in row
        and row["rf_pin"] is None
        and type(row.get("transmit_output")) is int
        and row["transmit_output"] == OUTPUT
        and type(row.get("reference_hz")) is int
        and row["reference_hz"] == REFERENCE_HZ
    )


def check_readback(row, drive, observed_ns):
    p.require(
        matches_synthesis(row)
        and "pad_readback" in row
        and row["pad_readback"] is None
        and row.get("inactivity_basis") == "si5351_register_shutdown",
        "Pico receipt does not identify Si5351 register evidence",
    )
    evidence = row.get("synthesis_readback")
    p._keys(
        evidence,
        (
            "stage",
            "epoch",
            "observed_monotonic_ns",
            "drive_ma",
            "transmit_output",
            "reference_hz",
        ),
    )
    when = _decimal_string(evidence["observed_monotonic_ns"])
    p.require(
        evidence["stage"] == "verified"
        and type(evidence["drive_ma"]) is int
        and evidence["drive_ma"] == drive
        and type(evidence["transmit_output"]) is int
        and evidence["transmit_output"] == OUTPUT
        and type(evidence["reference_hz"]) is int
        and evidence["reference_hz"] == REFERENCE_HZ
        and _decimal_string(evidence["epoch"]) > 0
        and 0 < when <= _decimal_string(observed_ns),
        "Pico synthesis readback does not verify the accepted clock, reference, and drive",
    )
    return evidence


def realization_bounds(value, carrier_hz):
    p._keys(
        value,
        (
            "requested_nhz",
            "programmed_nhz",
            "increment",
            "nominal_sample_hz",
            "quantization_bound_nhz",
            "correction",
        ),
    )
    requested = carrier_hz * 10**9
    programmed = _decimal_string(value["programmed_nhz"])
    bound = _decimal_string(value["quantization_bound_nhz"])
    p.require(
        value["nominal_sample_hz"] is None
        and value["increment"] is None
        and _decimal_string(value["requested_nhz"]) == requested
        and programmed > bound,
        "Si5351 realization does not match the requested carrier",
    )
    correction = value["correction"]
    if correction is not None:
        p._keys(
            correction, ("ppb", "automatic", "generation", "observed_raw_ns", "uncertainty_ppb")
        )
        _decimal_string(correction["generation"])
        _decimal_string(correction["observed_raw_ns"])
        p.require(
            type(correction["ppb"]) is int
            and type(correction["automatic"]) is bool
            and type(correction["uncertainty_ppb"]) is int
            and correction["uncertainty_ppb"] >= 0,
            "Malformed Si5351 frequency correction",
        )
    return (programmed - bound) // 10**9, (programmed + bound + 10**9 - 1) // 10**9


def applied_factor(value, target, point, timing):
    bounds = realization_bounds(value, point.carrier_hz)
    result = _disposition(Admission(point, target, None, timing.tone_ms, bounds), timing, 1)
    p.require(result.reason is None, "Si5351 LOAD left the admitted sensor correction range")
    return result.correction_percent


def check_running(reply, initial, drive, carrier_hz, duration_ms):
    row, current = reply["job"], reply["current"]
    evidence = check_readback(row, drive, reply["observation_monotonic_ns"])
    realization_bounds(row["realization"], carrier_hz)
    launched = _decimal_string(row["launch_monotonic_ns"])
    accepted = _decimal_string(row["accepted_monotonic_ns"])
    observed = _decimal_string(reply["observation_monotonic_ns"])
    p.require(
        row["phase"] == "running"
        and current["engine"] == ENGINE
        and current["output_active"] is True
        and current["owned"] is True
        and current["boot_drive_ma"] == current["saved_drive_ma"] == drive
        and row["output_inactive_confirmed"] is False
        and row["recovery_required"] is False
        and initial["realization"] == row["realization"]
        and initial["accepted_monotonic_ns"] == row["accepted_monotonic_ns"]
        and initial["admission_revision"] == row["admission_revision"]
        and accepted
        <= _decimal_string(evidence["observed_monotonic_ns"])
        <= launched
        <= observed
        < launched + duration_ms * 1_000_000,
        "Pico did not verify a matching running Si5351 window",
    )
    return observed


def stop_context_matches(reply, drive):
    current = reply["current"]
    return (
        reply["job"].get("inactivity_basis") == "si5351_register_shutdown"
        and current.get("engine") == ENGINE
        and current.get("saved_drive_ma") == current.get("boot_drive_ma") == drive
    )


class Si5351Tone(PicoTone):
    engine = ENGINE
    drives = DRIVES
    minimum_ms = 10

    def __init__(self, link, target_id):
        super().__init__(link, target_id)
        self.engine_assertion = True

    def _reads(self, names, deadline_ns, *, target=None):
        identity, replies = self.link.exchange(
            [request("GET", CONTROL + name) for name in names], deadline_ns, target=target
        )
        for name, (status, _, body) in zip(names, replies, strict=True):
            p.require(
                status == 200
                and body.get("contract") == CONTRACT
                and (
                    name in ("capabilities", "status", "config") or body.get("target") == identity
                ),
                f"Pico {name} did not verify for the current Si5351 boot",
            )
        return identity, replies

    def _settings(self, reply):
        saved, active = reply.get("saved"), reply.get("boot_active")
        for settings in (saved, active):
            p._keys(settings, SETTINGS_FIELDS)
            p.require(
                type(settings["drive_ma"]) is int
                and settings["drive_ma"] in DRIVES
                and settings["reference_hz"] == REFERENCE_HZ
                and settings["reference_source"] == "external_xa"
                and type(settings["transmit_output"]) is int
                and settings["transmit_output"] == OUTPUT
                and settings["address"] == 96
                and settings["rf_gate_gp"] is None,
                "Prepare the selected CLK0 Si5351 profile with a 25 MHz external reference",
            )
        p.require(
            reply.get("schema") == "si5351"
            and reply.get("execution_engine") == ENGINE
            and reply.get("physically_qualified") is True
            and reply.get("storage_healthy") is True
            and (reply.get("qualification") or {}).get("profile_id") == PROFILE_ID
            and type(reply.get("pending_restart")) is bool,
            "Pico has no authoritative ordinary Si5351 settings",
        )
        return saved, active

    def snapshot(self, target_id, *, deadline_ns=None):
        p.require(target_id == self.target_id, "Wrong configured Pico target")
        identity, replies = self._reads(
            ("capabilities", "status", "message-schedule", "si5351", "config"),
            deadline_ns or time.monotonic_ns() + 12_000_000_000,
        )
        caps, status, messages, state, config = (row[2] for row in replies)
        tone_descriptor(caps, ENGINE, DRIVES, self.minimum_ms)
        saved, active = self._settings(state)
        revision = replies[-1][1]
        configured = config.get("config")
        job = status["job"]
        p.require(
            isinstance(revision, str)
            and bool(revision)
            and revision == replies[-2][1]
            and isinstance(configured, dict)
            and configured.get("si5351") == saved
            and job.get("boot_id") == identity["boot_id"]
            and type(job.get("output_active")) is bool,
            "Pico Si5351 configuration and native state did not verify",
        )
        stable_settings = dict(
            config={
                **configured,
                "si5351": {key: value for key, value in saved.items() if key != "drive_ma"},
            },
            message_schedule=messages["saved"],
        )
        return Si5351Target(
            target_id,
            identity["device_id"],
            identity["boot_id"],
            revision,
            "pico",
            "CLK0",
            ENGINE,
            active["drive_ma"],
            saved["drive_ma"],
            job["state"] in ("empty", "complete", "aborted", "missed") and job["owner_id"] is None,
            job["output_active"] is False,
            state["pending_restart"] or saved != active,
            configured.get("enabled") is False
            and status["standalone"].get("enabled") is False
            and "saved" in messages
            and (messages["saved"] is None or messages["saved"].get("enabled") is False),
            state["qualification"]["profile_id"],
            active["reference_hz"],
            r.digest(r.encoded(stable_settings)),
            caps["test_tone"]["maximum_duration_ms"],
        )

    def change_drive(self, target, drive, deadline_ns):
        p.require(
            type(drive) is int
            and drive in DRIVES
            and drive != target.active_drive_ma
            and target.idle
            and target.output_inactive
            and target.schedules_inhibited
            and not target.restart_pending
            and target.active_drive_ma == target.saved_drive_ma
            and self.snapshot(target.target_id, deadline_ns=deadline_ns) == target
            and (self._pending_request is None or self.terminal_receipt is not None),
            "Si5351 drive change needs the reviewed idle boot and confirmed RF off",
        )
        binding = self._binding(target)
        _, ((_, revision, state),) = self._reads(("si5351",), deadline_ns, target=binding)
        saved, active = self._settings(state)
        p.require(
            revision == target.revision
            and saved == active
            and saved["drive_ma"] == target.active_drive_ma,
            "Si5351 settings changed",
        )
        updated = {**saved, "drive_ma": drive}
        _, ((code, _, _),) = self.link.exchange(
            [
                request(
                    "POST",
                    CONTROL + "config/update",
                    dict(
                        contract=CONTRACT,
                        schema="config-update",
                        target=binding,
                        mode="merge",
                        config={"si5351": updated},
                    ),
                    revision,
                )
            ],
            min(deadline_ns, time.monotonic_ns() + 12_000_000_000),
            target=binding,
        )
        p.require(code in (200, 202), "Pico refused the Si5351 drive save")
        saved_target = self.snapshot(target.target_id, deadline_ns=deadline_ns)
        p.require(
            saved_target.boot_id == target.boot_id
            and saved_target.device_id == target.device_id
            and saved_target.saved_drive_ma == drive
            and saved_target.active_drive_ma == target.active_drive_ma
            and saved_target.settings_sha256 == target.settings_sha256
            and saved_target.restart_pending
            and saved_target.idle
            and saved_target.output_inactive
            and saved_target.schedules_inhibited,
            "Si5351 drive save did not verify; restart was withheld",
        )
        try:
            _, ((code, _, reply),) = self.link.exchange(
                [
                    request(
                        "POST", CONTROL + "restart", dict(contract=CONTRACT), saved_target.revision
                    )
                ],
                min(deadline_ns, time.monotonic_ns() + 12_000_000_000),
                target=binding,
            )
        except (OSError, ValueError):
            # A delivered reset may close USB before the response arrives.
            pass
        else:
            p.require(
                code == 202 and reply.get("restart_requested") is True,
                "Pico refused the Si5351 drive restart",
            )
        while time.monotonic_ns() < deadline_ns:
            try:
                current = self.snapshot(
                    target.target_id,
                    deadline_ns=min(deadline_ns, time.monotonic_ns() + 8_000_000_000),
                )
            except (OSError, ValueError):
                time.sleep(0.4)
                continue
            if current.boot_id != target.boot_id:
                p.require(
                    current.device_id == target.device_id
                    and current.settings_sha256 == target.settings_sha256
                    and current.active_drive_ma == current.saved_drive_ma == drive
                    and current.idle
                    and current.output_inactive
                    and current.schedules_inhibited
                    and not current.restart_pending,
                    "Si5351 settings, drive, or RF state did not verify after restart",
                )
                return current
            time.sleep(0.4)
        raise TimeoutError("Pico did not verify the new Si5351 boot")

    def _matches_engine(self, row, target):
        return isinstance(target, Si5351Target) and matches_synthesis(row)

    def _check_assessment(self, result, target, point):
        super()._check_assessment(result, target, point)
        p.require(
            result.get("target") == self._binding(target)
            and result.get("minimum_duration_ms") == self.minimum_ms
            and type(result.get("maximum_duration_ms")) is int
            and self.minimum_ms <= result["maximum_duration_ms"] <= target.maximum_duration_ms
            and type(result.get("requires_restart")) is bool
            and (
                result["admission"] not in ("ready", "requires_restart")
                or (result["admission"] == "requires_restart")
                == result["requires_restart"]
                == (point.drive_ma != target.active_drive_ma)
            ),
            "Si5351 Review bounds or drive transition do not match the target",
        )

    def _admission(self, target, point: Point, row):
        if row["admission"] == "refused":
            return super()._admission(target, point, row)
        bounds = realization_bounds(row["realization"], point.carrier_hz)
        return Admission(point, target, None, row["maximum_duration_ms"], bounds)

    def _check_running(self, reply, row):
        check_running(
            reply,
            self.accepted_receipt["job"],
            self.tone.drive_ma,
            self.tone.carrier_hz,
            self.tone.duration_ms,
        )

    def observe(self, job, deadline_ns):
        # Leave time for the identified Stop even if cancellation arrives while
        # Status holds the shared USB transport.
        return super().observe(job, min(deadline_ns, time.monotonic_ns() + 3_000_000_000))

    def _stop_context_matches(self, reply):
        return stop_context_matches(reply, self.tone.drive_ma)

    def _observation(self, job, reply, active, inactive):
        result = super()._observation(job, reply, active, inactive)
        return Si5351Observation(
            result.job,
            result.observed_ns,
            result.active,
            result.output_inactive,
            result.carrier_hz,
            result.drive_ma,
            reply,
        )
