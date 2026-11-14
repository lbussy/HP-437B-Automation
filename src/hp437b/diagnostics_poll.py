"""One supervised source-off USB488 poll; adapter evidence only, no procedure enablement."""

import time

from . import diagnostics as diag
from .diagnostics_snapshot import _quiet


def plan():
    return [
        dict(step_id=step, command=code, kind=kind, status="not_attempted")
        for step, code, kind in (
            ("before.SM", "SM", "query"),
            ("before.SRE", "*SRE?", "query"),
            ("before.STB", "*STB?", "query"),
            ("poll.once", "USB488_READ_STATUS_BYTE", "poll"),
            ("after.STB", "*STB?", "query"),
            ("after.TR1", "TR1", "acquisition"),
            ("after.SM", "SM", "query"),
        )
    ]


def assessment(reason=None):
    return dict(
        stop_reason=reason,
        accepted_full_case=False,
        instrument_poll_success_verified=False,
        freshness_verified=False,
        procedure_completion_verified=False,
        evidence_limit="Adapter can mask GPIB timeout and merge cached SRQ bits",
    )


def collect(instrument, wire, rows, started, *, deadline, before_step, after_step, on_row, stop):
    baseline = None
    for row in rows:
        row["started_elapsed_s"] = time.monotonic() - started
        row["io_attempted"] = False
        reason = None
        try:
            before_step(row["step_id"])
            row["io_attempted"] = True
            if row["kind"] == "poll":
                try:
                    row["value"] = wire.poll_once(deadline, cancelled=stop.is_set)
                finally:
                    row["poll_receipt"] = wire.poll_receipt
                if row["value"].get("status") != "adapter_reply_validated":
                    raise ValueError("Probe did not return validated USB framing")
            elif row["kind"] == "acquisition":
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
                    reason = "post_poll_measurement_error"
            else:
                reply = instrument.query(row["command"])
                row.update(raw_hex=reply.raw.hex(), value=diag._value(reply.value))
                if row["command"] == "SM":
                    if not _quiet(reply.value, allow_standby=baseline is not None):
                        reason = "source_or_operation_or_error_not_quiet"
                    if baseline is None:
                        baseline = reply.value
                    elif any(
                        getattr(reply.value, key) != getattr(baseline, key)
                        for key in (
                            "logarithmic",
                            "relative",
                            "unit",
                            "group_trigger",
                            "limits_on",
                            "offset_on",
                            "duty_on",
                        )
                    ):
                        reason = "observed_configuration_flags_changed"
                elif row["command"] == "*SRE?" and reply.value != 0:
                    reason = "nonzero_service_mask_no_poll_no_mask_change"
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
            return "query_failed", assessment("transaction_failed_no_followup")
        row.update(status="completed", elapsed_s=time.monotonic() - started)
        on_row(row)
        if reason:
            return "observation_stop", assessment(reason)
    return "completed", assessment()
