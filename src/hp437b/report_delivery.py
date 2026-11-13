"""Optional PDF export and portable, hashed report/evidence ZIPs; no acquisition."""

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from . import controlled_sweep as s
from . import pdf_reports
from . import provenance as p
from . import reporting as r
from .workflow_report import preflight

SCHEMA = "hp437b.portable-report.v1"
MAX_ARCHIVE = 256 * 1024 * 1024


def workflow_kind(source):
    bundle = p.Bundle(source)
    cap = p._json(bundle.read("workflow.json"))
    if cap.get("schema") == s.SCHEMA:
        return cap["workflow_kind"]
    for kind in ("WF-04", "WF-05", "WF-06"):
        if cap.get("schema") == s.module(kind).SCHEMA:
            return kind
    raise ValueError("PDF export supports WF-04–WF-06 and their fake suites")


def preflight_delivery(source, report, *, pdf=False, package=False):
    p.require(not package or pdf, "Portable packages require PDFs")
    if pdf:
        pdf_reports.preflight()
    if package:
        target = Path(str(Path(report).resolve()) + ".zip")
        p.require(not target.exists(), "Portable ZIP output exists")
        _layout(source, report, target)


def _layout(source, report, target):
    source, report, target = Path(source).resolve(), Path(report).resolve(), Path(target).absolute()
    p.require(
        source != report and source not in report.parents and report not in source.parents,
        "Report and evidence must be separate",
    )
    p.require(not target.is_symlink(), "Symlink ZIP output is unsupported")
    target = target.parent.resolve() / target.name
    for root in (source, report):
        p.require(
            target != root and root not in target.parents and target not in root.parents,
            "ZIP must be outside report/evidence directories",
        )
    return source, report, target


def _exact_inventory(bundle):
    inv = bundle.inventory("artifacts.json", "synthetic")
    p.require(
        not any(path.is_symlink() for path in bundle.root.rglob("*")),
        "Symlink bundle entries are unsupported",
    )
    actual = {
        path.relative_to(bundle.root).as_posix()
        for path in bundle.root.rglob("*")
        if path.is_file()
    }
    p.require(actual == set(bundle.entries), "Uninventoried files cannot enter a portable package")
    return inv


def _pair(source, report):
    evidence = p.Bundle(source)
    source_inv = _exact_inventory(evidence)
    output = p.Bundle(report)
    report_inv = _exact_inventory(output)
    if "suite.json" in evidence.entries:
        from . import test_suite as u

        cap, binding, _ = u.load(source)
        expected = {
            **cap,
            "profile_id": binding["profile"]["profile_id"],
            "profile_revision": binding["profile"]["revision"],
            "dut": binding["profile"]["dut"],
            "operator": binding["operator"],
            "source_inventory_sha256": r.digest(evidence.read("artifacts.json")),
        }
        run_id = cap["suite_id"]
        schema = "hp437b.test-suite-report.v1"
        for item in cap["children"]:
            _pair(Path(source) / item["path"], Path(report) / "workflows" / item["workflow"])
    else:
        kind = workflow_kind(source)
        w = s.module(kind)
        cap, rows, native = w.load(source)
        expected = w.analyze(cap, rows)
        p.require(
            output.json("provenance.json") == w.provenance(cap, native),
            "Report provenance differs from evidence",
        )
        p.verify(output.json("provenance.json"), source)
        run_id = cap["run_id"]
        schema = {
            "WF-04": "hp437b.power-setting-report.v1",
            "WF-05": "hp437b.frequency-sweep-report.v1",
            "WF-06": "hp437b.supply-sensitivity-report.v1",
        }[kind]
    p.require(
        report_inv.get("schema") == schema
        and report_inv.get("run_id") == run_id
        and source_inv.get("run_id") == run_id,
        "Report/capture identity mismatch",
    )
    p.require(
        output.json("results.json") == expected, "Report results differ from verified evidence"
    )
    meta = output.json("metadata.json")
    p.require(
        meta.get("source_inventory_sha256", meta.get("capture_inventory_sha256"))
        == r.digest(evidence.read("artifacts.json")),
        "Report source hash mismatch",
    )
    p.require(
        meta.get("pdf", {}).get("page_count") == 1
        and output.read("report.pdf").startswith(b"%PDF-"),
        "Portable export requires a sealed one-page PDF report",
    )
    return evidence, output, run_id


