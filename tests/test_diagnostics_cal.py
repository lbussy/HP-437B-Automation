"""One CAL case reuses the accepted ZERO model and completion controls."""

import subprocess
import sys
from types import SimpleNamespace

import pytest
from test_diagnostics_lifecycle import RESOURCE, events, run
from test_diagnostics_zero import Backend

from hp437b import diagnostics_cal as cal
from hp437b import diagnostics_physical as dp
from hp437b import diagnostics_zero as zero
from hp437b.errors import OperationTimeout
from hp437b.instrument import Instrument
from hp437b.simulation import status_fixture


def cal_run(tmp_path, scenario="healthy", **overrides):
    args = dict(
        lifecycle=False,
        confirmed_error_fixtures=False,
        supervised_cal=True,
        confirmed_cal=True,
        cal_reference_factor="99",
        cal_factor_source="Synthetic sensor REF CAL FACTOR label",
        prepared=dict.fromkeys(
            (*dp.PREPARED, "direct_reference_path", "warmed_up", "zero_ready"), True
        ),
        work_s=35,
        total_s=40,
        _factory_override=Backend(tmp_path / "trace.jsonl", scenario, calibration=True),
    )
    args.update(overrides)
    return run(tmp_path, **args)


@pytest.mark.parametrize("scenario", ["healthy", "immediate", "standby"])
def test_CAL_uses_same_completion_path_one_factor_and_off_restoration(tmp_path, scenario):
    r, t = cal_run(tmp_path, scenario)
    a = r["cal_assessment"]
    assert r["status"] == "completed" and a["accepted_full_case"]
    assert (
        a["clear_baseline_observed"]
        and a["completion_indication_observed"]
        and a["post_clear_observed"]
    )
    assert a["reference_restored_off_verified"] and not a["reference_may_be_on"]
    assert r["cal_reference_factor"] == a["reference_factor"] == "99"
    assert r["transport_closed"] and r["local_return"]["status"] == "accepted"
    writes = [e["command"] for e in t if e["event"] == "write"]
    assert writes == [
        "*IDN?",
        "SM",
        "*ESE?",
        "*SRE?",
        "CS",
        "CL99EN",
        "CS",
        "SM",
        "TR1",
        "SM",
        "TR3",
    ]
    assert all(q["accepted_before_deadline"] for q in r["queries"])
    assert r["front_panel_confirmation"] == "not_provided"


@pytest.mark.parametrize(
    "scenario", ["partial_zero", "native_error", "stale_tag", "error_and_done"]
)
def test_unknown_CAL_completion_has_no_ascii_retry_or_reference_off_command(tmp_path, scenario):
    r, t = cal_run(tmp_path, scenario)
    assert r["status"] == "query_failed" and not r["cal_assessment"]["accepted_full_case"]
    assert (
        r["cal_assessment"]["cal_may_have_started"] and r["cal_assessment"]["reference_may_be_on"]
    )
    assert not r["cal_assessment"]["reference_restored_off_verified"]
    writes = [e["command"] for e in t if e["event"] == "write"]
    assert writes.count("CL99EN") == 1 and writes[-1] == "CL99EN"
    assert "ZE" not in writes and "OC0" not in writes
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in t)


def test_reference_must_be_off_after_known_CAL_completion(tmp_path):
    r, t = cal_run(tmp_path, "reference_left_on")
    assert r["status"] == "observation_stop"
    assert not r["cal_assessment"]["accepted_full_case"]
    assert not r["cal_assessment"]["reference_restored_off_verified"]
    assert r["cal_assessment"]["reference_may_be_on"]
    assert "TR1" not in [e.get("command") for e in t]


def test_cancel_pending_CAL_retains_unknown_reference_and_stops_worker(tmp_path):
    trace = tmp_path / "trace.jsonl"
    r, t = cal_run(
        tmp_path, "cancel", cancelled=lambda: any(e["event"] == "pending" for e in events(trace))
    )
    assert r["status"] == "cancelled" and r["worker"]["stopped"]
    assert not r["cal_assessment"]["accepted_full_case"]
    assert r["cal_assessment"]["reference_may_be_on"]
    assert [e["command"] for e in t if e["event"] == "write"][-1] == "CL99EN"


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_cal": False},
        {"cal_reference_factor": None},
        {"cal_reference_factor": True},
        {"cal_reference_factor": "99.05"},
        {"cal_reference_factor": "121"},
        {"cal_factor_source": ""},
        {"supervised_zero": True},
        {"include_latched_reads": True},
        {"work_s": 45, "total_s": 50},
        {"prepared": dict.fromkeys(dp.PREPARED, True)},
    ],
)
def test_CAL_context_factor_and_budget_guards_precede_open(tmp_path, overrides):
    with pytest.raises(ValueError):
        cal_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


