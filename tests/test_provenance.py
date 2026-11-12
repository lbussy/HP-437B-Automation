"""Independent provenance oracles, malformed evidence, and additive WF-01 import."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from hp437b import provenance as p


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def seal(root, mode="physical"):
    entries = {}
    for path in root.rglob("*"):
        if path.is_file() and path.name not in ("artifacts.json", "completion-artifacts.json"):
            data = path.read_bytes()
            entries[str(path.relative_to(root))] = {
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
    dump(root / "artifacts.json", {"mode": mode, "artifacts": entries})


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "capture"
    workflow = {
        "workflow_id": "power-reference-v1",
        "run_id": "test-A",
        "mode": "physical",
        "simulation": False,
        "status": "completed",
        "started_utc": "2026-11-12T12:00:00+00:00",
        "finished_utc": "2026-11-12T12:05:00+00:00",
        "profile": {"unit": "W", "duration_s": 300},
        "software": {"commit": "fixture", "dirty": True},
        "setup": {
            "meter_serial": "M-001",
            "sensor_serial": "S-001",
            "known_issues": ["meter issue: supplied, not a new test"],
            "calibration_references": [
                {"certificate": "fictional", "path": "../../do-not-open.pdf", "sha256": "0" * 64}
            ],
            "reference_cal_factor_percent": {
                "value": "99",
                "origin": "historical label, 2026-11-11",
            },
            "active_measurement_cal_factor_percent": {
                "value": "100",
                "origin": "historical setting, not reread",
            },
        },
        "sessions": [
            {
                "identity": {
                    "manufacturer": "HEWLETT-PACKARD",
                    "model": "437B",
                    "serial": "",
                    "firmware": "1.8",
                    "raw": "fictional",
                }
            }
        ],
        "stages": {"S40": {"status": "completed"}},
        "final_state": {"source": "off", "front_panel_confirmation": "pending"},
    }
    dump(root / "workflow.json", workflow)
    path = root / "stages/S40.csv"
    path.parent.mkdir()
    path.write_text("session_id,sequence,value,unit,status\nfixture-session,1,0.000988,W,ok\n")
    dump(
        root / "stages/S40.csv.session.json",
        {
            "simulation": False,
            "session_id": "fixture-session",
            "rows": 1,
            "host": "fictional host",
            "context": {"workflow_run_id": "test-A"},
        },
    )
    seal(root)
    return root


def change_manifest(root, action, mode="physical"):
    path = root / "workflow.json"
    data = json.loads(path.read_text())
    action(data)
    dump(path, data)
    seal(root, mode)


def test_import_separates_supplied_observed_derived_unknown(bundle):
    value = p.import_wf01(bundle)
    assert value["schema"] == p.SCHEMA and value["run"]["run_id"] == "test-A"
    assert value["dut"]["kind"] == "reference_signal"
    meter, sensor, adapter, host = value["equipment"]
    assert meter["facts"]["label_serial"]["basis"] == "supplied"
    assert meter["facts"]["reported_identifications"]["basis"] == "observed"
    assert meter["facts"]["reported_serial"]["basis"] == "unknown"
    assert meter["facts"]["reported_serial"]["value"] is None
    assert sensor["facts"]["reference_cal_factor_percent"]["observed_at"] is None
    assert "historical" in sensor["facts"]["reference_cal_factor_percent"]["value"]["origin"]
    assert meter["facts"]["calibration_references"]["basis"] == "unknown"
    assert sensor["facts"]["known_issues"]["basis"] == "unknown"
    assert value["run"]["facts"]["calibration_references"]["basis"] == "supplied"
    assert "do-not-open" in value["run"]["facts"]["calibration_references"]["value"][0]["path"]
    assert adapter["facts"]["identity_limit"]["basis"] == "derived"
    assert host["facts"]["recorded_platforms"]["value"] == ["fictional host"]
    assert p.verify(value, bundle)


def test_export_is_repeatable_and_leaves_capture_unchanged(bundle, tmp_path):
    before = {str(f.relative_to(bundle)): f.read_bytes() for f in bundle.rglob("*") if f.is_file()}
    first = p.export_wf01(bundle, tmp_path / "prov-A")
    second = p.export_wf01(bundle, tmp_path / "prov-B")
    assert first == second
    assert p.load(tmp_path / "prov-A/provenance.json") == first
    assert before == {
        str(f.relative_to(bundle)): f.read_bytes() for f in bundle.rglob("*") if f.is_file()
    }
    manifest = json.loads((tmp_path / "prov-A/artifacts.json").read_text())
    for name, expected in manifest["artifacts"].items():
        data = (tmp_path / "prov-A" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected["sha256"]
    with pytest.raises(p.ProvenanceError):
        p.export_wf01(bundle, tmp_path / "prov-A")
    with pytest.raises(p.ProvenanceError):
        p.export_wf01(bundle, bundle / "do-not-add")
    assert not (bundle / "do-not-add").exists()


def test_label_identity_reuse_and_conflicting_history_is_not_overwritten(bundle):
    first = p.import_wf01(bundle)
    change_manifest(
        bundle,
        lambda w: (w.update(run_id="test-B"), w["sessions"][0]["identity"].update(firmware="1.9")),
    )
    meta = bundle / "stages/S40.csv.session.json"
    data = json.loads(meta.read_text())
    data["context"]["workflow_run_id"] = "test-B"
    dump(meta, data)
    seal(bundle)
    second = p.import_wf01(bundle)
    assert first["equipment"][0]["equipment_id"] == second["equipment"][0]["equipment_id"]
    assert first["equipment"][2]["equipment_id"] != second["equipment"][2]["equipment_id"]
    history = p.equipment_history([first, second, first])
    snapshots = history[first["equipment"][0]["equipment_id"]]
    assert len(snapshots) == 2
    assert [s["facts"]["reported_identifications"]["value"][0]["firmware"] for s in snapshots] == [
        "1.8",
        "1.9",
    ]


def test_forged_copied_value_does_not_verify(bundle):
    value = p.import_wf01(bundle)
    value["equipment"][0]["facts"]["label_serial"]["value"] = "FORGED"
    with pytest.raises(p.ProvenanceError, match="disagrees"):
        p.verify(value, bundle)


@pytest.mark.parametrize(
    "case",
    [
        "tamper",
        "missing",
        "escape",
        "symlink",
        "unsealed",
        "bad-pointer",
        "cross-run",
        "mode",
        "session-mode",
    ],
)
def test_invalid_evidence_refused_before_creating_export(bundle, tmp_path, case):
    if case == "tamper":
        (bundle / "stages/S40.csv").write_text("changed")
    elif case == "missing":
        (bundle / "stages/S40.csv").unlink()
    elif case == "escape":
        manifest = json.loads((bundle / "artifacts.json").read_text())
        manifest["artifacts"]["../outside"] = {"bytes": 0, "sha256": "0" * 64}
        dump(bundle / "artifacts.json", manifest)
    elif case == "symlink":
        path = bundle / "stages/S40.csv"
        data = path.read_bytes()
        outside = tmp_path / "outside.csv"
        outside.write_bytes(data)
        path.unlink()
        path.symlink_to(outside)
    elif case == "unsealed":
        (bundle / "artifacts.json").unlink()
    elif case == "cross-run":
        path = bundle / "stages/S40.csv.session.json"
        data = json.loads(path.read_text())
        data["context"]["workflow_run_id"] = "OTHER"
        dump(path, data)
        seal(bundle)
    elif case == "mode":
        change_manifest(bundle, lambda w: w.update(simulation=True))
    elif case == "session-mode":
        path = bundle / "stages/S40.csv.session.json"
        data = json.loads(path.read_text())
        data["simulation"] = True
        dump(path, data)
        seal(bundle)
    elif case == "bad-pointer":
        value = p.import_wf01(bundle)
        value["equipment"][0]["facts"]["label_serial"]["refs"][0]["pointer"] = "/absent"
        with pytest.raises(p.ProvenanceError):
            p.verify(value, bundle)
        return
    with pytest.raises(p.ProvenanceError):
        p.export_wf01(bundle, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


@pytest.mark.parametrize("raw", ['{"mode":1,"mode":2}', '{"value":NaN}', '{"value":1e9999}'])
def test_ambiguous_or_nonfinite_json_is_rejected(bundle, tmp_path, raw):
    (bundle / "workflow.json").write_text(raw)
    with pytest.raises(p.ProvenanceError):
        p.export_wf01(bundle, tmp_path / "out")


def test_operator_confirmation_is_a_separate_supplied_attestation(bundle):
    base_hash = hashlib.sha256((bundle / "artifacts.json").read_bytes()).hexdigest()
    operator = {
        "mode": "physical",
        "run_id": "test-A",
        "confirmed_utc": "2026-11-12T12:06:00+00:00",
        "rmt_off": True,
    }
    dump(bundle / "operator-confirmation.json", operator)
    data = (bundle / "operator-confirmation.json").read_bytes()
    dump(
        bundle / "completion-artifacts.json",
        {
            "mode": "physical",
            "base_inventory_sha256": base_hash,
            "artifacts": {
                "operator-confirmation.json": {
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            },
        },
    )
    value = p.import_wf01(bundle)
    assert value["run"]["facts"]["operator_confirmation"]["basis"] == "supplied"
    assert (
        value["run"]["facts"]["capture_final_state"]["value"]["front_panel_confirmation"]
        == "pending"
    )
    operator["run_id"] = "OTHER"
    dump(bundle / "operator-confirmation.json", operator)
    with pytest.raises(p.ProvenanceError):
        p.import_wf01(bundle)


def test_generic_record_supports_an_external_dut_without_wf01_relabeling(tmp_path):
    source = {"purpose": "measure an amplifier", "model": "fictional amplifier"}
    dump(tmp_path / "setup.json", source)
    data = (tmp_path / "setup.json").read_bytes()
    ev = {
        "evidence_id": "setup",
        "path": "setup.json",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }

    def f(key):
        return p.fact(
            source[key], basis="supplied", refs=[{"evidence_id": "setup", "pointer": "/" + key}]
        )

    device = p.equipment("asset:amp-1", "device_under_test", {"model": f("model")})
    subject = p.dut(
        "dut:amp-1", "external_device", [device["equipment_id"]], {"description": f("model")}
    )
    value = p.record(
        "run:gain-1", "synthetic", "gain-v1", {"purpose": f("purpose")}, subject, [device], [ev]
    )
    assert p.verify(value, tmp_path)
    p.write(tmp_path / "record.json", value)
    assert p.load(tmp_path / "record.json") == value
    with pytest.raises(FileExistsError):
        p.write(tmp_path / "record.json", value)


@pytest.mark.parametrize(
    "basis,value,note",
    [
        ("unknown", 1, "reason"),
        ("unknown", None, ""),
        ("observed", None, ""),
        ("magic", 1, ""),
        ([], 1, ""),
    ],
)
def test_invalid_fact_is_rejected(basis, value, note):
    with pytest.raises(p.ProvenanceError):
        p.fact(value, basis=basis, note=note)


def test_missing_equipment_and_evidence_references_are_rejected(bundle):
    value = p.import_wf01(bundle)
    bad = copy.deepcopy(value)
    bad["dut"]["equipment_refs"] = ["missing"]
    with pytest.raises(p.ProvenanceError):
        p.validate(bad)
    bad = copy.deepcopy(value)
    bad["equipment"][0]["facts"]["label_serial"]["refs"][0]["evidence_id"] = "missing"
    with pytest.raises(p.ProvenanceError):
        p.validate(bad)


def test_bundle_code_is_never_executed(bundle, tmp_path):
    marker = tmp_path / "must-not-exist"
    (bundle / "runner.py").write_text(f"raise RuntimeError({str(marker)!r})\n")
    seal(bundle)
    p.import_wf01(bundle)
    assert not marker.exists()


def test_new_sidecar_cannot_clobber_an_existing_path(bundle, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    (output / "precious").write_text("keep")
    with pytest.raises(p.ProvenanceError):
        p.export_wf01(bundle, output)
    assert (output / "precious").read_text() == "keep"


@pytest.mark.parametrize("raw", ["[]", "null", "123"])
def test_nonobject_manifest_is_rejected(bundle, raw):
    (bundle / "workflow.json").write_text(raw)
    with pytest.raises(p.ProvenanceError):
        p.import_wf01(bundle)


def test_timezone_naive_timestamp_is_rejected(bundle):
    change_manifest(bundle, lambda w: w.update(started_utc="2026-11-12T12:00:00"))
    with pytest.raises(p.ProvenanceError):
        p.import_wf01(bundle)


def test_legacy_synthetic_id_is_derived_and_does_not_become_physical(bundle):
    path = bundle / "stages/S40.csv.session.json"
    data = json.loads(path.read_text())
    data["simulation"] = True
    del data["context"]["workflow_run_id"]
    dump(path, data)
    change_manifest(
        bundle,
        lambda w: (w.pop("run_id"), w.update(mode="synthetic", simulation=True)),
        mode="synthetic",
    )
    value = p.import_wf01(bundle)
    assert value["run"]["mode"] == "synthetic"
    assert value["run"]["run_id"].startswith("wf01-import:")
    assert value["run"]["facts"]["source_run_id"]["basis"] == "unknown"
    assert value["dut"]["kind"] == "reference_signal"


def test_copied_boolean_cannot_be_replaced_by_integer_zero(bundle):
    value = p.import_wf01(bundle)
    f = value["run"]["facts"]["capture_final_state"]
    f["value"]["test"] = False
    # Use an explicit JSON boolean source fact, then attempt Python's False == 0 shortcut.
    change_manifest(bundle, lambda w: w.update(boolean=False))
    value = p.import_wf01(bundle)
    ref = {"evidence_id": "workflow.json", "pointer": "/boolean"}
    value["run"]["facts"]["boolean"] = p.fact(0, basis="observed", refs=[ref])
    with pytest.raises(p.ProvenanceError, match="disagrees"):
        p.verify(value, bundle)


def test_failed_run_does_not_become_completed(bundle):
    change_manifest(bundle, lambda w: w.update(status="failed"))
    assert p.import_wf01(bundle)["run"]["facts"]["execution_status"]["value"] == "failed"


def test_resealed_inventory_cannot_hide_absent_capture(bundle):
    (bundle / "stages/S40.csv").unlink()
    seal(bundle)
    with pytest.raises(p.ProvenanceError, match="pair"):
        p.import_wf01(bundle)


def test_export_storage_failure_never_creates_a_completion_manifest(bundle, tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("injected provenance storage failure")

    monkeypatch.setattr(p.os, "fsync", fail)
    output = tmp_path / "failed-export"
    with pytest.raises(OSError, match="injected provenance"):
        p.export_wf01(bundle, output)
    assert not (output / "artifacts.json").exists()


def test_pointer_escaping_and_generic_round_trip(tmp_path):
    data = {"a/b": {"~key": 0}}
    dump(tmp_path / "source.json", data)
    raw = (tmp_path / "source.json").read_bytes()
    evidence = {
        "evidence_id": "source",
        "path": "source.json",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    f = p.fact(
        0,
        basis="observed",
        refs=[{"evidence_id": "source", "pointer": "/a~1b/~0key"}],
        observed_at="2026-11-12T12:00:00Z",
    )
    subject = p.dut("test-subject", "external_device", [], {"observed_zero": f})
    value = p.record("run-zero", "synthetic", "generic-v1", {}, subject, [], [evidence])
    assert p.verify(value, tmp_path)


@pytest.mark.parametrize("value", [{1: "not a string key"}, (1, 2), float("nan"), float("inf")])
def test_non_native_or_nonfinite_values_refused(value):
    with pytest.raises(p.ProvenanceError):
        p.fact(value, basis="supplied", refs=[{"evidence_id": "input", "pointer": ""}])


def test_future_synthetic_workflow_emits_detached_standard_record(tmp_path):
    from runpy import run_path

    runner = run_path(str(Path(__file__).parents[1] / "tools/exercise_workflow.py"))["run"]
    output = tmp_path / "capture"
    capture = runner(output)
    value = p.load(p.sidecar_path(output) / "provenance.json")
    assert value["run"]["mode"] == "synthetic"
    assert value["run"]["run_id"] == capture["run_id"]
    assert value["run"]["facts"]["source_run_id"]["basis"] == "observed"
    assert value["run"]["facts"]["execution_status"]["value"] == "completed"
    assert p.verify(value, output)
    assert not (output / "provenance.json").exists()


def test_future_sidecar_conflict_stops_before_synthetic_session_creation(tmp_path, monkeypatch):
    from runpy import run_path

    runner = run_path(str(Path(__file__).parents[1] / "tools/exercise_workflow.py"))["run"]
    output = tmp_path / "capture"
    p.sidecar_path(output).mkdir()

    def forbidden(*args):
        pytest.fail("must reject before constructing a session")

    monkeypatch.setitem(runner.__globals__, "Bench", forbidden)
    with pytest.raises(FileExistsError):
        runner(output)
    assert not output.exists()
