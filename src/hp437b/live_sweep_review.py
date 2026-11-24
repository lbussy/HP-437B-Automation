"""Read-only planning and timing for an automatic physical guided sweep."""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Protocol

from . import provenance as p
from . import reporting as r
from . import sweep_matrix
from .sensor_correction import PROFILE, SENSOR_SERIAL, TABLE, correction


@dataclass(frozen=True)
class Point:
    point_id: str
    band: str
    dial_hz: int
    carrier_hz: int
    drive_ma: int


@dataclass(frozen=True)
class Target:
    target_id: str
    device_id: str
    boot_id: str
    revision: str
    owner: str
    output: str
    profile: str
    active_drive_ma: int
    saved_drive_ma: int | None
    idle: bool
    output_inactive: bool
    restart_pending: bool
    schedules_inhibited: bool


@dataclass(frozen=True)
class Admission:
    point: Point
    target: Target
    reason: str | None
    maximum_tone_ms: int | None = None
    realization_hz: tuple[int, int] | None = None


class AdmissionReader(Protocol):
    """Only read operations are available during review."""

    def snapshot(self, target_id: str) -> Target: ...

    def admit(self, target: Target, point: Point, duration_ms: int) -> Admission: ...


@dataclass(frozen=True)
class Timing:
    startup_ms: int
    ready_status_ms: int
    read_ms: int
    spacing_ms: int
    stop_ms: int
    point_overhead_ms: int
    preparation_ms: int
    drive_change_ms: int
    settle_attempts: int = 3
    samples: int = 3

    def __post_init__(self):
        for key, value in asdict(self).items():
            minimum = 1 if key in ("startup_ms", "read_ms", "stop_ms", "preparation_ms") else 0
            p.require(
                type(value) is int and minimum <= value <= 3_600_000,
                f"Invalid timing field {key}",
            )
        p.require(self.read_ms <= 30_000, "Read limit exceeds 30 seconds")
        p.require(2 <= self.settle_attempts <= 3, "Plan needs two or three settling attempts")
        p.require(1 <= self.samples <= 3, "Plan needs one to three retained samples")

    @property
    def tone_ms(self):
        # Each read budget includes its meter and source status exchanges. Count any
        # setup/status still needed after keying separately.
        return (
            self.startup_ms
            + self.ready_status_ms
            + (self.settle_attempts + self.samples) * self.read_ms
            + (self.samples - 1) * self.spacing_ms
            + self.stop_ms
        )

    def require_read_window(self, now_ns, hard_end_ns):
        p.require(
            type(now_ns) is int
            and type(hard_end_ns) is int
            and now_ns >= 0
            and now_ns + (self.read_ms + self.stop_ms) * 1_000_000 <= hard_end_ns,
            "Insufficient active time for another reading and verified stop",
        )


@dataclass(frozen=True)
class ReviewTarget:
    reader: AdmissionReader
    timing: Timing
    tolerance_hz: int


@dataclass(frozen=True)
class Disposition:
    point: Point
    reason: str | None
    correction_percent: str | None
    realization_hz: tuple[int, int] | None
    maximum_tone_ms: int | None


@dataclass(frozen=True)
class Review:
    target: Target
    fixture_digest: str
    timing: Timing
    tolerance_hz: int
    include_pdf: bool
    dispositions: tuple[Disposition, ...]
    selected_ids: tuple[str, ...]
    max_run_ms: int

    @property
    def digest(self):
        return r.digest(r.encoded(asdict(self)))

    def public(self):
        return {**asdict(self), "review_digest": self.digest}

    def require_admitted_start(self, reviewed_digest):
        p.require(reviewed_digest == self.digest, "Start differs from the latest live review")
        selected = set(self.selected_ids)
        p.require(
            all(row.reason is None for row in self.dispositions if row.point.point_id in selected),
            "Select and review an admitted matrix before Start",
        )


def _matrix(profile):
    points = []
    for drive in sweep_matrix.PROFILES[profile][1]:
        for band, dial in sweep_matrix.DIALS.items():
            points.append(
                Point(f"P{len(points) + 1:03d}", band, dial, dial + sweep_matrix.OFFSET_HZ, drive)
            )
    return tuple(points)


