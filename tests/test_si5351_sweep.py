"""Control/1 Si5351 contract and HP integration, without RF or instrument I/O."""

import json
import time
from copy import deepcopy
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile

import pytest
import test_guided_sweep
from test_pico_sweep import FIXTURE, PicoWire, setup_injected

from hp437b import (
    guided_report,
    guided_sweep,
    live_sweep_review,
    operator_jobs,
    pico_sweep,
    pico_tone,
    sweep_matrix,
)
from hp437b import reporting as r
from hp437b.pico_tone import CONTRACT, CONTROL, TONE
from hp437b.si5351_tone import DRIVES, ENGINE, PROFILE_ID, Si5351Tone
from hp437b.workflow_report import _seal

local_http_server = test_guided_sweep.local_http_server

FIXTURE = {**FIXTURE, "fixture": "Si5351 CLK0 coax directly to the 8482A"}
PREPARED = dict.fromkeys(pico_sweep.SI5351_PREPARED, True)
TARGET_ID = sweep_matrix.SI5351_TARGET
CARRIER = 14_097_100
# Above JavaScript's safe integer range, so a round trip through event evidence
# would show any conversion through floating point.
REMOTE = 2**53 + 117


class Si5351Wire(PicoWire):
    def __init__(self):
        super().__init__()
        self.saved = self.active = 8
        self.requests, self.status_queries = [], []
        self.refuse_2m = False
        self.lose_start = False
        self.lose_receipt = False
        self.lose_stop_reply = False
        self.shutdown_failed = False
        self.drift_on_restart = False
        self.readback_output = 0
        self.other = {"preserved": True}

    def settings(self, drive):
        return dict(
            reference_hz=25_000_000,
            reference_source="external_xa",
            crystal_load_pf=None,
            address=96,
            drive_ma=drive,
            transmit_output=0,
            loopback_output=None,
            loopback_input_gp=None,
            rf_gate_gp=None,
            rf_gate_active_high=True,
            reference_use="measurement_only",
            trusted_uncertainty_ppb=None,
            manual_correction_ppb=0,
            automatic_calibration=False,
        )

    def realization(self, carrier):
        return dict(
            requested_nhz=str(carrier * 10**9),
            programmed_nhz=str(carrier * 10**9 + 1),
            increment=None,
            nominal_sample_hz=None,
            quantization_bound_nhz="1",
            correction=None,
        )

    def status_receipt(self):
        envelope = dict(
            contract=CONTRACT,
            schema="test-tone-status",
            target=self.binding,
            receipt="known",
            job=deepcopy(self.tone),
            observation_monotonic_ns=str(REMOTE + 20),
            current=dict(
                engine=ENGINE,
                saved_drive_ma=self.saved,
                boot_drive_ma=self.active,
                output_active=self.running,
                owned=self.running,
            ),
        )
        return envelope

    def reply(self, request):
        path = request["path"]
        method = request["method"]
        body = json.loads(request["body"]) if request["body"] else None
        revision = str(self.rev)
        self.requests.append((method, path, body, request["if_match"]))
        result = dict(contract=CONTRACT)
        if path == CONTROL + "capabilities":
            _, _, result = super().reply(request)
            feature = result["test_tone"]
            feature.pop("drive_ma")
            feature.update(
                active_engine=ENGINE,
                minimum_duration_ms=10,
                maximum_duration_ms=120_000,
                engines={ENGINE: {"drive_ma": list(DRIVES)}},
            )
        elif path == CONTROL + "status":
            _, _, result = super().reply(request)
            result["job"]["boot_id"] = self.binding["boot_id"]
        elif path == CONTROL + "message-schedule":
            return super().reply(request)
        elif path == CONTROL + "si5351":
            result.update(
                schema="si5351",
                target=self.binding,
                saved=self.settings(self.saved),
                boot_active=self.settings(self.active),
                execution_engine=ENGINE,
                pending_restart=self.saved != self.active,
                physically_qualified=True,
                storage_healthy=True,
                qualification={"profile_id": PROFILE_ID},
            )
        elif path == CONTROL + "config":
            result["config"] = dict(
                enabled=False,
                si5351=self.settings(self.saved),
                other=self.other,
            )
        elif path == CONTROL + "config/update":
            assert method == "POST" and request["if_match"] == revision and not self.running
            assert body["target"] == self.binding and body["mode"] == "merge"
            settings = body["config"]["si5351"]
            assert body["config"] == {"si5351": self.settings(settings["drive_ma"])}
            self.saved = settings["drive_ma"]
            self.saved_drives.append(self.saved)
            self.rev += 1
            return 202, str(self.rev), result
        elif path == CONTROL + "restart":
            if self.drift_on_restart:
                self.other["preserved"] = False
            return super().reply(request)
        elif path == TONE + "review":
            assert body["target"] == self.binding and method == "POST"
            tone = body["tone"]
            assert set(tone) == {"engine", "duration_ms", "carrier_hz", "proposed_drive_ma"}
            assert tone["engine"] == ENGINE and 10 <= tone["duration_ms"] <= 120_000
            drive, carrier = tone["proposed_drive_ma"], tone["carrier_hz"]
            refused = self.refuse_2m and carrier == 144_490_500
            result.update(
                schema="test-tone-review",
                target=self.binding,
                assessment_revision=revision,
                admission="refused"
                if refused
                else "ready"
                if drive == self.active
                else "requires_restart",
                reasons=["unqualified_frequency_not_permitted"] if refused else [],
                requires_restart=drive != self.active,
                proposed_drive_ma=drive,
                boot_drive_ma=self.active,
                saved_drive_ma=self.saved,
                engine=ENGINE,
                execution_engine=ENGINE,
                profile_id=PROFILE_ID,
                rf_pin=None,
                transmit_output=0,
                reference_hz=25_000_000,
                minimum_duration_ms=10,
                maximum_duration_ms=120_000,
                realization=self.realization(carrier),
            )
        elif path == TONE + "start":
            assert method == "POST" and request["if_match"] == revision and not self.running
            assert body["target"] == self.binding
            tone = body["tone"]
            assert set(tone) == {"engine", "carrier_hz", "duration_ms", "expected_drive_ma"}
            assert tone["engine"] == ENGINE and tone["expected_drive_ma"] == self.active
            self.jobs.append((tone["carrier_hz"], self.active))
            self.running = True
            self.tone = dict(
                job_id=f"{len(self.jobs):032x}",
                request_id=body["request_id"],
                carrier_hz=tone["carrier_hz"],
                duration_ms=tone["duration_ms"],
                boot_drive_ma=self.active,
                engine=ENGINE,
                execution_engine=ENGINE,
                profile_id=PROFILE_ID,
                rf_pin=None,
                transmit_output=0,
                reference_hz=25_000_000,
                phase="running",
                outcome=None,
                control_revision=f'"tone:{len(self.jobs)}:1"',
                admission_revision=revision,
                output_inactive_confirmed=False,
                recovery_required=False,
                inactivity_basis="si5351_register_shutdown",
                accepted_monotonic_ns=str(REMOTE),
                launch_monotonic_ns=str(REMOTE + 10),
                ended_monotonic_ns=None,
                pad_readback=None,
                synthesis_readback=dict(
                    stage="verified",
                    epoch="1",
                    observed_monotonic_ns=str(REMOTE + 5),
                    drive_ma=self.active,
                    transmit_output=self.readback_output,
                    reference_hz=25_000_000,
                ),
                realization=self.realization(tone["carrier_hz"]),
            )
            if self.lose_start:
                raise TimeoutError("Start reply was lost after dispatch")
            return 202, self.tone["control_revision"], self.status_receipt()
        elif path.startswith(TONE + "status?"):
            query = parse_qs(urlsplit(path).query)
            assert query.pop("device_id") == [self.device]
            assert query.pop("boot_id") == [self.binding["boot_id"]]
            assert query in (
                {"request_id": [self.tone["request_id"]]},
                {"job_id": [self.tone["job_id"]]},
            )
            self.status_queries.append(query)
            if self.lose_receipt or self.lose_stop_at == len(self.jobs):
                raise TimeoutError("Native status unavailable")
            return 200, self.tone["control_revision"], self.status_receipt()
        elif path == TONE + "stop":
            assert method == "POST" and body["target"] == self.binding
            assert body["job_id"] == self.tone["job_id"]
            assert request["if_match"] == self.tone["control_revision"]
            self.running = self.shutdown_failed
            self.tone.update(
                phase="terminal",
                outcome="failed" if self.running else "stopped",
                output_inactive_confirmed=not self.running,
                recovery_required=self.running,
                ended_monotonic_ns=str(REMOTE + 18),
                control_revision=f'"tone:{len(self.jobs)}:2"',
            )
            if self.lose_stop_reply:
                raise TimeoutError("Stop reply was lost after dispatch")
            # Running observations occur before Stop's terminal observation.
            return 200, self.tone["control_revision"], self.status_receipt()
        else:
            pytest.fail(f"Unexpected operation: {method} {path}")
        if self.tone is not None and self.tone["phase"] == "running":
            assert not self.running or path == CONTROL + "status"
        return 200, revision, result

    def exchange(self, requests, deadline_ns, *, target=None):
        identity, replies = super().exchange(requests, deadline_ns, target=target)
        for _, _, reply in replies:
            if reply.get("receipt") == "known" and reply["job"]["phase"] == "running":
                reply["observation_monotonic_ns"] = str(REMOTE + 12)
        return identity, replies


