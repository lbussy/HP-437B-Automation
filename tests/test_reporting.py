"""Reporting independently checks captures, provenance, output, and analysis boundaries."""

import csv
import hashlib
import io
import json

import pytest

from hp437b import provenance as p
from hp437b import reporting as r


# Independent, fictional, small capture; no real measurements in test fixtures.
@pytest.fixture
def capture(tmp_path):
    root = tmp_path / "source"
    (root / "stages").mkdir(parents=True)
    workflow = {
        "workflow_id": "power-reference-v1",
        "run_id": "fictional-report",
        "mode": "synthetic",
        "simulation": True,
        "status": "failed",
        "stages": {"S40": {"status": "failed"}},
        "final_state": {"source": "unknown", "local": "unknown"},
        "profile": {"unit": "W", "interval_s": 1},
        "provenance": {
            "meter": "fictional",
            "sensor": "fictional",
            "known_equipment_issues": "<script>alert('source instructions')</script>",
        },
    }
    (root / "workflow.json").write_bytes(r.encoded(workflow))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "session_id",
            "sequence",
            "received_utc",
            "elapsed_s",
            "value",
            "unit",
            "status",
            "raw_hex",
            "error",
            "instrument_error",
        ]
    )
    for seq, value, raw in [
        (1, "0.001", b"+1.0000E-03\r\n"),
        (2, "0.003", b"+3.0000E-03\r\n"),
        (3, "", b""),
    ]:
        writer.writerow(
            [
                "fictional-session",
                seq,
                f"2026-11-12T00:00:0{seq}+00:00",
                seq * 2,
                value,
                "W",
                "ok" if value else "failed",
                raw.hex(),
                "" if value else "fictional timeout",
                "",
            ]
        )
    (root / "stages/S40.csv").write_text(stream.getvalue())
    (root / "stages/S40.csv.session.json").write_bytes(
        r.encoded(
            {
                "session_id": "fictional-session",
                "simulation": True,
                "status": "failed",
                "rows": 3,
                "settings": {"unit": "W"},
                "context": {"stage_id": "S40", "workflow_run_id": "fictional-report"},
            }
        )
    )
    reseal(root)
    provenance = tmp_path / "provenance" / "provenance.json"
    provenance.parent.mkdir()
    p.write(provenance, p.import_wf01(root))
    return root, provenance


def reseal(root):
    entries = {}
    for file in root.rglob("*"):
        if file.is_file() and file.name != "artifacts.json":
            data = file.read_bytes()
            entries[file.relative_to(root).as_posix()] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
    (root / "artifacts.json").write_bytes(r.encoded({"mode": "synthetic", "artifacts": entries}))


def reimport(root, path):
    reseal(root)
    path.unlink()
    p.write(path, p.import_wf01(root))


def response(packet):
    return {
        "schema": r.AGENT_SCHEMA,
        "packet_sha256": r.digest(r.encoded(packet)),
        "run_id": packet["run_id"],
        "author": "fictional analysis fixture",
        "created_utc": "2026-11-12T12:00:00+00:00",
        "model": None,
        "findings": [
            {
                "kind": "limitation",
                "text": "The failed execution retains partial measurements; no measurement acceptance criteria were evaluated.",
                "refs": ["workflow/status", "S40/nonvalid", "scope/0"],
            }
        ],
    }


def test_independent_statistics_and_failure_gaps(capture):
    root, provenance = capture
    _, result, packet = r.prepare(root, provenance)
    stage = result["stages"]["S40"]
    assert (stage["attempted"], stage["valid"], stage["nonvalid"]) == (3, 2, 1)
    assert stage["metrics"]["mean_W"] == "0.002"
    assert stage["metrics"]["peak_to_peak_W"] == "0.002"
    assert stage["metrics"]["sample_sd_W"].startswith("0.001414213562373095")
    assert stage["median_receipt_spacing_s"] == 2
    assert stage["receipt_span_s"] == 4
    assert stage["points"][-1]["value_W"] is None
    assert result["stages"]["S10"] == {"outcome": "not_recorded", "capture": "absent"}
    assert packet["mode"] == "synthetic" and packet["facts"]["S40/mean_W"]["unit"] == "W"


