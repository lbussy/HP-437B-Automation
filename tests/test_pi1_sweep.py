import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from hp437b import pi1_meter as hp
from hp437b import pi1_owner as pi
from hp437b import pi1_report as report
from hp437b import pi1_sweep as sweep
from hp437b import reporting as r
from hp437b.errors import OperationTimeout
from hp437b.reconciliation import _lease
from hp437b.simulation import status_fixture
from hp437b.transport import VisaTransport

BANK = {"drive": 3, "hysteresis": True, "slew": False}
OFF = {
    "gpclk_enabled": False,
    "gpclk_busy": False,
    "gpio_input": True,
    "owned": False,
    "mux": "INPUT",
}
ON = {**{key: not value for key, value in OFF.items()}, "mux": "ALT5"}
SOURCE = {
    **pi.TARGET,
    "device": "1" * 32,
    "boot": "2" * 32,
    "revision": "3" * 40,
    "executable": "4" * 64,
    "station": "5" * 64,
    "capabilities": pi.CAPABILITIES,
}
FIXTURE = {
    "signal_path": "Contained load on GPIO20 with isolated DC path to the HP 8482A",
    "maximum_indication_w": "0.010",
    "peak_w": "0.100",
    "dc_v": "0",
    "shutdown": "Unplug the Pi supply",
    "confirm": dict.fromkeys(sweep.CONFIRM, True),
}


