# WF-06: Supply-voltage sensitivity, v1

Status: synthetic implementation, November 12, 2026. Physical transmitter/supply control, voltage observation, and restoration remain **DUT-CTRL-01**. Normal logging, meter/transport commands, existing workflows, dependencies, and CLI defaults are unchanged.

This human-started workflow compares RF output at explicit supply voltages while declared RF frequency, power setting, and signal mode remain fixed. It produces a one-page **RF Output Power Test**, deterministic results, plots, a technical appendix, and reusable PROV-01 provenance. No real supply, voltage observer, transmitter, meter, or AI provider is accessed.

## Run and report

Use an isolated environment with the optional `reports` extra and new output directories. The existing offline guard adds an accident barrier:

```bash
python tools/offline_qa.py --seconds 120 -- python -m hp437b.supply_sensitivity synthetic \
  --scenario droop --operator 'Bench operator' \
  --output output/reports/wf06-droop \
  --report-output output/reports/wf06-droop-report
```

Open `report.html`. `--no-plots` supports an installation without Matplotlib; omitting `--report-output` captures only. Re-report sealed evidence without reacquisition:

```bash
python tools/offline_qa.py -- python -m hp437b.supply_sensitivity report \
  --bundle output/reports/wf06-droop \
  --output output/reports/wf06-droop-report-again --no-plots
```

Exit codes: synthetic capture 0 completed, 1 failed/interrupted, and 2 invalid configuration/publication error. Offline reporting can publish a failed capture successfully; execution and restoration failures remain in the report. Publication failure never retries capture or contacts equipment.

## Declared plan and model bounds

`--plan PLAN.json` accepts this exact structure with 1–5 ordered points:

```json
{
  "schema": "hp437b.supply-sensitivity-plan.v1",
  "name": "Fictional transmitter",
  "frequency_Hz": 14000000,
  "power_setting": "Nominal output (fixed)",
  "signal_mode": "Continuous carrier (synthetic)",
  "measurement_plane": "DUT_output",
  "fixture_description": "Fictional fixed fixture; no physical RF",
  "fixture_loss_dB": "30",
  "fixture_source": "Fictional fixture table r1; fixed frequency",
  "simulation_loss_dB": "30",
  "supply": {
    "minimum_V": "10",
    "maximum_V": "14",
    "current_limit_A": "2",
    "restore_V": "12",
    "nominal_V": "12",
    "nominal_point_id": "P02",
    "tolerance_V": "0.1",
    "observation_location": "DUT supply terminals (synthetic)"
  },
  "points": [
    {"point_id": "P01", "requested_V": "11", "synthetic_observed_V": "11", "synthetic_DUT_W": "4.5"},
    {"point_id": "P02", "requested_V": "12", "synthetic_observed_V": "12", "synthetic_DUT_W": "5"},
    {"point_id": "P03", "requested_V": "13", "synthetic_observed_V": "13", "synthetic_DUT_W": "5.2"}
  ]
}
```

Point IDs must be P01 onward in requested order. Repeated voltages retain distinct IDs/history. `nominal_point_id` is explicit or null; a declared nominal point must request `nominal_V`. Neither an observed 12 V value, a restoration target, the first row, nor a nearest voltage implicitly becomes the nominal reference.

Requests, nominal voltage, and restoration target must be inside the supplied envelope before output allocation or any virtual actor event. Fixed frequency is an integer within the synthetic 8482A profile, 100 kHz–4.2 GHz. Numerical bounds: envelope 0.1–100 V, current-limit setting 0.01–100 A, readback tolerance 0–1 V, fixture/model loss 0–100 dB, source power zero or 1e−20–10,000 W, and nonzero synthetic sensor input 1e−30–0.1 W. These are **software/model bounds, not actual DUT ratings, fixture ratings, damage limits, or permission to apply voltage/RF**. The default 10–14 V envelope and 2 A setting are fictional. A current-limit acknowledgement is not a current measurement or evidence of actual current compliance.

