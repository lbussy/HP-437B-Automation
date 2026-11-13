"""Human-started, fake-only profile suites with immutable capture and offline reports."""

import argparse
import csv
import html
import signal
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

from . import controlled_sweep as s
from . import dut_simulation as f
from . import provenance as p
from . import report_identity, report_sheet
from . import reporting as r
from . import test_profiles as t
from .workflow_report import _seal, preflight

SCHEMA = "hp437b.test-suite.v1"
TITLES = {
    "WF-04": "Output versus setting",
    "WF-05": "Output versus frequency",
    "WF-06": "Supply-voltage sensitivity",
}


def selection(document, workflows):
    selected = list(t.KINDS if workflows is None else workflows)
    if workflows is None:
        selected = [kind for kind in selected if kind in document["workflows"]]
    p.require(
        1 <= len(selected) <= 3
        and len(set(selected)) == len(selected)
        and all(kind in document["workflows"] for kind in selected),
        "Select distinct workflows present in the profile",
    )
    return selected


def initial_state(document, selected):
    plan = document["workflows"][selected[0]]["plan"]
    control, _ = s.specification(selected[0], plan, plan["points"][0])
    supply = control["supply"]
    hardware = f.Hardware(
        False,
        1000000,
        "Initial state (synthetic)",
        supply["restore_V"],
        supply["restore_current_limit_A"],
    )
    previous = supply
    for kind in selected[1:]:
        plan = document["workflows"][kind]["plan"]
        current, _ = s.specification(kind, plan, plan["points"][0])
        current = current["supply"]
        p.require(
            abs(D(previous["restore_V"]) - D(current["restore_V"])) <= D(current["tolerance_V"])
            and D(previous["restore_current_limit_A"]) == D(current["restore_current_limit_A"]),
            "Adjacent workflow restoration conditions are incompatible",
        )
        previous = current
    return hardware


def observed_result(kind, result):
    values = [
        D(point["measured_W"])
        for point in result["points"]
        if point["status"] == "completed" and point["measured_W"] is not None
    ]
    return dict(
        measurement_plane=result["measurement_plane"],
        minimum_W=str(min(values)) if values else None,
        maximum_W=str(max(values)) if values else None,
        spread_dB=result["observed_spread_dB"] if kind == "WF-05" else None,
        secant_W_per_V=result["secant_W_per_V"] if kind == "WF-06" else None,
    )


def format_observed(row):
    measured = row["observed_result"]
    if measured["minimum_W"] is None:
        return "No completed RF point result"

    def number(value):
        return "0" if D(value) == 0 else report_sheet._n(value)

    low, high = D(measured["minimum_W"]), D(measured["maximum_W"])
    text = number(low) + ("–" + number(high) if high != low else "") + " W"
    text += " (" + measured["measurement_plane"].replace("_", " ") + ")"
    text += f"; {row['completed_points']}/{row['requested_points']} points"
    if measured["spread_dB"] is not None:
        text += "; spread " + number(measured["spread_dB"]) + " dB"
    if measured["secant_W_per_V"] is not None:
        text += "; endpoint " + number(measured["secant_W_per_V"]) + " W/V"
    return text


def summary(kind, cap, result, inventory_hash):
    return dict(
        workflow=kind,
        execution=cap["status"],
        acceptance=result["acceptance"],
        observed_result=observed_result(kind, result),
        completed_points=result["completed_points"],
        requested_points=result["requested_points"],
        zero_mean_W=result["zero_mean_W"],
        rf_state=cap["control_summary"]["rf_state"],
        supply_restored=cap["control_summary"]["supply_restored"],
        run_id=cap["run_id"],
        capture_inventory_sha256=inventory_hash,
    )


def aggregate(selected, rows, reason):
    completed = len(rows) == len(selected) and all(
        row["execution"] == "completed" and row["rf_state"] == "off" and row["supply_restored"]
        for row in rows
    )
    status = (
        "completed"
        if completed
        else "interrupted"
        if reason
        and (reason.startswith("cancelled:") or (rows and rows[-1]["execution"] == "interrupted"))
        else "failed"
    )
    acceptance = (
        "FAIL"
        if any(row["acceptance"] == "FAIL" for row in rows)
        else "PASS"
        if completed and all(row["acceptance"] == "PASS" for row in rows)
        else "NOT EVALUATED"
    )
    return dict(
        status=status,
        acceptance=acceptance,
        attempted_workflows=len(rows),
        completed_workflows=sum(row["execution"] == "completed" for row in rows),
        results=rows,
    )


