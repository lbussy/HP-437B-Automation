"""WF-03 synthetic saved-capture validation, equal-cycle statistics, and reports.

This entry point has no physical mode, discovery, source driver, or AI provider.
"""

import argparse
import html
import os
import sys
import tempfile
from decimal import Decimal as D
from decimal import localcontext
from pathlib import Path
from uuid import UUID

from . import protocol, report_context, report_identity, report_sheet
from . import provenance as p
from . import reporting as r
from .workflow_report import _seal, preflight

WORKFLOW = "transmission-cycle-repeatability-v1"
SCHEMA = "hp437b.repeatability-capture.v1"
PROFILE = {
    "cycles": 5,
    "settling_s": 20,
    "plateau_s": 30,
    "off_wait_s": 20,
    "baseline_count": 3,
    "interval_s": 1,
    "timeout_s": 10,
    "whole_run_ceiling_s": 900,
}
CYCLES = tuple(f"C{i:02d}" for i in range(1, 6))
ROLES = ("settling", "plateau", "off-baseline")
STAGES = ("baseline-before", *(f"{cycle}-{role}" for cycle in CYCLES for role in ROLES))
CLOSED = ("completed", "failed", "interrupted", "skipped")


def validate_criteria(criteria):
    if criteria is None:
        return None
    p.require(
        isinstance(criteria, dict)
        and set(criteria)
        == {
            "source",
            "decision_rule",
            "max_cycle_spread_percent",
            "min_samples_per_cycle",
            "max_gap_s",
        },
        "Unsupported WF-03 criteria fields",
    )
    p.require(
        isinstance(criteria["source"], str) and 0 < len(criteria["source"].strip()) <= 240,
        "Criteria need source/revision",
    )
    p.require(criteria["decision_rule"] == "inclusive-no-guard-band", "Unsupported decision rule")
    p.require(
        r.number(criteria["max_cycle_spread_percent"]) >= 0, "Spread limit must be nonnegative"
    )
    p.require(
        type(criteria["min_samples_per_cycle"]) is int
        and 1 <= criteria["min_samples_per_cycle"] <= 30,
        "Invalid required sample count",
    )
    p.require(r.number(criteria["max_gap_s"]) > 0, "Gap limit must be positive")
    return criteria