def deadline():
    return time.monotonic_ns() + 10**10


def point(drive=8):
    return live_sweep_review.Point("P050", "20m", CARRIER - 1500, CARRIER, drive)


def reviewed(source, *, pdf=False):
    return live_sweep_review.review(
        source,
        TARGET_ID,
        fixture_digest=r.digest(r.encoded(FIXTURE)),
        timing=pico_sweep.TIMING,
        tolerance_hz=1,
        include_pdf=pdf,
    )


def run(tmp_path, source, review, *, pdf=False, continue_from=None):
    return pico_sweep.run(
        source,
        tmp_path / "capture",
        sweep_matrix.si5351_plan(guided_sweep.example()),
        FIXTURE,
        tmp_path / "locks",
        PREPARED,
        review.digest,
        operator="Lee Bussy [AA0NT]",
        include_pdf=pdf,
        continue_from=continue_from,
    )


def test_continuation_carries_sealed_prefix_and_measures_only_remaining_drives(
    tmp_path, monkeypatch
):
    wire = Si5351Wire()
    setup_injected(monkeypatch, wire)
    source = Si5351Tone(wire, TARGET_ID)
    reply = wire.reply
    timeouts = []

    def fail_before_start(request):
        result = reply(request)
        if request["path"] == TONE + "review" and len(wire.jobs) == 40 and len(timeouts) < 2:
            timeouts.append(request["path"])
            raise TimeoutError("Pre-Start review unavailable")
        return result

    monkeypatch.setattr(wire, "reply", fail_before_start)
    earlier = tmp_path / "earlier"
    partial = run(earlier, source, reviewed(source))
    assert partial["execution"] == "failed"
    assert partial["completed_points"] == len(wire.jobs) == 40
    assert len(timeouts) == 2 and wire.saved == wire.active == 8 and not wire.running

    source = Si5351Tone(wire, TARGET_ID)
    fresh = reviewed(source)
    latest = tmp_path / "latest"
    full = run(latest, source, fresh, continue_from=earlier / "capture")
    assert full["execution"] == "completed"
    assert full["completed_points"] == len(wire.jobs) == 56
    assert full["points"][:40] == partial["points"][:40]
    assert [drive for _, drive in wire.jobs[40:]] == [6, 6, *([8] * 14)]
    record, _, _ = guided_sweep.load(latest / "capture")
    assert record["continuation"]["carried_points"] == 40
    assert wire.active == wire.saved == 8 and not wire.running
    assert (latest / "capture/zero/diagnostics.json").is_file()
    assert not (latest / "capture/P040").exists()
    assert (latest / "capture/P041/terminal.json").is_file()


