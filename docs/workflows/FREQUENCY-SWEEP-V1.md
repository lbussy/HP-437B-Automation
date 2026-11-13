# WF-05: Output power versus frequency, v1

The additive [shared DUT-CTRL-01 fake-control path](CONTROLLED-SWEEPS-V1.md) executes these point plans through guarded controls and the production logger with a fake meter. Use `controlled` for that path; `synthetic` retains the original fixture generator. Physical drivers remain open.

Status: synthetic implementation, November 12, 2026. Physical transmitter tuning, correction selection/readback, and RF shutdown remain **DUT-CTRL-01**. Production logging, meter/transport commands, existing workflows, dependencies, and CLI defaults are unchanged.

This human-started workflow compares output across explicit frequency points while the declared transmitter power setting/mode stays fixed. It produces a one-page **RF Output Power Test**, plots, deterministic results, a technical appendix, and PROV-01 provenance. It neither measures frequency accuracy nor establishes spectral purity, modulation-channel flatness, or continuous all-band performance.

## Run and report

Use an isolated environment with the optional `reports` extra. Every output directory must be new. No hardware is opened; the existing offline guard adds an accident barrier:

```bash
python tools/offline_qa.py --seconds 120 -- python -m hp437b.frequency_sweep synthetic \
  --scenario band-droop --operator 'Bench operator' \
  --output output/reports/wf05-band-droop \
  --report-output output/reports/wf05-band-droop-report
```

Open `report.html`. Use `--no-plots` without Matplotlib, or omit `--report-output` for capture only. Re-report sealed evidence without repeating capture:

```bash
python tools/offline_qa.py -- python -m hp437b.frequency_sweep report \
  --bundle output/reports/wf05-band-droop \
  --output output/reports/wf05-band-droop-report-again --no-plots
```

Exit codes: synthetic capture 0 completed, 1 failed/interrupted, and 2 invalid configuration/publication failure. Offline report publication may succeed for a failed run; the report retains the failed execution and cannot assign overall PASS. A publication failure preserves the capture and never causes reacquisition or RF commands.

## Exact-point plan

`--plan PLAN.json` accepts this exact structure with 1–5 ordered points:

```json
{
  "schema": "hp437b.frequency-sweep-plan.v1",
  "name": "Fictional transmitter",
  "power_setting": "Nominal output (fixed)",
  "signal_mode": "Continuous carrier (synthetic)",
  "measurement_plane": "DUT_output",
  "fixture_description": "Fictional frequency-dependent fixture; no physical RF",
  "points": [
    {
      "point_id": "P01",
      "frequency_Hz": 1800000,
      "target_W": "5",
      "synthetic_DUT_W": "5",
      "simulation_loss_dB": "30",
      "simulation_sensor_factor_percent": "98",
      "fixture_loss_dB": "30",
      "fixture_source": "Fictional fixture table r1; exact point",
      "sensor_factor_percent": "98",
      "factor_source": "Fictional sensor table r1; exact point",
      "factor_applied_in": "analysis"
    }
  ]
}
```

Point IDs must be P01 onward in requested order. Repeated frequencies retain distinct IDs/history and are not sorted away. `frequency_Hz` must be an explicitly supplied integer within 100 kHz–4.2 GHz; unknown/out-of-range frequencies are rejected before allocation. No interpolation, nearest-band lookup, extrapolation, or automatic calibration-table upload is implemented.

Targets are watts at `measurement_plane` (`DUT_output` or `sensor_input`). A target may be null. A missing supplied sensor factor or fixture loss must have its corresponding source null; known corrections require an explicit source/revision description. Custom plans require scenario `nominal`, meaning no injected fault, not a claim that output is flat.

Default frequencies are 1.8/3.5/7/14/28 MHz, fixed nominal setting, 5 W targets, unity sensor factors, and fictional 30 dB loss. The band-droop scenario models 4.8/5.0/5.1/4.9/4.7 W. Unequal-correction cases use 98/97/96/95/94% factors and alternating 30/40 dB loss. All identities and correction tables are fictional; no actual sensor label/certificate is imported.

Finite profile: three signed source-off samples before/after, then 20 virtual settling samples and 30 plateau samples per point at one-second virtual receipts. Five complete points yield 256 samples, including 150 plateau samples, below the 900-second ceiling. Model bounds: source power zero or 1e−20–10,000 W; losses 0–100 dB; factors 1–150%; true sensor input/response and recorded indications at most 0.1 W; nonzero recorded indications at least 1e−30 W. These are **numerical model bounds, not meter programming specifications, damage limits, or fixture ratings**. Only corrected sensor means in the nominal 1 µW–100 mW measurement range are eligible for comparisons.

## Sensor factor and fixture correction

The [437B operating manual](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=40), printed page 3-10, distinguishes sensor-specific CAL FAC compensation and reference calibration. This synthetic model uses an explicitly defined indication convention; it does not qualify actual CAL FAC programming or a physical sensor calibration.

- Model truth creates incident sensor power from source power and `simulation_loss_dB`, then a unity-factor indication using `simulation_sensor_factor_percent / 100`. Truth fields never replace missing supplied correction data in analysis.
- With `factor_applied_in: analysis`, the fake meter acknowledges unity factor (100%). Analysis computes `sensor_W = indicated_W × 100 / sensor_factor_percent`, once.
- With `factor_applied_in: meter`, the fake meter must acknowledge the expected supplied factor before RF. The saved indication already includes that correction, so `sensor_W = indicated_W`; analysis does not apply it again. Unknown expected factors in this mode are rejected; a mismatched readback stops before keying.
- A known fixture loss then gives `DUT_W = sensor_W × 10^(fixture_loss_dB / 10)`, once. Sensor-plane comparisons use corrected sensor watts without fixture multiplication. Missing fixture data can still support sensor-plane results; missing sensor factors leave only descriptive indications.