def _zip_entry(archive, name, data):
    item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    item.create_system = 3
    item.external_attr = 0o100644 << 16
    item.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def package(source, report, target=None):
    target = Path(str(Path(report).resolve()) + ".zip") if target is None else Path(target)
    source, report, target = _layout(source, report, target)
    p.require(not target.exists(), "Portable ZIP output exists")
    evidence, output, run_id = _pair(source, report)
    p.require(
        sum(item["bytes"] for bundle in (evidence, output) for item in bundle.entries.values())
        <= MAX_ARCHIVE,
        "Portable payload exceeds 256 MiB",
    )
    manifest = dict(
        schema=SCHEMA,
        mode="synthetic",
        run_id=run_id,
        evidence_inventory_sha256=r.digest(evidence.read("artifacts.json")),
        report_inventory_sha256=r.digest(output.read("artifacts.json")),
        artifacts={},
    )
    readme = b"RF Output Power Test - portable report\n\nExtract the entire ZIP into a new directory. Open report/report.pdf for the one-page answer. Open report/report.html for linked detail and individual reports. Sealed original evidence is under evidence/. Provenance references are relative to the corresponding original capture (for suites: evidence/captures/WF-04 etc.).\n\nHashes detect changes, not author/device authenticity. All included measurements are synthetic. No equipment, network, or AI-provider access is needed.\n\nVerify without extracting: python -m hp437b.report_delivery verify --package FILE.zip\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=".report-package-", suffix=".tmp", dir=target.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            with zipfile.ZipFile(handle, "w") as archive:
                for prefix, bundle in (("evidence", evidence), ("report", output)):
                    for name, item in sorted(bundle.entries.items()):
                        data = bundle.read(name, item)
                        path = prefix + "/" + name
                        _zip_entry(archive, path, data)
                        manifest["artifacts"][path] = dict(bytes=len(data), sha256=r.digest(data))
                _zip_entry(archive, "START-HERE.txt", readme)
                manifest["artifacts"]["START-HERE.txt"] = dict(
                    bytes=len(readme), sha256=r.digest(readme)
                )
                _zip_entry(archive, "package-manifest.json", r.encoded(manifest))
            handle.flush()
            os.fsync(handle.fileno())
        verify(temporary)
        fresh_evidence, fresh_report, fresh_id = _pair(source, report)
        p.require(
            fresh_id == run_id
            and r.digest(fresh_evidence.read("artifacts.json"))
            == manifest["evidence_inventory_sha256"]
            and r.digest(fresh_report.read("artifacts.json"))
            == manifest["report_inventory_sha256"],
            "Report/evidence changed during packaging",
        )
        os.link(temporary, target)  # atomic no-overwrite publication, same filesystem
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def verify(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [item.filename for item in entries]
        p.require(
            len(names) == len(set(names))
            and len(names) == len({name.casefold() for name in names})
            and 0 < len(names) <= 8194,
            "Duplicate/excessive archive entries",
        )
        p.require(
            sum(item.file_size for item in entries) <= MAX_ARCHIVE + p.MAX_JSON
            and all(
                0 <= item.file_size <= p.MAX_FILE
                and ((item.external_attr >> 16) & 0o170000) == 0o100000
                for item in entries
            ),
            "Invalid archive member size/type",
        )
        for name in names:
            p._relative(name)
            p.require(
                name in ("START-HERE.txt", "package-manifest.json")
                or name.startswith(("report/", "evidence/")),
                "Unexpected archive path",
            )
        manifest = p._json(archive.read("package-manifest.json"))
        p._keys(
            manifest,
            (
                "schema",
                "mode",
                "run_id",
                "evidence_inventory_sha256",
                "report_inventory_sha256",
                "artifacts",
            ),
        )
        p.require(
            manifest["schema"] == SCHEMA
            and manifest["mode"] == "synthetic"
            and set(manifest["artifacts"]) == set(names) - {"package-manifest.json"},
            "Archive manifest mismatch",
        )
        for name, expected in manifest["artifacts"].items():
            p._keys(expected, ("bytes", "sha256"))
            data = archive.read(name)
            p.require(
                expected == dict(bytes=len(data), sha256=r.digest(data)),
                "Archive member hash mismatch",
            )
        for prefix, key in (
            ("report", "report_inventory_sha256"),
            ("evidence", "evidence_inventory_sha256"),
        ):
            data = archive.read(prefix + "/artifacts.json")
            p.require(r.digest(data) == manifest[key], "Archive root inventory hash mismatch")
            inv = p._json(data)
            p.require(
                inv.get("mode") == "synthetic" and inv.get("run_id") == manifest["run_id"],
                "Archive root identity mismatch",
            )
            expected_paths = {prefix + "/" + name for name in inv["artifacts"]} | {
                prefix + "/artifacts.json"
            }
            p.require(
                expected_paths == {name for name in names if name.startswith(prefix + "/")},
                "Archive inventory file set mismatch",
            )
            for name, expected in inv["artifacts"].items():
                p.require(
                    manifest["artifacts"][prefix + "/" + name] == expected,
                    "Archive inventory/member mismatch",
                )
    return manifest


def export(source, output, *, plots=True, portable=False):
    source, output = preflight(source, output, plots=plots)
    preflight_delivery(source, output, pdf=True, package=portable)
    if (source / "suite.json").is_file():
        from . import test_suite

        return test_suite.publish(source, output, plots=plots, pdf=True, package=portable)
    w = s.module(workflow_kind(source))
    return w.publish(source, output, plots=plots, pdf=True, package=portable)


def announce(report, *, pdf=False, package=False):
    if pdf or package:
        print(Path(report).resolve() / "report.pdf")
    if package:
        print(Path(str(Path(report).resolve()) + ".zip"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export_cmd = commands.add_parser("export")
    export_cmd.add_argument("--bundle", required=True, type=Path)
    export_cmd.add_argument("--output", required=True, type=Path)
    export_cmd.add_argument("--package", action="store_true")
    export_cmd.add_argument("--no-plots", action="store_true")
    zip_cmd = commands.add_parser("package")
    zip_cmd.add_argument("--bundle", required=True, type=Path)
    zip_cmd.add_argument("--report", required=True, type=Path)
    zip_cmd.add_argument("--output", required=True, type=Path)
    verify_cmd = commands.add_parser("verify")
    verify_cmd.add_argument("--package", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify(args.package)
            print("Verified portable report: " + result["run_id"])
        elif args.command == "package":
            print(package(args.bundle, args.report, args.output))
        else:
            export(args.bundle, args.output, plots=not args.no_plots, portable=args.package)
            print(args.output / "report.pdf")
            if args.package:
                print(Path(str(args.output) + ".zip"))
        return 0
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Report delivery: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
