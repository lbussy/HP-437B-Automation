"""Fake suite orchestration, cross-workflow boundaries, and immutable saved reports."""

import json
import signal

import pytest

from hp437b import controlled_sweep as s
from hp437b import provenance as p
from hp437b import reporting as r
from hp437b import test_profiles as t
from hp437b import test_suite as u
from hp437b.workflow_report import _seal


def snapshot(source):
    return {
        str(path.relative_to(source)): r.digest(path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }


def criteria(kind):
    return dict(
        source="Fictional example limits",
        decision_rule="inclusive-no-guard-band",
        min_samples_per_point=30,
        max_gap_s="1",
        **{"max_abs_change_percent" if kind == "WF-06" else "max_abs_error_percent": "10"},
    )


def test_complete_shared_state_suite_reports_and_profile_independent_reuse(tmp_path, monkeypatch):
    profile = t.example()
    profile["operator"] = "Saved operator"
    profile["dut"].update(model="EXAMPLE-TX", serial="Fictional-01")
    source = tmp_path / "capture"
    result = u.run(profile, source, report_output=tmp_path / "report", plots=False)
    assert result["status"] == "completed" and result["acceptance"] == "NOT EVALUATED"
    assert result["completed_workflows"] == 3 and len(result["children"]) == 3
    assert u.format_observed(result["results"][0]) == "1–10 W (DUT output); 3/3 points"
    assert "spread 0 dB" in u.format_observed(result["results"][1])
    assert "endpoint 0 W/V" in u.format_observed(result["results"][2])
    record, binding, bundle = u.load(source)
    assert record == result and binding["operator"]["origin"] == "profile"
    state = None
    run_ids = set()
    session_ids = set()
    for index, item in enumerate(record["children"], 1):
        w = s.module(item["workflow"])
        cap, rows, native = w.load(source / item["path"])
        assert cap["run_id"] not in run_ids
        run_ids.add(cap["run_id"])
        assert cap["suite_context"]["suite_id"] == record["suite_id"]
        assert cap["suite_context"]["index"] == index
        if state is not None:
            assert cap["suite_context"]["initial_hardware"] == state
        state = u.final_hardware(cap, native)
        assert state["rf"] is False
        for name in native.entries:
            if name.endswith(".csv.session.json"):
                sid = native.json(name)["session_id"]
                assert sid not in session_ids
                session_ids.add(sid)
        p.verify(w.provenance(cap, native), source / item["path"])
        assert len(rows) == 6 + 50 * len(cap["plan"]["points"])
    before = snapshot(source)
    profile["dut"]["serial"] = "Changed later"
    monkeypatch.setenv("HP437B_OPERATOR", "Changed later")
    again = u.publish(source, tmp_path / "again", plots=False)
    assert (
        again["operator"]["value"] == "Saved operator" and again["dut"]["serial"] == "Fictional-01"
    )
    assert snapshot(source) == before
    page = (tmp_path / "again/report.html").read_text()
    assert "RF Output Power Test" in page and "SYNTHETIC" in page and "Pre-RF zero" in page
    assert page.index("Equipment:") < page.index("Report Harness:") < page.index("Record:")
    for kind in t.KINDS:
        assert f"workflows/{kind}/report.html" in page
    p.Bundle(tmp_path / "again").inventory("artifacts.json", "synthetic")


@pytest.mark.parametrize("selected", [["WF-05"], ["WF-06", "WF-04"], ["WF-05", "WF-04", "WF-06"]])
def test_subset_and_explicit_order(tmp_path, selected):
    cap = u.run(t.example(), tmp_path / "capture", workflows=selected, plots=False)
    assert (
        cap["selected"] == selected and [item["workflow"] for item in cap["children"]] == selected
    )
    assert u.load(tmp_path / "capture")[0] == cap


@pytest.mark.parametrize(
    "fault",
    [
        "meter-timeout",
        "meter-malformed",
        "cancel",
        "source-still-on",
        "source-off-failure",
        "restore-failure",
        "restore-mismatch",
        "key-rejected",
        "initial-on",
    ],
)
def test_fault_stops_cross_workflow_without_reset_or_retry(tmp_path, fault):
    source = tmp_path / "capture"
    result = u.run(
        t.example(), source, fault=fault, fault_workflow="WF-05", fault_point="P02", plots=False
    )
    assert result["status"] == ("interrupted" if fault == "cancel" else "failed")
    assert result["stop_reason"] == "execution:WF-05" and result["acceptance"] != "PASS"
    assert [item["workflow"] for item in result["children"]] == ["WF-04", "WF-05"]
    assert not (source / "captures/WF-06").exists()
    assert result["results"][0]["execution"] == "completed"
    u.load(source)
    u.publish(source, tmp_path / "report", plots=False)
    page = (tmp_path / "report/report.html").read_text()
    assert "skipped" in page and not (tmp_path / "report/workflows/WF-06").exists()


@pytest.mark.parametrize("boundary", t.KINDS)
def test_explicit_cooperative_cancel_preserves_finished_workflows(tmp_path, boundary):
    source = tmp_path / "capture"
    cap = u.run(t.example(), source, stop_before=boundary, plots=False)
    assert cap["status"] == "interrupted" and cap["stop_reason"] == "cancelled:" + boundary
    assert len(cap["children"]) == t.KINDS.index(boundary)
    assert u.load(source)[0] == cap
    u.publish(source, tmp_path / "report", plots=False)
    if boundary == "WF-04":
        assert "Not captured" in (tmp_path / "report/report.html").read_text()


def test_callback_cancellation_observed_at_boundary(tmp_path):
    checks = iter([False, True])
    cap = u.run(t.example(), tmp_path / "capture", cancelled=lambda: next(checks), plots=False)
    assert cap["status"] == "interrupted" and cap["attempted_workflows"] == 1
    assert cap["results"][0]["rf_state"] == "off" and cap["results"][0]["supply_restored"]
    u.load(tmp_path / "capture")


@pytest.mark.parametrize("policy", ["absent", "pass", "fail-first", "fail-last"])
def test_acceptance_policy_and_fail_fast(tmp_path, policy):
    profile = t.example()
    if policy != "absent":
        for kind in t.KINDS:
            profile["workflows"][kind]["criteria"] = criteria(kind)
    if policy == "fail-first":
        profile["workflows"]["WF-04"]["plan"]["points"][1]["synthetic_DUT_W"] = "4"
    if policy == "fail-last":
        profile["workflows"]["WF-06"]["plan"]["points"][1]["synthetic_DUT_W"] = "4"
    cap = u.run(profile, tmp_path / "capture", plots=False)
    assert (
        cap["acceptance"]
        == {"absent": "NOT EVALUATED", "pass": "PASS", "fail-first": "FAIL", "fail-last": "FAIL"}[
            policy
        ]
    )
    assert len(cap["children"]) == (1 if policy == "fail-first" else 3)
    assert cap["status"] == ("failed" if policy == "fail-first" else "completed")
    u.load(tmp_path / "capture")


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "unknown",
        "empty",
        "missing",
        "incompatible",
        "bad-operator",
        "bad-stop",
        "bad-fault",
        "bad-point",
        "factor-kind",
    ],
)
def test_invalid_suite_rejected_before_capture_allocation(tmp_path, monkeypatch, case):
    profile = t.example()
    kwargs = {}
    if case == "duplicate":
        kwargs["workflows"] = ["WF-04", "WF-04"]
    if case == "unknown":
        kwargs["workflows"] = ["WF-99"]
    if case == "empty":
        kwargs["workflows"] = []
    if case == "missing":
        profile["workflows"].pop("WF-04")
        kwargs["workflows"] = ["WF-04"]
    if case == "incompatible":
        profile["workflows"]["WF-06"]["plan"]["supply"]["current_limit_A"] = "2"
    if case == "bad-operator":
        kwargs["operator"] = "\n"
    if case == "bad-stop":
        kwargs.update(workflows=["WF-04"], stop_before="WF-05")
    if case == "bad-fault":
        kwargs["fault"] = "meter-timeout"
    if case == "bad-point":
        kwargs.update(fault="meter-timeout", fault_workflow="WF-05", fault_point="P99")
    if case == "factor-kind":
        kwargs.update(fault="factor-mismatch", fault_workflow="WF-04")

    def unexpected(*args, **kwargs):
        raise AssertionError("invalid suite started capture")

    monkeypatch.setattr(s, "run", unexpected)
    with pytest.raises((ValueError, KeyError, TypeError)):
        u.run(profile, tmp_path / "capture", plots=False, **kwargs)
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize(
    "case",
    ["summary", "order", "profile", "state", "context", "timeline", "hidden", "stop", "missing"],
)
def test_resealed_invalid_suite_refuses_report_before_allocation(tmp_path, case):
    source = tmp_path / "capture"
    u.run(t.example(), source, plots=False)
    cap = json.loads((source / "suite.json").read_bytes())
    if case == "summary":
        cap["results"][0]["acceptance"] = "PASS"
    if case == "order":
        cap["selected"].reverse()
    if case == "profile":
        binding = json.loads((source / "test-profile.json").read_bytes())
        binding["profile"]["revision"] = 2
        (source / "test-profile.json").write_bytes(r.encoded(binding))
        cap["profile_binding_sha256"] = r.digest(r.encoded(binding))
    if case in ("state", "context", "timeline"):
        child = source / "captures/WF-05"
        item = json.loads((child / "workflow.json").read_bytes())
        if case == "state":
            item["suite_context"]["initial_hardware"]["setting"] = "Reset between workflows"
        if case == "context":
            item["suite_context"]["suite_id"] = cap["children"][0]["run_id"]
        if case == "timeline":
            item["started_utc"] = cap["started_utc"]
        (child / "workflow.json").write_bytes(r.encoded(item))
        (child / "artifacts.json").unlink()
        _seal(child, dict(schema=s.SCHEMA, mode="synthetic", run_id=item["run_id"]))
    if case == "hidden":
        (source / "captures/WF-99").mkdir()
        (source / "captures/WF-99/hidden.json").write_text("{}")
    if case == "stop":
        cap["stop_reason"] = "cancelled:WF-05"
    if case == "missing":
        cap["children"].pop()
    (source / "suite.json").write_bytes(r.encoded(cap))
    (source / "artifacts.json").unlink()
    _seal(source, dict(schema=u.SCHEMA, mode="synthetic", run_id=cap["suite_id"]))
    with pytest.raises((ValueError, KeyError, TypeError)):
        u.publish(source, tmp_path / "no-report", plots=False)
    assert not (tmp_path / "no-report").exists()