def analyze(cycles, *, execution="completed", criteria=None, duration_s=30):
    """Retain all requested cycles; aggregate completed cycles with equal weights."""
    validate_criteria(criteria)
    p.require(
        execution in CLOSED[:3] and isinstance(cycles, list) and 1 <= len(cycles) <= 5,
        "Invalid execution/cycle list",
    )
    p.require(type(duration_s) is int and 1 <= duration_s <= 30, "Invalid plateau window")
    rows, means = [], []
    with localcontext() as ctx:
        ctx.prec = 34
        for index, cycle in enumerate(cycles, 1):
            p.require(
                cycle["cycle_id"] == f"C{index:02d}" and cycle["status"] in CLOSED,
                "Invalid cycle order/state",
            )
            points = cycle.get("points", [])
            p.require(isinstance(points, list) and len(points) <= 100000, "Invalid cycle points")
            values, times = [], []
            previous = None
            for point in points:
                t = r.number(str(point["elapsed_s"]))
                p.require(
                    0 <= t <= duration_s + 10 and (previous is None or t >= previous),
                    "Invalid cycle receipt time",
                )
                previous = t
                p.require(
                    point["status"] in ("ok", "failed", "interrupted", "instrument_error"),
                    "Invalid row status",
                )
                value = r.number(point["value_W"]) if point["value_W"] is not None else None
                p.require(
                    (value is not None) == (point["status"] == "ok"), "Point status/value mismatch"
                )
                if value is not None:
                    times.append(t)
                    values.append(value)
            mean = sum(values) / len(values) if values else None
            nonvalid = len(points) - len(values)
            p.require(cycle["status"] != "skipped" or not points, "Skipped cycle has measurements")
            eligible = cycle["status"] == "completed"
            p.require(
                not eligible or (bool(values) and nonvalid == 0),
                "Completed cycle has incomplete data",
            )
            if eligible:
                means.append(mean)
            gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
            max_gap = (
                max([*gaps, times[0], max(D(0), D(duration_s) - times[-1])])
                if times
                else D(duration_s)
            )
            rows.append(
                {
                    "cycle_id": cycle["cycle_id"],
                    "status": cycle["status"],
                    "included_in_aggregate": eligible,
                    "attempted": len(points),
                    "valid": len(values),
                    "nonvalid": nonvalid,
                    "mean_W": str(mean) if mean is not None else None,
                    "min_W": str(min(values)) if values else None,
                    "max_W": str(max(values)) if values else None,
                    "max_gap_including_edges_s": str(max_gap),
                    "receipts_after_window": sum(t > duration_s for t in times),
                    "points": points,
                }
            )
        overall = sum(means) / len(means) if means else None
        spread = max(means) - min(means) if len(means) >= 2 else None
        percent = 100 * spread / overall if spread is not None and overall > 0 else None
        sd = (
            (sum((v - overall) ** 2 for v in means) / (len(means) - 1)).sqrt()
            if len(means) >= 2
            else None
        )
    acceptance = {
        "outcome": "not_evaluated",
        "reason": "No DUT limits/decision rule supplied",
        "criteria": criteria,
    }
    if criteria is not None:
        complete = (
            execution == "completed"
            and len(means) == len(cycles)
            and all(
                row["valid"] >= criteria["min_samples_per_cycle"]
                and row["nonvalid"] == 0
                and row["receipts_after_window"] == 0
                and D(row["max_gap_including_edges_s"]) <= r.number(criteria["max_gap_s"])
                for row in rows
            )
        )
        if complete and percent is not None:
            acceptance.update(
                outcome="pass"
                if percent <= r.number(criteria["max_cycle_spread_percent"])
                else "fail",
                reason="Supplied inclusive cycle-spread comparison; no uncertainty guard band",
            )
        else:
            acceptance["reason"] = (
                "Incomplete execution/required cycle coverage or undefined spread percentage"
            )
    return {
        "schema": "hp437b.repeatability-results.v1",
        "execution": execution,
        "requested_cycles": len(cycles),
        "completed_cycles": len(means),
        "cycles": rows,
        "metrics": {
            k: str(v) if v is not None else None
            for k, v in {
                "equal_cycle_mean_W": overall,
                "cycle_spread_W": spread,
                "cycle_spread_percent": percent,
                "cycle_sample_sd_W": sd,
            }.items()
        },
        "unavailable_reasons": {
            "spread": None if spread is not None else "At least two completed cycles required",
            "percent": None
            if percent is not None
            else "Fewer than two completed cycles or nonpositive equal-cycle mean",
        },
        "acceptance": acceptance,
    }


def require_status(raw_hex, source_on):
    status = protocol.status(bytes.fromhex(raw_hex))
    p.require(
        status.unit == "W"
        and status.reference_on is source_on
        and status.operating_mode == 0
        and status.range_code in range(11, 16)
        and status.filter_code in range(10, 20)
        and not (
            status.relative
            or status.offset_on
            or status.duty_on
            or status.measurement_error
            or status.entry_error
        ),
        "WF-03 source/settings status mismatch",
    )


