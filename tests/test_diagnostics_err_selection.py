"""Countermodels for ERR=0: none is asserted to describe the physical 437B."""

import subprocess
import sys

import pytest
from test_diagnostics_lifecycle import RESOURCE, events, run

from hp437b import diagnostics_err_selection as selection
from hp437b.instrument import Instrument
from hp437b.simulation import status_fixture


class Clock:
    now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Countermodel:
    capabilities = frozenset({"write", "read", "eom"})

    def __init__(self, mode, clock):
        self.mode, self.clock = mode, clock
        self.events = 0
        self.entry = 0
        self.since = 0
        self.writes = []

    def write(self, raw, deadline):
        self.writes.append(raw)
        self.pending = raw
        if raw == b"QX":
            self.events = 32
            self.entry = 0 if self.mode == "event_only" else 91
            self.since = self.clock.now
        elif self.mode == "err_discards" and raw == b"ERR?":
            self.entry = 0
        elif self.mode == "esr_discards" and raw == b"*ESR?":
            self.entry = 0

    def read(self, deadline):
        code = self.pending
        if code == b"*ESR?":
            value, self.events = self.events, 0
        elif code == b"SM":
            raw = bytearray(status_fixture(logarithmic=False))
            visible = self.mode != "delayed" or self.clock.now - self.since >= 1
            entry = self.entry if visible else 0
            raw[2:4] = f"{entry:02d}".encode()
            if visible:
                self.entry = 0
            return bytes(raw)
        elif code == b"ERR?":
            # Three different mechanisms can reproduce the prior zero trace.
            value = self.entry if self.mode == "numeric" else 0
            if self.mode == "numeric":
                self.entry = 0
        else:
            assert code in (b"*ESE?", b"*SRE?", b"*STB?")
            value = 0
        return f"{value:03d}\r\n".encode()


def collect(monkeypatch, mode, *, after=lambda: None):
    clock = Clock()
    monkeypatch.setattr(selection, "time", clock)
    wire = Countermodel(mode, clock)
    rows = selection.plan()
    status, result = selection.collect(
        Instrument(wire),
        rows,
        clock.monotonic(),
        before_step=lambda _: None,
        after_step=after,
        on_row=lambda _: None,
        raw_reply=lambda: b"",
    )
    return status, result, wire, rows


def test_plan_is_fixed_qx_only_with_unique_steps_and_two_no_command_waits():
    rows = selection.plan()
    assert len(rows) == 64 == len({r["step_id"] for r in rows})
    assert [r["fixture_hex"] for r in rows if r["kind"] == "stimulus"] == [b"QX".hex()] * 5
    assert [r["requested_wait_s"] for r in rows if r["kind"] == "wait"] == [2.0, 2.0]
    assert {r["command"] for r in rows if r["kind"] == "query"} == {
        "SM",
        "ERR?",
        "*ESR?",
        "*ESE?",
        "*SRE?",
        "*STB?",
    }


@pytest.mark.parametrize(
    "mode", ["event_only", "sm_only", "err_discards", "esr_discards", "delayed", "numeric"]
)
def test_countermodels_remain_observations_not_causal_or_queue_claims(monkeypatch, mode):
    status, result, wire, rows = collect(monkeypatch, mode)
    assert status == "completed"
    assert all(row["status"] == "completed" for row in rows)
    assert len(wire.writes) == 62  # Waits perform no I/O.
    assert wire.entry == 0  # Finish with a delayed case, not an unobserved pending entry.
    assert "unresolved" in result["cause"] and result["queue_observation"].startswith("not_tested")
    cases = result["cases"]
    assert all(case["esr_replies"] == [32, 0] for case in cases.values())
    assert cases["sm_first"]["err_replies"] == [0, 0, 0]
    if mode == "event_only":
        assert all(case["sm_entry_errors"] == [0, 0] for case in cases.values())
    elif mode == "delayed":
        assert cases["sm_first"]["sm_entry_errors"] == [0, 0]
        assert cases["delayed_sm_first"]["sm_entry_errors"] == [91, 0]
    else:
        assert cases["sm_first"]["sm_entry_errors"] == [91, 0]
    if mode in ("event_only", "sm_only", "err_discards", "esr_discards", "delayed"):
        assert cases["esr_first"]["err_replies"] == [0, 0, 0]
    if mode in ("err_discards", "numeric"):
        assert cases["err_first"]["sm_entry_errors"] == [0, 0]
    assert cases["err_first"]["err_replies"] == ([91, 0, 0] if mode == "numeric" else [0, 0, 0])


def test_incomplete_case_is_not_a_zero_observation():
    cases = selection.assessment(selection.plan())["cases"]
    assert all(not case["complete"] and case["err_replies"] == [] for case in cases.values())


