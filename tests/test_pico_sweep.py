import functools
import json
from dataclasses import replace

import pytest

from hp437b import (
    guided_report,
    guided_sweep,
    live_sweep_review,
    operator_jobs,
    pico_pilot,
    pico_sweep,
    pico_tone,
    sweep_matrix,
)
from hp437b import reporting as r
from hp437b.pico_tone import CONTRACT, CONTROL, DRIVES, TONE, PicoTone
from hp437b.simulation import DemoTransport

FIXTURE = dict(
    resource="USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_2.0::0::INSTR",
    meter_serial="TEST 437B",
    sensor_serial="MY41094127",
    fixture="Direct GP2 coax to 8482A",
    known_issues=[],
)
PREPARED = dict.fromkeys(pico_sweep.PREPARED, True)


class PicoWire:
    """Exercise production Control/1 request and reply validation without USB or RF."""

    def __init__(self):
        self.device, self.boot, self.rev = "1" * 32, 1, 1
        self.saved = self.active = 12
        self.tone = None
        self.running = False
        self.jobs = []
        self.saved_drives = []
        self.restart_count = 0
        self.lose_restart = True
        self.lose_stop_at = None

    @property
    def binding(self):
        return dict(scope="member", device_id=self.device, boot_id=f"{self.boot:032x}")

    def exchange(self, requests, deadline_ns, *, target=None):
        assert deadline_ns > 0
        assert target in (None, self.binding)
        before = self.binding
        replies = [self.reply(request) for request in requests]
        return before, replies

    def reply(self, request):
        path, method = request["path"], request["method"]
        rev = str(self.rev)
        body = json.loads(request["body"]) if request["body"] else {}
        code = 200
        response = dict(contract=CONTRACT)
        if path == CONTROL + "capabilities":
            response["test_tone"] = dict(
                available=True,
                schema="test-tone",
                drive_ma=list(DRIVES),
                carrier_units="Hz",
                carrier_reference="absolute",
                duration_units="ms",
                **{
                    operation: TONE + operation
                    for operation in ("review", "start", "status", "stop")
                },
            )
        elif path == CONTROL + "status":
            response.update(
                job=dict(
                    state="running" if self.running else "empty",
                    owner_id="test" if self.running else None,
                    output_active=self.running,
                ),
                standalone=dict(enabled=False),
            )
        elif path == CONTROL + "message-schedule":
            response.update(target=self.binding, saved=None)
        elif path == CONTROL + "gpio-drive":
            if method == "PUT":
                assert not self.running and self.active == self.saved and request["if_match"] == rev
                assert body["target"] == self.binding
                self.saved = body["gpio_drive_ma"]
                self.saved_drives.append(self.saved)
                self.rev += 1
                rev = str(self.rev)
            response.update(
                schema="gpio-drive",
                target=self.binding,
                execution_engine="pio-dma-gp2",
                rf_gp=2,
                storage_healthy=True,
                application_error=None,
                saved=self.saved,
                boot_active=self.active,
                pending_restart=self.saved != self.active,
            )
        elif path == CONTROL + "restart":
            assert method == "POST" and request["if_match"] == rev and self.saved != self.active
            self.boot += 1
            self.restart_count += 1
            self.active = self.saved
            self.tone = None
            self.rev += 1
            if self.lose_restart:
                self.lose_restart = False
                raise TimeoutError("USB dropped after restart")
            code = 202
            response["restart_requested"] = True
        elif path == TONE + "review":
            assert self.saved == self.active and not self.running and body["target"] == self.binding
            proposal = body["tone"]
            carrier, drive = proposal["carrier_hz"], proposal["proposed_drive_ma"]
            response.update(
                schema="test-tone-review",
                target=self.binding,
                assessment_revision=rev,
                admission="ready" if drive == self.active else "requires_restart",
                proposed_drive_ma=drive,
                boot_drive_ma=self.active,
                saved_drive_ma=self.saved,
                reasons=[],
                maximum_duration_ms=120000,
                rf_pin=2,
                realization=dict(
                    requested_nhz=str(carrier * 10**9),
                    programmed_nhz=str(carrier * 10**9),
                    quantization_bound_nhz="1",
                ),
            )
        else:
            if path == TONE + "start":
                assert (
                    not self.running
                    and request["if_match"] == rev
                    and body["target"] == self.binding
                )
                new = body["tone"]
                assert new["expected_drive_ma"] == self.active
                self.running = True
                self.rev += 1
                self.jobs.append((new["carrier_hz"], self.active))
                self.tone = dict(
                    job_id=f"{len(self.jobs):032x}",
                    request_id=body["request_id"],
                    carrier_hz=new["carrier_hz"],
                    boot_drive_ma=self.active,
                    duration_ms=new["duration_ms"],
                    rf_pin=2,
                    control_revision="job-etag",
                    phase="running",
                    outcome=None,
                    recovery_required=False,
                    output_inactive_confirmed=False,
                    launch_monotonic_ns="10",
                    ended_monotonic_ns="0",
                    pad_readback=dict(
                        stage="verified",
                        drive_ma=self.active,
                        rf_pin=2,
                        epoch="1",
                        observed_monotonic_ns="3",
                    ),
                )
                code = 202
            elif path == TONE + "stop":
                assert body["job_id"] == self.tone["job_id"] and request["if_match"] == "job-etag"
                if self.lose_stop_at == len(self.jobs):
                    raise TimeoutError("Stop unavailable")
                self.running = False
                self.tone.update(
                    phase="terminal",
                    outcome="stopped",
                    output_inactive_confirmed=True,
                    ended_monotonic_ns="20",
                )
            else:
                assert path.startswith(TONE + "status?")
            response.update(
                schema="test-tone-status",
                receipt="known",
                target=self.binding,
                job=dict(self.tone),
                current=dict(output_active=self.running, owned=self.running),
                observation_monotonic_ns="4",
            )
        return code, rev, response