@pytest.mark.parametrize("include_pdf", [False, True])
def test_full_si5351_matrix_and_report(tmp_path, monkeypatch, local_http_server, include_pdf):
    if include_pdf:
        pytest.importorskip("reportlab")
        pypdf = pytest.importorskip("pypdf")
    wire = Si5351Wire()
    setup_injected(monkeypatch, wire)
    status_timeouts = []
    readiness_timeouts = []
    launch_timeouts = []
    reply = wire.reply

    def transient_timeouts(request):
        result = reply(request)
        ninth_job = {"job_id": [f"{9:032x}"]}
        if (
            request["path"].startswith(TONE + "status?")
            and wire.status_queries.count(ninth_job) == 9
            and wire.status_queries[-1] == ninth_job
            and not status_timeouts
        ):
            status_timeouts.append(request["path"])
            raise TimeoutError("Lost the status reply after the second retained reading")
        if request["path"] == TONE + "review" and len(wire.jobs) == 40 and not readiness_timeouts:
            readiness_timeouts.append(request["path"])
            raise TimeoutError("Lost the ready review before Start")
        if (
            request["path"].startswith(TONE + "status?")
            and len(wire.jobs) == 53
            and not launch_timeouts
        ):
            launch_timeouts.append(request["path"])
            raise TimeoutError("Lost the running status after Start")
        return result

    monkeypatch.setattr(wire, "reply", transient_timeouts)
    from hp437b.guided_client import Client
    from hp437b.report_delivery import verify

    wire.config = pico_tone.UsbHost(
        "bench", "/bench/usb_installer.py", "a" * 64, "1" * 16, wire.device
    )

    class Process:
        code = None

        def poll(self):
            return self.code

    process = Process()
    popen = operator_jobs.subprocess.Popen

    def spawn(command, *args, **kwargs):
        if command[1:3] == ["-m", "hp437b.operator_jobs"]:
            return process
        return popen(command, *args, **kwargs)

    monkeypatch.setattr(operator_jobs.subprocess, "Popen", spawn)
    monkeypatch.setattr(pico_tone, "UsbLink", lambda config: wire)
    root = tmp_path / "jobs"
    manager = operator_jobs.Jobs(
        root,
        sweep_config=FIXTURE,
        plots=include_pdf,
        workflow_lock_root=tmp_path / "locks",
        live_review_targets={
            TARGET_ID: live_sweep_review.ReviewTarget(
                Si5351Tone(wire, TARGET_ID), pico_sweep.TIMING, 1
            )
        },
    )
    try:
        server, *_ = local_http_server(manager)
        client = Client(f"http://127.0.0.1:{server.server_port}")
        assert client.state()["guided"]["live_si5351_schema"] == sweep_matrix.SI5351_SCHEMA
        review = client.review_live(TARGET_ID, include_pdf=include_pdf)
        state = client.start(
            sweep_matrix.si5351_plan(
                {**guided_sweep.example(), "name": "WsprryPico on Raspberry Pico 2W"}
            ),
            operator="Lee Bussy [AA0NT]",
            meter_mode="physical",
            prepared=PREPARED,
            include_pdf=include_pdf,
            pico_review_digest=review["review_digest"],
        )
        assert state["phase"] == "starting" and state["total"] == 56
        job_path = root / state["job_id"]
        operator_jobs.worker(job_path)
        process.code = 0
        state = client.state()["jobs"][0]
        assert state["phase"] == "finished" and state["pdf_ready"] is include_pdf
    finally:
        process.code = 0
        manager.close()
    capture = job_path / "capture"
    record, result, _ = guided_sweep.load(capture)
    assert result["execution"] == "completed", result.get("stop_reason")
    assert result["completed_points"] == result["requested_points"] == 56
    assert len(status_timeouts) == 1
    assert len(readiness_timeouts) == 1
    assert len(launch_timeouts) == 1
    assert wire.status_queries.count({"job_id": [f"{9:032x}"]}) == 10
    assert wire.jobs == [
        (dial + 1500, drive) for drive in DRIVES for dial in sweep_matrix.SI5351_DIALS.values()
    ]
    assert wire.saved_drives == [2, 4, 6, 8] and wire.restart_count == 4
    assert wire.saved == wire.active == 8 and not wire.running
    assert wire.other == {"preserved": True}
    assert (
        len({body["request_id"] for _, path, body, _ in wire.requests if path == TONE + "start"})
        == 56
    )
    for job, dial in zip(
        result["points"],
        (x for _ in DRIVES for x in sweep_matrix.SI5351_DIALS.values()),
        strict=True,
    ):
        assert job["carrier_hz"] == dial + 1500 and job["samples"] == 2
    tone = json.loads((capture / "P001" / "tone.json").read_text())
    assert tone["accepted"]["job"]["accepted_monotonic_ns"] == str(REMOTE)
    conductor = json.loads((capture / "P001" / "samples.csv.session.json").read_text())
    assert conductor["sensor_correction"]["status_checked"] is True
    assert not list((tmp_path / "locks").glob("*.json"))
    report = job_path / "report"
    assert guided_report.validate_pair(capture, report)
    page = (report / "report.html").read_text()
    output = "QRP Labs Si5351A Synthesizer and 25MHz TCXO module"
    assert output in page
    assert "Fixture: Si5351 CLK0 coax directly to the 8482A" in page
    assert "Unfiltered GPIO" not in page and "Si5351 clock harmonics" not in page
    if include_pdf:
        verify(job_path / "report.zip")
        with ZipFile(job_path / "report.zip") as package:
            instructions = package.read("START-HERE.txt")
            assert b"Si5351 CLK0" in instructions and b"operator-confirmed" not in instructions
        pdf = pypdf.PdfReader(report / "report.pdf")
        assert output in pdf.pages[0].extract_text()
        assert len(pdf.pages[0].images) == 2
        assert sum(p.extract_text().count("144490500") for p in pdf.pages) == 4
        assert "Si5351 clock harmonics" in " ".join(p.extract_text() for p in pdf.pages)
    else:
        assert not (report / "report.pdf").exists()

    # Recompute the inventory after substituting a valid-looking foreign receipt.
    # Import must reject the native binding even if all file hashes still agree.
    window_path = capture / "P001" / "rf-window.json"
    window = json.loads(window_path.read_text())
    window["brackets"][0]["before"]["receipt"]["job"]["job_id"] = "a" * 32
    window_path.write_bytes(r.encoded(window))
    (capture / "artifacts.json").unlink()
    _seal(capture, {key: record[key] for key in ("schema", "mode", "run_id")})
    with pytest.raises(ValueError, match="receipt lost"):
        guided_sweep.load(capture)


