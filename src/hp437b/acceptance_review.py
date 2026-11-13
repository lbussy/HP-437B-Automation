"""Post-capture, supplied-limit assessments. No acquisition or source mutation."""

import html
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from . import pdf_reports as pdf
from . import provenance as p
from . import (
    reference_report,
    reference_suite,
    report_context,
    report_identity,
    report_sheet,
    run_history,
)
from . import reporting as r
from .workflow_report import _seal

SCHEMA = "hp437b.acceptance-criteria.v1"
REPORT_SCHEMA = "hp437b.acceptance-report.v1"
RULE = "inclusive-no-guard-band"
BASE = ("mean_min_mW", "mean_max_mW", "min_valid_samples", "max_gap_s")
FIELDS = {
    "WF-01": BASE,
    "WF-02": (*BASE, "max_abs_endpoint_change_percent"),
    "WF-03": (*BASE, "max_cycle_spread_percent"),
}
PERFORMANCE = (
    "mean_min_mW",
    "mean_max_mW",
    "max_abs_endpoint_change_percent",
    "max_cycle_spread_percent",
)


def number(value):
    p.require(
        type(value) in (str, int, float) and len(str(value)) <= 64,
        "A limit must be a finite nonnegative number",
    )
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Invalid numeric limit") from None
    p.require(
        result.is_finite() and 0 <= result <= Decimal("1e12"),
        "Limits must be finite, nonnegative, and at most 1e12",
    )
    return result


def validate(criteria):
    p._keys(criteria, ("schema", "source", "decision_rule", "workflows"))
    p.require(
        criteria["schema"] == SCHEMA and criteria["decision_rule"] == RULE,
        "Unsupported criteria schema or decision rule",
    )
    source = criteria["source"]
    p.require(
        source is None
        or (
            isinstance(source, str)
            and 0 < len(source.strip()) <= 240
            and not any(ord(c) < 32 or ord(c) == 127 for c in source)
        ),
        "Criteria source must be a single line of at most 240 characters",
    )
    supplied = criteria["workflows"]
    p.require(
        isinstance(supplied, dict) and set(supplied) <= set(FIELDS), "Unknown workflow criteria"
    )
    normalized = {}
    for kind in FIELDS:
        if kind not in supplied:
            continue
        value = supplied[kind]
        p.require(
            isinstance(value, dict) and set(value) <= set(FIELDS[kind]), "Unknown limit field"
        )
        row = {}
        for key in FIELDS[kind]:
            item = value.get(key)
            if item is None:
                row[key] = None
            elif key == "min_valid_samples":
                p.require(
                    type(item) is int and 1 <= item <= 1000000,
                    "Minimum valid sample count must be an integer from 1 to 1000000",
                )
                row[key] = item
            else:
                numeric = number(item)
                p.require(key != "max_gap_s" or numeric > 0, "Maximum gap must be positive")
                row[key] = str(
                    numeric
                )  # Keep extreme small exponents compact; never expand fixed-point text.
        lo, hi = row["mean_min_mW"], row["mean_max_mW"]
        p.require(
            lo is None or hi is None or Decimal(lo) <= Decimal(hi), "Mean minimum exceeds maximum"
        )
        normalized[kind] = row
    p.require(
        source is not None
        or not any(v is not None for row in normalized.values() for v in row.values()),
        "Record who supplied the limits or their criteria reference",
    )
    return dict(
        schema=SCHEMA,
        source=source.strip() if source else None,
        decision_rule=RULE,
        workflows=normalized,
    )


def collect(source, workflow=None):
    source = Path(source)
    p.require(source.is_dir() and not source.is_symlink(), "Sealed capture missing or symlinked")
    bundle = p.Bundle(source)
    if workflow is None:
        record, _, _ = reference_suite.load(source)
        kinds = record["workflows"]
        children = [
            (x["workflow"], source / "captures" / x["workflow"]) for x in record["children"]
        ]
    else:
        p.require(workflow in FIELDS, "Unsupported individual workflow")
        record, _, _ = reference_report.load(source, workflow)
        kinds, children = [workflow], [(workflow, source)]
    rows = {}
    for kind, child in children:
        native, results, _ = reference_suite.native(child, kind)
        rows[kind] = dict(
            native=native, results=results, metrics=run_history.metrics(native, results, kind)
        )
    return dict(
        run_id=record["run_id"],
        mode=record["mode"],
        execution=record["status"],
        started_utc=record["started_utc"],
        operator=record.get("operator", (record.get("setup") or {}).get("operator")),
        setup=record.get("setup"),
        software=record.get("software"),
        workflows=kinds,
        rows=rows,
        source_inventory_sha256=r.digest(bundle.read("artifacts.json")),
    )


