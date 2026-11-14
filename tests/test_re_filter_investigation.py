"""Competing RE/refresh models and regression of the recorded failure pattern."""

import pytest
from test_diagnostics_acquisition import Backend, Clock, Model, setting_run
from test_diagnostics_lifecycle import events

from hp437b import diagnostics_acquisition as settings
from hp437b.instrument import Instrument


def test_candidate_plan_has_no_restoration_trigger_and_records_version():
    rows = settings.plan(2)
    restore = [r for r in rows if r["phase"] == "restore"]
    assert len(rows) == 50 and len({r["step_id"] for r in rows}) == 50
    assert [r["command"] for r in restore] == [
        "OC0",
        "RE",
        "RA",
        "FA",
        "TR3",
        "restore_refresh",
        "SM",
    ]
    assert restore[-2]["argument"] == 4
    assert settings.PLAN_VERSION == 2 and settings.RESTORE_RESERVE_S == 24


@pytest.mark.parametrize(
    "scenario,code",
    [
        ("healthy", 11),
        ("remote_keeps_manual", 2),
        ("resolution_ignored", 2),
        ("remote_value_ignored", 2),
        ("old_timeout", 2),
    ],
)
def test_remote_mode_observations_do_not_claim_effective_resolution_or_auto_side_effect(
    tmp_path, scenario, code
):
    result, trace = setting_run(tmp_path, scenario=scenario)
    assert result["status"] == "completed"
    assert result["acquisition_settings_plan_version"] == 2
    a = result["acquisition_settings_assessment"]
    assert a["auto_modes_reference_off_verified"] and a["reference_on_observed"]
    assert a["resolution_usb_verified"] is False
    assert a["remote_RE_filter_observations"][0]["filter_code"] == code
    rows = [r for r in result["queries"] if r["phase"] == "restore"]
    assert all(r["status"] == "completed" and r["accepted_before_deadline"] for r in rows)
    assert rows[-1]["value"]["standby"] is False
    writes = [e["command"] for e in trace if e["event"] == "write"]
    assert "TR1" not in writes[writes.index("OC0") + 1 :]
    assert "TR2" not in writes[writes.index("OC0") + 1 :]


def test_one_countermodel_reproduces_v1_filter_observation_and_restore_trigger_failure():
    # Literal old sequence comes from the sealed trace; it is not replayed on USB.
    wire = Model(scenario="old_timeout")
    instrument = Instrument(wire)
    instrument.query("SM")
    instrument.command("OC1", confirmed=True)
    instrument.acquire("TR1")
    instrument.query("SM")
    instrument.command("FM", 4)
    instrument.command("RE", 1)
    instrument.acquire("TR1")
    assert instrument.query("SM").value.filter_code == 2
    for code, value in (("OC0", None), ("RE", 2), ("RA", None), ("FA", None)):
        instrument.command(code, value)
    with pytest.raises(TimeoutError, match="synthetic"):
        instrument.acquire("TR1")
    assert wire.writes[-1] == b"TR1"


def test_same_sm_observation_cannot_distinguish_applied_from_ignored_remote_resolution():
    values = []
    for scenario in ("remote_keeps_manual", "remote_value_ignored"):
        wire = Model(scenario=scenario)
        instrument = Instrument(wire)
        instrument.query("SM")
        instrument.command("FM", 4)
        instrument.command("RE", 1)
        instrument.acquire("TR1")
        values.append((wire.resolution, instrument.query("SM").raw))
    assert values[0][0] == 1 and values[1][0] == 2
    assert values[0][1] == values[1][1]


def test_stale_reference_on_snapshot_is_not_treated_as_restoration_success(tmp_path):
    result, trace = setting_run(tmp_path, scenario="stale_restore")
    assert result["status"] == "observation_stop"
    a = result["acquisition_settings_assessment"]
    assert a["restoration_attempted"] and not a["auto_modes_reference_off_verified"]
    assert not a["accepted_full_case"] and a["reference_may_be_on"]
    assert [e for e in trace if e["event"] == "close"][0]["reference"] is False
    # A stale status frame is a logical stop, never an automatic second query/retry.
    assert (
        len([r for r in result["queries"] if r["phase"] == "restore" and r["command"] == "SM"]) == 1
    )


def test_restore_refresh_wait_is_cancellable_before_any_status_query(tmp_path):
    factory = Backend(tmp_path / "trace.jsonl")
    factory.settings_restore_refresh_s = 0.5
    result, trace = setting_run(
        tmp_path,
        _factory_override=factory,
        cancelled=lambda: any(e.get("command") == "OC0" for e in events(tmp_path / "trace.jsonl")),
    )
    assert result["status"] == "cancelled"
    assert not result["acquisition_settings_assessment"]["auto_modes_reference_off_verified"]
    assert not any(
        r["status"] == "completed"
        for r in result["queries"]
        if r["phase"] == "restore" and r["command"] == "SM"
    )


def test_no_observed_reference_on_transition_means_no_claim_of_fresh_source_off_verification(
    monkeypatch,
):
    clock = Clock()
    monkeypatch.setattr(settings, "time", clock)
    wire = Model(clock=clock)
    rows = settings.plan(2)

    def step(_):
        clock.now += 1

    status, a = settings.collect(
        Instrument(wire),
        rows,
        0,
        deadline=45,
        before_step=step,
        after_step=lambda: None,
        on_row=lambda r: None,
        raw_reply=lambda: b"",
    )
    assert status == "observation_stop" and a["restoration_attempted"]
    assert not a["reference_on_observed"] and not a["auto_modes_reference_off_verified"]
    assert wire.reference is False and a["reference_may_be_on"]


@pytest.mark.parametrize("delay,verified", [(2.0, True), (8.0, False)])
def test_bounded_refresh_observes_progress_but_does_not_wait_indefinitely(
    monkeypatch, delay, verified
):
    clock = Clock()
    monkeypatch.setattr(settings, "time", clock)

    class Delayed(Model):
        def write(self, raw, deadline=None):
            super().write(raw, deadline)
            if raw == b"TR3" and b"OC0" in self.writes:
                self.ready_at = self.clock.monotonic() + delay

    wire = Delayed(scenario="remote_keeps_manual", clock=clock)
    rows = settings.plan(2)
    status, a = settings.collect(
        Instrument(wire),
        rows,
        0,
        deadline=60,
        before_step=lambda _: None,
        after_step=lambda: None,
        on_row=lambda _: None,
        raw_reply=lambda: b"",
    )
    assert a["auto_modes_reference_off_verified"] is verified
    assert status == ("completed" if verified else "observation_stop")
    assert clock.now < 60
    assert (
        sum(
            r["phase"] == "restore" and r["command"] == "SM" and r["status"] == "completed"
            for r in rows
        )
        == 1
    )


@pytest.mark.parametrize("scenario", ["fa_ignored", "remote_wrong_filter"])
def test_unexpected_mode_and_ignored_explicit_fa_remain_real_stops(tmp_path, scenario):
    result, _ = setting_run(tmp_path, scenario=scenario)
    assert result["status"] == "observation_stop"
    assert result["acquisition_settings_assessment"]["restoration_attempted"]
    assert not result["acquisition_settings_assessment"]["accepted_full_case"]