def final_hardware(cap, bundle):
    p.require(bool(cap["children"]), "Suite workflow produced no native point evidence")
    return bundle.json(cap["children"][-1]["path"] + "/workflow.json")["final_hardware"]


def run(
    document,
    output,
    *,
    workflows=None,
    operator=None,
    report_output=None,
    plots=True,
    pdf=False,
    package=False,
    fault=None,
    fault_workflow=None,
    fault_point=None,
    stop_before=None,
    cancelled=None,
    progress=None,
):
    document = t.validate(document)
    selected = selection(document, workflows)
    binding = t.bind(document, selected[0], operator)
    hardware = initial_state(document, selected)
    p.require(
        stop_before is None or stop_before in selected, "Cancellation boundary is not selected"
    )
    p.require(
        (fault is None and fault_workflow is None and fault_point is None)
        or (fault in s.FAULTS and fault_workflow in selected),
        "Specify a valid fault and selected workflow together",
    )
    if fault is not None:
        p.require(
            fault != "factor-mismatch" or fault_workflow == "WF-05",
            "Factor mismatch requires WF-05",
        )
        ids = [
            point["point_id"] for point in document["workflows"][fault_workflow]["plan"]["points"]
        ]
        p.require(fault_point is None or fault_point in ids, "Fault point is not requested")
    pdf = pdf or package
    p.require(not pdf or report_output is not None, "PDF/package delivery requires report output")
    output = Path(output).resolve()
    p.require(not output.exists() and not p.sidecar_path(output).exists(), "Suite output exists")
    if report_output is not None:
        preflight(output, report_output, plots=plots)
        from .report_delivery import preflight_delivery

        preflight_delivery(output, report_output, pdf=pdf, package=package)
    epoch = datetime.now(UTC)
    record = dict(
        schema=SCHEMA,
        mode="synthetic",
        simulation=True,
        suite_id=str(uuid.uuid4()),
        selected=selected,
        profile_binding_sha256=r.digest(r.encoded(binding)),
        software=report_identity.identify(),
        started_utc=epoch.isoformat(),
        finished_utc=None,
        fault=fault,
        fault_workflow=fault_workflow,
        fault_point=fault_point,
        stop_before=stop_before,
        stop_reason=None,
        children=[],
        status="running",
        acceptance=None,
        attempted_workflows=0,
        completed_workflows=0,
        results=[],
    )
    output.mkdir(parents=True)
    (output / "captures").mkdir()
    (output / "test-profile.json").write_bytes(r.encoded(binding))
    (output / "starting.json").write_bytes(r.encoded(record))
    rows = []
    try:
        for index, kind in enumerate(selected, 1):
            if stop_before == kind or (cancelled is not None and cancelled()):
                record["stop_reason"] = "cancelled:" + kind
                break
            if progress is not None:
                progress(
                    dict(event="workflow_started", workflow=kind, index=index, total=len(selected))
                )
            entry = document["workflows"][kind]
            context = dict(
                schema="hp437b.suite-context.v1",
                suite_id=record["suite_id"],
                index=index,
                initial_hardware=hardware.snapshot(),
            )
            source = output / "captures" / kind
            s.run(
                kind,
                source,
                plan=entry["plan"],
                criteria=entry["criteria"],
                operator=binding["operator"]["value"],
                test_profile={**binding, "workflow_kind": kind},
                suite_context=context,
                hardware=hardware,
                epoch=epoch,
                fault=fault if kind == fault_workflow else None,
                fault_point=fault_point if kind == fault_workflow else None,
            )
            w = s.module(kind)
            cap, samples, bundle = w.load(source)
            result = w.analyze(cap, samples)
            row = summary(kind, cap, result, r.digest(bundle.read("artifacts.json")))
            rows.append(row)
            record["children"].append(
                dict(workflow=kind, path="captures/" + kind, run_id=cap["run_id"])
            )
            epoch = r.timestamp(cap["finished_utc"])
            if progress is not None:
                progress(
                    dict(
                        event="workflow_finished",
                        workflow=kind,
                        index=index,
                        total=len(selected),
                        result=row,
                    )
                )
            if (
                cap["status"] != "completed"
                or row["rf_state"] != "off"
                or not row["supply_restored"]
            ):
                record["stop_reason"] = "execution:" + kind
                break
            if result["acceptance"] == "FAIL":
                record["stop_reason"] = "criteria:" + kind
                break
        record.update(
            aggregate(selected, rows, record["stop_reason"]), finished_utc=epoch.isoformat()
        )
        (output / "suite.json").write_bytes(r.encoded(record))
        _seal(output, dict(schema=SCHEMA, mode="synthetic", run_id=record["suite_id"]))
        load(output)
    except BaseException as exc:
        (output / "artifacts.json").unlink(missing_ok=True)
        (output / "failure.json").write_bytes(
            r.encoded(
                dict(
                    status="unsealed",
                    error_type=type(exc).__name__,
                    completed_children=record["children"],
                )
            )
        )
        raise
    if report_output is not None:
        publish(output, report_output, plots=plots, pdf=pdf, package=package)
    return record


