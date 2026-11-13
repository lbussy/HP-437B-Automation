"""Explicit checkout-backed POWER REF execution; ordinary logging is untouched."""

import argparse
import fcntl
import os
import signal
import subprocess
from contextlib import contextmanager
from pathlib import Path
from runpy import run_path

from . import provenance as p
from . import reference_report as reports

SCRIPTS = {
    "WF-01": "run_power_reference.py",
    "WF-02": "run_stability_reference.py",
    "WF-03": "run_cycle_reference.py",
}
PREPARED = (
    "adapter_on_mac",
    "direct_sensor_reference_path",
    "reference_off",
    "warmed_up",
    "other_apps_closed",
    "operator_available",
)


def configuration(root, setup, resource, python):
    root, setup, python = Path(root).resolve(), Path(setup).resolve(), Path(python).absolute()
    p.require(
        all((root / "tools" / name).is_file() for name in SCRIPTS.values()),
        "POWER REF requires the trusted source checkout with existing runners",
    )
    p.require(python.is_file() and os.access(python, os.X_OK), "Bench Python is unavailable")
    p.require(setup.stat().st_size <= 256 * 1024, "Setup exceeds limit")
    document = p._json(setup.read_bytes())
    # Preparation booleans in old records are not authorization for a new run.
    candidate = {**document, **dict.fromkeys(PREPARED, True)}
    run_path(str(root / "tools" / SCRIPTS["WF-01"]))["validate_setup"](resource, candidate, True)
    p.require(
        all(isinstance(note, str) for note in document["known_issues"]), "Invalid known-issues list"
    )
    return dict(root=str(root), setup=document, resource=resource, python=str(python))


def capture(path, request, *, module=None, options=None):
    """Run the existing execute() with cancellation only before a new stage."""
    config, kind = request["reference_config"], request["workflows"][0]
    module = module or run_path(str(Path(config["root"]) / "tools" / SCRIPTS[kind]))
    with observing(module, path):
        return module["execute"](
            path / "capture",
            config["resource"],
            request["prepared_setup"],
            confirmed=True,
            **(options or {}),
        )


@contextmanager
def observing(module, path):
    original = module["execute"].__globals__["Controller"]

    class Observed(original):
        def begin(self, *args, **kwargs):
            super().begin(*args, **kwargs)
            if not kwargs.get("cleanup") and (path / "cancel.requested").exists():
                raise KeyboardInterrupt(
                    "Operator requested cancellation at a completed stage boundary"
                )

    module["execute"].__globals__["Controller"] = Observed
    try:
        yield
    finally:
        module["execute"].__globals__["Controller"] = original


def supervise(path, request, *, lock_fd=None, extra_fds=()):
    config = request["reference_config"]
    limit = 2100 if request["workflows"] == ["WF-02"] else 900
    command = [config["python"], "-m", "hp437b.operator_reference", "--child", "--job", str(path)]
    with (
        (path / ".capture.lock").open("a+b") as guard,
        (path / "capture-worker.log").open("xb") as log,
    ):
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        child = subprocess.Popen(
            command,
            cwd=config["root"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            pass_fds=(guard.fileno(),) + (() if lock_fd is None else (lock_fd,)) + extra_fds,
        )
        try:
            try:
                code = child.wait(timeout=limit - 30)
            except subprocess.TimeoutExpired:
                child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=28)
                except subprocess.TimeoutExpired:
                    pass
                raise RuntimeError(
                    "POWER REF outer deadline: reconcile reference/local state; no automatic retry"
                ) from None
            p.require(
                code == 0,
                "POWER REF capture failed to seal; inspect saved checkpoint and source/local state",
            )
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)


def run(path, request, emit, *, lock_fd=None):
    kind = request["workflows"][0]
    emit(phase="running", current=kind, index=1)
    supervise(path, request, lock_fd=lock_fd)
    record, result, _ = reports.load(path / "capture", kind)
    emit(
        phase="reporting",
        current=None,
        outcome=record["status"],
        final_state=record["final_state"],
        acceptance="NOT EVALUATED",
        results=[
            dict(
                workflow=kind,
                execution=record["status"],
                acceptance="NOT EVALUATED",
                completed_points=1 if record["status"] == "completed" else 0,
                requested_points=1,
            )
        ],
    )
    reports.publish(
        path / "capture",
        path / "report",
        kind,
        plots=request["plots"],
        operator=request["operator"],
    )
    emit(phase="finished", error=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true", required=True)
    parser.add_argument("--job", type=Path, required=True)
    args = parser.parse_args()
    request = p._json((args.job / "request.json").read_bytes())
    capture(args.job, request)


if __name__ == "__main__":
    main()