Targets/limits are decimal strings; values must be finite. `measurement_plane` is `DUT_output` or `sensor_input`. Fixture loss/source may both be null, leaving corrected DUT power unavailable while sensor-plane observations remain possible. Sensor calibration is assumed already represented in the indicated sensor watts; this workflow does not program or reapply a sensor factor. Supplied fixed fixture loss is applied once: `DUT_W = sensor_W × 10^(fixture_loss_dB / 10)`.

`synthetic_DUT_W`, `synthetic_observed_V`, and `simulation_loss_dB` drive the fake capture, not analysis. Analysis uses saved voltage readbacks and RF samples, never substitutes model truth for missing observations/corrections, and never infers a universal voltage-to-power function. Custom plans require scenario `nominal`, meaning no injected control fault, not a claim of constant output.

## Finite sequence and cleanup

Default nominal scenario: 11/12/13 V with 5 W at all points; `droop` reproduces 4.5/5/5.2 W. Sequence:

1. Acknowledge source off; capture three signed pre-RF baseline samples.
2. Acknowledge the declared current-limit setting. Mismatch stops before any voltage point is activated.
3. While source off/control healthy, command the point voltage and retain its acknowledgement/readback at the declared observation location.
4. Require a readback within both the declared envelope and request tolerance before keying RF. Missing, unsafe, or mismatched readback fails the point; it does not become an observed-voltage RF result.
5. Acknowledge RF on, capture 20 virtual settling and 30 plateau samples, then make one source-off attempt/acknowledgement.
6. Stop after any failure/cancellation; retain partial/failed/skipped points. With healthy control and known RF off, attempt the **distinct, predeclared restoration action once**, then verify its readback. This is not a measurement retry.
7. Capture three final baseline samples only after completed points and verified restoration.

Three complete points produce 156 samples, including 90 plateau samples; five points produce 256 samples. Receipts advance at virtual one-second intervals within a 900-second ceiling. Acknowledgements are instantaneous virtual events, not measured hardware/backend latency. Baseline is signed and descriptive; no automatic meter zero or subtraction occurs.

This version requires voltage observation before RF. Missing readback therefore stops acquisition at that point; it does not silently publish commanded-voltage power as observed-voltage sensitivity. A future explicitly labeled commanded-only profile would need separate implementation/acceptance.

Timeout/malformed cases model uncertain communication and issue no subsequent actor commands. Failed source-off also prohibits changing/restoring supply voltage while RF state is unknown. Supply write failure or untrusted current-limit setup leaves restoration unknown, with no retry. Complete instrument-error/cancellation cases can acknowledge RF off and then perform the declared restoration. Restoration write failure, wrong readback, or missing readback fails the run even if every RF point completed. A failed restoration is never retried automatically.

These are synthetic state-machine assertions, not acceptance of an actual supply shutdown or hardware recovery path. Meter local return cannot establish external RF-off or restored supply state.

## Calculations and acceptance

For each point, retain requested/observed voltage and error, valid RF count, sensor/DUT mean/min/max, maximum receipt gap, nominal-relative W/percent change, coverage reason, and acceptance. Only completed points with supported observed voltage, positive measured power, and sensor mean within the nominal 1 µW–100 mW measurement range are eligible for comparisons. Unknown corrections, partial reads, and skipped points remain explicit.

`change_W = measured_W − nominal_mean_W`; `change_percent = 100 × change_W / nominal_mean_W` requires an eligible positive declared nominal reference. A missing/incomplete/nonpositive nominal point leaves percentages unavailable with reasons. It never becomes a zero denominator or silently selects another point.

Endpoint secant is `(power_at_upper_observed_V − power_at_lower_observed_V) / (upper_observed_V − lower_observed_V)`. Two distinct eligible observed voltages are required. Endpoints are the lowest/highest observed voltage among available eligible points, with the **first captured point on ties**; endpoint IDs are retained. Later repeated anchors remain separate rather than changing endpoint selection or hiding history. Partial endpoint results are labeled as available-point observations and cannot pass a complete-run criterion. This is neither a fitted universal regulator slope nor DC-to-RF efficiency; no DC current/input power is measured.

