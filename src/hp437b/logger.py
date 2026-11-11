"""Finite CSV sessions with explicit provenance, UTC receipt times, and raw evidence."""

import csv
import json
import math
import os
import platform
import tempfile
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .errors import StateUncertain
from .instrument import Instrument

FIELDS = [
    "session_id",
    "sequence",
    "received_utc",
    "elapsed_s",
    "overrun_s",
    "value",
    "unit",
    "status",
    "instrument_error",
    "error",
    "raw_hex",
]


def _atomic_json(path: Path, value: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".hp437b-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def collect(
    instrument: Instrument,
    output: str | Path,
    *,
    count: int | None = 10,
    duration: float | None = None,
    interval: float = 1.0,
    unit: str = "dBm",
    context: dict | None = None,
    connect=None,
    simulation: bool = False,
    clock=time.monotonic,
    sleep=time.sleep,
    utcnow=lambda: datetime.now(UTC),
) -> dict:
    """Reserve outputs, optionally connect, configure absolute units, log, and close.

    duration bounds the start of acquisitions; a final acquisition may last up to
    the operation timeout. Overruns skip backlog rather than burst to catch up.
    The sidecar records completion/failure and the last complete raw response.
    """
    if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 1):
        raise ValueError("count must be a positive integer or None")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("duration must be finite and positive")
    if count is None and duration is None:
        raise ValueError("Choose a finite count or duration")
    if not math.isfinite(interval) or interval < 0:
        raise ValueError("interval must be finite and nonnegative")
    if unit not in ("W", "dBm"):
        raise ValueError("Choose absolute units W or dBm")
    # Validate caller provenance before reserving output or touching hardware.
    user_context = json.loads(json.dumps(context or {}, allow_nan=False))
    started_utc = utcnow().isoformat()
    path = Path(output)
    sidecar = path.with_name(path.name + ".session.json")
    handle = path.open("x", newline="", encoding="utf-8")
    try:
        with sidecar.open("x", encoding="utf-8"):
            pass
    except BaseException:
        handle.close()
        path.unlink()  # This invocation owns the newly created empty CSV only.
        raise
    record = {
        "schema_version": 1,
        "session_id": str(uuid.uuid4()),
        "simulation": simulation,
        "status": "starting",
        "started_utc": started_utc,
        "rows": 0,
        "host": platform.platform(),
        "python": platform.python_version(),
        "settings": {
            "unit": unit,
            "interval_s": interval,
            "count": count,
            "duration_s": duration,
            "operation_timeout_s": instrument.timeout,
        },
        "context": user_context,
    }
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    try:
        writer.writeheader()
        handle.flush()
        _atomic_json(sidecar, record)
        if connect:
            connect()
        identity = asdict(instrument.identify())
        identity["raw"] = identity["raw"].hex()
        record["instrument"] = identity
        record["transport"] = dict(getattr(instrument.transport, "metadata", {}))
        instrument.configure_absolute(unit)
        # SM is updated only after a measurement (manual 3-33). Consume a
        # setup acquisition before asking for status, avoiding stale unit fields.
        probe = instrument.acquire("TR2")
        record["setup_measurement_raw_hex"] = probe.raw.hex()
        initial = instrument.read_status()
        if initial.unit != unit:
            raise ValueError("Initial status does not match requested absolute units")
        record["initial_status_raw_hex"] = initial.raw.hex()
        # Offset/duty/calibration settings remain visible in this status; no automatic preset/zero.
        record["status"] = "running"
        _atomic_json(sidecar, record)
        start = target = clock()
        index = 0
        while count is None or index < count:
            now = clock()
            if duration is not None and now - start >= duration:
                break
            wait = max(0.0, target - now)
            if duration is not None:
                wait = min(wait, max(0.0, start + duration - now))
            if wait:
                sleep(wait)
            now = clock()
            if duration is not None and now - start >= duration:
                break
            next_target = now + interval
            row = {
                "session_id": record["session_id"],
                "sequence": index + 1,
                "overrun_s": max(0.0, now - target),
                "unit": unit,
            }
            try:
                measurement = instrument.acquire("TR2")
                row.update(
                    value="" if measurement.value is None else str(measurement.value),
                    status="instrument_error" if measurement.error_code else "ok",
                    instrument_error=measurement.error_code or "",
                    raw_hex=measurement.raw.hex(),
                    unit=measurement.unit,
                )
                if measurement.unit != unit:
                    raise StateUncertain("Units changed during collection; stop and reconcile")
            except BaseException as exc:
                row.update(
                    status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                    error=f"{type(exc).__name__}: {exc}",
                    raw_hex=instrument.last_raw.hex(),
                )
                raise
            finally:
                row.update(received_utc=utcnow().isoformat(), elapsed_s=clock() - start)
                writer.writerow(row)
                handle.flush()
                record["rows"] += 1
            index += 1
            target = next_target
        record["status"] = "completed"
        return record
    except BaseException as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        # Resource cleanup happens even if flushing/final metadata persistence fails.
        try:
            handle.close()
        except BaseException as exc:
            record["status"] = "failed"
            record["file_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            try:
                instrument.close()
            except BaseException as exc:
                record["status"] = "failed"
                record["cleanup_error"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                record["finished_utc"] = utcnow().isoformat()
                record["last_raw_hex"] = instrument.last_raw.hex()
                _atomic_json(sidecar, record)
