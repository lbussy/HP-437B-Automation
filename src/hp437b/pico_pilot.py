"""One conducted 30 m Test Tone pilot with the HP 437B and 8482A."""

import argparse
import csv
import time
import uuid
from contextlib import ExitStack
from dataclasses import asdict, replace
from decimal import Decimal
from pathlib import Path

from . import diagnostics_physical as diagnostics
from . import provenance as p
from . import reporting as r
from . import sweep_matrix
from .instrument import Instrument
from .live_sweep_review import Point, Timing, stable
from .live_sweep_window import ActiveWindow
from .logger import _atomic_json, collect
from .pico_tone import PicoTone, UsbHost, UsbLink
from .reconciliation import _lease
from .reconciliation_physical import PhysicalTarget, _matching_usb
from .sensor_correction import PROFILE, SENSOR_SERIAL, correction
from .transport import VisaTransport
from .workflow_report import _seal

SCHEMA = "hp437b.pico-pilot.v1"
DIAL_HZ = sweep_matrix.DIALS["30m"]
POINT = Point("P001", "30m", DIAL_HZ, DIAL_HZ + sweep_matrix.OFFSET_HZ, 12)
TIMING = Timing(
    startup_ms=8000,
    ready_status_ms=0,
    read_ms=18_000,
    spacing_ms=1000,
    stop_ms=8000,
    point_overhead_ms=80_000,
    preparation_ms=140_000,
    drive_change_ms=0,
    samples=2,
)
# This is a proposed review budget. It is not a multi-drive execution guarantee.
MATRIX_REVIEW_TIMING = replace(TIMING, drive_change_ms=120_000, preparation_ms=260_000)
PREPARED = (
    "pico_gp2_direct_to_sensor",
    "8482a_my41094127_on_sensor",
    "meter_warmed_and_prepared_cal",
    "power_ref_off",
    "other_control_apps_closed",
    "operator_at_bench",
)
MAX_W = Decimal("0.1")
READ_TOLERANCE_W = Decimal("0.0000002")
BASELINE_LIMIT_W = Decimal("0.000005")


def _idle(target):
    p.require(
        target.idle
        and target.output_inactive
        and target.schedules_inhibited
        and not target.restart_pending
        and target.active_drive_ma == POINT.drive_ma
        and target.saved_drive_ma in (None, POINT.drive_ma),
        "Pico must be idle, RF off, schedules disabled, and at the expected 12 mA",
    )


def review(source):
    target = source.snapshot(source.target_id)
    _idle(target)
    assessed = source.assess(target, POINT, TIMING.tone_ms)
    p.require(
        assessed["admission"] == "ready" and assessed["maximum_duration_ms"] >= TIMING.tone_ms,
        "Pico refused the exact 30 m pilot: " + ", ".join(assessed["reasons"]),
    )
    row = assessed["realization"]
    expected = POINT.carrier_hz * 10**9
    p.require(
        int(row["requested_nhz"]) == expected
        and abs(int(row["programmed_nhz"]) - expected) + int(row["quantization_bound_nhz"])
        <= 10**9,
        "Pilot realization exceeds the reviewed 1 Hz tolerance",
    )
    factor = correction(PROFILE, SENSOR_SERIAL, POINT.carrier_hz)["commanded_factor_percent"]
    p.require(
        all(
            correction(PROFILE, SENSOR_SERIAL, hz)["commanded_factor_percent"] == factor
            for hz in range(POINT.carrier_hz - 1, POINT.carrier_hz + 2)
        ),
        "Pilot realization bound crosses a CAL FAC step",
    )
    return target, assessed


