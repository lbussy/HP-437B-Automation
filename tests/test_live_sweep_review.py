"""Read-only review against injected controller observations."""

import threading
import time
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from urllib.error import HTTPError

import pytest

from hp437b import live_sweep_review as live
from hp437b import live_sweep_window as window
from hp437b.guided_client import Client
from hp437b.operator_jobs import Jobs
from hp437b.operator_ui import server

TIMING = live.Timing(
    startup_ms=2500,
    ready_status_ms=1000,
    read_ms=7600,
    spacing_ms=1000,
    stop_ms=4000,
    point_overhead_ms=3000,
    preparation_ms=90_000,
    drive_change_ms=20_000,
)


class Owner:
    def __init__(self, owner="pico", profile="pico-gpio", *, cap=60_000):
        self.target = live.Target(
            "selected",
            "device",
            "boot",
            "R1",
            owner,
            "GP2" if owner == "pico" else "GPIO4",
            profile,
            4,
            4,
            True,
            True,
            False,
            True,
        )
        self.received = []
        self.cap = cap
        self.forbidden = set()

    def snapshot(self, target_id):
        assert target_id == self.target.target_id
        return self.target

    def admit(self, target, point, duration_ms):
        self.received.append((point.band, point.carrier_hz, point.drive_ma, duration_ms))
        if (point.band, point.drive_ma) in self.forbidden:
            return live.Admission(point, target, "unsupported_band_or_drive")
        return live.Admission(point, target, None, self.cap, (point.carrier_hz, point.carrier_hz))


def review(owner, **overrides):
    return live.review(
        owner,
        "selected",
        **{
            "fixture_digest": "f" * 64,
            "timing": TIMING,
            "tolerance_hz": 1,
            "include_pdf": False,
            **overrides,
        },
    )


@pytest.mark.parametrize(
    "owner,profile,drives",
    [
        ("pico", "pico-gpio", (2, 4, 8, 12)),
        ("pi", "pi-bcm283x", (2, 4, 6, 8, 10, 12, 14, 16)),
        ("pi", "pi-bcm2711", (1, 2, 3, 4, 5, 6, 7, 8)),
        ("pi", "pi-rp1", (2, 4, 8, 12)),
        ("pico", "si5351", (2, 4, 6, 8)),
    ],
)
def test_review_submits_each_absolute_carrier_once_and_freezes_matrix(owner, profile, drives):
    frequencies = [
        ("2200m", 137500),
        ("630m", 475700),
        ("160m", 1838100),
        ("80m", 3570100),
        ("60m", 5366200),
        ("40m", 7040100),
        ("30m", 10140200),
        ("20m", 14097100),
        ("17m", 18106100),
        ("15m", 21096100),
        ("12m", 24926100),
        ("10m", 28126100),
        ("6m", 50294500),
    ]
    if profile == "si5351":
        frequencies.append(("2m", 144490500))
    source = Owner(owner, profile)
    proposal = review(source)
    proposal.require_admitted_start(proposal.digest)
    assert source.received == [
        (band, rf, drive, 55100) for drive in drives for band, rf in frequencies
    ]
    total = len(drives) * len(frequencies)
    assert len(proposal.dispositions) == len(proposal.selected_ids) == total
    assert proposal.dispositions[6].correction_percent == "101.1"
    # Initial 4 mA to 2 mA, three transitions, and restoration to 4 mA.
    restart_cost = 5 * TIMING.drive_change_ms if owner == "pico" else 0
    assert proposal.max_run_ms == 90_000 + total * 58100 + restart_cost


def test_pico_si5351_requires_full_review_and_blocks_a_refused_2m_drive():
    source = Owner(profile="si5351")
    with pytest.raises(ValueError, match="full 56-point"):
        review(source, selected_ids=["P001"])
    assert not source.received

    source.forbidden.add(("2m", 6))
    proposal = review(source)
    row = proposal.dispositions[41]
    assert (row.point.point_id, row.point.carrier_hz, row.point.drive_ma) == ("P042", 144490500, 6)
    assert row.reason == "unsupported_band_or_drive"
    with pytest.raises(ValueError, match="admitted matrix"):
        proposal.require_admitted_start(proposal.digest)


def test_refused_row_remains_visible_and_reduction_invalidates_prior_review():
    source = Owner("pi", "pi-rp1")
    source.forbidden.add(("6m", 12))
    proposal = review(source)
    assert proposal.dispositions[-1].reason == "unsupported_band_or_drive"
    with pytest.raises(ValueError, match="admitted matrix"):
        proposal.require_admitted_start(proposal.digest)
    reduced = review(source, selected_ids=proposal.selected_ids[:-1])
    assert reduced.dispositions == proposal.dispositions
    assert reduced.selected_ids == proposal.selected_ids[:-1]
    with pytest.raises(ValueError, match="differs from"):
        reduced.require_admitted_start(proposal.digest)
    reduced.require_admitted_start(reduced.digest)
    assert replace(reduced, include_pdf=True).digest != reduced.digest
    assert replace(reduced, fixture_digest="a" * 64).digest != reduced.digest


@pytest.mark.parametrize(
    "edits", [{"restart_pending": True}, {"output_inactive": False}, {"schedules_inhibited": False}]
)
def test_unsafe_snapshot_refused_before_any_admission(edits):
    source = Owner()
    source.target = replace(source.target, **edits)
    with pytest.raises(ValueError, match="unavailable"):
        review(source)
    assert source.received == []


def test_admission_fails_if_target_changes_during_review():
    class Rebooting(Owner):
        def snapshot(self, target_id):
            target = super().snapshot(target_id)
            return replace(target, boot_id="new") if self.received else target

    with pytest.raises(ValueError, match="changed during"):
        review(Rebooting())


