"""Fixed invalid numeric-entry hypotheses; no hardware or claimed meter model."""

import subprocess
import sys

import pytest
from test_diagnostics_err_selection import Clock
from test_diagnostics_lifecycle import RESOURCE, events, run

from hp437b import diagnostics_err_selection as selection
from hp437b.commands import encode
from hp437b.instrument import Instrument
from hp437b.simulation import status_fixture

SETTINGS = dict(frequency="0.0500GZ", cal_factor="100.0%")


class NumericModel:
    capabilities = frozenset({"write", "read", "eom"})

    def __init__(self, mode, clock):
        self.mode, self.clock = mode, clock
        self.events = self.entry = self.error = 0
        self.since = 0
        self.writes = []

    def write(self, raw, deadline):
        assert raw in (b"FR-3GZ", b"SM", b"ERR?", b"*ESR?", b"*STB?", b"*ESE?", b"*SRE?")
        self.writes.append(raw)
        self.pending = raw
        if raw == b"FR-3GZ":
            self.events = (
                32
                if self.mode == "wrong_event"
                else 144
                if self.mode == "power_on_event"
                else 48
                if self.mode == "mixed_event"
                else 16
            )
            self.entry = self.error = 0 if self.mode == "event_only" else 82
            self.since = self.clock.now
        if self.mode == "err_discards" and raw == b"ERR?":
            self.entry = 0
        if self.mode == "esr_discards" and raw == b"*ESR?":
            self.entry = 0

    def read(self, deadline):
        code = self.pending
        if code == b"*ESR?":
            value = self.events
            if self.mode != "sticky_event":
                self.events = 0
        elif code == b"ERR?":
            value = self.error if self.mode in ("numeric", "sticky_err") else 0
            if self.mode == "numeric":
                self.error = 0
        elif code == b"SM":
            raw = bytearray(status_fixture(logarithmic=False))
            visible = self.mode != "delayed" or self.clock.now - self.since >= 1
            raw[2:4] = f"{self.entry if visible else 0:02d}".encode()
            if visible and self.mode != "persistent_entry":
                self.entry = 0
            return bytes(raw)
        else:
            value = 0
        return f"{value:03d}\r\n".encode()


def numeric_collect(monkeypatch, mode):
    clock = Clock()
    monkeypatch.setattr(selection, "time", clock)
    wire = NumericModel(mode, clock)
    rows = selection.plan(numeric_entry=True)
    status, assessment = selection.collect(
        Instrument(wire),
        rows,
        0,
        numeric_entry=True,
        before_step=lambda _: None,
        after_step=lambda: None,
        on_row=lambda _: None,
        raw_reply=lambda: b"",
    )
    return status, assessment, wire, rows


def numeric_run(tmp_path, **overrides):
    args = dict(lifecycle=False, numeric_entry=True, numeric_original_settings=SETTINGS)
    args.update(overrides)
    return run(tmp_path, **args)


def test_plan_is_same_bounded_ordering_with_only_fixed_invalid_frequency():
    rows = selection.plan(numeric_entry=True)
    assert len(rows) == 64 == len({r["step_id"] for r in rows})
    assert [r["fixture_hex"] for r in rows if r["kind"] == "stimulus"] == [b"FR-3GZ".hex()] * 5
    assert [r["phase"] for r in rows if r["kind"] == "stimulus"] == list(selection.CASES)
    assert sum(r["kind"] == "wait" for r in rows) == 2
    with pytest.raises(ValueError):
        encode("FR", -3, unit="GZ")
    with pytest.raises(ValueError):
        encode("QX")


@pytest.mark.parametrize(
    "mode", ["event_only", "excludes_entry", "err_discards", "esr_discards", "delayed", "numeric"]
)
def test_models_record_numeric_visibility_without_assuming_err_selects_it(monkeypatch, mode):
    status, result, wire, rows = numeric_collect(monkeypatch, mode)
    assert status == "completed" and all(row["status"] == "completed" for row in rows)
    assert result["fixed_fixture"] == "FR-3GZ" and result["expected_event_bit"] == 16
    assert "unresolved" in result["cause"] and result["queue_observation"].startswith("not_tested")
    assert wire.entry == 0 and wire.writes.count(b"FR-3GZ") == 5
    assert len(wire.writes) == 62  # No command is sent during either pause.
    cases = result["cases"]
    assert all(case["esr_replies"] == [16, 0] for case in cases.values())
    if mode == "event_only":
        assert all(not case["expected_numeric_code_observed"] for case in cases.values())
    elif mode == "delayed":
        assert cases["sm_first"]["sm_entry_errors"] == [0, 0]
        assert cases["delayed_sm_first"]["sm_entry_errors"] == [82, 0]
    else:
        assert cases["sm_first"]["sm_entry_errors"] == [82, 0]
    if mode == "numeric":
        assert cases["err_first"]["err_replies"] == [82, 0, 0]
    else:
        assert cases["err_first"]["err_replies"] == [0, 0, 0]
    if mode == "err_discards":
        assert cases["err_first"]["sm_entry_errors"] == [0, 0]
    if mode == "esr_discards":
        assert cases["esr_first"]["sm_entry_errors"] == [0, 0]


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("wrong_event", "documented_execution_error_event_not_observed"),
        ("mixed_event", "unexpected_or_persistent_error_event_no_further_stimulus"),
        ("power_on_event", "unexpected_or_persistent_error_event_no_further_stimulus"),
        ("sticky_event", "unexpected_or_persistent_error_event_no_further_stimulus"),
        ("persistent_entry", "source_or_active_error_not_clear_after_status_pair"),
        ("sticky_err", "error_reply_not_quiet_no_further_stimulus"),
    ],
)
def test_unexpected_or_persistent_conditions_stop_after_one_numeric_stimulus(
    monkeypatch, mode, reason
):
    status, result, wire, rows = numeric_collect(monkeypatch, mode)
    assert status == "observation_stop" and result["stop_reason"] == reason
    assert wire.writes.count(b"FR-3GZ") == 1
    assert result["stopped_after_phase"] == "sm_first"
    assert not result["cases"]["delayed_sm_first"]["complete"]
    assert result["cases"]["delayed_sm_first"]["err_replies"] == []