class PilotMeter(Instrument):
    """Use native logger records while controlling Start after the RF-off setup."""

    def __init__(self, transport, expected_idn, *, launch=None, timing=None, allow_limited=False):
        super().__init__(transport, timeout=30)
        self.expected_idn, self.launch = expected_idn, launch
        self.cleanup_stack = ExitStack()
        self.window = None
        self.prepared = False
        self.samples_taken = 0
        self.settling = []
        self.brackets = []
        self.status_frames = []
        self.timing = timing or TIMING
        self.allow_limited = allow_limited

    def identify(self):
        result = super().identify()
        p.require(result.raw.rstrip(b"\r\n") == self.expected_idn, "Meter identity changed")
        return result

    def read_status(self):
        status = super().read_status()
        p.require(
            status.unit == "W"
            and not any(
                (
                    status.reference_on,
                    status.entry_error,
                    status.measurement_error,
                    status.offset_on,
                    status.duty_on,
                )
            ),
            "External W capture requires RF reference, offset, duty, and error flags off",
        )
        self.prepared = True
        return status

    def _read_with_status(self, deadline_ns):
        try:
            self.timeout = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
            reading = self._parsed_sample()
            self.timeout = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
            self.status_frames.append(self.read_status().raw.hex())
            return reading
        finally:
            self.timeout = 30

    def _parsed_sample(self):
        reading = super().acquire("TR2")
        p.require(
            reading.error_code is None and reading.value is not None and reading.value <= MAX_W,
            "Meter error or reading above the prepared sensor input limit",
        )
        return reading

    def acquire(self, trigger="TR2"):
        p.require(trigger == "TR2", "Use delayed-trigger TR2 for the pilot")
        if not self.prepared or self.launch is None:
            return self._parsed_sample()
        if self.window is None:
            self.window = self.launch(self.cleanup_stack)
            for _ in range(self.timing.settle_attempts):
                reading, bracket = self.window.read(self._read_with_status)
                self.settling.append(
                    {
                        "raw_hex": reading.raw.hex(),
                        "value_W": str(reading.value),
                        "bracket": asdict(bracket),
                    }
                )
                if len(self.settling) > 1 and stable(
                    Decimal(self.settling[-2]["value_W"]), reading.value, READ_TOLERANCE_W
                ):
                    break
            else:
                raise ValueError("The two successive settling readings did not agree")
        reading, bracket = self.window.read(
            self._read_with_status, final=self.samples_taken + 1 == self.timing.samples
        )
        p.require(
            self.allow_limited or reading.value > BASELINE_LIMIT_W,
            "The 30 m indication did not exceed the pilot's RF-off limit",
        )
        self.brackets.append(asdict(bracket))
        self.samples_taken += 1
        return reading

    def close(self):
        try:
            self.cleanup_stack.close()
        finally:
            super().close()


def _capture(path, config, *, launch=None, point=POINT, timing=None, context=None):
    transport = VisaTransport(config.resource)
    timing = timing or TIMING
    meter = PilotMeter(
        transport,
        config.expected_idn,
        launch=launch,
        timing=timing,
        allow_limited=context is not None,
    )
    try:
        record = collect(
            meter,
            path,
            count=timing.samples if launch else 1,
            interval=timing.spacing_ms / 1000,
            unit="W",
            connect=lambda: transport.open(30),
            sensor_correction=correction(PROFILE, SENSOR_SERIAL, point.carrier_hz),
            context=context
            if context is not None
            else {
                "pilot": asdict(point),
                "sensor_serial": SENSOR_SERIAL,
                "measurement_plane": "meter_indication_at_sensor_input",
            },
        )
        p.require(
            record.get("instrument_cleanup", {}).get("status") == "accepted",
            "Meter TR3 and Go To Local closure are unconfirmed",
        )
        return record
    finally:
        if launch:
            _atomic_json(
                path.with_name("rf-window.json"),
                {
                    "settling": meter.settling,
                    "brackets": meter.brackets,
                    "status_frames": meter.status_frames,
                    "stop": asdict(meter.window.stop_observation)
                    if meter.window and meter.window.stop_observation
                    else None,
                },
            )


def _baseline(path, config):
    _capture(path, config)
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    p.require(
        len(rows) == 1
        and rows[0]["status"] == "ok"
        and abs(Decimal(rows[0]["value"])) <= BASELINE_LIMIT_W,
        "RF-off indication exceeds the reviewed 5 µW baseline limit",
    )
    return rows[0]["value"]


def wait_running(source, tone, window, launch_by, cancelled):
    while time.monotonic_ns() < launch_by and not cancelled():
        observed = source.observe(tone.job, min(launch_by, window.stop_by_ns))
        if observed.active:
            return window
        if observed.output_inactive:
            break
        time.sleep(0.1)
    if cancelled():
        raise KeyboardInterrupt("Stopped while waiting for the Pico tone")
    raise ValueError("Pico did not confirm a matching running tone in time")


def zero_meter(output, config, lock_root, meter_serial, cancelled):
    zero = diagnostics.run_physical(
        output,
        target=config,
        confirmed=True,
        prior_worker_stopped=True,
        prepared={
            **dict.fromkeys(diagnostics.PREPARED, True),
            "no_rf_input": True,
            "warmed_up": True,
        },
        equipment={"meter_serial": meter_serial, "sensor_serial": SENSOR_SERIAL},
        workflow_lock_root=lock_root,
        supervised_zero=True,
        confirmed_zero=True,
        work_s=45,
        total_s=50,
        cancelled=cancelled,
    )
    p.require(
        zero["status"] == "completed"
        and zero["zero_assessment"]["accepted_full_case"]
        and zero["transport_closed"],
        "Fresh supervised ZERO or its closure is unconfirmed",
    )