RF point coverage and overall run completion are separate. A failed restoration can leave 3/3 RF points complete and a descriptive secant available, while overall execution is failed and acceptance remains NOT EVALUATED.

Without supplied criteria, acceptance is **NOT EVALUATED**. Optional `--criteria CRITERIA.json`:

```json
{
  "source": "Fictional transmitter specification r1",
  "decision_rule": "inclusive-no-guard-band",
  "min_samples_per_point": 30,
  "max_gap_s": "1",
  "max_abs_change_percent": "10",
  "max_abs_secant_W_per_V": "0.35"
}
```

One or both limits are required when criteria are supplied. Optional `point_limits_percent` overrides the shared change limit for requested IDs; it requires `max_abs_change_percent`. Limits are nonnegative and inclusive. Overall PASS/FAIL requires complete eligible requested coverage, completed execution, known RF off, verified restoration, and all selected criteria evaluable. A secant-only criterion can evaluate without a nominal point; change criteria cannot. Repeated equal voltages have no secant, so they cannot pass a secant criterion. There is no uncertainty model or guard band, and no extrapolation to untested voltages.

Catalogue oracle: observed 11/12/13 V, corrected 4.5/5/5.2 W, relative changes −10/0/+4%, endpoint secant 0.35 W/V. Explicit fictional 10%/0.35 W/V limits pass inclusively; stricter limits fail. With observed offsets 10.98/12.02/13.01 V, the same RF vector gives `0.7 / 2.03 ≈ 0.344827586 W/V`, not the requested-voltage secant.

## Evidence, scenarios, and completion boundary

Capture: `starting.json`, finalized `workflow.json`, virtual `samples.csv`, `trace.json`, and final atomic `artifacts.json`. Import verifies hashes, schema/mode/run joins, phase/order/count/time, finite W/V values, current-limit setup, voltage-command/readback/source progression, nominal designation, restoration actions/readbacks, final state, and absence of retries/post-fault commands. The CSV is virtual WF-06 evidence, not the production logger CSV. Hashes detect change; they do not authenticate measurements or establish calibration.

Publication: one-page `report.html`/`report.md`, optional PNG/SVG, deterministic `results.json`, reusable `provenance.json`, producer `metadata.json` with full commit/source hashes, complete `appendix.html`, and final report inventory. The main sheet includes transmitter/operator/time, fixed RF conditions, measurement plane, fictional supply envelope/current-limit setting, pre-RF zero, nominal reference, requested/observed/output/change table, endpoint secant, acceptance, RF-off, and restoration outcome. Footer order is Equipment → Report Harness → Record, retaining existing tag-aware harness identity. Source captures remain unchanged during reimports, and publication failure never reacquires samples.

Twenty-two scenarios: nominal, droop, observed-offset, repeated-anchor, missing-nominal, missing-readback, unsafe-readback, same-voltage, missing-loss, sensor-plane, zero-nominal, timeout, malformed, instrument-error, cancel, missing-point, source-off-failure, supply-control-failure, current-limit-mismatch, restore-failure, restore-mismatch, and restore-unverified. Invalid/unsafe requests are rejected separately before allocation/activation. Tests also cover independent arithmetic, inclusive/point-specific criteria, truth isolation, corruption, storage failure, path protection, CLI behavior, provenance, and optional plots.

Local campaign evidence is ignored under `output/reports/wf06-synthetic-20261112/`; totals and package/report checks are in [VALIDATION](../VALIDATION.md). Delivered to `devel` at `c7f15d0`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43330393273).

Physical work requires **DUT-CTRL-01**: a suitable DUT and controlled supply, rated RF path, documented operating limits/current-limit policy, actual voltage-observer identity/location/calibration, source-off behavior, restoration verification, and independent safe shutdown. This is not an experiment on the 437B supply or POWER REF. POWER REF cannot provide a transmitter supply-voltage sweep, and changing meter correction/units cannot create one. Equipment exchange remains a separate follow-up, not a synthetic software gate.
