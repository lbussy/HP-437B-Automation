"""Human-started reference suites; native child evidence and shutdown remain authoritative."""

import fcntl
import html
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path

from . import operator_reference as ref
from . import pdf_reports as pdf
from . import provenance as p
from . import reference_report as reports
from . import report_context, report_identity, report_sheet
from . import reporting as r
from .logger import _atomic_json
from .workflow_report import _seal, preflight

SCHEMA = "hp437b.reference-suite.v1"
REPORT_SCHEMA = "hp437b.reference-suite-report.v1"
KINDS = tuple(ref.SCRIPTS)


def selection(kinds):
    p.require(
        isinstance(kinds, list)
        and bool(kinds)
        and all(isinstance(k, str) and k in KINDS for k in kinds)
        and kinds == [k for k in KINDS if k in kinds],
        "Select distinct POWER REF workflows in WF-01–WF-03 order",
    )
    return list(kinds)


def native(source, kind):
    return reports.load(source, kind, allow_synthetic=True)


def safe_to_advance(record, source):
    state = record["final_state"]
    if record["mode"] == "synthetic":
        return state["source"] == "off" and state["local"] == "true"
    free_run = record.get("free_run_check", {}).get("passed") is True
    if record.get("workflow_id") == "power-reference-v1":
        events = p._json((Path(source) / "trace.json").read_bytes())["events"]
        free_run = any(
            e.get("operation") == "free_run_display"
            and e.get("standby") is False
            and any(c.isdigit() for c in e.get("text", ""))
            and "TRIGGER" not in e.get("text", "").upper()
            for e in events
        )
    return state["source"] == "off" and "GTL accepted" in state["local"] and free_run


def fake_capture(output, kind, *, operator=None):
    """Explicit virtual-time generators; no resource, factory, or backend argument."""
    if kind == "WF-01":
        root = Path(__file__).resolve().parents[2]
        return run_path(str(root / "tools/exercise_workflow.py"))["run"](output, operator=operator)
    from . import repeatability_simulation, stability_simulation

    return (stability_simulation if kind == "WF-02" else repeatability_simulation).run(
        output, operator=operator
    )


def child_result(source, kind):
    record, result, _ = native(source, kind)
    values = reports.summary(record, result, kind)
    return dict(
        workflow=kind,
        run_id=record["run_id"],
        execution=record["status"],
        acceptance="NOT EVALUATED",
        safe_to_advance=safe_to_advance(record, source),
        final_state=record["final_state"],
        rows=values["rows"],
        capture_inventory_sha256=r.digest((Path(source) / "artifacts.json").read_bytes()),
    )