def test_wait_is_cancellable_without_new_instrument_command(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(selection, "time", clock)
    wire = Countermodel("event_only", clock)
    rows = selection.plan()

    def check():
        if clock.now >= 0.04:
            raise InterruptedError("cancelled")

    status, result = selection.collect(
        Instrument(wire),
        rows,
        0,
        before_step=lambda _: None,
        after_step=check,
        on_row=lambda _: None,
        raw_reply=lambda: b"STALE",
    )
    assert status == "query_failed" and result["stop_reason"] == "step_failed"
    assert wire.writes[-1] == b"QX" and wire.writes.count(b"QX") == 4
    failed = [row for row in rows if row["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["kind"] == "wait" and "raw_hex" not in failed[0]


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("healthy", "completed"),
        ("entry_errors_invisible", "completed"),
        ("nonzero_mask", "observation_stop"),
        ("preexisting_error", "observation_stop"),
        ("preexisting_event", "observation_stop"),
        ("fixture_ignored", "observation_stop"),
        ("status_does_not_clear", "observation_stop"),
        ("malformed", "query_failed"),
    ],
)
def test_new_profile_uses_existing_spawned_bridge_and_stop_cleanup_rules(
    tmp_path, scenario, expected
):
    result, trace = run(tmp_path, lifecycle=False, err_selection=True, scenario=scenario)
    assert result["status"] == expected
    assert result["err_selection_profile"] and not result["lifecycle_profile"]
    assert result["lifecycle_assessment"]["accepted_full_case"] is (expected == "completed")
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert "FR-3GZ" not in writes
    assert ("TR3" in writes) is (expected != "query_failed")
    assert result["transport_closed"]
    if expected == "completed":
        assert len(result["queries"]) == 64
        assert all(row["accepted_before_deadline"] for row in result["queries"])
        waits = [row for row in result["queries"] if row["kind"] == "wait"]
        assert all(row["visa_read_status"] is None and "raw_hex" not in row for row in waits)
        assert all(row["elapsed_s"] - row["started_elapsed_s"] >= 2 for row in waits)


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_error_fixtures": False},
        {"err_selection": 1},
        {"lifecycle": True},
        {"include_latched_reads": True},
    ],
)
def test_profile_confirmation_and_exclusivity_before_usb(tmp_path, overrides):
    args = dict(lifecycle=False, err_selection=True)
    args.update(overrides)
    with pytest.raises(ValueError):
        run(tmp_path, **args)
    assert not (tmp_path / "trace.jsonl").exists()


@pytest.mark.parametrize("mode", ["event_only", "err_discards", "esr_discards", "delayed"])
def test_distinct_models_match_both_prior_qx_orderings_including_zero_sm(mode):
    wire = Countermodel(mode, Clock())
    instrument = Instrument(wire)
    for queries in (("*ESR?",) * 3 + ("ERR?",) * 3, ("ERR?",) * 3 + ("*ESR?",) * 3):
        with instrument._operation() as deadline:
            instrument._write(b"QX", deadline)
        observed = [(code, instrument.query(code).value) for code in queries]
        assert [value for code, value in observed if code == "ERR?"] == [0, 0, 0]
        assert [value for code, value in observed if code == "*ESR?"] == [32, 0, 0]
        assert [instrument.query("SM").value.entry_error for _ in range(2)] == [0, 0]


@pytest.mark.parametrize("deadline", [False, True])
def test_parent_cancel_or_deadline_during_wait_sends_no_cleanup_commands(tmp_path, deadline):
    trace_path = tmp_path / "trace.jsonl"
    args = (
        dict(work_s=1, total_s=5)
        if deadline
        else dict(cancelled=lambda: sum(e.get("command") == "QX" for e in events(trace_path)) >= 4)
    )
    result, trace = run(tmp_path, lifecycle=False, err_selection=True, **args)
    assert result["status"] == ("deadline" if deadline else "cancelled")
    assert result["lifecycle_assessment"]["accepted_full_case"] is False
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes[-1] == "QX" and writes.count("QX") == 4
    assert "TR3" not in writes and result["transport_closed"]


@pytest.mark.parametrize(
    "flags",
    [
        ["--err-selection"],
        ["--err-selection", "--lifecycle", "--confirm-fixed-error-fixtures"],
        ["--err-selection", "--include-latched-reads", "--confirm-fixed-error-fixtures"],
    ],
)
def test_cli_rejects_missing_confirmation_or_combined_profiles_before_setup(flags):
    result = subprocess.run(
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
    assert result.returncode == 2 and "Traceback" not in result.stderr
