"""Operator-guided radio sweeps with a replaceable point-confirmation boundary."""

import csv
import math
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path
from typing import Protocol

from . import protocol, report_context
from . import provenance as p
from . import reporting as r
from .instrument import Instrument
from .logger import _atomic_json, collect
from .simulation import DemoTransport
from .transport import VisaTransport
from .workflow_report import _seal

SCHEMA = "hp437b.guided-sweep.v1"
BANDS = "2200m 630m 160m 80m 60m 40m 30m 20m 17m 15m 12m 10m 8m 6m 5m 4m 2m".split()
PREPARED = ("rf_path_ready", "meter_prepared", "reference_off", "operator_available")


def text(value, limit=120):
    p.require(
        isinstance(value, str)
        and value.strip() == value
        and 0 < len(value) <= limit
        and all(ord(c) >= 32 and ord(c) != 127 for c in value),
        "Use nonempty, single-line labels within the stated length limit",
    )
    return value


def example():
    return dict(
        schema=SCHEMA,
        name="Radio under test",
        series="combined",
        order="frequency",
        frequencies=list(BANDS),
        drives=["2 mA", "4 mA", "8 mA", "12 mA"],
        samples=10,
        interval_s=1.0,
        settling_s=5.0,
        timeout_s=10.0,
        measurement_notes="Meter-indicated power at sensor input; record the RF path and meter corrections here.",
    )


def validate(plan):
    p._keys(
        plan,
        (
            "schema",
            "name",
            "series",
            "order",
            "frequencies",
            "drives",
            "samples",
            "interval_s",
            "settling_s",
            "timeout_s",
            "measurement_notes",
        ),
    )
    p.require(plan["schema"] == SCHEMA, "Unsupported guided sweep plan")
    text(plan["name"])
    text(plan["measurement_notes"], 1000)
    p.require(plan["series"] in ("frequency", "drive", "combined"), "Invalid series")
    p.require(plan["order"] in ("frequency", "drive"), "Invalid point order")
    for key, limit in (("frequencies", 32), ("drives", 16)):
        values = plan[key]
        p.require(isinstance(values, list) and 1 <= len(values) <= limit, f"Use 1–{limit} {key}")
        for value in values:
            text(value, 60)
        p.require(len(set(values)) == len(values), "Use distinct labels")
    p.require(
        plan["series"] != "frequency" or len(plan["drives"]) == 1,
        "Frequency-only sweeps require one fixed drive label",
    )
    p.require(
        plan["series"] != "drive" or len(plan["frequencies"]) == 1,
        "Drive-only sweeps require one fixed frequency label",
    )
    p.require(type(plan["samples"]) is int and 1 <= plan["samples"] <= 1000, "Use 1–1000 samples")
    for key, low, high in (("interval_s", 0.1, 60), ("settling_s", 0, 120), ("timeout_s", 0.1, 30)):
        value = plan[key]
        p.require(
            type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            f"Invalid {key}: use {low}–{high}",
        )
    p.require(plan["samples"] * plan["interval_s"] <= 3600, "Point capture exceeds one hour")
    return p._json(r.encoded(plan))


def points(plan):
    plan = validate(plan)
    pairs = [(f, d) for f in plan["frequencies"] for d in plan["drives"]]
    if plan["order"] == "drive":
        pairs = [(f, d) for d in plan["drives"] for f in plan["frequencies"]]
    return [dict(point_id=f"P{i:03d}", frequency=f, drive=d) for i, (f, d) in enumerate(pairs, 1)]


def configuration(document):
    p._keys(document, ("resource", "meter_serial", "sensor_serial", "known_issues", "fixture"))
    VisaTransport(document["resource"])  # Syntax only; no discovery or device I/O.
    for key in ("meter_serial", "sensor_serial", "fixture"):
        text(document[key], 1000 if key == "fixture" else 120)
    p.require(
        isinstance(document["known_issues"], list) and len(document["known_issues"]) <= 20,
        "Record known equipment issues",
    )
    for issue in document["known_issues"]:
        text(issue, 500)
    return p._json(r.encoded(document))


class PointGate(Protocol):
    """UI, CLI, or orchestration adapters authorize exactly one identified point."""

    def confirm(self, point: dict, token: str) -> dict: ...

    def cancelled(self) -> bool: ...