def load(source):
    bundle = p.Bundle(source)
    inventory = bundle.inventory("artifacts.json", "synthetic")
    record = bundle.json("workflow.json")
    p.require(
        record.get("schema") == SCHEMA
        and record.get("workflow_id") == WORKFLOW
        and record.get("mode") == "synthetic"
        and record.get("simulation") is True,
        "Only synthetic WF-03 captures are supported",
    )
    p.require(
        inventory.get("schema") == "hp437b.repeatability-export.v1"
        and inventory.get("run_id") == record["run_id"],
        "Capture inventory/run mismatch",
    )
    UUID(record["run_id"])
    p.require(
        record.get("profile") == PROFILE
        and all(type(record["profile"][k]) is int for k in PROFILE),
        "Unsupported WF-03 profile",
    )
    p.require(
        record["status"] in CLOSED[:3] and set(record["stages"]) == set(STAGES),
        "Unfinalized workflow/stages",
    )
    p.require(
        record["preflight"]["status"] in CLOSED
        and record["final_state"]["source"] in ("off", "on", "unknown")
        and record["final_state"]["local"] in ("true", "unknown"),
        "Invalid initial/final state",
    )
    p.require(
        record["subject"] == "Fictional POWER REF source - WF-03 simulation",
        "Unsupported measured source",
    )
    validate_criteria(record.get("criteria"))
    started, finished = r.timestamp(record["started_utc"]), r.timestamp(record["finished_utc"])
    p.require(
        0 <= (finished - started).total_seconds() <= PROFILE["whole_run_ceiling_s"],
        "Invalid workflow duration",
    )
    p.require(
        isinstance(record["cycles"], list)
        and [c["cycle_id"] for c in record["cycles"]] == list(CYCLES),
        "Missing/reordered requested cycles",
    )
    stages, session_ids = {}, set()
    for stage in STAGES:
        item = record["stages"][stage]
        state = item["status"]
        name = f"stages/{stage}.csv"
        p.require(state in CLOSED, "Unfinalized capture stage")
        if state == "skipped":
            p.require(
                name not in bundle.entries and name + ".session.json" not in bundle.entries,
                "Skipped capture has data",
            )
            continue
        if (
            state in ("failed", "interrupted")
            and name not in bundle.entries
            and name + ".session.json" not in bundle.entries
        ):
            p.require(bool(item.get("error")), "Absent capture needs a failure reason")
            continue
        metadata = bundle.json(name + ".session.json")
        context = metadata.get("context", {})
        cycle_id = None if stage == "baseline-before" else stage[:3]
        p.require(
            context.get("workflow_id") == WORKFLOW
            and context.get("workflow_run_id") == record["run_id"]
            and context.get("stage_id") == stage
            and context.get("cycle_id") == cycle_id
            and context.get("mode") == "synthetic",
            "Session/workflow/cycle join mismatch",
        )
        p.require(metadata["session_id"] not in session_ids, "Duplicate capture session")
        session_ids.add(metadata["session_id"])
        settings = metadata["settings"]
        duration = 20 if stage.endswith("-settling") else 30 if stage.endswith("-plateau") else None
        p.require(
            settings.get("interval_s") == 1
            and settings.get("operation_timeout_s") == 10
            and settings.get("duration_s") == duration
            and settings.get("count") == (None if duration else 3),
            "Session/profile bounds mismatch",
        )
        result = r.stage_result(bundle.read(name), metadata, "synthetic", stage, state)
        for key in ("started_utc", "finished_utc"):
            p.require(
                started <= r.timestamp(metadata[key]) <= finished, "Session time outside workflow"
            )
        for raw in (metadata.get("initial_status_raw_hex"), item.get("final_status_raw_hex")):
            if raw is None:
                p.require(state != "completed", "Completed stage lacks status evidence")
            else:
                require_status(raw, stage.endswith(("-settling", "-plateau")))
        stages[stage] = result
    cycles = []
    stopped = False
    for cycle in record["cycles"]:
        cid = cycle["cycle_id"]
        state = cycle["status"]
        p.require(state in CLOSED, "Unfinalized cycle")
        p.require(
            not stopped or state == "skipped", "Later cycle continued after failed/skipped cycle"
        )
        if state != "completed":
            stopped = True
        for key, on in (("source_on", True), ("source_off", False)):
            control = cycle[key]
            p.require(control["status"] in CLOSED, "Unfinalized cycle control")
            if control["status"] == "completed":
                require_status(control["status_raw_hex"], on)
        p.require(cycle["off_wait"]["status"] in CLOSED, "Unfinalized off dwell")
        if cycle["off_wait"]["status"] == "completed":
            p.require(cycle["off_wait"]["duration_s"] == 20, "Off dwell mismatch")
        if state == "completed":
            p.require(
                all(
                    cycle[k]["status"] == "completed"
                    for k in ("source_on", "source_off", "off_wait")
                )
                and all(
                    record["stages"][f"{cid}-{role}"]["status"] == "completed"
                    and f"{cid}-{role}" in stages
                    for role in ROLES
                ),
                "Completed cycle lacks full capture/control/off evidence",
            )
        plateau = stages.get(cid + "-plateau", {})
        cycles.append({"cycle_id": cid, "status": state, "points": plateau.get("points", [])})
    if record["status"] == "completed":
        p.require(
            not stopped
            and record["preflight"]["status"] == "completed"
            and record["stages"]["baseline-before"]["status"] == "completed"
            and record["final_state"] == {"source": "off", "local": "true"},
            "Completed run lacks full cycles/closure",
        )
    result = analyze(cycles, execution=record["status"], criteria=record.get("criteria"))
    result.update(run_id=record["run_id"], mode="synthetic", stages=stages)
    provenance = make_provenance(record, bundle)
    p.verify(provenance, source)
    return record, result, provenance, bundle


