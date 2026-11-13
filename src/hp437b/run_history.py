"""Read-only POWER REF history details and conservative, declared-context comparisons."""

import fcntl
from contextlib import contextmanager
from decimal import Decimal, localcontext
from pathlib import Path

from . import provenance as p
from . import reference_suite, report_recovery

# Attestation timestamps and presence are operational facts, not measurement settings.
TRANSIENT = {
    "adapter_on_mac",
    "direct_sensor_reference_path",
    "reference_off",
    "warmed_up",
    "other_apps_closed",
    "operator_available",
    "prepared_record_utc",
    "confirmation_origin",
    "operator",
}


@contextmanager
def closed_capture(path):
    lock = Path(path) / ".capture.lock"
    p.require(not lock.is_symlink(), "Symlink capture lock is unsupported")
    with lock.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("The capture worker still owns this run; wait for closure") from None
        yield


def metrics(record, result, kind):
    stages = result["stages"]
    zero = stages.get("S10" if kind == "WF-01" else "baseline-before", {})
    values = result.get("metrics", {})
    if kind == "WF-01":
        plateau = stages.get("S40", {})
        mean = plateau.get("metrics", {}).get("mean_W")
        valid = plateau.get("valid", 0)
    elif kind == "WF-02":
        mean, valid = values.get("mean_W"), result["coverage"]["valid"]
    else:
        mean = values.get("equal_cycle_mean_W")
        valid = sum(c.get("valid", 0) for c in result["cycles"] if c["included_in_aggregate"])
    return dict(
        zero_W=zero.get("metrics", {}).get("mean_W"),
        mean_W=mean,
        valid_plateau=valid,
        endpoint_change_percent=values.get("endpoint_change_percent"),
        cycle_spread_W=values.get("cycle_spread_W"),
        completed_cycles=result.get("completed_cycles"),
    )


def details(path, request):
    """Use native readers, never the operational state or an old report as numeric evidence."""
    path = Path(path)
    with closed_capture(path):
        digest = report_recovery.inspect(path, request)
        source = path / "capture"
        if request["mode"] == "reference_suite":
            parent, _, _ = reference_suite.load(source)
            captured = [item["workflow"] for item in parent["children"]]
        else:
            captured = request["workflows"]
        rows = []
        for kind in captured:
            child = source / "captures" / kind if request["mode"] == "reference_suite" else source
            native, result, _ = reference_suite.native(child, kind)
            setup = native.get("setup") or {}
            context = {k: v for k, v in setup.items() if k not in TRANSIENT}
            unknown = [k for k in ("meter_serial", "sensor_serial", "signal") if not setup.get(k)]
            rows.append(
                dict(
                    workflow=kind,
                    run_id=native["run_id"],
                    mode=native["mode"],
                    execution=native["status"],
                    started_utc=native["started_utc"],
                    finished_utc=native.get("finished_utc"),
                    metrics=metrics(native, result, kind),
                    meter_serial=setup.get("meter_serial"),
                    sensor_serial=setup.get("sensor_serial"),
                    context=context,
                    profile=native.get("profile"),
                    unknown_context=unknown,
                    resource=native.get("resource"),
                    software=native.get("software"),
                )
            )
        # Detect a concurrent local edit even when a writer ignored the advisory capture lock.
        p.require(
            report_recovery.inspect(path, request) == digest, "Capture changed during inspection"
        )
        return dict(
            source_inventory_sha256=digest,
            workflows=rows,
            requested_workflows=request["workflows"],
            not_captured=[k for k in request["workflows"] if k not in captured],
        )


def compare(entries, kind):
    p.require(kind in reference_suite.KINDS, "Select a POWER REF workflow")
    selected = []
    for job_id, detail in entries:
        row = next((row for row in detail["workflows"] if row["workflow"] == kind), None)
        p.require(row is not None, f"{kind} was not captured in run {job_id[:8]}")
        selected.append(dict(job_id=job_id, **row))
    p.require(
        len({row["run_id"] for row in selected}) == len(selected),
        "These jobs contain the same acquisition; choose distinct measurements",
    )
    differences = []
    first = selected[0]
    for row in selected:
        flags = []
        if row["mode"] != first["mode"]:
            flags.append("Physical and synthetic data differ")
        if row["execution"] != "completed":
            flags.append("Capture is incomplete; available values are partial")
        if row["unknown_context"]:
            flags.append("Missing declared context: " + ", ".join(row["unknown_context"]))
        if row["profile"] is None:
            flags.append("Measurement profile is unknown")
        changed = sorted(
            k
            for k in set(first["context"]) | set(row["context"])
            if first["context"].get(k) != row["context"].get(k)
        )
        if changed:
            flags.append("Equipment/setup differs: " + ", ".join(changed))
        if row["profile"] != first["profile"]:
            flags.append("Measurement profile differs")
        if row["resource"] != first["resource"]:
            flags.append("Recorded resource differs")
        row["flags"] = flags
        differences.extend(flags)
    eligible = not differences and all(row["metrics"]["mean_W"] is not None for row in selected)
    with localcontext() as context:
        context.prec = 50
        for row in selected:
            row["mean_change_W"] = (
                str(Decimal(row["metrics"]["mean_W"]) - Decimal(first["metrics"]["mean_W"]))
                if eligible
                else None
            )
    return dict(
        workflow=kind,
        rows=selected,
        changes_available=eligible,
        notes=list(dict.fromkeys(differences))
        or [
            "Recorded contexts match; this does not independently establish equivalent conditions."
        ],
        verdict="Descriptive comparison only; no acceptance or calibration verdict",
    )
