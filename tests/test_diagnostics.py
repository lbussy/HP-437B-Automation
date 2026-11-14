"""Fake batch sequencing through the real Instrument APIs; no physical I/O."""

import json

import pytest

from hp437b import diagnostics as diag
from hp437b.errors import StateUncertain, TransportError
from hp437b.instrument import Instrument


def writes(receipt):
    return [event["command"] for event in receipt["trace"] if event["operation"] == "write"]


def read_receipt(path):
    return json.loads((path / "diagnostics.json").read_text())


def test_default_reads_do_not_touch_latched_evidence(tmp_path):
    path = tmp_path / "basic"
    result = diag.run_simulated(path)
    saved = read_receipt(path)
    assert result["status"] == saved["status"] == "completed"
    assert writes(result) == ["*ESE?", "*SRE?", "*STB?", "OD", "TR3"]
    assert all(row["status"] == "completed" for row in saved["queries"])
    assert saved["queries"][2]["raw_hex"] == b"000\r\n".hex()
    assert saved["queries"][2]["value"] == 0
    assert saved["queries"][3]["value"] == "-0.050 uW"
    assert saved["cleanup"]["status"] == "accepted"
    assert saved["trace"][-2:] == [{"operation": "go_to_local"}, {"operation": "close"}]
    assert saved["transport_closed"] and not saved["hardware_access"]
    assert saved["evidence"] == "simulated"
    assert saved["health_verdict"].startswith("Not evaluated")


def test_explicit_latch_reads_come_after_masks_and_stb_with_sm_last(tmp_path):
    result = diag.run_simulated(tmp_path / "latched", include_latched_reads=True)
    assert writes(result) == ["*ESE?", "*SRE?", "*STB?", "OD", "ERR?", "*ESR?", "SM", "TR3"]
    assert "May clear" in result["queries"][-1]["effect"]
    assert result["queries"][-1]["value"]["unit"] == "W"
    assert result["queries"][-1]["raw_hex"].endswith("0d0a")
    # Every reply is consumed before selecting another output; cleanup is separate.
    operations = [event["operation"] for event in result["trace"]]
    assert operations == ["write", "read"] * 7 + ["write", "go_to_local", "close"]


def test_error_indications_are_retained_without_a_health_pass_or_clearing_command(tmp_path):
    result = diag.run_simulated(
        tmp_path / "errors", include_latched_reads=True, scenario="instrument_errors"
    )
    rows = {row["command"]: row for row in result["queries"]}
    assert result["status"] == "completed"  # Collection outcome, not instrument health.
    assert result["health_verdict"].startswith("Not evaluated")
    assert rows["*STB?"]["value"] == 12 and rows["ERR?"]["value"] == 91
    assert rows["*ESR?"]["value"] == 32
    assert rows["SM"]["value"]["measurement_error"] == 1
    assert rows["SM"]["value"]["entry_error"] == 91
    assert rows["*STB?"]["raw_hex"] == b"012\r\n".hex()
    assert not set(writes(result)) & {"CS", "*CLS", "OC0", "OC1", "PR", "ZE", "CL"}


@pytest.mark.parametrize("code", diag.BASIC_QUERIES + diag.LATCHED_QUERIES)
def test_malformed_reply_at_each_step_keeps_raw_and_never_queries_again(tmp_path, code):
    result = diag.run_simulated(
        tmp_path / "bad", include_latched_reads=True, scenario="malformed_reply", fault_at=code
    )
    commands = list(diag.BASIC_QUERIES + diag.LATCHED_QUERIES)
    index = commands.index(code)
    assert result["status"] == "query_failed"
    assert writes(result) == commands[: index + 1]
    failed = result["queries"][index]
    assert failed["raw_hex"] == b"\xffBROKEN\r\n".hex()
    assert failed["error"].startswith("ProtocolError:")
    assert all(row["status"] == "completed" for row in result["queries"][:index])
    assert all(row["status"] == "not_attempted" for row in result["queries"][index + 1 :])
    assert result["cleanup"] is None
    assert result["trace"][-1] == {"operation": "close"}
    assert result["transport_closed"]


@pytest.mark.parametrize(
    "scenario,error,raw",
    [
        ("read_error", "TransportError:", ""),
        ("late_reply", "OperationTimeout:", b"000\r\n".hex()),
    ],
)
def test_failed_or_late_read_is_not_retried_or_hidden(tmp_path, scenario, error, raw):
    result = diag.run_simulated(tmp_path / "fault", scenario=scenario, timeout_s=0.02)
    assert result["status"] == "query_failed"
    assert writes(result) == ["*ESE?", "*SRE?"]
    row = result["queries"][1]
    assert row["error"].startswith(error) and row["raw_hex"] == raw
    assert "value" not in row
    assert result["transport_closed"] and result["cleanup"] is None


