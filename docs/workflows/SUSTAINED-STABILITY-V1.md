# WF-02: Sustained output stability

Implemented November 12, 2026, for **synthetic capture, provenance, analysis, and deterministic reporting**. The [physical POWER REF runner](WF-02-PHYSICAL.md) is now integrated and tested with explicit fakes; the selected Mac bench run is recorded separately. Normal logging is unchanged. This implements the first priority in the [transmitter test catalogue](TRANSMITTER-TEST-CATALOG.md#wf-02-sustained-output-stability); it does not claim a transmitter measurement or hardware acceptance.

## Run a synthetic test

Use the existing isolated development/report environment with pinned dependencies and the optional `reports` extra. From the checkout:

```bash
python tools/offline_qa.py --seconds 120 -- \
  python -m hp437b.stability synthetic \
  --scenario ramp \
  --operator "Example Operator" \
  --output output/reports/new-wf02-capture \
  --report-output output/reports/new-wf02-report
```

Open `output/reports/new-wf02-report/report.html`. The new capture and report directories must be separate, non-nested, and nonexistent. The simulated thirty minutes run on a virtual clock, without a thirty-minute wall-clock wait. The synthetic command has no hardware resource argument, driver/factory injection, resource discovery, provider, model call, or synthetic-to-physical fallback. The path uses the existing `Instrument` and `collect` APIs with an explicit fake wire; it does not modify their behavior.

`--no-plots` produces text/HTML/JSON without requiring Matplotlib. `--operator` and `HP437B_OPERATOR` use the established attribution policy; a captured name takes precedence over an environment default when reporting later. A supplied override is separately attributed in report metadata, without changing capture provenance.

To regenerate a report from a sealed WF-02 capture:

```bash
python -m hp437b.stability report \
  --bundle output/reports/new-wf02-capture \
  --output output/reports/new-wf02-reported-again
```

Reporting verifies saved evidence and performs no acquisition or source action. It accepts sealed synthetic WF-02 v1 captures and the explicit [physical POWER REF schema/contract](WF-02-PHYSICAL.md), with mode-specific validation and presentation. WF-01 bundles remain WF-01; no import relabels them as stability experiments. The existing WF-01 report commands remain unchanged.

## Fixed v1 profile and evidence

| Stage | Recorded behavior |
| --- | --- |
| Preflight | Validate scenario, operator, optional criteria, and output layout before constructing fakes; verify simulated initial source-off/settings |
| `baseline-before` | Three signed source-off readings in W; retain the baseline mean as the report's “zero” |
| Source on | Explicit simulated OC1 with setup acquisition/status verification |
| `settling` | Retain a twenty-second observation acquisition, excluded from plateau/bin/drift statistics |
| `plateau` | 1,800-second acquisition-start window, one-second requested spacing, ten-second operation timeout; six 300-second receipt-time bins |
| Source off | Explicit simulated OC0 and status verification after healthy completed I/O |
| `baseline-after` | Three source-off readings, then healthy close/free-run/local return through existing APIs |
| Finalization | Seal capture, validate/recompute results/provenance, and optionally generate the report after closure |

The whole-run virtual ceiling is 2,100 seconds. Captures retain actual timing/counts; irregular simulated spacing does not promise 1 Hz or 1,800 rows. Setup probes, settling samples, and post-stage probes are not plateau samples. The fake clock is normalized at the setup boundary to avoid floating-point artifacts at the finite acquisition-start limit; the normal logger is untouched.

Each capture contains `starting.json`, `workflow.json`, `stages/*.csv` and existing `.csv.session.json` files, `trace.json`, inspectable simulation/analysis source snapshots as text, and a final `artifacts.json` inventory. The starting checkpoint deliberately retains its original `running` state; the final workflow plus valid completion inventory governs closed-capture import. A crash or storage failure before sealing is incomplete evidence, not a completed run.

The workflow records software/full commit identity and module hashes, fictional source/meter/sensor/adapter identities, virtual UTC start/finish, criteria, operator, stage outcomes, and simulated source/local certainty. Stage CSV files use the existing logger format. Initial status remains in the logger sidecar; fresh post-stage status is retained in the workflow manifest. A report validates session/run/stage joins, raw-frame/value/unit consistency, finalized outcomes, source/settings status, source hashes, and final-state consistency. File inventories check consistency, not authenticity.

The report folder contains:

| Artifact | Purpose |
| --- | --- |
| `report.html`, `report.md` | Concise **RF Output Power Test**, with Test set to **Sustained output stability**, conspicuous synthetic identification, zero baseline, drift results, coverage, and interpretation limits |
| `power-trend.png`, `.svg` | Optional sample-only plot with separate bin-mean markers; no interpolation across gaps |
| `results.json` | Recomputed full-precision results, bins, points, stage results, coverage, criteria/outcomes, and reasons for unavailable metrics |
| `provenance.json` | Reusable PROV-01 record, evidence hashes/pointers, supplied synthetic identities, run/DUT/equipment joins, and captured operator |
| `report-context.json` | Report-time operator attribution, independent of original capture facts |
| `evidence.html`, `evidence.md` | Technical appendix: capture, provenance, calculations, methods, and complete results |
| `artifacts.json` | Written last: report inventory, source inventory digest, report harness identity/full commit, context, execution, acceptance, and deterministic-only analysis declaration |

The footer order remains Equipment traceability, Report Harness, and Record. A report storage error retains diagnostics without a completed report inventory; the sealed capture can be reported again to a new output path. It never repeats the synthetic acquisition or changes the saved source state.

## Calculations and coverage

All power statistics use valid linear W readings, with 34-digit Decimal calculation precision. The report displays mW/µW; machine results retain W. Baselines may be signed, are descriptive, and are never subtracted. No sensor/fixture correction, uncertainty, reference-accuracy claim, or DUT compliance limit is invented.

- Mean, minimum, maximum, and peak-to-peak describe valid plateau samples. They are not time-weighted energy statistics.
- Bins are `[start, end)`, with an exact final endpoint included in the last bin. Receipts after the declared window remain explicit in global sample statistics and a separate count, outside bins; they prevent a passing comparison. Acquisition-start bounds and receipt-time bins are different concepts.
- Endpoint change is the last-bin mean minus the first-bin mean. Percent change uses the positive first-bin mean as denominator. Missing endpoint bins leave both change metrics unavailable; zero/negative first means leave percentage unavailable rather than dividing or fabricating zero.
- Drift slope is unweighted least-squares power against actual monotonic receipt seconds, scaled to W/min. It requires two distinct valid times. Filtering/sensor response remains part of the recorded measurement path; slope does not isolate transmitter thermal behavior.
- Coverage records expected/present bin counts, per-bin sample counts, attempted/valid/nonvalid totals, receipt span, median valid spacing, and maximum gap including window edges. Invalid rows remain explicit gaps; no interpolation supplies missing values.

The report separates execution, coverage, and acceptance. **No criteria means Acceptance: NOT EVALUATED.** Completion does not mean DUT pass. The synthetic reference signal remains the named subject; it cannot be relabeled a measured radio.

### Optional explicit comparison

V1 supports one limited rule: maximum absolute endpoint drift percent, subject to minimum valid samples in every bin and a maximum valid-receipt gap including window edges. Supply the complete criteria file before capture using `--criteria PATH`. For example, this is a **fictional software-test criterion**, not an adopted equipment specification:

```json
{
  "source": "Fictional software example revision 1",
  "decision_rule": "inclusive-no-guard-band",
  "max_abs_endpoint_drift_percent": "3",
  "min_samples_per_bin": 1,
  "max_gap_s": "2"
}
```

Numeric limits are decimal strings; the sample count is an integer. Bounds are inclusive. A valid completed execution with sufficient coverage and a defined percentage compares `abs(endpoint_change_percent) <= limit`. A failed/interrupted execution, invalid rows, insufficient bin/gap coverage, late receipts, or an undefined percentage returns **not evaluated**, never an overall pass. A completed comparison outside the supplied drift limit returns **fail**. Synthetic pass/fail remains a fictional comparison, not a measured DUT verdict. The explicit no-guard-band rule does not account for uncertainty and cannot establish metrological conformity. Other decision rules/fields are rejected rather than silently ignored. Target-power bands and uncertainty-aware verdicts remain future extensions.

CLI exit status is zero for completed execution with no failed comparison, one for failed/interrupted execution or a failed comparison, and two for input/publication errors. A report can finish successfully while faithfully reporting failed measurement execution.

## Synthetic cases and acceptance

| Scenario | Expected behavior |
| --- | --- |
| `constant` | Full window; 1 mW plateau, zero endpoint drift and slope |
| `ramp` | Slow increasing plateau; calculations use quantized saved frames and actual receipt times |
| `step` | Mid-run level change; sample and bin means preserve the discontinuity |
| `irregular` | Nonuniform receipt spacing; slope uses timestamps, and actual coverage/rate is reported |
| `excess-drift` | Larger ramp; optional supplied drift limit can fail |
| `nonpositive` | Signed near-zero plateau; absolute statistics remain available, percentage is undefined |
| `missing-first`, `missing-last` | Deliberately shortened/offset captures, explicitly interrupted; one endpoint bin absent, percentage unavailable |
| `timeout`, `malformed` | Failed row and partial capture; no subsequent blind commands, source/local state unknown |
| `cancel` | Between-transaction cancellation; healthy bounded simulated source-off cleanup, interrupted execution |
| `source-off-failure` | Full plateau but failed shutdown; overall execution failed and final state unknown |

Independent numerical tests use the catalogue's four-point ramp as an oracle, exact inclusive threshold cases, altered timestamp spacing, signed/missing endpoints, gap/bin/nonvalid coverage, and explicit late receipts. Integration tests exercise every scenario through actual `collect`/`Instrument` fakes, PROV-01 validation, sealed reporting, captured/operator precedence, CLI handoffs, optional plots, corruption/symlink and semantic mismatch refusal, output conflict protection, and report-write failure without reacquisition.

Local verification: **687 tests passed with stress enabled**, including 42 WF-02 checks. All twelve synthetic scenarios produced sealed captures, verified PROV-01 records, deterministic reports, and PNG/SVG plots in the ignored `output/reports/wf02-synthetic-20261112/` exercise. Independent oracle/boundary checks, expected failure outcomes, source preservation, and inventories passed. Success, missing-endpoint, timeout, and shutdown-failure report previews each remain one page on Letter and A4. Source/wheel builds and an isolated installed-wheel synthetic CLI run from outside the checkout passed; the latter used no plotting dependency. Lint, formatting, Markdown links, the five original PDF checksums, and `git diff --check` passed. Implementation pushed to `devel` at `7ab4561`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43287825697). No hardware or AI/provider calls were performed.

## POWER REF follow-up

The [supervised physical integration](WF-02-PHYSICAL.md) uses the prepared current sensor/reference path, actual equipment/provenance, source/settings verification, shared exclusive ownership, outer/stage deadlines, and existing uncertainty-aware shutdown. It is a separate runner: the synthetic command still has no physical mode and cannot activate POWER REF. The physical importer checks explicit setup/control/session/free-run evidence and separates protocol cleanup from operator front-panel confirmation. It preserves the current meter's supply discrepancy. Twenty seconds remains a declared observation allowance, not a universal settling specification.

The recorded thirty-minute POWER REF result describes slow changes in the combined source/meter/sensor path. It does not measure a transmitter, establish absolute calibration, or isolate which component drifts. No radio or replacement meter is needed for that scoped reference exercise. External transmitter workflows still require DUT-CTRL-01 and their prepared source/fixture policy.
