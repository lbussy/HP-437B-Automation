"""Real optional PDF generation, portable report integrity, and failure isolation."""

import zipfile
from pathlib import Path

import pytest

from hp437b import controlled_sweep as s
from hp437b import pdf_reports as pdf
from hp437b import provenance as p
from hp437b import report_delivery as d
from hp437b import reporting as r
from hp437b import test_profiles as t
from hp437b import test_suite as u
from hp437b.workflow_report import _seal

pytest.importorskip("reportlab")
pypdf = pytest.importorskip("pypdf")


def snapshot(root):
    return {
        str(path.relative_to(root)): r.digest(path.read_bytes())
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture(scope="module")
def captures(tmp_path_factory):
    root = tmp_path_factory.mktemp("pdf-captures")
    for kind in t.KINDS:
        s.module(kind).controlled(root / kind, operator="Jöhn Smith")
    u.run(t.example(), root / "suite", operator="Jöhn Smith")
    return root


@pytest.mark.parametrize("kind", (*t.KINDS, "suite"))
def test_real_one_page_pdf_metadata_fonts_and_immutable_results(tmp_path, captures, kind):
    source = captures / kind
    before = snapshot(source)
    out = tmp_path / "report"
    result = d.export(source, out, plots=False, portable=True)
    reader = pypdf.PdfReader(out / "report.pdf")
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "RF Output Power Test" in text and "SYNTHETIC" in text and "Jöhn Smith" in text
    assert "-0.02" in text and "µW" in text and "NOT EVALUATED" in text
    assert text.index("Equipment:") < text.index("Report Harness:") < text.index("Record:")
    assert "Bitstream Vera" in reader.metadata["/Subject"]
    fonts = reader.pages[0]["/Resources"]["/Font"].get_object().values()
    assert any(
        "/FontDescriptor" in font.get_object()
        and "/FontFile2" in font.get_object()["/FontDescriptor"]
        for font in fonts
    )
    meta = p._json((out / "metadata.json").read_bytes())
    assert meta["pdf"]["renderer_version"] == "5.1.0" and meta["pdf"]["page_count"] == 1
    bundle = p.Bundle(out)
    bundle.inventory("artifacts.json", "synthetic")
    assert "report.pdf" in bundle.entries and "font-license.txt" in bundle.entries
    manifest = d.verify(Path(str(out) + ".zip"))
    assert manifest["run_id"] == (result["suite_id"] if kind == "suite" else result["run_id"])
    assert snapshot(source) == before
    if kind == "suite":
        for child in t.KINDS:
            assert len(pypdf.PdfReader(out / "workflows" / child / "report.pdf").pages) == 1
        uris = [
            item.get_object().get("/A", {}).get("/URI")
            for item in reader.pages[0].get("/Annots", [])
        ]
        assert set(uris) == {f"workflows/{child}/report.pdf" for child in t.KINDS}
        with zipfile.ZipFile(Path(str(out) + ".zip")) as archive:
            assert "report/workflows/WF-04/provenance.json" in archive.namelist()
            assert "evidence/captures/WF-04/points/P01/stages/plateau.csv" in archive.namelist()


@pytest.mark.parametrize("kind", t.KINDS)
def test_legacy_fixture_commands_support_pdf_and_package(tmp_path, kind):
    w = s.module(kind)
    assert (
        w.main(
            [
                "synthetic",
                "--output",
                str(tmp_path / "source"),
                "--report-output",
                str(tmp_path / "report"),
                "--package",
                "--no-plots",
            ]
        )
        == 0
    )
    assert (tmp_path / "report/report.pdf").exists()
    d.verify(tmp_path / "report.zip")


@pytest.mark.parametrize("case", ["timeout", "initial-on", "empty", "criteria", "restore"])
def test_partial_failed_empty_and_criteria_reports_keep_truth(tmp_path, case):
    profile = t.example()
    kwargs = {}
    if case == "timeout":
        kwargs = dict(fault="meter-timeout", fault_workflow="WF-05")
    if case == "initial-on":
        kwargs = dict(fault="initial-on", fault_workflow="WF-04", fault_point="P01")
    if case == "empty":
        kwargs = dict(stop_before="WF-04")
    if case == "restore":
        kwargs = dict(fault="restore-failure", fault_workflow="WF-06")
    if case == "criteria":
        entry = profile["workflows"]["WF-04"]
        entry["plan"]["points"][1]["synthetic_DUT_W"] = "4.8"
        entry["criteria"] = dict(
            source="Fictional criteria",
            decision_rule="inclusive-no-guard-band",
            max_abs_error_percent="1",
            min_samples_per_point=30,
            max_gap_s="1",
        )
    source = tmp_path / "source"
    out = tmp_path / "report"
    result = u.run(profile, source, report_output=out, package=True, plots=False, **kwargs)
    assert result["acceptance"] != "PASS"
    text = pypdf.PdfReader(out / "report.pdf").pages[0].extract_text()
    if case in ("empty", "initial-on"):
        assert "Not captured" in text
    if case == "criteria":
        assert "FAIL" in text
    assert len(pypdf.PdfReader(out / "report.pdf").pages) == 1
    d.verify(tmp_path / "report.zip")


def test_pdf_and_zip_bytes_reproducible_for_same_saved_run(tmp_path, captures):
    source = captures / "suite"
    u.publish(source, tmp_path / "one", pdf=True, plots=False)
    u.publish(source, tmp_path / "two", pdf=True, plots=False)
    assert (tmp_path / "one/report.pdf").read_bytes() == (tmp_path / "two/report.pdf").read_bytes()
    # Same report folder, different archive names: deterministic entry metadata.
    one = d.package(source, tmp_path / "one", tmp_path / "a.zip")
    two = d.package(source, tmp_path / "one", tmp_path / "b.zip")
    assert one.read_bytes() == two.read_bytes()


def test_package_relocates_extracts_and_reimports_offline(tmp_path, captures):
    source = captures / "suite"
    d.export(source, tmp_path / "report", portable=True, plots=False)
    moved = tmp_path / "moved"
    with zipfile.ZipFile(tmp_path / "report.zip") as archive:
        archive.extractall(moved)
    cap, _, _ = u.load(moved / "evidence")
    assert cap["completed_workflows"] == 3
    # Relocated report/evidence pairs still qualify; the original path is irrelevant.
    d.package(moved / "evidence", moved / "report", tmp_path / "repacked.zip")
    assert (moved / "report/report.pdf").is_file()
    for item in cap["children"]:
        w = s.module(item["workflow"])
        native, _, bundle = w.load(moved / "evidence" / item["path"])
        prov = p._json(
            (moved / "report/workflows" / item["workflow"] / "provenance.json").read_bytes()
        )
        p.verify(prov, moved / "evidence" / item["path"])


@pytest.mark.parametrize(
    "case",
    ["bytes", "hash", "missing", "extra", "traversal", "duplicate", "symlink", "case-collision"],
)
def test_archive_tampering_and_unsafe_members_rejected(tmp_path, captures, case):
    d.export(captures / "WF-04", tmp_path / "report", portable=True, plots=False)
    original = tmp_path / "report.zip"
    with zipfile.ZipFile(original) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    target = tmp_path / "tampered.zip"
    with zipfile.ZipFile(target, "w") as archive:
        for info, data in entries:
            if case == "missing" and info.filename == "report/report.pdf":
                continue
            if case == "bytes" and info.filename == "report/report.pdf":
                data += b"changed"
            if case == "hash" and info.filename == "package-manifest.json":
                obj = p._json(data)
                obj["artifacts"]["report/report.pdf"]["sha256"] = "0" * 64
                data = r.encoded(obj)
            if case == "symlink" and info.filename == "report/report.pdf":
                info.external_attr = 0o120777 << 16
            archive.writestr(info, data)
        if case == "extra":
            d._zip_entry(archive, "report/hidden.txt", b"extra")
        if case == "traversal":
            d._zip_entry(archive, "../escape.txt", b"bad")
        if case == "duplicate":
            with pytest.warns(UserWarning):
                d._zip_entry(archive, "report/report.pdf", b"bad")
        if case == "case-collision":
            d._zip_entry(archive, "report/REPORT.pdf", b"bad")
    with pytest.raises((ValueError, KeyError, TypeError, zipfile.BadZipFile)):
        d.verify(target)


def test_inventory_report_pair_and_hidden_files_checked_before_zip(tmp_path, captures):
    source = captures / "WF-04"
    s.module("WF-04").publish(source, tmp_path / "report", pdf=True, plots=False)
    before = snapshot(source)
    with pytest.raises(ValueError):
        d.package(captures / "WF-05", tmp_path / "report", tmp_path / "wrong.zip")
    (tmp_path / "report/hidden.txt").write_text("not inventoried")
    with pytest.raises(ValueError, match="Uninventoried"):
        d.package(source, tmp_path / "report", tmp_path / "hidden.zip")
    assert not (tmp_path / "wrong.zip").exists() and not (tmp_path / "hidden.zip").exists()
    assert snapshot(source) == before


def test_report_resealed_wrong_results_refused(tmp_path, captures):
    source = captures / "WF-04"
    out = tmp_path / "report"
    d.export(source, out, plots=False)
    result = p._json((out / "results.json").read_bytes())
    result["acceptance"] = "PASS"
    (out / "results.json").write_bytes(r.encoded(result))
    inv = p._json((out / "artifacts.json").read_bytes())
    (out / "artifacts.json").unlink()
    _seal(out, {key: value for key, value in inv.items() if key != "artifacts"})
    with pytest.raises(ValueError, match="results differ"):
        d.package(source, out, tmp_path / "bad.zip")
    assert not (tmp_path / "bad.zip").exists()


def test_package_no_overwrite_nested_symlink_and_preflight(tmp_path, captures):
    source = captures / "WF-04"
    out = tmp_path / "report"
    d.export(source, out, portable=True, plots=False)
    data = (tmp_path / "report.zip").read_bytes()
    with pytest.raises(ValueError):
        d.package(source, out)
    assert (tmp_path / "report.zip").read_bytes() == data
    with pytest.raises(ValueError):
        d.package(source, out, source / "bad.zip")
    link = tmp_path / "alias"
    link.symlink_to(source, target_is_directory=True)
    with pytest.raises(ValueError):
        d.package(source, out, link / "bad.zip")
    (tmp_path / "future.zip").write_bytes(b"existing")
    with pytest.raises(ValueError):
        u.run(
            t.example(),
            tmp_path / "new-source",
            report_output=tmp_path / "future",
            package=True,
            plots=False,
        )
    assert not (tmp_path / "new-source").exists()


def test_pdf_failure_preserves_capture_and_has_no_sealed_report(tmp_path, captures, monkeypatch):
    source = captures / "WF-04"
    before = snapshot(source)

    def fail(*args, **kwargs):
        raise OSError("Fake PDF storage failure")

    monkeypatch.setattr(pdf, "workflow", fail)
    with pytest.raises(OSError):
        d.export(source, tmp_path / "failed", plots=False)
    assert snapshot(source) == before and not (tmp_path / "failed/artifacts.json").exists()


def test_package_failure_preserves_sealed_report_and_retry_never_captures(
    tmp_path, captures, monkeypatch
):
    source = captures / "WF-04"
    before = snapshot(source)
    original = d._zip_entry

    def fail(*args, **kwargs):
        raise OSError("Fake ZIP disk error")

    monkeypatch.setattr(d, "_zip_entry", fail)
    with pytest.raises(OSError):
        d.export(source, tmp_path / "report", portable=True, plots=False)
    assert snapshot(source) == before and not (tmp_path / "report.zip").exists()
    assert not list(tmp_path.glob(".report-package-*"))
    p.Bundle(tmp_path / "report").inventory("artifacts.json", "synthetic")
    monkeypatch.setattr(d, "_zip_entry", original)

    def forbidden(*args, **kwargs):
        raise AssertionError("Package retried acquisition")

    monkeypatch.setattr(s, "run", forbidden)
    d.package(source, tmp_path / "report")
    d.verify(tmp_path / "report.zip")


def test_unsupported_font_character_is_not_silently_lost(tmp_path):
    source = tmp_path / "source"
    w = s.module("WF-04")
    w.controlled(source, operator="Example 😀")
    with pytest.raises(ValueError, match="cannot represent"):
        w.publish(source, tmp_path / "report", pdf=True, plots=False)
    assert not (tmp_path / "report/artifacts.json").exists()
    w.load(source)


def test_cli_profile_suite_and_report_only_exports(tmp_path, captures, capsys):
    profile = tmp_path / "profile.json"
    profile.write_bytes(r.encoded(t.example()))
    assert (
        t.main(
            [
                "run",
                "--profile",
                str(profile),
                "--workflow",
                "WF-04",
                "--output",
                str(tmp_path / "profile-cap"),
                "--report-output",
                str(tmp_path / "profile-rep"),
                "--package",
                "--no-plots",
            ]
        )
        == 0
    )
    assert (
        u.main(
            [
                "run",
                "--profile",
                str(profile),
                "--workflows",
                "WF-05",
                "--output",
                str(tmp_path / "suite-cap"),
                "--report-output",
                str(tmp_path / "suite-rep"),
                "--pdf",
                "--no-plots",
            ]
        )
        == 0
    )
    assert (tmp_path / "suite-rep/report.pdf").exists() and not (
        tmp_path / "suite-rep.zip"
    ).exists()
    assert (
        d.main(
            [
                "export",
                "--bundle",
                str(captures / "WF-06"),
                "--output",
                str(tmp_path / "export"),
                "--package",
                "--no-plots",
            ]
        )
        == 0
    )
    assert d.main(["verify", "--package", str(tmp_path / "export.zip")]) == 0
    assert (
        d.main(
            [
                "package",
                "--bundle",
                str(captures / "WF-06"),
                "--report",
                str(tmp_path / "export"),
                "--output",
                str(tmp_path / "extra.zip"),
            ]
        )
        == 0
    )
    assert d.main(["verify", "--package", str(tmp_path / "missing.zip")]) == 2
    assert "report.pdf" in capsys.readouterr().out


def test_optional_plot_pdf_uses_generated_local_assets(tmp_path, captures):
    pytest.importorskip("matplotlib")
    d.export(captures / "suite", tmp_path / "report", portable=True, plots=True)
    for kind in t.KINDS:
        page = pypdf.PdfReader(tmp_path / "report/workflows" / kind / "report.pdf").pages[0]
        assert "/XObject" in page["/Resources"]
    d.verify(tmp_path / "report.zip")
    d.export((captures / "suite"), tmp_path / "again", plots=True)
    for kind in t.KINDS:
        assert (tmp_path / "report/workflows" / kind / "report.pdf").read_bytes() == (
            tmp_path / "again/workflows" / kind / "report.pdf"
        ).read_bytes()


def test_concurrent_report_change_prevents_zip_publication(tmp_path, captures, monkeypatch):
    source = captures / "WF-04"
    out = tmp_path / "report"
    d.export(source, out, plots=False)
    original = d.verify

    def change_after_copy(path):
        result = original(path)
        (out / "report.md").write_text(
            (out / "report.md").read_text() + "\nChanged during packaging\n"
        )
        inventory = p._json((out / "artifacts.json").read_bytes())
        (out / "artifacts.json").unlink()
        _seal(out, {key: value for key, value in inventory.items() if key != "artifacts"})
        return result

    monkeypatch.setattr(d, "verify", change_after_copy)
    with pytest.raises(ValueError, match="changed during packaging"):
        d.package(source, out, tmp_path / "not-published.zip")
    assert not (tmp_path / "not-published.zip").exists()
    assert not list(tmp_path.glob(".report-package-*"))
