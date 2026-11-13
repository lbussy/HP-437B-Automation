"""Saved WF-01–WF-03 POWER REF delivery; never acquires or changes equipment."""

import html
import tempfile
from pathlib import Path

from . import pdf_reports as pdf
from . import provenance as p
from . import report_context, report_identity, report_sheet
from . import reporting as r
from .workflow_report import _seal, preflight

TITLES = {
    "WF-01": "POWER REF baseline and output",
    "WF-02": "Sustained output stability",
    "WF-03": "Transmission-cycle repeatability",
}
SCHEMA = "hp437b.reference-report.v1"


def load(source, kind, *, allow_synthetic=False):
    p.require(kind in TITLES, "Unsupported POWER REF workflow")
    if kind == "WF-01":
        provenance = p.import_wf01(source)
        with tempfile.TemporaryDirectory(prefix="hp437b-reference-report-") as directory:
            target = Path(directory) / "provenance.json"
            target.write_bytes(r.encoded(provenance))
            _, results, _ = r.prepare(source, target)
        record = p._json(p.Bundle(source).read("workflow.json"))
    else:
        from . import repeatability, stability

        record, results, provenance, _ = (stability if kind == "WF-02" else repeatability).load(
            source
        )
    p.require(
        record["mode"] == "physical" or (allow_synthetic and record["mode"] == "synthetic"),
        "POWER REF operator reports require physical-format captures",
    )
    return record, results, provenance


def summary(record, results, kind):
    def number(value, scale=1, unit=""):
        return "Not captured" if value is None else pdf._number(r.number(value) * scale) + unit

    stages = results["stages"]
    zero = (
        stages.get("S10" if kind == "WF-01" else "baseline-before", {})
        .get("metrics", {})
        .get("mean_W")
    )
    rows = [["Pre-RF zero (signed)", number(zero, 1000000, " µW")]]
    if kind == "WF-01":
        stage = stages.get("S40", {})
        rows += [
            ["Average RF power", number(stage.get("metrics", {}).get("mean_W"), 1000, " mW")],
            ["Valid plateau readings", str(stage.get("valid", 0))],
        ]
    else:
        metrics = results["metrics"]
        mean = metrics.get("mean_W", metrics.get("equal_cycle_mean_W"))
        rows += [["Average RF power", number(mean, 1000, " mW")]]
        if kind == "WF-02":
            rows += [
                ["Endpoint change", number(metrics["endpoint_change_percent"], unit="%")],
                ["Valid plateau readings", str(results["coverage"]["valid"])],
            ]
        else:
            rows += [
                ["Cycle-mean spread", number(metrics.get("cycle_spread_W"), 1000, " mW")],
                ["Completed cycles", str(results.get("completed_cycles", "See native report"))],
            ]
    rows += [
        [
            "Final reference / local (protocol)",
            record["final_state"]["source"] + " / " + record["final_state"]["local"],
        ]
    ]
    return dict(
        schema=SCHEMA,
        workflow=kind,
        mode=record["mode"],
        run_id=record["run_id"],
        execution=record["status"],
        acceptance="NOT EVALUATED",
        rows=rows,
        native_results=results,
    )


def validate_pair(source, output):
    report = p.Bundle(output)
    report.inventory("artifacts.json", p._json(report.read("artifacts.json"))["mode"])
    meta = report.json("metadata.json")
    record, results, provenance = load(source, meta["workflow"], allow_synthetic=True)
    p.require(
        meta["schema"] == SCHEMA
        and meta["run_id"] == record["run_id"]
        and meta["mode"] == record["mode"]
        and meta["source_inventory_sha256"] == r.digest(p.Bundle(source).read("artifacts.json")),
        "Reference report identity/source mismatch",
    )
    p.require(
        report.json("results.json") == summary(record, results, meta["workflow"]),
        "Reference report results differ from native evidence",
    )
    p.require(
        report.json("provenance.json") == provenance,
        "Reference report provenance differs from native evidence",
    )
    p.verify(provenance, source)
    return record["run_id"]


