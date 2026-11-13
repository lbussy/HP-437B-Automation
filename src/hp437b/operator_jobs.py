"""Single-user fake job supervision; UI state is not measurement evidence."""

import fcntl
import importlib.util
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from . import pdf_reports
from . import provenance as p
from . import report_delivery as delivery
from . import reporting as r
from . import test_profiles as profiles
from . import test_suite as suite

ACTIVE = ("starting", "running", "reporting")
ID = re.compile(r"[0-9a-f]{32}")


def atomic(path, value):
    data = r.encoded(value)
    p.require(len(data) <= 512 * 1024, "Operational state exceeds limit")
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read(path):
    p.require(
        not path.is_symlink() and path.stat().st_size <= 512 * 1024, "Invalid operational file"
    )
    return p._json(path.read_bytes())


class Jobs:
    def __init__(self, root, *, profiles_dir=None, plots=True):
        self.external = Path(profiles_dir).resolve() if profiles_dir else None
        p.require(
            self.external is None or self.external.is_dir(), "Profiles directory does not exist"
        )
        pdf_reports.preflight()
        p.require(
            not plots or importlib.util.find_spec("matplotlib") is not None,
            "Install the reports extra or start with --no-plots",
        )
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.require(
            not (self.root / ".operator.lock").is_symlink(), "Symlink operator lock is unsupported"
        )
        self.lockfile = (self.root / ".operator.lock").open("a+b")
        try:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lockfile.close()
            raise ValueError(
                "Another operator session or its finishing worker owns this run directory"
            ) from None
        self.mutex = threading.RLock()
        self.process = None
        self.active_id = None
        self.log = None
        self.plots = plots
        self.profile_root = self.root / "profiles"
        p.require(not self.profile_root.is_symlink(), "Symlink profile directory is unsupported")
        self.profile_root.mkdir(exist_ok=True)
        for path in self.root.iterdir():
            if (
                path.is_dir()
                and not path.is_symlink()
                and ID.fullmatch(path.name)
                and (path / "state.json").is_file()
            ):
                state = read(path / "state.json")
                if state.get("phase") in ACTIVE:
                    state.update(
                        phase="failed",
                        error="The previous operator session ended. No test was restarted; saved evidence is retained.",
                    )
                    atomic(path / "state.json", state)
        self.import_profile(profiles.example())

    def import_profile(self, document):
        doc = profiles.validate(document)
        key = r.digest(r.encoded(doc))
        target = self.profile_root / (key + ".json")
        with self.mutex:
            if not target.exists():
                with target.open("xb") as handle:
                    handle.write(r.encoded(doc))
        return key

    def catalog(self):
        found = {}
        issues = []
        roots = [self.profile_root] + ([self.external] if self.external else [])
        for root in roots:
            for path in sorted(root.glob("*.json"))[:100]:
                try:
                    p.require(
                        path.stat().st_size <= profiles.MAX_PROFILE, "Profile exceeds 256 KiB"
                    )
                    doc = profiles.load(path)
                    key = r.digest(r.encoded(doc))
                    found[key] = doc
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    issues.append(path.name + ": " + str(exc))
        return found, issues

    def _path(self, job_id):
        p.require(isinstance(job_id, str) and ID.fullmatch(job_id), "Invalid job ID")
        path = self.root / job_id
        p.require(path.is_dir() and not path.is_symlink(), "Run not found")
        return path

    def _reap(self):
        if self.process is not None and self.process.poll() is not None:
            path = self._path(self.active_id)
            state = read(path / "state.json")
            if state["phase"] in ACTIVE:
                state.update(
                    phase="failed",
                    error="Worker exited before completing its records. Saved capture files are retained.",
                )
                atomic(path / "state.json", state)
            self.process = None
            self.active_id = None
            if self.log is not None:
                self.log.close()
                self.log = None

    def start(self, key, workflows, operator):
        with self.mutex:
            self._reap()
            p.require(self.process is None, "A suite is already running")
            docs, _ = self.catalog()
            p.require(key in docs, "Select an available DUT profile")
            doc = profiles.validate(docs[key])
            selected = suite.selection(doc, workflows)
            suite.initial_state(doc, selected)
            profiles.bind(doc, selected[0], operator)
            job_id = uuid.uuid4().hex
            path = self.root / job_id
            delivery.preflight_delivery(path / "capture", path / "report", pdf=True, package=True)
            path.mkdir(mode=0o700)
            request = dict(
                schema="hp437b.operator-request.v1",
                job_id=job_id,
                profile=doc,
                workflows=selected,
                operator=operator,
                plots=self.plots,
                started_utc=datetime.now(UTC).isoformat(),
            )
            atomic(path / "request.json", request)
            atomic(
                path / "state.json",
                dict(
                    job_id=job_id,
                    phase="starting",
                    current=None,
                    index=0,
                    total=len(selected),
                    results=[],
                    error=None,
                    outcome=None,
                ),
            )
            self.log = (path / "worker.log").open("xb")
            try:
                self.process = subprocess.Popen(
                    [sys.executable, "-m", "hp437b.operator_jobs", "--job", str(path)],
                    stdin=subprocess.DEVNULL,
                    stdout=self.log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    pass_fds=(self.lockfile.fileno(),),
                )
                self.active_id = job_id
            except BaseException:
                self.log.close()
                self.log = None
                state = read(path / "state.json")
                state.update(
                    phase="failed", error="Unable to start the local worker. No test was started."
                )
                atomic(path / "state.json", state)
                raise
            return self.get(job_id)

    def get(self, job_id):
        path = self._path(job_id)
        request = read(path / "request.json")
        state = read(path / "state.json")
        p.require(
            state["job_id"] == job_id and request["job_id"] == job_id,
            "Operational run identity mismatch",
        )
        return {
            **state,
            "profile_name": request["profile"]["dut"]["name"],
            "profile_id": request["profile"]["profile_id"],
            "operator": request["operator"] or request["profile"]["operator"],
            "workflows": request["workflows"],
            "started_utc": request["started_utc"],
            "cancel_requested": (path / "cancel.requested").is_file(),
            "active": self.active_id == job_id
            and self.process is not None
            and self.process.poll() is None,
            "pdf_ready": (path / "report/artifacts.json").is_file()
            and (path / "report/report.pdf").is_file(),
            "package_ready": (path / "report.zip").is_file(),
        }

    def state(self):
        with self.mutex:
            self._reap()
            docs, issues = self.catalog()
            items = []
            for key, doc in docs.items():
                items.append(
                    dict(
                        key=key,
                        profile_id=doc["profile_id"],
                        revision=doc["revision"],
                        name=doc["dut"]["name"],
                        description=doc["description"],
                        operator=doc["operator"],
                        workflows=[
                            dict(
                                id=kind,
                                label=suite.TITLES[kind],
                                points=len(doc["workflows"][kind]["plan"]["points"]),
                            )
                            for kind in profiles.KINDS
                            if kind in doc["workflows"]
                        ],
                    )
                )
            jobs = []
            for path in self.root.iterdir():
                if path.is_dir() and ID.fullmatch(path.name):
                    try:
                        jobs.append(self.get(path.name))
                    except (ValueError, KeyError, OSError):
                        continue
            jobs.sort(key=lambda item: item["started_utc"], reverse=True)
            return dict(
                profiles=sorted(
                    items, key=lambda item: (item["name"], item["profile_id"], item["revision"])
                ),
                profile_issues=issues,
                jobs=jobs[:20],
                active_id=self.active_id,
                plots=self.plots,
            )

    def cancel(self, job_id):
        with self.mutex:
            self._reap()
            p.require(self.active_id == job_id, "This suite is no longer running")
            state = self.get(job_id)
            p.require(
                state["phase"] in ("starting", "running"),
                "Capture has finished; reports are being prepared",
            )
            path = self._path(job_id) / "cancel.requested"
            try:
                with path.open("xb") as handle:
                    handle.write(b"Cooperative boundary cancellation requested\n")
            except FileExistsError:
                pass
            return self.get(job_id)

    def artifact(self, job_id, name):
        path = self._path(job_id)
        if name == "package.zip":
            target = path / "report.zip"
            delivery.verify(target)
            return target.read_bytes(), "application/zip", True
        p._relative(name)
        bundle = p.Bundle(path / "report")
        bundle.inventory("artifacts.json", "synthetic")
        p.require(name in bundle.entries, "Report artifact is not available")
        media = {
            ".pdf": "application/pdf",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".txt": "text/plain; charset=utf-8",
            ".md": "text/plain; charset=utf-8",
        }
        p.require(Path(name).suffix in media, "Unsupported report artifact")
        return bundle.read(name), media[Path(name).suffix], False

    def close(self):
        with self.mutex:
            self._reap()
            if self.process is not None:
                try:
                    self.cancel(self.active_id)
                except ValueError:
                    pass
                try:
                    self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass  # worker retains inherited lock; never kill a run
            if self.log is not None:
                self.log.close()
            self.lockfile.close()  # do not explicitly unlock the worker's inherited file description


