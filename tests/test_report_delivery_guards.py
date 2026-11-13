"""Optional delivery must never become a requirement of normal capture/logging."""

import pytest

from hp437b import controlled_sweep as s
from hp437b import pdf_reports
from hp437b import test_profiles as t
from hp437b import test_suite as u


@pytest.mark.parametrize("entry", ["WF-04", "WF-05", "WF-06", "profile", "suite"])
def test_missing_pdf_extra_stops_before_capture(tmp_path, monkeypatch, entry):
    def missing():
        raise ValueError("Install optional pdf extra")

    monkeypatch.setattr(pdf_reports, "preflight", missing)
    output = tmp_path / "capture"
    report = tmp_path / "report"
    with pytest.raises(ValueError, match="pdf extra"):
        if entry.startswith("WF-"):
            s.module(entry).controlled(output, report_output=report, pdf=True, plots=False)
        elif entry == "profile":
            t.capture(t.example(), "WF-04", output, report_output=report, package=True, plots=False)
        else:
            u.run(t.example(), output, report_output=report, pdf=True, plots=False)
    assert not output.exists() and not report.exists()


@pytest.mark.parametrize("entry", ["WF-04", "profile", "suite"])
def test_pdf_requires_report_output(tmp_path, entry):
    with pytest.raises(ValueError, match="requires report output"):
        if entry == "WF-04":
            s.module(entry).controlled(tmp_path / "capture", pdf=True)
        elif entry == "profile":
            t.capture(t.example(), "WF-04", tmp_path / "capture", package=True)
        else:
            u.run(t.example(), tmp_path / "capture", pdf=True)
    assert not (tmp_path / "capture").exists()


def test_standard_report_never_loads_optional_renderer(tmp_path, monkeypatch):
    def unexpected():
        raise AssertionError("Normal report loaded optional PDF renderer")

    monkeypatch.setattr(pdf_reports, "preflight", unexpected)
    u.run(t.example(), tmp_path / "capture", report_output=tmp_path / "report", plots=False)
    assert (tmp_path / "report/report.html").exists()
    assert not (tmp_path / "report/report.pdf").exists()