class Bench:
    def __init__(self, root):
        self.root = root
        (root / "tmp").mkdir()
        self.ns = 100 * sweep.NS
        self.now = 1000
        self.ops = []
        self.source = dict(SOURCE)
        self.overrides = {}
        self.group = None
        self.tone = None
        self.stops = 0
        self.generation = 0
        self.starts = 0
        self.zero_count = 0
        self.meter_contact = 0
        self.meter_commands = []
        self.raw = b"+3.0100E-03\r\n"
        self.blocked = None
        self.zero_fault = False
        self.run = None
        self.stop_signal = threading.Event()
        self.controller = sweep.Controller(
            pi.Owner(command=self.ssh, clock=self.clock),
            meter=self.meter,
            zero=self.zero,
            root=root,
            clock=self.clock,
            sleep=self.sleep,
            wall=lambda: self.now,
            emit=lambda _: None,
        )

    def path(self, name):
        return self.root / "tmp" / name

    def clock(self):
        return self.ns

    def sleep(self, seconds):
        self.ns += int(seconds * sweep.NS)

    def admit(self, point):
        requested = point["carrier_hz"] * 10**9
        return {
            "carrier_hz": point["carrier_hz"],
            "drive_code": point["drive_ma"] // 2 - 1,
            "ppm_millionths": 0,
            "policy": "uncalibrated",
            "lower_nhz": requested - 500,
            "upper_nhz": requested + 500,
            "deadline_ms": 50_000,
            "plan": r.digest(r.encoded(point)),
            "refusal": None,
        }

    def ssh(self, argv, *, input, timeout, **kwargs):
        assert argv == pi.SSH and 0 < timeout <= 3
        request = json.loads(input)
        assert request["contract"] == pi.CONTRACT
        operation = request["operation"]
        self.ops.append(operation)
        self.sleep(0.0001)
        try:
            receipt = self.owner(operation, request)
            if operation in self.overrides:
                receipt = self.overrides[operation](receipt, request)
        except subprocess.TimeoutExpired:
            raise
        if receipt is None:
            return subprocess.CompletedProcess(argv, 127, b"", b"fake stderr")
        reply = {
            "contract": pi.CONTRACT,
            "operation": operation,
            "request_sha256": r.digest(input),
            "receipt": receipt,
        }
        return subprocess.CompletedProcess(argv, 0, r.encoded(reply), b"")

    def owner(self, op, req):
        fields = {
            **OFF,
            "bank": BANK,
            "service": sweep.SERVICE,
            **{key: self.source[key] for key in ("boot", "device")},
            "run": req.get("run"),
        }
        if op == "review":
            return self.source
        assert req["source"] == self.source
        if op == "admit":
            return self.admit(req["point"])
        if op == "claim":
            assert self.run is None and req["lifetime_ms"] == sweep.RUN_S * 1000
            self.run = req["run"]
            return {**fields, "run": self.run, "exclusive": True, "durable": True}
        assert self.run == req["run"]
        if op == "admit_matrix":
            return {
                **{key: fields[key] for key in sweep.OWNER_FIELDS},
                "admissions": [self.admit(point) for point in req["points"]],
            }
        if op == "open_group":
            assert self.group is None and self.tone is None
            pending = sweep.json_file(self.controller.auth / "source-pending.json")
            assert (pending["run"], pending["instance"]) == (self.run, req["instance"])
            self.group = req["instance"]
            self.generation = 0
            return {
                **fields,
                "instance": self.group,
                "drive_code": req["drive_code"],
                "listen": "127.0.0.1",
                "port": 43146,
                "ancillary_off": True,
                "lifetime_ms": req["lifetime_ms"],
            }
        if op == "release":
            assert self.group is None and self.tone is None
            self.run = None
            return {**fields, "run": req["run"], "released": True}
        assert self.group == req["instance"]
        if op == "close_group":
            assert self.tone is None
            self.group = None
            return {**fields, "instance": req["instance"], "exited": True}
        if op == "start":
            assert self.tone is None
            assert req["duration_ms"] == pi.TONE_MS
            assert req["admission"] == self.admit(req["point"])
            pending = sweep.json_file(self.controller.auth / "source-pending.json")
            assert pending["request"] == req["request"] and pending["phase"] == "start-pending"
            self.starts += 1
            self.generation += 1
            plan = req["admission"]
            self.tone = {
                **fields,
                "instance": self.group,
                "request": req["request"],
                "generation": self.generation,
                "revision": 1,
                "phase": "accepted",
                "plan": plan["plan"],
                "drive_code": plan["drive_code"],
                "gpio": 20,
                "clock": "GPCLK0",
                "cutoff_ms": pi.TONE_MS,
            }
            return self.tone
        assert self.tone and self.tone["request"] == req["request"]
        assert req["generation"] in (None, self.generation)
        if op == "status":
            return {
                **self.tone,
                **ON,
                "phase": "active",
                "revision": 2,
                "bank": {**BANK, "drive": self.tone["drive_code"]},
            }
        if op == "stop":
            assert threading.current_thread() is not threading.main_thread()
            self.stops += 1
            result = {**self.tone, **OFF, "phase": "terminal", "revision": 3}
            self.tone = None
            self.stop_signal.set()
            return result
        raise AssertionError(op)

    def meter(self):
        self.meter_contact += 1
        return hp.Meter(transport=lambda _: Wire(self), match=lambda _: None, clock=self.clock)

    def zero(self, output, lock_root, run, cancelled):
        assert not cancelled() and self.group is None and self.tone is None
        lock, mark = sweep._meter_paths(lock_root)
        assert sweep.json_file(mark)["phase"] == "zero-pending"
        with pytest.raises(BlockingIOError, match="Unresolved Pi"):
            with _lease(lock):
                pass
        with _lease(lock, pi_sweep_run=run):
            self.zero_count += 1
            if self.zero_fault:
                raise ValueError("Fake ZERO failed")
            Path(output).mkdir()
            (output / "diagnostics.json").write_bytes(
                r.encoded(
                    {
                        "schema": "hp437b.diagnostics.physical.v1",
                        "status": "completed",
                        "supervised_zero_profile": True,
                        "supervised_cal_profile": False,
                        "transport_closed": True,
                        "zero_assessment": {"accepted_full_case": True},
                        "target": {"resource": hp.RESOURCE},
                        "equipment_labels": {
                            "meter_serial": hp.METER_SERIAL,
                            "sensor_serial": sweep.SENSOR_SERIAL,
                        },
                    }
                )
            )

    def review(self):
        return self.controller.review(FIXTURE, self.path("review.json"))

    def start(self, name="capture", **kwargs):
        auth = sweep.json_file(self.path("review.json"))["authorization"]
        return self.controller.start(self.path("review.json"), auth, self.path(name), **kwargs)