def coverage(row, kind, limits):
    native, result = row["native"], row["results"]
    minimum, gap = limits.get("min_valid_samples"), limits.get("max_gap_s")
    if native["status"] != "completed":
        return False, "Capture did not complete"
    if row["metrics"].get("zero_W") is None:
        return False, "Pre-RF zero is unavailable"
    if minimum is None or gap is None:
        return False, "Specify minimum valid samples and maximum gap before applying limits"
    max_gap = Decimal(gap)
    if kind == "WF-01":
        stage = result["stages"].get("S40", {})
        points = stage.get("points", [])
        times = [Decimal(str(x["elapsed_s"])) for x in points if x["status"] == "ok"]
        duration_value = native["profile"].get(
            "duration_s", native["profile"].get("sustained_duration_s")
        )
        if duration_value is None:
            return False, "Recorded plateau duration is unavailable"
        duration = Decimal(str(duration_value))
        gaps = (
            [
                times[0],
                max(Decimal(0), duration - times[-1]),
                *[b - a for a, b in zip(times, times[1:], strict=False)],
            ]
            if times
            else [duration]
        )
        good = (
            stage.get("outcome") == "completed"
            and stage.get("nonvalid") == 0
            and len(times) >= minimum
            and max(gaps) <= max_gap
            and all(0 <= t <= duration for t in times)
        )
    elif kind == "WF-02":
        data = result["coverage"]
        good = (
            data["nonvalid"] == 0
            and data["receipts_after_window"] == 0
            and all(x["count"] >= minimum for x in result["bins"])
            and Decimal(data["max_gap_including_edges_s"]) <= max_gap
        )
    else:
        good = result["completed_cycles"] == result["requested_cycles"] and all(
            x["included_in_aggregate"]
            and x["valid"] >= minimum
            and x["nonvalid"] == 0
            and x["receipts_after_window"] == 0
            and Decimal(x["max_gap_including_edges_s"]) <= max_gap
            for x in result["cycles"]
        )
    return bool(
        good
    ), "Required coverage satisfied" if good else "Required coverage was not satisfied"


def evaluate(data, criteria):
    criteria = validate(criteria)
    p.require(
        set(criteria["workflows"]) <= set(data["workflows"]),
        "Criteria include workflows outside this capture",
    )
    rows = []
    with localcontext() as context:
        context.prec = 50
        for kind in data["workflows"]:
            limits = criteria["workflows"].get(kind, {})
            row = data["rows"].get(kind)
            metrics = row["metrics"] if row else dict(zero_W=None, mean_W=None)
            applicable = [k for k in PERFORMANCE if limits.get(k) is not None]
            good, reason = (
                coverage(row, kind, limits) if row else (False, "Workflow was not captured")
            )
            if not applicable:
                good, reason = False, "No performance limits supplied"
            checks = []
            for key in applicable:
                metric = (
                    metrics.get("mean_W")
                    if key.startswith("mean_")
                    else (
                        metrics.get("endpoint_change_percent")
                        if kind == "WF-02"
                        else row["results"]["metrics"].get("cycle_spread_percent")
                        if row
                        else None
                    )
                )
                value = (
                    Decimal(metric) * (1000 if key.startswith("mean_") else 1)
                    if metric is not None
                    else None
                )
                if key == "max_abs_endpoint_change_percent" and value is not None:
                    value = abs(value)
                limit = Decimal(limits[key])
                outcome = (
                    "Not evaluated"
                    if not good or value is None
                    else (
                        "Pass"
                        if (value >= limit if key == "mean_min_mW" else value <= limit)
                        else "Fail"
                    )
                )
                checks.append(
                    dict(
                        limit=key,
                        observed=str(value) if value is not None else None,
                        threshold=limits[key],
                        outcome=outcome,
                    )
                )
            outcome = (
                "Fail"
                if any(x["outcome"] == "Fail" for x in checks)
                else (
                    "Pass"
                    if checks and all(x["outcome"] == "Pass" for x in checks)
                    else "Not evaluated"
                )
            )
            if good and any(x["outcome"] == "Not evaluated" for x in checks):
                reason = "A required measurement metric is unavailable"
            rows.append(
                dict(
                    workflow=kind,
                    run_id=row["native"]["run_id"] if row else None,
                    execution=row["native"]["status"] if row else "not captured",
                    metrics=metrics,
                    limits=limits,
                    coverage_satisfied=good,
                    reason=reason,
                    checks=checks,
                    outcome=outcome,
                )
            )
    outcome = (
        "Fail"
        if any(x["outcome"] == "Fail" for x in rows)
        else (
            "Pass"
            if data["execution"] == "completed"
            and rows
            and all(x["outcome"] == "Pass" for x in rows)
            else "Not evaluated"
        )
    )
    return dict(
        schema="hp437b.acceptance-results.v1",
        run_id=data["run_id"],
        mode=data["mode"],
        original_execution=data["execution"],
        source_inventory_sha256=data["source_inventory_sha256"],
        criteria=criteria,
        criteria_sha256=r.digest(r.encoded(criteria)),
        outcome=outcome,
        workflows=rows,
    )


