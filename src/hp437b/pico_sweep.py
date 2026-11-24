"""Conducted direct-GPIO Pico matrix using the HP 437B and native Test Tone."""

import csv
import shutil
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from . import guided_sweep as guided
from . import live_sweep_review as live
from . import pico_pilot as pilot
from . import protocol, sweep_matrix
from . import provenance as p
from . import reporting as r
from .live_sweep_window import ActiveWindow
from .logger import _atomic_json
from .reconciliation import _lease
from .reconciliation_physical import PhysicalTarget, _matching_usb
from .sensor_correction import PROFILE, SENSOR_SERIAL
from .workflow_report import _seal

SCHEMA = sweep_matrix.PICO_SCHEMA
TIMING = pilot.MATRIX_REVIEW_TIMING
PREPARED = pilot.PREPARED


def configuration(config):
    config = guided.configuration(config)
    p.require(
        config["sensor_serial"] == SENSOR_SERIAL and not guided.reference_source(config),
        "Configure the conducted 8482A MY41094127 fixture for live Pico capture",
    )
    return config


def prepared_check(prepared):
    p._keys(prepared, PREPARED)
    p.require(
        all(value is True for value in prepared.values()),
        "Confirm the complete current Pico bench setup",
    )


def authorization(record, point, token):
    return dict(
        kind="operator-started-pico-sweep",
        run_id=record["run_id"],
        review_digest=record["review"]["review_digest"],
        plan_sha256=r.digest(r.encoded(record["plan"])),
        point=point,
        token=token,
    )


def pending_meter(root, resource):
    return Path(root) / (r.digest(resource.encode()) + ".pico-sweep-pending.json")


def _current(source, expected, *, deadline_ns=None):
    current = source.snapshot(source.target_id, deadline_ns=deadline_ns)
    p.require(
        (current.device_id, current.boot_id, current.profile, current.output)
        == (expected.device_id, expected.boot_id, "pico-gpio", "GP2")
        and current.idle
        and current.output_inactive
        and current.schedules_inhibited
        and not current.restart_pending
        and current.saved_drive_ma == current.active_drive_ma == expected.active_drive_ma,
        "Pico identity, drive, or safe output state changed",
    )
    return current


def _admitted(source, target, point, expected, *, deadline=None, cancelled=lambda: False):
    current = target
    while True:
        if cancelled():
            raise KeyboardInterrupt("Sweep stopped before RF")
        attempt_deadline = min(deadline, time.monotonic_ns() + 8_000_000_000) if deadline else None
        assessed = source.assess(current, point, TIMING.tone_ms, deadline_ns=attempt_deadline)
        if assessed["admission"] == "ready":
            admitted = live._disposition(source._admission(current, point, assessed), TIMING, 1)
            p.require(
                admitted.reason is None and admitted.correction_percent == expected,
                "Pico realization, duration, or sensor correction changed after review",
            )
            return current, assessed
        if not (
            deadline
            and time.monotonic_ns() + 1_000_000_000 < deadline
            and assessed["reasons"] == ["clock_admission_refused"]
        ):
            raise ValueError("Pico refused the reviewed point: " + ", ".join(assessed["reasons"]))
        time.sleep(1)
        current = _current(source, target, deadline_ns=deadline)


def _power_limited(path):
    with path.open(newline="") as stream:
        return any(
            Decimal(row["value"]) <= pilot.BASELINE_LIMIT_W for row in csv.DictReader(stream)
        )


def previous_capture(path, plan, fixture, expected_target):
    previous, result, bundle = guided.load(path)
    prefix = result["completed_points"] + result["limited_points"]
    sequence = previous.get("continuation", {}).get("sequence", 0) + 1
    p.require(
        previous["schema"] == SCHEMA
        and previous["plan"] == plan
        and previous["review_fixture"] == fixture
        and previous["status"] in ("failed", "interrupted")
        and previous["restoration"] == "verified"
        and previous.get("rf_off_after_W") is not None
        and previous.get("final_target") == expected_target
        and 0 < prefix < len(previous["points"])
        and sequence <= 5,
        "Previous capture is ineligible for a known-safe continuation of this sweep",
    )
    return (
        previous,
        result,
        dict(
            run_id=previous["run_id"],
            inventory_sha256=r.digest(bundle.read("artifacts.json")),
            carried_points=prefix,
            sequence=sequence,
        ),
    )