def test_2m_refusal_prevents_any_mutation_or_meter_access(tmp_path):
    wire = Si5351Wire()
    wire.refuse_2m = True
    source = Si5351Tone(wire, TARGET_ID)
    review = reviewed(source)
    refusals = [row for row in review.dispositions if row.reason]
    assert [(row.point.band, row.point.drive_ma, row.reason) for row in refusals] == [
        ("2m", drive, "unqualified_frequency_not_permitted") for drive in DRIVES
    ]
    with pytest.raises(ValueError, match="admitted matrix"):
        run(tmp_path, source, review)
    assert not (tmp_path / "capture").exists()
    assert all(method == "GET" or path == TONE + "review" for method, path, *_ in wire.requests)


@pytest.mark.parametrize("duration", [10, 120_000])
def test_duration_and_uncertain_start_stop_reconcile_exactly_once(duration):
    wire = Si5351Wire()
    wire.lose_start = wire.lose_stop_reply = True
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    assessment = source.assess(target, point(), duration)
    tone = source.start(target, point(), duration, "a" * 32, assessment)
    assert source.observe(tone.job, deadline()).active
    assert source.stop(tone.job, deadline()).output_inactive
    assert wire.status_queries == [
        {"request_id": ["a" * 32]},
        {"job_id": [tone.job.job_id]},
        {"job_id": [tone.job.job_id]},
    ]
    assert [path for _, path, *_ in wire.requests].count(TONE + "start") == 1
    assert [path for _, path, *_ in wire.requests].count(TONE + "stop") == 1
    with pytest.raises(ValueError, match="fresh Pico tone request"):
        source.start(target, point(), duration, "a" * 32, assessment)