def test_cleanup_failure_keeps_successful_queries_and_closes_once(tmp_path):
    result = diag.run_simulated(tmp_path / "cleanup", scenario="cleanup_error")
    assert result["status"] == "cleanup_failed"
    assert all(row["status"] == "completed" for row in result["queries"])
    assert result["cleanup"]["status"] == "failed"
    assert "Go To Local failure" in result["cleanup_error"]
    assert result["trace"].count({"operation": "close"}) == 1
    assert result["trace"].count({"operation": "go_to_local"}) == 1
    assert result["transport_closed"]


def test_source_on_is_reported_without_source_switching(tmp_path):
    result = diag.run_simulated(tmp_path / "on", scenario="source_on", include_latched_reads=True)
    assert result["queries"][-1]["value"]["reference_on"] is True
    assert not set(writes(result)) & {"OC0", "OC1"}
    assert "source-off" in result["limitations"][1]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"include_latched_reads": 1},
        {"include_latched_reads": "yes"},
        {"timeout_s": True},
        {"timeout_s": 0},
        {"timeout_s": float("nan")},
        {"timeout_s": float("inf")},
        {"timeout_s": 5.1},
        {"timeout_s": "1"},
        {"scenario": "physical"},
        {"scenario": None},
        {"scenario": "malformed_reply", "fault_at": "SM"},
        {"scenario": "malformed_reply", "fault_at": "*CLS"},
        {"fault_at": "*SRE?"},
        {"scenario": "source_on"},
    ],
)
def test_invalid_requests_do_not_reserve_output_or_construct_transport(
    tmp_path, monkeypatch, kwargs
):
    monkeypatch.setattr(diag, "_FakeWire", lambda *a: pytest.fail("Transport constructed"))
    with pytest.raises(ValueError):
        diag.run_simulated(tmp_path / "invalid", **kwargs)
    assert not (tmp_path / "invalid").exists()


def test_existing_output_is_preserved_before_any_transport_is_created(tmp_path, monkeypatch):
    path = tmp_path / "existing"
    path.mkdir()
    (path / "diagnostics.json").write_bytes(b"original")
    monkeypatch.setattr(diag, "_FakeWire", lambda *a: pytest.fail("Transport constructed"))
    with pytest.raises(FileExistsError):
        diag.run_simulated(path)
    assert (path / "diagnostics.json").read_bytes() == b"original"


def test_keyboard_interrupt_retains_partial_receipt_and_does_not_send_cleanup(
    tmp_path, monkeypatch
):
    original_read = diag._FakeWire.read

    def interrupt(wire, deadline):
        if wire.pending == "*SRE?":
            raise KeyboardInterrupt
        return original_read(wire, deadline)

    monkeypatch.setattr(diag._FakeWire, "read", interrupt)
    with pytest.raises(KeyboardInterrupt):
        diag.run_simulated(tmp_path / "interrupt")
    receipt = read_receipt(tmp_path / "interrupt")
    assert receipt["status"] == "interrupted"
    assert receipt["queries"][0]["status"] == "completed"
    assert receipt["queries"][1]["status"] == "interrupted"
    assert receipt["queries"][2]["status"] == "not_attempted"
    assert receipt["transport_closed"] and writes(receipt) == ["*ESE?", "*SRE?"]

    # An interruption during healthy cleanup is also partial, never completed.
    monkeypatch.setattr(diag._FakeWire, "read", original_read)

    def interrupt_cleanup(wire, deadline):
        raise KeyboardInterrupt

    monkeypatch.setattr(diag._FakeWire, "return_local", interrupt_cleanup)
    with pytest.raises(KeyboardInterrupt):
        diag.run_simulated(tmp_path / "interrupt-cleanup")
    receipt = read_receipt(tmp_path / "interrupt-cleanup")
    assert receipt["status"] == "interrupted"
    assert receipt["cleanup_error"].startswith("KeyboardInterrupt:")
    assert receipt["transport_closed"]
    assert all(row["status"] == "completed" for row in receipt["queries"])


def test_write_failure_stops_without_read_or_local_commands(tmp_path, monkeypatch):
    original_write = diag._FakeWire.write

    def fail(wire, data, deadline):
        if data == b"*SRE?":
            raise TransportError("Simulated rejected write")
        return original_write(wire, data, deadline)

    monkeypatch.setattr(diag._FakeWire, "write", fail)
    result = diag.run_simulated(tmp_path / "write")
    assert result["status"] == "query_failed"
    assert writes(result) == ["*ESE?"]
    assert result["queries"][1]["raw_hex"] == ""  # Never carries over the previous reply.
    assert result["trace"][-1] == {"operation": "close"}


def test_closed_or_uncertain_instrument_still_rejects_reads_before_io():
    wire = diag._FakeWire("read_error", "*ESE?")
    device = Instrument(wire)
    with pytest.raises(TransportError):
        device.query("*ESE?")
    calls = list(wire.trace)
    with pytest.raises(StateUncertain):
        device.query("*SRE?")
    assert wire.trace == calls
    device.close()
    calls = list(wire.trace)
    with pytest.raises(StateUncertain):
        device.query("*ESE?")
    assert wire.trace == calls
