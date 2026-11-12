# WF-03: Transmission-cycle repeatability

Implemented November 12, 2026, for **synthetic capture, equal-cycle analysis, provenance, and deterministic reporting**. Physical POWER REF integration/execution remains open. This implements the second priority in the [transmitter test catalogue](TRANSMITTER-TEST-CATALOG.md#wf-03-transmission-cycle-repeatability), without changing ordinary logging or operating any hardware.

## Run a synthetic test

Use the existing isolated pinned development/report environment and optional `reports` extra:

```bash
python tools/offline_qa.py --seconds 120 -- \
  python -m hp437b.repeatability synthetic \
  --scenario shifted \
  --operator "Example Operator" \
  --output output/reports/new-wf03-capture \
  --report-output output/reports/new-wf03-report
```

Open `output/reports/new-wf03-report/report.html`. The capture/report outputs must be new, separate, non-nested directories. All elapsed acquisition/wait time is virtual; this does not require a six-minute wall-clock wait. `--no-plots` generates HTML/Markdown/JSON without Matplotlib. Operator attribution follows the established `--operator`, captured-name, and `HP437B_OPERATOR` policy; a report-time override never rewrites captured facts.

A human may regenerate a report from a sealed capture:

```bash
python -m hp437b.repeatability report \
  --bundle output/reports/new-wf03-capture \
  --output output/reports/new-wf03-reported-again
```

This entry point has **no physical mode**, USB resource, source driver/factory argument, resource discovery, AI/provider, or automatic fallback. The named subject is the fictional POWER REF fixture, not a transmitter. WF-01 and WF-02 files cannot be relabeled/imported as WF-03. Normal `hp437b log`, source preservation, CSV/sidecar schema, healthy/failed-read shutdown, dependencies, and existing workflow behavior remain unchanged.

## Fixed cycle profile

The versioned workflow ID is `transmission-cycle-repeatability-v1`. It requests five numbered cycles, C01–C05, absolute W, one-second acquisition spacing, ten-second operation timeouts, three initial baseline readings, and a 900-second virtual whole-run ceiling. Each cycle consists of:

| Action | Evidence |
| --- | --- |
| Source on | Explicit simulated OC1 and a consumed setup acquisition/fresh status |
| Settling | Twenty-second acquisition-start window; readings retained separately and excluded from plateau/aggregate statistics |
| Plateau | Thirty-second acquisition-start window; actual elapsed receipt times and valid/failed rows retained |
| Source off | One simulated OC0 with fresh source-off status; no automatic retry |
| Off dwell | Twenty seconds of virtual source-off allowance, with start/end recorded |
| Off baseline | Three source-off readings, retained separately; healthy close/free-run/local return through the existing APIs |

Preflight refuses an initially on source without adopting it. Status policy verifies absolute W, source state, REL/offset/duty off, no instrument errors, and the selected automatic range/filter mode. No zero, CAL, factor adjustment, reset, USB clear, or new bus capability is enabled. Each stage uses a fresh fake Instrument over the existing `collect` API; every response is consumed before another command.

All clocks, source transitions, status responses, local-return outcomes, and waits in this implementation are explicit fakes. The existing WF-02 fake wire/clock helpers are reused without changing them; WF-03 records their hash and source snapshot alongside its own modules. The whole-run virtual budget is checked as time advances. CLI QA also supplies a real outer wall-clock bound. This is not a qualified physical deadline supervisor; that belongs to the later physical integration.

## Statistics and coverage

The one-page title remains **RF Output Power Test**, with **Transmission-cycle repeatability** in the Test row. It shows the pre-RF “zero,” completed/requested cycles, equal-cycle mean, cycle-mean spread, sample SD, all five requested cycle rows, and an optional cycle-mean plot. Equipment traceability, Report Harness, and Record remain in that footer order. Synthetic identification remains prominent.

Each cycle row retains status, valid/attempted count, available plateau mean, and min/max in linear W. A fully completed cycle requires source-on verification, completed settling and plateau captures, verified source-off, the off dwell, and the off baseline. Failed/interrupted cycles can retain useful plateau data, including a complete plateau followed by failed shutdown; these means remain visible but **do not enter aggregate statistics**. Missing/skipped cycles stay in the five-cycle denominator and on the plot axis/table.

Aggregate calculations use 34-digit Decimal arithmetic and equal weights over completed cycle means, regardless of their individual sample counts:

- Equal-cycle mean = sum of completed cycle means / completed cycle count.
- Cycle spread = maximum minus minimum completed cycle mean; unavailable with fewer than two completed cycles.
- Relative spread = 100 × spread / positive equal-cycle mean. Zero/negative denominator leaves percentage unavailable.
- Cycle sample SD = square root of the squared deviations of completed cycle means divided by `n−1`; unavailable with fewer than two completed cycles.

These are statistics of steady plateau readings, not pooled-sample statistics, time-weighted energy, measurement uncertainty, keying delay, waveform/overshoot/PEP, or calibrated leakage. Signed off baselines remain descriptive, are never subtracted, and are preserved separately for every cycle. Sensor/fixture corrections or uncertainty estimates are not invented. The report does not infer RF response speed from requested sampling intervals.

### Optional supplied comparison

No supplied limits means **Acceptance: NOT EVALUATED**. A completed acquisition is not a DUT pass. V1 supports only maximum cycle-spread percentage, with all five cycles complete, a minimum valid sample count in each plateau, and a maximum gap including each window's edges. For example, this is a **fictional software criterion**, not an adopted equipment specification:

```json
{
  "source": "Fictional cycle example revision 1",
  "decision_rule": "inclusive-no-guard-band",
  "max_cycle_spread_percent": "2",
  "min_samples_per_cycle": 10,
  "max_gap_s": "3"
}
```

Supply it before capture with `--criteria PATH`. Numeric limits are decimal strings; sample count is an integer. Bounds are inclusive, with no uncertainty guard band. Failed/interrupted execution, incomplete cycles, invalid rows, insufficient coverage, receipts after the plateau window, or undefined percentage prevents an overall pass and returns **not evaluated**. An otherwise complete comparison outside the supplied spread bound returns **fail**. Synthetic pass/fail is a fictional comparison, never measured transmitter compliance. Per-cycle target-power limits and other decision rules are future extensions; unknown fields/rules are rejected.

CLI exit status: zero for completed execution with no failed comparison; one for failed/interrupted execution or failed comparison; two for input/publication errors. Report completion and measurement execution remain separate outcomes.

## Failure and preservation policy

Stop progression at the first acquisition, policy, source-control, cancellation, or storage failure. Never replace a failed sample with a late reply or retry. A known healthy between-transaction failure after owned activation can attempt one bounded source-off verification. An uncertain read/write, failed close, or failed/still-on source-off does not lead to another open/write/GTL or OC0 attempt. Subsequent cycles are skipped with reasons. Initial-on is refused without deactivation because the workflow does not own that activation.

The capture contains `starting.json`, a final `workflow.json`, unchanged CSV/session pairs in `stages/`, `trace.json`, inspectable module snapshots as text, and a last-written `artifacts.json`. A finalization/storage failure without the inventory is incomplete evidence; the original running checkpoint stays explicit. Report import verifies mode/schema, file hashes, ordered requested cycles and session joins, source/settings status, closed captures/control/dwell outcomes, raw frames/values/units, and monotonic receipt timing. Hashes establish consistency, not authenticity.

The report output contains `report.html/md`, optional `cycle-means.png/svg`, `results.json`, reusable PROV-01 `provenance.json`, `report-context.json`, technical `evidence.html/md`, and a last-written completion inventory carrying full producer commit/version/context. The appendix retains every stage, cycle, off baseline, method, criteria, and source/final-state outcome. No agent response or manual analysis-file handoff is required. Report failure preserves the sealed capture and never reopens a source or repeats measurement; choose a new report output path for another attempt.

## Synthetic scenarios and acceptance

| Scenario | Intended outcome |
| --- | --- |
| `repeatable` | Five equal 1 mW cycle means, zero spread and SD |
| `shifted` | Means 1.000, 0.990, 1.010, 1.000, and 1.000 mW; equal mean 1.000 mW, spread 0.020 mW (2%), sample SD approximately 0.00707107 mW |
| `unequal-counts` | Same cycle means as shifted, with 15 samples in C02 versus 30 in the others; equal-cycle mean stays 1.000 mW, unlike the pooled-sample mean |
| `nonpositive` | Signed near-zero plateau means; absolute statistics remain available, percentage is undefined |
| `partial-cycle` | Two completed cycles, ten valid C03 plateau rows, interrupted execution; partial mean visible but excluded |
| `missing-cycle` | Two completed cycles; C03 unavailable/interrupted, later cycles skipped |
| `cancel` | Between-read C02 cancellation with healthy source-off cleanup |
| `timeout`, `malformed` | Partial C02 failed row, uncertain final state, no post-fault transactions |
| `instrument-error` | Complete error response stops acquisition; healthy source-off cleanup |
| `source-off-failure` | Full C02 plateau followed by failed off transfer; cycle incomplete/excluded and final state unknown |
| `still-on` | C02 off write completes but verification remains on; no repeated OC0 |
| `source-mismatch` | C02 source-state policy failure; stop and perform known-healthy owned-source cleanup |
| `initial-on` | Refuse preflight without adopting/switching the source; no cycles captured |

Independent tests use the catalogue's three-cycle arithmetic example, deliberately unequal sample weights, inclusive threshold boundaries, absent/negative denominators, missing/partial cycles, coverage, and late receipts. Integration checks exercise every scenario through actual Instrument/collect fakes, provenance, publication, CLI status, input/corruption/semantic guards, source preservation, optional plots, and capture/report storage failures. Local verification: **746 tests passed with stress enabled**, including 45 WF-03 checks. All fourteen scenarios produced verified captures, PROV-01 records, PNG/SVG plots, and deterministic reports in ignored `output/reports/wf03-synthetic-20261112/`. Final presentation refinements were followed by another passing 45-check targeted run. All fourteen report variants remain one page on Letter and A4, with visible no-data/partial states and intact footers. Every original capture stayed unchanged during report regeneration; final presentations are in separate `*-report-v3` directories rather than overwriting sealed outputs. The shifted example PDF is `WF-03-Transmission-Cycle-Repeatability-Synthetic.pdf` at the exercise root.

Source/wheel builds, an isolated installed-wheel synthetic CLI run from outside the checkout without plotting dependencies, lint/formatting, Markdown links, five original PDF checksums, and `git diff --check` passed. The wheel exercise used unequal sample counts and retained all five completed cycles. Hosted CI is pending these local changes. No hardware or model/provider calls were made, and ordinary logging/runtime/pins remain unchanged.

## POWER REF follow-up

The next step is a separate supervised physical integration/exercise using the current prepared direct sensor/reference path and existing source/uncertainty-aware shutdown policy. It needs real source/settings/identity observations, exclusive ownership, cycle/stage/outer deadlines, off-dwell evidence, and owner final-state confirmation. The synthetic command cannot operate the meter. POWER REF can exercise the slow cycle sequence without a radio or replacement meter, but its result describes the reference/meter/sensor path, not transmitter keying or calibration. External transmitter cycles still need DUT-CTRL-01, a rated fixture, and a source-specific permitted duty-cycle/settling policy.
