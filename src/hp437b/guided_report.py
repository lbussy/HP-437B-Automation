"""Deterministic reports of sealed operator-guided sweeps; no acquisition."""

import csv
import html
import re
from decimal import Decimal as D
from pathlib import Path

from . import guided_sweep as sweep
from . import pdf_reports as pdf
from . import provenance as p
from . import report_identity, report_sheet, sweep_matrix
from . import reporting as r
from .workflow_report import _seal, preflight

SCHEMA = "hp437b.guided-sweep-report.v1"
COMPLETE_SCHEMA = "hp437b.guided-combined-report.v2"


def check_complete_pdf(data, page_count):
    # ReportLab writes the generated page tree as plain PDF objects. Compare
    # its page-object count and tree count with the sealed renderer receipt.
    page_objects = re.findall(
        rb"(?m)^([0-9]+) 0 obj\r?\n<<(?:(?!endobj).)*?/Type /Page\s*>>\s*endobj",
        data,
        re.S,
    )
    trees = re.findall(rb"/Count ([0-9]+) /Kids \[([^\]]*)\] /Type /Pages", data)
    p.require(
        data.startswith(b"%PDF-")
        and type(page_count) is int
        and page_count == len(page_objects)
        and page_count > 0
        and len(trees) == 1
        and int(trees[0][0]) == page_count
        and re.findall(rb"([0-9]+) 0 R", trees[0][1]) == page_objects,
        "Combined PDF page count differs from its sealed receipt",
    )


def provenance(record, bundle):
    return dict(
        schema="hp437b.guided-sweep-provenance.v1",
        run_id=record["run_id"],
        mode=record["mode"],
        operator=record["operator"],
        equipment=record["equipment"],
        declared_plan=record["plan"],
        prepared=record["prepared"],
        label_basis="Simulated setpoints; no transmitter control or RF evidence"
        if record["schema"] == sweep_matrix.SCHEMA
        else "Control/1 requested carrier and job-bound Pico GPIO drive"
        if record["schema"] == sweep_matrix.PICO_SCHEMA
        else "Operator-confirmed declarations; not independently measured",
        evidence={
            name: dict(sha256=item["sha256"], bytes=item["bytes"])
            for name, item in bundle.entries.items()
        },
    )


def validate_pair(source, output):
    record, values, bundle = sweep.load(source)
    report = p.Bundle(output)
    report.inventory("artifacts.json", record["mode"])
    meta = report.json("metadata.json")
    p.require(
        meta["source_inventory_sha256"] == r.digest(bundle.read("artifacts.json"))
        and meta["run_id"] == record["run_id"],
        "Guided report source binding mismatch",
    )
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
        basis = (
            "simulated setpoint"
            if record["schema"] == sweep_matrix.SCHEMA
            else "Pico job setting"
            if record["schema"] == sweep_matrix.PICO_SCHEMA
            else "operator confirmed"
        )
        ax.set_xlabel(("Frequency" if axis == "frequency" else "Drive") + f" label ({basis})")
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


def _milliwatts(value):
    return pdf._number(D(value) * 1000 if value is not None else None)


def _point_factor(bundle, row, record):
    prefix = ""
    while (
        "continuation" in record
        and int(row["point_id"][1:]) <= record["continuation"]["carried_points"]
    ):
        prefix += "prior/"
        record = bundle.json(prefix + "workflow.json")
    key = prefix + row["point_id"] + "/samples.csv.session.json"
    if key not in bundle.entries:
        return "—"
    correction = bundle.json(key).get("sensor_correction")
    if correction and correction["status_checked"]:
        return correction["commanded_factor_percent"] + "%"
    return "—"


