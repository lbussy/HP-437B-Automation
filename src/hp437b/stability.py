"""WF-02 saved-run validation, provenance, drift analysis, and deterministic reports.

Synthetic and supervised POWER REF v1 captures are accepted. No device I/O here.
"""

import argparse
import html
import math
import os
import statistics
import sys
import tempfile
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

from . import protocol, report_context, report_identity, report_sheet
from . import provenance as p
from . import reporting as r
from .workflow_report import _seal, preflight

WORKFLOW = "sustained-output-stability-v1"
SCHEMA = "hp437b.stability-capture.v1"
PROFILE = {
    "duration_s": 1800,
    "bin_s": 300,
    "interval_s": 1,
    "timeout_s": 10,
    "observation_s": 20,
    "whole_run_ceiling_s": 2100,
}
STAGES = ("baseline-before", "settling", "plateau", "baseline-after")


def validate_criteria(criteria):
    if criteria is None:
        return None
    p.require(
        isinstance(criteria, dict)
        and set(criteria)
        == {
            "source",
            "decision_rule",
            "max_abs_endpoint_drift_percent",
            "min_samples_per_bin",
            "max_gap_s",
        },
        "Unsupported WF-02 criteria fields",
    )
    p.require(
        isinstance(criteria["source"], str) and 0 < len(criteria["source"].strip()) <= 240,
        "Criteria need a source/revision",
    )
    p.require(
        criteria["decision_rule"] == "inclusive-no-guard-band",
        "Only explicit inclusive-no-guard-band comparisons are supported",
    )
    p.require(
        r.number(criteria["max_abs_endpoint_drift_percent"]) >= 0, "Drift limit must be nonnegative"
    )
    p.require(r.number(criteria["max_gap_s"]) > 0, "Gap limit must be positive")
    p.require(
        type(criteria["min_samples_per_bin"]) is int
        and 1 <= criteria["min_samples_per_bin"] <= 1800,
        "Invalid bin coverage requirement",
    )
    return criteria


