"""Fixed invalid-frequency/entry-bit poll experiment; no valid numeric setters."""

import time

from . import diagnostics as diag
from .diagnostics_poll import assessment as base_assessment
from .diagnostics_snapshot import _quiet


def plan():
    phases = (
        ("baseline", "query", ("SM", "*ESE?", "*SRE?", "*ESR?", "*ESR?", "*STB?")),
        ("stimulus", "stimulus", ("FR-3GZ",)),
        ("before", "query", ("*STB?", "*STB?")),
        ("poll", "poll", ("USB488_READ_STATUS_BYTE",)),
        ("after", "query", ("*STB?", "*STB?")),
        ("cleanup", "query", ("SM", "SM", "*ESR?", "*ESR?", "*STB?", "*ESE?", "*SRE?")),
        ("acquisition", "acquisition", ("TR1",)),
        ("final", "query", ("SM",)),
    )
    rows = []
    for phase, kind, codes in phases:
        for number, code in enumerate(codes):
            row = dict(
                step_id=f"{phase}.{number}.{code}",
                phase=phase,
                kind=kind,
                command=code,
                status="not_attempted",
            )
            if kind == "stimulus":
                row["fixture_hex"] = b"FR-3GZ".hex()
            rows.append(row)
    return rows


def values(rows, phase, command):
    return [
        r["value"]
        for r in rows
        if r["phase"] == phase and r["command"] == command and r["status"] == "completed"
    ]


def assessment(rows, reason=None, fixture_attempted=False, cleanup_verified=False):
    polls = values(rows, "poll", "USB488_READ_STATUS_BYTE")
    before, after = values(rows, "before", "*STB?"), values(rows, "after", "*STB?")
    positive = bool(polls and polls[0].get("adapter_status_byte", 0) & 4)
    observation = "not_observed"
    if positive and len(after) == 2:
        bits = tuple(bool(v & 4) for v in after)
        observation = {
            (False, False): "entry_bit_absent_on_both_post_poll_ASCII_reads",
            (True, True): "entry_bit_present_on_both_post_poll_ASCII_reads",
            (True, False): "entry_bit_present_then_absent_after_poll",
            (False, True): "entry_bit_absent_then_present_after_poll",
        }[bits]
    return dict(
        **base_assessment(reason),
        fixture_attempted=fixture_attempted,
        nonzero_entry_poll_observed=positive,
        before_status_bytes=before,
        after_status_bytes=after,
        entry_bit_observation=observation,
        quiet_cleanup_verified=cleanup_verified,
        numeric_settings_verified=False,
        evidence_scope="One fixed entry-error stimulus; no cal/zero completion or general poll lifecycle proof",
    )


def collect(instrument, wire, rows, started, *, deadline, before_step, after_step, on_row, stop):
    reason = None
    skip_main = fixture_attempted = cleanup_verified = False
    baseline = None
    cleanup_started = False
    for row in rows:
        cleanup = row["phase"] in ("cleanup", "acquisition", "final")
        if skip_main and not cleanup:
            continue
        if cleanup and not fixture_attempted:
            break
        cleanup_started |= cleanup
        row.update(started_elapsed_s=time.monotonic() - started, io_attempted=False)
        mismatch = None
        abort_cleanup = False
        try:
            before_step(row["step_id"])
            code, phase, kind = row["command"], row["phase"], row["kind"]
            row["io_attempted"] = True
            if kind == "stimulus":
                fixture_attempted = True  # Partial write can still have taken effect.
                with instrument._operation() as operation_deadline:
                    instrument._write(b"FR-3GZ", operation_deadline)
                row["sent_hex"] = b"FR-3GZ".hex()
            elif kind == "poll":
                try:
                    row["value"] = wire.poll_once(deadline, cancelled=stop.is_set)
                finally:
                    row["poll_receipt"] = wire.poll_receipt
                if row["value"].get("status") != "adapter_reply_validated":
                    raise ValueError("Probe did not return validated USB framing")
                if not row["value"]["adapter_status_byte"] & 4:
                    mismatch = "entry_bit_not_observed_in_native_poll"
            elif kind == "acquisition":
                measured = instrument.acquire("TR1")
                row.update(
                    raw_hex=measured.raw.hex(),
                    value=dict(
                        value=str(measured.value) if measured.value is not None else None,
                        unit=measured.unit,
                        error_code=measured.error_code,
                    ),
                )
                if measured.error_code is not None:
                    mismatch, abort_cleanup = "post_cleanup_measurement_error", True
            else:
                reply = instrument.query(code)
                value = reply.value
                row.update(raw_hex=reply.raw.hex(), value=diag._value(value))
                if code == "SM":
                    if baseline is None:
                        baseline = value
                        if not _quiet(value):
                            mismatch = "nonquiet_baseline_no_stimulus"
                    else:
                        allowed_entry = (0, 82) if row["step_id"] == "cleanup.0.SM" else (0,)
                        if (
                            value.reference_on
                            or value.operating_mode
                            or value.measurement_error
                            or value.entry_error not in allowed_entry
                            or (value.standby and phase != "final")
                        ):
                            mismatch, abort_cleanup = "nonquiet_cleanup_status", True
                        if any(
                            getattr(value, k) != getattr(baseline, k)
                            for k in (
                                "logarithmic",
                                "relative",
                                "unit",
                                "group_trigger",
                                "limits_on",
                                "offset_on",
                                "duty_on",
                            )
                        ):
                            mismatch, abort_cleanup = "observed_configuration_flags_changed", True
                elif code in ("*ESE?", "*SRE?") and value != 0:
                    mismatch = "nonzero_mask_no_mask_change"
                    abort_cleanup = cleanup
                elif phase == "baseline" and code == "*ESR?":
                    allowed = (0, 128) if row["step_id"] == "baseline.3.*ESR?" else (0,)
                    if value not in allowed:
                        mismatch = "preexisting_or_persistent_event_no_stimulus"
                elif phase == "baseline" and code == "*STB?" and value != 0:
                    mismatch = "nonzero_baseline_status_no_stimulus"
                elif phase == "before" and value != 4:
                    mismatch = "isolated_entry_bit_not_preserved_before_poll"
                elif phase == "after" and value not in (0, 4):
                    mismatch = "unexpected_post_poll_status_bits"
                elif phase == "cleanup" and code == "*ESR?":
                    expected = 16 if row["step_id"] == "cleanup.2.*ESR?" else 0
                    if value != expected:
                        mismatch = "execution_event_or_read_clear_not_observed"
                        abort_cleanup = value != 0 and expected == 0
                elif phase == "cleanup" and code == "*STB?" and value != 0:
                    mismatch, abort_cleanup = "status_not_quiet_after_SM_event_reads", True
            after_step()
        except BaseException as exc:
            row.update(
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                elapsed_s=time.monotonic() - started,
            )
            if row["io_attempted"] and row["kind"] != "poll":
                row["raw_hex"] = wire.captured_raw.hex()
            on_row(row)
            if not isinstance(exc, Exception):
                raise
            return "query_failed", assessment(
                rows, "transaction_failed_no_further_commands", fixture_attempted
            )
        row.update(status="completed", elapsed_s=time.monotonic() - started)
        on_row(row)
        if mismatch:
            reason = reason or mismatch
            if not cleanup_started and phase in ("baseline", "before"):
                skip_main = True
            if cleanup and abort_cleanup:
                break
        if row["phase"] == "final" and mismatch is None:
            cleanup_verified = True
    return ("observation_stop" if reason else "completed"), assessment(
        rows, reason, fixture_attempted, cleanup_verified
    )
