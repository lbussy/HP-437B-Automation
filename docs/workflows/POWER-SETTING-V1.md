# WF-04: Output power versus setting, v1

The additive [shared DUT-CTRL-01 fake-control path](CONTROLLED-SWEEPS-V1.md) executes these point plans through guarded controls and the production logger with a fake meter. Use `controlled` for that path; `synthetic` retains the original fixture generator. Physical drivers remain open.

Status: synthetic implementation, November 12, 2026. Physical transmitter integration remains open under **DUT-CTRL-01**. Normal logging, transport, meter commands, existing physical workflows, dependencies, and CLI defaults are unchanged.

This human-started workflow compares recorded power with explicit targets at ordered transmitter settings. It produces a one-page **RF Output Power Test**, plots, a technical appendix, deterministic results, and reusable PROV-01 provenance. It does not qualify a transmitter or the meter from synthetic data. No model/provider, network request, instrument opening, or physical source control is involved.

## Run a demonstration

Use an isolated reporting environment with the optional `reports` extra. New output directories are required. The existing hardware-blocking guard can be used for every synthetic run:

```bash
python tools/offline_qa.py --seconds 120 -- python -m hp437b.power_setting synthetic \
  --scenario compressed --operator 'Bench operator' \
  --output output/reports/wf04-compressed \
  --report-output output/reports/wf04-compressed-report
```

Open `report.html` in the report directory. `--no-plots` supports an installation without Matplotlib. Capture without `--report-output` is also supported. Regenerate reports from saved evidence without repeating capture:

```bash
python tools/offline_qa.py -- python -m hp437b.power_setting report \
  --bundle output/reports/wf04-compressed \
  --output output/reports/wf04-compressed-report-again --no-plots
```

Synthetic CLI exit codes: 0 completed capture, 1 failed/interrupted capture, and 2 invalid configuration/publication error. A report of a failed capture can publish successfully; its execution remains failed and its overall acceptance remains NOT EVALUATED. There is no measurement retry or reacquisition after publication failure.

## Plan, bounds, and source model

The default fictional transmitter has Low/Medium/High settings, explicit DUT-plane targets of 1/5/10 W, declared 50 MHz frequency, and a fictional 30 dB fixture. At most five ordered points are allowed; repeated setting labels are permitted and retain separate point IDs/history. No percentage-to-power mapping is inferred from labels.

`--plan PLAN.json` accepts this exact structure (1–5 points):

```json
{
  "schema": "hp437b.power-setting-plan.v1",
  "name": "Fictional transmitter",
  "frequency_Hz": 50000000,
  "signal_mode": "Continuous carrier (synthetic)",
  "measurement_plane": "DUT_output",
  "fixture_description": "Fictional 30 dB fixture; no physical RF",
  "points": [
    {
      "point_id": "P01",
      "setting": "Low",
      "target_W": "1",
      "synthetic_DUT_W": "1",
      "simulation_loss_dB": "30",
      "fixture_loss_dB": "30"
    }
  ]
}
```

`measurement_plane` is `DUT_output` or `sensor_input`; targets are in watts at that declared plane. `target_W` and supplied `fixture_loss_dB` may be null. Simulator truth (`synthetic_DUT_W`, `simulation_loss_dB`) creates sensor samples; analysis never uses that truth to replace unknown supplied correction data. Custom plans require scenario `nominal`, meaning no injected fault, not an assertion of proportional output.

Bounds are explicit: declared frequency 100 kHz–4.2 GHz; synthetic DUT power 0–10,000 W; loss 0–100 dB; synthetic sensor input at most 0.1 W. These are software/model checks, **not damage limits, fixture ratings, or permission to apply RF**. Sensor means outside the nominal 1 µW–100 mW measurement range are descriptive and ineligible for acceptance. Positive targets of at least 1e−20 W are required when supplied; nonzero model powers have the same numerical floor. Text is bounded and single-line; numeric fields are finite decimal strings.

The source actor is separate from the meter reference. Sequence: acknowledged off → three signed source-off baseline samples → while unkeyed, select/acknowledge setting and declared frequency → acknowledge keying → 20 virtual settling samples → 30 virtual plateau samples → one unkey attempt/acknowledgement → next point → three final baseline samples. Virtual samples arrive at requested one-second intervals; total virtual duration is at most 256 seconds, below the 900-second ceiling. The default complete capture has 156 samples, including 90 plateau samples. Acknowledgements and timestamps are synthetic, not independently observed physical states or measured backend timing.

POWER REF remains off in this model. This standalone generator does not call `Instrument`/`collect` or exercise USB, native timeouts, meter frames, or automatic local return. Existing logger/backend acceptance stays separate. The simulator cannot become a physical runner by changing a resource string.

## Calculations and decisions

