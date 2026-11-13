"""Reusable control boundaries, deadlines, ownership, and readback guards."""

import copy
from decimal import Decimal as D

import pytest

from hp437b import dut_control as c
from hp437b import dut_simulation as f


def rig(scenario="nominal", plan=None):
    plan = c.default_plan() if plan is None else plan
    b = f.Bench(plan, scenario)
    controls = c.Controls(
        plan, f.FakeTransmitter(b), f.FakeSupply(b), f.FakeObserver(b), clock=lambda: b.now
    )
    b.controls = controls
    return b, controls


def test_distinct_ack_state_observation_and_restore():
    b, controls = rig()
    controls.preflight()
    controls.configure()
    controls.activate()
    controls.verify()
    assert b.rf and controls.rf == "on" and D(b.voltage) == 13 and D(b.current) == 2
    controls.deactivate()
    controls.restore()
    assert b.rf is False and D(b.voltage) == 12 and D(b.current) == D("1.5")
    assert controls.restored and controls.rf == "off"
    assert controls.order == list(c.PHASES)
    assert len(controls.events) <= 48
    assert all(event["end_s"] <= event["deadline_s"] for event in controls.events)


def test_configuration_cannot_key_without_preflight():
    _, controls = rig()
    with pytest.raises(c.ControlFailure):
        controls.activate()
    assert controls.events == []


def test_unowned_initial_on_is_not_unkeyed():
    b, controls = rig("initial-on")
    with pytest.raises(c.ControlFailure):
        controls.preflight()
    assert b.rf is True and not controls.adopted
    assert not any(event["operation"] == "set_rf" for event in controls.events)


@pytest.mark.parametrize("scenario", ("key-rejected", "source-off-failure", "source-still-on"))
def test_one_off_attempt_and_no_restore_on_unverified_off(scenario):
    _, controls = rig(scenario)
    controls.preflight()
    controls.configure()
    if scenario == "key-rejected":
        with pytest.raises(c.ControlFailure):
            controls.activate()
        assert controls.blocked
    else:
        controls.activate()
        with pytest.raises(c.ControlFailure):
            controls.deactivate()
        with pytest.raises(c.ControlFailure):
            controls.restore()
    assert (
        sum(
            event["operation"] == "set_rf" and event["request"].get("on") is False
            for event in controls.events
        )
        <= 1
    )
    assert not controls.restored


def test_phase_may_not_be_retried():
    _, controls = rig()
    controls.preflight()
    before = copy.deepcopy(controls.events)
    with pytest.raises(c.ControlFailure):
        controls.preflight()
    assert controls.events == before


def test_late_reply_stops_commands():
    _, controls = rig("late-reply")
    controls.preflight()
    with pytest.raises(c.ControlFailure):
        controls.configure()
    last = controls.events[-1]
    assert last["end_s"] > last["deadline_s"] and controls.blocked
    before = copy.deepcopy(controls.events)
    with pytest.raises(c.ControlFailure):
        controls.restore()
    assert controls.events == before


def test_rf_on_budget_is_checked_before_next_operation():
    b, controls = rig()
    controls.preflight()
    controls.configure()
    controls.activate()
    before = copy.deepcopy(controls.events)
    b.advance(61)
    with pytest.raises(c.ControlFailure):
        controls.verify()
    assert controls.blocked and controls.rf == "unknown" and controls.events == before


def test_fixture_envelope_before_any_actor():
    plan = c.default_plan()
    plan["fixture"]["minimum_loss_dB"] = "0"
    with pytest.raises(ValueError):
        rig(plan=plan)


def test_observation_missing_can_restore_without_keying():
    _, controls = rig("voltage-missing")
    controls.preflight()
    with pytest.raises(c.ControlFailure):
        controls.configure()
    assert controls.rf == "off" and not controls.owned_rf
    controls.restore()
    assert controls.restored


def test_mismatched_current_readback_is_not_old_verified_value():
    _, controls = rig("current-mismatch")
    controls.preflight()
    with pytest.raises(c.ControlFailure):
        controls.configure()
    assert controls.blocked and controls.current == "0.5"


def test_no_physical_endpoint_admitted():
    b, controls = rig()
    controls.devices["transmitter"].simulation = False
    with pytest.raises(ValueError):
        c.Controls(c.default_plan(), *controls.devices.values(), clock=lambda: b.now)


def test_bad_ack_type_is_uncertain():
    _, controls = rig()
    controls.preflight()
    controls.devices["supply"].set_current_limit = lambda **kwargs: 1
    with pytest.raises(c.ControlFailure):
        controls.configure()
    assert controls.blocked


def test_nonfinite_and_backwards_control_clock_refused():
    b, controls = rig()
    with pytest.raises(ValueError):
        c.Controls(c.default_plan(), *controls.devices.values(), clock=lambda: float("nan"))
    controls.preflight()
    before = copy.deepcopy(controls.events)
    b.now = -1
    with pytest.raises(c.ControlFailure):
        controls.configure()
    assert controls.events == before and controls.blocked
