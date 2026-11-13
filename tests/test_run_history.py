"""Saved-job browsing and native, context-aware comparisons without acquisition."""

import json
import uuid

import pytest
import test_operator_ui as ui_tests
import test_report_recovery as recovery_tests

from hp437b import operator_jobs as jobs
from hp437b import reporting as r
from hp437b import run_history

manager = recovery_tests.manager
source = recovery_tests.source


def test_history_filters_and_report_attempt_details(manager, source):
    baseline = manager.history()
    assert baseline["total"] == 1 and baseline["entries"][0]["job_id"] == source.name
    assert manager.history(category="reports")["total"] == 0
    before = r.digest((source / "capture/artifacts.json").read_bytes())
    detail = manager.run_details(source.name)
    assert detail["source_job_id"] == source.name and detail["workflows"][0]["mode"] == "physical"
    assert detail["source_inventory_sha256"] == before
    job = manager.regenerate_reports(source.name)
    assert ui_tests.wait(manager, job["job_id"])["phase"] == "finished"
    assert manager.history(category="measurements")["total"] == 1
    assert manager.history(category="reports")["entries"][0]["source_job_id"] == source.name
    report_detail = manager.run_details(job["job_id"])
    assert report_detail["report_attempt"] and report_detail["workflows"] == detail["workflows"]
    with pytest.raises(ValueError, match="not report"):
        manager.compare_runs([source.name, job["job_id"]], detail["workflows"][0]["workflow"])


def test_pagination_and_unreadable_record(manager, source):
    request = jobs.read(source / "request.json")
    state = jobs.read(source / "state.json")
    for _ in range(22):
        path = manager.root / uuid.uuid4().hex
        path.mkdir()
        jobs.atomic(path / "request.json", {**request, "job_id": path.name})
        jobs.atomic(path / "state.json", {**state, "job_id": path.name})
    page1 = manager.history()
    page2 = manager.history(offset=20)
    assert page1["total"] == 23 and len(page1["entries"]) == 20 and len(page2["entries"]) == 3
    assert not ({x["job_id"] for x in page1["entries"]} & {x["job_id"] for x in page2["entries"]})
    bad = manager.root / uuid.uuid4().hex
    bad.mkdir()
    (bad / "request.json").write_text("invalid")
    assert bad.name in manager.history()["unreadable_jobs"]
    for value in [-1, True, "0"]:
        with pytest.raises(ValueError):
            manager.history(value)
    with pytest.raises(ValueError):
        manager.history(category="anything")


def test_details_reject_invalid_active_tampered_and_duplicate_acquisition(manager, source):
    detail = manager.run_details(source.name)
    kind = detail["workflows"][0]["workflow"]
    for ids in [[], [source.name], [source.name, source.name], ["../bad", source.name], ["x"] * 5]:
        with pytest.raises(ValueError):
            manager.compare_runs(ids, kind)
    import shutil

    target = manager.root / uuid.uuid4().hex
    shutil.copytree(source, target)
    for name in ["request.json", "state.json"]:
        doc = jobs.read(target / name)
        doc["job_id"] = target.name
        jobs.atomic(target / name, doc)
    with pytest.raises(ValueError, match="same acquisition"):
        manager.compare_runs([source.name, target.name], kind)
    with pytest.raises(ValueError, match="not captured"):
        manager.compare_runs(
            [source.name, target.name], next(k for k in ["WF-01", "WF-02", "WF-03"] if k != kind)
        )
    state = jobs.read(source / "state.json")
    jobs.atomic(source / "state.json", {**state, "phase": "running"})
    with pytest.raises(ValueError, match="close"):
        manager.run_details(source.name)
    jobs.atomic(source / "state.json", state)
    (source / "capture/artifacts.json").write_text("{}")
    with pytest.raises(ValueError):
        manager.run_details(source.name)


def row(run_id="one", **updates):
    result = dict(
        workflow="WF-01",
        run_id=run_id,
        mode="physical",
        execution="completed",
        metrics=dict(mean_W="0.001", zero_W="-0.00000001"),
        context=dict(meter_serial="M", sensor_serial="S", signal=dict(source="POWER REF")),
        profile=dict(duration_s=300),
        unknown_context=[],
        resource="USB0::example",
    )
    result.update(updates)
    return result


