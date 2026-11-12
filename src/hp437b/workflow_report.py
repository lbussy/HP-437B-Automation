"""Human-started, deterministic WF-01 provenance and richer report publication.

Consumes sealed captures only. No AI provider, network client, hardware operation,
measurement retry, or source-code execution exists in this module.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

from . import provenance as p
from . import reporting as r


def preflight(source, output, *, plots=True):
    """Validate a future capture/report layout before an optional physical run starts."""
    source, output = Path(source).resolve(), Path(output).resolve()
    p.require(not output.exists(), "Workflow report output already exists")
    for protected in (source, p.sidecar_path(source)):
        p.require(
            output != protected
            and protected not in output.parents
            and output not in protected.parents,
            "Capture/report outputs must be separate, non-nested directories",
        )
    p.require(
        not plots or importlib.util.find_spec("matplotlib") is not None,
        "Install the optional reports extra, or request --report-no-plots/--no-plots",
    )
    return source, output


def _seal(output, metadata):
    bundle = p.Bundle(output)
    for path in sorted(output.rglob("*")):
        if path.is_file():
            bundle.read(path.relative_to(output).as_posix())
    files = {
        name: {"sha256": item["sha256"], "bytes": item["bytes"]}
        for name, item in bundle.entries.items()
    }
    temporary = output / ".inventory.tmp"
    with temporary.open("xb") as handle:
        handle.write(r.encoded({**metadata, "artifacts": files}))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output / "artifacts.json")


def publish(source, output, *, plots=True, operator=None):
    """Import provenance and build a complete report in one invocation after closure."""
    source, output = preflight(source, output, plots=plots)
    r.report_context.validate_operator(operator)
    # Refuse unsealed/running captures before allocating a job output.
    original = p.import_wf01(source)
    p.verify(original, source)
    source_inventory = r.digest(p.Bundle(source).read("artifacts.json"))
    output.mkdir(parents=True, exist_ok=False)
    try:
        provenance = output / "provenance"
        record = p.export_wf01(source, provenance)
        p.require(record == original, "Source changed before provenance export")
        result = r.export(
            source,
            provenance / "provenance.json",
            output / "report",
            plots=plots,
            operator=operator,
        )
        p.verify(original, source)
        p.require(
            r.digest(p.Bundle(source).read("artifacts.json")) == source_inventory,
            "Capture inventory changed during report generation",
        )
        summary = {
            "schema": "hp437b.deterministic-job.v1",
            "run_id": result["run_id"],
            "mode": result["mode"],
            "execution": result["status"],
            "report_status": "completed",
            "analysis": "deterministic_only",
            "operator": p._json((output / "report/artifacts.json").read_bytes())["report_context"][
                "operator"
            ],
            "measurement_criteria": "not_evaluated",
            "capture_inventory_sha256": source_inventory,
            "provenance_inventory_sha256": r.digest((provenance / "artifacts.json").read_bytes()),
            "report_inventory_sha256": r.digest((output / "report/artifacts.json").read_bytes()),
        }
        (output / "job.json").write_bytes(r.encoded(summary))
        _seal(
            output,
            {
                "schema": "hp437b.deterministic-job-export.v1",
                "mode": result["mode"],
                "run_id": result["run_id"],
                "generator_sha256": r.digest(Path(__file__).read_bytes()),
            },
        )
        return summary
    except Exception as exc:
        # Keep diagnostics; a valid root inventory is the completion boundary.
        (output / "failure.json").write_bytes(
            r.encoded({"report_status": "failed", "error_type": type(exc).__name__})
        )
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument(
        "--operator", help="Operator name; defaults to captured name, then HP437B_OPERATOR"
    )
    args = parser.parse_args(argv)
    try:
        result = publish(args.bundle, args.output, plots=not args.no_plots, operator=args.operator)
        print(r.encoded(result).decode(), end="")
        return 0 if result["execution"] == "completed" else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Deterministic report failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