def review(
    reader: AdmissionReader,
    target_id: str,
    *,
    fixture_digest: str,
    timing: Timing,
    tolerance_hz: int,
    include_pdf: bool,
    selected_ids=None,
) -> Review:
    """Review all requested settings without touching the meter or mutating the source."""
    p.require(
        isinstance(fixture_digest, str)
        and len(fixture_digest) == 64
        and all(c in "0123456789abcdef" for c in fixture_digest),
        "Use an immutable fixture snapshot",
    )
    p.require(type(tolerance_hz) is int and tolerance_hz >= 0, "Invalid frequency tolerance")
    p.require(type(include_pdf) is bool, "Invalid report selection")
    p.require(isinstance(timing, Timing), "Invalid timing budget")
    target = reader.snapshot(target_id)
    p.require(
        isinstance(target, Target)
        and target.target_id == target_id
        and isinstance(target.profile, str)
        and target.profile in sweep_matrix.PROFILES
        and target.owner in ("pico", "pi")
        and (
            target.profile == "si5351"
            or (target.profile == "pico-gpio" and target.owner == "pico")
            or (target.profile.startswith("pi-") and target.owner == "pi")
        )
        and all(
            isinstance(value, str) and bool(value)
            for value in (target.device_id, target.boot_id, target.revision, target.output)
        ),
        "Source identity or output profile is unavailable",
    )
    p.require(
        target.idle is True
        and target.output_inactive is True
        and target.restart_pending is False
        and target.schedules_inhibited is True
        and target.active_drive_ma == target.saved_drive_ma
        and type(target.active_drive_ma) is int
        and type(target.saved_drive_ma) is int
        and target.active_drive_ma in sweep_matrix.PROFILES[target.profile][1],
        "Source is unavailable for a fresh live review",
    )
    points = _matrix(target.profile)
    available_ids = {point.point_id for point in points}
    if selected_ids is not None:
        p.require(
            isinstance(selected_ids, (tuple, list))
            and all(isinstance(item, str) for item in selected_ids)
            and len(set(selected_ids)) == len(selected_ids),
            "Invalid reduced point selection",
        )
    selected = available_ids if selected_ids is None else set(selected_ids)
    p.require(bool(selected) and selected <= available_ids, "Invalid reduced point selection")
    selected_points = tuple(point for point in points if point.point_id in selected)

    batch = getattr(reader, "admit_many", None)
    receipts = (
        batch(target, points, timing.tone_ms)
        if batch
        else (reader.admit(target, point, timing.tone_ms) for point in points)
    )
    dispositions = []
    for point, receipt in zip(points, receipts, strict=True):
        p.require(
            isinstance(receipt, Admission) and receipt.point == point and receipt.target == target,
            "Read-only admission belongs to a different point or target revision",
        )
        dispositions.append(_disposition(receipt, timing, tolerance_hz))
    p.require(reader.snapshot(target_id) == target, "Source changed during live review")

    change_count = 0
    if target.owner == "pico":
        drives = (
            target.active_drive_ma,
            *(point.drive_ma for point in selected_points),
            target.active_drive_ma,
        )
        change_count = sum(left != right for left, right in zip(drives, drives[1:], strict=False))
        p.require(change_count == 0 or timing.drive_change_ms > 0, "Missing Pico restart budget")
    max_run = (
        timing.preparation_ms
        + len(selected_points) * (timing.point_overhead_ms + timing.tone_ms)
        + change_count * timing.drive_change_ms
    )
    return Review(
        target,
        fixture_digest,
        timing,
        tolerance_hz,
        include_pdf,
        tuple(dispositions),
        tuple(point.point_id for point in selected_points),
        max_run,
    )


def _disposition(receipt, timing, tolerance_hz):
    point = receipt.point
    reason, cap, bounds = receipt.reason, receipt.maximum_tone_ms, receipt.realization_hz
    commanded = None
    p.require(
        reason is None or (isinstance(reason, str) and 0 < len(reason) <= 120),
        "Invalid owner refusal",
    )
    if reason is None:
        p.require(type(cap) is int and cap > 0, "Missing owner-enforced tone duration limit")
        p.require(
            isinstance(bounds, tuple)
            and len(bounds) == 2
            and all(type(bound) is int and bound > 0 for bound in bounds)
            and bounds[0] <= bounds[1],
            "Missing owner realization or realization bound",
        )
        low, high = bounds
        if timing.tone_ms > cap:
            reason = "tone_budget_exceeds_owner_limit"
        elif max(abs(low - point.carrier_hz), abs(high - point.carrier_hz)) > tolerance_hz:
            reason = "realization_outside_tolerance"
        elif low < TABLE[0][0] or high > TABLE[-1][0]:
            reason = "realization_outside_calibration"
        else:
            # Linear interpolation can turn at a chart knot. Check every knot
            # inside the interval as well as its endpoints.
            checks = (low, high, *(hz for hz, _ in TABLE if low < hz < high))
            factors = {
                correction(PROFILE, SENSOR_SERIAL, hz)["commanded_factor_percent"]
                for hz in (point.carrier_hz, *checks)
            }
            if len(factors) == 1:
                commanded = factors.pop()
            else:
                reason = "realization_crosses_calibration_step"
    return Disposition(point, reason, commanded, bounds, cap)


def stable(previous_w: Decimal, current_w: Decimal, tolerance_w: Decimal) -> bool:
    """Compare signed complete readings without treating stability as above-floor power."""
    p.require(
        all(isinstance(v, Decimal) and v.is_finite() for v in (previous_w, current_w, tolerance_w))
        and tolerance_w >= 0,
        "Invalid settling observation",
    )
    proportional = max(abs(previous_w), abs(current_w)) / 100
    return abs(previous_w - current_w) <= max(tolerance_w, proportional)
