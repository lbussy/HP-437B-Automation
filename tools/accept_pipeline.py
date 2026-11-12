"""Guarded, offline WF-01 → PROV-01 → analysis → REPORT-01 acceptance.

Fresh runs use only the explicit synthetic workflow. Optional retained inputs
are read-only and explicitly named; source-provided code is never executed.
Scripted findings test the analysis interface, not model reasoning.
"""

import argparse
import csv
import hashlib
import io
import os
import re
import sys
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from html.parser import HTMLParser
from pathlib import Path
from runpy import run_path

from hp437b import provenance as p
from hp437b import reporting as r

# Independent scenario oracles: execution, total valid/nonvalid, S40 valid, source.
ORACLES = {
    "nominal": ("completed", 309, 0, 300, "off"),
    "slow": ("completed", 129, 0, 120, "off"),
    "malformed": ("failed", 8, 1, 2, "unknown"),
    "timeout": ("failed", 8, 1, 2, "unknown"),
    "cancel": ("interrupted", 8, 0, 2, "off"),
    "instrument-error": ("failed", 8, 1, 2, "off"),
    "source-off-failure": ("failed", 306, 0, 300, "unknown"),
}


def guarded():
    p.require(os.environ.get("HP437B_OFFLINE_GUARD") == "active", "Use tools/offline_qa.py")
    p.require(__debug__, "Acceptance requires assertions enabled in the synthetic workflow")


def read_json(path):
    path = Path(path)
    return p._json(p.Bundle(path.parent).read(path.name))


def snapshot(root):
    """Bounded full-tree hash audit, including files outside a bundle inventory."""
    bundle = p.Bundle(root)
    for path in sorted(bundle.root.rglob("*")):
        p.require(not path.is_symlink(), "Symlink inputs are unsupported")
        if path.is_file():
            bundle.read(path.relative_to(bundle.root).as_posix())
    return {
        name: {"sha256": item["sha256"], "bytes": item["bytes"]}
        for name, item in bundle.entries.items()
    }


def seal(output, metadata):
    files = snapshot(output)
    temporary = output / ".inventory.tmp"
    with temporary.open("xb") as handle:
        handle.write(r.encoded({**metadata, "artifacts": files}))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output / "artifacts.json")


def fixture_analysis(packet):
    return {
        "schema": r.AGENT_SCHEMA,
        "packet_sha256": r.digest(r.encoded(packet)),
        "run_id": packet["run_id"],
        "author": "Scripted acceptance fixture; not an agent inference",
        "created_utc": datetime.now(UTC).isoformat(),
        "model": None,
        "findings": [
            {
                "kind": "limitation",
                "text": "Scripted interface fixture: measurement criteria are not evaluated; narrative reasoning is not tested by this fixture.",
                "refs": ["scope/0", "workflow/status"],
            }
        ],
    }


class LocalAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        p.require(tag not in ("script", "iframe", "object", "embed"), "Executable report element")
        for key, value in attrs:
            p.require(not key.startswith("on"), "Executable report attribute")
            if key in ("src", "href"):
                p._relative(value)
                self.assets.append(value)