The CF column marks **A** for analysis and **M** for meter. The appendix retains exact factors, sources, location, readbacks, and both indicated/corrected readings. No existing meter factor, offset, REF CF, or sensor table is changed. Baseline is a signed indication, not an automatic zero or subtraction.

## Source sequence and failures

Synthetic actor: acknowledged off → baseline → while unkeyed, tune/acknowledge requested frequency with fixed setting/mode → acknowledge meter factor → key/settle/plateau → one off attempt/acknowledgement → next point → final baseline. Both frequency and correction acknowledgement are required before keying. Frequency acknowledgement is not independent frequency measurement. Events are virtual; there is no pending hardware transaction or real source driver.

A failure/cancellation stops progression, retaining the partial/failed point and all remaining skipped points in the requested denominator. Timeout/malformed cases model uncertain communication and make no later actor commands; final external source-off is unknown. Complete instrument-error/cancellation cases can acknowledge source-off. A source-off failure is not retried. Missing/mismatched frequency or meter-factor readback stops before that point is keyed. Meter local restoration alone cannot turn off an external transmitter.

Nineteen scenarios: nominal, band-droop, unequal-corrections, meter-corrected, repeated-anchor, missing-target, missing-loss, missing-factor, sensor-plane, zero-output, timeout, malformed, instrument-error, cancel, source-off-failure, frequency-mismatch, frequency-unverified, factor-mismatch, and missing-band.

## Analysis and acceptance

Per point: retained sample count, indicated/sensor/DUT mean and min/max where supported, maximum receipt gap, target, signed W/percent/dB errors, declared/acknowledged frequency, factors/losses, coverage reason, and acceptance. `error_percent = 100 × (measured − target) / target`; dB error needs positive measured/target powers. Zero output may have −100% error while dB error is unavailable. Partial values remain descriptive, not passing points.

Across completed positive eligible points, report observed minimum/maximum and `10 log10(max_mean / min_mean)` in dB at the declared comparison plane, plus separate DUT-plane statistics where supported. Two eligible points are required for spread. Worst observed target error retains its point ID and uses available completed-point comparisons, including descriptive zero-output cases; it is separate from positive-power eligibility for spread. DUT-plane spread retains a separate coverage count/scope when sensor-plane results have missing fixture corrections. Missing/ineligible points yield partial observed spread explicitly labeled as such; this cannot satisfy a complete requested-point criterion. A single-point result is not a band-spread result.

Without criteria, acceptance is **NOT EVALUATED**. `--criteria CRITERIA.json` supports one or both optional limits:

```json
{
  "source": "Fictional transmitter specification r1",
  "decision_rule": "inclusive-no-guard-band",
  "min_samples_per_point": 30,
  "max_gap_s": "1",
  "max_abs_error_percent": "6",
  "max_spread_dB": "0.4"
}
```

An optional `point_limits_percent` mapping overrides the shared error limit for requested point IDs. It requires `max_abs_error_percent`; unknown IDs are rejected. Limits are nonnegative and inclusive. There is no uncertainty model/guard band. Overall PASS/FAIL requires complete execution/eligible coverage and every selected criterion to be evaluable. Missing targets prevent an error criterion but do not prevent a spread-only criterion. Incomplete requested coverage, unknown necessary corrections, nonpositive power, or insufficient timing coverage cannot pass the complete sweep criterion. No result is extrapolated between points or beyond the supplied frequencies.

Catalogue oracle: corrected means 4.8/5.0/5.1/4.9/4.7 W, errors −4/0/+2/−2/−6%, spread `10 log10(5.1/4.7) ≈ 0.354723182 dB`, worst target error P05. Default acceptance remains NOT EVALUATED. Explicit fictional 6%/0.4 dB limits pass; 0.3 dB spread or a stricter P05 bound fails.

## Evidence, publication, and boundary

Capture: `starting.json`, finalized `workflow.json`, WF-05 virtual `samples.csv`, `trace.json`, and final atomic `artifacts.json`. This is not the production logger CSV or a native backend test. Import verifies hashes, schemas/mode/run joins, point/phase counts/order, W values, timing, exact frequency/factor acknowledgements, fixed setting/mode trace, stop progression, final source state, and correction provenance. Hashes detect changes; they do not authenticate measurements.

Publication: single-page `report.html`/`report.md`, optional PNG/SVG, `results.json`, reusable `provenance.json`, full producer commit/source metadata in `metadata.json`, complete `appendix.html`, and final report inventory. The sheet includes operator, fixed setting/mode, signed pre-RF zero, declared frequencies, per-point factors/losses/results, coverage/spread/worst point, acceptance, and final synthetic source state. Footer order is Equipment → Report Harness → Record; semantic tags/development commits follow the existing harness policy. Failures retain evidence without reacquisition; source captures remain unchanged during reimports.

Tests cover all scenarios, independent arithmetic, correction placement/no double application, no simulator-truth substitution, missing data and repeated anchors, criteria/coverage, invalid configuration before output, storage failure, hash/semantic corruption, CLI/path protection, provenance, and optional plots. Local campaign evidence is ignored under `output/reports/wf05-synthetic-20261112/`; totals are in [VALIDATION](../VALIDATION.md). Delivered to `devel` at `64ea656`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43319936286).

Physical integration still needs **DUT-CTRL-01**: rated RF path, source tuning/control, actual factor selection/readback, safe shutdown, and applicable uncertainty/criteria records. POWER REF supplies only a fixed nominal 50 MHz point; changing its label, meter units, or factor cannot create a frequency sweep. Replacement equipment does not block this synthetic milestone.
