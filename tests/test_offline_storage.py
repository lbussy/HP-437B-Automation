"""OQ-05 injected task-local storage faults; no disk exhaustion/host changes."""

import csv
import json
from pathlib import Path

import pytest

from hp437b.instrument import Instrument
from hp437b.logger import _atomic_json, collect
from hp437b.simulation import DemoTransport


@pytest.mark.parametrize("operation", ["write", "flush"])
def test_sample_storage_failure_surfaces_and_closes(tmp_path, monkeypatch, operation):
    path = tmp_path / "synthetic.csv"
    original = Path.open
    wire = DemoTransport()

    class Broken:
        def __init__(self, handle):
            self.handle = handle
            self.calls = 0

        def __getattr__(self, name):
            return getattr(self.handle, name)

        def inject(self, *args):
            self.calls += 1
            if self.calls == 2:  # Header succeeds; first CSV sample faults.
                raise OSError("injected sample storage failure")
            return getattr(self.handle, operation)(*args)

    def open_owned(self, *args, **kwargs):
        handle = original(self, *args, **kwargs)
        if self == path and args[:1] == ("x",):
            wrapper = Broken(handle)
            setattr(wrapper, operation, wrapper.inject)
            return wrapper
        return handle

    monkeypatch.setattr(Path, "open", open_owned)
    with pytest.raises(OSError, match="injected sample storage"):
        collect(Instrument(wire), path, count=3, interval=0, simulation=True)
    saved = json.loads(path.with_name(path.name + ".session.json").read_text())
    assert wire.closed and saved["status"] == "failed" and saved["simulation"]
    assert saved["rows"] == 0  # No sample successfully flushed before the exception.
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == (1 if operation == "flush" else 0)
    assert saved["last_raw_hex"] == b"-3.0000E+01\r\n".hex()


@pytest.mark.parametrize("operation", ["replace", "fsync"])
def test_atomic_metadata_failure_preserves_previous_bytes(tmp_path, monkeypatch, operation):
    import hp437b.logger as module

    path = tmp_path / "synthetic.json"
    path.write_bytes(b'{"previous":"durable"}\n')
    before = path.read_bytes()

    def fail(*args):
        raise OSError("injected metadata failure")

    monkeypatch.setattr(module.os, operation, fail)
    with pytest.raises(OSError, match="injected metadata"):
        _atomic_json(path, {"new": "never committed"})
    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [path.name]


def test_final_metadata_failure_preserves_last_running_record(tmp_path, monkeypatch):
    import hp437b.logger as module

    path = tmp_path / "synthetic.csv"
    wire = DemoTransport()
    original = module.os.replace
    calls = 0

    def fail_final(source, destination):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("injected final metadata failure")
        return original(source, destination)

    monkeypatch.setattr(module.os, "replace", fail_final)
    with pytest.raises(OSError, match="injected final metadata"):
        collect(Instrument(wire), path, count=2, interval=0, simulation=True)
    saved = json.loads(path.with_name(path.name + ".session.json").read_text())
    assert wire.closed and saved["status"] == "running" and saved["rows"] == 0
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2 and all(row["status"] == "ok" for row in rows)
    # A failed final replacement cannot promise completed metadata or power-loss durability.
    assert not list(tmp_path.glob(".hp437b-*"))
