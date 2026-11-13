"""Profile validation, preserved provenance, and fake-only single-workflow execution."""

import json
from decimal import Decimal as D

import pytest

from hp437b import controlled_sweep as s
from hp437b import provenance as p
from hp437b import reporting as r
from hp437b import test_profiles as t
from hp437b.workflow_report import _seal


def snapshot(source):
    return {
        str(path.relative_to(source)): r.digest(path.read_bytes())
        for path in source.rglob("*")
        if path.is_file()
    }


def criteria(kind):
    result = dict(
        source="Fictional example limits",
        decision_rule="inclusive-no-guard-band",
        min_samples_per_point=30,
        max_gap_s="1",
    )
    result["max_abs_change_percent" if kind == "WF-06" else "max_abs_error_percent"] = "10"
    return result


@pytest.mark.parametrize("kind", t.KINDS)
def test_profile_runs_existing_pipeline_with_supplied_identity_and_limits(tmp_path, kind):
    profile = t.example()
    profile["operator"] = "Profile operator"
    profile["dut"].update(
        manufacturer="Fictional maker",
        model="TX Example",
        serial="EXAMPLE-123",
        asset_id="example:tx",
    )
    profile["workflows"][kind]["criteria"] = criteria(kind)
    source = tmp_path / "capture"
    record = t.capture(profile, kind, source, plots=False)
    assert record["status"] == "completed" and record["operator"] == "Profile operator"
    binding = p._json((source / "test-profile.json").read_bytes())
    assert binding["operator"]["origin"] == "profile"
    assert binding["profile"] == profile
    w = s.module(kind)
    cap, rows, bundle = w.load(source)
    result = w.analyze(cap, rows)
    assert result["acceptance"] == "PASS"
    assert D(result["zero_mean_W"]) == D("-2E-8")
    prov = w.provenance(cap, bundle)
    p.verify(prov, source)
    assert prov["dut"]["facts"]["profile_identity"]["value"]["serial"] == "EXAMPLE-123"
    assert prov["run"]["facts"]["test_profile"]["value"] == binding
    before = snapshot(source)
    profile["revision"] += 1
    profile["dut"]["serial"] = "LATER"
    first = w.publish(source, tmp_path / "report", plots=False)
    second = w.publish(source, tmp_path / "again", plots=False)
    assert first == second == result and snapshot(source) == before
    assert "Profile operator" in (tmp_path / "report/report.html").read_text()
    assert "EXAMPLE-123" in (tmp_path / "report/appendix.html").read_text()


@pytest.mark.parametrize(
    "origin,explicit,stored,env,expected",
    [
        ("argument", "Chosen", "Saved", "Env", "Chosen"),
        ("profile", None, "Saved", "Env", "Saved"),
        ("environment", None, None, "Env", "Env"),
        ("not_recorded", None, None, None, None),
    ],
)
def test_operator_precedence_preserved_without_environment_on_import(
    tmp_path, monkeypatch, origin, explicit, stored, env, expected
):
    monkeypatch.delenv("HP437B_OPERATOR", raising=False)
    if env:
        monkeypatch.setenv("HP437B_OPERATOR", env)
    profile = t.example()
    profile["operator"] = stored
    source = tmp_path / "capture"
    t.capture(profile, "WF-04", source, operator=explicit, plots=False)
    monkeypatch.setenv("HP437B_OPERATOR", "Changed later")
    cap, _, bundle = s.module("WF-04").load(source)
    assert cap["operator"] == expected
    assert bundle.json("test-profile.json")["operator"]["origin"] == origin


@pytest.mark.parametrize(
    "mutation",
    [
        "mode",
        "schema",
        "unknown-key",
        "id",
        "revision",
        "dut-name",
        "serial",
        "operator",
        "workflow",
        "empty",
        "points",
        "unselected-plan",
        "criteria",
        "physical-model",
    ],
)
def test_bad_profile_rejected_before_any_output_or_capture(tmp_path, monkeypatch, mutation):
    profile = t.example()
    if mutation == "mode":
        profile["mode"] = "physical"
    if mutation == "schema":
        profile["schema"] = "new-version"
    if mutation == "unknown-key":
        profile["command"] = "ssh wspr5"
    if mutation == "id":
        profile["profile_id"] = "../bad"
    if mutation == "revision":
        profile["revision"] = True
    if mutation == "dut-name":
        profile["dut"]["name"] = "Different"
    if mutation == "serial":
        profile["dut"]["serial"] = "two\nlines"
    if mutation == "operator":
        profile["operator"] = "\n"
    if mutation == "workflow":
        profile["workflows"]["WF-99"] = profile["workflows"].pop("WF-06")
    if mutation == "empty":
        profile["workflows"] = {}
    if mutation == "points":
        profile["workflows"]["WF-04"]["plan"]["points"][0]["point_id"] = "P99"
    if mutation == "unselected-plan":
        profile["workflows"]["WF-06"]["plan"]["supply"]["restore_V"] = "1000"
    if mutation == "criteria":
        profile["workflows"]["WF-05"]["criteria"] = dict(unknown=True)
    if mutation == "physical-model":
        profile["workflows"]["WF-06"]["plan"]["points"][0]["synthetic_DUT_W"] = "10000"

    def unexpected(*args, **kwargs):
        raise AssertionError("Capture called for invalid profile")

    monkeypatch.setattr(s, "run", unexpected)
    with pytest.raises((ValueError, KeyError, TypeError)):
        t.capture(profile, "WF-04", tmp_path / "capture")
    assert not (tmp_path / "capture").exists()