class Wire:
    capabilities = frozenset({"write", "read", "eom", "go_to_local"})

    def __init__(self, bench):
        self.bench = bench
        self.pending = None
        self.factor = b"99.0"
        self.logarithmic = True

    def open(self, timeout, *, preflight):
        assert 0 < timeout <= 2
        preflight()

    def write(self, data, deadline):
        self.bench.meter_commands.append(data)
        if data.startswith(b"KB") and data.endswith(b"EN"):
            assert self.bench.tone is None
            self.factor = data[2:-2]
        elif data == b"LN":
            self.logarithmic = False
        else:
            self.pending = data

    def read(self, deadline):
        operation = self.pending
        self.pending = None
        if operation == b"TR1":
            if not self.bench.tone:
                return b"-1.7000E-07\r\n"
            if self.bench.blocked:
                return self.bench.blocked()
            raw = self.bench.raw
            return raw() if callable(raw) else raw
        if operation == b"SM":
            return status_fixture(logarithmic=self.logarithmic)
        if operation == b"*IDN?":
            return hp.IDN + b"\r\n"
        if operation == b"KBOD":
            return b"CAL FAC " + self.factor + b" %\r\n"
        raise AssertionError(operation)

    def return_local(self, deadline):
        assert self.bench.tone is None
        self.bench.meter_commands.append(b"GTL")

    def close(self):
        self.bench.meter_commands.append(b"CLOSE")


@pytest.fixture
def bench(tmp_path):
    return Bench(tmp_path)


def test_complete_cli_full_matrix_and_reexport(bench, capsys):
    assert sweep.main(["plan"], controller=bench.controller) == 0
    plan = json.loads(capsys.readouterr().out)
    assert len(plan["requested_points"]) == 80
    assert [row["drive_ma"] for row in plan["requested_points"][::10]] == list(range(2, 17, 2))
    assert [row["carrier_hz"] for row in plan["requested_points"][:10]] == [
        475700,
        1838100,
        3570100,
        5366200,
        7040100,
        10140200,
        14097100,
        18106100,
        21096100,
        28126100,
    ]
    assert bench.ops == []
    bench.path("fixture.json").write_bytes(r.encoded(FIXTURE))
    assert (
        sweep.main(
            [
                "review",
                "--fixture",
                str(bench.path("fixture.json")),
                "--output",
                str(bench.path("review.json")),
            ],
            controller=bench.controller,
        )
        == 0
    )
    saved = json.loads(capsys.readouterr().out)
    assert set(bench.ops) == {"review", "admit"}
    assert bench.zero_count == bench.meter_contact == 0
    assert (
        sweep.main(
            [
                "start",
                "--review",
                str(bench.path("review.json")),
                "--authorize",
                saved["authorization"],
                "--output",
                str(bench.path("capture")),
            ],
            controller=bench.controller,
        )
        == 0
    )
    assert bench.ops.count("open_group") == bench.ops.count("close_group") == 8
    assert bench.starts == bench.stops == 80
    assert bench.zero_count == bench.meter_contact == 1
    assert bench.meter_commands.count(b"TR1") == 4 * 80 + 6
    assert b"TR2" not in bench.meter_commands
    assert bench.meter_commands[-3:] == [b"TR3", b"GTL", b"CLOSE"]
    assert bench.run is bench.group is bench.tone is None
    result, rows, _ = report.load(bench.path("capture"))
    assert sum(row["samples"] for row in rows) == 160
    assert rows[0]["cal_fac_percent"] == "100.7" and rows[0]["dbm"] == pytest.approx(4.785665)
    assert len(result["pre"]) == len(result["post"]) == 3
    assert (
        sweep.main(
            [
                "report",
                "--capture",
                str(bench.path("capture")),
                "--output",
                str(bench.path("report")),
            ],
            controller=bench.controller,
        )
        == 0
    )
    assert (
        report.publish(bench.path("capture"), bench.path("report2"))["coverage"]["measured"] == 80
    )
    assert (bench.path("report") / "index.html").read_text().count("<tr>") >= 81
    assert len((bench.path("capture") / "readings.csv").read_text().splitlines()) == 161
    with pytest.raises(ValueError, match="replay"):
        bench.start("elsewhere")
    assert bench.starts == 80