def test_read_only_export_inventory_and_escaped_html(capture, tmp_path):
    root, provenance = capture
    before = {str(f): f.read_bytes() for f in root.rglob("*") if f.is_file()}
    out = tmp_path / "report"
    r.export(root, provenance, out, plots=False)
    assert before == {str(f): f.read_bytes() for f in root.rglob("*") if f.is_file()}
    page = (out / "report.html").read_text()
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert "Content-Security-Policy" in page and "<img" not in page
    assert "NOT EVALUATED" in page and "No captured samples" not in page
    manifest = json.loads((out / "artifacts.json").read_text())
    assert manifest["agent_analysis"] == "not_supplied" and manifest["plots"] is False
    for name, entry in manifest["artifacts"].items():
        data = (out / name).read_bytes()
        assert len(data) == entry["bytes"] and r.digest(data) == entry["sha256"]
    assert (out / "analysis-packet.json").read_bytes() == r.encoded(r.prepare(root, provenance)[2])
    with pytest.raises(p.ProvenanceError, match="exists"):
        r.export(root, provenance, out, plots=False)


@pytest.mark.parametrize(
    "change",
    [
        "value",
        "sequence",
        "unit",
        "session",
        "elapsed",
        "utc",
        "status",
        "raw",
        "failed-value",
        "header",
        "nan",
    ],
)
def test_resealed_bad_csv_rejected(capture, change):
    root, provenance = capture
    path = root / "stages/S40.csv"
    text = path.read_text()
    if change == "value":
        text = text.replace("0.001,W", "0.002,W")
    elif change == "sequence":
        text = text.replace("fictional-session,2,", "fictional-session,4,")
    elif change == "unit":
        text = text.replace(",W,", ",dBm,")
    elif change == "session":
        text = text.replace("fictional-session,2,", "other-session,2,")
    elif change == "elapsed":
        text = text.replace(",4,0.003,", ",1,0.003,")
    elif change == "utc":
        text = text.replace("00:00:02+00:00", "00:00:00+00:00")
    elif change == "status":
        text = text.replace(",ok,", ",passing,")
    elif change == "raw":
        text = text.replace(b"+1.0000E-03\r\n".hex(), "41414141")
    elif change == "failed-value":
        text = text.replace(",6,,W,", ",6,0,W,")
    elif change == "header":
        text = text.replace("session_id,sequence", "sequence,sequence")
    else:
        text = text.replace(",2,0.001,", ",NaN,0.001,")
    path.write_text(text)
    reimport(root, provenance)
    with pytest.raises(p.ProvenanceError):
        r.prepare(root, provenance)


@pytest.mark.parametrize("change", ["rows", "simulation", "stage", "status", "settings"])
def test_bad_sidecar_rejected(capture, change):
    root, provenance = capture
    path = root / "stages/S40.csv.session.json"
    data = json.loads(path.read_text())
    if change == "rows":
        data["rows"] = 2
    elif change == "simulation":
        data["simulation"] = False
    elif change == "stage":
        data["context"]["stage_id"] = "S10"
    elif change == "status":
        data["status"] = "running"
    else:
        data["settings"]["unit"] = "dBm"
    path.write_bytes(r.encoded(data))
    reseal(root)
    with pytest.raises(p.ProvenanceError):
        r.prepare(root, provenance)


def test_stale_provenance_and_saved_calculation(capture):
    root, provenance = capture
    path = root / "workflow.json"
    data = json.loads(path.read_text())
    data["final_state"]["source"] = "off"
    path.write_bytes(r.encoded(data))
    reseal(root)
    with pytest.raises(p.ProvenanceError):
        r.prepare(root, provenance)
    (root / "analysis.json").write_bytes(
        r.encoded({"stages": {"S40": {"attempted": 3, "valid": 3, "nonvalid": 0}}})
    )
    reimport(root, provenance)
    with pytest.raises(p.ProvenanceError, match="count mismatch"):
        r.prepare(root, provenance)


