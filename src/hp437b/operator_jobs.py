"""Single-user job supervision; UI state is not measurement evidence."""

import fcntl
import importlib.util
import os
import re
import subprocess
import sys
import threading
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from . import guided_sweep, live_sweep_review, reference_profiles, sweep_matrix
from . import provenance as p
from . import report_delivery as delivery
from . import reporting as r
from . import test_profiles as profiles
from . import test_suite as suite

ACTIVE = ("starting", "waiting", "running", "reporting")
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
    def __init__(
        self,
        root,
        *,
        profiles_dir=None,
        plots=True,
        reference_config=None,
        sweep_config=None,
        preparation_config=None,
        workflow_lock_root=None,
        live_review_targets=None,
    ):
        from . import operator_preparation as prep

        self.preparation_config = (
            prep.configuration(preparation_config) if preparation_config is not None else None
        )
        if (
            self.preparation_config
            and reference_config
            and self.preparation_config["resource"] == reference_config["resource"]
        ):
            p.require(
                Path(self.preparation_config["workflow_lock_root"]).resolve()
                == Path(reference_config["root"]).resolve() / "tmp/workflow-locks",
                "Preparation and POWER REF must share the resource lock root",
            )
        self.reference_config = reference_config
        self.sweep_config = sweep_config
        self.live_review_targets = dict(live_review_targets or {})
        self.workflow_lock_root = Path(
            workflow_lock_root or Path(__file__).resolve().parents[2] / "tmp/workflow-locks"
        ).resolve()
        self.external = Path(profiles_dir).resolve() if profiles_dir else None
        p.require(
            self.external is None or self.external.is_dir(), "Profiles directory does not exist"
        )
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
        self.reference_profile_root = self.root / "reference-profiles"
        p.require(
            not self.reference_profile_root.is_symlink(), "Symlink reference profiles unsupported"
        )
        self.reference_profile_root.mkdir(exist_ok=True)
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

    def reference_catalog(self):
        found, issues = {}, []
        for path in sorted(self.reference_profile_root.glob("*.json"))[:100]:
            try:
                doc = reference_profiles.validate(read(path))
                key = r.digest(r.encoded(doc))
                p.require(path.name == key + ".json", "Profile content/hash mismatch")
                found[key] = doc
            except (ValueError, KeyError, TypeError, OSError) as exc:
                issues.append(path.name + ": " + str(exc))
        return found, issues

    def save_reference_profile(self, document):
        doc = reference_profiles.validate(document)
        key = r.digest(r.encoded(doc))
        with self.mutex:
            docs, issues = self.reference_catalog()
            p.require(not issues, "Resolve unreadable reference profiles before saving")
            for old_key, old in docs.items():
                p.require(
                    (old["profile_id"], old["revision"]) != (doc["profile_id"], doc["revision"])
                    or old_key == key,
                    "That profile revision already exists; increment the revision",
                )
            p.require(key in docs or len(docs) < 100, "At most 100 reference profiles may be saved")
            target = self.reference_profile_root / (key + ".json")
            p.require(not target.is_symlink(), "Symlink profile unsupported")
            if not target.exists():
                atomic(target, doc)
        return key

    def reference_profile(self, key):
        docs, _ = self.reference_catalog()
        p.require(isinstance(key, str) and key in docs, "Select an available reference profile")
        return docs[key]

    def start_reference_profile(self, key, meter_mode, operator, prepared):
        p.require(meter_mode in ("synthetic", "physical"), "Select a valid reference source")
        with self.mutex:
            doc = self.reference_profile(key)
            return self.start_reference(
                doc["workflows"],
                operator if operator is not None else doc["operator"],
                prepared,
                suite_mode=meter_mode,
                test_profile=reference_profiles.bind(doc, "before_capture"),
            )

    def assess_reference_profile(self, source_job_id, key, assessor):
        r.report_context.validate_operator(assessor)
        with self.mutex:
            doc = self.reference_profile(key)
            return self._saved_report(
                source_job_id,
                "acceptance_review",
                doc["criteria"],
                assessor,
                reference_profiles.bind(doc, "post_capture"),
            )

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

    def pending_reference(self):
        for path in self.root.iterdir():
            if (
                path.is_dir()
                and not path.is_symlink()
                and ID.fullmatch(path.name)
                and (path / "request.json").is_file()
            ):
                request = read(path / "request.json")
                if (
                    request.get("mode") == "physical"
                    or (
                        request.get("mode") == "meter_preparation"
                        and request.get("meter_mode") == "physical"
                    )
                    or (
                        request.get("mode") == "reference_suite"
                        and request.get("meter_mode") == "physical"
                    )
                ) and not (path / "operator-confirmation.json").is_file():
                    return path.name
        return None

    def start(self, key, workflows, operator):
        with self.mutex:
            self._reap()
            p.require(self.process is None, "A suite is already running")
            p.require(
                self.pending_reference() is None,
                "Confirm the prior physical run’s front-panel state first",
            )
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

    def review_live_guided(self, target_id, selected_ids, include_pdf):
        """Review configured targets without reserving a run or contacting the meter."""
        from . import pico_sweep

        p.require(isinstance(target_id, str), "Select a configured live review target")
        with self.mutex:
            self._reap()
            p.require(
                self.process is None, "Wait for the current run before reviewing live settings"
            )
            target = self.live_review_targets.get(target_id)
        p.require(
            target is not None,
            sweep_matrix.SI5351_UNAVAILABLE
            if target_id == sweep_matrix.SI5351_TARGET
            else "Live review is unavailable for the selected target",
        )
        if target_id == sweep_matrix.SI5351_TARGET:
            from .si5351_tone import Si5351Tone

            p.require(isinstance(target.reader, Si5351Tone), sweep_matrix.SI5351_UNAVAILABLE)
        config = guided_sweep.configuration(self.sweep_config)
        p.require(
            not guided_sweep.reference_source(config), "Live review needs an external RF fixture"
        )
        schema = (
            pico_sweep.si5351_schema(config)
            if target_id == sweep_matrix.SI5351_TARGET
            else sweep_matrix.PICO_SCHEMA
        )
        pico_sweep.configuration(config, schema=schema)
        proposed = live_sweep_review.review(
            target.reader,
            target_id,
            fixture_digest=r.digest(r.encoded(config)),
            timing=target.timing,
            tolerance_hz=target.tolerance_hz,
            include_pdf=include_pdf,
            selected_ids=selected_ids,
            schema=schema,
        )
        if target_id == sweep_matrix.SI5351_TARGET:
            from .pico_sweep import SI5351_INITIAL_DRIVE_MA

            p.require(
                proposed.target.active_drive_ma == SI5351_INITIAL_DRIVE_MA,
                "Prepare the Pico Si5351 at a saved and boot-active drive of 8 mA",
            )
        return proposed.public()

    def start_guided(
        self,
        plan,
        operator,
        meter_mode,
        prepared,
        *,
        include_pdf=None,
        pico_review_digest=None,
        pico_previous_job_id=None,
    ):
        from . import guided_sweep as guided

        with self.mutex:
            self._reap()
            p.require(self.process is None, "A run is already active")
            p.require(self.pending_reference() is None, "Confirm the prior reference run first")
            plan = guided.validate(plan)
            live_pico = plan["schema"] in sweep_matrix.PICO_SCHEMAS
            si5351 = plan["schema"] in sweep_matrix.SI5351_SCHEMAS
            if plan["schema"] in sweep_matrix.MATRIX_SCHEMAS and include_pdf is None:
                include_pdf = False
            p.require(
                include_pdf is None or (type(include_pdf) is bool and plan["series"] == "combined"),
                "PDF selection requires the combined sweep and a boolean",
            )
            operator = r.report_context.validate_operator(operator)
            guided.check_mode(plan, meter_mode, live_pico=live_pico)
            p.require(
                live_pico or (pico_review_digest is None and pico_previous_job_id is None),
                "Pico review only applies to a live Pico sweep",
            )
            config = None
            lock_root = self.workflow_lock_root
            if meter_mode == "physical":
                p.require(
                    self.sweep_config is not None, "A sweep meter must be configured at launch"
                )
                config = guided.configuration(self.sweep_config)
                guided.check_source_plan(plan, config)
                if (
                    self.reference_config
                    and config["resource"] == self.reference_config["resource"]
                ):
                    lock_root = Path(self.reference_config["root"]).resolve() / "tmp/workflow-locks"
                if (
                    self.preparation_config
                    and config["resource"] == self.preparation_config["resource"]
                ):
                    lock_root = Path(self.preparation_config["workflow_lock_root"]).resolve()
                from . import pico_sweep

                p.require(
                    not pico_sweep.pending_meter(lock_root, config["resource"]).exists(),
                    "The configured meter has unresolved Pico capture state",
                )
                if live_pico:
                    from .pico_tone import PicoTone
                    from .si5351_tone import Si5351Tone

                    source = self.live_review_targets.get(pico_sweep.target_id(plan["schema"]))
                    p.require(
                        source is not None
                        and isinstance(source.reader, PicoTone)
                        and isinstance(source.reader, Si5351Tone) == si5351,
                        sweep_matrix.SI5351_UNAVAILABLE
                        if si5351
                        else "Configure the installed Pico USB bridge before Start",
                    )
                    p.require(
                        isinstance(pico_review_digest, str)
                        and re.fullmatch(r"[0-9a-f]{64}", pico_review_digest),
                        f"Review all {len(guided.points(plan))} Pico points before Start",
                    )
                    pico_sweep.configuration(config, schema=plan["schema"])
                    pico_sweep.prepared_check(prepared, schema=plan["schema"])
                    if pico_previous_job_id is not None:
                        prior = self.get(pico_previous_job_id)
                        p.require(
                            prior["phase"] not in ACTIVE and prior["sweep_plan"] == plan,
                            "Select a sealed earlier run of this exact Pico plan",
                        )
                else:
                    p.require(
                        isinstance(prepared, dict)
                        and set(prepared) == set(guided.PREPARED)
                        and all(value is True for value in prepared.values()),
                        "Confirm the prepared RF path and meter before starting",
                    )
            else:
                p.require(prepared == {}, "Simulated sweeps do not use bench attestations")
            job_id = uuid.uuid4().hex
            path = self.root / job_id
            if live_pico:
                from . import guided_report

                guided_report.preflight(path / "capture", path / "report", plots=self.plots)
            delivery.preflight_delivery(
                path / "capture",
                path / "report",
                pdf=include_pdf is not False,
                package=include_pdf is not False,
            )
            request = dict(
                schema="hp437b.operator-request.v1",
                mode="guided",
                job_id=job_id,
                profile=dict(
                    dut=dict(name=plan["name"]), profile_id="operator-guided", operator=operator
                ),
                workflows=["GUIDED"],
                operator=operator,
                plots=self.plots,
                started_utc=datetime.now(UTC).isoformat(),
                sweep_plan=plan,
                meter_mode=meter_mode,
                sweep_config=config,
                prepared=prepared,
            )
            if include_pdf is not None:
                request["include_pdf"] = include_pdf
            if config is not None:
                request["workflow_lock_root"] = str(lock_root)
            if live_pico:
                request["pico_usb"] = asdict(source.reader.link.config)
                request["pico_review_digest"] = pico_review_digest
                if pico_previous_job_id is not None:
                    request["pico_previous_job_id"] = pico_previous_job_id
            path.mkdir(mode=0o700)
            atomic(path / "request.json", request)
            atomic(
                path / "state.json",
                dict(
                    job_id=job_id,
                    phase="starting",
                    current="GUIDED",
                    index=0,
                    total=len(guided.points(plan)),
                    results=[],
                    point_results=[],
                    prompt=None,
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
                state.update(phase="failed", error="Unable to start guided worker")
                atomic(path / "state.json", state)
                raise
            return self.get(job_id)

    def confirm_guided(self, job_id, confirmation):
        from . import guided_sweep as guided

        with self.mutex:
            self._reap()
            p.require(self.active_id == job_id, "This sweep is no longer active")
            job = self.get(job_id)
            p.require(
                job["mode"] == "guided"
                and job["phase"] == "waiting"
                and not job["cancel_requested"],
                "No point is awaiting confirmation",
            )
            prompt = job["prompt"]
            # The service timestamps authorization; clients cannot backdate a capture.
            p._keys(
                confirmation,
                (
                    "point_id",
                    "frequency",
                    "drive",
                    "token",
                    "operator",
                    "frequency_confirmed",
                    "drive_confirmed",
                ),
            )
            value = {**confirmation, "confirmed_utc": datetime.now(UTC).isoformat()}
            guided.check_confirmation(value, prompt, prompt["token"])
            path = self._path(job_id) / ("confirm-" + prompt["token"] + ".json")
            p.require(not path.exists(), "This point has already been confirmed")
            # Atomic publication prevents the worker reading a partially written receipt.
            temporary = path.with_suffix(".tmp")
            with temporary.open("xb") as handle:
                handle.write(r.encoded(value))
                handle.flush()
                os.fsync(handle.fileno())
            os.link(temporary, path)
            temporary.unlink()
            return self.get(job_id)

    def start_preparation(
        self, action, meter_mode, operator, prepared, reference_factor, factor_source
    ):
        from . import operator_preparation as prep

        with self.mutex:
            self._reap()
            p.require(self.process is None, "A run is already active")
            p.require(self.pending_reference() is None, "Confirm the prior physical run first")
            operator = r.report_context.validate_operator(operator)
            factor, source = prep.inputs(
                action, meter_mode, prepared, reference_factor, factor_source
            )
            p.require(
                meter_mode != "physical" or self.preparation_config is not None,
                "Meter preparation must be explicitly configured at service launch",
            )
            config = (
                prep.configuration(self.preparation_config) if meter_mode == "physical" else None
            )
            job_id = uuid.uuid4().hex
            path = self.root / job_id
            path.mkdir(mode=0o700)
            request = dict(
                schema="hp437b.operator-request.v1",
                mode="meter_preparation",
                job_id=job_id,
                profile=dict(
                    dut=dict(name="Meter preparation"),
                    profile_id="meter-preparation",
                    operator=operator,
                ),
                workflows=[action],
                operator=operator,
                plots=False,
                started_utc=datetime.now(UTC).isoformat(),
                meter_mode=meter_mode,
                preparation_config=config,
                prepared=prepared,
                reference_factor=factor,
                factor_source=source,
            )
            atomic(path / "request.json", request)
            atomic(
                path / "state.json",
                dict(
                    job_id=job_id,
                    phase="starting",
                    current=action,
                    index=0,
                    total=1,
                    results=[],
                    error=None,
                    outcome=None,
                ),
            )
            self.log = (path / "worker.log").open("xb")
            try:
                self.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "hp437b.operator_jobs",
                        "--job",
                        str(path),
                        "--lock-fd",
                        str(self.lockfile.fileno()),
                    ],
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
                    phase="failed",
                    error="Unable to start preparation worker; no operation was started",
                )
                atomic(path / "state.json", state)
                raise
            return self.get(job_id)

    def start_reference_suite(self, workflows, meter_mode, operator, prepared):
        p.require(meter_mode in ("synthetic", "physical"), "Invalid suite source")
        return self.start_reference(workflows, operator, prepared, suite_mode=meter_mode)

    def start_reference(self, kind, operator, prepared, *, suite_mode=None, test_profile=None):
        from . import operator_reference as ref
        from . import reference_suite

        with self.mutex:
            self._reap()
            workflows = reference_suite.selection(kind) if suite_mode is not None else [kind]
            if test_profile is not None:
                reference_profiles.validate_binding(
                    test_profile, workflows, test_profile["profile"]["criteria"]
                )
            p.require(
                suite_mode is None or suite_mode in ("synthetic", "physical"),
                "Invalid suite source",
            )
            if suite_mode == "synthetic" and "WF-01" in workflows:
                p.require(
                    (Path(__file__).resolve().parents[2] / "tools/exercise_workflow.py").is_file(),
                    "WF-01 reference simulation requires the source checkout",
                )
            physical = suite_mode != "synthetic"
            p.require(
                not physical or self.reference_config is not None,
                "POWER REF is not enabled by this service",
            )
            p.require(self.process is None, "A suite is already running")
            p.require(
                suite_mode is not None or kind in ref.SCRIPTS, "Select one POWER REF workflow"
            )
            p.require(
                (
                    isinstance(prepared, dict)
                    and set(prepared) == set(ref.PREPARED)
                    and all(value is True for value in prepared.values())
                )
                if physical
                else prepared == {},
                "Fresh prepared setup confirmations are required for every POWER REF run",
            )
            r.report_context.validate_operator(operator)
            p.require(
                self.pending_reference() is None,
                "Confirm the prior physical run's front-panel state before another POWER REF run",
            )
            config = p._json(r.encoded(self.reference_config)) if physical else None
            setup = {
                **(config["setup"] if config else {}),
                **prepared,
                "prepared_record_utc": datetime.now(UTC).isoformat(),
                "confirmation_origin": "Operator freshly confirmed each setup item in the local UI",
                "operator": operator,
            }
            if operator is None:
                setup.pop("operator")
            if not physical:
                setup = None
            job_id = uuid.uuid4().hex
            path = self.root / job_id
            delivery.preflight_delivery(path / "capture", path / "report", pdf=True, package=True)
            path.mkdir(mode=0o700)
            request = dict(
                schema="hp437b.operator-request.v1",
                mode="physical" if suite_mode is None else "reference_suite",
                job_id=job_id,
                profile=dict(
                    dut=dict(name="Internal POWER REF" if physical else "Simulated POWER REF"),
                    profile_id="prepared-power-reference",
                    operator=operator,
                ),
                workflows=workflows,
                operator=operator,
                plots=self.plots,
                started_utc=datetime.now(UTC).isoformat(),
                reference_config=config,
                prepared_setup=setup,
            )
            if suite_mode is not None:
                request["meter_mode"] = suite_mode
            if test_profile is not None:
                request["test_profile"] = test_profile
            atomic(path / "request.json", request)
            atomic(
                path / "state.json",
                dict(
                    job_id=job_id,
                    phase="starting",
                    current=None,
                    index=0,
                    total=len(workflows),
                    results=[],
                    error=None,
                    outcome=None,
                ),
            )
            self.log = (path / "worker.log").open("xb")
            try:
                self.process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "hp437b.operator_jobs",
                        "--job",
                        str(path),
                        "--lock-fd",
                        str(self.lockfile.fileno()),
                    ],
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
                    phase="failed", error="Unable to start reference worker; no capture was started"
                )
                atomic(path / "state.json", state)
                raise
            return self.get(job_id)

    def regenerate_reports(self, source_job_id, *, include_pdf=None):
        return self._saved_report(source_job_id, "report_recovery", include_pdf=include_pdf)

    def assess_run(self, source_job_id, criteria, assessor):
        from . import acceptance_review

        criteria = acceptance_review.validate(criteria)
        r.report_context.validate_operator(assessor)
        return self._saved_report(source_job_id, "acceptance_review", criteria, assessor)

    def _saved_report(
        self,
        source_job_id,
        mode,
        criteria=None,
        assessor=None,
        test_profile=None,
        *,
        include_pdf=None,
    ):
        from . import report_recovery

        with self.mutex:
            self._reap()
            p.require(self.process is None, "Wait for the active run or report attempt to finish")
            source = self._path(source_job_id)
            source_job = self.get(source_job_id)
            p.require(
                not source_job["active"] and source_job["phase"] not in ACTIVE,
                "Wait for the source worker to close",
            )
            original = read(source / "request.json")
            guided = original.get("mode") == "guided"
            p.require(
                not guided or mode == "report_recovery", "Guided captures support regeneration only"
            )
            p.require(
                include_pdf is None or (guided and type(include_pdf) is bool),
                "PDF selection is available for guided combined captures",
            )
            if guided and include_pdf is None:
                include_pdf = original.get("include_pdf")
            source_hash = report_recovery.inspect(source, original)
            if test_profile is not None:
                reference_profiles.validate_binding(test_profile, original["workflows"], criteria)
            if criteria is not None:
                p.require(
                    set(criteria["workflows"]) <= set(original["workflows"]),
                    "Criteria include workflows outside this capture",
                )
            job_id = uuid.uuid4().hex
            path = self.root / job_id
            delivery.preflight_delivery(
                source / "capture",
                path / "report",
                pdf=include_pdf is not False,
                package=include_pdf is not False,
            )
            path.mkdir(mode=0o700)
            request = dict(
                schema="hp437b.operator-request.v1",
                mode=mode,
                job_id=job_id,
                profile=original["profile"],
                workflows=original["workflows"],
                operator=original["operator"],
                plots=self.plots,
                started_utc=datetime.now(UTC).isoformat(),
                source_job_id=source_job_id,
                source_inventory_sha256=source_hash,
            )
            if include_pdf is not None:
                request["include_pdf"] = include_pdf
            if mode == "acceptance_review":
                request.update(criteria=criteria, assessor=assessor)
            if test_profile is not None:
                request["test_profile"] = test_profile
            atomic(path / "request.json", request)
            atomic(
                path / "state.json",
                dict(
                    job_id=job_id,
                    phase="starting",
                    current=None,
                    index=0,
                    total=1,
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
                    env={
                        key: value for key, value in os.environ.items() if key != "HP437B_OPERATOR"
                    },
                    pass_fds=(self.lockfile.fileno(),),
                )
                self.active_id = job_id
            except BaseException:
                self.log.close()
                self.log = None
                state = read(path / "state.json")
                state.update(
                    phase="failed",
                    error="Unable to start report worker; no measurement was started",
                )
                atomic(path / "state.json", state)
                raise
            return self.get(job_id)

    def confirm_reference(self, job_id, operator, confirmed):
        with self.mutex:
            self._reap()
            job = self.get(job_id)
            p.require(
                (
                    job["mode"] == "physical"
                    or (job["mode"] == "meter_preparation" and job.get("meter_mode") == "physical")
                    or (job["mode"] == "reference_suite" and job.get("meter_mode") == "physical")
                )
                and not job["active"]
                and job["phase"] not in ACTIVE,
                "Physical worker must be closed before confirming front-panel state",
            )
            p.require(
                confirmed is True, "Confirm live numeric readings, RMT off, and POWER REF off"
            )
            r.report_context.validate_operator(operator)
            path = self._path(job_id)
            with (path / ".capture.lock").open("a+b") as guard:
                try:
                    fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError(
                        "The capture child still owns the meter; wait for closure before confirming"
                    ) from None
            if job["mode"] == "meter_preparation":
                from . import reconciliation as rec

                request = read(path / "request.json")
                config = request["preparation_config"]
                key = r.digest(config["resource"].encode())
                Path(config["workflow_lock_root"]).mkdir(parents=True, exist_ok=True)
                with rec._lease(Path(config["workflow_lock_root"]) / (key + ".lock")):
                    pass  # An orphaned native child must release the meter first.
            inventory = path / "capture/artifacts.json"
            value = dict(
                schema="hp437b.operator-front-panel.v1",
                job_id=job_id,
                operator=operator,
                confirmed_utc=datetime.now(UTC).isoformat(),
                live_readings=True,
                rmt_off=True,
                power_ref_off=True,
                capture_inventory_sha256=r.digest(inventory.read_bytes())
                if inventory.is_file()
                else None,
            )
            if job["mode"] == "meter_preparation":
                value["no_zero_cal_hold_or_error"] = True
                if (path / "preparation-result.json").exists():
                    from . import operator_preparation as prep

                    prep.artifact(path, "receipt.json")
                value["preparation_receipt_sha256"] = (
                    r.digest((path / "capture/diagnostics.json").read_bytes())
                    if (path / "capture/diagnostics.json").is_file()
                    else None
                )
            target = path / "operator-confirmation.json"
            p.require(not target.exists(), "Front-panel confirmation already recorded")
            with target.open("xb") as handle:
                handle.write(r.encoded(value))
            return self.get(job_id)

    def get(self, job_id):
        path = self._path(job_id)
        request = read(path / "request.json")
        state = read(path / "state.json")
        p.require(
            state["job_id"] == job_id and request["job_id"] == job_id,
            "Operational run identity mismatch",
        )
        physical = request.get("mode") == "physical" or (
            request.get("mode") in ("reference_suite", "meter_preparation")
            and request.get("meter_mode") == "physical"
        )
        stage = None
        checkpoint = path / "capture/workflow.json"
        if request.get("mode") == "reference_suite" and state.get("current"):
            checkpoint = path / "steps" / state["current"] / "capture/workflow.json"
        if request.get("mode") == "meter_preparation":
            checkpoint = path / "capture/diagnostics.json"
            if checkpoint.is_file():
                try:
                    stage = read(checkpoint).get("stage")
                except (OSError, ValueError, TypeError):
                    pass
        if physical and request.get("mode") != "meter_preparation" and checkpoint.is_file():
            try:
                current = read(checkpoint)
                tables = [current.get("stages", {}), current.get("control_stages", {})]
                stage = next(
                    (
                        name
                        for table in tables
                        for name, item in table.items()
                        if item.get("status") == "running"
                    ),
                    None,
                )
            except (OSError, ValueError, TypeError):
                pass
        return {
            **state,
            "mode": request.get("mode", "synthetic"),
            "preparation_ready": request.get("mode") == "meter_preparation"
            and state["phase"] not in ACTIVE
            and (path / "preparation-result.json").is_file(),
            "preparation_summary": read(path / "preparation-result.json")
            if request.get("mode") == "meter_preparation"
            and (path / "preparation-result.json").is_file()
            else None,
            "source_job_id": request.get("source_job_id"),
            "assessment_outcome": state.get("assessment_outcome"),
            "test_profile": request.get("test_profile"),
            "assessment_ready": (path / "assessment/artifacts.json").is_file()
            and (path / "assessment/report.pdf").is_file(),
            "report_recovery_available": (
                request.get("mode") in ("physical", "reference_suite")
                or (
                    request.get("mode") == "guided"
                    and request["sweep_plan"]["series"] == "combined"
                )
            )
            and state["phase"] not in ACTIVE
            and (path / "capture/artifacts.json").is_file(),
            "meter_mode": request.get("meter_mode"),
            "sweep_plan": request.get("sweep_plan"),
            "sweep_config": request.get("sweep_config"),
            "stage": state.get("stage") if request.get("mode") == "guided" else stage,
            "front_panel_confirmed": (path / "operator-confirmation.json").is_file(),
            "profile_name": request["profile"]["dut"]["name"],
            "profile_id": request["profile"]["profile_id"],
            "operator": request["operator"] or request["profile"]["operator"],
            "workflows": request["workflows"],
            "started_utc": request["started_utc"],
            "cancel_requested": (path / "cancel.requested").is_file(),
            "active": self.active_id == job_id
            and self.process is not None
            and self.process.poll() is None,
            "include_pdf": request.get("include_pdf"),
            "report_ready": (path / "report/artifacts.json").is_file()
            and (path / "report/report.html").is_file(),
            "pdf_ready": (path / "report/artifacts.json").is_file()
            and (path / "report/report.pdf").is_file(),
            "package_ready": (path / "report.zip").is_file(),
        }

    def state(self):
        from . import pico_sweep

        si5351_schema = pico_sweep.si5351_schema(self.sweep_config)
        with self.mutex:
            self._reap()
            docs, issues = self.catalog()
            reference_docs, reference_issues = self.reference_catalog()
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
                reference_profiles=[
                    dict(key=key, document=doc) for key, doc in reference_docs.items()
                ],
                reference_profile_issues=reference_issues,
                profiles=sorted(
                    items, key=lambda item: (item["name"], item["profile_id"], item["revision"])
                ),
                profile_issues=issues,
                jobs=jobs[:20]
                + [job for job in jobs[20:] if job["job_id"] == self.pending_reference()],
                report_sources=[
                    dict(
                        job_id=job["job_id"],
                        name=job["profile_name"],
                        started_utc=job["started_utc"],
                        workflows=job["workflows"],
                        outcome=job.get("outcome"),
                        mode=job["mode"],
                        include_pdf=job["include_pdf"],
                    )
                    for job in jobs
                    if job["report_recovery_available"]
                ],
                active_id=self.active_id,
                pending_reference=self.pending_reference(),
                plots=self.plots,
                preparation=(
                    {
                        key: self.preparation_config[key]
                        for key in ("resource", "meter_serial", "sensor_serial", "known_issues")
                    }
                    if self.preparation_config
                    else None
                ),
                guided=dict(
                    default_plan=guided_sweep.example(),
                    meter=self.sweep_config,
                    automatic_simulation=sweep_matrix.catalog(),
                    live_review_targets=sorted(self.live_review_targets),
                    si5351_unavailable=sweep_matrix.SI5351_UNAVAILABLE,
                    live_si5351_schema=si5351_schema
                    if sweep_matrix.SI5351_TARGET in self.live_review_targets
                    else None,
                    live_si5351_bands=sweep_matrix.bands(
                        sweep_matrix.dials_for_schema(si5351_schema)
                    ),
                    live_pico_schema=sweep_matrix.PICO_SCHEMA
                    if "pico-gpio" in self.live_review_targets
                    and si5351_schema != sweep_matrix.TIS_1W_SCHEMA
                    else None,
                ),
                reference=(
                    dict(
                        resource=self.reference_config["resource"],
                        meter_serial=self.reference_config["setup"]["meter_serial"],
                        sensor_serial=self.reference_config["setup"]["sensor_serial"],
                        known_issues=self.reference_config["setup"]["known_issues"],
                    )
                    if self.reference_config
                    else None
                ),
            )

    def history(self, offset=0, category="all"):
        p.require(type(offset) is int and offset >= 0, "Invalid history offset")
        p.require(
            category in ("all", "measurements", "reports", "preparation"), "Invalid history filter"
        )
        with self.mutex:
            self._reap()
            entries, issues = [], []
            for path in self.root.iterdir():
                if not path.is_dir() or not ID.fullmatch(path.name):
                    continue
                try:
                    job = self.get(path.name)
                    report = job["mode"] in ("report_recovery", "acceptance_review")
                    if (
                        category == "reports"
                        and not report
                        or category == "measurements"
                        and (report or job["mode"] == "meter_preparation")
                        or category == "preparation"
                        and job["mode"] != "meter_preparation"
                    ):
                        continue
                    entries.append(
                        {
                            key: job[key]
                            for key in (
                                "job_id",
                                "source_job_id",
                                "mode",
                                "meter_mode",
                                "profile_name",
                                "started_utc",
                                "phase",
                                "outcome",
                                "workflows",
                                "include_pdf",
                                "report_ready",
                                "pdf_ready",
                                "package_ready",
                                "report_recovery_available",
                                "assessment_outcome",
                                "assessment_ready",
                                "preparation_ready",
                            )
                        }
                    )
                except (ValueError, KeyError, TypeError, OSError):
                    issues.append(path.name)
            entries.sort(key=lambda entry: (entry["started_utc"], entry["job_id"]), reverse=True)
            return dict(
                entries=entries[offset : offset + 20],
                total=len(entries),
                offset=offset,
                unreadable_jobs=issues,
            )

    def run_details(self, job_id):
        from . import run_history

        with self.mutex:
            self._reap()
            job = self.get(job_id)
            source_id = (
                job["source_job_id"]
                if job["mode"] in ("report_recovery", "acceptance_review")
                else job_id
            )
            source = self._path(source_id)
            source_job = self.get(source_id)
            p.require(
                not source_job["active"] and source_job["phase"] not in ACTIVE,
                "Wait for the source worker to close before inspecting measurements",
            )
            request = read(source / "request.json")
            p.require(
                request.get("mode") in ("physical", "reference_suite"),
                "POWER REF details are available for individual and combined POWER REF captures",
            )
            detail = run_history.details(source, request)
            confirmation = source / "operator-confirmation.json"
            value = read(confirmation) if confirmation.exists() else None
            if value:
                p.require(
                    value.get("schema") == "hp437b.operator-front-panel.v1"
                    and value.get("job_id") == source_id
                    and all(
                        value.get(k) is True for k in ("live_readings", "rmt_off", "power_ref_off")
                    ),
                    "Invalid original front-panel attestation",
                )
                p.require(
                    value.get("capture_inventory_sha256") == detail["source_inventory_sha256"],
                    "Front-panel confirmation is bound to different evidence",
                )
            return dict(
                job_id=job_id,
                source_job_id=source_id,
                report_attempt=job["mode"] in ("report_recovery", "acceptance_review"),
                front_panel_confirmation=value,
                **detail,
            )

    def compare_runs(self, job_ids, workflow):
        from . import run_history

        p.require(
            isinstance(job_ids, list)
            and 2 <= len(job_ids) <= 4
            and all(isinstance(x, str) and ID.fullmatch(x) for x in job_ids)
            and len(set(job_ids)) == len(job_ids),
            "Choose two to four distinct measurement runs",
        )
        with self.mutex:
            entries = []
            for job_id in job_ids:
                p.require(
                    self.get(job_id)["mode"] in ("physical", "reference_suite"),
                    "Select measurements, not report-regeneration attempts",
                )
                entries.append((job_id, self.run_details(job_id)))
            return run_history.compare(entries, workflow)

    def cancel(self, job_id):
        with self.mutex:
            self._reap()
            p.require(self.active_id == job_id, "This suite is no longer running")
            state = self.get(job_id)
            p.require(
                state["mode"] not in ("report_recovery", "acceptance_review"),
                "Report regeneration has no measurement to cancel; wait for publication",
            )
            p.require(
                state["phase"] in ("starting", "waiting", "running"),
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
        if name.startswith("preparation/"):
            from . import operator_preparation as prep

            job = self.get(job_id)
            p.require(
                job["mode"] == "meter_preparation"
                and not job["active"]
                and job["phase"] not in ACTIVE,
                "Wait for preparation to close",
            )
            return prep.artifact(path, name[len("preparation/") :])
        if name.startswith("assessment/"):
            name = name[len("assessment/") :]
            if name == "package.zip":
                delivery.verify(path / "assessment.zip")
                return (path / "assessment.zip").read_bytes(), "application/zip", True
            p.require(
                name
                in (
                    "report.pdf",
                    "report.html",
                    "results.json",
                    "criteria.json",
                    "metadata.json",
                    "provenance.json",
                ),
                "Unsupported assessment artifact",
            )
            bundle = p.Bundle(path / "assessment")
            bundle.inventory("artifacts.json", p._json(bundle.read("artifacts.json"))["mode"])
            media = (
                "application/pdf"
                if name.endswith(".pdf")
                else "text/html; charset=utf-8"
                if name.endswith(".html")
                else "application/json"
            )
            return bundle.read(name), media, False
        if name == "package.zip":
            target = path / "report.zip"
            delivery.verify(target)
            return target.read_bytes(), "application/zip", True
        p._relative(name)
        bundle = p.Bundle(path / "report")
        bundle.inventory("artifacts.json", p._json(bundle.read("artifacts.json"))["mode"])
        p.require(name in bundle.entries, "Report artifact is not available")
        media = {
            ".pdf": "application/pdf",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json",
            ".csv": "text/csv; charset=utf-8",
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


def worker(path, *, lock_fd=None):
    path = Path(path).resolve()
    request = read(path / "request.json")
    expected = ("schema", "job_id", "profile", "workflows", "operator", "plots", "started_utc")
    if request.get("mode") == "physical":
        expected += ("mode", "reference_config", "prepared_setup")
    if request.get("mode") == "reference_suite":
        expected += ("mode", "meter_mode", "reference_config", "prepared_setup")
    if request.get("mode") == "acceptance_review":
        expected += ("mode", "source_job_id", "source_inventory_sha256", "criteria", "assessor")
    if request.get("mode") == "report_recovery":
        expected += ("mode", "source_job_id", "source_inventory_sha256")
    if request.get("mode") == "meter_preparation":
        expected += (
            "mode",
            "meter_mode",
            "preparation_config",
            "prepared",
            "reference_factor",
            "factor_source",
        )
    if request.get("mode") == "guided":
        expected += ("mode", "sweep_plan", "meter_mode", "sweep_config", "prepared")
        if "workflow_lock_root" in request:
            expected += ("workflow_lock_root",)
        if request["sweep_plan"].get("schema") in sweep_matrix.PICO_SCHEMAS:
            expected += ("pico_usb", "pico_review_digest")
            if "pico_previous_job_id" in request:
                p.require(
                    isinstance(request["pico_previous_job_id"], str)
                    and ID.fullmatch(request["pico_previous_job_id"])
                    and request["pico_previous_job_id"] != path.name,
                    "Invalid prior Pico job ID",
                )
                expected += ("pico_previous_job_id",)
    if "test_profile" in request:
        p.require(
            request.get("mode") in ("reference_suite", "acceptance_review"),
            "Unsupported profile worker mode",
        )
        expected += ("test_profile",)
    if "include_pdf" in request:
        p.require(
            request.get("mode") in ("guided", "report_recovery")
            and type(request["include_pdf"]) is bool,
            "Invalid PDF worker option",
        )
        expected += ("include_pdf",)
    p._keys(request, expected)
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
        if request.get("mode") == "meter_preparation":
            from . import operator_preparation as prep

            with (path / ".capture.lock").open("a+b") as guard:
                fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                prep.run(path, request, emit)
            return
        if request.get("mode") in ("report_recovery", "acceptance_review"):
            from . import report_recovery

            source_id = request["source_job_id"]
            p.require(isinstance(source_id, str) and ID.fullmatch(source_id), "Invalid source job")
            source = path.parent / source_id
            p.require(source.is_dir() and not source.is_symlink(), "Source run not found")
            original = read(source / "request.json")
            source_state = read(source / "state.json")
            p.require(
                original["job_id"] == source_id and source_state["job_id"] == source_id,
                "Source run identity mismatch",
            )
            p.require(source_state["phase"] not in ACTIVE, "Source run is still active")
            emit(phase="reporting", current=None)
            if request["mode"] == "acceptance_review":
                from . import acceptance_review

                if "test_profile" in request:
                    p.require(
                        request["test_profile"]["selected"] == "post_capture",
                        "Saved-run profile must be selected post capture",
                    )
                result = acceptance_review.publish(
                    source,
                    path / "report",
                    original,
                    request["criteria"],
                    request["assessor"],
                    expected_hash=request["source_inventory_sha256"],
                    test_profile=request.get("test_profile"),
                )
                emit(
                    assessment_outcome=result["outcome"],
                    assessment_source=request["criteria"]["source"],
                )
            else:
                report_recovery.publish(
                    source,
                    path / "report",
                    original,
                    request["source_inventory_sha256"],
                    plots=request["plots"],
                    include_pdf=request.get("include_pdf"),
                )
            emit(phase="finished", outcome="completed", index=1, error=None)
            return
        if request.get("mode") == "reference_suite":
            from . import reference_suite

            binding = request.get("test_profile")
            if binding is not None:
                p.require(
                    binding["selected"] == "before_capture",
                    "Run profile must be selected before capture",
                )
                reference_profiles.validate_binding(
                    binding, request["workflows"], binding["profile"]["criteria"]
                )

            def capture_emit(**values):
                if binding is not None and values.get("phase") == "finished":
                    values["phase"] = "reporting"
                emit(**values)

            reference_suite.run(path, request, capture_emit, lock_fd=lock_fd)
            if binding is not None:
                from . import acceptance_review

                try:
                    result = acceptance_review.publish(
                        path,
                        path / "assessment",
                        request,
                        binding["profile"]["criteria"],
                        request["operator"],
                        test_profile=binding,
                    )
                    emit(assessment_outcome=result["outcome"], assessment_error=None)
                except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                    emit(assessment_error=str(exc)[:500], assessment_outcome=None)
                emit(phase="finished", current=None)
            return
        if request.get("mode") == "guided":
            from contextlib import ExitStack

            from . import guided_report, reconciliation

            plan = guided_sweep.validate(request["sweep_plan"])
            live_pico = plan["schema"] in sweep_matrix.PICO_SCHEMAS
            guided_sweep.check_mode(plan, request["meter_mode"], live_pico=live_pico)
            if live_pico:
                from . import guided_report

                p.require(type(request.get("include_pdf")) is bool, "Invalid Pico report selection")
                folder = Path(request["workflow_lock_root"])
                p.require(folder.is_absolute(), "Guided meter requires the shared lock root")
                guided_report.preflight(path / "capture", path / "report", plots=request["plots"])
                delivery.preflight_delivery(
                    path / "capture",
                    path / "report",
                    pdf=request["include_pdf"],
                    package=request["include_pdf"],
                )
            with ExitStack() as leases:
                leases.enter_context(reconciliation._lease(path / ".capture.lock"))
                if request["meter_mode"] == "physical" and not live_pico:
                    folder = Path(request["workflow_lock_root"])
                    p.require(folder.is_absolute(), "Guided meter requires the shared lock root")
                    folder.mkdir(parents=True, exist_ok=True)
                    key = r.digest(request["sweep_config"]["resource"].encode())
                    try:
                        leases.enter_context(reconciliation._lease(folder / (key + ".lock")))
                    except BlockingIOError:
                        raise ValueError(
                            "Another workflow owns the configured sweep meter"
                        ) from None
                gate = guided_sweep.FileGate(path, emit)
                if live_pico:
                    from . import pico_sweep
                    from .pico_tone import PicoTone, UsbHost, UsbLink
                    from .si5351_tone import Si5351Tone

                    adapter = (
                        Si5351Tone if plan["schema"] in sweep_matrix.SI5351_SCHEMAS else PicoTone
                    )
                    source = adapter(
                        UsbLink(UsbHost(**request["pico_usb"])),
                        pico_sweep.target_id(plan["schema"]),
                    )
                    previous = request.get("pico_previous_job_id")
                    result = pico_sweep.run(
                        source,
                        path / "capture",
                        plan,
                        request["sweep_config"],
                        request["workflow_lock_root"],
                        request["prepared"],
                        request["pico_review_digest"],
                        operator=request["operator"],
                        include_pdf=request["include_pdf"],
                        continue_from=path.parent / previous / "capture" if previous else None,
                        cancelled=gate.cancelled,
                        emit=emit,
                    )
                else:
                    result = guided_sweep.run(
                        path / "capture",
                        plan,
                        gate,
                        mode=request["meter_mode"],
                        config=request["sweep_config"],
                        operator=request["operator"],
                        prepared=request["prepared"],
                        emit=emit,
                    )
            emit(
                phase="reporting",
                prompt=None,
                current=None,
                outcome=result["execution"],
                acceptance=result["acceptance"],
                stop_reason=result.get("stop_reason"),
                point_results=result["points"],
                results=[
                    dict(
                        workflow="GUIDED",
                        execution=result["execution"],
                        acceptance=result["acceptance"],
                        completed_points=result["completed_points"],
                        requested_points=result["requested_points"],
                    )
                ],
            )
            guided_report.publish(
                path / "capture",
                path / "report",
                plot=request["plots"],
                include_pdf=request.get("include_pdf"),
            )
            emit(phase="finished", error=None)
            return
        if request.get("mode") == "physical":
            from . import operator_reference

            operator_reference.run(path, request, emit, lock_fd=lock_fd)
            return
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
    parser.add_argument("--lock-fd", type=int)
    args = parser.parse_args()
    worker(args.job, lock_fd=args.lock_fd)
