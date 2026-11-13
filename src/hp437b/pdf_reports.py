"""Optional one-page PDF sheets from validated workflow results, never HTML or devices."""

from decimal import Decimal as D
from importlib import metadata, resources
from io import BytesIO
from xml.sax.saxutils import escape

from . import provenance as p
from . import report_sheet
from . import reporting as r

FONT = "HPReportVera"
BOLD = "HPReportVeraBold"


def preflight():
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise ValueError(
            "Install the optional pdf extra: pip install 'hp437b-automation[pdf]'"
        ) from exc
    root = resources.files("reportlab") / "fonts"
    for name, filename in ((FONT, "Vera.ttf"), (BOLD, "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(root / filename)))
    return root


def _text(value):
    from reportlab.pdfbase import pdfmetrics

    text = str(value if value is not None else "Not recorded")
    supported = pdfmetrics.getFont(FONT).face.charToGlyph
    p.require(
        all(ord(char) in supported or char == "\n" for char in text),
        "PDF font cannot represent a supplied character; HTML/evidence remain available",
    )
    return escape(text).replace("\n", "<br/>")


def _number(value):
    if value is None:
        return "—"
    return "0" if D(str(value)) == 0 else report_sheet._n(value)


def _zero(result):
    value = result["zero_mean_W"]
    return _number(r.number(value) * 1000000) + " µW" if value is not None else "Not captured"


def _write(
    output,
    *,
    lines,
    columns,
    rows,
    widths,
    notes,
    producer,
    run_id,
    plot=None,
    suite=None,
    physical=False,
):
    root = preflight()
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    license_text = (root / "bitstream-vera-license.txt").read_text(encoding="utf-8")
    style = ParagraphStyle(
        "report",
        fontName=FONT,
        fontSize=8.7,
        leading=11.5,
        spaceAfter=4,
        textColor=colors.HexColor("#18242b"),
    )
    small = ParagraphStyle("small", parent=style, fontSize=7.5, leading=9.7)
    heading = ParagraphStyle(
        "title", parent=style, fontName=BOLD, fontSize=19, leading=23, spaceAfter=6
    )
    bold = ParagraphStyle("bold", parent=style, fontName=BOLD)
    cell = ParagraphStyle("cell", parent=small, spaceAfter=0)

    def paragraph(value, which=style):
        return Paragraph(_text(value), which)

    content = [
        paragraph("RF Output Power Test", heading),
        paragraph(
            "POWER REF - recorded measurement"
            if physical
            else "SYNTHETIC - fictional measurements; no physical RF",
            bold,
        ),
    ]
    content.extend(paragraph(line) for line in lines)
    content.append(Spacer(1, 8))
    grid = [[paragraph(value, bold) for value in columns]]
    grid += [[paragraph(value, cell) for value in row] for row in rows]
    widths = [width * 540 / sum(widths) for width in widths]
    table = Table(grid, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#a6b6c2")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#ccd3d8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    content.extend([table, Spacer(1, 9)])
    if plot is not None:
        from PIL import Image as PILImage

        plot_bytes = plot.read_bytes()
        p.require(len(plot_bytes) <= p.MAX_FILE, "PDF plot exceeds import budget")
        with PILImage.open(BytesIO(plot_bytes)) as image:
            width, height = image.size
            p.require(
                0 < width <= 10000 and 0 < height <= 10000, "Invalid generated PDF plot dimensions"
            )
        content.extend(
            [
                Image(
                    BytesIO(plot_bytes),
                    width=min(520, 120 * width / height),
                    height=min(120, 520 * height / width),
                ),
                Spacer(1, 7),
            ]
        )
    content.extend(paragraph(note, small) for note in notes)
    if suite is not None:
        links = "Details: " + " | ".join(
            f'<link href="workflows/{kind}/report.pdf" color="#135c91">{kind} PDF</link>'
            for kind in suite
        )
        content.append(
            Paragraph(
                links
                if suite
                else "Details: no workflow started; see the saved cancellation record.",
                small,
            )
        )
    else:
        content.append(
            Paragraph(
                'Details: <link href="appendix.html" color="#135c91">HTML appendix</link>; provenance.json; results.json.',
                small,
            )
        )
    pages = []

    def footer(canvas, doc):
        pages.append(doc.page)
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#a6b6c2"))
        canvas.line(36, 66, 576, 66)
        details = (
            "Equipment: See individual reports and provenance."
            if suite is not None
            else "Equipment: Meter, sensor, and fixture records in provenance.json."
        )
        foot = paragraph(
            details + "\n" + report_sheet.producer_note(producer) + "\nRecord: " + run_id, small
        )
        _, height = foot.wrap(540, 55)
        p.require(height <= 55, "PDF footer exceeds one-page layout")
        foot.drawOn(canvas, 36, 60 - height)
        canvas.restoreState()

    data = BytesIO()
    doc = SimpleDocTemplate(
        data,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=82,
        title="RF Output Power Test",
        author="HP 437B Automation",
        creator=report_sheet.producer_note(producer),
        subject="Embedded Bitstream Vera font notice:\n" + license_text,
    )

    def canvasmaker(*args, **kwargs):
        kwargs["invariant"] = 1
        return Canvas(*args, **kwargs)

    from reportlab.platypus.doctemplate import LayoutError

    try:
        doc.build(content, onFirstPage=footer, onLaterPages=footer, canvasmaker=canvasmaker)
    except LayoutError as exc:
        raise ValueError(
            "PDF content cannot fit the one-page layout; capture is preserved"
        ) from exc
    p.require(pages == [1], "PDF report exceeds one page; capture is preserved for re-reporting")
    p.require(not (output / "report.pdf").exists(), "PDF output exists")
    (output / "report.pdf").write_bytes(data.getvalue())
    (output / "font-license.txt").write_text(license_text, encoding="utf-8")
    meta_path = output / "metadata.json"
    meta = p._json(meta_path.read_bytes())
    meta["pdf"] = dict(
        schema="hp437b.pdf-output.v1",
        renderer="ReportLab",
        renderer_version=metadata.version("reportlab"),
        page_size="Letter",
        page_count=1,
        invariant=True,
        font_license="font-license.txt",
    )
    meta_path.write_bytes(r.encoded(meta))


def _criteria_notes(criteria):
    if criteria is None:
        return ["Acceptance limits not supplied."]
    labels = {
        "max_abs_error_percent": ("maximum absolute target error", "%"),
        "max_spread_dB": ("maximum spread", " dB"),
        "max_abs_change_percent": ("maximum absolute nominal-relative change", "%"),
        "max_abs_secant_W_per_V": ("maximum absolute endpoint sensitivity", " W/V"),
    }
    limits = [
        label + " " + _number(criteria[key]) + unit
        for key, (label, unit) in labels.items()
        if key in criteria
    ]
    overrides = criteria.get("point_limits_percent", {})
    if overrides:
        limits.append(
            "point overrides "
            + ", ".join(
                key + "=" + _number(value) + "%" for key, value in sorted(overrides.items())
            )
        )
    limits.extend(
        [
            "minimum " + str(criteria["min_samples_per_point"]) + " samples/point",
            "maximum receipt gap " + _number(criteria["max_gap_s"]) + " s",
        ]
    )
    return [
        "Criteria: " + criteria["source"],
        "; ".join(limits) + ". Inclusive limits; no guard band.",
    ]


def workflow(output, capture, result, producer, kind):
    from .test_suite import TITLES

    plan = capture["plan"]
    lines = [
        "Test: " + TITLES[kind],
        "Transmitter: " + plan["name"],
        "Operator: " + str(capture["operator"] or "Not recorded"),
        "When: " + r.timestamp(capture["started_utc"]).strftime("%d %b %Y, %H:%M:%S UTC"),
        "Measurement plane: " + result["measurement_plane"].replace("_", " "),
        f"Execution: {result['execution']}; {result['completed_points']}/{result['requested_points']} points complete. Acceptance: {result['acceptance']}",
        "Pre-RF zero: " + _zero(result) + "; signed source-off indication; no subtraction",
    ]
    identity = (
        p._json((output / "provenance.json").read_bytes())["dut"]["facts"]
        .get("profile_identity", {})
        .get("value")
    )
    if identity and (identity["model"] or identity["serial"] or identity["asset_id"]):
        lines.insert(
            2,
            "Supplied model / serial / asset: "
            + " / ".join(
                str(identity[key] or "Not recorded") for key in ("model", "serial", "asset_id")
            ),
        )
    condition = "Signal: " + plan["signal_mode"]
    if kind != "WF-05":
        condition += (
            "; declared frequency " + _number(D(str(plan["frequency_Hz"])) / 1000000) + " MHz"
        )
    if kind != "WF-04":
        condition += "; fixed setting " + plan["power_setting"]
    lines.insert(-2, condition)
    if kind == "WF-06":
        supply = plan["supply"]
        lines.insert(
            -2,
            "Supply profile: "
            + _number(supply["minimum_V"])
            + "–"
            + _number(supply["maximum_V"])
            + " V; current-limit setting "
            + _number(supply["current_limit_A"])
            + " A",
        )
    if kind == "WF-04":
        columns = ["Setting", "Target W", "Measured W", "Error %", "Valid / state"]
        widths = [148, 82, 82, 70, 158]
        rows = [
            [
                point["point_id"] + " · " + point["setting"],
                _number(point["target_W"]),
                _number(point["measured_W"]),
                _number(point["error_percent"]),
                f"{point['valid_samples']}/30; {point['status']}",
            ]
            for point in result["points"]
        ]
        plot = "power-setting.png"
    elif kind == "WF-05":
        columns = [
            "Point / MHz",
            "CF % / location",
            "Loss dB",
            "Target W",
            "Measured W",
            "Error %",
            "Valid / state",
        ]
        widths = [80, 78, 58, 66, 76, 58, 124]
        rows = [
            [
                point["point_id"] + " · " + _number(D(str(point["frequency_Hz"])) / 1000000),
                _number(point["sensor_factor_percent"]) + " / " + point["factor_applied_in"],
                _number(point["fixture_loss_dB"]),
                _number(point["target_W"]),
                _number(point["measured_W"]),
                _number(point["error_percent"]),
                f"{point['valid_samples']}/30; {point['status']}",
            ]
            for point in result["points"]
        ]
        lines.append(
            "Observed frequency-point spread: " + _number(result["observed_spread_dB"]) + " dB"
        )
        plot = "frequency-sweep.png"
    else:
        columns = ["Point", "Request V", "Observed V", "RF power W", "Change %", "Valid / state"]
        widths = [50, 76, 82, 88, 76, 168]
        rows = [
            [
                point["point_id"],
                _number(point["requested_V"]),
                _number(point["observed_V"]),
                _number(point["measured_W"]),
                _number(point["change_percent"]),
                f"{point['valid_samples']}/30; {point['status']}",
            ]
            for point in result["points"]
        ]
        lines.append(
            "Observed endpoint sensitivity: "
            + _number(result["secant_W_per_V"])
            + " W/V; nominal point: "
            + str(plan["supply"]["nominal_point_id"] or "Not recorded")
        )
        plot = "supply-sensitivity.png"
    final = capture["final_state"]
    state = capture.get("control_summary")
    lines.append(
        "Final controls: RF "
        + (
            state["rf_state"].upper()
            if state
            else "OFF acknowledged"
            if final["external_source_off"]
            else "UNKNOWN"
        )
        + (
            "; supply restoration " + ("VERIFIED" if state["supply_restored"] else "UNVERIFIED")
            if state
            else ""
        )
    )
    if kind == "WF-06" and state is None:
        lines.append("Supply restoration: " + capture["restoration"]["status"].upper())
    notes = [
        "Missing values are unavailable, not zero. Partial/failed points cannot establish complete coverage. Frequency/setting acknowledgements are not independent RF measurements.",
        "Supplied corrections are applied once at the declared plane; see results/provenance for factors, their sources, and acceptance criteria. No accuracy or uncertainty verdict is implied.",
    ] + _criteria_notes(capture["criteria"])
    path = output / plot
    _write(
        output,
        lines=lines,
        columns=columns,
        rows=rows,
        widths=widths,
        notes=notes,
        producer=producer,
        run_id=capture["run_id"],
        plot=path if path.is_file() else None,
    )


def suite(output, result, producer):
    from .test_suite import TITLES, format_observed, stop_description

    dut = result["dut"]
    lines = [
        "Test suite summary",
        "Transmitter: " + dut["name"],
        "Model / serial: "
        + str(dut["model"] or "Not recorded")
        + " / "
        + str(dut["serial"] or "Not recorded"),
        "Operator: " + str(result["operator"]["value"] or "Not recorded"),
        "When: " + r.timestamp(result["started_utc"]).strftime("%d %b %Y, %H:%M:%S UTC"),
        f"Profile: {result['profile_id']}, revision {result['profile_revision']}",
        f"Execution: {result['status']}; {result['completed_workflows']}/{len(result['selected'])} workflows complete. Acceptance: {result['acceptance']}",
        "Stop reason: " + stop_description(result),
    ]
    by_kind = {row["workflow"]: row for row in result["results"]}
    rows = []
    for kind in result["selected"]:
        row = by_kind.get(kind)
        rows.append(
            [
                kind + "\n" + TITLES[kind],
                row["execution"] if row else "skipped",
                format_observed(row) + "\n" + row["acceptance"]
                if row
                else "Not measured\nNOT EVALUATED",
                _zero(row) if row else "Not captured",
            ]
        )
    last = result["results"][-1] if result["results"] else None
    lines.append(
        "Final shared controls: "
        + (
            "RF "
            + last["rf_state"].upper()
            + "; supply restoration "
            + ("VERIFIED" if last["supply_restored"] else "UNVERIFIED")
            if last
            else "Not observed; no workflow started"
        )
    )
    notes = [
        "Zero values are signed source-off indications; no subtraction. Skipped tests have no measurements. Individual reports retain conditions, criteria, corrections, and detailed results.",
        "These are fake-control results, not physical transmitter performance or equipment acceptance. Missing criteria remain NOT EVALUATED.",
    ]
    _write(
        output,
        lines=lines,
        columns=["Test", "Execution", "Observed result / decision", "Pre-RF zero"],
        rows=rows,
        widths=[126, 64, 262, 88],
        notes=notes,
        producer=producer,
        run_id=result["suite_id"],
        suite=[row["workflow"] for row in result["results"]],
    )
