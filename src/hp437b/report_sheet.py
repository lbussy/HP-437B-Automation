"""Human RF-output result sheets. Detailed machine evidence lives in an appendix."""

import html
from datetime import UTC, datetime
from decimal import Decimal


def _value(entity, name, default=None):
    value = entity.get("facts", {}).get(name, {}).get("value")
    return default if value is None else value


def _text(value, default="Not recorded"):
    return value if isinstance(value, str) and value.strip() else default


def _short(text, limit=240):
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "... (see appendix)"


def _when(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def _n(value):
    value = Decimal(str(value))
    text = format(value, ".6g")
    if "e" in text.lower() and Decimal("0.000001") <= abs(value) < Decimal("1000000"):
        text = format(Decimal(text), "f")
    return text.rstrip("0").rstrip(".") if "." in text and "e" not in text.lower() else text


def build(results, record):
    """Present the recorded DUT honestly; a POWER REF run cannot become a radio test."""
    subject, run = record["dut"], record["run"]
    reference = subject["kind"] == "reference_signal"
    subject_name = (
        "POWER REF output (internal reference source)"
        if reference
        else _text(
            _value(subject, "name", _value(subject, "description")), "Test device not identified"
        )
    )
    identity = _text(_value(subject, "serial"), "")
    signal = _value(subject, "declared_signal", {})
    frequency = signal.get("nominal_frequency_Hz") if isinstance(signal, dict) else None
    try:
        frequency = (
            f"{_n(Decimal(str(frequency)) / Decimal('1000000'))} MHz (declared)"
            if frequency is not None
            else "Not recorded"
        )
    except (ValueError, ArithmeticError):
        frequency = "Not recorded"
    started, finished = (_when(_value(run, key)) for key in ("started_utc", "finished_utc"))
    when = started.strftime("%d %b %Y, %H:%M:%S") if started else "Not recorded"
    if started and finished:
        when += " - " + finished.strftime(
            "%H:%M:%S" if started.date() == finished.date() else "%d %b %Y, %H:%M:%S"
        )
    if started:
        when += " UTC"
    primary = next((key for key in ("S40", "S30") if results["stages"][key].get("valid", 0)), None)
    data = results["stages"].get(primary, {})
    metrics = data.get("metrics", {})
    mean = Decimal(metrics["mean_W"]) if metrics.get("mean_W") is not None else None
    factor, unit = (
        (Decimal(1), "W") if mean is not None and abs(mean) >= 1 else (Decimal(1000), "mW")
    )
    if mean is not None and abs(mean) < Decimal("0.000001"):
        factor, unit = Decimal(1000000), "µW"

    def power(key):
        text = metrics.get(key)
        return f"{_n(Decimal(text) * factor)} {unit}" if text is not None else "Not measured"

    baseline = results["stages"].get("S10", {})
    baseline_mean = baseline.get("metrics", {}).get("mean_W")
    baseline_zero = (
        f"{_n(Decimal(baseline_mean) * Decimal(1000000))} µW (mean of {baseline['valid']} readings)"
        if baseline.get("valid", 0) and baseline_mean is not None
        else "Not captured"
    )
    rows = [
        ('RF-off baseline ("zero")', baseline_zero),
        ("Average RF power", power("mean_W")),
        (
            "Power in dBm",
            f"{10 * (mean / Decimal('0.001')).log10():.4f} dBm"
            if mean is not None and mean > 0
            else "Not available",
        ),
        (
            "Observed range",
            f"{_n(Decimal(metrics['min_W']) * factor)} - {_n(Decimal(metrics['max_W']) * factor)} {unit}"
            if mean is not None
            else "Not measured",
        ),
        ("Peak-to-peak variation", power("peak_to_peak_W")),
        (
            "Readings",
            f"{data['valid']} valid / {data['attempted']} attempted"
            if primary
            else "No RF power readings captured",
        ),
        (
            "Recorded sample span",
            f"{data['receipt_span_s']:.2f} s"
            if data.get("receipt_span_s") is not None
            else "Not recorded",
        ),
    ]
    execution = {"completed": "Completed", "failed": "FAILED", "interrupted": "INTERRUPTED"}[
        results["status"]
    ]
    notes = []
    if results["status"] != "completed":
        notes.append(
            "The test did not complete. Available readings are partial results; see the appendix for the failure and final source state."
            if primary
            else "The test did not complete; no RF power readings were captured. See the appendix for the failure and final source state."
        )
    if primary == "S30":
        notes.append("Short-capture readings only; the sustained measurement is unavailable.")
    issues = _value(run, "known_equipment_issues", [])
    if isinstance(issues, str):
        issues = [issues]
    if isinstance(issues, list):
        for issue in issues[:2]:
            if isinstance(issue, str) and issue.strip():
                notes.append(_short(issue))
        if len(issues) > 2:
            notes.append("Additional equipment limitations are recorded in the appendix.")
    notes.append(
        "Power is reported at the sensor input. No fixture-loss correction or measurement uncertainty is added."
    )
    equipment = []
    for item in record["equipment"]:
        if item["role"] not in ("meter", "sensor"):
            continue
        identifications = _value(item, "reported_identifications", [])
        model = (
            next(
                (d.get("model") for d in identifications if isinstance(d, dict) and d.get("model")),
                None,
            )
            if isinstance(identifications, list)
            else None
        )
        # These models are the fixed WF-01 measurement fixture; serials retain label origin.
        name = _text(
            model,
            "HP 437B"
            if reference and item["role"] == "meter"
            else "HP 8482A"
            if reference and item["role"] == "sensor"
            else item["role"].capitalize(),
        )
        name = _short(name, 64)
        serial = _value(item, "label_serial")
        if reference and name == "437B":
            name = "HP 437B"
        equipment.append(
            name
            + (
                f" S/N {_short(serial, 64)}"
                if isinstance(serial, str) and serial
                else " (serial not recorded)"
            )
        )
    return {
        "title": "RF Output Power Test",
        "subject": _short(subject_name, 180),
        "subject_id": _short(identity, 100),
        "test": _text(_value(run, "test_name"), "Output power and repeatability"),
        "when": when,
        "frequency": frequency,
        "mode": results["mode"],
        "execution": execution,
        "acceptance": "NOT EVALUATED - acceptance limits not specified"
        if _value(subject, "measurement_criteria") is None
        else "NOT EVALUATED - see recorded criteria in appendix",
        "capture": (
            "Partial sustained measurement"
            if data.get("outcome") in ("failed", "interrupted")
            else "Sustained measurement"
        )
        if primary == "S40"
        else "Short capture only"
        if primary
        else "No measurement captured",
        "rows": rows,
        "notes": notes,
        "equipment": "; ".join(equipment) or "See traceability appendix",
        "run_id": _short(results["run_id"], 90),
        "has_plot": primary is not None,
    }


STYLE = """
@page { size: Letter; margin: 14mm; }
* { box-sizing: border-box; }
body { margin:0; background:#f2f3f4; color:#17212a; font:14px/1.4 Arial,Helvetica,sans-serif; }
.sheet { max-width:760px; margin:28px auto; padding:32px 36px; background:white; }
h1 { margin:0 0 18px; font-size:25px; line-height:1.15; font-weight:700; }
h2 { font-size:15px; margin:18px 0 7px; }
p { margin:4px 0 9px; }
.meta { width:100%; border-collapse:collapse; margin-bottom:14px; }
.meta th { width:110px; text-align:left; color:#46535e; font-weight:400; vertical-align:top; }
.meta td { font-weight:600; }
.meta td,.meta th { padding:3px 0; overflow-wrap:anywhere; }
.outcome { border-top:2px solid #244e63; border-bottom:1px solid #aab5bc; padding:9px 0; }
.outcome p { margin:2px 0; }
.readings { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
.readings th,.readings td { text-align:left; padding:5px 0; border-bottom:1px solid #e1e5e8; }
.readings th { font-weight:400; width:46%; }
.readings td { font-weight:600; }
figure { margin:14px 0 0; }
figure img { width:100%; height:auto; display:block; }
figcaption { font-size:12px; color:#46535e; margin-top:3px; }
.notes { padding-left:17px; margin:0; font-size:12px; }
.notes li { margin-bottom:4px; }
footer { border-top:1px solid #aab5bc; margin-top:16px; padding-top:8px; font-size:11px; overflow-wrap:anywhere; }
footer p { margin:3px 0; }
a { color:#164e69; text-underline-offset:3px; }
a:focus-visible { outline:2px solid #164e69; outline-offset:3px; }
::selection { background:#c5dce9; color:#17212a; }
.simulation { font-weight:700; color:#6f3900; }
@media(max-width:600px) { .sheet { margin:0; padding:20px 16px; } h1 { font-size:23px; } .meta th { width:90px; } }
@media print { body { background:white; font-size:10pt; line-height:1.3; } .sheet { margin:0; padding:0; max-width:none; } h1 { font-size:18pt; margin-bottom:12px; } h2 { margin-top:12px; } figure { margin-top:10px; } figure img { max-height:46mm; object-fit:contain; } .screen-links { display:none; } footer { margin-top:12px; } .notes { font-size:9pt; } }
"""


def _markdown(value):
    reserved = set("\\`*_{}[]()#+-.!|")
    return "".join(
        f"&#{ord(char)};"
        if char in reserved
        else "<br>"
        if char == "\n"
        else ""
        if char == "\r"
        else html.escape(char, quote=True)
        for char in str(value)
    )


def producer_note(producer):
    producer = producer or {}
    commit = producer.get("commit")
    release = producer.get("release_version")
    if release and commit and producer.get("dirty") is False:
        identity = f"v{release}"
    else:
        identity = f"commit {commit[:12]}" if commit else "development build (commit unavailable)"
    if producer.get("dirty") is True:
        identity += " (modified working tree)"
    elif commit and producer.get("dirty") is None and producer.get("basis") == "source_checkout":
        identity += " (working-tree state unknown)"
    return f"Report Harness: HP 437B Automation {identity}"


def render(results, record, *, plots, producer=None, operator=None):
    model = build(results, record)
    provenance_note = producer_note(producer)
    esc = lambda text: html.escape(str(text), quote=True)  # noqa: E731
    meta = [
        (
            "Device / source",
            model["subject"] + (f" | S/N {model['subject_id']}" if model["subject_id"] else ""),
        ),
        ("Test", model["test"]),
        ("Operator", operator or _text(_value(record["run"], "operator"))),
        ("When", model["when"]),
        ("Frequency", model["frequency"]),
    ]
    body = [f"<h1>{esc(model['title'])}</h1>"]
    md = [f"# {model['title']}", ""]
    if model["mode"] == "synthetic":
        line = "SYNTHETIC - simulated readings; no physical transmitter was measured."
        body.append(f"<p class='simulation'>{line}</p>")
        md += [f"**{line}**", ""]
    body.append(
        "<table class='meta'>"
        + "".join(f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in meta)
        + "</table>"
    )
    for key, value in meta:
        md += [f"**{_markdown(key)}:** {_markdown(value)}  "]
    body.append(
        f"<section class='outcome'><p><strong>Test execution:</strong> {esc(model['execution'])}</p><p><strong>Acceptance:</strong> {esc(model['acceptance'])}</p></section>"
    )
    md += [
        "",
        f"**Test execution:** {esc(model['execution'])}",
        "",
        f"**Acceptance:** {esc(model['acceptance'])}",
        "",
        f"## {model['capture']}",
        "",
        "| Result | Measured value |",
        "| --- | --- |",
    ]
    body.append(
        f"<h2>{esc(model['capture'])}</h2><table class='readings'>"
        + "".join(
            f"<tr><th scope='row'>{esc(k)}</th><td>{esc(v)}</td></tr>" for k, v in model["rows"]
        )
        + "</table>"
    )
    md += [f"| {_markdown(k)} | {_markdown(v)} |" for k, v in model["rows"]]
    if plots and model["has_plot"]:
        body.append(
            "<figure><img src='power-trend.png' alt='Captured RF power over elapsed measurement time'><figcaption>Individual power readings at the sensor input. Dotted lines mark failed attempts.</figcaption></figure>"
        )
        md += ["", "![Captured RF output power](power-trend.png)"]
    body.append(
        "<h2>Notes affecting interpretation</h2><ul class='notes'>"
        + "".join(f"<li>{esc(note)}</li>" for note in model["notes"])
        + "</ul>"
    )
    md += ["", "## Notes affecting interpretation", ""] + [
        f"- {_markdown(note)}" for note in model["notes"]
    ]
    body.append(
        f"<footer><p><strong>Equipment traceability:</strong> {esc(model['equipment'])}</p><p>{esc(provenance_note)}</p><p>Record: {esc(model['run_id'])}</p><p class='screen-links'><a href='evidence.html'>Technical appendix and full traceability</a></p></footer>"
    )
    md += [
        "",
        f"**Equipment traceability:** {_markdown(model['equipment'])}",
        "",
        _markdown(provenance_note),
        "",
        f"Record: {_markdown(model['run_id'])}",
        "",
        "[Technical appendix and full traceability](evidence.md)",
        "",
    ]
    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\"><title>RF Output Power Test</title><style>"
        + STYLE
        + "</style></head><body><main class='sheet'>"
        + "\n".join(body)
        + "</main></body></html>\n"
    )
    return "\n".join(md), page