def test_detached_validated_values_and_single_workflow_selection(tmp_path):
    original = t.example()
    valid = t.validate(original)
    valid["dut"]["serial"] = "Edited"
    assert original["dut"]["serial"] is None
    original["workflows"] = {"WF-05": original["workflows"]["WF-05"]}
    assert t.validate(original)
    with pytest.raises(ValueError, match="not included"):
        t.capture(original, "WF-04", tmp_path / "no-output")
    assert not (tmp_path / "no-output").exists()


@pytest.mark.parametrize(
    "raw", [b'{"schema":1,"schema":2}', b'{"x":NaN}', b"[]", b" " * (t.MAX_PROFILE + 1)]
)
def test_bounded_strict_input(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises((ValueError, KeyError, TypeError)):
        t.load(path)


@pytest.mark.parametrize(
    "mutation", ["file", "profile-hash", "plan", "criteria", "operator", "workflow", "unbound"]
)
def test_resealed_corruption_cannot_rebind_evidence(tmp_path, mutation):
    source = tmp_path / "capture"
    t.capture(t.example(), "WF-04", source, plots=False)
    path = source / "test-profile.json"
    binding = json.loads(path.read_bytes())
    if mutation == "file":
        binding["profile"]["dut"]["serial"] = "Altered"
    if mutation == "profile-hash":
        binding["profile_sha256"] = "0" * 64
    if mutation == "plan":
        binding["profile"]["workflows"]["WF-04"]["plan"]["points"][0]["target_W"] = "2"
    if mutation == "criteria":
        binding["profile"]["workflows"]["WF-04"]["criteria"] = criteria("WF-04")
    if mutation == "operator":
        binding["operator"] = dict(value="Altered", basis="supplied", origin="argument")
    if mutation == "workflow":
        binding["workflow_kind"] = "WF-05"
    if mutation in ("plan", "criteria"):
        binding["profile_sha256"] = r.digest(r.encoded(binding["profile"]))
    path.write_bytes(r.encoded(binding))
    for name in ("starting.json", "workflow.json"):
        item = json.loads((source / name).read_bytes())
        if mutation == "unbound":
            del item["test_profile"]
        elif mutation != "file":
            item["test_profile"]["sha256"] = r.digest(path.read_bytes())
        (source / name).write_bytes(r.encoded(item))
    (source / "artifacts.json").unlink()
    cap = json.loads((source / "workflow.json").read_bytes())
    _seal(source, dict(schema=s.SCHEMA, mode="synthetic", run_id=cap["run_id"]))
    with pytest.raises((ValueError, KeyError, TypeError)):
        s.module("WF-04").publish(source, tmp_path / "no-report", plots=False)
    assert not (tmp_path / "no-report").exists()


@pytest.mark.parametrize(
    "fault,stop,status", [("meter-timeout", None, "failed"), (None, "P02", "interrupted")]
)
def test_failed_partial_capture_retains_profile_and_no_later_points(tmp_path, fault, stop, status):
    profile = t.example()
    source = tmp_path / "capture"
    t.capture(
        profile, "WF-04", source, fault=fault, fault_point="P02", stop_before=stop, plots=False
    )
    w = s.module("WF-04")
    cap, rows, bundle = w.load(source)
    assert cap["status"] == status and cap["operator"] is None
    assert len(cap["children"]) == (2 if fault else 1)
    assert bundle.json("test-profile.json")["profile"] == profile
    assert w.publish(source, tmp_path / "report", plots=False)["acceptance"] != "PASS"


def test_cli_template_validation_run_and_errors(tmp_path, capsys):
    assert t.main(["example"]) == 0
    document = json.loads(capsys.readouterr().out)
    path = tmp_path / "profile.json"
    path.write_bytes(r.encoded(document))
    assert t.main(["validate", "--profile", str(path)]) == 0
    for kind in t.KINDS:
        assert (
            t.main(
                [
                    "run",
                    "--profile",
                    str(path),
                    "--workflow",
                    kind,
                    "--output",
                    str(tmp_path / kind),
                    "--report-output",
                    str(tmp_path / (kind + "-report")),
                    "--no-plots",
                ]
            )
            == 0
        )
    assert (
        t.main(
            [
                "run",
                "--profile",
                str(path),
                "--workflow",
                "WF-04",
                "--output",
                str(tmp_path / "WF-04"),
                "--no-plots",
            ]
        )
        == 2
    )
    path.write_text("{}")
    assert t.main(["validate", "--profile", str(path)]) == 2


def test_independent_limits_can_fail_without_changing_measurements(tmp_path):
    profile = t.example()
    entry = profile["workflows"]["WF-04"]
    entry["criteria"] = criteria("WF-04")
    entry["criteria"]["max_abs_error_percent"] = "1"
    entry["plan"]["points"][1]["synthetic_DUT_W"] = "4.8"
    t.capture(profile, "WF-04", tmp_path / "capture", plots=False)
    w = s.module("WF-04")
    cap, rows, _ = w.load(tmp_path / "capture")
    result = w.analyze(cap, rows)
    assert result["execution"] == "completed" and result["acceptance"] == "FAIL"
    assert D(result["points"][1]["measured_W"]) == D("4.8")