def run(path, request, emit, *, lock_fd=None, capture=None):
    """Stop progression on cancellation, failure, uncertain closure, or storage error."""
    path = Path(path).resolve()
    kinds = selection(request["workflows"])
    mode = request["meter_mode"]
    p.require(mode in ("synthetic", "physical"), "Invalid reference suite source")
    report_context.validate_operator(request["operator"])
    if mode == "physical":
        p.require(request["reference_config"] is not None, "Bench reference configuration missing")
        p.require(
            all(request["prepared_setup"].get(k) is True for k in ref.PREPARED),
            "Fresh suite preparation missing",
        )
    else:
        p.require(
            request["reference_config"] is None and request["prepared_setup"] is None,
            "Simulated suite cannot contain bench configuration",
        )
    source = path / "capture"
    source.mkdir()
    (source / "captures").mkdir()
    record = dict(
        schema=SCHEMA,
        run_id=str(uuid.uuid4()),
        mode=mode,
        resource=request["reference_config"]["resource"] if mode == "physical" else None,
        workflows=kinds,
        operator=request["operator"],
        setup=request["prepared_setup"],
        software=report_identity.identify(),
        started_utc=datetime.now(UTC).isoformat(),
        status="running",
        children=[],
        stop_reason=None,
        final_state=dict(
            source="off" if mode == "synthetic" else "not observed",
            local="not observed",
            front_panel_confirmation="not applicable" if mode == "synthetic" else "pending",
        ),
    )
    checkpoint = source / "reference-suite.json"

    def save():
        _atomic_json(checkpoint, record)

    save()
    # Inherited by native children: a dead UI worker cannot imply hardware closure.
    with (path / ".capture.lock").open("a+b") as guard:
        fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
        target = None
        kind = None
        try:
            for index, kind in enumerate(kinds):
                if (path / "cancel.requested").exists():
                    record.update(
                        status="interrupted", stop_reason="Cancelled before the next workflow"
                    )
                    break
                emit(
                    phase="running",
                    current=kind,
                    index=index,
                    total=len(kinds),
                    results=list(record["children"]),
                )
                target = source / "captures" / kind
                if capture is not None:
                    capture(target, kind)
                elif mode == "synthetic":
                    fake_capture(target, kind, operator=request["operator"])
                else:
                    step = path / "steps" / kind
                    step.mkdir(parents=True)
                    (step / "cancel.requested").symlink_to(path / "cancel.requested")
                    child = {**request, "workflows": [kind]}
                    child["prepared_setup"] = {
                        **request["prepared_setup"],
                        "confirmation_origin": (
                            "Suite-start operator confirmation retained; prior child source-off/local closure verified before progression"
                            if index
                            else "Suite-start fresh operator confirmation; first native workflow verifies initial reference-off"
                        ),
                    }
                    _atomic_json(step / "request.json", child)
                    ref.supervise(step, child, lock_fd=lock_fd, extra_fds=(guard.fileno(),))
                    shutil.copytree(step / "capture", target)
                sidecar = p.sidecar_path(target)
                if sidecar.exists():
                    retained = path / "native-provenance"
                    retained.mkdir(exist_ok=True)
                    sidecar.rename(retained / kind)
                item = child_result(target, kind)
                p.require(native(target, kind)[0]["mode"] == mode, "Child mode differs from suite")
                record["children"].append(item)
                record["final_state"] = item["final_state"]
                save()
                emit(results=list(record["children"]), index=index + 1, current=None)
                if item["execution"] != "completed" or not item["safe_to_advance"]:
                    record.update(
                        status="interrupted" if item["execution"] == "interrupted" else "failed",
                        stop_reason="Child incomplete or source/local closure unverified; later workflows not started",
                    )
                    break
            else:
                record["status"] = "completed"
        except BaseException as exc:
            if (
                target is not None
                and target.exists()
                and not any(x["workflow"] == kind for x in record["children"])
            ):
                retained = path / "unfinished"
                retained.mkdir(exist_ok=True)
                target.rename(retained / kind)
            record.update(
                status="interrupted" if isinstance(exc, KeyboardInterrupt) else "failed",
                stop_reason=f"{type(exc).__name__}: {exc}"[:500],
            )
            # A child that did not seal is retained operationally, not represented as valid evidence.
            record["final_state"] = dict(
                source="unknown",
                local="unknown",
                front_panel_confirmation="pending" if mode == "physical" else "not applicable",
            )
            if not isinstance(exc, (Exception, KeyboardInterrupt)):
                raise
        finally:
            record["finished_utc"] = datetime.now(UTC).isoformat()
            save()
            _seal(source, dict(schema=SCHEMA, mode=mode, run_id=record["run_id"]))
    values = load(source)[1]
    emit(
        phase="reporting",
        current=None,
        outcome=record["status"],
        final_state=record["final_state"],
        results=record["children"],
        acceptance="NOT EVALUATED",
        stop_reason=record["stop_reason"],
    )
    publish(source, path / "report", plots=request["plots"])
    emit(phase="finished", error=None)
    return values


