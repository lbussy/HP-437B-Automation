import csv
import json
from datetime import UTC, datetime

import pytest

from hp437b.errors import ProtocolError
from hp437b.instrument import Instrument
from hp437b.logger import collect
from hp437b.simulation import DemoTransport

STATUS = b"000000110010001A0002000001\r\n"
SETUP = [
    ("write", b"*IDN?"),
    ("read", b"HEWLETT-PACKARD,437B,,1.9\r\n"),
    ("write", b"RL0"),
    ("write", b"LG"),
    ("write", b"TR2"),
    ("read", b"-3.0000E+01\r\n"),
    ("write", b"SM"),
    ("read", STATUS),
]


def load(path):
    return list(csv.DictReader(path.open())), json.loads(
        path.with_name(path.name + ".session.json").read_text()
    )


def test_synthetic_session_and_units(tmp_path):
    path = tmp_path / "demo.csv"
    wire = DemoTransport()
    record = collect(Instrument(wire), path, count=2, interval=0, unit="W", simulation=True)
    rows, saved = load(path)
    assert wire.closed and record["status"] == saved["status"] == "completed"
    assert saved["simulation"] is True and saved["rows"] == 2
    assert [r["value"] for r in rows] == ["0.0000010000"] * 2
    assert all(r["unit"] == "W" and r["received_utc"].endswith("+00:00") for r in rows)
    assert rows[0]["raw_hex"] == b"+1.0000E-06\r\n".hex()
    assert "initial_status_raw_hex" in saved


def test_error_sentinel_is_recorded_then_collection_continues(tmp_path, scripted):
    wire = scripted(
        SETUP
        + [
            ("write", b"TR2"),
            ("read", b"9.0031E+40\r\n"),
            ("write", b"TR2"),
            ("read", b"-3.0000E+01\r\n"),
        ]
    )
    path = tmp_path / "measurement.csv"
    collect(Instrument(wire), path, count=2, interval=0)
    rows, saved = load(path)
    assert rows[0]["value"] == "" and rows[0]["instrument_error"] == "31"
    assert rows[0]["status"] == "instrument_error" and rows[1]["status"] == "ok"
    assert saved["status"] == "completed" and wire.closed


@pytest.mark.parametrize(
    "reply,expected",
    [
        (b"MALFORMED\r\n", "failed"),
        (KeyboardInterrupt(), "interrupted"),
        (OSError("disconnected"), "failed"),
    ],
)
def test_failure_partial_csv_and_sidecar(tmp_path, scripted, reply, expected):
    wire = scripted(SETUP + [("write", b"TR2"), ("read", reply)])
    path = tmp_path / "partial.csv"
    with pytest.raises((ProtocolError, KeyboardInterrupt, OSError)):
        collect(Instrument(wire), path, count=5, interval=0)
    rows, saved = load(path)
    assert len(rows) == saved["rows"] == 1 and saved["status"] == expected
    assert rows[0]["status"] == expected and wire.closed and not wire.steps
    if isinstance(reply, bytes):
        assert rows[0]["raw_hex"] == reply.hex() == saved["last_raw_hex"]


def test_output_conflicts_do_not_connect_or_replace(tmp_path):
    path = tmp_path / "existing.csv"
    path.write_text("precious\n")
    connected = []
    with pytest.raises(FileExistsError):
        collect(Instrument(DemoTransport()), path, connect=lambda: connected.append(True))
    assert path.read_text() == "precious\n" and not connected
    path.unlink()
    metadata = path.with_name(path.name + ".session.json")
    metadata.write_text("precious metadata")
    with pytest.raises(FileExistsError):
        collect(Instrument(DemoTransport()), path)
    assert not path.exists() and metadata.read_text() == "precious metadata"


@pytest.mark.parametrize(
    "options",
    [
        {"count": 0},
        {"interval": float("nan")},
        {"duration": float("inf")},
        {"count": None},
        {"unit": "INVALID"},
    ],
)
def test_invalid_settings_before_output_or_connection(tmp_path, options):
    connected = []
    with pytest.raises(ValueError):
        collect(
            Instrument(DemoTransport()),
            tmp_path / "bad.csv",
            connect=lambda: connected.append(True),
            **options,
        )
    assert not list(tmp_path.iterdir()) and not connected


def test_setup_failure_closes_and_records_error(tmp_path, scripted):
    wire = scripted([("write", b"*IDN?"), ("read", b"WRONG\r\n")])
    path = tmp_path / "setup.csv"
    with pytest.raises(ProtocolError):
        collect(Instrument(wire), path)
    rows, saved = load(path)
    assert not rows and saved["rows"] == 0 and saved["status"] == "failed" and wire.closed


