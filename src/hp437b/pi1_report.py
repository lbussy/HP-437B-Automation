"""Validate a sealed Pi 1 capture and render its complete matrix offline."""

import csv
import io
import math
import os
from contextlib import suppress
from decimal import Decimal
from html import escape

from . import pi1_meter as hp
from . import pi1_sweep as sweep
from . import protocol
from . import provenance as p
from . import reporting as r
from .logger import FIELDS
from .sensor_correction import PROFILE, SENSOR_SERIAL, correction
from .workflow_report import _seal, preflight

REPORT = "hp437b.gpio-qualification-report.v1"
HISTORICAL_REPORT = "hp437b.pi1-gpio20-report.v1"


def _bytes(value):
    p.require(
        isinstance(value, str) and len(value) <= 8192 and len(value) % 2 == 0,
        "Invalid raw meter frame",
    )
    raw = bytes.fromhex(value)
    p.require(raw.hex() == value, "Noncanonical raw frame")
    return raw


def _calibrated(row, point):
    p._keys(row, ("display_hex", "status_hex"))
    receipt = correction(PROFILE, SENSOR_SERIAL, point.carrier_hz)
    p.require(
        hp.factor_matches(_bytes(row["display_hex"]), receipt)
        and hp.healthy(protocol.status(_bytes(row["status_hex"]))),
        "CAL FAC readback or status disagrees with the certificate",
    )
    return receipt


def _reading(frame, maximum):
    value = protocol.measurement(_bytes(frame["raw_hex"]), "W")
    p.require(
        value.error_code is None
        and value.value is not None
        and value.value <= maximum
        and str(value.value) == frame["watts"]
        and hp.healthy(protocol.status(_bytes(frame["status_hex"]))),
        "Reading disagrees with its meter frames",
    )
    return value.value


def _owner_binding(receipt, record):
    historical = record["schema"] == sweep.HISTORICAL_SCHEMA
    source = record["review"]["source"]
    sweep.owner_binding(
        receipt, source, record["run"], record.get("claim", {}).get("owner"), historical=historical
    )


def _current_source(record):
    return record["review"]["source"] if record["schema"] == sweep.SCHEMA else None


def _observation(obs, record, row, plan, bank, phase, earliest, latest):
    p._keys(obs, ("sent_ns", "received_ns", "receipt"))
    a, b = obs["sent_ns"], obs["received_ns"]
    p.require(
        type(a) is int and type(b) is int and earliest <= a <= b <= latest,
        "Owner observation is outside the local deadline or sample window",
    )
    _owner_binding(obs["receipt"], record)
    source = _current_source(record)
    worker = (
        None
        if source is None
        else next(
            group["opened"]["worker"]
            for group in record["groups"]
            if group["instance"] == row["instance"]
        )
    )
    return sweep.validate_tone(obs["receipt"], row, plan, bank, phase, source, worker)