def analyze(points, *, duration_s=1800, bin_s=300, execution="completed", criteria=None):
    """Decimal arithmetic over validated receipt-time points; no baseline subtraction."""
    validate_criteria(criteria)
    p.require(
        type(duration_s) is int
        and type(bin_s) is int
        and 0 < bin_s <= duration_s <= 1800
        and duration_s % bin_s == 0,
        "Invalid analysis window",
    )
    p.require(execution in ("completed", "failed", "interrupted"), "Invalid execution state")
    bins = [[] for _ in range(duration_s // bin_s)]
    valid, times = [], []
    previous = None
    for point in points:
        t = r.number(str(point["elapsed_s"]))
        p.require(t >= 0 and (previous is None or t >= previous), "Nonmonotonic analysis time")
        previous = t
        p.require(
            point["status"] in ("ok", "failed", "interrupted", "instrument_error"),
            "Invalid point status",
        )
        value = r.number(point["value_W"]) if point["value_W"] is not None else None
        p.require((value is not None) == (point["status"] == "ok"), "Point value/status mismatch")
        if value is None:
            continue
        valid.append((t, value))
        times.append(t)
        if t <= duration_s:
            bins[min(int(t // bin_s), len(bins) - 1)].append(value)

    def text(value):
        return str(value) if value is not None else None

    with localcontext() as ctx:
        ctx.prec = 34
        values = [v for _, v in valid]
        mean = sum(values) / len(values) if values else None
        means = [sum(b) / len(b) if b else None for b in bins]
        first, last = means[0], means[-1]
        delta = last - first if first is not None and last is not None else None
        percent = delta / first * 100 if delta is not None and first > 0 else None
        slope = None
        if len(valid) >= 2:
            tm = sum(times) / len(times)
            denominator = sum((t - tm) ** 2 for t in times)
            if denominator:
                slope = sum((t - tm) * (v - mean) for t, v in valid) / denominator * 60
        metrics = {
            "mean_W": mean,
            "min_W": min(values) if values else None,
            "max_W": max(values) if values else None,
            "peak_to_peak_W": max(values) - min(values) if values else None,
            "first_bin_mean_W": first,
            "last_bin_mean_W": last,
            "endpoint_change_W": delta,
            "endpoint_change_percent": percent,
            "slope_W_per_minute": slope,
        }
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    edge_gaps = [times[0], max(D(0), D(duration_s) - times[-1])] if times else [D(duration_s)]
    max_gap = max([*gaps, *edge_gaps])
    coverage = {
        "bins_present": sum(bool(b) for b in bins),
        "bins_expected": len(bins),
        "attempted": len(points),
        "valid": len(valid),
        "nonvalid": len(points) - len(valid),
        "receipt_span_s": text(times[-1] - times[0]) if times else None,
        "median_spacing_s": text(D(str(statistics.median(gaps)))) if gaps else None,
        "max_gap_including_edges_s": text(max_gap),
        "receipts_after_window": sum(t > duration_s for t in times),
    }
    acceptance = {
        "outcome": "not_evaluated",
        "reason": "No DUT limits/decision rule supplied",
        "criteria": criteria,
    }
    if criteria is not None:
        complete = (
            execution == "completed"
            and coverage["nonvalid"] == 0
            and all(len(b) >= criteria["min_samples_per_bin"] for b in bins)
            and max_gap <= r.number(criteria["max_gap_s"])
            and coverage["receipts_after_window"] == 0
        )
        if not complete or percent is None:
            acceptance.update(
                outcome="not_evaluated",
                reason="Incomplete execution/required coverage or undefined endpoint percentage",
            )
        else:
            acceptance.update(
                outcome="pass"
                if percent.copy_abs() <= r.number(criteria["max_abs_endpoint_drift_percent"])
                else "fail",
                reason="Supplied inclusive endpoint-drift comparison; no uncertainty guard band",
            )
    return {
        "schema": "hp437b.stability-results.v1",
        "execution": execution,
        "metrics": {k: text(v) for k, v in metrics.items()},
        "bins": [
            {
                "index": i,
                "start_s": i * bin_s,
                "end_s": (i + 1) * bin_s,
                "count": len(b),
                "mean_W": text(means[i]),
            }
            for i, b in enumerate(bins)
        ],
        "coverage": coverage,
        "acceptance": acceptance,
        "unavailable_reasons": {
            "endpoint": None if delta is not None else "First or last bin is absent",
            "percent": None
            if percent is not None
            else "Endpoint absent or first-bin mean is nonpositive",
            "slope": None
            if slope is not None
            else "At least two distinct valid receipt times required",
        },
        "points": points,
    }


D = Decimal


def load(source):
    """Validate hashes, closed capture semantics, and run/session joins before reporting."""
    bundle = p.Bundle(source)
    header = p._json(bundle.read("artifacts.json"))
    mode = header.get("mode")
    p.require(mode in ("synthetic", "physical"), "Unsupported WF-02 capture mode")
    inventory = bundle.inventory("artifacts.json", mode)
    record = bundle.json("workflow.json")
    p.require(
        record.get("schema") == SCHEMA
        and record.get("workflow_id") == WORKFLOW
        and record.get("mode") == mode
        and record.get("simulation") is (mode == "synthetic"),
        "Only explicit WF-02 capture schemas are supported",
    )
    p.require(
        inventory.get("run_id") == record["run_id"]
        and inventory.get("schema") == "hp437b.stability-export.v1",
        "Capture inventory/run mismatch",
    )
    UUID(record["run_id"])
    p.require(
        record.get("profile") == PROFILE
        and all(type(record["profile"][key]) is int for key in PROFILE)
        and set(record["stages"]) == set(STAGES),
        "Unsupported WF-02 profile/stages",
    )
    p.require(
        record["status"] in ("completed", "failed", "interrupted"), "Unsealed/running workflow"
    )
    p.require(
        record["final_state"]["source"]
        in (("off", "unknown") if mode == "synthetic" else ("off", "on", "unknown"))
        and isinstance(record["final_state"]["local"], str),
        "Invalid final state",
    )
    p.require(
        record["status"] != "completed"
        or (
            all(record["stages"][s]["status"] == "completed" for s in STAGES)
            and record["final_state"]["source"] == "off"
            and (
                record["final_state"]["local"] == "true"
                if mode == "synthetic"
                else record["final_state"]["local"]
                == "USB488 GTL accepted; front panel not yet confirmed"
            )
        ),
        "Completed workflow lacks completed stages/cleanup",
    )
    if mode == "physical":
        validate_physical(record)
    started, finished = r.timestamp(record["started_utc"]), r.timestamp(record["finished_utc"])
    p.require(
        0 <= (finished - started).total_seconds() <= PROFILE["whole_run_ceiling_s"],
        "Invalid workflow duration",
    )
    validate_criteria(record.get("criteria"))
    stages, session_ids = {}, set()
    for stage in STAGES:
        state = record["stages"][stage]["status"]
        p.require(state in ("completed", "failed", "interrupted", "skipped"), "Unfinalized stage")
        name = f"stages/{stage}.csv"
        if state == "skipped":
            p.require(
                name not in bundle.entries and name + ".session.json" not in bundle.entries,
                "Skipped stage has capture",
            )
            continue
        if (
            state in ("failed", "interrupted")
            and name not in bundle.entries
            and name + ".session.json" not in bundle.entries
        ):
            p.require(
                bool(record["stages"][stage].get("error")), "Absent capture needs a failure reason"
            )
            continue
        metadata = bundle.json(name + ".session.json")
        context = metadata.get("context", {})
        p.require(
            context.get("workflow_id") == WORKFLOW
            and context.get("workflow_run_id") == record["run_id"]
            and context.get("stage_id") == stage,
            "Session/workflow join mismatch",
        )
        p.require(metadata["session_id"] not in session_ids, "Duplicate session identity")
        session_ids.add(metadata["session_id"])
        settings = metadata.get("settings", {})
        p.require(
            settings.get("interval_s") == PROFILE["interval_s"]
            and settings.get("operation_timeout_s") == PROFILE["timeout_s"],
            "Session settings/profile mismatch",
        )
        if stage in ("baseline-before", "baseline-after"):
            p.require(
                settings.get("count") == 3 and settings.get("duration_s") is None,
                "Baseline capture bounds mismatch",
            )
        else:
            planned_duration = 20 if stage == "settling" else 1800
            partial_endpoint = (
                mode == "synthetic"
                and stage == "plateau"
                and state == "interrupted"
                and record.get("scenario") in ("missing-first", "missing-last")
            )
            p.require(
                settings.get("count") is None
                and settings.get("duration_s") == (1500 if partial_endpoint else planned_duration),
                "Acquisition bounds/profile mismatch",
            )
        stages[stage] = r.stage_result(bundle.read(name), metadata, mode, stage, state)
        for field in ("started_utc", "finished_utc"):
            p.require(
                started <= r.timestamp(metadata[field]) <= finished,
                "Session time lies outside workflow",
            )
        for field in ("initial_status_raw_hex", "final_status_raw_hex"):
            raw_status = (
                metadata.get(field)
                if field == "initial_status_raw_hex"
                else record["stages"][stage].get(field)
            )
            if raw_status is None:
                p.require(state != "completed", "Completed session lacks status evidence")
                continue
            status = protocol.status(bytes.fromhex(raw_status))
            p.require(
                status.unit == "W"
                and status.reference_on == (stage in ("settling", "plateau"))
                and not (
                    status.relative
                    or status.offset_on
                    or status.duty_on
                    or status.measurement_error
                    or status.entry_error
                ),
                "Stage status/source mismatch",
            )
        offset = record["stages"][stage].get("window_offset_s", 0)
        p.require(type(offset) is int and 0 <= offset < 1800, "Invalid window offset")
        p.require(stage == "plateau" or offset == 0, "Only plateau windows support offsets")
        p.require(
            record["status"] != "completed" or offset == 0,
            "Completed window cannot omit its beginning",
        )
        for point in stages[stage]["points"]:
            point["elapsed_s"] += offset
            p.require(
                point["elapsed_s"] <= PROFILE["duration_s"] + PROFILE["timeout_s"],
                "Receipt outside bounded workflow window",
            )
    p.require(
        record["status"] != "completed" or all(s in stages for s in STAGES),
        "Missing completed capture",
    )
    points = stages.get("plateau", {}).get("points", [])
    results = analyze(points, execution=record["status"], criteria=record.get("criteria"))
    results.update(run_id=record["run_id"], mode=mode, stages=stages)
    provenance = make_provenance(record, bundle)
    p.verify(provenance, source)
    return record, results, provenance, bundle


def validate_physical(record):
    setup = record.get("setup", {})
    required = (
        "adapter_on_mac",
        "direct_sensor_reference_path",
        "reference_off",
        "warmed_up",
        "other_apps_closed",
        "operator_available",
    )
    p.require(all(setup.get(key) is True for key in required), "Physical prepared setup missing")
    p.require(
        record["subject"] == "POWER REF output (internal reference source)"
        and isinstance(setup.get("known_issues"), list)
        and all(isinstance(note, str) for note in setup["known_issues"]),
        "Physical reference/issue declaration missing",
    )
    for role in ("meter", "sensor"):
        p.require(
            isinstance(setup.get(role + "_serial"), str)
            and setup[role + "_serial"]
            and setup[role + "_serial"] in record["equipment"][role],
            "Physical label identity mismatch",
        )
    controls = record.get("control_stages", {})
    p.require(
        set(controls) == {"preflight", "source-on", "source-off", "free-run"}
        and all(
            item["status"] in ("completed", "failed", "interrupted", "skipped")
            for item in controls.values()
        ),
        "Unfinalized physical controls",
    )
    p.require(isinstance(record.get("sessions"), list), "Physical session observations missing")
    if record["status"] == "completed":
        p.require(
            all(item["status"] == "completed" for item in controls.values())
            and record.get("free_run_check", {}).get("passed") is True,
            "Physical completion lacks controls/free-run evidence",
        )
    for session in record["sessions"]:
        identity = session.get("identity")
        if identity is not None:
            decoded = protocol.identification(bytes.fromhex(identity["raw"]))
            p.require(
                decoded.model == "437B"
                and decoded.firmware == identity["firmware"]
                and (
                    not setup.get("expected_firmware")
                    or decoded.firmware == setup["expected_firmware"]
                ),
                "Physical returned identity mismatch",
            )


def make_provenance(record, bundle):
    def copied(value, pointer):
        return p.fact(
            value,
            basis="supplied",
            refs=[{"evidence_id": "workflow.json", "pointer": pointer}],
            note="Synthetic fixture declaration, not physical observation"
            if record["mode"] == "synthetic"
            else "Supplied setup/run declaration; returned protocol identities are recorded separately",
        )

    facts = {
        key: copied(record[key], "/" + key)
        for key in ("started_utc", "finished_utc", "software", "profile", "status", "final_state")
    }
    if record.get("operator") is not None:
        facts["operator"] = copied(record["operator"], "/operator")
    mode = record["mode"]
    identities = {
        role: (
            "synthetic:" + role
            if mode == "synthetic"
            else mode + ":" + role + ":" + r.digest(identity.encode())[:16]
        )
        for role, identity in record["equipment"].items()
    }
    devices = [
        p.equipment(identities[role], role, {"identity": copied(identity, f"/equipment/{role}")})
        for role, identity in record["equipment"].items()
    ]
    if mode == "physical":
        facts["setup"] = copied(record["setup"], "/setup")
        facts["instrument_sessions"] = p.fact(
            record["sessions"],
            basis="observed",
            refs=[{"evidence_id": "workflow.json", "pointer": "/sessions"}],
            note="Protocol session observations; label serials remain supplied",
        )
    subject = p.dut(
        "synthetic:reference" if mode == "synthetic" else identities["source"] + ":reference",
        "reference_signal",
        [identities["source"]],
        {"name": copied(record["subject"], "/subject")},
    )
    return p.record(
        record["run_id"],
        mode,
        WORKFLOW,
        facts,
        subject,
        devices,
        list(bundle.entries.values()),
    )


def plot(results, output):
    with tempfile.TemporaryDirectory(prefix="hp437b-stability-mpl-") as cache:
        old = os.environ.get("MPLCONFIGDIR")
        os.environ["MPLCONFIGDIR"] = cache
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            from matplotlib.figure import Figure
        finally:
            if old is None:
                os.environ.pop("MPLCONFIGDIR", None)
            else:
                os.environ["MPLCONFIGDIR"] = old
        figure = Figure(figsize=(9, 2.5), layout="constrained")
        FigureCanvasAgg(figure)
        axis = figure.subplots()
        points = results["points"]
        axis.plot(
            [v["elapsed_s"] / 60 for v in points],
            [float(v["value_W"]) * 1000 if v["value_W"] is not None else math.nan for v in points],
            ".",
            markersize=2,
            color="#164e69",
        )
        for b in results["bins"]:
            if b["mean_W"] is not None:
                axis.plot(
                    [(b["start_s"] + b["end_s"]) / 120],
                    [float(b["mean_W"]) * 1000],
                    "s",
                    color="#ac331c",
                    markersize=4,
                )
        axis.set(
            xlabel="Host receipt elapsed time (min)", ylabel="Sensor input power (mW)", xlim=(0, 30)
        )
        axis.grid(alpha=0.2)
        for extension in ("png", "svg"):
            figure.savefig(
                output / f"power-trend.{extension}",
                dpi=150,
                metadata={"Title": results["mode"].upper() + " sustained output stability"},
            )
        figure.clear()


def render(record, results, producer, operator, plots):
    esc = lambda value: html.escape(str(value), quote=True)  # noqa: E731

    def n(value, scale=1, suffix=""):
        return f"{D(value) * D(str(scale)):.6g}{suffix}" if value is not None else "Not available"

    physical = record["mode"] == "physical"
    equipment_text = (
        " | ".join(record["equipment"][role] for role in ("meter", "sensor"))
        if physical
        else "Fictional 437B, 8482A, and POWER REF source; see appendix."
    )
    metrics, coverage = results["metrics"], results["coverage"]
    baseline = results["stages"].get("baseline-before", {})
    zero = baseline.get("metrics", {}).get("mean_W")
    rows = [
        (
            'RF-off baseline ("zero")',
            n(zero, 1e6, " µW") + f" ({baseline.get('valid', 0)} readings)",
        ),
        ("Average RF power", n(metrics["mean_W"], 1000, " mW")),
        (
            "First → last bin mean",
            n(metrics["first_bin_mean_W"], 1000, " mW")
            + " → "
            + n(metrics["last_bin_mean_W"], 1000, " mW"),
        ),
        ("Endpoint change", n(metrics["endpoint_change_percent"], 1, "%")),
        ("Sampled drift slope", n(metrics["slope_W_per_minute"], 1000, " mW/min")),
        (
            "Observed min / max",
            n(metrics["min_W"], 1000, " mW") + " / " + n(metrics["max_W"], 1000, " mW"),
        ),
        (
            "Coverage",
            f"{coverage['bins_present']}/{coverage['bins_expected']} bins; {coverage['valid']}/{coverage['attempted']} valid readings",
        ),
        ("Largest gap (including window edges)", n(coverage["max_gap_including_edges_s"], 1, " s")),
    ]
    started = r.timestamp(record["started_utc"])
    finished = r.timestamp(record["finished_utc"])
    when = (
        started.strftime("%d %b %Y, %H:%M:%S")
        + " – "
        + finished.strftime(
            ("%d %b %Y, " if started.date() != finished.date() else "")
            + "%H:%M:%S UTC"
            + ("" if physical else " (virtual)")
        )
    )
    meta = [
        ("Device / source", record["subject"]),
        ("Test", "Sustained output stability"),
        ("Operator", operator or "Not recorded"),
        (
            "When",
            when,
        ),
        ("Frequency", "50 MHz (declared)" if physical else "50 MHz (declared, synthetic)"),
        ("Window", "30 minutes; six 5-minute bins"),
    ]
    acceptance = results["acceptance"]
    notes = [
        "Internal POWER REF/meter/sensor path; no transmitter was measured."
        if physical
        else "Synthetic reference/meter/sensor path; no transmitter was measured.",
        "Receipt-time drift includes the measurement path and filtering; it is not RF waveform timing or transmitter-only drift.",
        "No baseline subtraction, fixture correction, or measurement uncertainty is applied.",
    ]
    if physical:
        notes.extend(record["setup"]["known_issues"])
        if record["final_state"]["source"] != "off":
            notes.append("Reference-off state is not confirmed; see failure/cleanup evidence.")
    if acceptance["criteria"] is not None:
        notes.append("Fictional/supplied comparison only: " + acceptance["reason"])
    if coverage["bins_present"] < coverage["bins_expected"]:
        notes.append("Missing bins: endpoint drift may be unavailable; gaps are not interpolated.")
    body = [
        "<h1>RF Output Power Test</h1>",
        ""
        if physical
        else "<p class='simulation'>SYNTHETIC — simulated readings; no physical transmitter was measured.</p>",
        "<table class='meta'>"
        + "".join(f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in meta)
        + "</table>",
        f"<p class='outcome'><strong>Test execution:</strong> {esc(record['status'])}<br><strong>Acceptance:</strong> {esc(acceptance['outcome'].upper().replace('_', ' '))} — {esc(acceptance['reason'])}</p>",
        "<h2>Sustained measurement</h2><table class='readings'>"
        + "".join(f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)
        + "</table>",
    ]
    if plots:
        body.append(
            "<figure><img src='power-trend.png' alt='Power samples and five-minute bin means over thirty minutes'><figcaption>Dots: individual readings. Squares: bin means. No interpolation across gaps.</figcaption></figure>"
        )
    body += [
        "<h2>Notes affecting interpretation</h2><ul class='notes'>"
        + "".join(f"<li>{esc(note)}</li>" for note in notes)
        + "</ul>",
        "<footer><p><strong>Equipment traceability:</strong> "
        + esc(equipment_text)
        + "</p><p>"
        + esc(report_sheet.producer_note(producer))
        + f"</p><p>Record: {esc(record['run_id'])}</p><p class='screen-links'><a href='evidence.html'>Technical appendix and full traceability</a></p></footer>",
    ]
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\"><title>RF Output Power Test</title><style>"
        + report_sheet.STYLE
        + "</style></head><body><main class='sheet'>"
        + "\n".join(body)
        + "</main></body></html>\n"
    )
    md = [
        "# RF Output Power Test",
        "",
        "" if physical else "**SYNTHETIC — no physical transmitter was measured.**",
        "",
        *[f"**{k}:** {report_sheet._markdown(v)}" for k, v in meta],
        "",
        f"**Execution:** {record['status']}",
        f"**Acceptance:** {acceptance['outcome']} — {acceptance['reason']}",
        "",
        *[f"- {k}: {v}" for k, v in rows],
        "",
        *[f"- {note}" for note in notes],
        "",
        "Equipment traceability: " + equipment_text,
        report_sheet.producer_note(producer),
        "Record: " + record["run_id"],
        "",
        "[Technical appendix](evidence.md)",
    ]
    return page, "\n".join(md) + "\n"


def publish(source, output, *, plots=True, operator=None):
    source, output = preflight(source, output, plots=plots)
    record, results, provenance, bundle = load(source)
    attribution = report_context.resolve_operator(operator, record.get("operator"))
    producer = report_identity.identify()
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name, value in (
            ("results.json", results),
            ("provenance.json", provenance),
            ("report-context.json", attribution),
        ):
            (output / name).write_bytes(r.encoded(value))
        if plots:
            plot(results, output)
        page, md = render(record, results, producer, attribution["value"], plots)
        (output / "report.html").write_text(page, encoding="utf-8")
        (output / "report.md").write_text(md, encoding="utf-8")
        appendix = {
            "workflow": record,
            "results": results,
            "provenance": provenance,
            "operator": attribution,
            "methods": {
                "bins": "[start,end), final endpoint included; later receipts retained outside bins",
                "slope": "unweighted least squares of valid W against monotonic receipt seconds, scaled to W/min",
                "gap": "valid receipt gaps plus start/end window edges",
                "mean": "arithmetic mean of linear W; not time-weighted energy",
                "uncertainty": "not supplied; no automatic guard band",
                "baseline": "descriptive mean, never subtracted",
            },
        }
        evidence = r.encoded(appendix).decode()
        (output / "evidence.md").write_text(
            "# WF-02 technical appendix\n\n```json\n" + evidence + "```\n", encoding="utf-8"
        )
        (output / "evidence.html").write_text(
            "<!doctype html><html lang='en'><meta charset='utf-8'><title>WF-02 technical appendix</title><h1>WF-02 technical appendix</h1><pre>"
            + html.escape(evidence)
            + "</pre></html>",
            encoding="utf-8",
        )
        p.verify(provenance, source)
        p.require(
            r.digest(bundle.read("artifacts.json")) == source_hash, "Capture inventory changed"
        )
        _seal(
            output,
            {
                "schema": "hp437b.stability-report-export.v1",
                "run_id": record["run_id"],
                "mode": record["mode"],
                "capture_inventory_sha256": source_hash,
                "report_producer": producer,
                "report_context": {"operator": attribution},
                "analysis": "deterministic_only",
                "execution": record["status"],
                "acceptance": results["acceptance"]["outcome"],
            },
        )
    except Exception as exc:
        (output / "failure.json").write_bytes(
            r.encoded({"report_status": "failed", "error_type": type(exc).__name__})
        )
        raise
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    synthetic = sub.add_parser("synthetic", help="Run explicit fakes and virtual time; no hardware")
    synthetic.add_argument("--scenario", default="constant")
    synthetic.add_argument("--output", type=Path, required=True)
    synthetic.add_argument("--criteria", type=Path)
    for command in (
        synthetic,
        sub.add_parser("report", help="Report an existing sealed WF-02 capture"),
    ):
        if command is not synthetic:
            command.add_argument("--bundle", type=Path, required=True)
        command.add_argument(
            "--report-output" if command is synthetic else "--output", type=Path, required=True
        )
        command.add_argument("--no-plots", action="store_true")
        command.add_argument("--operator")
    args = parser.parse_args(argv)
    try:
        if args.action == "synthetic":
            from .stability_simulation import run

            criteria = p._json(args.criteria.read_bytes()) if args.criteria else None
            run(
                args.output,
                args.scenario,
                report_output=args.report_output,
                criteria=criteria,
                plots=not args.no_plots,
                operator=args.operator,
            )
            results = p._json((args.report_output / "results.json").read_bytes())
        else:
            source = args.bundle
            results = publish(source, args.output, plots=not args.no_plots, operator=args.operator)
        print(
            r.encoded(
                {
                    "run_id": results["run_id"],
                    "mode": results["mode"],
                    "execution": results["execution"],
                    "acceptance": results["acceptance"]["outcome"],
                }
            ).decode(),
            end="",
        )
        return (
            1
            if results["execution"] != "completed" or results["acceptance"]["outcome"] == "fail"
            else 0
        )
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        print(f"WF-02 failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
