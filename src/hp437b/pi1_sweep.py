"""Plan, review, and run a conducted BCM2835 GPIO sweep from the Mac."""

import argparse
import hashlib
import hmac
import os
import secrets
import sys
import threading
import time
from contextlib import ExitStack
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import pi1_meter as hp
from . import pi1_owner as pi
from . import provenance as p
from . import reporting as r
from .live_sweep_review import Point
from .logger import _atomic_json
from .pico_sweep import pending_meter as pico_pending
from .reconciliation import _lease, pi_sweep_marker
from .sensor_correction import PROFILE, SENSOR_SERIAL, correction
from .sweep_matrix import DIALS, OFFSET_HZ, PROFILES

HISTORICAL_SCHEMA = "hp437b.pi1-gpio20-sweep.v1"
SCHEMA = "hp437b.gpio-qualification-sweep.v1"
BANDS = ("630m", "160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "10m")
DRIVES = PROFILES["pi-bcm283x"][1]
POINTS = tuple(
    Point(f"P{index:03d}", band, DIALS[band], DIALS[band] + OFFSET_HZ, drive)
    for index, (drive, band) in enumerate(((drive, band) for drive in DRIVES for band in BANDS), 1)
)
NS = 10**9
REVIEW_S = pi.REVIEW_OP_S
PREVIOUS_REVIEW_S = 270
HISTORICAL_REVIEW_TTL_S = 600
PREPARATION_S = 100
GROUP_S = 15
POINT_PREP_S = 22
START_S = 7
DWELL_S = 3
READ_S = 5
SPACING_S = 1
STOP_S = 8
FINAL_S = 45
TONE_S = pi.TONE_MS // 1000
POINT_S = POINT_PREP_S + TONE_S
GROUP_LIFETIME_MS = (len(BANDS) * POINT_S + 2 * GROUP_S) * 1000
RUN_S = PREPARATION_S + len(DRIVES) * 2 * GROUP_S + len(POINTS) * POINT_S + FINAL_S
PILOT_RUN_S = PREPARATION_S + 2 * GROUP_S + POINT_S + FINAL_S
SERVICE = {key: pi.TARGET[key] for key in ("service_active", "service_enabled", "service_pid")}
CONFIRM = (
    "conducted_gpio20_fixture_through_16ma_all_ten_carriers",
    "meter_437b_3125u22346_and_8482a_my41094127",
    "meter_prepared_cal_at_99_percent_and_power_ref_off",
    "rf_off_other_apps_closed_ready_for_supervised_zero",
    "independent_shutdown_ready_operator_present",
)
ROOT = Path(__file__).resolve().parents[2]
LOCKS = ROOT / "tmp/workflow-locks"


def plan(gpio=None, *, pilot=False):
    p.require(
        START_S + DWELL_S + 5 * READ_S + 4 * SPACING_S + STOP_S + 1.5 < TONE_S,
        "Point budget does not fit before cutoff",
    )
    return {
        "schema": HISTORICAL_SCHEMA if gpio is None else SCHEMA,
        "target": pi.TARGET if gpio is None else {**pi.TARGET, **pi.route(gpio)},
        "meter_serial": hp.METER_SERIAL,
        "sensor_serial": SENSOR_SERIAL,
        "tone_ms": pi.TONE_MS,
        "drive_codes": {str(drive): drive // 2 - 1 for drive in DRIVES},
        "requested_points": [asdict(point) for point in POINTS],
        "review_limit_s": PREVIOUS_REVIEW_S if gpio is None else REVIEW_S,
        "start_to_finalize_limit_s": PILOT_RUN_S if pilot else RUN_S,
        "timing_s": {
            "preparation": PREPARATION_S,
            "group_transition": GROUP_S,
            "point_preparation": POINT_PREP_S,
            "start": START_S,
            "dwell": DWELL_S,
            "bracketed_read": READ_S,
            "spacing": SPACING_S,
            "stop": STOP_S,
            "final": FINAL_S,
            "group_max_lease": GROUP_LIFETIME_MS // 1000,
        },
    }


def fixture(value, gpio=20):
    p._keys(value, ("signal_path", "maximum_indication_w", "peak_w", "dc_v", "shutdown", "confirm"))
    for key in ("signal_path", "shutdown"):
        p.require(
            isinstance(value[key], str) and 0 < len(value[key].strip()) <= 400,
            f"Record the fixture {key}",
        )
    expected = (f"conducted_gpio{gpio}_fixture_through_16ma_all_ten_carriers", *CONFIRM[1:])
    p._keys(value["confirm"], expected)
    p.require(all(v is True for v in value["confirm"].values()), "Bench confirmations are required")
    for key, low, high in (
        ("maximum_indication_w", hp.FLOOR_W, hp.LIMIT_W),
        ("peak_w", hp.FLOOR_W, Decimal("0.1")),
        ("dc_v", Decimal(0), Decimal(0)),
    ):
        number = value[key]
        p.require(isinstance(number, str) and len(number) <= 24, f"Record decimal {key}")
        try:
            number = Decimal(number)
        except InvalidOperation as exc:
            raise p.ProvenanceError(f"Invalid fixture {key}") from exc
        p.require(number.is_finite() and low <= number <= high, f"Fixture {key} exceeds limits")
    p.require(
        Decimal(value["maximum_indication_w"]) <= Decimal(value["peak_w"]),
        "Indication limit exceeds the fixture peak bound",
    )
    return value


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def checkpoint(path, value):
    _atomic_json(path, value)
    sync_directory(path.parent)


def json_file(path):
    p.require(
        path.is_file() and not path.is_symlink() and path.stat().st_size <= p.MAX_JSON,
        "Expected a bounded regular JSON file",
    )
    with path.open("rb") as stream:
        return p._json(stream.read(p.MAX_JSON + 1))


def signed(data, key):
    return hmac.new(key, r.encoded(data), hashlib.sha256).hexdigest()


def checked_path(path, root=ROOT):
    path = Path(path).absolute()
    p.require(
        path == path.resolve()
        and any(
            path.is_relative_to(root / parent) and path != root / parent
            for parent in ("tmp", "temp")
        )
        and not path.is_relative_to(root / "tmp/workflow-locks"),
        "Use a new output or review path under this checkout's ignored tmp or temp directory",
    )
    return path


def create_json(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(r.encoded(data))
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def _valid_token(value, pattern=pi.HEX):
    return isinstance(value, str) and bool(pattern.fullmatch(value))


def requested_points(review):
    return POINTS[:1] if review.get("scope") == "pilot" else POINTS


def run_limit(review):
    return PILOT_RUN_S if review.get("scope") == "pilot" else RUN_S


def validate_review(record, *, permit_refusal=False, historical=False, saved=False):
    fields = ("id", "issued", "plan", "fixture", "source", "admissions")
    legacy = saved and isinstance(record, dict) and "scope" not in record
    p._keys(record, (*fields, "expires" if legacy else "scope"))
    source = record["source"]
    p.require(isinstance(source, dict), "Malformed WsprryPi source")
    gpio = None if historical else source.get("gpio")
    p.require(historical or type(gpio) is int and gpio in pi.MUX, "Missing reviewed GPIO selection")
    pi.target(source, gpio)
    p.require(
        legacy or record["scope"] == "sweep" or (record["scope"] == "pilot" and gpio == 20),
        "Pilot scope is restricted to the first GPIO20 point",
    )
    expected_plan = plan(gpio, pilot=record.get("scope") == "pilot")
    if (
        saved
        and isinstance(record["plan"], dict)
        and record["plan"].get("review_limit_s") == PREVIOUS_REVIEW_S
    ):
        expected_plan["review_limit_s"] = PREVIOUS_REVIEW_S
    p.require(
        _valid_token(record["id"])
        and type(record["issued"]) is int
        and (
            not legacy
            or (
                type(record["expires"]) is int
                and record["expires"] == record["issued"] + HISTORICAL_REVIEW_TTL_S
            )
        )
        and r.encoded(record["plan"]) == r.encoded(expected_plan),
        "Review matrix, deadline, or authorization identity changed",
    )
    fixture(record["fixture"], 20 if historical else gpio)
    rows = record["admissions"]
    p.require(isinstance(rows, list) and len(rows) == len(POINTS), "Review needs every matrix row")
    for point, row in zip(POINTS, rows, strict=True):
        pi.admission(
            row, point, permit_refusal=permit_refusal, source=None if historical else source
        )
    p.require(
        len({(row["policy"], row["ppm_millionths"]) for row in rows}) == 1,
        "Clock correction changed while reviewing the matrix",
    )
    return record


def duty_key(directory):
    directory.mkdir(mode=0o700, exist_ok=True)
    p.require(
        directory.stat().st_uid == os.getuid() and directory.stat().st_mode & 0o077 == 0,
        "Review authorization storage must be private",
    )
    key_path = directory / "review-key"
    with _lease(directory / "review-key.lock"):
        if not key_path.exists():
            create_json(key_path, secrets.token_hex(32))
        key = json_file(key_path)
        p.require(
            _valid_token(key, pi.HASH) and key_path.stat().st_mode & 0o077 == 0,
            "Invalid local review key",
        )
    return bytes.fromhex(key)


def _meter_paths(directory):
    digest = r.digest(hp.RESOURCE.encode())
    lock = directory / f"{digest}.lock"
    return lock, pi_sweep_marker(lock)


class Controller:
    def __init__(
        self,
        owner,
        *,
        meter=hp.Meter,
        zero=hp.zero,
        root=ROOT,
        clock=time.monotonic_ns,
        wall=time.time,
        sleep=time.sleep,
        emit=print,
    ):
        self.owner, self.meter, self.zero = owner, meter, zero
        self.root, self.clock, self.wall, self.sleep, self.emit = root, clock, wall, sleep, emit
        self.locks = root / "tmp/workflow-locks"
        self.auth = self.locks / "pi1-gpio20"

    def by(self, duration, enclosing):
        return min(self.clock() + duration * NS, enclosing)

    def review(self, prepared, output, gpio, *, pilot=False):
        p.require(not pilot or gpio == 20, "Pilot scope requires GPIO20")
        selection = pi.route(gpio)
        prepared = fixture(prepared, gpio)
        output = checked_path(output, self.root)
        p.require(not output.exists(), "Review already exists")
        end = self.clock() + REVIEW_S * NS
        reply = self.owner.call(
            "review_matrix",
            {
                "route": selection,
                "points": [asdict(point) for point in POINTS],
                "duration_ms": pi.TONE_MS,
            },
            end,
        )
        p._keys(reply, ("source", "admissions"))
        issued = int(self.wall())
        record = validate_review(
            {
                "id": secrets.token_hex(16),
                "issued": issued,
                "scope": "pilot" if pilot else "sweep",
                "plan": plan(gpio, pilot=pilot),
                "fixture": prepared,
                "source": reply["source"],
                "admissions": reply["admissions"],
            },
            permit_refusal=True,
        )
        self.locks.mkdir(parents=True, exist_ok=True)
        create_json(
            output, {"review": record, "authorization": signed(record, duty_key(self.auth))}
        )
        return record

    def start(self, review_file, token, output, *, pilot=False, cancelled=lambda: False):
        began = self.clock()
        output = checked_path(output, self.root)
        review_file = checked_path(review_file, self.root)
        wrapper = json_file(review_file)
        p._keys(wrapper, ("review", "authorization"))
        review = validate_review(wrapper["review"])
        p.require(
            review["scope"] == ("pilot" if pilot else "sweep"),
            "Review authorization does not match the requested run scope",
        )
        p.require(
            _valid_token(token, pi.HASH)
            and _valid_token(wrapper["authorization"], pi.HASH)
            and hmac.compare_digest(token, wrapper["authorization"])
            and hmac.compare_digest(token, signed(review, duty_key(self.auth))),
            "Start requires the locally issued review authorization",
        )
        with _lease(self.auth / "source.lock"):
            return Run(self, review, output, began + run_limit(review) * NS, cancelled).execute()


def _service(value):
    p.require(r.encoded(value) == r.encoded(SERVICE), "Normal WsprryPi service state changed")


def _off(receipt, source=None):
    p.require(
        pi.native_off(receipt, current=source is not None),
        "Native shutdown, pin mode, or ownership is unconfirmed",
    )


class Run:
    def __init__(self, controller, review, output, end, cancelled):
        self.c = controller
        self.review, self.output, self.end, self.cancelled = review, output, end, cancelled
        self.work_end = end - FINAL_S * NS
        self.run = secrets.token_hex(16)
        self.instance = None
        self.source = review["source"]
        self.points = requested_points(review)
        self.bank = None
        self.incarnation = None
        self.worker = None
        self.group_close_attempted = False
        self.meter = None
        self.claimed = False
        self.source_pending = self.c.auth / "source-pending.json"
        _, self.meter_pending = _meter_paths(self.c.locks)
        self.record = {
            "schema": SCHEMA,
            "mode": "physical",
            "run": self.run,
            "review": review,
            "status": "running",
            "error": None,
            "bank": None,
            "groups": [],
            "began_ns": end - run_limit(review) * NS,
            "finished_ns": None,
            "pre": [],
            "post": [],
            "post_error": "Final RF-off baseline not reached",
            "meter_identity": None,
            "meter_cleanup": None,
            "zero_sha256": None,
            "source_cleanup": None,
            "points": [{"point": asdict(point), "state": "not reached"} for point in self.points],
        }

    def save(self):
        checkpoint(self.output / "workflow.json", self.record)

    def journal(self, path, phase, **fields):
        checkpoint(
            path,
            {
                "run": self.run,
                "phase": phase,
                "boot": self.source["boot"],
                "device": self.source["device"],
                "route": pi.route(self.source["gpio"]),
                "owner": self.incarnation,
                "worker": self.worker,
                **fields,
            },
        )

    def gate(self, end):
        if self.cancelled():
            raise KeyboardInterrupt("Sweep cancelled")
        if self.c.clock() >= end:
            raise TimeoutError("Reviewed sweep budget expired")

    def call(self, op, end, *, independent=False, **fields):
        receipt = self.c.owner.call(
            op, {"run": self.run, "source": self.source, **fields}, end, independent=independent
        )
        owner_binding(receipt, self.source, self.run, self.incarnation)
        return receipt

    def lookup_after_loss(self, op, end, *, lookup, **fields):
        try:
            return self.call(op, end, **fields)
        except (TimeoutError, OSError):
            return self.call("lookup", end, kind=op, **lookup)

    def fresh(self, point, reviewed, end):
        self.gate(end)
        value = self.c.owner.call(
            "admit", {"source": self.source, "point": asdict(point), "duration_ms": pi.TONE_MS}, end
        )
        p.require(
            pi.admission(value, point, source=self.source) == reviewed,
            "Native clock admission changed after Review",
        )

    def guard(self, end):
        self.gate(end)
        p.require(
            pi.target(
                self.c.owner.call("review", {"route": pi.route(self.source["gpio"])}, end),
                self.source["gpio"],
            )
            == self.source,
            "Owner, clock source provenance, or normal service changed",
        )

    def baseline(self, label, end):
        readings = self.record[label]
        read = self.meter.read_final if label == "post" else self.meter.read
        for _ in range(3):
            self.gate(end)
            row = {}
            readings.append(row)
            value = read(self.c.by(READ_S, end), row)
            row["watts"] = str(value)
            if label == "pre":
                p.require(abs(value) <= hp.BASELINE_W, "Initial RF-off indication exceeds 5 µW")

    def group(self, drive):
        end = self.c.by(GROUP_S, self.work_end)
        self.guard(end)
        self.instance = secrets.token_hex(16)
        self.group_close_attempted = False
        group = {"instance": self.instance, "drive_ma": drive, "opened": None, "closed": None}
        self.record["groups"].append(group)
        self.journal(self.source_pending, "group-pending", instance=self.instance, drive_ma=drive)
        self.save()
        opened = self.lookup_after_loss(
            "open_group",
            end,
            lookup={"instance": self.instance},
            instance=self.instance,
            drive_code=drive // 2 - 1,
            lifetime_ms=GROUP_LIFETIME_MS,
        )
        while opened.get("phase") == "pending":
            p._keys(opened, (*OWNER_FIELDS, *ROUTE_FIELDS, "instance", "worker", "phase"))
            p.require(
                opened["instance"] == self.instance and _valid_token(opened["worker"]),
                "Pending group receipt does not identify this worker",
            )
            self.gate(end)
            self.c.sleep(0.05)
            opened = self.call("lookup", end, kind="open_group", instance=self.instance)
        validate_open(opened, self.instance, drive, self.bank, self.source)
        self.worker = opened["worker"]
        group["opened"] = opened
        return group

    def close_group(self, end):
        instance = self.instance
        group = self.record["groups"][-1]
        self.group_close_attempted = True
        receipt = self.lookup_after_loss(
            "close_group", end, lookup={"instance": instance}, instance=instance
        )
        validate_group_close(receipt, instance, self.bank, self.source, self.worker)
        group["closed"] = receipt
        self.instance = None
        self.worker = None

    def point(self, index, point):
        end = self.c.by(POINT_S, self.work_end)
        setup_end = self.c.by(POINT_PREP_S, end - TONE_S * NS)
        row = self.record["points"][index]
        reviewed = self.review["admissions"][index]
        row.update(
            state="failed",
            instance=self.instance,
            dispatch_pending=False,
            rf_confirmed=False,
            samples=[],
            factor={},
            error=None,
        )
        self.c.emit(f"{point.point_id} {point.drive_ma} mA {point.band} {point.carrier_hz} Hz")
        try:
            self.guard(setup_end)
            self.fresh(point, reviewed, setup_end)
            self.meter.factor(
                correction(PROFILE, SENSOR_SERIAL, point.carrier_hz), setup_end, row["factor"]
            )
            self.gate(setup_end)
            row["request"] = secrets.token_hex(16)
            identity = {"instance": self.instance, "worker": self.worker, "request": row["request"]}
            self.journal(
                self.source_pending,
                "reserve-pending",
                instance=self.instance,
                request=row["request"],
            )
            receipt = self.lookup_after_loss(
                "reserve",
                setup_end,
                lookup=identity,
                **identity,
                point=asdict(point),
                admission=reviewed,
                duration_ms=pi.TONE_MS,
            )
            validate_tone(receipt, row, reviewed, self.bank, "reserved", self.source, self.worker)
            row.update(reservation=receipt, dispatch_pending=True)
            self.journal(
                self.source_pending,
                "start-pending",
                instance=self.instance,
                request=row["request"],
                generation=receipt["generation"],
            )
            self.save()
            self.gate(setup_end)
            hard_end = self.c.clock() + TONE_S * NS
            p.require(hard_end <= end, "Insufficient time for a bounded tone and verified Stop")
            with Tone(self, point, reviewed, row, hard_end) as tone:
                tone.measure()
            row["state"] = classify(row, self.record["pre"])
        except BaseException as exc:
            row["error"] = describe(exc)
            raise
        self.save()

    def execute(self):
        consumed = self.c.auth / f"{self.review['id']}.used"
        preparation_end = self.c.by(PREPARATION_S, self.work_end)
        self.gate(preparation_end)
        p.require(
            not consumed.exists()
            and not self.source_pending.exists()
            and not self.meter_pending.exists(),
            "Start replay or unresolved recovery state",
        )
        with self.c.owner.runtime(preparation_end):
            return self._execute(preparation_end, consumed)

    def _execute(self, preparation_end, consumed):
        self.guard(preparation_end)
        self.output.mkdir(mode=0o700)
        create_json(consumed, {"run": self.run})
        self.save()
        completed = False
        meter_lock, _ = _meter_paths(self.c.locks)
        with ExitStack() as leases:
            try:
                self.journal(self.source_pending, "claim-pending")
                self.claimed = True
                claim = self.lookup_after_loss(
                    "claim", preparation_end, lookup={}, lifetime_ms=RUN_S * 1000
                )
                self.bank = validate_claim(claim, self.run, self.source)
                self.incarnation = claim["owner"]
                self.record.update(bank=self.bank, claim=claim)
                fresh = self.call(
                    "admit_matrix",
                    self.c.by(pi.OP_S, preparation_end),
                    points=[asdict(point) for point in POINTS],
                    duration_ms=pi.TONE_MS,
                )
                p._keys(fresh, (*OWNER_FIELDS, *ROUTE_FIELDS, "admissions"))
                p.require(
                    r.encoded(fresh["admissions"]) == r.encoded(self.review["admissions"]),
                    "Native matrix admission changed before meter preparation",
                )
                # Probe the meter lock before ZERO. ZERO owns its normal lock and releases it.
                with _lease(meter_lock):
                    p.require(
                        not pico_pending(self.c.locks, hp.RESOURCE).exists(),
                        "Meter recovery is outstanding",
                    )
                    self.journal(self.meter_pending, "zero-pending")
                self.zero(self.output / "zero", preparation_end)
                leases.enter_context(_lease(meter_lock, pi_sweep_run=self.run))
                self.journal(self.meter_pending, "capture-pending")
                self.meter = self.c.meter()
                self.record["meter_identity"] = self.meter.open(preparation_end)
                self.meter.factor(
                    correction(PROFILE, SENSOR_SERIAL, POINTS[0].carrier_hz),
                    preparation_end,
                    self.record.setdefault("baseline_factor", {}),
                )
                self.baseline("pre", preparation_end)
                for index, point in enumerate(self.points):
                    self.gate(self.work_end)
                    if index % len(BANDS) == 0:
                        self.c.emit(f"Drive group {point.drive_ma} mA")
                        self.group(point.drive_ma)
                    self.point(index, point)
                    if index % len(BANDS) == len(BANDS) - 1 or index + 1 == len(self.points):
                        self.close_group(self.c.by(GROUP_S, self.work_end))
                        self.save()
                completed = True
            except BaseException as exc:
                self.record["error"] = describe(exc)
            finally:
                self.cleanup()
                self.record["finished_ns"] = self.c.clock()
                if self.record["finished_ns"] > self.end:
                    self.record["error"] = self.record["error"] or "Finalization deadline exceeded"
                self.record["status"] = (
                    "completed"
                    if completed and self.healthy() and self.record["error"] is None
                    else "partial"
                )
                self.save()
                from .pi1_report import seal_capture

                seal_capture(self.output, self.record)
        return self.record

    def zero(self, path, end):
        self.c.zero(path, self.c.locks, self.run, lambda: self.cancelled() or self.c.clock() >= end)
        self.record["zero_sha256"] = r.digest((path / "diagnostics.json").read_bytes())
        self.gate(end)

    def cleanup(self):
        if self.claimed:
            try:
                if self.instance is not None:
                    p.require(
                        not self.group_close_attempted,
                        "Group cleanup was already attempted, reconciliation is required",
                    )
                    self.close_group(self.c.by(GROUP_S, self.end))
                terminal = self.lookup_after_loss(
                    "release", self.c.by(2 * pi.OP_S, self.end), lookup={}
                )
                # Retain the native receipt even when it fails validation.
                self.record["source_cleanup"] = {"receipt": terminal, "verified": False}
                validate_release(terminal, self.run, self.bank, self.source)
                self.record["source_cleanup"]["verified"] = True
                self.source_pending.unlink()
                sync_directory(self.source_pending.parent)
            except BaseException as exc:
                self.record["source_cleanup"] = {
                    **(self.record["source_cleanup"] or {}),
                    "verified": False,
                    "error": describe(exc),
                }
        if self.meter is not None:
            if self.source_verified() and len(self.record["pre"]) == 3 and self.meter.can_read():
                try:
                    baseline_end = self.end - hp.FINAL_CLOSE_RESERVE_S * NS
                    self.meter.factor(
                        correction(PROFILE, SENSOR_SERIAL, POINTS[0].carrier_hz),
                        baseline_end,
                        self.record.setdefault("post_factor", {}),
                    )
                    self.baseline("post", baseline_end)
                    self.record["post_error"] = None
                except BaseException as exc:
                    self.record["post_error"] = describe(exc)
            else:
                self.record["post_error"] = (
                    "Final baseline unavailable after failed capture or shutdown"
                )
            try:
                closed = self.meter.close()
                self.record["meter_cleanup"] = closed or {
                    "status": "unverified",
                    "error": "Meter return to local is unconfirmed",
                }
            except BaseException as exc:
                self.record["meter_cleanup"] = {"status": "unverified", "error": describe(exc)}
        if (
            self.record["zero_sha256"] is not None
            and self.source_verified()
            and (self.meter is None or self.record["meter_cleanup"]["status"] == "accepted")
        ):
            self.meter_pending.unlink(missing_ok=True)
            sync_directory(self.meter_pending.parent)

    def source_verified(self):
        return (self.record["source_cleanup"] or {}).get("verified") is True

    def healthy(self):
        return (
            self.source_verified()
            and self.record["post_error"] is None
            and len(self.record["post"]) == 3
            and self.record["meter_cleanup"]["status"] == "accepted"
        )


def describe(exc):
    return f"{type(exc).__name__}: {exc}"[:400]


def classify(row, initial):
    values = [Decimal(entry["watts"]) for entry in row["samples"] if entry["kind"] == "retained"]
    p.require(len(values) == 2, "A completed point needs exactly two retained samples")
    floor = max(hp.FLOOR_W, *(abs(Decimal(entry["watts"])) for entry in initial))
    return "limited" if min(values) <= floor else "measured"


def settled(a, b):
    return abs(a - b) <= max(Decimal("0.0000002"), Decimal("0.01") * max(abs(a), abs(b)))


OFF_FIELDS = ("gpclk_enabled", "gpclk_busy", "gpio_input", "owned", "mux")
OWNER_FIELDS = ("run", "boot", "device")
ROUTE_FIELDS = ("owner", "profile", "gpio", "route_mux")
EXTRA_OFF_FIELDS = ("other_gpio_input", "dma_idle", "pwm_idle")


def _route_fields(source):
    return () if source is None else ROUTE_FIELDS


def _off_fields(source):
    return OFF_FIELDS if source is None else (*OFF_FIELDS, *EXTRA_OFF_FIELDS)


def owner_binding(value, source, run, incarnation=None, *, historical=False):
    p.require(
        isinstance(value, dict)
        and all(
            value.get(key) == expected
            for key, expected in (
                ("run", run),
                ("boot", source["boot"]),
                ("device", source["device"]),
            )
        ),
        "Owner receipt belongs to a different run, device, or boot",
    )
    if not historical:
        p.require(
            _valid_token(value.get("owner"))
            and (incarnation is None or value["owner"] == incarnation)
            and value.get("profile") == source["profile"]
            and type(value.get("gpio")) is int
            and value["gpio"] == source["gpio"]
            and value.get("route_mux") == source["mux"],
            "Owner receipt belongs to a different profile, pin, or incarnation",
        )


def validate_claim(value, run, source=None):
    p._keys(
        value,
        (
            *OWNER_FIELDS,
            *_route_fields(source),
            "bank",
            "service",
            "exclusive",
            "durable",
            *_off_fields(source),
        ),
    )
    _service(value["service"])
    _off(value, source)
    p.require(
        value["run"] == run and value["exclusive"] is True and value["durable"] is True,
        "Source lease or Pi-local recovery state is unconfirmed",
    )
    return pi.bank(value["bank"])


def validate_open(value, instance, drive, bank, source=None):
    p._keys(
        value,
        (
            *OWNER_FIELDS,
            *_route_fields(source),
            *(("worker", "phase") if source is not None else ()),
            "instance",
            "drive_code",
            "bank",
            "service",
            "listen",
            "ancillary_off",
            "lifetime_ms",
            "port",
            *_off_fields(source),
        ),
    )
    _service(value["service"])
    _off(value, source)
    p.require(
        value["instance"] == instance
        and type(value["drive_code"]) is int
        and value["drive_code"] == drive // 2 - 1
        and pi.bank(value["bank"]) == bank
        and value["listen"] == "127.0.0.1"
        and value["ancillary_off"] is True
        and type(value["port"]) is int
        and 1024 <= value["port"] <= (49151 if source is None else 65535)
        and (source is None or (value["phase"] == "ready" and _valid_token(value["worker"])))
        and type(value["lifetime_ms"]) is int
        and value["lifetime_ms"] == GROUP_LIFETIME_MS,
        "Temporary WsprryPi process, lifetime, pad state, or listener is unconfirmed",
    )


def validate_group_close(value, instance, bank, source=None, worker=None):
    p._keys(
        value,
        (
            *OWNER_FIELDS,
            *_route_fields(source),
            *(("worker",) if source is not None else ()),
            "instance",
            "bank",
            "exited",
            "service",
            *_off_fields(source),
        ),
    )
    _service(value["service"])
    _off(value, source)
    p.require(
        value["instance"] == instance
        and value["exited"] is True
        and (
            source is None
            or (_valid_token(value["worker"]) and (worker is None or value["worker"] == worker))
        )
        and pi.bank(value["bank"]) == bank,
        "Process exit or pad bank restoration is unconfirmed",
    )


def validate_release(value, run, bank, source=None):
    p._keys(
        value,
        (
            *OWNER_FIELDS,
            *_route_fields(source),
            "bank",
            "released",
            "service",
            *_off_fields(source),
        ),
    )
    _service(value["service"])
    _off(value, source)
    p.require(
        value["run"] == run and value["released"] is True and pi.bank(value["bank"]) == bank,
        "Source lease release or bank restoration is unconfirmed",
    )


TONE_FIELDS = (
    *OWNER_FIELDS,
    "instance",
    "request",
    "generation",
    "revision",
    "phase",
    "plan",
    "drive_code",
    "gpio",
    "clock",
    "cutoff_ms",
    "service",
    *OFF_FIELDS,
)


def validate_tone(value, row, admission, bank, phase, source=None, worker=None):
    extra = (
        ()
        if source is None
        else (
            "owner",
            "profile",
            "route_mux",
            *EXTRA_OFF_FIELDS,
            "worker",
            "ceiling_ms",
            "armed_at_ms",
            "inactive_at_ms",
            "reserved_until_ms",
        )
    )
    p._keys(value, (*TONE_FIELDS, *extra, "bank"))
    _service(value["service"])
    p.require(
        value["instance"] == row["instance"]
        and value["request"] == row["request"]
        and type(value["generation"]) is int
        and value["generation"] > 0
        and type(value["revision"]) is int
        and value["revision"] >= 0
        and value["phase"] == phase
        and value["plan"] == admission["plan"]
        and type(value["gpio"]) is int
        and value["gpio"] == (20 if source is None else source["gpio"])
        and value["clock"] == "GPCLK0"
        and type(value["cutoff_ms"]) is int
        and value["cutoff_ms"] == pi.TONE_MS
        and type(value["drive_code"]) is int
        and value["drive_code"] == admission["drive_code"],
        "Owner response does not identify this bounded GPIO job",
    )
    if source is not None:
        reservation = row.get("reservation")
        p.require(
            value["worker"] == worker
            and _valid_token(worker)
            and value["other_gpio_input"] is True
            and type(value["reserved_until_ms"]) is int
            and value["reserved_until_ms"] > 0
            and type(value["inactive_at_ms"]) is int
            and type(value["armed_at_ms"]) is int
            and type(value["ceiling_ms"]) is int
            and (
                value["armed_at_ms"] == value["ceiling_ms"] == 0
                if phase in ("reserved", "cancelled-before-enable")
                else 0 < value["armed_at_ms"] < value["reserved_until_ms"]
                and value["ceiling_ms"] - value["armed_at_ms"] == pi.TONE_MS
            )
            and (
                value["armed_at_ms"] <= value["inactive_at_ms"] <= value["ceiling_ms"]
                if phase == "terminal"
                else value["inactive_at_ms"] > 0
                if phase == "cancelled-before-enable"
                else value["inactive_at_ms"] == 0
            )
            and (
                reservation is None
                or (
                    value["generation"] == reservation["generation"]
                    and value["reserved_until_ms"] == reservation["reserved_until_ms"]
                )
            ),
            "Qualification worker, reservation, or Pi deadline does not match",
        )
    pad = pi.bank(value["bank"])
    if phase == "active":
        p.require(
            pad == {**bank, "drive": admission["drive_code"]}
            and value["mux"] == ("ALT5" if source is None else source["mux"])
            and (source is None or (value["dma_idle"] is False and value["pwm_idle"] is False))
            and all(
                value[key] is expected
                for key, expected in (
                    ("gpclk_enabled", True),
                    ("gpclk_busy", True),
                    ("gpio_input", False),
                    ("owned", True),
                )
            ),
            "Selected GPIO clock or effective BCM2835 drive is unconfirmed",
        )
    elif phase in ("terminal", "reserved", "cancelled-before-enable"):
        _off(value, source)
        p.require(
            (
                pad in (bank, {**bank, "drive": admission["drive_code"]})
                if source is None
                else pad == bank
            ),
            "Unexpected pad bank change during tone shutdown",
        )
    return value


class Tone:
    """Run Stop on a separate SSH connection, including after a lost Start reply."""

    def __init__(self, run, point, admission, row, end):
        self.run, self.point, self.admission, self.row = run, point, admission, row
        self.end = end
        self.clock = run.c.clock
        self.sleep = run.c.sleep
        self.stop_by = end - STOP_S * NS
        self.ready = threading.Event()
        self.closing = threading.Event()
        self.stop_result = None
        self.stop_error = None
        self.job = row["reservation"]["generation"]
        self.pi_window = None
        self.window_lock = threading.Lock()
        self.thread = threading.Thread(target=self._supervise, daemon=True)

    def __enter__(self):
        self.row["host_start_ns"] = self.end - TONE_S * NS
        self.thread.start()
        return self

    def __exit__(self, kind, exc, traceback):
        self.ready.set()
        self.thread.join(max(0, (self.end - self.clock()) / NS))
        if self.stop_result is not None:
            self.row["stop"] = self.stop_result
        else:
            self.row["stop_error"] = self.stop_error or "Verified Stop deadline expired"
        if kind is None:
            p.require(
                self.stop_result is not None,
                "Native Stop unverified; independent shutdown may be needed",
            )
            stop = self.stop_result
            last = self.row["samples"][-1]["after"]
            p.require(
                stop["receipt"]["generation"] == self.job
                and stop["receipt"]["revision"] > last["receipt"]["revision"]
                and last["received_ns"] <= stop["sent_ns"],
                "Owner terminal event does not follow the last active window",
            )

    def _supervise(self):
        try:
            while not self.ready.is_set() and self.clock() < self.stop_by:
                if self.run.cancelled():
                    break
                self.ready.wait(0.02)
        finally:
            self.closing.set()
            try:
                try:
                    self.stop_result = self._call("stop", self.end, "terminal", independent=True)
                except (TimeoutError, OSError):
                    self.stop_result = self._call("status", self.end, "terminal", independent=True)
            except BaseException as exc:
                self.stop_error = describe(exc)

    def _call(self, operation, end, phase, **fields):
        start = self.clock()
        receipt = self.run.call(
            operation,
            end,
            instance=self.row["instance"],
            request=self.row["request"],
            generation=self.job,
            worker=self.run.worker,
            **fields,
        )
        timestamp = self.clock()
        p.require(start <= timestamp <= end, "Owner receipt missed its host observation window")
        if (
            operation in ("stop", "status")
            and phase == "terminal"
            and receipt.get("phase") == "cancelled-before-enable"
        ):
            phase = "cancelled-before-enable"
        validate_tone(
            receipt,
            self.row,
            self.admission,
            self.run.bank,
            phase,
            self.run.source,
            self.run.worker,
        )
        p.require(
            receipt["generation"] == self.job, "Owner returned a different controller generation"
        )
        if receipt["ceiling_ms"]:
            window = (receipt["armed_at_ms"], receipt["ceiling_ms"])
            with self.window_lock:
                p.require(self.pi_window in (None, window), "Owner changed the armed Pi deadline")
                self.pi_window = window
        return {"sent_ns": start, "received_ns": timestamp, "receipt": receipt}

    def _ensure_open(self, end):
        self.run.gate(end)
        p.require(not self.closing.is_set(), "The RF window is closing")

    def measure(self):
        startup_end = self.row["host_start_ns"] + START_S * NS
        self._ensure_open(startup_end)
        self.row["start_attempted"] = True
        ack = self._call(
            "start",
            startup_end,
            "accepted",
            point=asdict(self.point),
            admission=self.admission,
            duration_ms=pi.TONE_MS,
        )
        self.row["ack"] = ack
        active = self._call("status", startup_end, "active")
        p.require(
            active["receipt"]["revision"] >= ack["receipt"]["revision"],
            "Active proof predates Start acceptance",
        )
        self.row["active"] = active
        self.row["rf_confirmed"] = True
        self.sleep(DWELL_S)
        previous = None
        for _ in range(3):
            current = self.sample("settling", active)
            if previous is not None and settled(previous, current):
                break
            previous = current
            self.sleep(SPACING_S)
        else:
            raise p.ProvenanceError("Successive settling indications did not agree")
        self.sleep(SPACING_S)
        self.sample("retained", active)
        self.sleep(SPACING_S)
        self.sample("retained", active)
        self.ready.set()

    def sample(self, kind, active):
        end = self.clock() + READ_S * NS
        p.require(end <= self.stop_by, "Insufficient time for another bracketed read")
        self._ensure_open(end)
        entry = {"kind": kind}
        samples = self.row["samples"]
        previous = samples[-1]["after"] if samples else active
        samples.append(entry)
        before = self._call("status", self.run.c.by(1, end), "active")
        entry["before"] = before
        p.require(
            before["receipt"]["revision"] >= previous["receipt"]["revision"],
            "Reordered active proof",
        )
        self._ensure_open(end)
        entry["read_started_ns"] = self.clock()
        value = self.run.meter.read(
            end - NS, entry, Decimal(self.run.review["fixture"]["maximum_indication_w"])
        )
        entry["read_finished_ns"] = self.clock()
        entry["received_utc"] = datetime.now(UTC).isoformat()
        self._ensure_open(end)
        after = self._call("status", self.run.c.by(1, end), "active")
        self._ensure_open(end)
        p.require(
            before["receipt"]["revision"] == after["receipt"]["revision"],
            "Controller changed during the sample window",
        )
        entry.update(after=after, watts=str(value))
        return value


def main(argv=None, *, controller=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    planning = actions.add_parser("plan")
    planning.add_argument("--gpio", required=True, type=int, choices=tuple(pi.MUX))
    review = actions.add_parser("review")
    review.add_argument("--gpio", required=True, type=int, choices=tuple(pi.MUX))
    review.add_argument("--fixture", required=True, type=Path)
    review.add_argument("--output", required=True, type=Path)
    review.add_argument(
        "--pilot", action="store_true", help="Authorize only the first GPIO20 point"
    )
    for action in ("start", "pilot"):
        start = actions.add_parser(action)
        start.add_argument("--review", required=True, type=Path)
        start.add_argument("--authorize", required=True)
        start.add_argument("--output", required=True, type=Path)
    report = actions.add_parser("report")
    report.add_argument("--capture", required=True, type=Path)
    report.add_argument("--output", required=True, type=Path)
    report.add_argument("--pdf", action="store_true")
    args = parser.parse_args(argv)
    controller = controller or Controller(
        pi.Owner(), emit=lambda line: print(line, file=sys.stderr)
    )
    try:
        if args.action == "plan":
            result = plan(args.gpio)
        elif args.action == "review":
            result = controller.review(
                json_file(args.fixture), args.output, args.gpio, pilot=args.pilot
            )
            print(r.encoded(json_file(args.output)).decode(), end="")
            return int(any(row["refusal"] is not None for row in result["admissions"]))
        elif args.action in ("start", "pilot"):
            result = controller.start(
                args.review, args.authorize, args.output, pilot=args.action == "pilot"
            )
            print(
                r.encoded(
                    {
                        "run": result["run"],
                        "status": result["status"],
                        "error": result["error"],
                        "output": str(args.output),
                    }
                ).decode(),
                end="",
            )
            return int(result["status"] != "completed")
        else:
            from .pi1_report import publish

            result = publish(args.capture, checked_path(args.output, controller.root), pdf=args.pdf)
        print(r.encoded(result).decode(), end="")
        return 0
    except KeyboardInterrupt:
        return 130
    except (ValueError, OSError) as exc:
        print(describe(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
