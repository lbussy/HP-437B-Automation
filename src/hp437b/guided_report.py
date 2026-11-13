"""Deterministic reports of sealed operator-guided sweeps; no acquisition."""

import csv
import html
from decimal import Decimal as D
from pathlib import Path

from . import guided_sweep as sweep
from . import pdf_reports as pdf
from . import provenance as p
from . import report_identity, report_sheet
from . import reporting as r
from .workflow_report import _seal, preflight

SCHEMA = "hp437b.guided-sweep-report.v1"


def provenance(record, bundle):
    return dict(
        schema="hp437b.guided-sweep-provenance.v1",
        run_id=record["run_id"],
        mode=record["mode"],
        operator=record["operator"],
        equipment=record["equipment"],
        declared_plan=record["plan"],
        prepared=record["prepared"],
        label_basis="Operator-confirmed declarations; not independently measured",
        evidence={
            name: dict(sha256=item["sha256"], bytes=item["bytes"])
            for name, item in bundle.entries.items()
        },
    )


def validate_pair(source, output):
    record, values, bundle = sweep.load(source)
    report = p.Bundle(output)
    report.inventory("artifacts.json", record["mode"])
    p.require(
        report.json("results.json") == values, "Guided report results differ from native evidence"
    )
    p.require(
        report.json("provenance.json") == provenance(record, bundle), "Guided provenance mismatch"
    )
    return record["run_id"]


def plots(output, record, result):
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    plan = record["plan"]
    files = []
    for axis, group, title in (
        ("frequency", "drive", "Power versus frequency"),
        ("drive", "frequency", "Power versus drive setting"),
    ):
        labels = plan["frequencies" if axis == "frequency" else "drives"]
        groups = plan["drives" if group == "drive" else "frequencies"]
        if len(labels) < 2:
            continue
        fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
        for label in groups:
            data = {
                row[axis]: float(D(row["mean_W"]) * 1000)
                for row in result["points"]
                if row[group] == label
                and row["status"] == "completed"
                and row["mean_W"] is not None
            }
            ax.plot(
                range(len(labels)),
                [data.get(x, float("nan")) for x in labels],
                marker="o",
                label=label,
            )
        ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
        ax.set_xlabel(
            "Frequency label (operator confirmed)"
            if axis == "frequency"
            else "Drive label (operator confirmed)"
        )
        ax.set_ylabel("Meter-indicated power at sensor input (mW)")
        ax.set_title(title + (" · SIMULATED" if record["mode"] == "synthetic" else ""))
        ax.grid(axis="y", alpha=0.2)
        ax.legend(fontsize=8, ncols=min(4, len(groups)))
        for extension in ("png", "svg"):
            filename = axis + "." + extension
            fig.savefig(output / filename, dpi=140)
            files.append(filename)
        plt.close(fig)
    return files