def carried_results(path, record):
    if "continuation" not in record:
        return []
    receipt = record["continuation"]
    p.require(1 <= receipt["sequence"] <= 5, "Invalid Pico continuation history")
    previous, result, observed = previous_capture(
        Path(path) / "prior", record["plan"], record["review_fixture"], record["review"]["target"]
    )
    count = observed["carried_points"]
    p.require(
        receipt == observed
        and record["points"][:count] == previous["points"][:count]
        and record["started_utc"] >= previous["finished_utc"],
        "Pico continuation differs from its sealed earlier capture",
    )
    return result["points"][:count]


def run(
    source,
    output,
    plan,
    fixture,
    lock_root,
    prepared,
    reviewed_digest,
    *,
    operator=None,
    include_pdf=False,
    continue_from=None,
    cancelled=lambda: False,
    emit=lambda **event: None,
):
    """Join the frozen owner review to a single physical run and seal its native evidence."""
    plan = guided.validate(plan)
    p.require(plan["schema"] == SCHEMA, "Use the exact direct-GPIO Pico matrix")
    prepared_check(prepared)
    fixture = configuration(fixture)
    review = live.review(
        source,
        source.target_id,
        fixture_digest=r.digest(r.encoded(fixture)),
        timing=TIMING,
        tolerance_hz=1,
        include_pdf=include_pdf,
    )
    review.require_admitted_start(reviewed_digest)
    p.require(review.target.profile == "pico-gpio", "Use the reviewed direct-GPIO Pico")
    target = original = review.target
    prior = (
        previous_capture(continue_from, plan, fixture, asdict(target)) if continue_from else None
    )
    equipment = dict(
        fixture,
        sensor_correction={
            "profile": PROFILE,
            "frequency_hz": {
                band: dial + sweep_matrix.OFFSET_HZ for band, dial in sweep_matrix.DIALS.items()
            },
        },
    )
    meter = PhysicalTarget(
        fixture["resource"], "HEWLETT-PACKARD_437B_2.0", b"HEWLETT-PACKARD,437B,,2.0"
    )
    meter.validate()
    lock_root = Path(lock_root)
    lock_root.mkdir(parents=True, exist_ok=True)
    source_pending = lock_root / (r.digest(target.device_id.encode()) + ".test-tone-pending.json")
    meter_pending = pending_meter(lock_root, meter.resource)
    meter_lock = lock_root / (r.digest(meter.resource.encode()) + ".lock")
    output = Path(output)
    output.mkdir(parents=True, mode=0o700)
    end = time.monotonic_ns() + review.max_run_ms * 1_000_000
    work_end = end - (TIMING.drive_change_ms + 30_000) * 1_000_000
    record = dict(
        schema=SCHEMA,
        mode="physical",
        run_id=uuid.uuid4().hex,
        plan=plan,
        equipment=equipment,
        prepared=prepared,
        operator=operator,
        review=review.public(),
        review_fixture=fixture,
        started_utc=datetime.now(UTC).isoformat(),
        status="running",
        error=None,
        drive_changes=[],
        points=[dict(point, status="skipped") for point in guided.points(plan)],
        restoration="unverified",
    )
    cursor = 0
    if prior:
        previous, _, continuation = prior
        cursor = continuation["carried_points"]
        record["continuation"] = continuation
        record["points"][:cursor] = previous["points"][:cursor]
        shutil.copytree(continue_from, output / "prior")
        carried_results(output, record)
    state_path = output / "workflow.json"
    _atomic_json(state_path, record)
    source_uncertain = False
    meter_uncertain = False

    def gate():
        return cancelled() or time.monotonic_ns() >= work_end

    def journal(path, phase, **fields):
        _atomic_json(
            path,
            dict(
                run_id=record["run_id"],
                capture=str(output.resolve()),
                phase=phase,
                target=asdict(target),
                **fields,
            ),
        )

    def change(drive, *, restore=False):
        nonlocal target, source_uncertain
        previous = _current(source, target)
        journal(source_pending, "restore-drive" if restore else "change-drive", requested_ma=drive)
        deadline = min(
            end if restore else work_end, time.monotonic_ns() + TIMING.drive_change_ms * 1_000_000
        )
        source_uncertain = True
        target = source.change_drive(previous, drive, deadline)
        source_uncertain = False
        record["drive_changes"].append(
            dict(previous=asdict(previous), current=asdict(target), restoration=restore)
        )
        _atomic_json(state_path, record)
        journal(source_pending, "owned-idle")
        return deadline

    def capture_point(point, disposition):
        nonlocal target, source_uncertain, meter_uncertain
        folder = output / point["point_id"]
        folder.mkdir()
        planned = {key: value for key, value in point.items() if key != "status"}
        request_id = uuid.uuid4().hex
        auth = authorization(record, planned, request_id)
        _atomic_json(folder / "pico-authorization.json", auth)
        point.update(status="running", token=request_id)
        _atomic_json(state_path, record)
        attempted = False

        def launch(stack):
            nonlocal target, source_uncertain, attempted
            target = _current(source, target)
            target, assessed = _admitted(
                source, target, disposition.point, disposition.correction_percent, cancelled=gate
            )
            journal(
                source_pending,
                "start-requested",
                request_id=request_id,
                point=asdict(disposition.point),
            )
            if gate():
                raise KeyboardInterrupt("Sweep stopped before the next tone")
            launch_by = time.monotonic_ns() + TIMING.startup_ms * 1_000_000
            source_uncertain = attempted = True
            tone = source.start(target, disposition.point, TIMING.tone_ms, request_id, assessed)
            window = stack.enter_context(
                ActiveWindow(
                    source, target, disposition.point, tone.job, TIMING, tone.hard_end_ns, gate
                )
            )
            _atomic_json(folder / "tone.json", dict(tone=asdict(tone), review=assessed))
            journal(
                source_pending, "tone-outcome-pending", request_id=request_id, job=asdict(tone.job)
            )
            return pilot.wait_running(source, tone, window, launch_by, gate)

        try:
            pilot._capture(
                folder / "samples.csv",
                meter,
                launch=launch,
                point=disposition.point,
                timing=TIMING,
                context=dict(
                    workflow=SCHEMA,
                    pico_authorization=auth,
                    plan_sha256=auth["plan_sha256"],
                    equipment=equipment,
                    point=planned,
                ),
            )
        finally:
            terminal = source.terminal_receipt if attempted else None
            if terminal and terminal["job"]["request_id"] == request_id:
                _atomic_json(folder / "terminal.json", terminal)
                source_uncertain = False
                journal(source_pending, "owned-idle")
            sidecar = folder / "samples.csv.session.json"
            if sidecar.is_file():
                cleanup = p._json(sidecar.read_bytes()).get("instrument_cleanup", {})
                meter_uncertain = cleanup.get("status") != "accepted"
        p.require(
            terminal is not None and terminal["job"]["outcome"] == "stopped",
            "Pico early Stop did not verify for the retained point",
        )
        point["status"] = "limited" if _power_limited(folder / "samples.csv") else "completed"

    try:
        with _lease(source_pending.with_suffix(".lock")):
            p.require(
                not source_pending.exists() and not meter_pending.exists(),
                "An earlier Pico capture needs supervised reconciliation",
            )
            p.require(_current(source, target) == target, "Pico changed after the frozen review")
            if gate():
                raise KeyboardInterrupt("Sweep stopped before ZERO")
            journal(meter_pending, "zero-pending")
            meter_uncertain = True
            emit(phase="running", current="GUIDED", stage="Fresh supervised ZERO")
            pilot.zero_meter(output / "zero", meter, lock_root, fixture["meter_serial"], gate)
            meter_uncertain = False
            with _lease(meter_lock):
                _matching_usb(meter.adapter_identity)
                target = _current(source, target)
                journal(source_pending, "owned-idle")
                journal(meter_pending, "capture-pending")
                try:
                    meter_uncertain = True
                    record["rf_off_before_W"] = pilot._baseline(output / "rf-off-before.csv", meter)
                    meter_uncertain = False
                    for i, (point, disposition) in enumerate(
                        zip(record["points"], review.dispositions, strict=True)
                    ):
                        if i < cursor:
                            continue
                        if gate():
                            raise KeyboardInterrupt("Sweep stopped at a point boundary")
                        if target.active_drive_ma != point["drive_ma"]:
                            emit(
                                stage=f"Saving {point['drive_ma']} mA and checking the Pico reboot",
                                index=i,
                            )
                            ready_by = change(point["drive_ma"])
                            target, _ = _admitted(
                                source,
                                target,
                                disposition.point,
                                disposition.correction_percent,
                                deadline=ready_by,
                                cancelled=gate,
                            )
                        emit(stage=f"{point['frequency']} · {point['drive']}", index=i)
                        capture_point(point, disposition)
                        _atomic_json(state_path, record)
                        emit(
                            index=i + 1,
                            point_results=guided.analyze_unsealed(output, record)["points"],
                        )
                    record["status"] = "completed"
                finally:
                    if not source_uncertain:
                        try:
                            target = _current(source, target)
                            if target.active_drive_ma != original.active_drive_ma:
                                emit(stage=f"Restoring {original.active_drive_ma} mA")
                                change(original.active_drive_ma, restore=True)
                            record["restoration"] = "verified"
                            record["final_target"] = asdict(target)
                            source_pending.unlink()
                        except (OSError, ValueError):
                            record["restoration"] = "unverified"
                            raise
                        if not meter_uncertain and "rf_off_before_W" in record:
                            meter_uncertain = True
                            record["rf_off_after_W"] = pilot._baseline(
                                output / "rf-off-after.csv", meter
                            )
                            meter_uncertain = False
                    if not meter_uncertain and not source_uncertain:
                        meter_pending.unlink(missing_ok=True)
    except (Exception, KeyboardInterrupt) as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
        for point in record["points"]:
            if point["status"] == "running":
                point["status"] = record["status"]
    finally:
        record["finished_utc"] = datetime.now(UTC).isoformat()
        _atomic_json(state_path, record)
        _seal(output, dict(schema=SCHEMA, mode="physical", run_id=record["run_id"]))
    return guided.load(output)[1]


