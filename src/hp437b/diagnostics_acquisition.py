"""Fixed supervised POWER REF setting checks, with healthy-path restoration only."""

import time

from . import diagnostics as diag

SETTLE_S = 20.0
PLAN_VERSION = 2
RESTORE_REFRESH_S = 4.0
RESTORE_RESERVE_S = 24.0
PHASES = (
    "baseline",
    "reference",
    "resolution1",
    "resolution2",
    "filter1",
    "filter4",
    "auto_filter",
    "filter_hold",
    "range_hold",
    "range5",
    "auto_range",
    "hold_immediate",
    "delayed",
    "free_run",
    "restore",
)
PRESERVED = (
    "logarithmic",
    "relative",
    "unit",
    "group_trigger",
    "limits_on",
    "offset_on",
    "duty_on",
)


def plan(original_resolution, settle_s=SETTLE_S, restore_refresh_s=RESTORE_REFRESH_S):
    groups = {
        "baseline": [("query", "SM", None)],
        "reference": [("command", "OC1", None), ("wait", "settle", settle_s)],
        "resolution1": [("command", "FM", 4), ("command", "RE", 1)],
        "resolution2": [("command", "FM", 4), ("command", "RE", 2)],
        "filter1": [("command", "FM", 1)],
        "filter4": [("command", "FM", 4)],
        "auto_filter": [("command", "FA", None)],
        "filter_hold": [("command", "FH", None)],
        "range_hold": [("command", "RH", None)],
        "range5": [("command", "RM", 5)],
        "auto_range": [("command", "RA", None)],
        "hold_immediate": [("command", "FM", 1), ("command", "TR0", None)],
        "delayed": [],
        "free_run": [("command", "TR3", None)],
        "restore": [
            ("command", "OC0", None),
            ("command", "RE", original_resolution),
            ("command", "RA", None),
            ("command", "FA", None),
            ("command", "TR3", None),
            ("wait", "restore_refresh", restore_refresh_s),
        ],
    }
    rows = []
    for phase in PHASES:
        steps = list(groups[phase])
        if phase not in ("baseline", "restore"):
            trigger = (
                "TR2"
                if phase in ("filter1", "filter4", "delayed")
                else "READ"
                if phase == "free_run"
                else "TR1"
            )
            steps += [("acquisition", trigger, None), ("query", "SM", None)]
        if phase == "restore":
            steps.append(("query", "SM", None))
        for number, (kind, code, value) in enumerate(steps):
            rows.append(
                dict(
                    step_id=f"{phase}.{number}.{code}",
                    phase=phase,
                    kind=kind,
                    command=code,
                    argument=value,
                    status="not_attempted",
                )
            )
    return rows