class FileGate:
    def __init__(self, path, emit):
        self.path, self.emit = Path(path), emit

    def cancelled(self):
        return (self.path / "cancel.requested").is_file()

    def confirm(self, point, token):
        self.emit(phase="waiting", prompt={**point, "token": token}, current="GUIDED")
        target = self.path / ("confirm-" + token + ".json")
        while not target.is_file():
            if self.cancelled():
                raise KeyboardInterrupt("Series stopped while awaiting confirmation")
            time.sleep(0.1)
        p.require(not target.is_symlink() and target.stat().st_size <= 8192, "Invalid confirmation")
        return p._json(target.read_bytes())


def check_confirmation(value, point, token):
    p._keys(
        value,
        (
            "point_id",
            "frequency",
            "drive",
            "token",
            "operator",
            "confirmed_utc",
            "frequency_confirmed",
            "drive_confirmed",
        ),
    )
    p.require(
        all(value[k] == point[k] for k in ("point_id", "frequency", "drive"))
        and value["token"] == token
        and value["frequency_confirmed"] is True
        and value["drive_confirmed"] is True,
        "Confirmation does not match the pending point",
    )
    report_context.validate_operator(value["operator"])
    stamp = datetime.fromisoformat(value["confirmed_utc"])
    p.require(stamp.utcoffset() is not None, "Confirmation requires a timezone")
    return value