def validate_window(folder, record, point, values, session):
    """Recheck that every credited read belongs to a matching running and stopped job."""
    tone_record = p._json((folder / "tone.json").read_bytes())
    tone, assessed = tone_record["tone"], tone_record["review"]
    receipt = p._json((folder / "terminal.json").read_bytes())
    window = p._json((folder / "rf-window.json").read_bytes())
    job, terminal = tone["job"], receipt["job"]
    reviewed = record["review"]["target"]
    point_boots = {reviewed["active_drive_ma"]: reviewed["boot_id"]}
    for transition in record["drive_changes"]:
        if not transition["restoration"]:
            observed = transition["current"]
            point_boots[observed["active_drive_ma"]] = observed["boot_id"]
    p.require(
        tone["request_id"] == terminal["request_id"] == point["token"]
        and job["job_id"] == terminal["job_id"]
        and job["target_id"] == reviewed["target_id"]
        and job["device_id"] == receipt["target"]["device_id"] == reviewed["device_id"]
        and job["boot_id"] == receipt["target"]["boot_id"] == assessed["target"]["boot_id"]
        and job["boot_id"] == point_boots[point["drive_ma"]]
        and assessed["target"]["device_id"] == job["device_id"]
        and assessed["admission"] == "ready"
        and tone["carrier_hz"] == terminal["carrier_hz"] == point["carrier_hz"]
        and tone["drive_ma"] == terminal["boot_drive_ma"] == point["drive_ma"]
        and tone["duration_ms"] == terminal["duration_ms"] == TIMING.tone_ms
        and terminal["phase"] == "terminal"
        and terminal["outcome"] == "stopped"
        and terminal["output_inactive_confirmed"] is True
        and terminal["recovery_required"] is False
        and receipt["current"]["output_active"] is False
        and receipt["current"]["owned"] is False
        and receipt["job"]["pad_readback"]["stage"] == "verified"
        and receipt["job"]["pad_readback"]["drive_ma"] == point["drive_ma"]
        and receipt["job"]["pad_readback"]["rf_pin"] == 2
        and int(receipt["job"]["pad_readback"]["epoch"]) > 0
        and 0
        < int(terminal["ended_monotonic_ns"]) - int(terminal["launch_monotonic_ns"])
        < tone["duration_ms"] * 1_000_000
        and session["instrument_cleanup"]["status"] == "accepted",
        "Pico point lacks a matching early Stop or healthy meter closure",
    )
    stop = window["stop"]
    p.require(
        stop["job"] == job
        and stop["active"] is False
        and stop["output_inactive"] is True
        and stop["observed_ns"] <= tone["hard_end_ns"]
        and len(window["brackets"]) == len(values) == TIMING.samples
        and 2 <= len(window["settling"]) <= TIMING.settle_attempts,
        "Pico point does not have a closed acquisition window",
    )
    statuses = [protocol.status(bytes.fromhex(frame)) for frame in window["status_frames"]]
    p.require(
        len(statuses) == len(window["brackets"]) + len(window["settling"])
        and all(
            item.unit == "W"
            and not any(
                (
                    item.reference_on,
                    item.entry_error,
                    item.measurement_error,
                    item.offset_on,
                    item.duty_on,
                )
            )
            for item in statuses
        ),
        "Missing or unsuitable meter status in the active acquisition window",
    )
    previous = 0
    settled = []
    for row in window["settling"]:
        raw = protocol.measurement(bytes.fromhex(row["raw_hex"]), "W")
        p.require(
            raw.value == Decimal(row["value_W"]) and raw.error_code is None,
            "Pico settling evidence differs from its native frame",
        )
        settled.append(raw.value)
    p.require(live.stable(*settled[-2:], pilot.READ_TOLERANCE_W), "Pico settling did not verify")
    for bracket in [*(row["bracket"] for row in window["settling"]), *window["brackets"]]:
        before, after = bracket["before"], bracket["after"]
        for item in (before, after):
            p.require(
                item["job"] == job
                and item["active"] is True
                and item["output_inactive"] is False
                and item["drive_ma"] == point["drive_ma"]
                and item["carrier_hz"] == point["carrier_hz"],
                "A meter read was not bracketed by the matching running Pico job",
            )
        p.require(
            previous
            <= before["observed_ns"]
            <= bracket["read_started_ns"]
            < bracket["read_finished_ns"]
            <= after["observed_ns"]
            <= stop["observed_ns"],
            "Pico measurement times are outside the verified RF window",
        )
        previous = after["observed_ns"]
    p.require(
        (point["status"] == "limited") == any(value <= pilot.BASELINE_LIMIT_W for value in values),
        "Pico low indication classification differs from the native samples",
    )


