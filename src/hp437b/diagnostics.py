"""Fake-first explicit diagnostics; no physical discovery or normal logger hook."""

import math
import time
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path

from .errors import TransportError
from .instrument import Instrument
from .logger import _atomic_json
from .simulation import status_fixture
from .transport import remaining

# Keep reads with known/uncertain latch effects out of the default sequence.
BASIC_QUERIES = ("*ESE?", "*SRE?", "*STB?", "OD")
LATCHED_QUERIES = ("ERR?", "*ESR?", "SM")
EFFECTS = {
    "*ESE?": "Read event-enable mask; no mask setter is sent.",
    "*SRE?": "Read service-request mask; no mask setter is sent.",
    "*STB?": "ASCII status query; documented not to clear the status byte; not serial polling.",
    "OD": "Read current display text; not a fresh measurement or numeric power sample.",
    "ERR?": "Error selection/lifecycle is unresolved (A06); preserve the reply before other reads.",
    "*ESR?": "Event-read clearing behavior needs bench evidence (A06); do not assume neutral.",
    "SM": "May clear resolved error latches; updates after measurement; may be stale here.",
}
_FAULTS = frozenset({"malformed_reply", "read_error", "late_reply"})
_SCENARIOS = _FAULTS | {"healthy", "instrument_errors", "cleanup_error", "source_on"}


class _FakeWire:
    """Fixed fixtures, not a model of meter error queues or status lifecycle."""

    capabilities = frozenset({"read", "write", "eom", "go_to_local"})

    def __init__(self, scenario, fault_at):
        self.scenario, self.fault_at = scenario, fault_at
        self.pending = None
        self.closed = False
        self.trace = []

    def write(self, data, deadline):
        remaining(deadline)
        if self.closed or self.pending is not None:
            raise TransportError("Invalid fake session state")
        code = data.decode("ascii")
        if code not in EFFECTS and code != "TR3":
            raise ValueError("Fake diagnostics rejects commands outside its fixed plan/cleanup")
        self.trace.append({"operation": "write", "command": code})
        if code != "TR3":
            self.pending = code

    def read(self, deadline):
        remaining(deadline)
        code, self.pending = self.pending, None
        if self.closed or code not in EFFECTS:
            raise TransportError("No fake query reply pending")
        if code == self.fault_at and self.scenario == "read_error":
            self.trace.append({"operation": "read_error", "command": code})
            raise TransportError("Simulated read failure")
        replies = {
            "*ESE?": b"000\r\n",
            "*SRE?": b"000\r\n",
            "*STB?": b"000\r\n",
            "OD": b"-0.050 uW\r\n",
            "ERR?": b"000\r\n",
            "*ESR?": b"000\r\n",
            "SM": status_fixture(logarithmic=False),
        }
        if self.scenario == "instrument_errors":
            replies.update({"*STB?": b"012\r\n", "ERR?": b"091\r\n", "*ESR?": b"032\r\n"})
            status = bytearray(replies["SM"])
            status[:4] = b"0191"
            replies["SM"] = bytes(status)
        if self.scenario == "source_on":
            status = bytearray(replies["SM"])
            status[16] = ord("1")
            replies["SM"] = bytes(status)
        raw = replies[code]
        if code == self.fault_at:
            if self.scenario == "malformed_reply":
                raw = b"\xffBROKEN\r\n"
            elif self.scenario == "late_reply":
                time.sleep(max(0, deadline - time.monotonic()) + 0.002)
        self.trace.append({"operation": "read", "command": code, "raw_hex": raw.hex()})
        return raw

    def return_local(self, deadline):
        remaining(deadline)
        self.trace.append({"operation": "go_to_local"})
        if self.scenario == "cleanup_error":
            raise TransportError("Simulated Go To Local failure")

    def close(self):
        self.trace.append({"operation": "close"})
        self.closed = True


def _value(value):
    if is_dataclass(value):
        result = asdict(value)
        result.pop("raw", None)  # Retained separately without decoding/reformatting.
        return result
    return value


