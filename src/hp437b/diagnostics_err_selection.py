"""Fixed QX query-order/timing experiment, separate from queue qualification.

QX is documented to set ESR bit 5; a numeric ERR reply of 91 is a hypothesis.
No frequency, source, mask, or measurement-setting writes are permitted here.
"""

import time

from . import diagnostics as diag
from . import diagnostics_lifecycle as life

CASES = (
    "sm_first",
    "err_first",
    "esr_first",
    "delayed_sm_first",
    "delayed_err_first",
)
PHASES = ("baseline", *CASES, "final")
WAIT_S = 2.0


def plan():
    rows = []
    for phase in PHASES:
        codes = []
        if phase in ("baseline", "final"):
            codes = ["*ESE?", "*SRE?", "*STB?", *(["*ESR?"] * 3), *(["ERR?"] * 3), "SM", "SM"]
        else:
            codes = ["command_error"]
            if phase.startswith("delayed_"):
                codes.append("wait")
            if phase.endswith("sm_first"):
                codes += ["SM", "SM", *(["ERR?"] * 3), "*ESR?", "*ESR?"]
            elif phase.endswith("err_first"):
                codes += [*(["ERR?"] * 3), "SM", "SM", "*ESR?", "*ESR?"]
            else:
                codes += ["*ESR?", "*ESR?", *(["ERR?"] * 3), "SM", "SM"]
        counts = {}
        for code in codes:
            counts[code] = counts.get(code, 0) + 1
            kind = "stimulus" if code == "command_error" else "wait" if code == "wait" else "query"
            row = dict(
                step_id=f"{phase}.{code}.{counts[code]}",
                phase=phase,
                kind=kind,
                command=code,
                status="not_attempted",
            )
            if kind == "stimulus":
                row["fixture_hex"] = b"QX".hex()
            if kind == "wait":
                row["requested_wait_s"] = WAIT_S
            rows.append(row)
    return rows


def assessment(rows):
    cases = {}
    for phase in CASES:
        selected = [row for row in rows if row["phase"] == phase]
        cases[phase] = dict(
            complete=all(row["status"] == "completed" for row in selected),
            err_replies=life._values(rows, phase, "ERR?"),
            esr_replies=life._values(rows, phase, "*ESR?"),
            sm_entry_errors=[s["entry_error"] for s in life._values(rows, phase, "SM")],
            sm_measurement_errors=[s["measurement_error"] for s in life._values(rows, phase, "SM")],
        )
    return dict(
        cases=cases,
        cause="unresolved; compare ordered observations, not a unique causal diagnosis",
        queue_observation="not_tested; one error stimulus per case",
        evidence_limit="QX only; two fixed 2-second idle windows are not a general timing bound or proof that ERR excludes entry errors",
    )


def _gate(rows, phase):
    # Reuse existing source/configuration and quiet-baseline guards, not its
    # unsupported numeric-code requirement for isolated QX.
    reason = life._gate(rows, phase)
    if reason:
        return reason
    if phase in CASES:
        events = life._values(rows, phase, "*ESR?")
        if not events or not events[0] & 32:
            return "documented_command_error_event_not_observed"
        if life._values(rows, phase, "ERR?")[-1] != 0:
            return "error_reply_not_quiet_no_further_stimulus"
    return None


def collect(instrument, rows, started, *, before_step, after_step, on_row, raw_reply):
    """One fixed pass; cancellable no-command waits; stop on any failed step."""
    for phase in PHASES:
        for row in (item for item in rows if item["phase"] == phase):
            before_step(row["step_id"])
            row["started_elapsed_s"] = time.monotonic() - started
            try:
                if row["kind"] == "stimulus":
                    with instrument._operation() as deadline:
                        instrument._write(b"QX", deadline)
                    row["sent_hex"] = b"QX".hex()
                elif row["kind"] == "wait":
                    end = time.monotonic() + WAIT_S
                    while time.monotonic() < end:
                        after_step()  # Cancellation/deadline check, no instrument I/O.
                        time.sleep(min(0.02, max(0, end - time.monotonic())))
                else:
                    reply = instrument.query(row["command"])
                    row.update(raw_hex=reply.raw.hex(), value=diag._value(reply.value))
                after_step()
            except BaseException as exc:
                row.update(
                    status="failed",
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_s=time.monotonic() - started,
                )
                if row["kind"] != "wait":
                    row["raw_hex"] = raw_reply().hex()
                on_row(row)
                if not isinstance(exc, Exception):
                    raise
                return "query_failed", dict(stop_reason="step_failed", **assessment(rows))
            row.update(status="completed", elapsed_s=time.monotonic() - started)
            on_row(row)
        reason = _gate(rows, phase)
        if reason:
            return "observation_stop", dict(
                stop_reason=reason, stopped_after_phase=phase, **assessment(rows)
            )
    return "completed", dict(stop_reason=None, **assessment(rows))