def _confirmed(record, row, point, admission, group):
    p.require(
        row["rf_confirmed"] is True
        and row["dispatch_pending"] is True
        and row.get("start_attempted") is True
        and sweep._valid_token(row["request"])
        and group["instance"] == row["instance"]
        and row.get("error") is None
        and "stop_error" not in row,
        "Confirmed samples are missing authorization or the temporary group binding",
    )
    source = _current_source(record)
    receipt = _calibrated(row["factor"], point)
    bank, start = record["bank"], row["host_start_ns"]
    p.require(
        type(start) is int
        and record["began_ns"] <= start
        and start + (sweep.TONE_S + sweep.FINAL_S) * sweep.NS
        <= record["began_ns"] + sweep.run_limit(record["review"]) * sweep.NS,
        "Invalid monotonic origin or whole-run reservation",
    )
    stop_by = start + (sweep.TONE_S - sweep.STOP_S) * sweep.NS
    active_by = start + sweep.START_S * sweep.NS
    ack = _observation(row["ack"], record, row, admission, bank, "accepted", start, active_by)
    active = _observation(
        row["active"], record, row, admission, bank, "active", row["ack"]["received_ns"], active_by
    )
    p.require(
        active["generation"] == ack["generation"]
        and active["revision"] >= ack["revision"]
        and (source is None or active["ceiling_ms"] == ack["ceiling_ms"]),
        "Start and active observations disagree",
    )
    previous = row["active"]["received_ns"] + sweep.DWELL_S * sweep.NS
    revision = active["revision"]
    samples = row["samples"]
    p.require(
        isinstance(samples, list)
        and len(samples) in (4, 5)
        and [frame["kind"] for frame in samples]
        == ["settling"] * (len(samples) - 2) + ["retained", "retained"],
        "Missing or reordered settling and retained readings",
    )
    values = []
    for frame in samples:
        p._keys(
            frame,
            (
                "kind",
                "before",
                "read_started_ns",
                "raw_hex",
                "status_hex",
                "read_finished_ns",
                "received_utc",
                "after",
                "watts",
            ),
        )
        p._timestamp(frame["received_utc"])
        a, b = frame["read_started_ns"], frame["read_finished_ns"]
        p.require(
            type(a) is int and type(b) is int and 0 <= a <= b <= stop_by,
            "Invalid meter monotonic interval",
        )
        before = _observation(frame["before"], record, row, admission, bank, "active", previous, a)
        after = _observation(frame["after"], record, row, admission, bank, "active", b, stop_by)
        p.require(
            before["generation"] == after["generation"] == ack["generation"]
            and revision <= before["revision"] == after["revision"]
            and (source is None or before["ceiling_ms"] == after["ceiling_ms"] == ack["ceiling_ms"])
            and frame["after"]["received_ns"] - frame["before"]["sent_ns"]
            <= sweep.READ_S * sweep.NS,
            "Measurement crosses a stale or changed RF window",
        )
        previous = frame["after"]["received_ns"] + sweep.SPACING_S * sweep.NS
        revision = after["revision"]
        values.append(_reading(frame, Decimal(record["review"]["fixture"]["maximum_indication_w"])))
    settling = values[:-2]
    p.require(
        not (len(settling) == 3 and sweep.settled(*settling[:2])) and sweep.settled(*settling[-2:]),
        "Settling sequence disagrees with the rule",
    )
    stop = _observation(
        row["stop"],
        record,
        row,
        admission,
        bank,
        "terminal",
        samples[-1]["after"]["received_ns"],
        start + sweep.TONE_S * sweep.NS,
    )
    p.require(
        stop["generation"] == ack["generation"]
        and stop["revision"] > revision
        and (source is None or stop["ceiling_ms"] == ack["ceiling_ms"]),
        "Terminal proof belongs to a different generation or precedes the last active sample",
    )
    p.require(row["state"] == sweep.classify(row, record["pre"]), "Invalid limited classification")
    mean = (values[-1] + values[-2]) / 2
    return {
        "samples": 2,
        "captured_samples": 2,
        "settling_reads": len(settling),
        "sample_w": [str(value) for value in values[-2:]],
        "mean_mw": str(mean * 1000),
        "dbm": round(10 * math.log10(float(mean * 1000)), 6)
        if row["state"] == "measured"
        else None,
        "cal_fac_percent": receipt["commanded_factor_percent"],
        "generation": ack["generation"],
    }