def test_independent_decimal_delta_and_each_context_exclusion():
    first = row()
    second = row("two", metrics=dict(mean_W="0.001002", zero_W="0"))

    def compare(a, b):
        return run_history.compare(
            [("a", dict(workflows=[a])), ("b", dict(workflows=[b]))], "WF-01"
        )

    result = compare(first, second)
    assert result["changes_available"] and result["rows"][1]["mean_change_W"] == "0.000002"
    cases = [
        dict(mode="synthetic"),
        dict(execution="interrupted"),
        dict(unknown_context=["sensor_serial"]),
        dict(context=dict(meter_serial="different")),
        dict(profile=dict(duration_s=600)),
        dict(resource="other"),
        dict(profile=None),
    ]
    for change in cases:
        result = compare(first, row("two", **change))
        assert not result["changes_available"] and result["notes"]
        assert all(x["mean_change_W"] is None for x in result["rows"])
    result = compare(first, row("two", metrics=dict(mean_W=None)))
    assert not result["changes_available"]


def test_original_confirmation_hash_is_checked(manager, source):
    jobs.atomic(
        source / "operator-confirmation.json",
        dict(
            schema="hp437b.operator-front-panel.v1",
            job_id=source.name,
            live_readings=True,
            rmt_off=True,
            power_ref_off=True,
            capture_inventory_sha256="0" * 64,
        ),
    )
    with pytest.raises(ValueError, match="different evidence"):
        manager.run_details(source.name)


def test_http_read_only_history_and_comparison_boundaries(manager, source):
    import urllib.error

    generator = ui_tests.http_server.__wrapped__()
    create = next(generator)
    try:
        _, _, request, _, _ = create(manager)
        with request("/api/run-history", dict(offset=0, category="all")) as response:
            assert json.loads(response.read())["total"] == 1
        with request("/api/run-details", dict(job_id=source.name)) as response:
            assert json.loads(response.read())["source_job_id"] == source.name
        for endpoint, body in [
            ("/api/run-history", dict(offset=0, category="all", path="/tmp")),
            ("/api/run-comparison", dict(job_ids=[source.name, source.name], workflow="WF-01")),
        ]:
            with pytest.raises(urllib.error.HTTPError):
                request(endpoint, body)
        with pytest.raises(urllib.error.HTTPError):
            request("/api/run-details", dict(job_id=source.name), {"Origin": "http://untrusted"})
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_native_metric_oracles_and_immutable_capture(manager, source):
    import csv
    from decimal import Decimal, localcontext

    capture = source / "capture"
    before = {
        str(p.relative_to(capture)): r.digest(p.read_bytes())
        for p in capture.rglob("*")
        if p.is_file()
    }
    detail = manager.run_details(source.name)
    row = detail["workflows"][0]
    kind = row["workflow"]

    def values(name):
        with (capture / "stages" / name).open() as handle:
            return [Decimal(x["value"]) for x in csv.DictReader(handle) if x["status"] == "ok"]

    with localcontext() as context:
        context.prec = 50
        zero = values("S10.csv" if kind == "WF-01" else "baseline-before.csv")
        assert abs(Decimal(row["metrics"]["zero_W"]) - sum(zero) / len(zero)) < Decimal("1e-28")
        if kind == "WF-03":
            cycles = [values(f"C{i:02d}-plateau.csv") for i in range(1, 6)]
            oracle = sum(sum(x) / len(x) for x in cycles) / len(cycles)
            assert row["metrics"]["valid_plateau"] == sum(map(len, cycles))
            assert row["metrics"]["completed_cycles"] == 5
        else:
            plateau = values("S40.csv" if kind == "WF-01" else "plateau.csv")
            oracle = sum(plateau) / len(plateau)
            assert row["metrics"]["valid_plateau"] == len(plateau)
        assert abs(Decimal(row["metrics"]["mean_W"]) - oracle) < Decimal("1e-28")
    assert before == {
        str(p.relative_to(capture)): r.digest(p.read_bytes())
        for p in capture.rglob("*")
        if p.is_file()
    }


def test_history_respects_capture_guard_and_invalid_attestation(manager, source):
    import fcntl

    with (source / ".capture.lock").open("a+b") as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="still owns"):
            manager.run_details(source.name)
    jobs.atomic(source / "operator-confirmation.json", dict(schema="other", job_id=source.name))
    with pytest.raises(ValueError, match="attestation"):
        manager.run_details(source.name)