@pytest.mark.parametrize("ppm, band", [(-76332300, "630m"), (-71997500, "160m")])
def test_low_band_native_refusal(bench, ppm, band):
    def refuse(value, req):
        value.update(policy="selected", ppm_millionths=ppm)
        if req["point"]["band"] == band:
            value.update(
                lower_nhz=None,
                upper_nhz=None,
                deadline_ms=None,
                plan=None,
                refusal="BCM2835 fractional divider is outside the native window",
            )
        return value

    bench.overrides["admit"] = refuse
    assert sum(row["refusal"] is not None for row in bench.review()["admissions"]) == 8
    with pytest.raises(ValueError, match="refused"):
        bench.start()
    assert bench.meter_contact == bench.starts == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "another Pi"),
        ("gpio", 4),
        ("service_pid", False),
        ("service_enabled", "enabled"),
        ("capabilities", []),
        ("boot", "n/a"),
    ],
)
def test_unqualified_source_never_enters_prepare(bench, field, value):
    bench.source[field] = value
    with pytest.raises(ValueError):
        bench.review()
    assert bench.ops == ["review"]
    assert bench.zero_count == bench.meter_contact == 0


def test_installed_pilot_cannot_supply_owner_contract(bench):
    bench.overrides["review"] = lambda *_: None
    with pytest.raises(OSError, match="unavailable"):
        bench.review()
    assert bench.ops == ["review"]


@pytest.mark.parametrize("fault", ["expired", "station", "matrix", "token", "changed-plan", "busy"])
def test_review_binding_prevents_unsafe_start(bench, fault):
    bench.review()
    saved = sweep.json_file(bench.path("review.json"))
    if fault == "expired":
        bench.now += sweep.REVIEW_TTL_S
    elif fault == "station":
        bench.source["station"] = "6" * 64
    elif fault == "matrix":
        saved["review"]["plan"]["requested_points"].reverse()
    elif fault == "token":
        saved["review"]["fixture"]["signal_path"] = "edited"
    elif fault == "changed-plan":

        def change(value, _):
            value["admissions"][0]["plan"] = "e" * 64
            return value

        bench.overrides["admit_matrix"] = change
    bench.path("review.json").write_bytes(r.encoded(saved))
    if fault == "changed-plan":
        assert bench.start()["status"] == "partial"
    elif fault == "busy":
        with _lease(bench.controller.auth / "source.lock"), pytest.raises(BlockingIOError):
            bench.start()
    else:
        with pytest.raises(ValueError):
            bench.start()
    assert bench.zero_count == bench.meter_contact == bench.starts == 0


def test_zero_failure_persists_meter_marker_across_output_paths(bench):
    bench.review()
    bench.zero_fault = True
    capture = bench.start()
    assert capture["status"] == "partial" and bench.starts == bench.meter_contact == 0
    assert report.load(bench.path("capture"))[1][0]["state"] == "not reached"
    lock, marker = sweep._meter_paths(bench.controller.locks)
    assert marker.exists()
    with pytest.raises(BlockingIOError), _lease(lock):
        pytest.fail("Unrelated physical workflow bypassed the marker")


@pytest.mark.parametrize(
    "raw, matched",
    [
        (b"+9.0000E+40\r\n", "failed"),
        (b"+2.0000E-02\r\n", "failed"),
        (b"+0.5000E-06\r\n", "limited"),
    ],
)
def test_raw_error_reviewed_bound_and_limited_report(bench, raw, matched):
    bench.raw = raw
    bench.review()
    run = bench.start()
    _, rows, _ = report.load(bench.path("capture"))
    assert rows[0]["state"] == matched
    assert rows[0]["dbm"] is None
    if matched == "failed":
        assert bench.stops == bench.starts == 1 and rows[1]["state"] == "not reached"
        assert run["points"][0]["samples"][0]["raw_hex"] == raw.hex()
        assert run["source_cleanup"]["verified"]
        assert run["meter_cleanup"]["status"] == ("unverified" if b"+40" in raw else "accepted")
    else:
        assert rows[0]["sample_w"] == ["5.000E-7", "5.000E-7"]