def validate(record):
    p.require(
        isinstance(record, dict)
        and record.get("schema") in (sweep.SCHEMA, sweep.HISTORICAL_SCHEMA)
        and record.get("mode") == "physical"
        and sweep._valid_token(record.get("run"))
        and record.get("status") in ("completed", "partial"),
        "Expected a finalized Pi 1 capture",
    )
    p.require(
        type(record["began_ns"]) is int
        and type(record["finished_ns"]) is int
        and 0 <= record["began_ns"] <= record["finished_ns"],
        "Invalid recorded host monotonic run interval",
    )
    source = _current_source(record)
    review = sweep.validate_review(record["review"], historical=source is None, saved=True)
    points = sweep.requested_points(review)
    group_count = len({point.drive_ma for point in points})
    rows = record["points"]
    p.require(isinstance(rows, list) and len(rows) == len(points), "Incomplete saved run scope")
    groups = record["groups"]
    p.require(isinstance(groups, list) and len(groups) <= group_count, "Invalid drive groups")
    instances = set()
    bank = record["bank"]
    if bank is not None:
        _owner_binding(record["claim"], record)
        p.require(
            sweep.validate_claim(record["claim"], record["run"], source) == bank,
            "Original pad state disagrees with source lease receipt",
        )
    for i, group in enumerate(groups):
        p._keys(group, ("instance", "drive_ma", "opened", "closed"))
        instance, drive = group["instance"], sweep.DRIVES[i]
        p.require(
            sweep._valid_token(instance)
            and instance not in instances
            and group["drive_ma"] == drive
            and (i == 0 or groups[i - 1]["closed"] is not None),
            "Unexpected owner group identity, drive, or predecessor cleanup",
        )
        instances.add(instance)
        if group["opened"] is not None:
            _owner_binding(group["opened"], record)
            sweep.validate_open(group["opened"], instance, drive, bank, source)
        if group["closed"] is not None:
            _owner_binding(group["closed"], record)
            sweep.validate_group_close(
                group["closed"], instance, bank, source, (group["opened"] or {}).get("worker")
            )
    for label in ("pre", "post"):
        baselines = record[label]
        p.require(isinstance(baselines, list) and len(baselines) <= 3, "Invalid baseline count")
        for i, row in enumerate(baselines):
            if "watts" in row:
                value = _reading(row, hp.LIMIT_W)
                p.require(
                    label != "pre"
                    or abs(value) <= hp.BASELINE_W
                    or (
                        i == len(baselines) - 1
                        and record["status"] == "partial"
                        and all(point["state"] == "not reached" for point in rows)
                    ),
                    "Invalid initial baseline evidence",
                )
            else:
                p.require(
                    i == len(baselines) - 1 and record["status"] == "partial",
                    "Malformed baseline in a successful session",
                )
    if record["pre"]:
        _calibrated(record["baseline_factor"], sweep.POINTS[0])
        p.require(
            sweep._valid_token(record["zero_sha256"], sweep.pi.HASH),
            "Fresh supervised ZERO is missing",
        )
        p.require(
            _bytes(record["meter_identity"]).rstrip(b"\r\n") == hp.IDN,
            "Meter identity does not match the fixture",
        )
    cleanup = record["source_cleanup"]
    source_verified = isinstance(cleanup, dict) and cleanup.get("verified") is True
    if source_verified:
        _owner_binding(cleanup["receipt"], record)
        sweep.validate_release(cleanup["receipt"], record["run"], bank, source)
        p.require(
            all(group["closed"] is not None for group in groups),
            "Released run contains an unclosed drive group",
        )
    p.require(
        not record["post"] or source_verified, "Final baseline requires verified source shutdown"
    )
    request_ids, jobs = set(), set()
    stopped = False
    preceding_tone = record["began_ns"]
    report_rows = []
    for index, (row, point, admission) in enumerate(
        zip(rows, points, review["admissions"][: len(points)], strict=True)
    ):
        p.require(r.encoded(row["point"]) == r.encoded(sweep.asdict(point)), "Saved matrix differs")
        state = row["state"]
        p.require(
            state in ("measured", "limited", "failed", "not reached")
            and (not stopped or state == "not reached"),
            "Invalid point progression",
        )
        if state == "not reached":
            p._keys(row, ("point", "state"))
        else:
            group_index = index // len(sweep.BANDS)
            p.require(
                group_index < len(groups) and groups[group_index]["opened"] is not None,
                "Point has no opened owner group",
            )
            group = groups[group_index]
            p.require(
                row["instance"] == group["instance"]
                and type(row["dispatch_pending"]) is bool
                and type(row["rf_confirmed"]) is bool,
                "Invalid point ownership evidence",
            )
            if row["dispatch_pending"]:
                request = row["request"]
                p.require(
                    sweep._valid_token(request) and request not in request_ids,
                    "Invalid or reused tone request",
                )
                request_ids.add(request)
                if source is not None:
                    reservation = row.get("reservation")
                    _owner_binding(reservation, record)
                    sweep.validate_tone(
                        reservation,
                        row,
                        admission,
                        bank,
                        "reserved",
                        source,
                        group["opened"]["worker"],
                    )
                    for key in ("ack", "active", "stop"):
                        if key not in row:
                            continue
                        observation = row[key]
                        phase = {"ack": "accepted", "active": "active", "stop": "terminal"}[key]
                        if (
                            key == "stop"
                            and observation["receipt"].get("phase") == "cancelled-before-enable"
                        ):
                            phase = "cancelled-before-enable"
                        _observation(
                            observation,
                            record,
                            row,
                            admission,
                            bank,
                            phase,
                            record["began_ns"],
                            record["finished_ns"],
                        )
            else:
                p.require(
                    not row["rf_confirmed"]
                    and "ack" not in row
                    and "samples" in row
                    and row["samples"] == [],
                    "Point without dispatch has RF evidence",
                )
        frames = row.get("samples", [])
        summary = {
            "samples": 0,
            "captured_samples": sum(
                frame["kind"] == "retained" and "raw_hex" in frame for frame in frames
            ),
            "settling_reads": sum(
                frame["kind"] == "settling" and "raw_hex" in frame for frame in frames
            ),
            "sample_w": [],
            "mean_mw": None,
            "dbm": None,
            "cal_fac_percent": None,
        }
        if state in ("measured", "limited"):
            p.require(
                len(record["pre"]) == 3 and all("watts" in frame for frame in record["pre"]),
                "Confirmed readings lack a complete initial baseline",
            )
            summary = _confirmed(record, row, point, admission, group)
            p.require(
                preceding_tone
                <= row["host_start_ns"]
                <= row["stop"]["received_ns"]
                <= record["finished_ns"],
                "Confirmed tones overlap or lie outside the run",
            )
            preceding_tone = row["stop"]["received_ns"]
            job = (row["instance"], summary.pop("generation"))
            p.require(job not in jobs, "Controller generation reused within a process")
            jobs.add(job)
        elif state == "failed":
            p.require(isinstance(row["error"], str) and bool(row["error"]), "Missing point failure")
        report_rows.append(
            {
                **row["point"],
                "state": state,
                "start_attempted": row.get("start_attempted", False),
                "rf_confirmed": row.get("rf_confirmed", False),
                "error": row.get("error"),
                **summary,
            }
        )
        stopped = stopped or state in ("failed", "not reached")
    if record["status"] == "completed":
        p.require(
            not stopped
            and len(groups) == group_count
            and source_verified
            and (record["meter_cleanup"] or {}).get("status") == "accepted"
            and record["post_error"] is None
            and len(record["post"]) == 3
            and record["error"] is None
            and record["finished_ns"] - record["began_ns"] <= sweep.run_limit(review) * sweep.NS,
            "Completed run has missing acquisition or cleanup",
        )
    return report_rows


