"""Supplied limits, coverage gates, immutable assessments, and portable verification."""

import copy
import json
from decimal import Decimal

import pytest
import test_operator_ui as ui_tests
import test_report_recovery as recovery_tests

from hp437b import acceptance_review as a
from hp437b import operator_jobs as jobs
from hp437b import report_delivery
from hp437b import reporting as r

manager = recovery_tests.manager
source = recovery_tests.source


def criteria(kind="WF-01", **limits):
    return dict(
        schema=a.SCHEMA,
        source="Fictional software-test limits; not DUT specifications",
        decision_rule=a.RULE,
        workflows={kind: dict(min_valid_samples=1, max_gap_s="500", **limits)},
    )


def test_native_equality_failure_and_original_preservation(manager, source):
    req = jobs.read(source / "request.json")
    kind = req["workflows"][0]
    data = a.collect(source / "capture", kind)
    with __import__("decimal").localcontext() as ctx:
        ctx.prec = 50
        mean = str(Decimal(data["rows"][kind]["metrics"]["mean_W"]) * 1000)
    bounds = criteria(kind, mean_min_mW=mean, mean_max_mW=mean)
    result = a.evaluate(data, bounds)
    # The existing WF-03 injected fixture records one receipt just beyond the window.
    # Its bounded final acquisition is valid under the corrected start-window contract.
    expected = "Pass"
    legacy = a.evaluate(data, bounds, coverage_policy=a.LEGACY_COVERAGE)
    assert legacy["outcome"] == ("Not evaluated" if kind == "WF-03" else "Pass")
    assert "coverage_policy" not in legacy
    if kind == "WF-03":
        assert data["rows"][kind]["results"]["cycles"][0]["receipts_after_window"] == 1
    assert result["outcome"] == expected
    assert a.evaluate(data, criteria(kind, mean_max_mW="0"))["outcome"] == "Fail"
    assert (
        a.evaluate(data, dict(schema=a.SCHEMA, source=None, decision_rule=a.RULE, workflows={}))[
            "outcome"
        ]
        == "Not evaluated"
    )
    before = recovery_tests.snapshot(source)
    started = manager.assess_run(source.name, bounds, "Software test assessor")
    job = ui_tests.wait(manager, started["job_id"])
    assert job["phase"] == "finished", job
    assert job["assessment_outcome"] == expected and not job["report_recovery_available"]
    assert manager.history(category="reports")["total"] == 1
    assert manager.run_details(job["job_id"])["source_job_id"] == source.name
    assert manager.pending_reference() == source.name
    output = manager.root / job["job_id"] / "report"
    assert a.validate_pair(source / "capture", output) == data["run_id"]
    assert report_delivery.verify(output.with_suffix(".zip"))["mode"] == "physical"
    assert not (output.parent / "capture").exists()
    assert recovery_tests.snapshot(source) == before
    meta = json.loads((output / "metadata.json").read_text())
    assert meta["timing"] == "post_capture" and meta["assessor"] == "Software test assessor"
    assert meta["criteria_sha256"] == r.digest((output / "criteria.json").read_bytes())


def test_coverage_missing_partial_and_no_criteria_never_pass(source):
    req = jobs.read(source / "request.json")
    kind = req["workflows"][0]
    data = a.collect(source / "capture", kind)
    limits = criteria(kind, mean_min_mW="0")
    for mutate in ["missing_coverage", "bad_coverage", "interrupted", "missing_metric"]:
        cap = copy.deepcopy(data)
        spec = copy.deepcopy(limits)
        if mutate == "missing_coverage":
            spec["workflows"][kind]["max_gap_s"] = None
        if mutate == "bad_coverage":
            spec["workflows"][kind]["min_valid_samples"] = 1000000
        if mutate == "interrupted":
            cap["rows"][kind]["native"]["status"] = "interrupted"
        if mutate == "missing_metric":
            cap["rows"][kind]["metrics"]["mean_W"] = None
        assert a.evaluate(cap, spec)["outcome"] == "Not evaluated", mutate
    cap = copy.deepcopy(data)
    cap["rows"] = {}
    cap["execution"] = "interrupted"
    assert a.evaluate(cap, limits)["workflows"][0]["execution"] == "not captured"
    assert a.evaluate(cap, limits)["outcome"] == "Not evaluated"


@pytest.mark.parametrize(
    "change",
    [
        dict(source=None),
        dict(decision_rule="unsupported"),
        dict(schema="other"),
        dict(workflows={"WF-04": {}}),
        dict(source="two\nlines"),
    ],
)
def test_criteria_header_rejected(change):
    value = criteria(mean_min_mW="0")
    value.update(change)
    with pytest.raises(ValueError):
        a.validate(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mean_min_mW", True),
        ("mean_max_mW", "NaN"),
        ("mean_max_mW", "Infinity"),
        ("mean_min_mW", "-1"),
        ("mean_min_mW", "1e99"),
        ("max_gap_s", "0"),
        ("min_valid_samples", True),
        ("min_valid_samples", 1.5),
        ("min_valid_samples", 0),
        ("mean_max_mW", ""),
        ("unknown", "1"),
    ],
)
def test_invalid_numbers_and_fields_rejected(field, value):
    spec = criteria()
    spec["workflows"]["WF-01"][field] = value
    with pytest.raises(ValueError):
        a.validate(spec)