@pytest.mark.parametrize(
    "fault",
    [
        "lost-start",
        "lost-stop",
        "stale-instance",
        "wrong-drive",
        "wrong-clock",
        "bank-restore",
        "external-bank-change",
        "process-cleanup",
        "status-timeout",
        "cancel",
    ],
)
def test_failure_progression_and_native_cleanup(bench, fault):
    def fail(*_):
        raise subprocess.TimeoutExpired("fake-ssh", 1)

    cancelled = threading.Event()
    if fault == "lost-start":
        bench.overrides["start"] = fail
    elif fault == "lost-stop":
        bench.overrides["stop"] = fail
    elif fault == "status-timeout":
        bench.overrides["status"] = fail
    elif fault == "cancel":
        bench.blocked = lambda: (cancelled.set(), b"+3.0100E-03\r\n")[1]
    else:
        op, patch = {
            "stale-instance": ("status", {"instance": "7" * 32}),
            "wrong-drive": ("status", {"bank": {**BANK, "drive": 6}}),
            "wrong-clock": ("status", {"clock": "GPCLK2"}),
            "bank-restore": ("close_group", {"bank": {**BANK, "drive": 5}}),
            "external-bank-change": ("close_group", {"bank": {**BANK, "hysteresis": False}}),
            "process-cleanup": ("close_group", {"exited": False}),
        }[fault]
        bench.overrides[op] = lambda value, req: {**value, **patch}
    bench.review()
    run = bench.start(cancelled=cancelled.is_set)
    assert run["status"] == "partial"
    assert bench.starts in (1, 10) and bench.starts == bench.stops
    assert bench.ops.count("close_group") == 1
    _, rows, _ = report.load(bench.path("capture"))
    assert rows[-1]["state"] == "not reached"
    if fault in ("bank-restore", "external-bank-change", "process-cleanup"):
        assert rows[0]["state"] == "measured"
        assert (bench.controller.auth / "source-pending.json").exists()
    if fault in ("lost-start", "status-timeout", "stale-instance", "wrong-drive", "wrong-clock"):
        assert not run["points"][0]["samples"]


def test_independent_stop_during_blocked_meter(bench):
    cancelled = threading.Event()

    def blocked():
        cancelled.set()
        assert bench.stop_signal.wait(1)
        return b"+3.0100E-03\r\n"

    bench.blocked = blocked
    bench.review()
    run = bench.start(cancelled=cancelled.is_set)
    assert run["status"] == "partial"
    assert bench.starts == bench.stops == 1
    row = run["points"][0]
    assert row["rf_confirmed"] and row["stop"]["receipt"]["phase"] == "terminal"
    assert "watts" not in row["samples"][0]


def test_rehashed_capture_window_tamper_is_rejected(bench):
    bench.review()
    bench.start()
    capture = bench.path("capture")
    run = sweep.json_file(capture / "workflow.json")
    run["points"][0]["samples"][0]["after"]["receipt"]["generation"] = 6
    sweep.checkpoint(capture / "workflow.json", run)
    (capture / "artifacts.json").unlink()
    report._seal(capture, {"schema": sweep.SCHEMA, "mode": "physical", "run": run["run"]})
    with pytest.raises(ValueError, match="changed RF window"):
        report.publish(capture, bench.path("report"))
    assert not bench.path("report").exists()


def test_refuses_unsealed_capture(bench):
    bench.path("crash").mkdir()
    (bench.path("crash") / "workflow.json").write_text("{}")
    with pytest.raises(ValueError):
        report.publish(bench.path("crash"), bench.path("report"))