def test_unknown_start_never_tries_another_start_or_restart():
    wire = Si5351Wire()
    wire.lose_start = wire.lose_receipt = True
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    assessment = source.assess(target, point(), 107_000)
    with pytest.raises(TimeoutError):
        source.start(target, point(), 107_000, "a" * 32, assessment)
    with pytest.raises(ValueError, match="closed prior job"):
        source.start(target, point(), 107_000, "b" * 32, assessment)
    assert len(wire.jobs) == 1
    assert wire.status_queries == [{"request_id": ["a" * 32]}]


@pytest.mark.parametrize("duration, drive", [(9, 8), (120_001, 8), (10.0, 8), (10, 12)])
def test_local_refusal_does_not_send_invalid_review(duration, drive):
    wire = Si5351Wire()
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    with pytest.raises(ValueError, match="Invalid Pico tone"):
        source.assess(target, point(drive), duration)
    assert not any(method == "POST" for method, *_ in wire.requests)


def test_wrong_synthesis_readback_and_failed_shutdown_are_not_credited():
    wire = Si5351Wire()
    wire.readback_output = 1
    wire.shutdown_failed = True
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    assessment = source.assess(target, point(), 107_000)
    tone = source.start(target, point(), 107_000, "a" * 32, assessment)
    with pytest.raises(ValueError, match="synthesis readback"):
        source.observe(tone.job, deadline())
    assert not source.stop(tone.job, deadline()).output_inactive
    assert source.terminal_receipt is None
    assert source.last_stop_receipt["job"]["recovery_required"] is True
    with pytest.raises(ValueError, match="closed prior job"):
        source.start(target, point(), 107_000, "b" * 32, assessment)