def provenance(data, meta):
    return dict(
        source_run_id=data["run_id"],
        source_inventory_sha256=data["source_inventory_sha256"],
        original_setup=data["setup"],
        acquisition_software=data["software"],
        assessment_id=meta["assessment_id"],
        evaluated_utc=meta["evaluated_utc"],
        assessor=meta["assessor"],
        criteria_sha256=meta["criteria_sha256"],
        timing="post_capture",
    )


def validate_pair(source, output):
    bundle = p.Bundle(output)
    bundle.inventory("artifacts.json", p._json(bundle.read("artifacts.json"))["mode"])
    meta = bundle.json("metadata.json")
    p.require(
        meta["schema"] == REPORT_SCHEMA and meta["timing"] == "post_capture",
        "Invalid assessment metadata",
    )
    data = collect(source, meta["source_workflow"])
    result = evaluate(data, bundle.json("criteria.json"))
    p.require(
        bundle.json("results.json") == result
        and meta["criteria_sha256"] == result["criteria_sha256"]
        and meta["source_inventory_sha256"] == data["source_inventory_sha256"]
        and meta["run_id"] == data["run_id"]
        and meta["mode"] == data["mode"],
        "Assessment differs from evidence or criteria",
    )
    p.require(
        bundle.json("provenance.json") == provenance(data, meta), "Assessment provenance mismatch"
    )
    return data["run_id"]