@pytest.mark.parametrize(
    "scenario,status",
    [
        ("healthy", "completed"),
        ("entry_errors_invisible", "completed"),
        ("fixture_ignored", "observation_stop"),
        ("nonzero_mask", "observation_stop"),
        ("preexisting_error", "observation_stop"),
        ("preexisting_event", "observation_stop"),
        ("changed_units", "observation_stop"),
        ("unexpected_source_on", "observation_stop"),
        ("status_does_not_clear", "observation_stop"),
        ("malformed", "query_failed"),
    ],
)
def test_numeric_profile_through_spawned_bridge_preserves_ownership_and_cleanup(
    tmp_path, scenario, status
):
    result, trace = numeric_run(tmp_path, scenario=scenario)
    assert result["status"] == status and result["transport_closed"]
    assert (
        result["numeric_entry_profile"]
        and not result["err_selection_profile"]
        and not result["lifecycle_profile"]
    )
    assert result["numeric_original_settings"] == SETTINGS
    assert result["numeric_settings_verified"] is False
    assert result["lifecycle_assessment"]["accepted_full_case"] is (status == "completed")
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert set(writes) <= {
        "*IDN?",
        "*ESE?",
        "*SRE?",
        "*STB?",
        "*ESR?",
        "ERR?",
        "SM",
        "FR-3GZ",
        "TR3",
    }
    assert ("TR3" in writes) is (status != "query_failed")
    if status == "completed":
        assert writes.count("FR-3GZ") == 5 and len(result["queries"]) == 64
        assert all(row["accepted_before_deadline"] for row in result["queries"])
    if scenario in ("preexisting_error", "preexisting_event", "nonzero_mask"):
        assert "FR-3GZ" not in writes


@pytest.mark.parametrize(
    "overrides",
    [
        {"confirmed_error_fixtures": False},
        {"numeric_entry": 1},
        {"lifecycle": True},
        {"err_selection": True},
        {"include_latched_reads": True},
        {"numeric_original_settings": None},
        {"numeric_original_settings": {}},
        {"numeric_original_settings": {"frequency": "0.0500GZ"}},
        {"numeric_original_settings": {"frequency": "0.0500GZ", "cal_factor": " "}},
        {"numeric_original_settings": {"frequency": "0.0500GZ", "cal_factor": "100%\n"}},
        {"numeric_original_settings": {"frequency": "X" * 81, "cal_factor": "100%"}},
        {"numeric_entry": False},
    ],
)
def test_numeric_confirmation_profile_and_before_settings_guards_precede_output_or_usb(
    tmp_path, overrides
):
    with pytest.raises(ValueError):
        numeric_run(tmp_path, **overrides)
    assert not (tmp_path / "trace.jsonl").exists() and not (tmp_path / "result").exists()


@pytest.mark.parametrize("deadline", [False, True])
def test_numeric_wait_parent_cancel_or_deadline_sends_no_followup_or_cleanup(tmp_path, deadline):
    path = tmp_path / "trace.jsonl"
    args = (
        dict(work_s=1, total_s=5)
        if deadline
        else dict(cancelled=lambda: sum(e.get("command") == "FR-3GZ" for e in events(path)) >= 4)
    )
    result, trace = numeric_run(tmp_path, **args)
    assert result["status"] == ("deadline" if deadline else "cancelled")
    assert not result["lifecycle_assessment"]["accepted_full_case"]
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert writes[-1] == "FR-3GZ" and writes.count("FR-3GZ") == 4
    assert "TR3" not in writes and result["transport_closed"]


@pytest.mark.parametrize(
    "flags",
    [
        ["--numeric-entry"],
        ["--numeric-entry", "--err-selection", "--confirm-fixed-error-fixtures"],
        ["--numeric-entry", "--lifecycle", "--confirm-fixed-error-fixtures"],
        ["--numeric-entry", "--include-latched-reads", "--confirm-fixed-error-fixtures"],
    ],
)
def test_numeric_cli_selection_guards_precede_setup_or_instrument(flags):
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