def _native(record):
    """Rebuild native CSV rows directly from complete retained meter frames."""
    data = io.StringIO(newline="")
    writer = csv.DictWriter(data, fieldnames=FIELDS)
    writer.writeheader()
    sequence = 0
    for row in record["points"]:
        for frame in row.get("samples", ()):
            if frame["kind"] != "retained" or "watts" not in frame:
                continue
            sequence += 1
            writer.writerow(
                {
                    "session_id": record["run"],
                    "sequence": sequence,
                    "value": frame["watts"],
                    "unit": "W",
                    "status": "ok"
                    if row["state"] in ("measured", "limited")
                    else "unconfirmed_point",
                    "raw_hex": frame["raw_hex"],
                    "received_utc": frame["received_utc"],
                    "elapsed_s": (frame["read_finished_ns"] - record["began_ns"]) / sweep.NS,
                }
            )
    sidecar = {
        "schema_version": 1,
        "session_id": record["run"],
        "simulation": False,
        "status": record["status"],
        "rows": sequence,
        "instrument_cleanup": record["meter_cleanup"],
        "settings": {"unit": "W", "trigger": "TR1"},
        "context": {
            "schema": record["schema"],
            "meter_serial": hp.METER_SERIAL,
            "sensor_serial": SENSOR_SERIAL,
            "measurement_plane": "sensor_input",
        },
    }
    return data.getvalue().encode(), r.encoded(sidecar)


def seal_capture(output, record):
    native, session = _native(record)
    for name, data in (("readings.csv", native), ("readings.csv.session.json", session)):
        with (output / name).open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    _seal(output, {"schema": record["schema"], "mode": "physical", "run": record["run"]})
    sweep.sync_directory(output)


def load(source):
    bundle = p.Bundle(source)
    inventory = bundle.inventory("artifacts.json", "physical")
    p.require(
        inventory.get("schema") in (sweep.SCHEMA, sweep.HISTORICAL_SCHEMA),
        "Wrong capture inventory",
    )
    p.require(not any(path.is_symlink() for path in bundle.root.rglob("*")), "Symlink capture")
    actual = {
        path.relative_to(bundle.root).as_posix()
        for path in bundle.root.rglob("*")
        if path.is_file()
    }
    p.require(actual == set(bundle.entries), "Unsealed or unexpected capture evidence")
    record = bundle.json("workflow.json")
    p.require(
        record.get("run") == inventory.get("run")
        and record.get("schema") == inventory.get("schema"),
        "Capture inventory belongs to another run or schema",
    )
    rows = validate(record)
    if record["zero_sha256"] is not None:
        zero_path = "zero/diagnostics.json"
        p.require(
            zero_path in bundle.entries
            and bundle.entries[zero_path]["sha256"] == record["zero_sha256"],
            "ZERO diagnostics are missing or cross-linked",
        )
        zero = bundle.json(zero_path)
        p.require(
            zero["schema"] == "hp437b.diagnostics.physical.v1"
            and zero["status"] == "completed"
            and zero["supervised_zero_profile"] is True
            and zero["supervised_cal_profile"] is False
            and zero["transport_closed"] is True
            and zero["zero_assessment"]["accepted_full_case"] is True
            and zero["target"]["resource"] == hp.RESOURCE
            and zero["equipment_labels"]
            == {"meter_serial": hp.METER_SERIAL, "sensor_serial": SENSOR_SERIAL},
            "ZERO diagnostics do not attest the reviewed meter and supervised closure",
        )
    for name, expected in zip(
        ("readings.csv", "readings.csv.session.json"), _native(record), strict=True
    ):
        p.require(
            bundle.read(name, bundle.entries[name]) == expected, "Native meter artifacts disagree"
        )
    return record, rows, bundle.entries["artifacts.json"]["sha256"]


