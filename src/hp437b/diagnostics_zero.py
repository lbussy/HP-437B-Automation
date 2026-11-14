"""One bounded supervised ZERO; no normal logging or general poll capability."""

import time

from . import diagnostics as diag
from .diagnostics_snapshot import _quiet
from .errors import OperationTimeout, ProtocolError, StateUncertain
from .serial_poll_probe import SerialPollProbe

ZERO_S = 30.0
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


def plan():
    return [
        dict(step_id=step, command=code, kind=kind, status="not_attempted")
        for step, code, kind in (
            ("before.SM", "SM", "query"),
            ("before.ESE", "*ESE?", "query"),
            ("before.SRE", "*SRE?", "query"),
            ("cache.consume", "POLL", "poll"),
            ("baseline.CS", "CS", "command"),
            ("baseline.poll", "POLL", "poll"),
            ("zero.start", "ZE", "command"),
            ("zero.wait", "POLL_UNTIL_COMPLETE", "poll_window"),
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


def collect(instrument, wire, rows, started, *, deadline, before_step, after_step, on_row, stop):
    result = assessment(None)
    result["zero_may_have_started"] = False
    baseline = None
    zero_deadline = None
    for row in rows:
        reason = None
        row.update(started_elapsed_s=time.monotonic() - started, io_attempted=False)
        step, kind, code = row["step_id"], row["kind"], row["command"]
        try:
            before_step(row["step_id"])
            if step == "zero.start":
                if deadline - time.monotonic() < ZERO_S + RESERVE_S:
                    reason = "insufficient_time_no_ZERO_started"
                else:
                    zero_deadline = time.monotonic() + ZERO_S
                    result["zero_may_have_started"] = True
            if reason is None:
                row["io_attempted"] = True
                if kind == "command":
                    if code == "ZE":
                        # Do not expose ZE as a general command or lift its existing guard.
                        with instrument._operation() as operation_deadline:
                            instrument._write(b"ZE", operation_deadline)
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
                            raise OperationTimeout("ZERO completion deadline; no command retry")
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
                            raise ProtocolError("ZERO measurement error; no further commands")
                        if byte not in (0, 2):
                            raise ProtocolError("Unexpected ZERO status; no further commands")
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
                        raise OperationTimeout("ZERO poll-count limit; no further commands")
                elif kind == "acquisition":
                    m = instrument.acquire("TR1")
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
            result["stop_reason"] = reason
            return "observation_stop", result
    return "completed", result