def test_drive_restart_is_scoped_and_detects_unrelated_drift():
    wire = Si5351Wire()
    wire.drift_on_restart = True
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    with pytest.raises(ValueError, match="after restart"):
        source.change_drive(target, 6, deadline())
    assert wire.saved == wire.active == 6
    assert wire.restart_count == 1 and not wire.jobs


def test_shutdown_failure_preserves_pending_work_and_excludes_unconfirmed_samples(
    tmp_path, monkeypatch
):
    wire = Si5351Wire()
    wire.shutdown_failed = True
    setup_injected(monkeypatch, wire)
    # The deliberately unclosed RF window can stop without wall-clock waiting.
    source = Si5351Tone(wire, TARGET_ID)
    review = reviewed(source)
    result = run(tmp_path, source, review)
    assert result["execution"] == "failed"
    assert "independent shutdown" in result["stop_reason"]
    assert result["requested_points"] == 56 and result["completed_points"] == 0
    assert result["points"][0]["samples"] == 0 and result["points"][0]["mean_W"] is None
    assert wire.saved_drives == [2] and len(wire.jobs) == 1
    pending = list((tmp_path / "locks").glob("*.json"))
    assert len(pending) == 2
    assert any(json.loads(path.read_text())["phase"] == "tone-outcome-pending" for path in pending)
    capture = tmp_path / "capture"
    failed = json.loads((capture / "P001" / "shutdown-unconfirmed.json").read_text())
    assert failed["job"]["recovery_required"] is True
    report = tmp_path / "report"
    guided_report.publish(capture, report, plot=False, include_pdf=False)
    assert guided_report.validate_pair(capture, report)
    assert "independent shutdown" in (report / "report.html").read_text()