def setup_injected(monkeypatch, wire, *, limited=False):
    class Meter(DemoTransport):
        metadata = {"transport": "test fixture"}
        capabilities = DemoTransport.capabilities | {"go_to_local"}

        def open(self, timeout):
            assert not wire.running

        def write(self, data, deadline):
            if data == b"TR3":
                # Healthy closure follows source Stop. Unknown-stop tests deliberately fail.
                if wire.lose_stop_at is None:
                    assert not wire.running
            elif data.startswith(b"KB"):
                assert not wire.running
            else:
                super().write(data, deadline)

        def read(self, deadline):
            if self.pending == b"*IDN?":
                self.pending = None
                return b"HEWLETT-PACKARD,437B,,2.0\r\n"
            if self.pending == b"TR2":
                self.pending = None
                if wire.running:
                    if limited and len(wire.jobs) == 1:
                        return b"+90.000E-09\r\n"
                    return f"+{(wire.active * 2 + len(wire.jobs) / 50):06.3f}E-03\r\n".encode()
                return b"-90.000E-09\r\n"
            return super().read(deadline)

        def return_local(self, deadline):
            pass

    monkeypatch.setattr(pico_pilot, "VisaTransport", lambda resource: Meter())
    monkeypatch.setattr(pico_sweep, "_matching_usb", lambda serial: None)

    def zero(path, *args):
        path.mkdir()
        (path / "diagnostics.json").write_text(
            json.dumps(
                dict(
                    status="completed",
                    transport_closed=True,
                    zero_assessment=dict(accepted_full_case=True),
                )
            )
        )

    monkeypatch.setattr(pico_pilot, "zero_meter", zero)
    collect = pico_pilot.collect
    monkeypatch.setattr(pico_pilot, "collect", functools.partial(collect, sleep=lambda _: None))

    # Avoid waiting for a genuine 107 second watchdog in the unknown-stop test.
    if wire.lose_stop_at:
        monkeypatch.setattr(
            pico_sweep,
            "TIMING",
            replace(pico_sweep.TIMING, read_ms=10, stop_ms=20, startup_ms=100, spacing_ms=1000),
        )


def run(tmp_path, wire, *, pdf=False, cancelled=lambda: False, stale=False, continue_from=None):
    source = PicoTone(wire, "pico-gpio")
    plan = sweep_matrix.pico_plan(guided_sweep.example())
    review = live_sweep_review.review(
        source,
        source.target_id,
        fixture_digest=r.digest(r.encoded(FIXTURE)),
        timing=pico_sweep.TIMING,
        tolerance_hz=1,
        include_pdf=pdf,
    )
    return pico_sweep.run(
        source,
        tmp_path / "capture",
        plan,
        FIXTURE,
        tmp_path / "locks",
        PREPARED,
        "0" * 64 if stale else review.digest,
        include_pdf=pdf,
        continue_from=continue_from,
        cancelled=cancelled,
    )


def test_pico_matrix_52_real_request_sequences_and_traceable_report(tmp_path, monkeypatch):
    wire = PicoWire()
    setup_injected(monkeypatch, wire)
    result = run(tmp_path, wire, pdf=True)
    assert result["completed_points"] == result["requested_points"] == 52
    assert result["attempted_points"] == 52 and result["execution"] == "completed"
    assert wire.jobs == [
        (dial + 1500, drive) for drive in DRIVES for dial in sweep_matrix.DIALS.values()
    ]
    assert wire.saved_drives == [2, 4, 8, 12] and wire.restart_count == 4
    assert wire.active == wire.saved == 12 and not wire.running
    assert not list((tmp_path / "locks").glob("*.json"))
    try:
        import reportlab  # noqa: F401
    except ImportError:
        pytest.skip("PDF dependency optional")
    report = tmp_path / "report"
    guided_report.publish(tmp_path / "capture", report, include_pdf=True)
    assert (report / "report.pdf").is_file()
    assert guided_report.validate_pair(tmp_path / "capture", report)


def test_limited_and_interrupted_rows_restore_original_drive(tmp_path, monkeypatch):
    wire = PicoWire()
    setup_injected(monkeypatch, wire, limited=True)
    result = run(tmp_path, wire, cancelled=lambda: len(wire.jobs) == 1 and not wire.running)
    assert result["execution"] == "interrupted"
    assert result["limited_points"] == 1 and result["completed_points"] == 0
    assert result["points"][0]["mean_dBm"] is None and result["not_reached_points"] == 51
    assert wire.saved_drives == [2, 12] and not wire.running
    assert not list((tmp_path / "locks").glob("*.json"))