def load(source):
    bundle = p.Bundle(source)
    inv = p._json(bundle.read("artifacts.json"))
    p.require(
        inv.get("schema") == SCHEMA and inv.get("mode") in ("synthetic", "physical"),
        "Invalid reference suite inventory",
    )
    bundle.inventory("artifacts.json", inv["mode"])
    record = bundle.json("reference-suite.json")
    p._keys(
        record,
        (
            "schema",
            "run_id",
            "mode",
            "resource",
            "workflows",
            "operator",
            "setup",
            "software",
            "started_utc",
            "finished_utc",
            "status",
            "children",
            "stop_reason",
            "final_state",
        ),
    )
    p.require(
        record["schema"] == SCHEMA
        and record["run_id"] == inv["run_id"]
        and record["mode"] == inv["mode"],
        "Suite identity mismatch",
    )
    p.require(
        not any(path.is_symlink() for path in Path(source).rglob("*")),
        "Symlink suite evidence is unsupported",
    )
    if record["mode"] == "physical":
        p.require(
            isinstance(record["setup"], dict)
            and all(record["setup"].get(k) is True for k in ref.PREPARED)
            and isinstance(record["resource"], str),
            "Physical suite preparation/resource missing",
        )
    else:
        p.require(
            record["setup"] is None and record["resource"] is None,
            "Simulated suite contains physical setup",
        )
    kinds = selection(record["workflows"])
    p.require(record["status"] in ("completed", "failed", "interrupted"), "Unfinished suite")
    report_context.validate_operator(record["operator"])
    p.require(
        isinstance(record["children"], list) and len(record["children"]) <= len(kinds),
        "Invalid child count",
    )
    seen = set()
    for i, item in enumerate(record["children"]):
        kind = kinds[i]
        target = Path(source) / "captures" / kind
        p.require(
            item == child_result(target, kind) and item["workflow"] == kind,
            "Child summary/hash differs from native evidence",
        )
        child = native(target, kind)[0]
        p.require(
            child["mode"] == record["mode"] and item["run_id"] not in seen,
            "Child mode/identity mismatch",
        )
        seen.add(item["run_id"])
        if record["mode"] == "physical":
            p.require(
                child["resource"] == record["resource"]
                and record["setup"] is not None
                and all(
                    child["setup"].get(k) == record["setup"].get(k)
                    for k in ("meter_serial", "sensor_serial")
                ),
                "Child equipment differs from suite",
            )
        p.require(
            i == len(record["children"]) - 1
            or (item["execution"] == "completed" and item["safe_to_advance"]),
            "Suite continued after a stopped child",
        )
    captured = set((Path(source) / "captures").iterdir())
    p.require(
        captured == {Path(source) / "captures" / x["workflow"] for x in record["children"]},
        "Unbound child capture",
    )
    expected_final = (
        record["children"][-1]["final_state"]
        if record["children"]
        else dict(
            source="off" if record["mode"] == "synthetic" else "not observed",
            local="not observed",
            front_panel_confirmation="not applicable"
            if record["mode"] == "synthetic"
            else "pending",
        )
    )
    p.require(
        record["final_state"] == expected_final
        or (
            record["status"] != "completed"
            and record["final_state"].get("source") == "unknown"
            and record["final_state"].get("local") == "unknown"
        ),
        "Suite final state differs from closure evidence",
    )
    p.require(
        (record["stop_reason"] is None)
        if record["status"] == "completed"
        else (isinstance(record["stop_reason"], str) and bool(record["stop_reason"])),
        "Suite stop reason/status mismatch",
    )
    if record["status"] == "completed":
        p.require(
            len(record["children"]) == len(kinds)
            and all(
                x["execution"] == "completed" and x["safe_to_advance"] for x in record["children"]
            ),
            "Incomplete suite cannot complete",
        )
        p.require(
            record["final_state"] == record["children"][-1]["final_state"], "Final state mismatch"
        )
    return (
        record,
        dict(
            schema=SCHEMA,
            run_id=record["run_id"],
            mode=record["mode"],
            execution=record["status"],
            acceptance="NOT EVALUATED",
            requested_workflows=kinds,
            children=record["children"],
            final_state=record["final_state"],
            stop_reason=record["stop_reason"],
        ),
        bundle,
    )


def report_values(record, result, source_hash):
    return {**result, "operator": record["operator"], "source_inventory_sha256": source_hash}


def validate_pair(source, output):
    record, result, source_bundle = load(source)
    bundle = p.Bundle(output)
    bundle.inventory("artifacts.json", record["mode"])
    p.require(
        bundle.json("results.json")
        == report_values(record, result, r.digest(source_bundle.read("artifacts.json"))),
        "Suite report differs from evidence",
    )
    p.require(
        bundle.json("provenance.json")
        == dict(
            run_id=record["run_id"],
            mode=record["mode"],
            setup=record["setup"],
            resource=record["resource"],
            software=record["software"],
            operator=record["operator"],
            children=record["children"],
        ),
        "Suite provenance differs from evidence",
    )
    for item in record["children"]:
        reports.validate_pair(
            Path(source) / "captures" / item["workflow"],
            Path(output) / "workflows" / item["workflow"],
        )
    return record["run_id"]


