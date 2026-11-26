"""One bounded supervised ZERO; no normal logging or general poll capability."""

import time

from . import diagnostics as diag
from .commands import encode
from .diagnostics_snapshot import _quiet
from .errors import OperationTimeout, ProtocolError, StateUncertain
from .serial_poll_probe import SerialPollProbe

COMPLETION_S = 30.0
GAP_S = 0.5
MAX_POLLS = 60
RESERVE_S = 8.0


class PollSession:
    """One run, increasing tags, sticky failure, no wrap or interrupt drain."""

    def __init__(self, interface, cancelled):
        self.interface, self.cancelled = interface, cancelled
        self.tag = 2
        self.failed = False
        self.receipt = None

    def poll(self, deadline):
        if self.failed or self.tag > 127:
            raise StateUncertain("ZERO poll session stopped; no retry/tag reuse")
        probe = SerialPollProbe(self.interface, cancelled=self.cancelled, tag=self.tag)
        self.tag += 1
        try:
            return probe._exchange(deadline)
        except BaseException:
            self.failed = True
            raise
        finally:
            self.receipt = probe.receipt


def plan(*, calibration_factor=None):
    prefix, action = ("cal", "CL") if calibration_factor is not None else ("zero", "ZE")
    if calibration_factor is not None:
        encode("CL", calibration_factor)
    return [
        dict(step_id=step, command=code, kind=kind, status="not_attempted")
        for step, code, kind in (
            ("before.SM", "SM", "query"),
            ("before.ESE", "*ESE?", "query"),
            ("before.SRE", "*SRE?", "query"),
            ("cache.consume", "POLL", "poll"),
            ("baseline.CS", "CS", "command"),
            ("baseline.poll", "POLL", "poll"),
            (f"{prefix}.start", action, "command"),
            (f"{prefix}.wait", "POLL_UNTIL_COMPLETE", "poll_window"),
            ("after.CS", "CS", "command"),
            ("after.poll", "POLL", "poll"),
            ("after.SM", "SM", "query"),
            ("after.TR1", "TR1", "acquisition"),
            ("final.SM", "SM", "query"),
        )
    ]


def assessment(reason="No worker receipt yet"):
    return dict(
        stop_reason=reason,
        accepted_full_case=False,
        zero_may_have_started=None,
        completion_indication_observed=False,
        clear_baseline_observed=False,
        post_clear_observed=False,
        zero_automation_qualified=False,
        evidence_limit="Supervised current-adapter ZERO only; firmware does not expose every bus error",
    )


