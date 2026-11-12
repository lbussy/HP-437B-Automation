"""Human-facing RF result sheets, using independent fictional transmitter data."""

import copy
import re

import pytest

from hp437b import report_sheet as s


def fact(value):
    return {"value": value}


@pytest.fixture
def example():
    record = {
        "run": {
            "facts": {
                "started_utc": fact("2026-11-12T08:00:00-06:00"),
                "finished_utc": fact("2026-11-12T08:05:00-06:00"),
            }
        },
        "dut": {
            "kind": "radio_transmitter",
            "facts": {
                "name": fact("Example transmitter"),
                "serial": fact("DEMO-001"),
                "declared_signal": fact({"nominal_frequency_Hz": 14097100}),
                "measurement_criteria": fact(None),
            },
        },
        "equipment": [
            {
                "role": "meter",
                "facts": {
                    "reported_identifications": fact([{"model": "437B"}]),
                    "label_serial": fact("M-DEMO"),
                },
            },
            {"role": "sensor", "facts": {"label_serial": fact("S-DEMO")}},
        ],
    }
    results = {
        "run_id": "layout-example-only",
        "mode": "synthetic",
        "status": "completed",
        "stages": {
            "S40": {
                "valid": 300,
                "attempted": 300,
                "receipt_span_s": 299.0,
                "metrics": {
                    "mean_W": "2.0000",
                    "min_W": "1.9900",
                    "max_W": "2.0100",
                    "peak_to_peak_W": "0.0200",
                },
            },
            "S30": {
                "valid": 3,
                "attempted": 3,
                "receipt_span_s": 2.0,
                "metrics": {"mean_W": "2", "min_W": "2", "max_W": "2", "peak_to_peak_W": "0"},
            },
        },
    }
    return results, record


def test_reader_gets_subject_time_rf_result_and_acceptance(example):
    results, record = example
    before = copy.deepcopy(example)
    model = s.build(results, record)
    assert model["title"] == "RF Output Power Test"
    assert model["subject"] == "Example transmitter" and model["subject_id"] == "DEMO-001"
    assert model["when"] == "12 Nov 2026, 14:00:00 - 14:05:00 UTC"
    assert model["frequency"] == "14.0971 MHz (declared)"
    values = dict(model["rows"])
    assert values["Average RF power"] == "2 W"
    assert values["Power in dBm"] == "33.0103 dBm"
    assert values["Observed range"] == "1.99 - 2.01 W"
    assert "NOT EVALUATED" in model["acceptance"]
    assert example == before


def test_reference_source_never_relabelled_as_transmitter(example):
    results, record = example
    record["dut"]["kind"] = "reference_signal"
    assert "POWER REF" in s.build(results, record)["subject"]
    assert "Example transmitter" not in s.build(results, record)["subject"]


def test_main_sheet_is_brief_and_technical_payload_is_linked(example):
    md, page = s.render(*example, plots=True)
    text = re.sub(r"<[^>]+>", " ", page.split("<body>")[1])
    assert len(text.split()) < 400
    assert "Technical appendix and full traceability" in page
    assert "evidence.html" in page and "evidence.md" in md
    assert "power-trend.png" in page and "power.png" not in page
    assert "<details" not in page and "evidence_id" not in page and "JSON" not in page
    assert "SYNTHETIC" in page and "no physical transmitter was measured" in page


def test_missing_signal_does_not_display_zero_output(example):
    results, record = example
    results["status"] = "failed"
    results["stages"] = {"S40": {"capture": "absent"}, "S30": {"capture": "absent"}}
    model = s.build(results, record)
    assert model["execution"] == "FAILED"
    assert "no RF power readings were captured" in model["notes"][0]
    assert dict(model["rows"])["Average RF power"] == "Not measured"
    _, page = s.render(results, record, plots=True)
    assert "power-trend.png" not in page and "No RF power readings captured" in page