def run(source, output, config, lock_root, prepared, *, cancelled=lambda: False):
    p._keys(prepared, PREPARED)
    p.require(
        all(value is True for value in prepared.values()), "Confirm the current conducted setup"
    )
    config.validate()
    target, assessed = review(source)
    output = Path(output)
    output.mkdir(parents=True, mode=0o700)
    run_id = uuid.uuid4().hex
    receipt = {
        "schema": SCHEMA,
        "run_id": run_id,
        "status": "preparing",
        "target": asdict(target),
        "point": asdict(POINT),
        "timing": asdict(TIMING),
        "prepared": prepared,
        "preflight": assessed,
    }
    pending = Path(lock_root) / (r.digest(target.device_id.encode()) + ".test-tone-pending.json")
    meter_lock = Path(lock_root) / (r.digest(config.resource.encode()) + ".lock")
    source_lock = pending.with_suffix(".lock")
    try:
        with _lease(source_lock):
            p.require(not pending.exists(), "An earlier Pico pilot needs reconciliation")
            zero_meter(output / "zero", config, lock_root, "3125U22346", cancelled)
            with _lease(meter_lock):
                _matching_usb(config.adapter_identity)
                _idle(source.snapshot(source.target_id))
                receipt["rf_off_before_W"] = _baseline(output / "rf-off-before.csv", config)

                def launch(stack):
                    current, latest = review(source)
                    p.require(
                        current == target and not cancelled(), "Pico setup changed before Start"
                    )
                    request_id = uuid.uuid4().hex
                    receipt.update(status="start_requested", request_id=request_id)
                    _atomic_json(output / "pilot.json", receipt)
                    _atomic_json(pending, receipt)
                    if cancelled():
                        pending.unlink()
                        raise KeyboardInterrupt("Pico pilot cancelled before Start")
                    launch_by = time.monotonic_ns() + TIMING.startup_ms * 1_000_000
                    tone = source.start(current, POINT, TIMING.tone_ms, request_id, latest)
                    window = stack.enter_context(
                        ActiveWindow(
                            source, current, POINT, tone.job, TIMING, tone.hard_end_ns, cancelled
                        )
                    )
                    receipt["job"] = asdict(tone)
                    _atomic_json(output / "pilot.json", receipt)
                    _atomic_json(pending, receipt)
                    return wait_running(source, tone, window, launch_by, cancelled)

                try:
                    _capture(output / "rf-on.csv", config, launch=launch)
                finally:
                    window_file = output / "rf-window.json"
                    if window_file.is_file() and p._json(window_file.read_bytes())["stop"]:
                        pending.unlink(missing_ok=True)
                    if source.terminal_receipt is not None:
                        _atomic_json(output / "terminal.json", source.terminal_receipt)
                _idle(source.snapshot(source.target_id))
                receipt["rf_off_after_W"] = _baseline(output / "rf-off-after.csv", config)
                p.require(source.terminal_receipt is not None, "Pico terminal receipt is missing")
                terminal = source.terminal_receipt["job"]
                elapsed = int(terminal["ended_monotonic_ns"]) - int(terminal["launch_monotonic_ns"])
                p.require(
                    terminal["outcome"] == "stopped" and 0 < elapsed < TIMING.tone_ms * 1_000_000,
                    "The identified Pico job did not confirm early Stop",
                )
                receipt["rf_on_elapsed_ns"] = elapsed
                receipt["status"] = "completed"
    except BaseException as exc:
        receipt.update(status="failed", error=type(exc).__name__)
        raise
    finally:
        _atomic_json(output / "pilot.json", receipt)
        _seal(output, {"schema": SCHEMA, "mode": "physical", "run_id": run_id})
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("review", "run"))
    parser.add_argument("--usb-target", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--meter-resource")
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--workflow-lock-root", type=Path)
    args = parser.parse_args()
    pico = PicoTone(UsbLink(UsbHost.from_file(args.usb_target)), "pico-pilot")
    if args.action == "review":
        target, assessed = review(pico)
        print(r.encoded({"target": asdict(target), "review": assessed}).decode(), end="")
        return
    if any(
        value is None
        for value in (args.output, args.meter_resource, args.prepared, args.workflow_lock_root)
    ):
        parser.error(
            "run requires --output, --meter-resource, --prepared, and --workflow-lock-root"
        )
    prepared = p._json(args.prepared.read_bytes())
    meter = PhysicalTarget(
        args.meter_resource, "HEWLETT-PACKARD_437B_2.0", b"HEWLETT-PACKARD,437B,,2.0"
    )
    cancel_file = args.output.with_suffix(".cancel")
    result = run(
        pico,
        args.output,
        meter,
        args.workflow_lock_root,
        prepared,
        cancelled=cancel_file.is_file,
    )
    print(r.encoded(result).decode(), end="")


if __name__ == "__main__":
    main()