def test_stale_review_cannot_allocate_hardware_or_change_drive(tmp_path, monkeypatch):
    wire = PicoWire()
    setup_injected(monkeypatch, wire)
    with pytest.raises(ValueError, match="latest live review"):
        run(tmp_path, wire, stale=True)
    assert not wire.saved_drives and not wire.jobs
    assert not (tmp_path / "capture").exists()


def test_unknown_stop_keeps_both_resources_blocked_and_does_not_restore(tmp_path, monkeypatch):
    wire = PicoWire()
    wire.lose_stop_at = 1
    setup_injected(monkeypatch, wire)
    result = run(tmp_path, wire)
    assert result["execution"] == "failed" and result["attempted_points"] == 1
    assert wire.saved_drives == [2] and len(list((tmp_path / "locks").glob("*.json"))) == 2


def test_continuation_reuses_earlier_sealed_points_without_rekeying(tmp_path, monkeypatch):
    wire = PicoWire()
    setup_injected(monkeypatch, wire)
    first_path = tmp_path / "first"
    first = run(first_path, wire, cancelled=lambda: len(wire.jobs) == 3 and not wire.running)
    original = first_path / "capture"
    manifest = (original / "artifacts.json").read_bytes()
    assert first["completed_points"] == 3
    second_path = tmp_path / "second"
    second = run(second_path, wire, continue_from=original)
    assert second["completed_points"] == 52 and len(wire.jobs) == 52
    assert second["points"][:3] == first["points"][:3]
    assert (original / "artifacts.json").read_bytes() == manifest
    assert (second_path / "capture/prior/artifacts.json").read_bytes() == manifest


def test_usb_bridge_retries_only_read_only_requests(monkeypatch):
    from types import SimpleNamespace

    member = dict(scope="member", device_id="1" * 32, boot_id="2" * 32)
    host = pico_tone.UsbHost(
        "bench", "/bench/usb_installer.py", "a" * 64, "1" * 16, member["device_id"]
    )
    attempts = []

    def command(*args, **kwargs):
        attempts.append(json.loads(kwargs["input"]))
        if len(attempts) == 2:
            return SimpleNamespace(
                returncode=0, stdout=json.dumps([member, [[200, "revision", {}]]]).encode()
            )
        return SimpleNamespace(returncode=255)

    monkeypatch.setattr(pico_tone.subprocess, "run", command)
    link = pico_tone.UsbLink(host)
    now = pico_tone.time.monotonic_ns()
    link.exchange([pico_tone.request("POST", TONE + "review")], now + 5 * 10**9)
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    with pytest.raises(ValueError, match="SSH transport"):
        link.exchange([pico_tone.request("POST", TONE + "start")], now + 5 * 10**9)
    assert len(attempts) == 3


def test_operator_start_runs_pico_worker_and_exports_sealed_capture(tmp_path, monkeypatch):
    wire = PicoWire()
    wire.config = pico_tone.UsbHost(
        "bench", "/bench/usb_installer.py", "a" * 64, "1" * 16, wire.device
    )
    source = PicoTone(wire, "pico-gpio")
    setup_injected(monkeypatch, wire)
    monkeypatch.setattr(pico_tone, "UsbLink", lambda config: wire)

    class Process:
        code = None

        def poll(self):
            return self.code

    process = Process()
    popen = operator_jobs.subprocess.Popen

    def capture_worker(command, *args, **kwargs):
        if command[1:3] == ["-m", "hp437b.operator_jobs"]:
            return process
        return popen(command, *args, **kwargs)

    monkeypatch.setattr(operator_jobs.subprocess, "Popen", capture_worker)
    root = tmp_path / "jobs"
    jobs = operator_jobs.Jobs(
        root,
        plots=False,
        sweep_config=FIXTURE,
        workflow_lock_root=tmp_path / "locks",
        live_review_targets={
            "pico-gpio": live_sweep_review.ReviewTarget(source, pico_sweep.TIMING, 1)
        },
    )
    try:
        plan = sweep_matrix.pico_plan(guided_sweep.example())
        with pytest.raises(ValueError, match="Review all 52"):
            jobs.start_guided(plan, None, "physical", PREPARED)
        reviewed = jobs.review_live_guided("pico-gpio", None, False)
        state = jobs.start_guided(
            plan, None, "physical", PREPARED, pico_review_digest=reviewed["review_digest"]
        )
        assert state["phase"] == "starting" and state["total"] == 52
        path = root / state["job_id"]
        try:
            operator_jobs.worker(path)
        finally:
            process.code = 0
        state = jobs.state()["jobs"][0]
        assert state["phase"] == "finished" and state["outcome"] == "completed"
        assert state["report_ready"] and not state["pdf_ready"]
        assert guided_report.validate_pair(path / "capture", path / "report")
    finally:
        jobs.close()