def publish(
    source, output, kind, *, plots=True, operator=None, package=True, allow_synthetic=False
):
    from . import report_delivery as delivery

    source, output = preflight(source, output, plots=plots)
    delivery.preflight_delivery(source, output, pdf=True, package=package)
    record, results, provenance = load(source, kind, allow_synthetic=allow_synthetic)
    values = summary(record, results, kind)
    operator = report_context.resolve_operator(
        operator, record.get("operator", record.get("setup", {}).get("operator"))
    )["value"]
    producer = report_identity.identify()
    source_hash = r.digest(p.Bundle(source).read("artifacts.json"))
    output.mkdir()
    (output / "provenance.json").write_bytes(r.encoded(provenance))
    if kind == "WF-01":
        with tempfile.TemporaryDirectory(prefix="hp437b-reference-provenance-") as directory:
            prov = Path(directory) / "provenance.json"
            prov.write_bytes(r.encoded(provenance))
            r.export(source, prov, output / "native", plots=plots, operator=operator)
    else:
        from . import repeatability, stability

        (stability if kind == "WF-02" else repeatability).publish(
            source, output / "native", plots=plots, operator=operator
        )
    meta = dict(
        schema=SCHEMA,
        mode=record["mode"],
        run_id=record["run_id"],
        workflow=kind,
        source_inventory_sha256=source_hash,
        report_producer=producer,
    )
    (output / "results.json").write_bytes(r.encoded(values))
    (output / "metadata.json").write_bytes(r.encoded(meta))
    lines = [
        "Test: " + TITLES[kind],
        "Source: Internal POWER REF; sensor input directly attached"
        + (" (simulated)" if record["mode"] == "synthetic" else ""),
        "Operator: " + (operator or "Not recorded"),
        "When: " + record["started_utc"],
        "Execution: " + record["status"] + "; acceptance: NOT EVALUATED",
    ]
    notes = [
        "Descriptive reference-source exercise; no transmitter or accuracy/compliance verdict.",
        "Signed source-off zero is not subtracted. No zero/CAL or factor adjustment.",
        "Front-panel live readings, RMT off, and POWER REF off require separate operator confirmation."
        if record["mode"] == "physical"
        else "Synthetic reference and cleanup only; no physical front-panel observation applies.",
        "Known equipment issues: " + "; ".join(record.get("setup", {}).get("known_issues", [])),
    ]
    esc = lambda value: html.escape(str(value))  # noqa: E731
    table = "".join(
        "<tr><th>" + esc(a) + "</th><td>" + esc(b) + "</td></tr>" for a, b in values["rows"]
    )
    page = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>RF Output Power Test</title><style>body{font:16px system-ui;color:#18242b;max-width:900px;margin:32px auto;padding:24px}td,th{text-align:left;padding:12px;border-bottom:1px solid #cbd6dc}a{color:#135c91}</style><h1>RF Output Power Test</h1>"
        + (
            "<p>SYNTHETIC - fictional reference exercise; no hardware</p>"
            if record["mode"] == "synthetic"
            else "<p>POWER REF — recorded measurement</p>"
        )
        + "".join("<p>" + esc(line) + "</p>" for line in lines)
        + "<table>"
        + table
        + "</table>"
        + "".join("<p>" + esc(line) + "</p>" for line in notes)
        + "<p><a href='native/report.html'>Full native report</a></p><footer>"
        + esc(
            "Equipment: "
            + record.get("setup", {}).get("meter_serial", "Simulated meter")
            + " / "
            + record.get("setup", {}).get("sensor_serial", "Simulated sensor")
        )
        + "<br>"
        + esc(report_sheet.producer_note(producer))
        + "<br>Record: "
        + esc(record["run_id"])
        + "</footer></html>"
    )
    (output / "report.html").write_text(page)
    # Keep PDF's relative detail link valid while the native report remains sealed.
    (output / "appendix.html").write_text(
        "<!doctype html><meta http-equiv='refresh' content='0;url=native/report.html'><a href='native/report.html'>Native report</a>"
    )
    pdf._write(
        output,
        lines=lines,
        columns=["Observation", "Recorded result"],
        rows=values["rows"],
        widths=[1, 2],
        notes=notes,
        producer=producer,
        run_id=record["run_id"],
        physical=record["mode"] == "physical",
    )
    meta = p._json((output / "metadata.json").read_bytes())
    _seal(output, meta)
    p.require(
        r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
        "Capture changed during reference reporting",
    )
    if package:
        delivery.package(source, output)
    return values


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workflow", choices=list(TITLES), required=True)
    parser.add_argument("--operator")
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    publish(
        args.bundle, args.output, args.workflow, plots=not args.no_plots, operator=args.operator
    )
    print(args.output / "report.pdf")


if __name__ == "__main__":
    main()
