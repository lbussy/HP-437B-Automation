# ACCEPT-01: Supplied acceptance limits for saved POWER REF captures

Status: implemented locally after RUN-HISTORY-01 delivery at `26969af`; [Python 3.11/3.14 software/reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43492179916). This separate local change evaluates saved evidence without acquisition. Normal logger, CLI, instrument/transport behavior, physical runner source, measurement timing, and dependency pins are unchanged.

## Operator use and scope

In the local interface, use **Assess saved POWER REF limits**. Select a sealed individual WF-01–WF-03 capture or combined POWER REF suite in the configured run directory. Enter the criteria source/person or specification reference, an optional assessor, the applicable performance limits, and coverage requirements. Press **Create assessment PDF & package**. Results and history identify a separate acceptance assessment rather than a new measurement or rewritten original report.

Each workflow has optional mean minimum/maximum limits in mW. WF-02 also admits maximum absolute endpoint change (%); WF-03 admits maximum cycle-mean spread (%). Bounds are inclusive. There are **no default DUT limits**, nominal-reference tolerances, or inferred requirements. Blank performance limits mean **Not evaluated**. Criteria source is required whenever any numerical requirement is supplied. Changing the selected source clears numeric fields; page reload does not restore previous form limits.

This version uses only the fixed `inclusive-no-guard-band` decision rule. It is a supplied-limit comparison of recorded sensor-input measurements, not an uncertainty-adjusted conformity, calibration, transmitter, or compliance verdict. All decisions are explicitly **post-capture**. They do not establish that limits were selected before the measurement. Original acquisition execution, criteria, reports, known equipment issues, software provenance, and later front-panel observations retain their original scope.

## Coverage and decisions

A performance comparison requires completed native execution, a recorded pre-RF zero, a supplied positive maximum gap, and a supplied minimum valid sample count. The minimum applies to the WF-01 plateau, every WF-02 bin, or every WF-03 cycle, respectively. Coverage must contain no invalid plateau samples or receipts after the declared window. WF-01 gaps include both edges of its recorded duration; WF-02 uses native bin/window coverage; WF-03 requires all requested cycles and their native coverage. These coverage requirements are not RF operating limits and do not change sampling.

- **Pass:** all supplied performance checks for that workflow pass with the required evidence/coverage.
- **Fail:** at least one supplied performance check fails after its evidence/coverage gates pass.
- **Not evaluated:** no performance limit is supplied, the workflow was not captured or completed, coverage requirements are missing/unmet, or a required metric is unavailable.

For an overall Pass, the source execution and every requested workflow must complete and pass its configured criteria. An unassessed requested workflow prevents overall Pass. Any valid workflow Fail produces overall Fail; otherwise an incomplete or unassessed scope is Not evaluated. A completed acquisition can still be Not evaluated if coverage does not meet the supplied requirements. Signed pre-RF zeros remain descriptive and are never subtracted.

Numeric decisions use Decimal arithmetic with 50-digit evaluation precision. Exact equality passes; immediately out-of-bound values fail. Negative/non-finite/excessive numeric inputs, inverted mean bounds, unsupported fields/workflows/rules, invalid counts, and missing source attribution are rejected. Input numbers are bounded to 64 characters and values from zero to 1e12; maximum gap must be positive and sample counts are integers from 1 to 1,000,000. Scientific notation stays compact when stored, including very small values. These software input budgets do not authorize instrument settings or physical signal levels.

## Records, reports, and preservation

Each accepted action creates an `acceptance_review` job and separate output directory. `criteria.json` is a normalized `hp437b.acceptance-criteria.v1` record; `results.json` retains source identity/hash, criteria/hash, per-workflow coverage reasons, every applied limit/observed value/check outcome, and the aggregate decision. Metadata records the assessment ID/time, assessor, post-capture timing, and report producer. `provenance.json` binds original setup/acquisition software and the new assessment facts without rewriting either.

The one-page **RF Output Power Test** presents the original measurement time, assessment time, assessor, criteria source, original execution, supplied-limit result, signed zero, measured power/drift/spread, configured limits, and coverage requirements. Known equipment issues remain visible. A full decision record and criterion document accompany the PDF/HTML and a verified portable ZIP containing the sealed original evidence. Original PDFs, packages, captures, and attestations remain unchanged. Repeated assessment requests use independent destinations and IDs.

The existing owning reader validates each source; an exclusive operational capture lock and expected source inventory hash prevent reuse of an active or changed capture. The portable report validator recomputes assessment decisions from the original evidence and stored criteria before publication. Hashes bind bytes, not author/device authenticity. Assessment/report failures retain the source and partial output; there is no automatic retry, resume, measurement repetition, or blind meter reopen. Original pending front-panel confirmation remains pending and continues to block new acquisition; it does not block this report-only action.

The same-origin authenticated `POST /api/acceptance-review` accepts exactly `source_job_id`, `criteria`, and `assessor`. Filesystem paths, resource names, drivers, and hardware commands are not accepted. The optional reporting/PDF dependencies are unchanged. Historical report recovery still regenerates the original report; acceptance is a separate explicit action. Assessment history entries trace the source and cannot be selected as new measurements for run comparison.

## Verification

The guarded full regression passed **1,405 tests**, with three opt-in stress cases skipped. Acceptance cases cover all three injected native readers, completed/incomplete/missing data, unset criteria, inclusive/adjacent decimal boundaries, signed drift, cycle spread, malformed inputs, attribution, coverage gaps and late receipts, source preservation, report lineage, physical/synthetic packages, recalculation after decision tampering, HTTP origin/body limits, and acquisition-free child execution. The legacy WF-03 fixture includes one late receipt and correctly remains Not evaluated under strict coverage; mathematical boundary cases use a separately healthy in-memory test condition rather than weakening that gate.

Hardware-blocked browser checks used saved current-Mac evidence and clearly labelled **illustrative software-check criteria, not DUT specifications**. They produced Not evaluated with no limits, Pass and Fail with different example limits on the same WF-01 capture, and full three-workflow Pass examples. Missing criteria source was refused without starting an attempt. The enhanced one-page suite PDF was rendered and visually inspected; observations and limits appear together. No instrument was opened and no RF setting or measurement was changed. Local generated evidence remains ignored under `output/reports/report-recovery-demo/` and `tmp/acceptance-review/`.

The final 36-case focused acceptance regression passed after the numeric-input safeguard. Source/wheel builds, source-preservation and package audits, Python lint/format, JavaScript syntax, documentation checks, and desktop/mobile/PDF review passed.
