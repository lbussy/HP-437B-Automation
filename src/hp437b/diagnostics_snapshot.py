"""Opaque LP2 capture and one post-read acquisition; no configuration restore."""

import hashlib
import time

from . import diagnostics as diag


def plan():
    return [
        dict(step_id=step, command=code, kind=kind, status="not_attempted")
        for step, code, kind in (
            ("before.SM", "SM", "query"),
            ("snapshot.LP2", "LP2", "query"),
            ("after.TR1", "TR1", "acquisition"),
            ("after.SM", "SM", "query"),
        )
    ]


def _quiet(status, *, allow_standby=False):
    return not (
        status.reference_on
        or (status.standby and not allow_standby)
        or status.operating_mode
        or status.measurement_error
        or status.entry_error
    )


def collect(instrument, rows, started, *, before_step, after_step, on_row, raw_reply):
    baseline = None
    for row in rows:
        before_step(row["step_id"])
        row["started_elapsed_s"] = time.monotonic() - started
        reason = None
        try:
            if row["command"] == "TR1":
                measurement = instrument.acquire("TR1")
                row.update(
                    raw_hex=measurement.raw.hex(),
                    value=dict(
                        value=str(measurement.value) if measurement.value is not None else None,
                        unit=measurement.unit,
                        error_code=measurement.error_code,
                    ),
                )
                if measurement.error_code is not None:
                    reason = "post_snapshot_measurement_error"
            else:
                reply = instrument.query(row["command"])
                row["raw_hex"] = reply.raw.hex()
                if row["command"] == "LP2":
                    row["value"] = dict(
                        length=len(reply.raw),
                        sha256=hashlib.sha256(reply.raw).hexdigest(),
                        interpretation="opaque; no settings decoded or restore supported",
                    )
                else:
                    row["value"] = diag._value(reply.value)
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
            return "query_failed", dict(
                stop_reason="transaction_failed", interpretation="opaque_only"
            )
        row.update(status="completed", elapsed_s=time.monotonic() - started)
        on_row(row)
        if reason:
            return "observation_stop", dict(stop_reason=reason, interpretation="opaque_only")
    return "completed", dict(stop_reason=None, interpretation="opaque_only")