def test_bounds_order_and_decimal_adjacent_values(source, monkeypatch):
    kind = jobs.read(source / "request.json")["workflows"][0]
    data = a.collect(source / "capture", kind)
    with pytest.raises(ValueError):
        a.validate(criteria(kind, mean_min_mW="2", mean_max_mW="1"))
    monkeypatch.setattr(a, "coverage", lambda *args: (True, "Isolated arithmetic test"))
    value = data["rows"][kind]["metrics"]["mean_W"]
    # A one-sided bound immediately outside the observed mean must fail, with no float rounding.
    from decimal import localcontext

    with localcontext() as ctx:
        ctx.prec = 50
        threshold = Decimal(value) * 1000 - Decimal("1e-20")
    assert a.evaluate(data, criteria(kind, mean_max_mW=str(threshold)))["outcome"] == "Fail"


def test_changed_decision_refused_when_resealed(manager, source):
    kind = jobs.read(source / "request.json")["workflows"][0]
    started = manager.assess_run(source.name, criteria(kind, mean_min_mW="0"), None)
    assert ui_tests.wait(manager, started["job_id"])["phase"] == "finished"
    output = manager.root / started["job_id"] / "report"
    results = json.loads((output / "results.json").read_text())
    results["outcome"] = "Fail"
    (output / "results.json").write_bytes(r.encoded(results))
    inv = json.loads((output / "artifacts.json").read_text())
    file = output / "results.json"
    inv["artifacts"]["results.json"] = dict(
        bytes=file.stat().st_size, sha256=r.digest(file.read_bytes())
    )
    (output / "artifacts.json").write_bytes(r.encoded(inv))
    with pytest.raises(ValueError, match="differs"):
        a.validate_pair(source / "capture", output)


def test_synthetic_suite_coverage_and_unconfigured_workflows(tmp_path, monkeypatch):
    from hp437b import reference_suite as suite

    path = tmp_path / "saved"
    path.mkdir()
    req = dict(
        mode="reference_suite",
        meter_mode="synthetic",
        reference_config=None,
        prepared_setup=None,
        workflows=list(suite.KINDS),
        operator=None,
        plots=False,
    )
    with monkeypatch.context() as patch:
        patch.setattr(suite, "publish", lambda *args, **kwargs: None)
        suite.run(path, req, lambda **kwargs: None)
    data = a.collect(path / "capture")
    spec = criteria("WF-01", mean_min_mW="0")
    assert a.evaluate(data, spec)["outcome"] == "Not evaluated"
    spec["workflows"].update(
        {k: dict(mean_min_mW="0", min_valid_samples=1, max_gap_s="500") for k in ["WF-02", "WF-03"]}
    )
    assert a.evaluate(data, spec)["outcome"] == "Pass"
    spec["workflows"]["WF-02"]["max_abs_endpoint_change_percent"] = "0"
    assert (
        a.evaluate(data, spec)["workflows"][1]["checks"][-1]["limit"]
        == "max_abs_endpoint_change_percent"
    )
    out = tmp_path / "report"
    a.publish(path, out, req, spec)
    assert report_delivery.verify(out.with_suffix(".zip"))["mode"] == "synthetic"


def test_http_assessment_and_no_path_or_hardware_input(manager, source):
    import urllib.error

    kind = jobs.read(source / "request.json")["workflows"][0]
    generator = ui_tests.http_server.__wrapped__()
    create = next(generator)
    try:
        _, _, request, _, _ = create(manager)
        body = dict(
            source_job_id=source.name, criteria=criteria(kind, mean_max_mW="0"), assessor=None
        )
        with pytest.raises(urllib.error.HTTPError):
            request("/api/acceptance-review", {**body, "resource": "USB0::anything"})
        with pytest.raises(urllib.error.HTTPError):
            request("/api/acceptance-review", body, {"Origin": "http://untrusted"})
        with request("/api/acceptance-review", body) as response:
            started = json.loads(response.read())
        result = ui_tests.wait(manager, started["job_id"])
        assert result["phase"] == "finished" and result["assessment_outcome"] == "Fail"
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_signed_drift_spread_and_exact_coverage_boundaries(source):
    kind = jobs.read(source / "request.json")["workflows"][0]
    data = a.collect(source / "capture", kind)
    cap = copy.deepcopy(data)
    row = cap["rows"][kind]
    if kind == "WF-03":
        # Isolate mathematical boundary behavior with a healthy, synthetic in-memory timeline.
        for cycle in row["results"]["cycles"]:
            cycle["receipts_after_window"] = 0
        row["results"]["metrics"]["cycle_spread_percent"] = "0.5"
        field = "max_cycle_spread_percent"
        spec = criteria(kind, **{field: "0.5"})
        assert a.evaluate(cap, spec)["outcome"] == "Pass"
        spec["workflows"][kind][field] = "0.49999999999999999999"
        assert a.evaluate(cap, spec)["outcome"] == "Fail"
        row["results"]["metrics"]["cycle_spread_percent"] = None
        assert a.evaluate(cap, spec)["outcome"] == "Not evaluated"
    elif kind == "WF-02":
        row["metrics"]["endpoint_change_percent"] = "-0.5"
        spec = criteria(kind, max_abs_endpoint_change_percent="0.5")
        assert a.evaluate(cap, spec)["outcome"] == "Pass"
        spec["workflows"][kind]["max_abs_endpoint_change_percent"] = "0.49999999999999999999"
        assert a.evaluate(cap, spec)["outcome"] == "Fail"
        row["metrics"]["endpoint_change_percent"] = None
        assert a.evaluate(cap, spec)["outcome"] == "Not evaluated"
    else:
        row["metrics"]["zero_W"] = None
        assert a.evaluate(cap, criteria(kind, mean_min_mW="0"))["outcome"] == "Not evaluated"