def make_provenance(record, bundle):
    def copied(key):
        return p.fact(
            record[key],
            basis="supplied",
            refs=[{"evidence_id": "workflow.json", "pointer": "/" + key}],
            note="Synthetic fixture declaration, not physical observation",
        )

    facts = {
        key: copied(key)
        for key in (
            "started_utc",
            "finished_utc",
            "profile",
            "software",
            "status",
            "final_state",
            "cycles",
        )
    }
    if record.get("operator") is not None:
        facts["operator"] = copied("operator")
    devices = [
        p.equipment(
            "synthetic:wf03:" + role,
            role,
            {
                "identity": p.fact(
                    value,
                    basis="supplied",
                    refs=[{"evidence_id": "workflow.json", "pointer": "/equipment/" + role}],
                    note="Fictional equipment",
                )
            },
        )
        for role, value in record["equipment"].items()
    ]
    subject = p.dut(
        "synthetic:wf03:reference",
        "reference_signal",
        ["synthetic:wf03:source", "synthetic:wf03:meter"],
        {"name": copied("subject")},
    )
    return p.record(
        record["run_id"],
        "synthetic",
        WORKFLOW,
        facts,
        subject,
        devices,
        list(bundle.entries.values()),
    )


def plot(result, output):
    with tempfile.TemporaryDirectory(prefix="hp437b-cycle-mpl-") as cache:
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
        fig = Figure(figsize=(9, 2.2), layout="constrained")
        FigureCanvasAgg(fig)
        axis = fig.subplots()
        for included, marker, color, label in (
            (True, "o", "#164e69", "Completed cycle"),
            (False, "x", "#ac331c", "Available incomplete cycle"),
        ):
            points = [
                (i, D(row["mean_W"]) * 1000)
                for i, row in enumerate(result["cycles"], 1)
                if row["mean_W"] is not None and row["included_in_aggregate"] is included
            ]
            if points:
                axis.plot(
                    [p[0] for p in points],
                    [float(p[1]) for p in points],
                    marker,
                    linestyle="none",
                    color=color,
                    label=label,
                )
        axis.set(
            xlabel="Requested transmission cycle",
            ylabel="Cycle mean (mW)",
            xticks=list(range(1, result["requested_cycles"] + 1)),
            xlim=(0.5, result["requested_cycles"] + 0.5),
        )
        axis.ticklabel_format(axis="y", style="plain", useOffset=False)
        axis.grid(alpha=0.2)
        if axis.lines:
            axis.legend(fontsize=8)
        else:
            axis.set_axis_off()
            axis.text(
                0.5,
                0.5,
                "No plateau data captured",
                ha="center",
                va="center",
                transform=axis.transAxes,
                color="#46535e",
            )
        for extension in ("png", "svg"):
            fig.savefig(
                output / f"cycle-means.{extension}",
                dpi=150,
                metadata={"Title": "SYNTHETIC transmission-cycle repeatability"},
            )
        fig.clear()


