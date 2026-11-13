"""Report-only publication from sealed operator POWER REF captures; no acquisition."""

import fcntl
from pathlib import Path

from . import provenance as p
from . import reference_report, reference_suite
from . import reporting as r


def inspect(path, request):
    """Validate the selected capture with its owning reader, including partial results."""
    source = Path(path) / "capture"
    p.require(
        source.is_dir() and not source.is_symlink(), "Sealed capture directory missing or symlinked"
    )
    mode = request.get("mode")
    if mode == "reference_suite":
        record, _, _ = reference_suite.load(source)
        p.require(record["mode"] == request["meter_mode"], "Saved suite mode mismatch")
        p.require(record["workflows"] == request["workflows"], "Saved selection mismatch")
    else:
        p.require(mode == "physical", "Select an individual or combined POWER REF capture")
        p.require(len(request["workflows"]) == 1, "Invalid individual workflow selection")
        record, _, _ = reference_report.load(source, request["workflows"][0])
    return r.digest((source / "artifacts.json").read_bytes())


def publish(source_job, output, source_request, expected_hash, *, plots):
    """Hold the source capture guard and publish into a new, non-overwriting destination."""
    source_job, output = Path(source_job), Path(output)
    lock = source_job / ".capture.lock"
    p.require(not lock.is_symlink(), "Symlink capture lock is unsupported")
    with lock.open("a+b") as guard:
        try:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("The capture worker still owns this run; wait for closure") from None
        p.require(inspect(source_job, source_request) == expected_hash, "Source capture changed")
        source = source_job / "capture"
        if source_request["mode"] == "reference_suite":
            result = reference_suite.publish(source, output, plots=plots)
        else:
            result = reference_report.publish(
                source, output, source_request["workflows"][0], plots=plots
            )
        p.require(inspect(source_job, source_request) == expected_hash, "Source capture changed")
        return result