def test_duration_and_overrun_scheduling(tmp_path):
    class Clock:
        now = 0.0
        waits = []

        def tick(self):
            return self.now

        def sleep(self, amount):
            self.waits.append(amount)
            self.now += amount

    clock = Clock()

    class Slow(DemoTransport):
        def read(self, deadline):
            if self.pending == b"TR2":
                clock.now += 2.0
            return super().read(deadline)

    path = tmp_path / "timed.csv"
    collect(
        Instrument(Slow()),
        path,
        count=None,
        duration=3.0,
        interval=1.0,
        clock=clock.tick,
        sleep=clock.sleep,
        utcnow=lambda: datetime(2026, 11, 11, tzinfo=UTC),
    )
    rows, saved = load(path)
    assert len(rows) == 2 and saved["status"] == "completed"
    assert [float(row["elapsed_s"]) for row in rows] == [2.0, 4.0]
    assert [float(row["overrun_s"]) for row in rows] == [0.0, 1.0]
    assert clock.waits == []  # No catch-up burst/backlog; final operation can extend duration.


def test_resource_cleanup_failure_is_recorded(tmp_path):
    class CloseFailure(DemoTransport):
        def close(self):
            raise OSError("close failed")

    path = tmp_path / "cleanup.csv"
    with pytest.raises(OSError, match="close failed"):
        collect(Instrument(CloseFailure()), path, count=1, interval=0, simulation=True)
    _, record = load(path)
    assert record["status"] == "failed" and "close failed" in record["cleanup_error"]


@pytest.mark.parametrize("fail", [False, True])
def test_logger_records_local_return_and_never_hides_rejection(tmp_path, fail):
    class LocalDemo(DemoTransport):
        capabilities = DemoTransport.capabilities | {"go_to_local"}
        local_return = None

        def write(self, data, deadline):
            if data != b"TR3":
                return super().write(data, deadline)

        def return_local(self, deadline):
            self.local_return = {"status": "failed" if fail else "accepted"}
            if fail:
                raise OSError("GTL rejected")

    wire = LocalDemo()
    path = tmp_path / "local.csv"
    if fail:
        with pytest.raises(OSError, match="GTL rejected"):
            collect(Instrument(wire), path, count=1, interval=0, simulation=True)
    else:
        collect(Instrument(wire), path, count=1, interval=0, simulation=True)
    rows, record = load(path)
    assert len(rows) == 1
    assert record["local_return"]["status"] == ("failed" if fail else "accepted")
    assert record["status"] == ("failed" if fail else "completed")
    assert record["instrument_cleanup"]["sequence"] == "TR3 then USB488 GTL"
    assert record["instrument_cleanup"]["status"] == ("failed" if fail else "accepted")
    assert wire.closed


def test_metadata_disk_failure_still_closes_resource(tmp_path, monkeypatch):
    import hp437b.logger as logger

    wire = DemoTransport()

    def fail(path, value):
        raise OSError("disk unavailable")

    monkeypatch.setattr(logger, "_atomic_json", fail)
    with pytest.raises(OSError):
        collect(Instrument(wire), tmp_path / "disk.csv", count=1)
    assert wire.closed


def test_changed_units_are_preserved_and_stop_collection(tmp_path):
    from hp437b.errors import StateUncertain

    class Changed(Instrument):
        calls = 0

        def acquire(self, trigger="TR2"):
            self.calls += 1
            if self.calls > 1:
                self.command("LN")
            return super().acquire(trigger)

    path = tmp_path / "units.csv"
    with pytest.raises(StateUncertain, match="Units changed"):
        collect(Changed(DemoTransport()), path, count=3, interval=0, simulation=True)
    rows, record = load(path)
    assert len(rows) == 1 and record["status"] == "failed"
    assert rows[0]["unit"] == "W" and rows[0]["value"] == "0.0000010000"


def test_csv_close_failure_is_reported_and_resource_closed(tmp_path, monkeypatch):
    from pathlib import Path

    original_open = Path.open
    path = tmp_path / "close.csv"
    wire = DemoTransport()

    class Wrapped:
        def __init__(self, handle):
            self.handle = handle

        def __getattr__(self, key):
            return getattr(self.handle, key)

        def close(self):
            self.handle.close()
            raise OSError("csv close failed")

    def patched_open(self, *args, **kwargs):
        handle = original_open(self, *args, **kwargs)
        return Wrapped(handle) if self == path and args and args[0] == "x" else handle

    monkeypatch.setattr(Path, "open", patched_open)
    with pytest.raises(OSError, match="csv close failed"):
        collect(Instrument(wire), path, count=1, interval=0, simulation=True)
    _, saved = load(path)
    assert wire.closed and saved["status"] == "failed" and "csv close failed" in saved["file_error"]


def test_fresh_measurement_precedes_sm_after_configuration(tmp_path, scripted):
    wire = scripted(SETUP + [("write", b"TR2"), ("read", b"-3.0000E+01\r\n")])
    path = tmp_path / "fresh.csv"
    collect(Instrument(wire), path, count=1, interval=0)
    rows, record = load(path)
    assert len(rows) == 1
    assert wire.calls[4:8] == [("write", b"TR2"), ("read", None), ("write", b"SM"), ("read", None)]
    assert record["setup_measurement_raw_hex"] == b"-3.0000E+01\r\n".hex()