def publish(source, output, *, plot=True, package=True):
    from . import report_delivery as delivery

    source, output = preflight(source, output, plots=plot)
    delivery.preflight_delivery(source, output, pdf=True, package=package)
    record, result, bundle = sweep.load(source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True)
    producer = report_identity.identify()
    meta = dict(
        schema=SCHEMA,
        run_id=record["run_id"],
        mode=record["mode"],
        source_inventory_sha256=source_hash,
        report_producer=producer,
    )
    for name, value in (
        ("metadata", meta),
        ("results", result),
        ("provenance", provenance(record, bundle)),
    ):
        (output / (name + ".json")).write_bytes(r.encoded(value))
    with (output / "points.csv").open("x", newline="") as handle:
        fields = list(result["points"][0])
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        writer.writerows(result["points"])
    images = plots(output, record, result) if plot else []
    esc = lambda value: html.escape(str(value))  # noqa: E731
    reference = sweep.reference_source(record["equipment"])
    title = "Operator-guided POWER REF repeats" if reference else "Operator-guided radio sweep"
    description = (
        "Recorded measurements" if record["mode"] == "physical" else "SIMULATED measurements"
    )
    notes = [
        "Frequency and drive labels are operator-confirmed declarations.",
        "Power is the meter indication at sensor input. Existing meter corrections are retained; no new fixture correction, uncertainty, or automatic baseline subtraction is added.",
        "Measurement notes: " + record["plan"]["measurement_notes"],
        "Acceptance: NOT EVALUATED. No acceptance limits were supplied.",
    ]
    if reference:
        notes.insert(
            0,
            "Fixed nominal 50 MHz POWER REF; repeat labels are capture order, not changed drive settings. No transmitter or frequency sweep was tested. Operator switches POWER REF manually and must turn it off after stopping or finishing.",
        )
    if record["equipment"]:
        notes += [
            "Known equipment issues: "
            + ("; ".join(record["equipment"]["known_issues"]) or "None reported")
        ]
    notes += ["Stop reason: " + record["error"]] if record["error"] else []
    lines = [
        "Test: " + title,
        ("Source: " if reference else "Radio: ") + record["plan"]["name"],
        "Operator: " + (record["operator"] or "Not recorded"),
        "When: " + record["started_utc"],
        "Execution: " + result["execution"] + "; acceptance: NOT EVALUATED",
    ]
    observed = [
        D(row["mean_W"])
        for row in result["points"]
        if row["status"] == "completed" and row["mean_W"] is not None
    ]
    rows = [
        ["Points captured", f"{result['completed_points']} / {result['requested_points']}"],
        [
            "Frequency labels / drive labels",
            f"{len(record['plan']['frequencies'])} / {len(record['plan']['drives'])}",
        ],
        [
            "Lowest / highest point mean",
            (pdf._number(min(observed) * 1000) + " / " + pdf._number(max(observed) * 1000) + " mW")
            if observed
            else "Not captured",
        ],
        ["Measurement plane", "Meter indication at sensor input"],
        ["Point order", record["plan"]["order"] + " first"],
    ]
    table = (
        "<table><thead><tr>"
        + "".join(
            "<th>" + esc(x) + "</th>"
            for x in ("Point", "Frequency", "Drive", "Status", "Samples", "Mean (mW)", "Mean (dBm)")
        )
        + "</tr></thead><tbody>"
    )
    for point in result["points"]:
        table += (
            "<tr>"
            + "".join(
                "<td>" + esc(x) + "</td>"
                for x in (
                    point["point_id"],
                    point["frequency"],
                    point["drive"],
                    point["status"],
                    point["samples"],
                    pdf._number(D(point["mean_W"]) * 1000) if point["mean_W"] is not None else "—",
                    pdf._number(point["mean_dBm"]),
                )
            )
            + "</tr>"
        )
    table += "</tbody></table>"
    page = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>RF Output Power Test</title>"
        "<style>body{font:16px/1.5 system-ui;color:#18242b;max-width:1100px;margin:auto;padding:24px}td,th{padding:8px;text-align:left;border-bottom:1px solid #cbd6dc}img{max-width:100%}.table{overflow-x:auto}footer{margin-top:28px}</style><h1>RF Output Power Test</h1><p>"
        + esc(description)
        + "</p>"
        + "".join("<p>" + esc(line) + "</p>" for line in lines + notes)
        + "".join(
            "<img src='"
            + name
            + "' alt='"
            + (
                "Power versus frequency labels"
                if name.startswith("frequency")
                else "Power versus drive setting labels"
            )
            + "'>"
            for name in images
            if name.endswith(".svg")
        )
        + "<div class='table'>"
        + table
        + "</div><p><a href='points.csv'>Full point table (CSV)</a> · <a href='results.json'>Statistics (JSON)</a> · <a href='report.pdf'>PDF summary</a></p><footer>"
        + esc(
            "Equipment: "
            + (
                record["equipment"]["meter_serial"] + " / " + record["equipment"]["sensor_serial"]
                if record["equipment"]
                else "Simulated meter"
            )
        )
        + "<br>"
        + esc(report_sheet.producer_note(producer))
        + "<br>Record: "
        + esc(record["run_id"])
        + "</footer></html>"
    )
    (output / "report.html").write_text(page)
    (output / "appendix.html").write_text(page)
    # The one-page PDF summarizes coverage; complete matrices/plots stay in HTML/CSV.
    pdf._write(
        output,
        lines=lines,
        columns=["Observation", "Result"],
        rows=rows,
        widths=[1, 2],
        notes=[
            notes[0],
            notes[1],
            "Complete point table, plots, notes, and stop reasons are in the HTML report.",
        ],
        producer=producer,
        run_id=record["run_id"],
        physical=record["mode"] == "physical",
        source_label=description + " · operator-guided radio sweep",
    )
    _seal(output, p._json((output / "metadata.json").read_bytes()))
    p.require(
        r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
        "Capture changed during reporting",
    )
    if package:
        delivery.package(source, output)
    return result


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    publish(args.bundle, args.output, plot=not args.no_plots)


if __name__ == "__main__":
    main()