def publish(source, output, *, plot=True, package=None, include_pdf=None):
    from . import report_delivery as delivery

    source, output = preflight(source, output, plots=plot)
    record, result, bundle = sweep.load(source)
    simulated = record["schema"] == sweep_matrix.SCHEMA
    live_pico = record["schema"] == sweep_matrix.PICO_SCHEMA
    automatic = simulated or live_pico
    if automatic and include_pdf is None:
        include_pdf = False
    p.require(include_pdf is None or type(include_pdf) is bool, "Invalid PDF option")
    complete = include_pdf is not None
    p.require(
        not complete or record["plan"]["series"] == "combined",
        "PDF selection is available for the combined sweep",
    )
    wants_pdf = include_pdf is not False
    package = wants_pdf if package is None else package
    p.require(not package or wants_pdf, "A guided package requires PDF output")
    delivery.preflight_delivery(source, output, pdf=wants_pdf, package=package)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True)
    producer = report_identity.identify()
    meta = dict(
        schema=COMPLETE_SCHEMA if complete else SCHEMA,
        run_id=record["run_id"],
        mode=record["mode"],
        source_inventory_sha256=source_hash,
        report_producer=producer,
    )
    if complete:
        meta["include_pdf"] = wants_pdf
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
        "Dial, carrier, drive, and power shown here are synthetic. No transmitter or meter was contacted."
        if simulated
        else "Pico Control/1 verifies the job and GPIO setting. The carrier is the requested setpoint."
        if live_pico
        else "Frequency and drive labels are operator-confirmed declarations.",
        "Power is the meter indication at sensor input. Configured sensor correction, when selected, is applied before each capture and retained in native session receipts. No new fixture correction, uncertainty, or automatic baseline subtraction is added.",
        "Measurement notes: " + record["plan"]["measurement_notes"],
        "Acceptance: NOT EVALUATED. No acceptance limits were supplied.",
    ]
    if complete:
        notes.append("Unfiltered GPIO harmonics can contribute to the sensor-input indication.")
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
    if simulated:
        lines.append("Simulated output: " + sweep_matrix.PROFILES[record["plan"]["profile"]][0])
    if live_pico:
        lines.append("RF output: Pico direct GPIO (GP2)")
        notes.append("Initial drive restoration: " + record["restoration"] + ".")
        if record.get("continuation"):
            count = record["continuation"]["carried_points"]
            notes.append(
                f"Includes {count} points carried forward from the sealed prior capture, with a fresh ZERO before the remaining points."
            )
        if result["limited_points"]:
            lines.append(f"Limited indications: {result['limited_points']}")
            notes.append(f"Limited points at the RF-off threshold: {result['limited_points']}.")
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
    columns = ["Point", "Frequency"]
    if automatic:
        columns.extend(["Dial Hz", "Test RF Hz"])
    columns.extend(["Drive", "Status", "N", "Mean mW", "dBm"])
    if complete:
        columns.extend(["Min mW", "Max mW", "Std dev mW", "CAL FAC"])
    table_rows = []
    for point in result["points"]:
        row = [point["point_id"], point["frequency"]]
        if automatic:
            row.extend([point["dial_hz"], point["carrier_hz"]])
        row.extend(
            [
                point["drive"],
                point["status"],
                point["samples"],
                _milliwatts(point["mean_W"]),
                pdf._number(point["mean_dBm"]),
            ]
        )
        if complete:
            row.extend(
                [
                    _milliwatts(point["min_W"]),
                    _milliwatts(point["max_W"]),
                    _milliwatts(point["stddev_W"]),
                    _point_factor(bundle, point, record),
                ]
            )
        table_rows.append(row)
    table = (
        "<table><thead><tr>"
        + "".join("<th scope='col'>" + esc(x) + "</th>" for x in columns)
        + "</tr></thead><tbody>"
    )
    for row in table_rows:
        table += "<tr>" + "".join("<td>" + esc(x) + "</td>" for x in row) + "</tr>"
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
        + "</div><p><a href='points.csv'>Full point table (CSV)</a> · <a href='results.json'>Statistics (JSON)</a>"
        + (" · <a href='report.pdf'>PDF report</a>" if wants_pdf else "")
        + "</p><footer>"
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
    if wants_pdf:
        pdf_rows = rows
        pdf_columns = ["Observation", "Result"]
        widths = [1, 2]
        pdf_notes = notes[:2] + [
            "Complete point table, plots, notes, and stop reasons are in the HTML report."
        ]
        if complete:
            pdf_columns = ["Point / band", *columns[2:]]
            widths = [
                1.35,
                *([1.05, 1.05] if automatic else []),
                0.8,
                1.2,
                0.5,
                1,
                0.75,
                0.95,
                0.95,
                1.05,
                0.95,
            ]
            pdf_rows = [[f"{row[0]} {row[1]}", *row[2:]] for row in table_rows]
            for cells, point in zip(pdf_rows, result["points"], strict=True):
                value = point["mean_dBm"]
                if value is not None:
                    cells[pdf_columns.index("dBm")] = format(D(value), ".2f")
            equipment = record["equipment"]
            lines += [
                f"Coverage: {result['completed_points']} of {result['requested_points']} points captured.",
            ]
            if equipment:
                lines.extend(
                    [
                        f"Meter / sensor: {equipment['meter_serial']} / {equipment['sensor_serial']}",
                        "Fixture: " + equipment["fixture"],
                    ]
                )
            pdf_notes = notes
        pdf._write(
            output,
            lines=lines,
            columns=pdf_columns,
            rows=pdf_rows,
            widths=widths,
            notes=pdf_notes,
            producer=producer,
            run_id=record["run_id"],
            physical=record["mode"] == "physical",
            source_label=description + " · operator-guided radio sweep",
            multipage=complete,
            plot=output / "frequency.png" if complete and "frequency.png" in images else None,
        )
        if complete:
            check_complete_pdf(
                (output / "report.pdf").read_bytes(),
                p._json((output / "metadata.json").read_bytes())["pdf"]["page_count"],
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
    parser.add_argument("--pdf", action=argparse.BooleanOptionalAction, default=None)
    args = parser.parse_args(argv)
    publish(args.bundle, args.output, plot=not args.no_plots, include_pdf=args.pdf)


if __name__ == "__main__":
    main()