def collect(
    instrument,
    wire,
    rows,
    started,
    *,
    deadline,
    before_step,
    after_step,
    on_row,
    stop,
    _calibration_factor=None,
    _followup=None,
):
    operation = "CAL" if _calibration_factor is not None else "ZERO"
    prefix = operation.lower()
    payload = encode("CL", _calibration_factor) if operation == "CAL" else b"ZE"
    reserve_s = 18.0 if operation == "CAL" else RESERVE_S
    started_key = f"{prefix}_may_have_started"
    result = assessment(None)
    if operation == "CAL":
        result = {k.replace("zero_", "cal_"): v for k, v in result.items()}
        result.update(
            reference_factor=payload[2:-2].decode(),
            reference_may_be_on=False,
            reference_restored_off_verified=False,
            evidence_limit="Supervised current-adapter CAL only; firmware does not expose every bus error",
        )
    result[started_key] = False
    baseline = None
    zero_deadline = None
    for row in rows:
        reason = None
        row.update(started_elapsed_s=time.monotonic() - started, io_attempted=False)
        step, kind, code = row["step_id"], row["kind"], row["command"]
        try:
            before_step(row["step_id"])
            if step == f"{prefix}.start":
                if deadline - time.monotonic() < COMPLETION_S + reserve_s:
                    reason = "insufficient_time_no_ZERO_started"
                else:
                    zero_deadline = time.monotonic() + COMPLETION_S
                    result[started_key] = True
                    if operation == "CAL":
                        result["reference_may_be_on"] = True
            if reason is None:
                row["io_attempted"] = True
                if kind == "command":
                    if code in ("ZE", "CL"):
                        # Do not expose ZE as a general command or lift its existing guard.
                        with instrument._operation() as operation_deadline:
                            instrument._write(payload, operation_deadline)
                    else:
                        instrument.command("CS")
                elif kind == "poll":
                    try:
                        value = wire.zero_poll(deadline, cancelled=stop.is_set)
                    finally:
                        row["poll_receipt"] = wire.zero_poll_receipt
                    row["value"] = value
                    byte = value["adapter_status_byte"]
                    if step == "cache.consume":
                        if byte not in (0, 2):
                            reason = "unexpected_cached_status_no_ZERO"
                    elif byte != 0:
                        raise ProtocolError("Completion/status not clear; no further commands")
                    elif step == "baseline.poll":
                        result["clear_baseline_observed"] = True
                    else:
                        result["post_clear_observed"] = True
                elif kind == "poll_window":
                    samples = []
                    row["value"] = dict(samples=samples)
                    for _number in range(MAX_POLLS):
                        after_step()
                        if time.monotonic() >= zero_deadline:
                            raise OperationTimeout(
                                f"{operation} completion deadline; no command retry"
                            )
                        try:
                            poll = wire.zero_poll(zero_deadline, cancelled=stop.is_set)
                        finally:
                            row["poll_receipt"] = wire.zero_poll_receipt
                        samples.append(
                            {
                                k: poll[k]
                                for k in (
                                    "tag",
                                    "adapter_status_byte",
                                    "capabilities_hex",
                                    "control_hex",
                                    "interrupt_hex",
                                )
                            }
                        )
                        after_step()
                        byte = poll["adapter_status_byte"]
                        if byte & 8:
                            raise ProtocolError(
                                f"{operation} measurement error; no further commands"
                            )
                        if byte not in (0, 2):
                            raise ProtocolError(
                                f"Unexpected {operation} status; no further commands"
                            )
                        if byte == 2:
                            result["completion_indication_observed"] = True
                            break
                        row["status"] = "running"
                        on_row(row)  # Bounded compact samples survive a later worker failure.
                        end = min(zero_deadline, time.monotonic() + GAP_S)
                        while time.monotonic() < end:
                            after_step()
                            time.sleep(min(0.02, max(0, end - time.monotonic())))
                    else:
                        raise OperationTimeout(f"{operation} poll-count limit; no further commands")
                elif kind == "acquisition":
                    m = (
                        _followup(instrument, wire, deadline, row)
                        if _followup is not None
                        else instrument.acquire("TR1")
                    )
                    row.update(
                        raw_hex=m.raw.hex(),
                        value=dict(
                            value=str(m.value) if m.value is not None else None,
                            unit=m.unit,
                            error_code=m.error_code,
                        ),
                    )
                    if m.error_code is not None:
                        reason = "post_ZERO_measurement_error"
                else:
                    reply = instrument.query(code)
                    row.update(raw_hex=reply.raw.hex(), value=diag._value(reply.value))
                    if code == "SM":
                        if not _quiet(reply.value, allow_standby=step in ("after.SM", "final.SM")):
                            reason = "nonquiet_status"
                        if baseline is None:
                            baseline = reply.value
                        elif any(
                            getattr(reply.value, k) != getattr(baseline, k)
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
                            reason = "interpretation_flags_changed"
                    elif reply.value != 0:
                        reason = "nonzero_mask_no_ZERO"
                after_step()
                if operation == "CAL" and step == "after.SM" and reason is None:
                    result["reference_may_be_on"] = False
                    result["reference_restored_off_verified"] = True
        except BaseException as exc:
            row.update(
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                elapsed_s=time.monotonic() - started,
            )
            if row["io_attempted"] and kind not in ("poll", "poll_window"):
                row["raw_hex"] = wire.captured_raw.hex()
            on_row(row)
            result["stop_reason"] = "failed_or_unknown_completion_no_further_commands"
            if not isinstance(exc, Exception):
                raise
            return "query_failed", result
        row.update(status="completed", elapsed_s=time.monotonic() - started)
        on_row(row)
        if reason:
            result["stop_reason"] = reason.replace("ZERO", operation)
            return "observation_stop", result
    return "completed", result