def test_partial_capture_and_shutdown_failure_remain_failures(example):
    results, record = example
    results["status"] = "failed"
    model = s.build(results, record)
    assert model["execution"] == "FAILED" and "partial results" in model["notes"][0]
    assert model["capture"] == "Sustained measurement"
    results["stages"]["S40"]["outcome"] = "failed"
    assert s.build(results, record)["capture"] == "Partial sustained measurement"
    results["stages"]["S40"] = {"capture": "absent"}
    model = s.build(results, record)
    assert model["capture"] == "Short capture only"
    assert any("Short-capture" in note for note in model["notes"])


def test_zero_and_negative_readings_are_never_converted_to_dbm(example):
    results, record = example
    for value in ("0", "-0.000001"):
        results["stages"]["S40"]["metrics"]["mean_W"] = value
        model = s.build(results, record)
        assert dict(model["rows"])["Power in dBm"] == "Not available"
        assert "Not measured" not in dict(model["rows"])["Average RF power"]


def test_supplied_names_and_issues_render_as_literal_text(example):
    results, record = example
    record["dut"]["facts"]["name"] = fact("<script>operator note</script>")
    record["run"]["facts"]["known_equipment_issues"] = fact(
        ["<img src=x onerror=alert(1)>" + " long note" * 100]
    )
    _, page = s.render(results, record, plots=False)
    assert "<script>" not in page and "<img src=x" not in page
    assert "&lt;script&gt;" in page and "(see appendix)" in page
    assert len(s.build(results, record)["notes"][0]) < 280


def test_time_without_timezone_does_not_assume_the_host_timezone(example):
    results, record = example
    record["run"]["facts"]["started_utc"] = fact("2026-11-12T08:00:00")
    assert s.build(results, record)["when"] == "Not recorded"


def test_markdown_does_not_turn_supplied_notes_into_links(example):
    results, record = example
    record["dut"]["facts"]["name"] = fact("![remote](https://example.invalid/image)")
    record["run"]["facts"]["known_equipment_issues"] = fact(["[open](https://example.invalid)"])
    md, _ = s.render(results, record, plots=False)
    assert "![remote]" not in md and "[open]" not in md
    assert "&#91;open&#93;" in md


def test_frequency_is_shown_as_readable_mhz_instead_of_scientific_notation(example):
    results, record = example
    record["dut"]["facts"]["declared_signal"] = fact({"nominal_frequency_Hz": 50000000})
    assert s.build(results, record)["frequency"] == "50 MHz (declared)"


@pytest.mark.parametrize(
    "mean,valid,expected",
    [
        ("-0.00000001", 3, "-0.01 µW (mean of 3 readings)"),
        ("0", 3, "0 µW (mean of 3 readings)"),
        (None, 0, "Not captured"),
    ],
)
def test_rf_off_zero_is_measured_before_rf_and_never_invented(example, mean, valid, expected):
    results, record = example
    results["stages"]["S10"] = {"valid": valid, "metrics": {"mean_W": mean}}
    model = s.build(results, record)
    assert model["rows"][0] == ('RF-off baseline ("zero")', expected)
    assert dict(model["rows"])["Average RF power"] == "2 W"
    assert results["stages"]["S10"]["metrics"]["mean_W"] == mean


def test_operator_in_header_physical_label_removed_and_synthetic_warning_preserved(example):
    results, record = example
    results["mode"] = "physical"
    md, page = s.render(results, record, plots=False, operator="A. O'Neil <operator>")
    assert "<th scope='row'>Operator</th><td>A. O&#x27;Neil &lt;operator&gt;</td>" in page
    assert "PHYSICAL - recorded test" not in page and "PHYSICAL - recorded test" not in md
    results["mode"] = "synthetic"
    _, synthetic = s.render(results, record, plots=False)
    assert "SYNTHETIC - simulated readings" in synthetic
    assert "Operator</th><td>Not recorded" in synthetic


def test_harness_line_precedes_record_and_release_hides_only_display_commit(example):
    producer = {"version": "0.1.0", "commit": "c" * 40, "dirty": False, "release_version": "1.2.3"}
    md, page = s.render(*example, plots=False, producer=producer)
    assert page.index("Report Harness:") < page.index("Record:")
    assert md.index("Report Harness:") < md.index("Record:")
    assert "HP 437B Automation v1.2.3" in page and "cccccccccccc" not in page
    assert producer["commit"] == "c" * 40