def test_report_storage_failure_is_retryable_without_capture(tmp_path, monkeypatch):
    source = tmp_path / "capture"
    u.run(t.example(), source, plots=False)
    before = snapshot(source)
    original = u._render

    def fail(*args):
        raise OSError("Fake report disk error")

    monkeypatch.setattr(u, "_render", fail)
    with pytest.raises(OSError):
        u.publish(source, tmp_path / "failed", plots=False)
    assert snapshot(source) == before and (tmp_path / "failed/failure.json").exists()
    assert not (tmp_path / "failed/artifacts.json").exists()
    monkeypatch.setattr(u, "_render", original)

    def unexpected(*args, **kwargs):
        raise AssertionError("Report attempted capture")

    monkeypatch.setattr(s, "run", unexpected)
    u.publish(source, tmp_path / "retry", plots=False)
    assert snapshot(source) == before


def test_capture_storage_failure_preserves_previous_child_and_stops(tmp_path, monkeypatch):
    original = s.run
    calls = []

    def capture(kind, *args, **kwargs):
        calls.append(kind)
        if kind == "WF-05":
            raise OSError("Fake capture storage error")
        return original(kind, *args, **kwargs)

    monkeypatch.setattr(s, "run", capture)
    source = tmp_path / "capture"
    with pytest.raises(OSError):
        u.run(t.example(), source, plots=False)
    assert calls == ["WF-04", "WF-05"]
    assert (source / "failure.json").exists() and not (source / "artifacts.json").exists()
    s.module("WF-04").load(source / "captures/WF-04")
    with pytest.raises(ValueError):
        u.load(source)