def capture_point(
    output,
    plan,
    point,
    confirmation,
    *,
    mode,
    config,
    cancelled,
    transport_factory=None,
    sleep=time.sleep,
):
    """A fresh production logger session, opened only after point authorization."""

    def pause(seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if cancelled():
                raise KeyboardInterrupt("Series stopped before the next acquisition")
            sleep(min(0.1, max(0, end - time.monotonic())))

    pause(plan["settling_s"])
    if cancelled():
        raise KeyboardInterrupt("Series stopped before opening the meter")
    transport = (
        transport_factory()
        if transport_factory
        else DemoTransport()
        if mode == "synthetic"
        else VisaTransport(config["resource"])
    )

    class GuidedInstrument(Instrument):
        def acquire(self, *args, **kwargs):
            if cancelled():
                raise KeyboardInterrupt("Series stopped before the next acquisition")
            reply = super().acquire(*args, **kwargs)
            if reply.error_code:
                raise ValueError("Meter reported a measurement error")
            return reply

        def read_status(self):
            status = super().read_status()
            p.require(
                not status.reference_on and not status.measurement_error and not status.entry_error,
                "Meter must be ready with POWER REF off and no errors",
            )
            return status

    instrument = GuidedInstrument(transport, timeout=plan["timeout_s"])
    context = dict(
        workflow=SCHEMA,
        point=point,
        confirmation=confirmation,
        plan_sha256=r.digest(r.encoded(plan)),
        equipment=config,
        measurement_plane="meter_indication_at_sensor_input",
    )
    try:
        return collect(
            instrument,
            output,
            count=plan["samples"],
            interval=plan["interval_s"],
            unit="W",
            context=context,
            simulation=mode == "synthetic",
            connect=(lambda: transport.open(plan["timeout_s"])) if mode == "physical" else None,
            sleep=pause,
        )
    finally:
        instrument.close()
        transport.close()


def run(
    output,
    plan,
    gate: PointGate,
    *,
    mode="synthetic",
    config=None,
    operator=None,
    prepared=None,
    emit=lambda **event: None,
    capture=capture_point,
):
    plan = validate(plan)
    p.require(mode in ("synthetic", "physical"), "Invalid meter mode")
    report_context.validate_operator(operator)
    if mode == "physical":
        config = configuration(config)
        p.require(
            isinstance(prepared, dict)
            and set(prepared) == set(PREPARED)
            and all(v is True for v in prepared.values()),
            "Confirm the prepared RF path and meter",
        )
    else:
        p.require(config is None, "Simulated runs cannot contain physical configuration")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    record = dict(
        schema=SCHEMA,
        mode=mode,
        run_id=str(uuid.uuid4()),
        plan=plan,
        operator=operator,
        equipment=config,
        prepared=prepared,
        started_utc=datetime.now(UTC).isoformat(),
        status="running",
        points=[{**point, "status": "skipped"} for point in points(plan)],
        error=None,
    )
    _atomic_json(output / "workflow.json", record)
    try:
        for i, point in enumerate(record["points"]):
            if gate.cancelled():
                raise KeyboardInterrupt("Series stopped at a point boundary")
            point["status"] = "waiting"
            token = uuid.uuid4().hex
            confirmation = check_confirmation(
                gate.confirm({k: point[k] for k in ("point_id", "frequency", "drive")}, token),
                point,
                token,
            )
            if gate.cancelled():
                raise KeyboardInterrupt("Series stopped before capture")
            folder = output / point["point_id"]
            folder.mkdir()
            _atomic_json(folder / "confirmation.json", confirmation)
            point.update(status="running", token=token)
            _atomic_json(output / "workflow.json", record)
            emit(
                phase="running", prompt=None, index=i, current="GUIDED", stage="settling / capture"
            )
            capture(
                folder / "samples.csv",
                plan,
                {k: point[k] for k in ("point_id", "frequency", "drive")},
                confirmation,
                mode=mode,
                config=config,
                cancelled=gate.cancelled,
            )
            point["status"] = "completed"
            _atomic_json(output / "workflow.json", record)
            emit(index=i + 1, point_results=analyze_unsealed(output, record)["points"])
        record["status"] = "completed"
    except BaseException as exc:
        record["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        record["error"] = f"{type(exc).__name__}: {exc}"[:500]
        for point in record["points"]:
            if point["status"] in ("waiting", "running"):
                point["status"] = record["status"]
        if not isinstance(exc, (Exception, KeyboardInterrupt)):
            raise
    finally:
        record["finished_utc"] = datetime.now(UTC).isoformat()
        _atomic_json(output / "workflow.json", record)
        _seal(output, dict(schema=SCHEMA, mode=mode, run_id=record["run_id"]))
    return load(output)[1]


def analyze_unsealed(source, record):
    """Recompute from native logger rows; partial observations never complete a point."""
    results = []
    plan_hash = r.digest(r.encoded(record["plan"]))
    prior_finished = None
    session_ids = set()
    for point in record["points"]:
        folder = Path(source) / point["point_id"]
        values, session, confirmation = [], None, None
        elapsed = []
        if (folder / "confirmation.json").is_file():
            confirmation = p._json((folder / "confirmation.json").read_bytes())
            check_confirmation(confirmation, point, point["token"])
        if (folder / "samples.csv.session.json").is_file():
            session = p._json((folder / "samples.csv.session.json").read_bytes())
            context = session["context"]
            settings = session["settings"]
            p.require(
                settings["unit"] == "W"
                and settings["count"] == record["plan"]["samples"]
                and settings["interval_s"] == record["plan"]["interval_s"]
                and settings["duration_s"] is None
                and settings["operation_timeout_s"] == record["plan"]["timeout_s"],
                "Native capture settings mismatch",
            )
            p.require(
                session["session_id"] not in session_ids, "Session identity reused across points"
            )
            session_ids.add(session["session_id"])
            confirmed = datetime.fromisoformat(confirmation["confirmed_utc"])
            p.require(
                prior_finished is None or confirmed >= prior_finished,
                "Confirmation predates previous point closure",
            )
            prior_finished = datetime.fromisoformat(session["finished_utc"])
            if "initial_status_raw_hex" in session:
                status = protocol.status(bytes.fromhex(session["initial_status_raw_hex"]))
                p.require(
                    status.unit == "W"
                    and not status.reference_on
                    and not status.measurement_error
                    and not status.entry_error,
                    "Invalid initial meter status",
                )
            p.require(
                session["simulation"] == (record["mode"] == "synthetic")
                and context["confirmation"] == confirmation
                and context["plan_sha256"] == plan_hash
                and context["equipment"] == record["equipment"]
                and context["point"] == {k: point[k] for k in ("point_id", "frequency", "drive")},
                "Native session context mismatch",
            )
            p.require(
                datetime.fromisoformat(session["started_utc"])
                >= datetime.fromisoformat(confirmation["confirmed_utc"]),
                "Capture predates confirmation",
            )
            with (folder / "samples.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            p.require(len(rows) == session["rows"], "Native row count mismatch")
            for i, row in enumerate(rows, 1):
                p.require(
                    row["session_id"] == session["session_id"] and int(row["sequence"]) == i,
                    "Native session/sequence mismatch",
                )
                if row["status"] == "ok":
                    p.require(row["unit"] == "W", "Guided captures require watts")
                    raw = protocol.measurement(bytes.fromhex(row["raw_hex"]), "W")
                    value = r.number(row["value"])
                    p.require(
                        raw.value == value
                        and raw.error_code is None
                        and not row["instrument_error"],
                        "Reading differs from raw native frame",
                    )
                    values.append(value)
                    elapsed.append(r.number(row["elapsed_s"]))
                    p.require(
                        elapsed[-1] >= 0 and (len(elapsed) < 2 or elapsed[-1] >= elapsed[-2]),
                        "Native receipt timing moved backwards",
                    )
            if point["status"] == "completed":
                p.require(
                    session["status"] == "completed"
                    and len(values) == record["plan"]["samples"]
                    and len(rows) == len(values),
                    "Incomplete native point capture",
                )
        p.require(
            point["status"] != "completed" or session is not None,
            "Completed point has no native evidence",
        )
        mean = sum(values, D(0)) / len(values) if values else None
        variance = (
            sum(((value - mean) ** 2 for value in values), D(0)) / len(values) if values else None
        )
        results.append(
            {
                **{k: point[k] for k in ("point_id", "frequency", "drive", "status")},
                "samples": len(values),
                "stddev_W": str(variance.sqrt()) if variance is not None else None,
                "max_receipt_gap_s": str(
                    max((b - a for a, b in zip(elapsed, elapsed[1:], strict=False)), default=D(0))
                )
                if elapsed
                else None,
                "mean_W": str(mean) if mean is not None else None,
                "min_W": str(min(values)) if values else None,
                "max_W": str(max(values)) if values else None,
                "mean_dBm": str(10 * (mean / D(".001")).log10())
                if mean is not None and mean > 0
                else None,
            }
        )
    return dict(
        schema=SCHEMA,
        mode=record["mode"],
        run_id=record["run_id"],
        execution=record["status"],
        acceptance="NOT EVALUATED",
        measurement_plane="meter_indication_at_sensor_input",
        requested_points=len(results),
        completed_points=sum(x["status"] == "completed" for x in results),
        points=results,
    )


def load(source):
    bundle = p.Bundle(source)
    inventory = p._json(bundle.read("artifacts.json"))
    p.require(
        inventory.get("schema") == SCHEMA and inventory.get("mode") in ("physical", "synthetic"),
        "Invalid sweep inventory",
    )
    bundle.inventory("artifacts.json", inventory["mode"])
    record = bundle.json("workflow.json")
    p.require(
        record["schema"] == SCHEMA
        and record["run_id"] == inventory["run_id"]
        and record["mode"] == inventory["mode"]
        and record["status"] in ("completed", "failed", "interrupted"),
        "Invalid sweep identity/status",
    )
    report_context.validate_operator(record["operator"])
    if record["mode"] == "physical":
        configuration(record["equipment"])
        p.require(
            isinstance(record["prepared"], dict)
            and set(record["prepared"]) == set(PREPARED)
            and all(v is True for v in record["prepared"].values()),
            "Physical setup confirmation missing",
        )
    else:
        p.require(record["equipment"] is None, "Synthetic record contains physical equipment")
    expected = points(record["plan"])
    p.require(len(expected) == len(record["points"]), "Requested point count changed")
    stopped = False
    for point, original in zip(record["points"], expected, strict=True):
        p.require(
            all(point[k] == v for k, v in original.items()), "Requested point labels/order changed"
        )
        p.require(
            point["status"] in ("completed", "failed", "interrupted", "skipped"), "Unfinished point"
        )
        if point["status"] == "completed":
            p.require(not stopped, "Capture continued after a stopped point")
        else:
            stopped = True
    p.require(
        record["status"] != "completed" or not stopped, "Incomplete series cannot be complete"
    )
    actual = {
        path.relative_to(bundle.root).as_posix()
        for path in bundle.root.rglob("*")
        if path.is_file()
    }
    p.require(
        actual == set(bundle.entries)
        and not any(path.is_symlink() for path in bundle.root.rglob("*")),
        "Uninventoried/symlink sweep evidence",
    )
    return record, analyze_unsealed(source, record), bundle