def test_small_scientific_limits_remain_bounded():
    spec = a.validate(criteria(mean_min_mW="1e-100000000"))
    assert spec["workflows"]["WF-01"]["mean_min_mW"] == "1E-100000000"
    assert len(r.encoded(spec)) < 1024
    assert a.validate(spec) == spec


@pytest.mark.parametrize(
    "times,timeout,minimum,gap,expected,reason",
    [
        ([0, 299, 300], 10, 3, 300, True, "coverage satisfied"),
        ([0, 299, 300.123], 10, 3, 300, True, "Final acquisition completed"),
        ([0, 299, 310], 10, 3, 300, True, "Final acquisition completed"),
        ([0, 299, 310.001], 10, 3, 300, False, "recorded timeout"),
        ([0, 300, 300.1], 10, 3, 300, False, "More than the final"),
        ([0, 300.1, 300.2], 10, 3, 300, False, "More than the final"),
        ([0, 299, 300.123], None, 3, 300, False, "timeout is unavailable"),
        ([0, 299, 300.123], 0, 3, 300, False, "timeout is unavailable"),
        ([0, 299, 300.123], 10, 4, 300, False, "minimum 4"),
        ([0, 299, 300.123], 10, 3, 2, False, "Maximum receipt gap"),
        ([-1, 299, 300.123], 10, 3, 300, False, "invalid"),
        ([0, 299, 298], 10, 3, 300, False, "invalid"),
        ([], 10, 1, 300, False, "minimum 1"),
    ],
)
def test_acquisition_start_window_and_real_coverage_failures(
    times, timeout, minimum, gap, expected, reason
):
    points = [dict(elapsed_s=t, status="ok") for t in times]
    good, detail = a._window_coverage(
        points,
        Decimal(300),
        Decimal(timeout) if timeout is not None else None,
        minimum,
        Decimal(gap),
    )
    assert good is expected and reason in detail


def test_failed_read_is_not_excused_by_final_acquisition_policy():
    points = [dict(elapsed_s=0, status="ok"), dict(elapsed_s=300.123, status="failed")]
    good, reason = a._window_coverage(points, Decimal(300), Decimal(10), 1, Decimal(500))
    assert not good and "failed or invalid" in reason


def test_legacy_sealed_assessment_still_verifies_and_new_policy_is_bound(
    manager, source, monkeypatch
):
    from hp437b.workflow_report import _seal

    kind = jobs.read(source / "request.json")["workflows"][0]
    spec = criteria(kind, mean_min_mW="0")
    job = ui_tests.wait(manager, manager.assess_run(source.name, spec, None)["job_id"])
    output = manager.root / job["job_id"] / "report"
    meta = jobs.read(output / "metadata.json")
    assert meta["coverage_policy"] == a.COVERAGE_POLICY
    data = a.collect(source / "capture", kind)
    assert a.validate_pair(source / "capture", output)
    # Reconstruct the prior release's metadata/results to exercise legacy verification.
    meta.pop("coverage_policy")
    (output / "metadata.json").write_bytes(r.encoded(meta))
    (output / "results.json").write_bytes(
        r.encoded(a.evaluate(data, spec, coverage_policy=a.LEGACY_COVERAGE))
    )
    (output / "provenance.json").write_bytes(r.encoded(a.provenance(data, meta)))
    (output / "artifacts.json").unlink()
    _seal(output, meta)
    assert a.validate_pair(source / "capture", output)
    meta["coverage_policy"] = "unknown"
    (output / "metadata.json").write_bytes(r.encoded(meta))
    (output / "artifacts.json").unlink()
    _seal(output, meta)
    with pytest.raises(ValueError, match="coverage policy"):
        a.validate_pair(source / "capture", output)