def publish(source, output, *, pdf=False):
    source, output = preflight(source, output, plots=False)
    try:
        run, rows, inventory_hash = load(source)
    except (KeyError, TypeError, IndexError, AttributeError, ArithmeticError) as exc:
        raise p.ProvenanceError("Malformed sealed Pi 1 capture") from exc
    if pdf:
        from .pdf_reports import preflight as pdf_preflight

        pdf_preflight()
    counts = {
        key: sum(row["state"] == key for row in rows)
        for key in ("measured", "limited", "failed", "not reached")
    }
    source = _current_source(run)
    selected = sweep.pi.route(20) if source is None else sweep.pi.route(source["gpio"])
    scope = run["review"].get("scope", "sweep")
    title = f"Pi 1 GPIO{selected['gpio']} {scope}"
    schema = HISTORICAL_REPORT if source is None else REPORT
    summary = {
        "schema": schema,
        "route": selected,
        "scope": scope,
        "run": run["run"],
        "capture_inventory_sha256": inventory_hash,
        "status": run["status"],
        "coverage": counts,
        "rows": rows,
        "measurement_plane": "HP 8482A sensor input. Indications may include harmonics.",
        "rf_frequency_accuracy": "unqualified",
        "criteria": "not evaluated",
        "source_cleanup": run["source_cleanup"],
        "meter_cleanup": run["meter_cleanup"],
        "pre": run["pre"],
        "post": run["post"],
        "post_error": run["post_error"],
        "error": run["error"],
        "fixture": run["review"]["fixture"],
        "clock": {
            name: run["review"]["admissions"][0][name] for name in ("policy", "ppm_millionths")
        },
        "correction": [
            correction(PROFILE, SENSOR_SERIAL, point.carrier_hz)
            for point in sweep.POINTS[: len(sweep.BANDS)]
        ],
    }
    output.mkdir(mode=0o700)
    sweep.create_json(output / "report.json", summary)
    with (output / "points.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    from .guided_report import html_summary

    lines = [
        f"Route: GPIO{selected['gpio']}/{selected['mux']} (GPCLK0)",
        f"Capture: {run['status']}",
        f"Measurement plane: {summary['measurement_plane']}",
        "RF frequency accuracy: Unqualified",
        "Acceptance criteria: Unevaluated",
        f"Coverage: {counts}",
        f"Final baseline: {run['post_error'] or ('recorded' if run['post'] else 'unavailable')}",
    ]
    columns = ("point_id", "band", "carrier_hz", "drive_ma", "state", "samples", "mean_mw", "dbm")
    header = "".join(f"<th>{escape(key)}</th>" for key in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{escape(str(row[key])) if row[key] is not None else ''}</td>" for key in columns
        )
        + "</tr>"
        for row in rows
    )
    with (output / "index.html").open("x", encoding="utf-8") as stream:
        stream.write(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{escape(title)}</title>"
            "<style>body>table{max-width:100%}.points{overflow-x:auto}"
            ".points:focus-visible{outline:2px solid #135c91}</style>"
            f"</head><body><h1>{escape(title)}</h1>{html_summary(lines)}"
            '<div class="points" tabindex="0" role="region" aria-label="Requested points">'
            f"<table><caption>Requested points</caption><thead><tr>{header}</tr></thead>"
            f"<tbody>{body}</tbody></table></div></body></html>"
        )
    if pdf:
        from .pdf_reports import _write
        from .report_identity import identify

        sweep.create_json(
            output / "metadata.json",
            {
                "schema": schema,
                "run": run["run"],
                "capture_inventory_sha256": inventory_hash,
            },
        )
        _write(
            output,
            lines=lines,
            columns=columns,
            rows=[[row[key] for key in columns] for row in rows],
            widths=(45, 45, 72, 55, 75, 48, 90, 70),
            notes=[
                summary["measurement_plane"],
                "Independent RF frequency accuracy is unqualified.",
            ],
            producer=identify(),
            run_id=run["run"],
            physical=True,
            source_label=f"Conducted {title}",
            multipage=True,
        )
    _seal(output, {"schema": schema, "mode": "physical", "run": run["run"]})
    with suppress(OSError):
        sweep.sync_directory(output)
    return {"status": "completed", "coverage": counts, "output": str(output)}