def publish(source_job, output, request, criteria, assessor=None, *, expected_hash=None):
    from . import report_delivery as delivery

    source_job, output = Path(source_job), Path(output)
    source = source_job / "capture"
    workflow = request["workflows"][0] if request["mode"] == "physical" else None
    with run_history.closed_capture(source_job):
        data = collect(source, workflow)
        p.require(
            expected_hash is None or data["source_inventory_sha256"] == expected_hash,
            "Source capture changed",
        )
        result = evaluate(data, criteria)
        delivery.preflight_delivery(source, output, pdf=True, package=True)
        output.mkdir()
        producer = report_identity.identify()
        meta = dict(
            schema=REPORT_SCHEMA,
            run_id=data["run_id"],
            mode=data["mode"],
            assessment_id=str(uuid.uuid4()),
            timing="post_capture",
            source_workflow=workflow,
            source_inventory_sha256=data["source_inventory_sha256"],
            criteria_sha256=result["criteria_sha256"],
            evaluated_utc=datetime.now(UTC).isoformat(),
            assessor=report_context.validate_operator(assessor),
            report_producer=producer,
        )
        for name, value in [
            ("criteria.json", result["criteria"]),
            ("results.json", result),
            ("metadata.json", meta),
            ("provenance.json", provenance(data, meta)),
        ]:
            (output / name).write_bytes(r.encoded(value))

        def n(value, scale=1):
            return "Not captured" if value is None else pdf._number(Decimal(value) * scale)

        rows = []
        for item in result["workflows"]:
            limits = item["limits"]
            text = []
            for key in PERFORMANCE:
                if limits.get(key) is not None:
                    label = {
                        "mean_min_mW": "Mean ≥",
                        "mean_max_mW": "Mean ≤",
                        "max_abs_endpoint_change_percent": "|Drift| ≤",
                        "max_cycle_spread_percent": "Spread ≤",
                    }[key]
                    text.append(
                        label + " " + limits[key] + (" mW" if key.startswith("mean_") else "%")
                    )
            measured = n(item["metrics"].get("mean_W"), 1000) + " mW"
            if (
                item["workflow"] == "WF-02"
                and item["metrics"].get("endpoint_change_percent") is not None
            ):
                measured += "; drift " + n(item["metrics"]["endpoint_change_percent"]) + "%"
            if item["workflow"] == "WF-03" and data["rows"].get("WF-03"):
                spread = data["rows"]["WF-03"]["results"]["metrics"].get("cycle_spread_percent")
                if spread is not None:
                    measured += "; spread " + n(spread) + "%"
            rows.append(
                [
                    item["workflow"],
                    n(item["metrics"].get("zero_W"), 1000000),
                    measured,
                    item["outcome"],
                    "; ".join(text) or "None supplied",
                ]
            )
        lines = [
            "Test: Supplied-limit assessment of saved POWER REF capture",
            "Measured: " + data["started_utc"],
            "Assessed: " + meta["evaluated_utc"],
            "Assessor: " + (meta["assessor"] or "Not recorded"),
            "Criteria source: " + (result["criteria"]["source"] or "Not supplied"),
            "Original execution: "
            + data["execution"]
            + "; supplied-limit result: "
            + result["outcome"],
        ]
        notes = [
            "Post-capture decision; original reports and measurements are unchanged.",
            "Inclusive boundaries; no uncertainty guard band. No accuracy, calibration, or compliance verdict.",
        ]
        for item in result["workflows"]:
            lim = item["limits"]
            label = (
                "per bin"
                if item["workflow"] == "WF-02"
                else "per cycle"
                if item["workflow"] == "WF-03"
                else "plateau"
            )
            if not any(lim.get(key) is not None for key in PERFORMANCE):
                notes.append(item["workflow"] + ": No performance limits supplied.")
                continue
            notes.append(
                item["workflow"]
                + ": "
                + item["reason"]
                + "; minimum samples "
                + str(lim.get("min_valid_samples") or "not supplied")
                + " "
                + label
                + "; maximum gap "
                + str(lim.get("max_gap_s") or "not supplied")
                + " s."
            )
        issues = (data["setup"] or {}).get("known_issues", [])
        if issues:
            notes.append("Recorded equipment issues: " + "; ".join(issues))
        esc = lambda v: html.escape(str(v))  # noqa: E731
        page = (
            "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>RF Output Power Test</title><style>body{font:16px system-ui;color:#18242b;max-width:900px;margin:32px auto;padding:24px}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:12px;border-bottom:1px solid #cbd6dc}a{color:#135c91}footer{border-top:1px solid #cbd6dc;padding-top:16px;margin-top:24px;font-size:13px}p{overflow-wrap:anywhere}</style>"
            + "<h1>RF Output Power Test</h1><h2>Post-capture supplied-limit assessment</h2>"
            + "".join("<p>" + esc(x) + "</p>" for x in lines)
            + "<table><tr>"
            + "".join(
                "<th>" + esc(x) + "</th>"
                for x in ["Workflow", "Zero (µW)", "Measured result", "Result", "Limits"]
            )
            + "</tr>"
            + "".join(
                "<tr>" + "".join("<td>" + esc(x) + "</td>" for x in row) + "</tr>" for row in rows
            )
            + "</table>"
            + "".join("<p>" + esc(x) + "</p>" for x in notes)
            + "<p><a href='criteria.json'>Criteria</a> · <a href='results.json'>Full decision record</a></p>"
            + "<footer>"
            + esc(report_sheet.producer_note(producer))
            + "<br>Assessment: "
            + meta["assessment_id"]
            + "<br>Record: "
            + data["run_id"]
            + "</footer></html>"
        )
        (output / "report.html").write_text(page)
        (output / "appendix.html").write_text(page)
        pdf._write(
            output,
            lines=lines,
            columns=["Workflow", "Zero (µW)", "Measured result", "Result", "Supplied limits"],
            rows=rows,
            widths=[0.8, 0.9, 0.9, 1.1, 2.3],
            notes=notes,
            producer=producer,
            run_id=data["run_id"],
            physical=data["mode"] == "physical",
            source_label="POWER REF — post-capture assessment"
            if data["mode"] == "physical"
            else "SYNTHETIC — supplied-limit assessment; no physical RF",
        )
        _seal(output, p._json((output / "metadata.json").read_bytes()))
        p.require(
            collect(source, workflow)["source_inventory_sha256"] == data["source_inventory_sha256"],
            "Source capture changed",
        )
        delivery.package(source, output)
        return result
