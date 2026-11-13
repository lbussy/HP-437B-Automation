"""Reusable, explicit fake-only DUT profiles for individual controlled sweep runs."""

import argparse
import re
import sys
from pathlib import Path

from . import controlled_sweep as s
from . import provenance as p
from . import report_context
from . import reporting as r

SCHEMA = "hp437b.dut-test-profile.v1"
BINDING = "hp437b.dut-test-profile-binding.v1"
KINDS = ("WF-04", "WF-05", "WF-06")
MAX_PROFILE = 256 * 1024


def validate(document):
    """Validate every selected plan and translated fake condition before any run."""
    p.require(len(r.encoded(document)) <= MAX_PROFILE, "Profile exceeds 256 KiB")
    p._keys(
        document,
        ("schema", "profile_id", "revision", "mode", "description", "operator", "dut", "workflows"),
    )
    p.require(
        document["schema"] == SCHEMA and document["mode"] == "fake",
        "Only v1 fake profiles are supported",
    )
    p.require(
        isinstance(document["profile_id"], str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", document["profile_id"]),
        "Invalid profile ID",
    )
    p.require(
        type(document["revision"]) is int and 1 <= document["revision"] <= 1000000,
        "Invalid profile revision",
    )
    w = s.module("WF-04")
    w.text(document["description"], 240)
    report_context.validate_operator(document["operator"])
    dut = document["dut"]
    p._keys(dut, ("name", "manufacturer", "model", "serial", "asset_id"))
    w.text(dut["name"])
    for key in ("manufacturer", "model", "serial", "asset_id"):
        if dut[key] is not None:
            w.text(dut[key])
    workflows = document["workflows"]
    p.require(
        isinstance(workflows, dict) and 1 <= len(workflows) <= 3 and set(workflows) <= set(KINDS),
        "Select one to three supported workflows",
    )
    for kind, entry in workflows.items():
        p._keys(entry, ("plan", "criteria"))
        workflow = s.module(kind)
        plan = workflow.validate_plan(entry["plan"])
        p.require(plan["name"] == dut["name"], "Workflow DUT name differs from profile identity")
        workflow.validate_criteria(entry["criteria"], plan)
        for point in plan["points"]:
            s.specification(kind, plan, point)
    # Return a detached JSON copy; callers cannot mutate a validated run by alias.
    return p._json(r.encoded(document))


def load(path):
    path = Path(path).absolute()
    data = p.Bundle(path.parent).read(path.name)
    p.require(len(data) <= MAX_PROFILE, "Profile exceeds 256 KiB")
    return validate(p._json(data))


def example():
    """Fictional example, with explicitly absent acceptance criteria and identities."""
    document = validate(
        dict(
            schema=SCHEMA,
            profile_id="fictional-transmitter",
            revision=1,
            mode="fake",
            description="Fictional reusable transmitter example; no physical RF or DUT limits",
            operator=None,
            dut=dict(
                name="Fictional transmitter",
                manufacturer=None,
                model=None,
                serial=None,
                asset_id=None,
            ),
            workflows={
                kind: dict(plan=s.module(kind).default_plan(), criteria=None) for kind in KINDS
            },
        )
    )

    # Match the other fake workflows' declared 1.5 A restored condition for suites.
    document["workflows"]["WF-06"]["plan"]["supply"]["current_limit_A"] = "1.5"
    return validate(document)


def bind(document, kind, operator=None):
    document = validate(document)
    p.require(kind in document["workflows"], "Workflow is not included in profile")
    identity = report_context.resolve_operator(operator, document["operator"])
    if identity["origin"] == "capture":
        identity["origin"] = "profile"
    return dict(
        schema=BINDING,
        profile=document,
        profile_sha256=r.digest(r.encoded(document)),
        workflow_kind=kind,
        operator=identity,
    )


def validate_binding(binding, kind):
    p._keys(binding, ("schema", "profile", "profile_sha256", "workflow_kind", "operator"))
    p.require(
        binding["schema"] == BINDING and binding["workflow_kind"] == kind,
        "Profile binding workflow/schema mismatch",
    )
    document = validate(binding["profile"])
    p.require(
        kind in document["workflows"]
        and binding["profile_sha256"] == r.digest(r.encoded(document)),
        "Profile snapshot identity/hash mismatch",
    )
    operator = binding["operator"]
    p._keys(operator, ("value", "basis", "origin"))
    value = report_context.validate_operator(operator["value"])
    p.require(value == operator["value"], "Operator binding is not normalized")
    p.require(
        operator["origin"] in ("argument", "profile", "environment", "not_recorded"),
        "Invalid operator origin",
    )
    p.require(
        (value is None and operator == dict(value=None, basis="unknown", origin="not_recorded"))
        or (
            value is not None
            and operator["basis"] == "supplied"
            and operator["origin"] != "not_recorded"
        ),
        "Invalid operator basis",
    )
    if operator["origin"] == "profile":
        p.require(
            value == report_context.validate_operator(document["operator"]),
            "Profile operator mismatch",
        )
    return document["workflows"][kind]


def capture(
    document,
    kind,
    output,
    *,
    operator=None,
    report_output=None,
    plots=True,
    fault=None,
    fault_point=None,
    stop_before=None,
):
    binding = bind(document, kind, operator)
    entry = validate_binding(binding, kind)
    return s.run(
        kind,
        output,
        plan=entry["plan"],
        criteria=entry["criteria"],
        operator=binding["operator"]["value"],
        report_output=report_output,
        plots=plots,
        fault=fault,
        fault_point=fault_point,
        stop_before=stop_before,
        test_profile=binding,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("example", help="Print fictional JSON template to stdout")
    check = commands.add_parser("validate", help="Validate all plans without capturing")
    check.add_argument("--profile", type=Path, required=True)
    run = commands.add_parser("run", help="Run one selected workflow using fakes only")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--workflow", choices=KINDS, required=True)
    run.add_argument("--operator")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--report-output", type=Path)
    run.add_argument("--no-plots", action="store_true")
    run.add_argument("--fault", choices=s.FAULTS)
    run.add_argument("--fault-point")
    run.add_argument("--stop-before")
    args = parser.parse_args(argv)
    try:
        if args.command == "example":
            print(r.encoded(example()).decode(), end="")
            return 0
        document = load(args.profile)
        if args.command == "validate":
            print(f"Valid fake profile: {document['profile_id']} revision {document['revision']}")
            return 0
        result = capture(
            document,
            args.workflow,
            args.output,
            operator=args.operator,
            report_output=args.report_output,
            plots=not args.no_plots,
            fault=args.fault,
            fault_point=args.fault_point,
            stop_before=args.stop_before,
        )
        return 0 if result["status"] == "completed" else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"DUT profile: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
