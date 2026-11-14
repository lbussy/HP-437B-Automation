"""Fixed, opt-in error-lifecycle experiment; no arbitrary command injection.

Sources: operating manual 3-39 (PDF 69), A-1/A-4 (PDF 151/154).
The hypotheses below describe bounded observations, not assumed meter semantics.
"""

import time

from . import diagnostics as diag

_STIMULI = {"command_error": b"QX", "execution_error": b"FR-3GZ"}
PHASES = ("baseline", "event", "single_a", "single_b", "a_then_b", "b_then_a", "final")


def plan():
    rows = []

    def add(phase, kind, code, count=1):
        for number in range(1, count + 1):
            rows.append(
                dict(
                    step_id=f"{phase}.{code}.{number}",
                    phase=phase,
                    kind=kind,
                    command=code,
                    status="not_attempted",
                )
            )

    for phase in PHASES:
        if phase in ("baseline", "final"):
            for code in ("*ESE?", "*SRE?", "*STB?"):
                add(phase, "query", code)
        if phase in ("event", "single_a"):
            add(phase, "stimulus", "command_error")
        elif phase == "single_b":
            add(phase, "stimulus", "execution_error")
        elif phase in ("a_then_b", "b_then_a"):
            codes = ("command_error", "execution_error")
            for code in codes if phase == "a_then_b" else codes[::-1]:
                add(phase, "stimulus", code)
        # Event case observes ESR before ERR; other error cases reverse that order.
        order = ("*ESR?", "ERR?") if phase in ("baseline", "event") else ("ERR?", "*ESR?")
        for code in order:
            add(phase, "query", code, 3)
        add(phase, "query", "SM", 2)
    for row in rows:
        if row["kind"] == "stimulus":
            row["fixture_hex"] = _STIMULI[row["command"]].hex()
    return rows


def _values(rows, phase, code):
    return [
        row["value"]
        for row in rows
        if row["phase"] == phase and row["command"] == code and row["status"] == "completed"
    ]


def assessment(rows):
    event = _values(rows, "event", "*ESR?")
    event_result = "inconclusive"
    if len(event) == 3 and event[0] & 32:
        if all(not value & 32 for value in event[1:]):
            event_result = "command_bit_cleared_on_subsequent_reads"
        elif all(value & 32 for value in event):
            event_result = "command_bit_persists_across_three_reads"
    ab, ba = _values(rows, "a_then_b", "ERR?"), _values(rows, "b_then_a", "ERR?")
    signatures = {
        ((91, 82, 0), (82, 91, 0)): "fifo_like_two_error_signature",
        ((82, 91, 0), (91, 82, 0)): "lifo_like_two_error_signature",
        ((82, 82, 82), (91, 91, 91)): "latest_error_sticky_signature",
        ((82, 0, 0), (91, 0, 0)): "latest_only_consuming_or_single_slot_signature",
        ((91, 0, 0), (82, 0, 0)): "first_only_consuming_or_single_slot_signature",
    }
    return dict(
        event_read_observation=event_result,
        error_selection_observation=signatures.get((tuple(ab), tuple(ba)), "inconclusive"),
        command_bit_reads=event,
        a_then_b_errors=ab,
        b_then_a_errors=ba,
        evidence_limit="Two fixed entry errors and three reads per group; no general queue or other event-bit claim",
    )


def _gate(rows, phase):
    status = _values(rows, phase, "SM")
    if len(status) != 2:
        return "status_pair_incomplete"
    final = status[-1]
    if (
        final["reference_on"]
        or final["operating_mode"] != 0
        or final["standby"]
        or final["measurement_error"]
        or final["entry_error"]
    ):
        return "source_or_active_error_not_clear_after_status_pair"
    if phase != "baseline":
        baseline = _values(rows, "baseline", "SM")[-1]
        preserved = (
            "logarithmic",
            "relative",
            "group_trigger",
            "limits_on",
            "offset_on",
            "duty_on",
        )
        if any(final[field] != baseline[field] for field in preserved):
            return "unexpected_measurement_configuration_change"
    if phase == "baseline":
        if any(s["measurement_error"] or s["entry_error"] for s in status):
            return "preexisting_status_error_preserved_no_error_injection_permitted"
        if _values(rows, phase, "*ESE?") != [0] or _values(rows, phase, "*SRE?") != [0]:
            return "nonzero_enable_mask_no_setter_or_error_injection_permitted"
        if _values(rows, phase, "ERR?") != [0, 0, 0]:
            return "preexisting_error_replies_preserved_no_error_injection_permitted"
        if any(value & 0x38 for value in _values(rows, phase, "*ESR?")):
            return "preexisting_error_event_bits_preserved_no_error_injection_permitted"
    elif phase == "event":
        values = _values(rows, phase, "*ESR?")
        if not values or not values[0] & 32:
            return "documented_command_error_event_not_observed"
    elif phase in ("single_a", "single_b"):
        expected = 91 if phase == "single_a" else 82
        if expected not in _values(rows, phase, "ERR?"):
            return "isolated_entry_error_not_observable_no_pair_inference_permitted"
    elif phase == "final":
        if _values(rows, phase, "*ESE?") != [0] or _values(rows, phase, "*SRE?") != [0]:
            return "enable_mask_changed"
    return None


def collect(instrument, rows, started, *, before_step, after_step, on_row, raw_reply):
    """Execute this fixed plan only, stopping on I/O failure or failed phase gate."""
    for phase in PHASES:
        for row in (item for item in rows if item["phase"] == phase):
            before_step(row["step_id"])
            row["started_elapsed_s"] = time.monotonic() - started
            try:
                if row["kind"] == "stimulus":
                    # Private diagnostic fixture only: never added to encode/command APIs.
                    payload = _STIMULI[row["command"]]
                    with instrument._operation() as deadline:
                        instrument._write(payload, deadline)
                    row["sent_hex"] = payload.hex()
                else:
                    reply = instrument.query(row["command"])
                    row.update(raw_hex=reply.raw.hex(), value=diag._value(reply.value))
                after_step()
            except BaseException as exc:
                row.update(
                    status="failed",
                    raw_hex=raw_reply().hex(),
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_s=time.monotonic() - started,
                )
                on_row(row)
                if not isinstance(exc, Exception):
                    raise
                return "query_failed", dict(stop_reason="transaction_failed", **assessment(rows))
            row.update(status="completed", elapsed_s=time.monotonic() - started)
            on_row(row)
        reason = _gate(rows, phase)
        if reason is not None:
            return "observation_stop", dict(
                stop_reason=reason, stopped_after_phase=phase, **assessment(rows)
            )
    return "completed", dict(stop_reason=None, **assessment(rows))