def test_zero_mean_and_one_point_are_undefined(capture):
    root, _ = capture
    data = (root / "stages/S40.csv").read_bytes()
    meta = json.loads((root / "stages/S40.csv.session.json").read_text())
    # Zero mean from signed raw values; valid zeros must not disappear.
    data = data.replace(b"0.001,W", b"-0.003,W").replace(
        b"+1.0000E-03\r\n".hex().encode(), b"-3.0000E-03\r\n".hex().encode()
    )
    result = r.stage_result(data, meta, "synthetic", "S40", "failed")
    assert result["metrics"]["mean_W"] == "0.000"
    assert result["metrics"]["relative_peak_to_peak_percent"] is None
    one = b"\n".join(data.splitlines()[:2]) + b"\n"
    meta["rows"] = 1
    result = r.stage_result(one, meta, "synthetic", "S40", "failed")
    assert result["metrics"]["sample_sd_W"] is None and result["receipt_span_s"] == 0


@pytest.mark.parametrize(
    "change", ["digest", "run", "reference", "verdict", "extra", "empty", "model"]
)
def test_agent_binding_and_schema_rejections(capture, change):
    _, _, packet = r.prepare(*capture)
    value = response(packet)
    if change == "digest":
        value["packet_sha256"] = "0" * 64
    elif change == "run":
        value["run_id"] = "other"
    elif change == "reference":
        value["findings"][0]["refs"] = ["invented/accuracy"]
    elif change == "verdict":
        value["findings"][0]["kind"] = "pass"
    elif change == "extra":
        value["commands"] = ["OC1"]
    elif change == "empty":
        value["findings"] = []
    else:
        value["model"] = False
    with pytest.raises(p.ProvenanceError):
        r.validate_agent(value, packet)


def test_agent_import_and_literal_prose(capture, tmp_path):
    root, provenance = capture
    _, _, packet = r.prepare(root, provenance)
    agent = response(packet)
    agent["findings"][0]["text"] += " <img src=https://evil.invalid> [click](https://evil.invalid)"
    analysis = tmp_path / "agent.json"
    analysis.write_bytes(r.encoded(agent))
    out = tmp_path / "agent-report"
    r.export(root, provenance, out, analysis_path=analysis, plots=False)
    appendix = (out / "evidence.html").read_text()
    assert (
        "DRAFT" in appendix and "<img src=https" not in appendix and "href='https" not in appendix
    )
    assert json.loads((out / "artifacts.json").read_text())["agent_analysis"] == "draft"


def test_existing_source_and_provenance_protected(capture):
    root, provenance = capture
    for output in (root, root / "report", provenance.parent / "report"):
        with pytest.raises(p.ProvenanceError):
            r.export(root, provenance, output, plots=False)


def test_failure_never_seals_report(capture, tmp_path, monkeypatch):
    def fail(*args):
        raise OSError("fictional disk full")

    monkeypatch.setattr(r, "plot", fail)
    out = tmp_path / "broken"
    with pytest.raises(OSError):
        r.export(*capture, out)
    assert not (out / "artifacts.json").exists()


def test_plot_exports_real_png_and_svg(capture, tmp_path):
    pytest.importorskip("matplotlib")
    out = tmp_path / "plots"
    r.export(*capture, out)
    assert (out / "power.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "<svg" in (out / "power.svg").read_text()
    assert "SYNTHETIC" in (out / "power.svg").read_text()


def test_cli_failure_is_nonzero_and_no_hardware(capture, tmp_path):
    assert (
        r.main(
            [
                "--bundle",
                str(capture[0]),
                "--provenance",
                str(capture[1]),
                "--output",
                str(tmp_path / "cli"),
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        r.main(
            [
                "--bundle",
                str(capture[0]),
                "--provenance",
                str(capture[1]),
                "--output",
                str(tmp_path / "cli"),
                "--no-plots",
            ]
        )
        == 1
    )


def test_failed_inventory_flush_does_not_publish(capture, tmp_path, monkeypatch):
    def fail(fd):
        raise OSError("fictional inventory flush failure")

    monkeypatch.setattr(r.os, "fsync", fail)
    out = tmp_path / "failed-seal"
    with pytest.raises(OSError, match="flush failure"):
        r.export(*capture, out, plots=False)
    assert not (out / "artifacts.json").exists()


def test_packet_records_original_and_normalized_provenance(capture):
    _, provenance = capture
    _, _, packet = r.prepare(*capture)
    assert packet["input_provenance_sha256"] == r.digest(provenance.read_bytes())
    assert packet["provenance_sha256"] == r.digest(r.encoded(p.load(provenance)))