def render(record, result, producer, operator, plots):
    esc = lambda v: html.escape(str(v), quote=True)  # noqa: E731

    def n(value, scale=1, suffix=""):
        if value is None:
            return "Not available"
        value = D(value) * D(str(scale))
        return ("0" if value == 0 else format(value, ".6g")) + suffix

    baseline = result["stages"].get("baseline-before", {})
    m = result["metrics"]
    acceptance = result["acceptance"]
    started, finished = r.timestamp(record["started_utc"]), r.timestamp(record["finished_utc"])
    meta = [
        ("Device / source", record["subject"]),
        ("Test", "Transmission-cycle repeatability"),
        ("Operator", operator or "Not recorded"),
        (
            "When",
            started.strftime("%d %b %Y, %H:%M:%S")
            + " - "
            + finished.strftime(
                ("%d %b %Y, " if started.date() != finished.date() else "")
                + "%H:%M:%S UTC (virtual)"
            ),
        ),
        ("Frequency", "50 MHz (declared, synthetic)"),
        ("Profile", "5 cycles: 20 s settle / 30 s measure / 20 s off"),
    ]
    rows = [
        (
            'RF-off baseline ("zero")',
            n(baseline.get("metrics", {}).get("mean_W"), 1e6, " µW")
            + f" ({baseline.get('valid', 0)} readings)",
        ),
        (
            "Completed / requested cycles",
            f"{result['completed_cycles']} / {result['requested_cycles']}",
        ),
        ("Equal-cycle mean RF power", n(m["equal_cycle_mean_W"], 1000, " mW")),
        (
            "Cycle-mean spread",
            (
                n(m["cycle_spread_W"], 1000, " mW")
                + " ("
                + n(m["cycle_spread_percent"], 1, "%")
                + ")"
            )
            if m["cycle_spread_W"] is not None
            else "Not available (need 2 completed cycles)",
        ),
        ("Sample SD of completed cycle means", n(m["cycle_sample_sd_W"], 1000, " mW")),
    ]
    notes = [
        "Synthetic POWER REF/meter/sensor path; no transmitter was measured.",
        "Aggregate statistics give each completed cycle equal weight. Incomplete cycles stay visible and are excluded.",
        "Steady plateau power only; no keying-delay, transient, PEP, leakage, or accuracy claim.",
    ]
    if record["final_state"]["source"] != "off":
        notes.append("Final source-off state is not confirmed (simulated); see shutdown evidence.")
    body = [
        "<h1>RF Output Power Test</h1>",
        "<p class='simulation'>SYNTHETIC - simulated readings; no physical transmitter was measured.</p>",
        "<table class='meta'>"
        + "".join(f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in meta)
        + "</table>",
        f"<p class='outcome'><strong>Test execution:</strong> {esc(record['status'])}<br><strong>Acceptance:</strong> {esc(acceptance['outcome'].upper().replace('_', ' '))} - {esc(acceptance['reason'])}</p>",
        "<table class='readings'>"
        + "".join(f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in rows)
        + "</table>",
        "<h2>Requested transmission cycles</h2>",
        "<table class='cycles'><thead><tr><th scope='col'>Cycle</th><th scope='col'>State</th><th scope='col'>Valid / attempted</th><th scope='col'>Mean (mW)</th><th scope='col'>Min / max (mW)</th></tr></thead><tbody>",
    ]
    cycle_lines = []
    for row in result["cycles"]:
        cells = [
            row["cycle_id"],
            row["status"],
            f"{row['valid']} / {row['attempted']}",
            n(row["mean_W"], 1000) if row["mean_W"] is not None else "Not captured",
            (n(row["min_W"], 1000) + " / " + n(row["max_W"], 1000))
            if row["mean_W"] is not None
            else "Not captured",
        ]
        body.append("<tr>" + "".join("<td>" + esc(c) + "</td>" for c in cells) + "</tr>")
        cycle_lines.append(" | ".join(cells))
    body.append("</tbody></table>")
    if plots:
        body.append(
            "<figure><img src='cycle-means.png' alt='Synthetic plateau mean by requested cycle, with incomplete cycles distinguished'><figcaption>Plateau means from saved readings; no line interpolates missing cycles.</figcaption></figure>"
        )
    body += [
        '<h2>Notes affecting interpretation</h2><ul class="notes">'
        + "".join("<li>" + esc(note) + "</li>" for note in notes)
        + "</ul>",
        "<footer><p><strong>Equipment traceability:</strong> Fictional 437B, 8482A, and POWER REF source.</p><p>"
        + esc(report_sheet.producer_note(producer))
        + f"</p><p>Record: {esc(record['run_id'])}</p><p class='screen-links'><a href='evidence.html'>Technical appendix and full traceability</a></p></footer>",
    ]
    style = (
        report_sheet.STYLE
        + "\n.cycles {width:100%;border-collapse:collapse;font-size:12px;font-variant-numeric:tabular-nums;} .cycles th,.cycles td{text-align:left;padding:4px 3px;border-bottom:1px solid #e1e5e8;} @media print {.cycles{font-size:9pt;} .cycles th,.cycles td{padding:3px;} .meta td,.meta th{padding:2px 0;} .readings th,.readings td{padding:4px 0;} figure img{max-height:35mm;} footer{break-inside:avoid;}}"
    )
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\"><title>RF Output Power Test</title><style>"
        + style
        + "</style></head><body><main class='sheet'>"
        + "\n".join(body)
        + "</main></body></html>\n"
    )
    md = [
        "# RF Output Power Test",
        "",
        "**SYNTHETIC - no physical transmitter was measured.**",
        "",
        *[f"**{k}:** {report_sheet._markdown(v)}" for k, v in meta],
        "",
        f"**Execution:** {record['status']}",
        f"**Acceptance:** {acceptance['outcome']} - {acceptance['reason']}",
        "",
        *[f"- {k}: {v}" for k, v in rows],
        "",
        "| Cycle | State | Valid / attempted | Mean (mW) | Min / max (mW) |",
        "| --- | --- | --- | --- | --- |",
        *["| " + line + " |" for line in cycle_lines],
        "",
        *["- " + note for note in notes],
        "",
        "Equipment traceability: fictional 437B/8482A/POWER REF",
        report_sheet.producer_note(producer),
        "Record: " + record["run_id"],
        "",
        "[Technical appendix](evidence.md)",
    ]
    return page, "\n".join(md) + "\n"