def publish(source, output, *, plots=True, package=True):
    from . import report_delivery as delivery

    source, output = preflight(source, output, plots=plots)
    delivery.preflight_delivery(source, output, pdf=True, package=package)
    record, result, bundle = load(source)
    source_hash = r.digest(bundle.read("artifacts.json"))
    values = report_values(record, result, source_hash)
    output.mkdir()
    (output / "workflows").mkdir()
    for item in record["children"]:
        reports.publish(
            source / "captures" / item["workflow"],
            output / "workflows" / item["workflow"],
            item["workflow"],
            plots=plots,
            operator=record["operator"],
            package=False,
            allow_synthetic=True,
        )
    producer = report_identity.identify()
    meta = dict(
        schema=REPORT_SCHEMA,
        run_id=record["run_id"],
        mode=record["mode"],
        source_inventory_sha256=source_hash,
        report_producer=producer,
    )
    (output / "metadata.json").write_bytes(r.encoded(meta))
    (output / "results.json").write_bytes(r.encoded(values))
    (output / "provenance.json").write_bytes(
        r.encoded(
            dict(
                run_id=record["run_id"],
                mode=record["mode"],
                setup=record["setup"],
                resource=record["resource"],
                software=record["software"],
                operator=record["operator"],
                children=record["children"],
            )
        )
    )
    rows = []
    for kind in record["workflows"]:
        item = next((x for x in record["children"] if x["workflow"] == kind), None)
        if item:
            data = dict(item["rows"])
            if kind == "WF-01":
                detail = data.get("Valid plateau readings", "0") + " readings"
            elif kind == "WF-02":
                detail = "Endpoint change: " + data.get("Endpoint change", "Not captured")
            else:
                detail = (
                    "Cycle spread: "
                    + data.get("Cycle-mean spread", "Not captured")
                    + "; "
                    + data.get("Completed cycles", "0")
                    + " cycles"
                )
            rows.append(
                [
                    kind + " · " + reports.TITLES[kind],
                    data["Pre-RF zero (signed)"],
                    data.get("Average RF power", "Not captured"),
                    item["execution"] + "; " + detail,
                ]
            )
        else:
            rows.append([kind + " · " + reports.TITLES[kind], "Not run", "Not captured", "Skipped"])
    lines = [
        "Test: POWER REF suite",
        "Source: Internal reference; direct sensor input"
        + (" (simulated)" if record["mode"] == "synthetic" else ""),
        "Operator: " + (record["operator"] or "Not recorded"),
        "When: " + record["started_utc"],
        f"Execution: {record['status']}; {len([x for x in record['children'] if x['execution'] == 'completed'])}/{len(record['workflows'])} workflows complete; acceptance: NOT EVALUATED",
    ]
    notes = [
        "Zero is the signed pre-RF baseline for each workflow; no subtraction or remote zero/CAL.",
        "Each completed child verified reference off and local shutdown before progression.",
        "No transmitter, absolute-accuracy, or compliance verdict.",
        "Final front-panel confirmation remains separate."
        if record["mode"] == "physical"
        else "Simulated cleanup only; no physical front-panel confirmation applies.",
    ]
    if record["stop_reason"]:
        notes.append("Stop reason: " + record["stop_reason"])
    if record["mode"] == "physical":
        notes.append(
            "Known equipment issues: " + "; ".join(record["setup"].get("known_issues", []))
        )
    esc = lambda x: html.escape(str(x))  # noqa: E731
    links = "".join(
        f"<p><a href='workflows/{x['workflow']}/report.pdf'>{x['workflow']} PDF</a> · <a href='workflows/{x['workflow']}/report.html'>Full detail</a></p>"
        for x in record["children"]
    )
    page = (
        "<!doctype html><html lang='en'><meta charset='utf-8'><title>RF Output Power Test</title><style>body{font:16px system-ui;color:#18242b;max-width:900px;margin:32px auto;padding:24px}td,th{text-align:left;padding:12px;border-bottom:1px solid #cbd6dc}a{color:#135c91}</style><h1>RF Output Power Test</h1>"
        + (
            "<p>SYNTHETIC — fictional reference suite; no hardware</p>"
            if record["mode"] == "synthetic"
            else "<p>POWER REF suite — recorded measurements</p>"
        )
        + "".join("<p>" + esc(x) + "</p>" for x in lines)
        + "<table><tr><th>Workflow</th><th>Pre-RF zero</th><th>Mean</th><th>Result</th></tr>"
        + "".join(
            "<tr>" + "".join("<td>" + esc(x) + "</td>" for x in row) + "</tr>" for row in rows
        )
        + "</table>"
        + "".join("<p>" + esc(x) + "</p>" for x in notes)
        + links
        + "<footer>Equipment: see provenance.json<br>"
        + esc(report_sheet.producer_note(producer))
        + "<br>Record: "
        + esc(record["run_id"])
        + "</footer></html>"
    )
    (output / "report.html").write_text(page)
    (output / "appendix.html").write_text(page)
    pdf._write(
        output,
        lines=lines,
        columns=["Workflow", "Pre-RF zero", "Mean", "Execution / result"],
        rows=rows,
        widths=[2, 1, 1, 1.5],
        notes=notes,
        producer=producer,
        run_id=record["run_id"],
        physical=record["mode"] == "physical",
    )
    meta = p._json((output / "metadata.json").read_bytes())
    _seal(output, meta)
    p.require(
        r.digest((source / "artifacts.json").read_bytes()) == source_hash,
        "Suite capture changed during reporting",
    )
    if package:
        delivery.package(source, output)
    return values


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Report a sealed reference suite without acquisition"
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    publish(args.bundle, args.output, plots=not args.no_plots)
    print(args.output / "report.pdf")


if __name__ == "__main__":
    main()