def test_owner_cap_reserve_and_signed_stability():
    proposal = review(Owner(cap=55_099))
    assert {row.reason for row in proposal.dispositions} == {"tone_budget_exceeds_owner_limit"}
    end = 60_000_000_000
    TIMING.require_read_window(48_400_000_000, end)
    with pytest.raises(ValueError, match="verified stop"):
        TIMING.require_read_window(48_400_000_001, end)
    assert live.stable(Decimal("-0.000000001"), Decimal("0"), Decimal("0.000000001"))
    assert not live.stable(Decimal("0.001"), Decimal("0.0011"), Decimal("0.000000001"))


def test_reported_realization_must_remain_in_tolerance_and_at_same_cal_factor():
    class OffFrequency(Owner):
        def admit(self, target, point, duration_ms):
            result = super().admit(target, point, duration_ms)
            if point.band == "30m":
                return replace(
                    result, realization_hz=(point.carrier_hz, point.carrier_hz + 6_000_000)
                )
            return result

    assert review(OffFrequency()).dispositions[6].reason == "realization_outside_tolerance"
    wide = review(OffFrequency(), tolerance_hz=6_000_000)
    assert wide.dispositions[6].reason == "realization_crosses_calibration_step"


def test_local_review_service_never_creates_or_starts_a_job(tmp_path):
    source = Owner("pi", "pi-bcm2711")
    with (
        closing(
            Jobs(
                tmp_path,
                plots=False,
                sweep_config=dict(
                    resource="USB0::0x03eb::0x2065::TEST::INSTR",
                    meter_serial="test only",
                    sensor_serial="MY41094127",
                    known_issues=[],
                    fixture="injected review fixture",
                ),
                live_review_targets={"selected": live.ReviewTarget(source, TIMING, 1)},
            )
        ) as jobs,
        server(jobs, 0) as app,
    ):
        worker = threading.Thread(target=app.serve_forever, daemon=True)
        worker.start()
        try:
            client = Client(f"http://127.0.0.1:{app.server_port}")
            assert client.state()["guided"]["live_review_targets"] == ["selected"]
            with pytest.raises(HTTPError) as unknown:
                client.review_live("127.0.0.1:9999")
            assert unknown.value.code == 400
            assert not source.received
            full = client.review_live("selected")
            reduced = client.review_live("selected", selected_ids=["P005"], include_pdf=True)
            assert len(full["dispositions"]) == len(reduced["dispositions"]) == 104
            assert reduced["selected_ids"] == ["P005"]
            assert full["review_digest"] != reduced["review_digest"]
            assert jobs.state()["jobs"] == []
        finally:
            app.shutdown()
            worker.join(timeout=5)


class Output:
    def __init__(self, point):
        self.point = point
        self.stopped = threading.Event()
        self.stop_calls = []

    def observe(self, job, deadline_ns):
        assert time.monotonic_ns() <= deadline_ns
        return window.Observation(
            job, time.monotonic_ns(), True, False, self.point.carrier_hz, self.point.drive_ma
        )

    def stop(self, job, deadline_ns):
        self.stop_calls.append(job)
        self.stopped.set()
        return window.Observation(job, time.monotonic_ns(), False, True, None, None)


def active_window(*, output=Output, cancelled=lambda: False):
    proposal = review(Owner())
    point = proposal.dispositions[0].point
    source = output(point)
    job = window.Job("selected", "device", "boot", "test-job-1")
    timing = replace(TIMING, read_ms=1000, stop_ms=2000)
    return window.ActiveWindow(
        source, proposal.target, point, job, timing, time.monotonic_ns() + 5_000_000_000, cancelled
    )


def test_finished_read_has_matching_bracket_and_dispatches_stop_before_cleanup():
    with active_window() as point:
        sample, evidence = point.read(lambda deadline: Decimal("0.004"), final=True)
        assert sample == Decimal("0.004")
        assert (
            evidence.before.observed_ns
            <= evidence.read_started_ns
            <= evidence.read_finished_ns
            <= evidence.after.observed_ns
        )
        assert evidence.before.job == evidence.after.job
        assert point.output.stopped.wait(1)
    assert point.stop_observation.output_inactive is True
    assert point.output.stop_calls == [point.job]


def test_stop_runs_while_meter_is_blocked_and_late_result_is_never_credited():
    cancel, entered, release = (threading.Event() for _ in range(3))
    capture_error = []
    capture_results = []

    def meter_read(_deadline):
        entered.set()
        assert release.wait(2)
        return Decimal("0.004")

    with active_window(cancelled=cancel.is_set) as point:

        def capture():
            try:
                capture_results.append(point.read(meter_read))
            except BaseException as exc:
                capture_error.append(exc)

        meter = threading.Thread(target=capture)
        meter.start()
        try:
            assert entered.wait(1)
            cancel.set()
            assert point.output.stopped.wait(1)
            assert meter.is_alive()
        finally:
            release.set()
            meter.join(1)
    assert not meter.is_alive() and not capture_results
    assert len(capture_error) == 1
    assert point.stop_observation.output_inactive is True


def test_wrong_drive_stops_before_meter_and_wrong_stop_identity_blocks_restart():
    class WrongDrive(Output):
        def observe(self, *args):
            return replace(super().observe(*args), drive_ma=12)

    with (
        pytest.raises(ValueError, match="effective drive"),
        active_window(output=WrongDrive) as point,
    ):
        point.read(lambda _: pytest.fail("meter read issued before drive was confirmed"))
    assert point.stop_observation.output_inactive is True

    class WrongStop(Output):
        def stop(self, *args):
            observed = super().stop(*args)
            return replace(observed, job=replace(observed.job, job_id="different"))

    with pytest.raises(ValueError, match="shutdown is unknown"), active_window(output=WrongStop):
        pass