def load(source):
    bundle = p.Bundle(source)
    inv = bundle.inventory("artifacts.json", "synthetic")
    record = bundle.json("suite.json")
    keys = (
        "schema",
        "mode",
        "simulation",
        "suite_id",
        "selected",
        "profile_binding_sha256",
        "software",
        "started_utc",
        "finished_utc",
        "fault",
        "fault_workflow",
        "fault_point",
        "stop_before",
        "stop_reason",
        "children",
        "status",
        "acceptance",
        "attempted_workflows",
        "completed_workflows",
        "results",
    )
    p._keys(record, keys)
    p.require(
        record["schema"] == SCHEMA
        and record["mode"] == "synthetic"
        and record["simulation"] is True
        and inv.get("schema") == SCHEMA
        and inv.get("run_id") == record["suite_id"],
        "Suite identity/mode mismatch",
    )
    uuid.UUID(record["suite_id"])
    binding = bundle.json("test-profile.json")
    selected = selection(t.validate(binding["profile"]), record["selected"])
    t.validate_binding(binding, selected[0])
    p.require(
        record["profile_binding_sha256"] == r.digest(bundle.read("test-profile.json")),
        "Suite profile binding hash mismatch",
    )
    p.require(
        record["stop_before"] is None or record["stop_before"] in selected,
        "Invalid cancellation selector",
    )
    fault = record["fault"]
    p.require(
        (fault is None and record["fault_workflow"] is None and record["fault_point"] is None)
        or (
            fault in s.FAULTS
            and record["fault_workflow"] in selected
            and (fault != "factor-mismatch" or record["fault_workflow"] == "WF-05")
        ),
        "Invalid suite fault",
    )
    if fault:
        ids = [
            item["point_id"]
            for item in binding["profile"]["workflows"][record["fault_workflow"]]["plan"]["points"]
        ]
        p.require(
            record["fault_point"] is None or record["fault_point"] in ids, "Invalid fault point"
        )
    initial = {
        **record,
        "finished_utc": None,
        "stop_reason": None,
        "children": [],
        "status": "running",
        "acceptance": None,
        "attempted_workflows": 0,
        "completed_workflows": 0,
        "results": [],
    }
    p.require(bundle.json("starting.json") == initial, "Suite starting/final mismatch")
    p.require(
        isinstance(record["children"], list) and len(record["children"]) <= len(selected),
        "Invalid suite child count",
    )
    state = initial_state(binding["profile"], selected).snapshot()
    epoch = r.timestamp(record["started_utc"])
    rows, seen = [], set()
    session_ids = set()
    reason = None
    for index, child in enumerate(record["children"], 1):
        kind = selected[index - 1]
        p._keys(child, ("workflow", "path", "run_id"))
        p.require(
            reason is None
            and kind != record["stop_before"]
            and child["workflow"] == kind
            and child["path"] == "captures/" + kind,
            "Out-of-order, cancelled, or post-failure suite child",
        )
        cap, samples, native = s.module(kind).load(Path(source) / child["path"])
        expected_context = dict(
            schema="hp437b.suite-context.v1",
            suite_id=record["suite_id"],
            index=index,
            initial_hardware=state,
        )
        expected_binding = {**binding, "workflow_kind": kind}
        p.require(
            cap.get("suite_context") == expected_context
            and native.json("test-profile.json") == expected_binding
            and cap["run_id"] == child["run_id"]
            and cap["run_id"] not in seen
            and r.timestamp(cap["started_utc"]) == epoch,
            "Suite child profile/state/timeline/identity mismatch",
        )
        seen.add(cap["run_id"])
        for name in native.entries:
            if name.endswith(".csv.session.json"):
                session_id = native.json(name)["session_id"]
                p.require(session_id not in session_ids, "Repeated meter session across workflows")
                session_ids.add(session_id)
        active = fault if record["fault_workflow"] == kind else None
        p.require(
            cap["fault"] == (active or "nominal") and cap["stop_before"] is None,
            "Child fault differs from suite request",
        )
        if active:
            ids = [point["point_id"] for point in cap["plan"]["points"]]
            p.require(
                cap["fault_point"] == (record["fault_point"] or ids[min(1, len(ids) - 1)]),
                "Child fault point differs",
            )
        result = s.module(kind).analyze(cap, samples)
        rows.append(summary(kind, cap, result, r.digest(native.read("artifacts.json"))))
        state = final_hardware(cap, native)
        epoch = r.timestamp(cap["finished_utc"])
        if (
            cap["status"] != "completed"
            or rows[-1]["rf_state"] != "off"
            or not rows[-1]["supply_restored"]
        ):
            reason = "execution:" + kind
        elif result["acceptance"] == "FAIL":
            reason = "criteria:" + kind
    if reason is None and len(rows) < len(selected):
        reason = "cancelled:" + selected[len(rows)]
    p.require(
        record["stop_reason"] == reason
        and (record["stop_before"] is None or record["stop_before"] not in selected[: len(rows)])
        and r.timestamp(record["finished_utc"]) == epoch
        and 0 <= (epoch - r.timestamp(record["started_utc"])).total_seconds() <= 2700,
        "Suite stop/timeline mismatch",
    )
    derived = aggregate(selected, rows, reason)
    p.require(
        all(r.encoded(record[key]) == r.encoded(value) for key, value in derived.items()),
        "Suite results differ from native evidence",
    )
    known = {"captures/" + item["workflow"] + "/" for item in record["children"]}
    p.require(
        all(
            not path.startswith("captures/") or any(path.startswith(prefix) for prefix in known)
            for path in bundle.entries
        ),
        "Hidden/unrequested suite child evidence",
    )
    return record, binding, bundle