For each point, retain valid plateau count, sensor mean/min/max, maximum receipt gap, fixture-corrected DUT mean when available, target, signed W/percent/dB errors, execution, acceptance, and unavailability reasons. Settling samples and baselines are excluded from plateau means. Baseline is the signed three-sample pre-RF mean; it is neither an automatic meter zero nor a subtraction.

- `DUT_W = sensor_W × 10^(fixture_loss_dB / 10)`, applied once. Sensor calibration is assumed already represented in sensor watts; do not apply another sensor factor.
- Sensor-plane comparisons use sensor watts directly, regardless of fixture correction availability.
- `error_W = measured_W − target_W`; `error_percent = 100 × error_W / target_W`.
- `error_dB = 10 log10(measured_W / target_W)` requires positive measured and target powers. Zero output may have −100% error while dB error is unavailable.

Targets, corrections, and measurements remain separate. Missing targets/losses yield null comparisons with reasons, never invented zeros or use of simulator truth. Partial means remain visible and labeled incomplete. Skipped points remain in the requested denominator; there is no overall PASS after incomplete execution.

Without supplied criteria, acceptance is **NOT EVALUATED**. Optional `--criteria CRITERIA.json`:

```json
{
  "source": "Fictional DUT specification r1",
  "decision_rule": "inclusive-no-guard-band",
  "max_abs_error_percent": "5",
  "min_samples_per_point": 30,
  "max_gap_s": "1"
}
```

Every point must complete, have a compatible target/correction, a mean within the nominal sensor range, sufficient valid samples, and acceptable receipt gaps before an overall PASS/FAIL is evaluated. Absolute percent error at the inclusive limit passes. An optional `point_limits_percent` object maps requested IDs (for example, `{"P03": "4"}`) to per-point overrides of the shared error limit; unknown point IDs are rejected. This rule does not model measurement uncertainty or provide a guard band. Real DUT criteria, rated fixtures, uncertainties, and decision rules need separate physical integration.

## Evidence and reports

Capture: `starting.json`, finalized `workflow.json`, `samples.csv`, `trace.json`, and an atomic, final `artifacts.json` inventory. The CSV is WF-04 virtual sample evidence, not the production logger's CSV format. Unfinished captures are not reportable. Saved import verifies file hashes, run/point joins, baseline/stage order/counts, finite W values, acknowledgements, source progression, final state, and virtual duration. Hashes detect change; they do not authenticate measurements or establish equipment calibration.

Report: `report.html`, `report.md`, `results.json`, `provenance.json`, producer `metadata.json`, `appendix.html`, optional PNG/SVG, and final artifact inventory. Producer metadata retains the full commit and source hashes; Report Harness follows existing release-tag/development-commit rules. The main sheet shows transmitter, operator, capture time, declared frequency, plane, pre-RF zero, coverage, point results, and acceptance. Footer order is Equipment → Report Harness → Record. Full setup/criteria, source acknowledgements, unavailable reasons, and limitations are in the appendix. Evidence is never modified during reimport or reporting.

Failures stop progression. Timeout/malformed cases model uncertain communication and retain unknown external source-off state without later commands. Complete instrument-error/cancellation cases can acknowledge bounded source-off. A source-off failure is not retried. Meter local state cannot establish that an external transmitter is off. These are fake-control assertions, not qualifications of an actual external shutdown path.

## Validation and completion boundary

Fourteen scenarios: nominal, compressed, nonmonotonic, missing-target, missing-loss, sensor-plane, zero-output, timeout, malformed, instrument-error, cancel, source-off-failure, ack-mismatch, and missing-point. Tests cover independent catalogue arithmetic, inclusive criteria, incomplete/ineligible decisions, no correction double application or truth leakage, invalid plans before output allocation, hash and semantic corruption, source trace/point joins, path protection, report storage failure, CLI exits, provenance, and optional plots.

The compressed example reproduces the catalogue: sensor means 1.0/4.8/9.5 mW, fictional 30 dB correction, DUT-plane means 1.0/4.8/9.5 W, errors 0/−4/−5%. Default acceptance remains NOT EVALUATED. With the explicitly fictional 5% criterion, the result passes inclusively; this says nothing about actual equipment.

Synthetic captures and reports are retained locally under ignored `output/reports/wf04-synthetic-20261112-v2/`. Validation totals and sample-sheet review are recorded in [VALIDATION](../VALIDATION.md). Delivered to `devel` at `db45dbc`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43313033157).

Next physical work requires **DUT-CTRL-01**: a prepared rated RF path, DUT-specific source controls/manual acknowledgements, observed condition policy, independent shutdown behavior, and safe correction records. POWER REF can rehearse a fixed single point but cannot create the multi-level sweep. No replacement meter or radio is required to finish this synthetic software milestone.