def test_cli_exit_codes_and_sigint_boundary_handler(tmp_path, monkeypatch):
    profile = tmp_path / "profile.json"
    profile.write_bytes(r.encoded(t.example()))
    original = signal.getsignal(signal.SIGINT)
    assert (
        u.main(["run", "--profile", str(profile), "--output", str(tmp_path / "ok"), "--no-plots"])
        == 0
    )
    assert (
        u.main(
            [
                "run",
                "--profile",
                str(profile),
                "--output",
                str(tmp_path / "failed"),
                "--fault",
                "meter-timeout",
                "--fault-workflow",
                "WF-05",
                "--no-plots",
            ]
        )
        == 1
    )
    assert (
        u.main(
            [
                "run",
                "--profile",
                str(profile),
                "--output",
                str(tmp_path / "cancel"),
                "--stop-before",
                "WF-05",
                "--no-plots",
            ]
        )
        == 130
    )
    assert (
        u.main(
            [
                "report",
                "--bundle",
                str(tmp_path / "ok"),
                "--output",
                str(tmp_path / "report"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        u.main(["run", "--profile", str(profile), "--output", str(tmp_path / "ok"), "--no-plots"])
        == 2
    )
    real = s.run

    def signal_during_child(*args, **kwargs):
        result = real(*args, **kwargs)
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        return result

    monkeypatch.setattr(s, "run", signal_during_child)
    assert (
        u.main(
            ["run", "--profile", str(profile), "--output", str(tmp_path / "sigint"), "--no-plots"]
        )
        == 130
    )
    assert signal.getsignal(signal.SIGINT) == original
    cap = u.load(tmp_path / "sigint")[0]
    assert cap["attempted_workflows"] == 1 and cap["results"][0]["execution"] == "completed"


def test_no_overwrite_or_nested_report_allocation(tmp_path, monkeypatch):
    source = tmp_path / "capture"
    with pytest.raises(ValueError):
        u.run(t.example(), source, report_output=source / "report", plots=False)
    assert not source.exists()
    u.run(t.example(), source, workflows=["WF-04"], plots=False)
    before = snapshot(source)
    with pytest.raises(ValueError):
        u.run(t.example(), source, plots=False)
    assert snapshot(source) == before


def test_optional_plots_and_escaped_identity(tmp_path):
    pytest.importorskip("matplotlib")
    profile = t.example()
    profile["operator"] = "<script>bad()</script>"
    cap = u.run(profile, tmp_path / "capture", report_output=tmp_path / "report", plots=True)
    assert cap["status"] == "completed"
    page = (tmp_path / "report/report.html").read_text()
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "<script>" not in (tmp_path / "report/report.md").read_text()
    assert list((tmp_path / "report/workflows").rglob("*.svg"))


def test_meter_factor_state_is_carried_then_prepared_while_off(tmp_path):
    profile = t.example()
    profile["workflows"]["WF-05"]["plan"] = s.module("WF-05").default_plan("meter-corrected")
    source = tmp_path / "capture"
    u.run(profile, source, workflows=["WF-05", "WF-06"], plots=False)
    first, _, first_bundle = s.module("WF-05").load(source / "captures/WF-05")
    final = u.final_hardware(first, first_bundle)
    second, _, native = s.module("WF-06").load(source / "captures/WF-06")
    assert final["meter_factor_percent"] != "100"
    assert second["suite_context"]["initial_hardware"] == final
    point = native.json("points/P01/workflow.json")
    assert point["initial_hardware"]["meter_factor_percent"] == final["meter_factor_percent"]
    assert point["initial_hardware"]["rf"] is False
    assert point["meter_preparation"]["observed_percent"] == "100"
    u.load(source)
