# POWER REF measurement report: synthetic worked example

**SYNTHETIC DESIGN EXAMPLE — no instrument, radio, reference output, or workflow runner was operated.** This report illustrates [workflow definition v1](../POWER-REFERENCE-V1.md), using a [fictional machine-readable fixture](power-reference-v1-synthetic.json). Its S40 stage is shortened to six count-bounded samples; this is not a five-minute acquisition. The arithmetic is calculated from the fixture, while control/state outcomes are declared examples. This remains a hand-worked design example; the later [synthetic prototype exercise](../WF-01-EXERCISE.md) produces executed bundles separately. The physical runner and full report product remain to be implemented.

## Identity and outcomes

| Field | Value |
| --- | --- |
| Workflow / run | `power-reference-v1` / `synthetic-wf01-example-001` |
| Purpose | Demonstrate a finite source-off/on/off measurement sequence and its resulting data analysis/report |
| Actual execution | Not run; the fixture illustrates a completed sequence |
| Fixture data integrity | Fifteen rows, sequential per-stage numbering, matching session IDs, W units, finite values, and raw/parsed correspondence checked |
| Measurement criteria | Not evaluated: no accuracy/stability/compliance limits supplied |
| Reference/local final state | Off/local in the fixture; no actual state observed |
| Narrative | Illustrative deterministic summary; no external agent/model used |

## Configuration and provenance

Equipment identities are fictional: `SYNTHETIC-437B-001`, `SYNTHETIC-8482A-001`, and `SYNTHETIC-USBGPIB-001`. There is no physical calibration record, zero/CAL event, measured frequency, or hardware setup in this example. Those fields must remain explicit in a physical report; the actual meter's documented issue belongs in reports using that meter.

Declared source: POWER REF-like fixture, nominal 50 MHz and 0.001 W. Requested receipt interval: 1 s; operation timeout: 10 s; source-on observation allowance: 20 s of example/virtual time. The fixture specifies sample values directly and applies no baseline subtraction or calibration correction. A physical run would retain actual factor/settings/path provenance separately.

## Stage coverage

| Stage | Source state in fixture | Planned/valid/error rows | Receipt span | Median receipt spacing |
| --- | --- | --- | --- | --- |
| S10 baseline-before | Off | 3 / 3 / 0 | 2 s | 1 s |
| S30 short-capture | On | 3 / 3 / 0 | 2 s | 1 s |
| S40 shortened sustained-capture example | On | 6 / 6 / 0 | 5 s | 1 s |
| S60 baseline-after | Off | 3 / 3 / 0 | 2 s | 1 s |

Source-on/off, preflight, and cleanup stages are described by the workflow definition and declared fixture outcomes, not executed control transactions. Setup/control probes are excluded from these sample counts. All receipt timestamps are fixed synthetic timestamps; spacing statistics characterize the fixture, not real meter/host performance. No row or stage is silently substituted for the default 300-second stage.

## Signal results

Each stage is analyzed separately. Values below are presentation conversions from W; the fixture retains the input decimal values and raw frame hex.

| Reference-on stage | Mean | Minimum | Maximum | Peak-to-peak | Sample standard deviation |
| --- | --- | --- | --- | --- | --- |
| S30 short-capture | 0.988 mW | 0.987 mW | 0.989 mW | 0.002 mW | 0.001 mW |
| S40 six-sample example | 0.988 mW | 0.987 mW | 0.989 mW | 0.002 mW | 0.000894427 mW |

S40 relative peak-to-peak variation is **0.202429% of its mean**. Its mean differs from S30's mean by **0 W**. First-to-last S40 change is **+0.002 mW**; this endpoint difference is not a fitted drift rate.

Compared with declared nominal 1 mW, the S40 mean is **−0.012 mW (−1.2%)**. This is a nominal comparison only. No independent reference uncertainty, sensor calibration, or acceptance band is established by the fixture, so neither accuracy nor equipment pass/fail follows from that number.

| Source-off stage | Mean | Minimum | Maximum | Peak-to-peak | Sample standard deviation |
| --- | --- | --- | --- | --- | --- |
| S10 baseline-before | −0.05 µW | −0.06 µW | −0.04 µW | 0.02 µW | 0.01 µW |
| S60 baseline-after | −0.04 µW | −0.05 µW | −0.03 µW | 0.02 µW | 0.01 µW |

The source-off mean change is **+0.01 µW**. Negative baseline readings are preserved. These descriptive, below-normal-range observations are not calibrated low-power values, leakage specifications, or corrections applied to the on-stage data.

## Interpretation

The example demonstrates the intended measurement-to-report structure: separate baselines and source-on captures, actual counts/timing, numerical summaries, nominal comparison, explicit provenance, and a clear separation between execution, data integrity, and measurement criteria. The two source-on stages share a mean; variation and endpoint changes remain visible rather than disappearing into a single pooled value.

The useful next software result is an executable synthetic workflow producing the same evidence-linked analysis/report, including failed and interrupted cases. A supervised POWER REF run can later exercise the physical source path with the connected sensor. No radio or replacement meter is required to develop that pipeline.

## Evidence and calculation details

The [fixture](power-reference-v1-synthetic.json) contains fifteen explicit rows, with stage/session/sequence/time/value/unit/status/raw fields and machine-readable analysis. Example values by stage in W are:

| Stage | Values (W), in receipt order |
| --- | --- |
| S10 | −0.00000005, −0.00000004, −0.00000006 |
| S30 | 0.000988, 0.000989, 0.000987 |
| S40 | 0.000987, 0.000988, 0.000989, 0.000988, 0.000987, 0.000989 |
| S60 | −0.00000004, −0.00000005, −0.00000003 |

Mean is the sample-weighted arithmetic mean. Sample standard deviation uses n−1; S40's squared-deviation sum is `0.000000000004 W²`, divided by 5 before square root. Peak-to-peak is maximum minus minimum; relative peak-to-peak uses the absolute mean as denominator. Receipt span is last timestamp minus first within a stage. Calculations use decimal precision 34; this is computational precision, not measurement resolution. Displayed derived quantities are rounded to at most six significant digits where needed. No additional independent digits, measurement uncertainty, or time-weighted signal average is implied.

This example has no generated physical CSV/sidecars, command trace, live source-state verification, plot artifact, or executed cleanup record. A real produced report must reference its own finalized bundle and hashes rather than treating this fixture or historical bench evidence as its run output.

Fixture SHA-256: `f662163c4f3a27317645036801d7445b0a8965651f00272c9a8c92bcb3b6442b`. This identifies the design fixture bytes, not an actual measurement run.
