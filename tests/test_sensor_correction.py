"""Serial-specific factors, preflight rejection, and application before acquisition."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from hp437b import guided_sweep as g
from hp437b.instrument import Instrument
from hp437b.logger import collect
from hp437b.sensor_correction import PROFILE, SOURCE, SOURCE_SHA256, TABLE, correction
from hp437b.simulation import DemoTransport


def test_certificate_integrity_and_frequency_interpolation():
    assert hashlib.sha256(Path(SOURCE).read_bytes()).hexdigest() == SOURCE_SHA256
    assert len(TABLE) == 14
    a = correction(PROFILE, "MY41094127", 10_140_200)
    assert a["commanded_factor_percent"] == "101.1"
    assert Decimal(a["interpolated_factor_percent"]) == Decimal("101.098598")
    assert a["bracket"] == [
        {"frequency_hz": 10_000_000, "factor_percent": "101.1"},
        {"frequency_hz": 30_000_000, "factor_percent": "100.9"},
    ]
    assert correction(PROFILE, "MY41094127", 50_000_000)["commanded_factor_percent"] == "99.0"
    assert correction(PROFILE, "MY41094127", 100_000)["commanded_factor_percent"] == "100.7"
    assert correction(PROFILE, "MY41094127", 4_200_000_000)["commanded_factor_percent"] == "93.4"
    # Half-grid ties are explicitly rounded half up, not Python's ties-to-even.
    assert correction(PROFILE, "MY41094127", 15_000_000)["commanded_factor_percent"] == "101.1"


@pytest.mark.parametrize("hz", [True, 10.14e6, "10140200", 99_999, 4_200_000_001, None])
def test_bad_frequency_rejected(hz):
    with pytest.raises(ValueError):
        correction(PROFILE, "MY41094127", hz)


def test_wrong_sensor_or_profile_rejected():
    for profile, serial in [(PROFILE, "3318A09219"), ("generic8482A", "MY41094127")]:
        with pytest.raises(ValueError):
            correction(profile, serial, 10_140_200)


class Wire(DemoTransport):
    def __init__(self, reject=False):
        super().__init__()
        self.writes = []
        self.reject = reject

    def write(self, data, deadline):
        self.writes.append(data)
        if data.startswith(b"KB"):
            if self.reject:
                raise OSError("injected correction write failure")
            return
        super().write(data, deadline)


def test_logger_applies_and_records_factor_before_readings(tmp_path):
    wire = Wire()
    receipt = correction(PROFILE, "MY41094127", 10_140_200)
    record = collect(
        Instrument(wire),
        tmp_path / "point.csv",
        count=2,
        interval=0,
        unit="W",
        simulation=True,
        sensor_correction=receipt,
        sleep=lambda _: None,
    )
    assert wire.writes.index(b"KB101.1EN") < wire.writes.index(b"TR2")
    assert record["sensor_correction"] == {**receipt, "command_sent": True, "status_checked": True}
    assert not any(x.startswith((b"CL", b"ZE", b"ET", b"FR", b"RF")) for x in wire.writes)


def test_invalid_receipt_never_allocates_or_touches_meter(tmp_path):
    wire = Wire()
    receipt = {**correction(PROFILE, "MY41094127", 10_140_200), "commanded_factor_percent": "99.0"}
    with pytest.raises(ValueError):
        collect(Instrument(wire), tmp_path / "point.csv", sensor_correction=receipt)
    assert not wire.writes and not list(tmp_path.iterdir())


def test_failed_factor_write_stops_before_acquisition(tmp_path):
    wire = Wire(reject=True)
    with pytest.raises(OSError):
        collect(
            Instrument(wire),
            tmp_path / "point.csv",
            count=1,
            sensor_correction=correction(PROFILE, "MY41094127", 10_140_200),
        )
    assert b"TR2" not in wire.writes and wire.closed
    record = json.loads((tmp_path / "point.csv.session.json").read_text())
    assert record["status"] == "failed" and record["rows"] == 0


def test_config_exact_frequency_mapping_and_missing_point():
    config = dict(
        resource="USB0::0x03eb::0x2065::TEST::INSTR",
        meter_serial="TEST",
        sensor_serial="MY41094127",
        known_issues=[],
        fixture="fake",
        sensor_correction=dict(
            profile=PROFILE, frequency_hz={"30m": 10_140_200, "20m": 14_097_100}
        ),
    )
    cfg = g.configuration(config)
    assert g.point_correction(cfg, "30m")["commanded_factor_percent"] == "101.1"
    assert g.point_correction(cfg, "20m")["frequency_hz"] == 14_097_100
    with pytest.raises(ValueError, match="frequency missing"):
        g.check_source_plan({**g.example(), "frequencies": ["40m"]}, cfg)
    with pytest.raises(ValueError):
        g.configuration({**config, "sensor_serial": "8482H"})


def test_guided_applies_new_factor_at_each_exact_frequency(tmp_path):
    from datetime import UTC, datetime

    class Gate:
        def cancelled(self):
            return False

        def confirm(self, point, token):
            return dict(
                **point,
                token=token,
                operator="Test operator",
                confirmed_utc=datetime.now(UTC).isoformat(),
                frequency_confirmed=True,
                drive_confirmed=True,
            )

    class OpenWire(Wire):
        def open(self, timeout):
            pass

    wires = []

    def capture(*args, **kwargs):
        wire = OpenWire()
        wires.append(wire)
        return g.capture_point(*args, **kwargs, transport_factory=lambda: wire)

    cfg = dict(
        resource="USB0::0x03eb::0x2065::TEST::INSTR",
        meter_serial="TEST",
        sensor_serial="MY41094127",
        known_issues=["Injected fake"],
        fixture="fake",
        sensor_correction=dict(
            profile=PROFILE, frequency_hz={"30m": 10_140_200, "50 MHz": 50_000_000}
        ),
    )
    plan = {
        **g.example(),
        "series": "frequency",
        "frequencies": ["30m", "50 MHz"],
        "drives": ["fixed"],
        "samples": 1,
        "interval_s": 0.1,
        "settling_s": 0,
    }
    result = g.run(
        tmp_path / "guided",
        plan,
        Gate(),
        mode="physical",
        config=cfg,
        prepared=dict.fromkeys(g.PREPARED, True),
        capture=capture,
    )
    assert result["completed_points"] == 2
    assert b"KB101.1EN" in wires[0].writes and b"KB99.0EN" in wires[1].writes
    assert all(w.closed for w in wires)
    assert g.load(tmp_path / "guided")[1] == result


def test_cli_rejects_mismatched_sensor_before_open(tmp_path, monkeypatch):
    from hp437b import cli

    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid profile opened hardware")

    monkeypatch.setattr(cli, "VisaTransport", forbidden)
    assert (
        cli.main(
            [
                "log",
                "--resource",
                "USB0::test::INSTR",
                "--output",
                str(tmp_path / "x.csv"),
                "--sensor-correction",
                PROFILE,
                "--frequency-hz",
                "10140200",
                "--sensor-serial",
                "WRONG",
            ]
        )
        == 1
    )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("index,digit", [(0, "1"), (2, "5"), (23, "1"), (24, "1")])
def test_corrected_capture_stops_on_errors_or_other_active_corrections(tmp_path, index, digit):
    class FlaggedWire(Wire):
        def read(self, deadline):
            is_status = self.pending == b"SM"
            raw = super().read(deadline)
            if is_status:
                raw = bytearray(raw)
                raw[index] = ord(digit)
                raw = bytes(raw)
            return raw

    wire = FlaggedWire()
    with pytest.raises(ValueError, match="error-free status"):
        collect(
            Instrument(wire),
            tmp_path / "point.csv",
            count=1,
            sensor_correction=correction(PROFILE, "MY41094127", 10_140_200),
        )
    record = json.loads((tmp_path / "point.csv.session.json").read_text())
    assert record["rows"] == 0 and record["status"] == "failed"
    assert record["sensor_correction"]["command_sent"] is True
    assert record["sensor_correction"]["status_checked"] is False