def publish(source, output, *, plots=True, operator=None):
    source, output = preflight(source, output, plots=plots)
    record, result, provenance, bundle = load(source)
    attribution = report_context.resolve_operator(operator, record.get("operator"))
    producer = report_identity.identify()
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name, value in (
            ("results.json", result),
            ("provenance.json", provenance),
            ("report-context.json", attribution),
        ):
            (output / name).write_bytes(r.encoded(value))
        if plots:
            plot(result, output)
        page, md = render(record, result, producer, attribution["value"], plots)
        (output / "report.html").write_text(page, encoding="utf-8")
        (output / "report.md").write_text(md, encoding="utf-8")
        evidence = r.encoded(
            {
                "workflow": record,
                "results": result,
                "provenance": provenance,
                "operator": attribution,
                "methods": {
                    "aggregate": "Equal weights over fully completed cycle means only, never pooled raw samples",
                    "spread": "Maximum minus minimum completed-cycle mean; at least two cycles",
                    "percent": "100 * spread / positive equal-cycle mean",
                    "sample_sd": "Sample (n-1) SD of completed-cycle means; at least two cycles",
                    "baseline": "Descriptive signed readings, never subtracted",
                    "coverage": "Requested cycles retained; valid receipt gaps include window edges",
                    "limits": "No criteria means not evaluated; no uncertainty guard band or metrological conformity",
                },
            }
        ).decode()
        (output / "evidence.md").write_text(
            "# WF-03 technical appendix\n\n```json\n" + evidence + "```\n", encoding="utf-8"
        )
        (output / "evidence.html").write_text(
            "<!doctype html><html lang='en'><meta charset='utf-8'><title>WF-03 technical appendix</title><h1>WF-03 technical appendix</h1><pre>"
            + html.escape(evidence)
            + "</pre></html>",
            encoding="utf-8",
        )
        p.verify(provenance, source)
        p.require(
            r.digest(bundle.read("artifacts.json")) == source_hash,
            "Capture changed during reporting",
        )
        _seal(
            output,
            {
                "schema": "hp437b.repeatability-report-export.v1",
                "mode": "synthetic",
                "run_id": record["run_id"],
                "capture_inventory_sha256": source_hash,
                "report_producer": producer,
                "report_context": {"operator": attribution},
                "generator_sha256": r.digest(Path(__file__).read_bytes()),
                "analysis": "deterministic_only",
                "execution": record["status"],
                "acceptance": result["acceptance"]["outcome"],
            },
        )
    except Exception as exc:
        (output / "failure.json").write_bytes(
            r.encoded({"report_status": "failed", "error_type": type(exc).__name__})
        )
        raise
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    synthetic = sub.add_parser("synthetic", help="Explicit fakes and virtual time only")
    synthetic.add_argument("--scenario", default="repeatable")
    synthetic.add_argument("--output", type=Path, required=True)
    synthetic.add_argument("--criteria", type=Path)
    for command in (
        synthetic,
        sub.add_parser("report", help="Report a sealed WF-03 synthetic capture"),
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
            from .repeatability_simulation import run

            criteria = p._json(args.criteria.read_bytes()) if args.criteria else None
            run(
                args.output,
                args.scenario,
                report_output=args.report_output,
                plots=not args.no_plots,
                criteria=criteria,
                operator=args.operator,
            )
            result = p._json((args.report_output / "results.json").read_bytes())
        else:
            result = publish(
                args.bundle, args.output, plots=not args.no_plots, operator=args.operator
            )
        print(
            r.encoded(
                {
                    "run_id": result["run_id"],
                    "mode": "synthetic",
                    "execution": result["execution"],
                    "completed_cycles": result["completed_cycles"],
                    "requested_cycles": result["requested_cycles"],
                    "acceptance": result["acceptance"]["outcome"],
                }
            ).decode(),
            end="",
        )
        return (
            1
            if result["execution"] != "completed" or result["acceptance"]["outcome"] == "fail"
            else 0
        )
    except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
        print(f"WF-03 failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