def test_CAL_deadline_uses_manual_ten_seconds_without_ascii_abort(monkeypatch, scripted):
    clock = [100.0]
    monkeypatch.setattr(zero.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        zero.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds)
    )
    wire = scripted(
        [
            ("write", b"SM"),
            ("read", status_fixture(logarithmic=False)),
            ("write", b"*ESE?"),
            ("read", b"000\r\n"),
            ("write", b"*SRE?"),
            ("read", b"000\r\n"),
            ("write", b"CS"),
            ("write", b"CL99EN"),
        ]
    )
    polls = []

    def poll(deadline, *, cancelled):
        v = dict(
            tag=2 + len(polls),
            adapter_status_byte=0,
            capabilities_hex="",
            control_hex="010200",
            interrupt_hex="8200",
        )
        polls.append(v)
        wire.zero_poll_receipt = v
        return v

    wire.zero_poll = poll
    wire.zero_poll_receipt = None
    wire.captured_raw = b""
    status, a = cal.collect(
        Instrument(wire),
        wire,
        cal.plan("99"),
        100,
        reference_factor="99",
        deadline=135,
        before_step=lambda _: None,
        after_step=lambda: None,
        on_row=lambda _: None,
        stop=SimpleNamespace(is_set=lambda: False),
    )
    assert status == "query_failed" and not a["completion_indication_observed"]
    assert len(polls) <= 22 and clock[0] <= 110.01
    assert wire.calls[-1] == ("write", b"CL99EN") and a["reference_may_be_on"]


def test_default_ZERO_plan_is_preserved_and_CAL_has_no_valid_setting_setters():
    old = zero.plan()
    new = cal.plan("99")
    assert len(old) == len(new) == 13
    assert old[6]["command"] == "ZE" and new[6]["command"] == "CL"
    assert all(old[i] == new[i] for i in range(13) if i not in (6, 7))
    assert cal.factor_text("99.0") == "99.0"


@pytest.mark.parametrize(
    "flags",
    [
        ["--supervised-cal"],
        ["--confirm-cal"],
        ["--supervised-cal", "--supervised-zero"],
        ["--supervised-cal", "--include-latched-reads"],
    ],
)
def test_CAL_cli_guard_precedes_setup(flags):
    r = subprocess.run(
        [
            sys.executable,
            "tools/diagnose_meter.py",
            "--resource",
            RESOURCE,
            "--setup",
            "missing",
            "--output",
            "unused",
            *flags,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 2 and "Traceback" not in r.stderr


def test_CAL_followup_can_exceed_old_native_cap_and_returns_local(tmp_path):
    r, trace = cal_run(tmp_path, "slow_followup")
    assert r["status"] == "completed" and r["cal_assessment"]["accepted_full_case"]
    read = next(e for e in trace if e["event"] == "followup_read")
    assert 9000 <= read["timeout_ms"] <= 10000
    assert r["local_return"]["status"] == "accepted"
    assert r["budgets"]["native_call_s"] == 2.0
    assert r["budgets"]["cal_followup_read_s"] == 10.0
    assert all(
        e["timeout_ms"] <= 2000 for e in trace if e["event"] == "read" and e["command"] != "TR1"
    )


@pytest.mark.parametrize("scenario", ["followup_timeout", "malformed_followup"])
def test_CAL_failed_followup_returns_local_without_retry_or_new_query(tmp_path, scenario):
    r, trace = cal_run(tmp_path, scenario)
    assert r["status"] == "query_failed" and not r["cal_assessment"]["accepted_full_case"]
    assert r["cal_failed_read_shutdown"]["status"] == "accepted"
    assert r["cal_failed_read_shutdown"]["disposal_only"]
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes[-2:] == ["TR1", "TR3"]
    assert writes.count("TR1") == writes.count("CL99EN") == 1
    assert r["local_return"]["status"] == "accepted" and r["transport_closed"]
    assert next(q for q in r["queries"] if q["step_id"] == "final.SM")["status"] == "not_attempted"
    assert sum(e["event"] == "control" and e["request"] == 0xA1 for e in trace) == 1


def test_partial_followup_write_never_runs_disposal_commands(tmp_path):
    r, trace = cal_run(tmp_path, "partial_followup")
    assert r["status"] == "query_failed"
    assert "cal_failed_read_shutdown" not in r
    assert [e["command"] for e in trace if e["event"] == "write"][-1] == "TR1"
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in trace)


@pytest.mark.parametrize("scenario", ["followup_local_failed", "followup_free_run_failed"])
def test_CAL_disposal_failure_remains_failure_with_one_local_attempt(tmp_path, scenario):
    r, trace = cal_run(tmp_path, scenario)
    assert r["status"] == "cleanup_failed" and not r["cal_assessment"]["accepted_full_case"]
    assert r["cal_failed_read_shutdown"]["status"] == "failed" and r["transport_closed"]
    assert sum(e["event"] == "control" and e["request"] == 0xA1 for e in trace) == 1
    assert [e["command"] for e in trace if e["event"] == "write"][-2:] == ["TR1", "TR3"]


def test_cancelled_CAL_followup_does_not_dispatch_shutdown_io(tmp_path):
    trace = tmp_path / "trace.jsonl"
    r, t = cal_run(
        tmp_path,
        "cancel_followup",
        cancelled=lambda: any(e["event"] == "followup_pending" for e in events(trace)),
    )
    assert r["status"] == "cancelled" and r["worker"]["stopped"]
    assert [e["command"] for e in t if e["event"] == "write"][-1] == "TR1"
    assert not any(e["event"] == "control" and e["request"] == 0xA1 for e in t)


def test_followup_reserves_cleanup_before_trigger_and_clears_old_io_markers(scripted):
    wire = scripted([])
    wire.last_write_complete = wire.read_started = True
    instrument = Instrument(wire)
    import time

    with pytest.raises(OperationTimeout, match="No time for CAL followup"):
        cal._followup(instrument, wire, time.monotonic() + 15, {})
    assert wire.calls == [] and not wire.last_write_complete and not wire.read_started
