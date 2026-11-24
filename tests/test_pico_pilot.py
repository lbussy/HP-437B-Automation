import csv
import json
import time

import pytest

from hp437b import pico_pilot
from hp437b.live_sweep_review import Target, Timing
from hp437b.live_sweep_window import ActiveWindow, Job, Observation
from hp437b.pico_tone import TONE, PicoTone
from hp437b.reconciliation_physical import PhysicalTarget
from hp437b.simulation import DemoTransport


def test_native_capture_starts_after_correction_and_stops_before_meter_closure(
    tmp_path, monkeypatch
):
    order = []
    job = Job("pico", "device", "boot", "job")
    target = Target(
        "pico", "device", "boot", "rev", "pico", "GP2", "pico-gpio", 12, 12, True, True, False, True
    )
    pilot = pico_pilot.POINT

    class Meter(DemoTransport):
        capabilities = DemoTransport.capabilities | {"go_to_local"}

        def __init__(self, resource):
            super().__init__()

        def open(self, timeout):
            order.append("opened")

        def write(self, data, deadline):
            if data in (b"KB101.1EN", b"TR3"):
                order.append(data)
                return
            super().write(data, deadline)

        def read(self, deadline):
            if self.pending == b"TR2" and "started" in order and "stopped" not in order:
                self.pending = None
                return b"+24.500E-03\r\n"
            return super().read(deadline)

        def return_local(self, deadline):
            order.append("local")

    class Source:
        def observe(self, key, deadline):
            assert key == job
            return Observation(key, time.monotonic_ns(), True, False, pilot.carrier_hz, 12)

        def stop(self, key, deadline):
            assert key == job
            order.append("stopped")
            return Observation(key, time.monotonic_ns(), False, True, None, None)

    monkeypatch.setattr(pico_pilot, "VisaTransport", Meter)
    timing = Timing(1000, 0, 1000, 0, 1000, 0, 1000, 0, samples=2)
    monkeypatch.setattr(pico_pilot, "TIMING", timing)
    cfg = PhysicalTarget("unused", "test", b"HEWLETT-PACKARD,437B,,1.9")

    def launch(stack):
        assert b"KB101.1EN" in order and "started" not in order
        order.append("started")
        return stack.enter_context(
            ActiveWindow(
                Source(),
                target,
                pilot,
                job,
                timing,
                time.monotonic_ns() + 5_000_000_000,
                lambda: False,
            )
        )

    csv_path = tmp_path / "rf-on.csv"
    receipt = pico_pilot._capture(csv_path, cfg, launch=launch)
    assert receipt["rows"] == 2
    assert order.index("stopped") < order.index(b"TR3") < order.index("local")
    assert order.count("stopped") == 1
    window = json.loads((tmp_path / "rf-window.json").read_bytes())
    assert len(window["settling"]) == len(window["brackets"]) == 2
    assert window["stop"]["output_inactive"] is True
    with csv_path.open(newline="") as handle:
        assert [row["value"] for row in csv.DictReader(handle)] == ["0.024500", "0.024500"]


def test_rf_off_baseline_blocks_a_nonzero_signal(tmp_path, monkeypatch):
    path = tmp_path / "off.csv"
    monkeypatch.setattr(
        pico_pilot,
        "_capture",
        lambda *args, **kwargs: path.write_text("status,value\nok,0.001\n"),
    )
    with pytest.raises(ValueError, match="baseline limit"):
        pico_pilot._baseline(path, None)


def test_pico_reconciles_lost_start_and_stop_replies_using_only_exact_status():
    point = pico_pilot.POINT
    target = Target(
        "pico",
        "1" * 32,
        "2" * 32,
        "revision",
        "pico",
        "GP2",
        "pico-gpio",
        12,
        12,
        True,
        True,
        False,
        True,
    )
    request_id, job_id = "3" * 32, "4" * 32
    duration = 107_000
    binding = dict(scope="member", device_id=target.device_id, boot_id=target.boot_id)
    row = dict(
        job_id=job_id,
        request_id=request_id,
        carrier_hz=point.carrier_hz,
        duration_ms=duration,
        rf_pin=2,
        boot_drive_ma=12,
        control_revision="job-revision",
        phase="running",
        outcome=None,
        output_inactive_confirmed=False,
        recovery_required=False,
        pad_readback=dict(
            stage="verified", rf_pin=2, drive_ma=12, epoch="1", observed_monotonic_ns="3"
        ),
    )

    class Link:
        def exchange(self, requests, deadline, *, target):
            assert target == binding and time.monotonic_ns() < deadline
            (request,) = requests
            path = request["path"].removeprefix(TONE)
            seen.append(path.split("?")[0])
            if request["method"] == "POST":
                data = json.loads(request["body"])
                if path == "start":
                    assert data["request_id"] == request_id and request["if_match"] == "revision"
                else:
                    assert path == "stop" and data["job_id"] == job_id
                    assert request["if_match"] == "job-revision"
                    row.update(phase="terminal", outcome="stopped", output_inactive_confirmed=True)
                raise TimeoutError("lost reply")
            active = row["phase"] == "running"
            assert f"device_id={binding['device_id']}&boot_id={binding['boot_id']}" in path
            assert path.endswith(
                f"request_id={request_id}" if len(seen) == 2 else f"job_id={job_id}"
            )
            return target, [
                (
                    200,
                    "job-revision",
                    dict(
                        target=target,
                        contract="Wsprry-Control/1",
                        schema="test-tone-status",
                        receipt="known",
                        job=dict(row),
                        current=dict(owned=active, output_active=active),
                        observation_monotonic_ns="4",
                    ),
                )
            ]

    seen = []
    source = PicoTone(Link(), "pico")
    assessed = dict(
        admission="ready", assessment_revision="revision", proposed_drive_ma=12, boot_drive_ma=12
    )
    tone = source.start(target, point, duration, request_id, assessed)
    deadline = time.monotonic_ns() + 8_000_000_000
    assert source.observe(tone.job, deadline).drive_ma == 12
    assert source.stop(tone.job, deadline).output_inactive is True
    assert source.terminal_receipt["job"]["outcome"] == "stopped"
    assert seen == ["start", "status", "status", "stop", "status"]