def verify_report(source, provenance, output, *, plots):
    """Check the complete evidence graph and an independent CSV mean/count oracle."""
    source, provenance, output = Path(source), Path(provenance), Path(output)
    record = p.load(provenance)
    p.verify(record, source)
    manifest = read_json(output / "artifacts.json")
    p.require(manifest.get("schema") == "hp437b.report-export.v1", "Report schema mismatch")
    mode, run_id = record["run"]["mode"], record["run"]["run_id"]
    p.require(
        manifest["mode"] == mode and manifest["run_id"] == run_id and manifest["plots"] is plots,
        "Report mode/run/plots mismatch",
    )
    checked = p.Bundle(output)
    checked.inventory("artifacts.json", mode)
    required = {
        "results.json",
        "provenance.json",
        "analysis-packet.json",
        "agent-prompt.txt",
        "agent-analysis.json",
        "report.md",
        "report.html",
        "evidence.md",
        "evidence.html",
    }
    if plots:
        required |= {"power.png", "power.svg", "power-trend.png"}
    p.require(set(manifest["artifacts"]) == required, "Missing/unexpected report artifacts")
    p.require(set(snapshot(output)) == required | {"artifacts.json"}, "Uninventoried report files")
    result, packet = checked.json("results.json"), checked.json("analysis-packet.json")
    p.require(checked.json("provenance.json") == record, "Report provenance changed")
    p.require(
        packet["input_provenance_sha256"] == r.digest(provenance.read_bytes()),
        "Original provenance hash mismatch",
    )
    p.require(
        packet["provenance_sha256"] == r.digest((output / "provenance.json").read_bytes()),
        "Normalized provenance hash mismatch",
    )
    p.require(
        packet["run_id"] == result["run_id"] == run_id and packet["mode"] == result["mode"] == mode,
        "Pipeline run/mode join failed",
    )
    p.require(result["measurement_criteria"] == "not_evaluated", "Invented acceptance verdict")
    agent = checked.json("agent-analysis.json")
    r.validate_agent(agent, packet)
    p.require(
        agent["packet_sha256"] == r.digest((output / "analysis-packet.json").read_bytes()),
        "Analysis not bound to exact packet bytes",
    )
    workflow = read_json(source / "workflow.json")
    p.require(result["status"] == workflow["status"], "Execution outcome lost")
    valid_total = nonvalid_total = 0
    for stage in r.CAPTURES:
        stage_result = result["stages"][stage]
        path = source / "stages" / f"{stage}.csv"
        if not path.exists():
            p.require(
                stage_result.get("capture") == "absent" and "metrics" not in stage_result,
                "Missing capture became numeric data",
            )
            continue
        rows = list(csv.DictReader(io.StringIO(path.read_text())))
        values = [Decimal(row["value"]) for row in rows if row["status"] == "ok"]
        count, invalid = len(values), len(rows) - len(values)
        p.require(
            (stage_result["valid"], stage_result["nonvalid"], stage_result["attempted"])
            == (count, invalid, len(rows)),
            "Independent count oracle failed",
        )
        p.require(packet["facts"][f"{stage}/valid"]["value"] == count, "Packet count changed")
        if values:
            with localcontext() as ctx:
                ctx.prec = 50
                mean = sum(values) / len(values)
                reported = Decimal(stage_result["metrics"]["mean_W"])
                # Arithmetic rounding tolerance only; never a DUT acceptance limit.
                p.require(
                    abs(reported - mean) <= max(abs(mean), Decimal("1e-30")) * Decimal("1e-32"),
                    "Independent arithmetic mean oracle failed",
                )
        else:
            p.require(stage_result["metrics"]["mean_W"] is None, "No valid rows became zero power")
        p.require(
            [point["status"] for point in stage_result["points"]]
            == [row["status"] for row in rows],
            "Failed-row gaps lost",
        )
        valid_total += count
        nonvalid_total += invalid
    page = (output / "report.html").read_text()
    parser = LocalAssets()
    parser.feed(page)
    p.require(all((output / name).is_file() for name in parser.assets), "Broken local report asset")
    p.require(
        (mode == "physical" or "SYNTHETIC - simulated readings" in page)
        and "NOT EVALUATED" in page
        and "DRAFT" in (output / "evidence.html").read_text(),
        "Report boundaries missing",
    )
    if plots:
        p.require(
            (output / "power.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            and "<svg" in (output / "power.svg").read_text(),
            "Invalid plot formats",
        )
    return {
        "run_id": run_id,
        "mode": mode,
        "execution": result["status"],
        "valid": valid_total,
        "nonvalid": nonvalid_total,
        "s40_valid": result["stages"]["S40"].get("valid", 0),
        "source": workflow["final_state"]["source"],
        "analysis_author": agent["author"],
        "report_inventory_sha256": r.digest((output / "artifacts.json").read_bytes()),
    }


def exercise_case(source, provenance, output, *, analysis=None, expected=None, plots=True):
    """No source modification, even when a later stage fails."""
    guarded()
    source, provenance, output = (
        Path(source).resolve(),
        Path(provenance).resolve(),
        Path(output).resolve(),
    )
    for protected in (
        source,
        provenance.parent,
        *([Path(analysis).resolve().parent] if analysis else []),
    ):
        p.require(output != protected and protected not in output.parents, "Output overlaps input")
    before = snapshot(source)
    provenance_before = provenance.read_bytes()
    provenance_tree_before = snapshot(provenance.parent)
    original_record = p.load(provenance)
    input_manifest = p.Bundle(provenance.parent).inventory(
        "artifacts.json", original_record["run"]["mode"]
    )
    p.require(
        input_manifest.get("schema") == "hp437b.provenance-export.v1"
        and provenance.name in input_manifest["artifacts"],
        "Unsealed provenance input",
    )
    analysis_before = Path(analysis).read_bytes() if analysis else None
    p.require(not output.exists(), "Acceptance case output already exists")
    output.mkdir(parents=True)
    try:
        imported = output / "imported-provenance"
        p.export_wf01(source, imported)
        p.require(
            p.load(imported / "provenance.json") == p.load(provenance),
            "Prospective/retained provenance disagrees with fresh import",
        )
        p.Bundle(imported).inventory("artifacts.json", p.load(provenance)["run"]["mode"])
        _, _, packet = r.prepare(source, imported / "provenance.json")
        if analysis is None:
            analysis = output / "scripted-analysis-fixture.json"
            analysis.write_bytes(r.encoded(fixture_analysis(packet)))
        r.export(
            source,
            imported / "provenance.json",
            output / "report",
            analysis_path=Path(analysis),
            plots=plots,
        )
        summary = verify_report(
            source, imported / "provenance.json", output / "report", plots=plots
        )
        if expected is not None:
            p.require(
                tuple(
                    summary[key]
                    for key in ("execution", "valid", "nonvalid", "s40_valid", "source")
                )
                == tuple(expected),
                "Scenario acceptance oracle failed",
            )
        summary["source_files_unchanged"] = len(before)
        summary["provenance_files_unchanged"] = len(provenance_tree_before)
        summary["analysis_kind"] = (
            "supplied_draft" if analysis_before is not None else "scripted_interface_fixture"
        )
        (output / "case.json").write_bytes(r.encoded(summary))
        return summary
    finally:
        p.require(snapshot(source) == before, "Acceptance changed source evidence")
        p.require(
            provenance.read_bytes() == provenance_before, "Acceptance changed provenance input"
        )
        if analysis_before is not None:
            p.require(
                Path(analysis).read_bytes() == analysis_before, "Acceptance changed analysis input"
            )


def load_cases(path):
    if path is None:
        return []
    path = Path(path).resolve()
    value = read_json(path)
    p._keys(value, ("schema", "cases"))
    p.require(
        value["schema"] == "hp437b.retained-cases.v1"
        and isinstance(value["cases"], list)
        and len(value["cases"]) <= 32,
        "Invalid retained case manifest",
    )
    cases, labels = [], set()
    for item in value["cases"]:
        p._keys(item, ("label", "bundle", "provenance", "analysis", "expected"))
        label = item["label"]
        p.require(
            isinstance(label, str)
            and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", label)
            and label not in labels,
            "Invalid/duplicate retained label",
        )
        labels.add(label)
        expected = item["expected"]
        p.require(
            isinstance(expected, list)
            and len(expected) == 5
            and expected[0] in ("completed", "failed", "interrupted")
            and all(type(n) is int and n >= 0 for n in expected[1:4])
            and expected[4] in ("off", "on", "unknown"),
            "Invalid retained oracle",
        )
        case = {"label": label, "expected": expected}
        for field in ("bundle", "provenance", "analysis"):
            p.require(
                isinstance(item[field], str) and bool(item[field]), "Explicit input paths required"
            )
            case[field] = (path.parent / item[field]).resolve()
        cases.append(case)
    return cases


def campaign(output, *, retained=None, plots=True):
    guarded()
    cases = load_cases(retained)
    output = Path(output).resolve()
    p.require(not output.exists(), "Campaign output already exists")
    for case in cases:
        for source in (case["bundle"], case["provenance"].parent, case["analysis"].parent):
            p.require(
                output != source and source not in output.parents,
                "Campaign output overlaps retained input",
            )
    output.mkdir(parents=True)
    try:
        # Import this maintained repository helper, never any code in an input bundle.
        run = run_path(str(Path(__file__).with_name("exercise_workflow.py")))["run"]

        summaries = {}
        for scenario, expected in ORACLES.items():
            bundle = output / f"synthetic-{scenario}"
            run(bundle, scenario)
            summaries[f"fresh-{scenario}"] = exercise_case(
                bundle,
                p.sidecar_path(bundle) / "provenance.json",
                output / f"accepted-{scenario}",
                expected=expected,
                plots=plots,
            )
        for case in cases:
            summaries[f"retained-{case['label']}"] = exercise_case(
                case["bundle"],
                case["provenance"],
                output / f"retained-{case['label']}",
                analysis=case["analysis"],
                expected=case["expected"],
                plots=plots,
            )
        summary = {
            "schema": "hp437b.pipeline-acceptance.v1",
            "acceptance": "passed",
            "hardware_io": False,
            "plots": plots,
            "cases": summaries,
            "limits": "WF-01/PROV-01/REPORT-01 v1 only. Scripted fixtures do not test model reasoning; supplied drafts retain their attribution. No DUT accuracy or new hardware claim.",
        }
        (output / "acceptance.json").write_bytes(r.encoded(summary))
        seal(
            output,
            {
                "schema": "hp437b.pipeline-export.v1",
                "mode": "offline-acceptance",
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
        )
        return summary
    except Exception as exc:
        (output / "failure.json").write_bytes(
            r.encoded({"acceptance": "failed", "error": f"{type(exc).__name__}: {exc}"})
        )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retained-manifest", type=Path)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = campaign(args.output, retained=args.retained_manifest, plots=not args.no_plots)
        print(f"Acceptance passed: {len(result['cases'])} cases; hardware I/O: none")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Acceptance failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