def test_export_pdf_uses_shared_renderer(bench):
    pytest.importorskip("reportlab")
    bench.review()
    bench.start()
    out = bench.path("report-pdf")
    report.publish(bench.path("capture"), out, pdf=True)
    assert (out / "report.pdf").read_bytes().startswith(b"%PDF-")
    assert sweep.json_file(out / "metadata.json")["pdf"]["page_count"] >= 2


def test_unstable_fails_without_keeping_sample_or_rekey(bench):
    readings = iter((b"+1.0000E-03\r\n", b"+2.0000E-03\r\n", b"+3.0000E-03\r\n"))
    bench.raw = lambda: next(readings)
    bench.review()
    run = bench.start()
    assert run["points"][0]["error"].endswith("settling indications did not agree")
    assert bench.starts == bench.stops == 1
    assert len(run["points"][0]["samples"]) == 3
    assert report.load(bench.path("capture"))[1][0]["samples"] == 0


def test_service_change_between_groups_blocks_next_start(bench):
    def changed(value, req):
        bench.source["service_enabled"] = "enabled"
        return value

    bench.overrides["close_group"] = changed
    bench.review()
    run = bench.start()
    assert bench.starts == bench.stops == 10
    assert run["status"] == "partial"
    assert run["points"][10]["state"] == "not reached"
    assert (bench.controller.auth / "source-pending.json").exists()


def test_source_disconnect_leaves_both_recovery_markers(bench):
    def disconnected(value, req):
        raise OSError("Injected SSH disconnect")

    bench.overrides.update(stop=disconnected, close_group=disconnected)
    bench.review()
    run = bench.start()
    assert run["points"][0]["state"] == "failed" and bench.starts == 1
    assert not run["source_cleanup"]["verified"]
    assert (bench.controller.auth / "source-pending.json").exists()
    assert sweep._meter_paths(bench.controller.locks)[1].exists()


def test_loss_before_start_reply_stops_by_pending_identity(bench):
    def lost_reply(value, request):
        raise subprocess.TimeoutExpired("fake-owner", 1)

    bench.overrides["start"] = lost_reply
    bench.review()
    run = bench.start()
    row = run["points"][0]
    assert row["start_attempted"] and row["dispatch_pending"] and not row["rf_confirmed"]
    assert "ack" not in row and row["stop"]["receipt"]["request"] == row["request"]
    assert bench.starts == bench.stops == 1
    assert report.load(bench.path("capture"))[1][0]["samples"] == 0


def test_report_refuses_cross_run_owner_receipt_even_if_rehashed(bench):
    bench.review()
    bench.start()
    capture = bench.path("capture")
    record = sweep.json_file(capture / "workflow.json")
    record["points"][0]["stop"]["receipt"]["run"] = "f" * 32
    sweep.checkpoint(capture / "workflow.json", record)
    (capture / "artifacts.json").unlink()
    report._seal(capture, {"schema": sweep.SCHEMA, "mode": "physical", "run": record["run"]})
    with pytest.raises(ValueError, match="Wrong run, device, or boot"):
        report.publish(capture, bench.path("report"))


def test_storage_failure_keeps_source_shutdown_ahead_of_finalization(bench, monkeypatch):
    checkpoint = sweep.checkpoint
    failed = False

    def fail_after_stop(path, data):
        nonlocal failed
        if path.name == "workflow.json" and bench.stops and not failed:
            assert bench.tone is None
            failed = True
            raise OSError("Fake checkpoint I/O failure")
        checkpoint(path, data)

    bench.review()
    monkeypatch.setattr(sweep, "checkpoint", fail_after_stop)
    run = bench.start()
    assert bench.starts == bench.stops == 1
    assert run["status"] == "partial"
    assert run["source_cleanup"]["verified"]
    assert run["meter_cleanup"]["status"] == "accepted"
    assert report.load(bench.path("capture"))[1][0]["state"] == "measured"


def _slow_usb_descriptor():
    time.sleep(30)


def test_usb_identity_preflight_respects_worker_deadline():
    wire = VisaTransport(hp.RESOURCE)
    with pytest.raises(OperationTimeout):
        wire.open(1, preflight=_slow_usb_descriptor)
    assert wire._process is None
