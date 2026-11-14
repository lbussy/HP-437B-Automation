"""CAL variant of the accepted bounded ZERO completion path."""

from . import diagnostics_zero as zero
from .commands import encode
from .errors import OperationTimeout, ProtocolError
from .transport import remaining

READ_S = 10.0
CLEANUP_RESERVE_S = 6.0
WORK_S = 35
TOTAL_S = 40


def factor_text(value):
    """Use the existing exact 50.0..120.0/0.1 CL encoder; never guess a factor."""
    return encode("CL", value)[2:-2].decode("ascii")


def plan(reference_factor):
    return zero.plan(calibration_factor=factor_text(reference_factor))


def assessment(reason="No worker receipt yet"):
    result = {k.replace("zero_", "cal_"): v for k, v in zero.assessment(reason).items()}
    result.update(
        reference_may_be_on=True,
        reference_restored_off_verified=False,
        evidence_limit="Supervised current-adapter CAL only; firmware does not expose every bus error",
    )
    return result


def collect(instrument, wire, rows, started, *, reference_factor, **kwargs):
    return zero.collect(
        instrument,
        wire,
        rows,
        started,
        _calibration_factor=factor_text(reference_factor),
        _followup=_followup,
        **kwargs,
    )


def _followup(instrument, wire, deadline, row):
    """One full read window, without changing the two-second write/control cap."""
    wire.last_write_complete = False
    wire.read_started = False
    if remaining(deadline) < READ_S + CLEANUP_RESERVE_S:
        raise OperationTimeout("No time for CAL followup and cleanup; TR1 not sent")
    old_timeout = instrument.timeout
    instrument.timeout = READ_S
    wire.cal_read_timeout_s = READ_S
    row["read_timeout_s"] = READ_S
    try:
        return instrument.acquire("TR1")
    finally:
        instrument.timeout = old_timeout
        wire.cal_read_timeout_s = None


def failed_read_shutdown(wire, rows, assessment, *, deadline, stage):
    """Dispose a failed measurement session after known CAL; never reuse its stream."""
    eligible = (
        all(
            assessment.get(k) is True
            for k in (
                "clear_baseline_observed",
                "completion_indication_observed",
                "post_clear_observed",
                "reference_restored_off_verified",
            )
        )
        and assessment.get("reference_may_be_on") is False
        and any(r["step_id"] == "after.TR1" and r["status"] == "failed" for r in rows)
        and wire.last_write_complete
        and wire.read_started
    )
    if not eligible:
        return None
    result = dict(status="failed", disposal_only=True, free_run=None, local_return=None)
    # No query, retry, uncertainty acknowledgement, or use of Instrument after failure.
    # TR3 intentionally abandons only the failed trigger, never an unfinished CAL.
    try:
        stage("failed_read_free_run")
        wire.write(b"TR3", deadline)
        result["free_run"] = "accepted"
    except Exception as exc:
        result.update(free_run="failed", free_run_error=f"{type(exc).__name__}: {exc}")
    try:
        stage("failed_read_local_return")
        local = wire.return_local(deadline)
        if not isinstance(local, dict) or local.get("status") != "accepted":
            raise ProtocolError("CAL failed-read local return was not accepted")
        result["local_return"] = local
    except Exception as exc:
        result["local_error"] = f"{type(exc).__name__}: {exc}"
    if result["free_run"] == "accepted" and result["local_return"] is not None:
        result["status"] = "accepted"
    return result