def worker(path):
    path = Path(path).resolve()
    request = read(path / "request.json")
    p._keys(
        request, ("schema", "job_id", "profile", "workflows", "operator", "plots", "started_utc")
    )
    p.require(
        request["schema"] == "hp437b.operator-request.v1"
        and request["job_id"] == path.name
        and ID.fullmatch(path.name),
        "Invalid worker request",
    )
    p.require(type(request["plots"]) is bool, "Invalid plot option")
    state = read(path / "state.json")
    rows = []

    def emit(**values):
        state.update(values)
        atomic(path / "state.json", state)

    def progress(event):
        if event["event"] == "workflow_started":
            emit(phase="running", current=event["workflow"], index=event["index"])
        else:
            rows.append(event["result"])
            emit(current=None, results=list(rows), index=event["index"])

    try:
        result = suite.run(
            request["profile"],
            path / "capture",
            workflows=request["workflows"],
            operator=request["operator"],
            plots=request["plots"],
            cancelled=lambda: (path / "cancel.requested").is_file(),
            progress=progress,
        )
        emit(
            phase="reporting",
            current=None,
            results=result["results"],
            outcome=result["status"],
            acceptance=result["acceptance"],
            stop_reason=result["stop_reason"],
        )
        suite.publish(path / "capture", path / "report", plots=request["plots"], package=True)
        emit(phase="finished", error=None)
    except BaseException as exc:
        emit(phase="failed", error=str(exc)[:500] or type(exc).__name__)
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    worker(parser.parse_args().job)