def _collect_queries(
    instrument,
    rows,
    started,
    *,
    before_query=lambda code: None,
    after_query=lambda: None,
    on_row=lambda row: None,
    raw_reply=None,
):
    """Shared fixed-plan collection; callers own transport, deadlines, and cleanup."""
    for row in rows:
        before_query(row["command"])
        row["started_elapsed_s"] = time.monotonic() - started
        try:
            reply = instrument.query(row["command"])
            after_query()
        except BaseException as exc:
            raw = raw_reply() if raw_reply is not None else instrument.last_raw
            row.update(
                status="failed" if isinstance(exc, Exception) else "interrupted",
                raw_hex=raw.hex(),
                error=f"{type(exc).__name__}: {exc}",
                elapsed_s=time.monotonic() - started,
            )
            on_row(row)
            if not isinstance(exc, Exception):
                raise
            return "query_failed"
        row.update(
            status="completed",
            raw_hex=reply.raw.hex(),
            value=_value(reply.value),
            elapsed_s=time.monotonic() - started,
        )
        on_row(row)
    return "completed"


def run_simulated(
    output,
    *,
    include_latched_reads=False,
    scenario="healthy",
    fault_at=None,
    timeout_s=0.25,
):
    """Reserve a new directory and run one finite fake-only diagnostic sequence.

    There is deliberately no resource, transport factory, or hardware mode.
    Successful query collection is not an instrument-health verdict. Fixed
    fixtures exercise the existing Instrument API and its uncertainty/close rules.
    """
    if type(include_latched_reads) is not bool:
        raise ValueError("include_latched_reads must be an explicit boolean")
    if not isinstance(scenario, str) or scenario not in _SCENARIOS:
        raise ValueError("Choose a documented fake scenario")
    if (
        isinstance(timeout_s, bool)
        or not isinstance(timeout_s, (int, float))
        or not math.isfinite(timeout_s)
        or not 0.01 <= timeout_s <= 5
    ):
        raise ValueError("timeout_s must be finite in 0.01..5 seconds")
    plan = BASIC_QUERIES + (LATCHED_QUERIES if include_latched_reads else ())
    if scenario in _FAULTS:
        fault_at = "*SRE?" if fault_at is None else fault_at
        if fault_at not in plan:
            raise ValueError("fault_at must be a query included in this batch")
    elif fault_at is not None:
        raise ValueError("fault_at applies only to fake read-failure scenarios")
    if scenario == "source_on" and not include_latched_reads:
        raise ValueError("source_on needs the explicitly selected SM read")
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    wire = _FakeWire(scenario, fault_at)
    instrument = Instrument(wire, timeout=timeout_s)
    receipt = {
        "schema": "hp437b.diagnostics.v1",
        "evidence": "simulated",
        "hardware_access": False,
        "started_utc": datetime.now(UTC).isoformat(),
        "scenario": scenario,
        "fault_at": fault_at,
        "include_latched_reads": include_latched_reads,
        "operation_timeout_s": timeout_s,
        "status": "running",
        "health_verdict": "Not evaluated; diagnostic replies only",
        "front_panel_confirmation": "Not applicable; simulated",
        "queries": [
            {"command": code, "effect": EFFECTS[code], "status": "not_attempted"} for code in plan
        ],
        "limitations": [
            "Fixed fixtures do not establish physical framing or latch/queue behavior.",
            "OD/SM do not establish a fresh power reading or source-off state.",
            "No retry, reconciliation, register clear, setter, zero, CAL, or source switching.",
            "Existing healthy cleanup sends TR3/GTL; uncertain sessions only close.",
        ],
    }
    started = time.monotonic()
    try:
        receipt["status"] = _collect_queries(instrument, receipt["queries"], started)
    except BaseException:
        receipt["status"] = "interrupted"
        raise
    finally:
        try:
            instrument.close()
        except BaseException as exc:
            receipt["cleanup_error"] = f"{type(exc).__name__}: {exc}"
            if not isinstance(exc, Exception):
                receipt["status"] = "interrupted"
                raise
            if receipt["status"] == "completed":
                receipt["status"] = "cleanup_failed"
        finally:
            receipt.update(
                finished_utc=datetime.now(UTC).isoformat(),
                elapsed_s=time.monotonic() - started,
                cleanup=instrument.cleanup,
                transport_closed=wire.closed,
                trace=wire.trace,
            )
            _atomic_json(path / "diagnostics.json", receipt)
    return receipt