def publish(source, output, *, plots=True, pdf=False, package=False):
    from . import pdf_reports, report_delivery

    pdf = pdf or package
    source, output = preflight(source, output, plots=plots)
    report_delivery.preflight_delivery(source, output, pdf=pdf, package=package)
    record, binding, bundle = load(source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    output.mkdir(parents=True)
    try:
        for item in record["children"]:
            s.module(item["workflow"]).publish(
                source / item["path"], output / "workflows" / item["workflow"], plots=plots, pdf=pdf
            )
        profile = binding["profile"]
        results = {
            **record,
            "profile_id": profile["profile_id"],
            "profile_revision": profile["revision"],
            "dut": profile["dut"],
            "operator": binding["operator"],
            "source_inventory_sha256": source_hash,
        }
        (output / "results.json").write_bytes(r.encoded(results))
        producer = report_identity.identify()
        (output / "metadata.json").write_bytes(
            r.encoded(
                dict(
                    producer=producer,
                    suite_id=record["suite_id"],
                    source_inventory_sha256=source_hash,
                )
            )
        )
        _render(output, results, producer)
        if pdf:
            pdf_reports.suite(output, results, producer)
        load(source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_hash,
            "Suite changed during report publication",
        )
        _seal(
            output,
            dict(schema="hp437b.test-suite-report.v1", mode="synthetic", run_id=record["suite_id"]),
        )
        if package:
            report_delivery.package(source, output)
        return results
    except BaseException as exc:
        if (output / "artifacts.json").exists():
            raise
        (output / "artifacts.json").unlink(missing_ok=True)
        (output / "failure.json").write_bytes(
            r.encoded(dict(status="unsealed", error_type=type(exc).__name__))
        )
        raise


def stop_description(result):
    reason = result["stop_reason"]
    if reason:
        category, kind = reason.split(":")
        reason = {
            "cancelled": f"Cancelled before {kind}",
            "criteria": f"{kind} did not meet supplied acceptance criteria",
            "execution": f"{kind} did not complete; see individual report",
        }[category]
    else:
        reason = "None"
    return reason


def _render(output, result, producer):
    def e(value):
        return html.escape(str(value if value is not None else "Not recorded"))

    by_kind = {row["workflow"]: row for row in result["results"]}
    table, markdown = [], []
    for kind in result["selected"]:
        row = by_kind.get(kind)
        execution = row["execution"] if row else "skipped"
        verdict = row["acceptance"] if row else "Not evaluated"
        observed = format_observed(row) if row else "Not measured"
        zero = (
            f"{D(row['zero_mean_W']) * 1000000:.4g} µW"
            if row and row["zero_mean_W"] is not None
            else "Not captured"
        )
        link = f'<a href="workflows/{kind}/report.html">Open report</a>' if row else "—"
        table.append(
            f"<tr><td>{e(kind)}<br>{e(TITLES[kind])}</td><td>{e(execution)}</td><td>{e(observed)}<br><strong>{e(verdict)}</strong></td><td>{e(zero)}</td><td>{link}</td></tr>"
        )
        markdown.append(
            f"| {kind} | {execution} | {observed}; {verdict} | {zero} | "
            + (f"[Report](workflows/{kind}/report.html)" if row else "—")
            + " |"
        )
    harness = report_sheet.producer_note(producer)
    when = r.timestamp(result["started_utc"]).strftime("%d %b %Y, %H:%M:%S UTC")
    reason = stop_description(result)
    last = result["results"][-1] if result["results"] else None
    final = (
        f"RF {last['rf_state'].upper()}; supply restoration {'VERIFIED' if last['supply_restored'] else 'UNVERIFIED'}"
        if last
        else "Not observed; no workflow started"
    )
    dut = result["dut"]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>RF Output Power Test</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>
@page{{size:Letter;margin:.6in}}body{{font:14px/1.4 system-ui,sans-serif;color:#18242b;max-width:1000px;margin:32px auto;padding:0 16px}}h1{{font-size:26px;margin-bottom:4px}}h2{{font-size:18px}}table{{border-collapse:collapse;width:100%;margin:24px 0}}td,th{{padding:10px 6px;border-bottom:1px solid #ccd3d8;text-align:left}}footer{{border-top:1px solid #9baab4;margin-top:28px;padding-top:12px;font-size:11px}}a{{color:#135c91}}@media print{{body{{margin:0;padding:0;font-size:11px}}h1{{font-size:23px}}table{{margin:16px 0}}a{{color:inherit}}}}
</style></head><body><main><h1>RF Output Power Test</h1><strong>SYNTHETIC — fictional measurements; no physical RF</strong><h2>Test suite summary</h2>
<p><strong>Transmitter:</strong> {e(dut["name"])}<br><strong>Model / serial:</strong> {e(dut["model"])} / {e(dut["serial"])}<br><strong>Operator:</strong> {e(result["operator"]["value"])}<br><strong>When:</strong> {e(when)}<br><strong>Profile:</strong> {e(result["profile_id"])}, revision {e(result["profile_revision"])}</p>
<p><strong>Execution:</strong> {e(result["status"])}; {result["completed_workflows"]}/{len(result["selected"])} workflows complete. <strong>Acceptance:</strong> {e(result["acceptance"])}.<br><strong>Stop reason:</strong> {e(reason)}<br><strong>Final shared controls:</strong> {e(final)}.</p>
<table><thead><tr><th>Test</th><th>Execution</th><th>Observed result / decision</th><th>Pre-RF zero</th><th>Details</th></tr></thead><tbody>{"".join(table)}</tbody></table>
<p>Zero values are signed source-off indications; no subtraction. Individual reports retain point results, supplied criteria, corrections, and control limitations. Skipped tests have no measurements.</p><p>These are fake-control workflow results, not transmitter performance or physical equipment acceptance. Missing criteria remain NOT EVALUATED. Shared-state and native evidence: results.json and the saved capture bundle.</p>
<footer>Equipment: See individual reports and provenance.<br>{e(harness)}<br>Record: {e(result["suite_id"])}</footer></main></body></html>"""
    (output / "report.html").write_text(page, encoding="utf-8")

    def md(value):
        return report_sheet._markdown(value if value is not None else "Not recorded")

    (output / "report.md").write_text(
        f"# RF Output Power Test\n\nSYNTHETIC — test suite summary; no physical RF.\n\nTransmitter: {md(dut['name'])}. Model / serial: {md(dut['model'])} / {md(dut['serial'])}.\n\nOperator: {md(result['operator']['value'])}. When: {md(when)}.\n\nProfile: {md(result['profile_id'])}, revision {result['profile_revision']}.\n\nExecution: {result['status']}; {result['completed_workflows']}/{len(result['selected'])} workflows complete. Acceptance: {result['acceptance']}.\n\nStop reason: {md(reason)}. Final shared controls: {final}.\n\n| Test | Execution | Result | Pre-RF zero | Details |\n| --- | --- | --- | --- | --- |\n"
        + "\n".join(markdown)
        + f"\n\nSigned source-off zero; no subtraction. Individual reports retain conditions, criteria, provenance, and limitations. Skipped tests have no measurements.\n\nEquipment: See individual reports.\n\n{md(harness)}\n\nRecord: {result['suite_id']}\n",
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("run")
    capture.add_argument("--profile", required=True, type=Path)
    capture.add_argument("--workflows", nargs="+", choices=t.KINDS)
    capture.add_argument("--operator")
    capture.add_argument("--report-output", type=Path)
    capture.add_argument("--fault", choices=s.FAULTS)
    capture.add_argument("--fault-workflow", choices=t.KINDS)
    capture.add_argument("--fault-point")
    capture.add_argument("--stop-before", choices=t.KINDS)
    report = commands.add_parser("report")
    report.add_argument("--bundle", required=True, type=Path)
    for sub in (capture, report):
        sub.add_argument("--output", required=True, type=Path)
        sub.add_argument("--no-plots", action="store_true")
        sub.add_argument("--pdf", action="store_true")
        sub.add_argument("--package", action="store_true")
    args = parser.parse_args(argv)
    previous = None
    try:
        if args.command == "report":
            publish(
                args.bundle,
                args.output,
                plots=not args.no_plots,
                pdf=args.pdf,
                package=args.package,
            )
            if args.pdf or args.package:
                from .report_delivery import announce

                announce(args.output, pdf=args.pdf, package=args.package)
            return 0
        requested = False

        def cancel(signum, frame):
            nonlocal requested
            requested = True

        previous = signal.signal(signal.SIGINT, cancel)
        record = run(
            t.load(args.profile),
            args.output,
            workflows=args.workflows,
            operator=args.operator,
            report_output=args.report_output,
            plots=not args.no_plots,
            pdf=args.pdf,
            package=args.package,
            fault=args.fault,
            fault_workflow=args.fault_workflow,
            fault_point=args.fault_point,
            stop_before=args.stop_before,
            cancelled=lambda: requested,
        )
        if args.pdf or args.package:
            from .report_delivery import announce

            announce(args.report_output, pdf=args.pdf, package=args.package)
        return (
            130
            if record["status"] == "interrupted"
            else 1
            if record["status"] != "completed" or record["acceptance"] == "FAIL"
            else 0
        )
    except (OSError, ValueError, KeyError, TypeError, csv.Error) as exc:
        print(f"Test suite: {exc}", file=sys.stderr)
        return 2
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)


if __name__ == "__main__":
    raise SystemExit(main())