def collect(instrument, rows, started, *, deadline, before_step, after_step, on_row, raw_reply):
    baseline = previous = None
    stop_reason = None
    restoration_attempted = restoration_verified = False
    may_be_on = False
    reference_on_observed = False
    changed = False

    def assessment():
        return dict(
            plan_version=PLAN_VERSION,
            restoration_verification="TR3 plus bounded refresh and SM; no restoration TR1",
            remote_RE_filter_observations=[
                dict(phase=row["phase"], filter_code=row["value"]["filter_code"])
                for row in rows
                if row["phase"] in ("resolution1", "resolution2")
                and row["command"] == "SM"
                and row["status"] == "completed"
            ],
            stop_reason=stop_reason,
            restoration_attempted=restoration_attempted,
            auto_modes_reference_off_verified=restoration_verified,
            reference_may_be_on=may_be_on,
            reference_on_observed=reference_on_observed,
            resolution_usb_verified=False,
            resolution_restore_basis="Original operator value; accepted RE write only; final front-panel comparison required",
            evidence_limit="Selected settings only; no RF accuracy, settling, general cadence, or dynamic trigger-hold claim",
        )

    for phase in PHASES:
        if stop_reason and phase != "restore":
            continue
        if phase == "restore":
            if not changed:
                break
            restoration_attempted = True
        for row in (row for row in rows if row["phase"] == phase):
            if (
                phase != "restore"
                and time.monotonic() + (row["argument"] if row["kind"] == "wait" else 0)
                >= deadline - RESTORE_RESERVE_S
            ):
                stop_reason = "main_budget_reserved_for_restoration"
                break
            row["started_elapsed_s"] = time.monotonic() - started
            kind, code, value = row["kind"], row["command"], row["argument"]
            row["io_attempted"] = False
            verified_restore = False
            observed_reference_on = False
            try:
                before_step(row["step_id"])
                kind, code, value = row["kind"], row["command"], row["argument"]
                if kind == "command":
                    changed = True  # A failed/partial write may still have taken effect.
                    if code == "OC1":
                        may_be_on = True
                    row["io_attempted"] = True
                    instrument.command(code, value, confirmed=code == "OC1")
                elif kind == "wait":
                    end = time.monotonic() + value
                    while time.monotonic() < end:
                        after_step()
                        time.sleep(min(0.02, max(0, end - time.monotonic())))
                elif kind == "acquisition":
                    row["io_attempted"] = True
                    measured = instrument.acquire(None if code == "READ" else code)
                    row.update(
                        raw_hex=measured.raw.hex(),
                        value=dict(
                            value=str(measured.value) if measured.value is not None else None,
                            unit=measured.unit,
                            error_code=measured.error_code,
                        ),
                    )
                    if measured.error_code is not None:
                        stop_reason = "measurement_error_restore_known_settings"
                else:
                    row["io_attempted"] = True
                    reply = instrument.query("SM")
                    status = reply.value
                    row.update(raw_hex=reply.raw.hex(), value=diag._value(status))
                    bad = (
                        status.measurement_error
                        or status.entry_error
                        or status.operating_mode
                        or status.reference_on != (phase not in ("baseline", "restore"))
                    )
                    if phase == "baseline":
                        baseline = status
                        may_be_on = status.reference_on
                        bad = (
                            bad
                            or status.standby
                            or status.unit != "W"
                            or status.relative
                            or status.offset_on
                            or status.duty_on
                            or status.range_code < 11
                            or status.filter_code < 10
                        )
                        if bad:
                            stop_reason = "baseline_requires_live_source_off_absolute_W_auto_range_auto_filter_no_corrections"
                    else:
                        bad = bad or any(
                            getattr(status, key) != getattr(baseline, key) for key in PRESERVED
                        )
                        if phase in ("auto_filter", "restore"):
                            bad = bad or status.filter_code < 10
                        if phase in ("resolution1", "resolution2"):
                            bad = bad or (status.filter_code < 10 and status.filter_code != 2)
                        if phase in ("filter1", "hold_immediate", "delayed"):
                            bad = bad or status.filter_code != 0
                        if phase == "filter4":
                            bad = bad or status.filter_code != 2
                        if phase == "filter_hold":
                            bad = bad or status.filter_code != previous.filter_code - 10
                        if phase == "range_hold":
                            bad = bad or status.range_code != previous.range_code - 10
                        if phase == "range5":
                            bad = bad or status.range_code != 5
                        if phase in ("auto_range", "restore"):
                            bad = bad or status.range_code < 11
                        if phase in ("free_run", "restore"):
                            bad = bad or status.standby
                        else:
                            bad = bad or not status.standby
                        if bad:
                            stop_reason = (
                                "observed_state_mismatch_restore_known_settings"
                                if phase != "restore"
                                else "restoration_observation_failed"
                            )
                        if phase == "restore" and not bad:
                            verified_restore = reference_on_observed
                    observed_reference_on = status.reference_on and phase not in (
                        "baseline",
                        "restore",
                    )
                    previous = status
                after_step()
                reference_on_observed = reference_on_observed or observed_reference_on
                if verified_restore:
                    restoration_verified = True
                    may_be_on = False
            except BaseException as exc:
                row.update(
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_s=time.monotonic() - started,
                )
                if row["io_attempted"]:
                    row["raw_hex"] = raw_reply().hex()
                on_row(row)
                stop_reason = "transaction_failed_or_cancelled_no_further_commands_or_restoration"
                if not isinstance(exc, Exception):
                    raise
                return "query_failed", assessment()
            row.update(status="completed", elapsed_s=time.monotonic() - started)
            on_row(row)
            if stop_reason and phase != "restore":
                break
    return "observation_stop" if stop_reason else "completed", assessment()
