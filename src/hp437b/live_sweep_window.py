"""Bound meter acquisitions to an observed owner-controlled finite RF window."""

import threading
import time
from dataclasses import dataclass
from typing import Protocol

from . import provenance as p
from .live_sweep_review import Point, Target, Timing


@dataclass(frozen=True)
class Job:
    target_id: str
    device_id: str
    boot_id: str
    job_id: str


@dataclass(frozen=True)
class Observation:
    job: Job
    observed_ns: int
    active: bool
    output_inactive: bool
    carrier_hz: int | None
    drive_ma: int | None


class Output(Protocol):
    """Supply fresh observations. Identified stop must have independent bounded I/O."""

    def observe(self, job: Job, deadline_ns: int) -> Observation: ...

    def stop(self, job: Job, deadline_ns: int) -> Observation: ...


@dataclass(frozen=True)
class Bracket:
    before: Observation
    read_started_ns: int
    read_finished_ns: int
    after: Observation


class ActiveWindow:
    """Own stop independently of VISA and poll a non-blocking cancellation signal."""

    def __init__(
        self,
        output: Output,
        target: Target,
        point: Point,
        job: Job,
        timing: Timing,
        hard_end_ns: int,
        cancelled,
        *,
        retry_observation_timeout=False,
        clock=time.monotonic_ns,
    ):
        p.require(
            (job.target_id, job.device_id, job.boot_id)
            == (target.target_id, target.device_id, target.boot_id)
            and bool(job.job_id),
            "RF job does not belong to the reviewed source and boot",
        )
        p.require(
            type(hard_end_ns) is int and 0 <= hard_end_ns <= clock() + timing.tone_ms * 1_000_000,
            "Require the fixed, reviewed finite tone deadline",
        )
        self.output, self.point, self.job = output, point, job
        self.timing, self.hard_end_ns = timing, hard_end_ns
        self.stop_by_ns = hard_end_ns - timing.stop_ms * 1_000_000
        self.cancelled, self.clock = cancelled, clock
        self.retry_observation_timeout = retry_observation_timeout
        self._requested = threading.Event()
        self._closing = threading.Event()
        self._worker = threading.Thread(target=self._watch, daemon=True)
        self.stop_observation = None
        self.stop_error = None

    def __enter__(self):
        self._worker.start()
        return self

    def __exit__(self, exc_type, error, traceback):
        self.request_stop()
        self._worker.join(max(0, (self.hard_end_ns - self.clock()) / 1_000_000_000))
        if self.stop_observation is None:
            raise ValueError(
                "RF shutdown is unknown for this job; reconcile before another Start"
            ) from error

    def request_stop(self):
        self._closing.set()
        self._requested.set()

    def _watch(self):
        while not self._requested.is_set():
            until_stop = (self.stop_by_ns - self.clock()) / 1_000_000_000
            try:
                cancelled = self.cancelled()
            except Exception:
                cancelled = True
            if cancelled or until_stop <= 0:
                break
            self._requested.wait(min(0.02, until_stop))
        self._closing.set()
        try:
            started = self.clock()
            event = self.output.stop(self.job, self.hard_end_ns)
            self._check_receipt(event, started, self.hard_end_ns)
            p.require(
                event.active is False and event.output_inactive is True,
                "The owner did not verify RF inactivity",
            )
            self.stop_observation = event
        except Exception as exc:
            self.stop_error = type(exc).__name__

    def _check_receipt(self, event, issued_ns, deadline_ns):
        p.require(
            isinstance(event, Observation)
            and event.job == self.job
            and type(event.observed_ns) is int
            and issued_ns <= event.observed_ns <= self.clock() <= deadline_ns,
            "Missing a fresh, timely observation for the identified RF job",
        )

    def observe(self, deadline_ns):
        self._require_open()
        deadline_ns = min(deadline_ns, self.stop_by_ns)
        issued = self.clock()
        try:
            observed = self.output.observe(self.job, deadline_ns)
        except TimeoutError:
            if not self.retry_observation_timeout or self.clock() >= deadline_ns:
                raise
            # Retry only the read-only status for this exact job. Keep the
            # original read deadline and give cancellation/Stop precedence.
            self._require_open()
            issued = self.clock()
            observed = self.output.observe(self.job, deadline_ns)
        self._check_receipt(observed, issued, deadline_ns)
        return observed

    def _active(self, deadline_ns):
        observed = self.observe(deadline_ns)
        p.require(
            observed.active is True
            and observed.output_inactive is False
            and type(observed.carrier_hz) is int
            and type(observed.drive_ma) is int
            and observed.carrier_hz == self.point.carrier_hz
            and observed.drive_ma == self.point.drive_ma,
            "Source did not confirm the accepted carrier and effective drive",
        )
        return observed

    def read(self, acquire, *, final=False):
        """Return a meter reply and its source bracket, or stop upon ambiguity.

        The caller supplies a bounded TR2/status operation. A successful final
        read schedules stop before the caller performs logger or meter cleanup.
        """
        try:
            self._require_open()
            budget_start = self.clock()
            self.timing.require_read_window(budget_start, self.hard_end_ns)
            read_end = budget_start + self.timing.read_ms * 1_000_000
            before = self._active(read_end)
            self._require_open()
            started = self.clock()
            p.require(started < read_end, "The reviewed read budget expired before TR2")
            result = acquire(read_end)
            finished = self.clock()
            self._require_open()
            p.require(finished <= read_end, "Meter acquisition exceeded the reviewed read limit")
            after = self._active(read_end)
            self._require_open()
            return result, Bracket(before, started, finished, after)
        except BaseException:
            self.request_stop()
            raise
        finally:
            if final:
                self.request_stop()

    def _require_open(self):
        if self.cancelled():
            raise KeyboardInterrupt("Automatic point cancelled")
        p.require(not self._closing.is_set(), "The RF window is closing")
        p.require(self._worker.is_alive(), "Enter the active RF window before acquiring")