def test_status_contention_leaves_the_identified_stop_budget(monkeypatch):
    import subprocess
    import threading
    from types import SimpleNamespace

    from hp437b.live_sweep_window import ActiveWindow

    wire = Si5351Wire()
    status_started = threading.Event()
    stop_sent = threading.Event()

    def dispatch(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        if any(row["path"].startswith(TONE + "status?") for row in payload["requests"]):
            status_started.set()
            assert not stop_sent.wait(kwargs["timeout"])
            raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
        if any(row["path"] == TONE + "stop" for row in payload["requests"]):
            stop_sent.set()
        result = wire.exchange(payload["requests"], deadline(), target=payload["target"])
        return SimpleNamespace(returncode=0, stdout=r.encoded(result))

    monkeypatch.setattr(pico_tone.subprocess, "run", dispatch)
    host = pico_tone.UsbHost("bench", "/bench/usb_installer.py", "a" * 64, "1" * 16, wire.device)
    source = Si5351Tone(pico_tone.UsbLink(host), TARGET_ID)
    target = source.snapshot(TARGET_ID)
    settings = point()
    duration = pico_sweep.TIMING.tone_ms
    tone = source.start(
        target, settings, duration, "a" * 32, source.assess(target, settings, duration)
    )
    finished = threading.Event()

    def observe():
        try:
            source.observe(tone.job, deadline())
        except TimeoutError:
            finished.set()

    thread = threading.Thread(target=observe)
    with ActiveWindow(
        source, target, settings, tone.job, pico_sweep.TIMING, tone.hard_end_ns, lambda: False
    ) as window:
        thread.start()
        assert status_started.wait(2)
        window.request_stop()
        assert stop_sent.wait(5)
    thread.join(1)
    assert finished.is_set() and window.stop_observation.output_inactive


def test_malformed_start_reply_reconciles_the_same_request(monkeypatch):
    wire = Si5351Wire()
    original = wire.reply

    def malformed(request):
        code, revision, reply = original(request)
        if request["path"] == TONE + "start":
            reply["job"]["engine"] = "pio-dma-gp2"
        return code, revision, reply

    monkeypatch.setattr(wire, "reply", malformed)
    source = Si5351Tone(wire, TARGET_ID)
    target = source.snapshot(TARGET_ID)
    duration = 107_000
    tone = source.start(
        target, point(), duration, "a" * 32, source.assess(target, point(), duration)
    )
    assert wire.status_queries == [{"request_id": ["a" * 32]}]
    assert len(wire.jobs) == 1
    assert source.stop(tone.job, deadline()).output_inactive


def test_remote_status_deadline_releases_usb_lock(tmp_path):
    import hashlib
    import subprocess
    import sys

    installer = tmp_path / "usb_installer.py"
    installer.write_text(
        """
from contextlib import contextmanager
from pathlib import Path
import time

@contextmanager
def device_lock(serial):
    try:
        yield
    finally:
        Path(__file__).with_name("lock-released").touch()

def selected(serial, role):
    return {"device_id": "1" * 32}

class Management:
    def __init__(self, device):
        self.hello = {"target": device}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        assert exc[0] is TimeoutError

    def exchange(self, row):
        assert row["method"] == "GET" and row["path"].startswith("/api/control/v1/test-tone/status?")
        time.sleep(10)
"""
    )
    data = dict(
        short_status=True,
        target=None,
        requests=[pico_tone.request("GET", TONE + "status?request_id=" + "a" * 32)],
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            pico_tone._USB_CALL,
            str(installer),
            hashlib.sha256(installer.read_bytes()).hexdigest(),
            "1" * 16,
            "1" * 32,
        ],
        input=r.encoded(data),
        capture_output=True,
        timeout=5,
        check=False,
    )
    assert result.returncode != 0 and b"tone status deadline expired" in result.stderr
    assert (tmp_path / "lock-released").is_file()