def validate_run(record, bundle):
    review = record["review"]
    original = review["target"]
    p.require(
        original["profile"] == "pico-gpio"
        and review["fixture_digest"] == r.digest(r.encoded(configuration(record["review_fixture"])))
        and review["review_digest"]
        == r.digest(
            r.encoded({key: value for key, value in review.items() if key != "review_digest"})
        )
        and review["selected_ids"] == [row["point_id"] for row in guided.points(record["plan"])]
        and review["timing"] == asdict(TIMING)
        and len(review["dispositions"]) == len(review["selected_ids"])
        and all(row["reason"] is None for row in review["dispositions"]),
        "Pico Start does not match the frozen review",
    )
    for field in ("rf_off_before_W", "rf_off_after_W"):
        if field in record:
            filename = field.removesuffix("_W").replace("_", "-") + ".csv"
            [row] = list(csv.DictReader(bundle.read(filename).decode().splitlines()))
            native = protocol.measurement(bytes.fromhex(row["raw_hex"]), "W")
            p.require(
                row["status"] == "ok"
                and row["unit"] == "W"
                and native.error_code is None
                and native.value == Decimal(row["value"])
                and native.value == Decimal(record[field])
                and abs(native.value) <= pilot.BASELINE_LIMIT_W,
                "Pico RF-off baseline differs from its native evidence",
            )
    previous = original
    visited_boots = {original["boot_id"]}
    for change in record["drive_changes"]:
        current = change["current"]
        p.require(
            change["previous"]["device_id"] == current["device_id"] == original["device_id"]
            and change["previous"]["boot_id"] == previous["boot_id"]
            and current["boot_id"] not in visited_boots
            and current["saved_drive_ma"]
            == current["active_drive_ma"]
            != previous["active_drive_ma"]
            and current["idle"] is True
            and current["output_inactive"] is True
            and current["schedules_inhibited"] is True
            and current["restart_pending"] is False,
            "Pico drive transition history does not verify",
        )
        previous = current
        visited_boots.add(current["boot_id"])
    if record["status"] == "completed":
        final = record.get("final_target", {})
        zero = bundle.json("zero/diagnostics.json")
        p.require(
            record["restoration"] == "verified"
            and final.get("device_id") == original["device_id"]
            and final.get("boot_id") == previous["boot_id"]
            and final.get("saved_drive_ma")
            == final.get("active_drive_ma")
            == original["active_drive_ma"]
            and final.get("output_inactive") is True
            and final.get("schedules_inhibited") is True
            and record.get("rf_off_before_W") is not None
            and record.get("rf_off_after_W") is not None,
            "Completed Pico sweep lacks restored drive or its RF-off baselines",
        )
        p.require(
            zero["status"] == "completed"
            and zero["zero_assessment"]["accepted_full_case"] is True
            and zero["transport_closed"] is True,
            "Completed Pico sweep has no verified ZERO",
        )
