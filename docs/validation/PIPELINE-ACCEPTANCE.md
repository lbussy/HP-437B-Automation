# E2E-01 / VAL-01: WF-01 v1 pipeline acceptance

Executed November 12, 2026. The accepted scope is the current fixed WF-01 process, its reusable PROV-01 evidence, REPORT-01 analysis handoff, and saved-run reports. It uses fresh synthetic captures and explicitly selected retained bundles. No meter, USB adapter, Pi, RF source, external model endpoint, or credentials are accessed. Normal logging remains unchanged.

This accepts the first end-to-end software profile. It does not certify the meter, establish DUT accuracy, enable guarded commands, qualify a new physical workflow on Pi, or claim external-model automation. Additional workflow definitions, external-radio experiments, user-defined measurement criteria/uncertainty, and unattended hardware behavior retain their own scopes. Equipment exchange is not a software acceptance gate.

## Requirements and acceptance assertions

The runner's scenario oracles were defined before the campaign from the existing workflow contract and retained evidence. They are software outcome/count assertions, not DUT measurement acceptance limits.

| ID | Required behavior | Evidence |
| --- | --- | --- |
| VAL-P01 | Run all seven synthetic scenarios through the actual workflow helper, Instrument/collect fakes, prospective provenance sidecar, detached reimport, analysis interface, and report | Seven fresh cases; independent execution/count/source-state oracles |
| VAL-P02 | Reprocess selected retained physical/synthetic evidence without changing inputs or relabeling simulation as measurement | Nine retained cases; 165 source files, 27 provenance-export files, and nine supplied draft files unchanged |
| VAL-P03 | Preserve run/mode joins across capture, provenance, normalized report record, packet, analysis, and report inventory | Exact identifiers, original/normalized provenance hashes, packet-byte hashes, and citation validation |
| VAL-P04 | Preserve complete, interrupted, failed, absent, and partial outcomes | Scenario table below; failure after full sustained acquisition remains a failed execution |
| VAL-P05 | Calculate descriptive results from the saved data and preserve invalid-row gaps | Independent CSV count and 50-digit Decimal mean oracle checks the reporting result; failed rows remain missing values |
| VAL-P06 | Produce complete plots, human reports, JSON, provenance, and attributed drafts | Required artifact sets, hashes/sizes, PNG/SVG signatures, local HTML assets/links, and report boundary labels checked |
| VAL-P07 | Reject corruption and cross-run/unsupported analysis instead of publishing success | Tampering at four pipeline boundaries; resealed semantic forgeries; mismatched runs/digests, dangling refs, verdict/command fields |
| VAL-P08 | Protect source evidence and reject incomplete outputs/storage failures | Before/after full-tree audits, input export-inventory checks, output overlap/existence guards, injected storage failure, and no completed campaign inventory |
| VAL-P09 | Exercise actual command-line handoffs and installed-package behavior | Nominal and timeout workflow CLI → provenance CLI → reporting CLI; package tests use installed modules |
| VAL-P10 | Keep normal operation and evidence meanings unchanged | Existing runtime, workflow runners, dependency pins/defaults, and CSV interfaces unchanged; full guarded software suite and manual PDF hashes checked |

The independent mean check uses 50-digit arithmetic and a relative rounding allowance of `1e-32` for comparison with 34-digit reporting arithmetic. That is a numerical implementation check, not an equipment tolerance, uncertainty estimate, or DUT limit.

## Scenario results

**All 16 pipeline acceptance cases passed.** Expected failed/interrupted workflow executions are successful acceptance cases when their evidence and reports faithfully preserve those outcomes.

| Input | Instances | Workflow execution | Total valid / nonvalid | S40 valid | Recorded final source |
| --- | --- | --- | --- | --- | --- |
| Synthetic nominal | Fresh + retained | Completed | 309 / 0 each | 300 | Off, simulated |
| Synthetic slow | Fresh + retained | Completed | 129 / 0 each | 120 | Off, simulated |
| Synthetic malformed response | Fresh + retained | Failed | 8 / 1 each | 2 | Unknown, simulated |
| Synthetic timeout | Fresh + retained | Failed | 8 / 1 each | 2 | Unknown, simulated |
| Synthetic cancel | Fresh + retained | Interrupted | 8 / 0 each | 2 | Off, simulated |
| Synthetic instrument error | Fresh + retained | Failed | 8 / 1 each | 2 | Off, simulated |
| Synthetic source-off failure | Fresh + retained | Failed | 306 / 0 each | 300 | Unknown, simulated |
| Retained successful physical run | One retained | Completed | 308 / 0 | 299 | Captured off; later owner confirmation retained separately |
| Retained physical failed open | One retained | Failed | 0 / 0; captures absent | No capture | Unknown |

Fresh scenarios retain their new run/session UUIDs and prospective sidecars. Retained legacy imports retain their original IDs, including hash-derived legacy synthetic IDs. No new physical observations are made. The current-unit issue and historical factors stay in provenance, and the original pending front-panel confirmation remains separate from the later supplied owner attestation.

The seven fresh cases use **scripted interface fixtures**, explicitly attributed as fixtures with no model inference. The nine retained cases replay the existing **assistant-authored drafts**, preserving their original attribution, timestamp, bytes, run binding, and packet hash. The runner does not manufacture new AI commentary or rewrite an old draft's binding. Draft schema/reference checks do not prove narrative reasoning, semantic entailment, or model resistance to prompt injection; human review remains appropriate before relying on narrative conclusions.

## Reproduce the acceptance campaign

Use a repository checkout with the pinned development tools and optional `reports` extra installed in a separate QA environment. Run through the existing [offline guard](OFFLINE-QUALIFICATION-RESULTS.md), which blocks accidental hardware access and imposes a finite outer deadline:

```bash
python tools/offline_qa.py --seconds 180 -- \
  python tools/accept_pipeline.py \
  --output output/reports/my-pipeline-acceptance
```

This creates seven fresh synthetic cases and checks their entire pipeline. `--no-plots` is an explicit text-only variant; the recorded 16-case acceptance campaign included plots for every case. The runner refuses optimized Python because the existing synthetic helper uses assertions. Run UUIDs and creation times differ on repetition; the required outcomes, counts, calculations, and graph relationships are reproducible.

Optionally supply `--retained-manifest PATH` to add up to 32 explicit retained cases. Paths resolve relative to that manifest. Each case requires a sealed source bundle, sealed provenance export, an existing bound draft, and the expected `[execution, total_valid, total_nonvalid, S40_valid, final_source]` oracle. For example, using fictional paths:

```json
{
  "schema": "hp437b.retained-cases.v1",
  "cases": [{
    "label": "prior-synthetic-nominal",
    "bundle": "prior/capture",
    "provenance": "prior/capture.provenance/provenance.json",
    "analysis": "prior/drafts/agent-analysis.json",
    "expected": ["completed", 309, 0, 300, "off"]
  }]
}
```

The output must be new and outside all retained source/provenance/draft directories. The runner imports only the maintained repository helper, never captured bundle code. It validates input provenance-export inventories as well as record-to-source evidence. Label/path/schema errors fail explicitly; no discovery or hardware fallback exists.

A complete campaign has `acceptance.json`, per-case `case.json`, full derived reports/provenance, and an atomically installed root `artifacts.json` inventory. The root inventory is the completion boundary; partial directories or a summary without a valid inventory are not accepted. Failures retain diagnostics and, where possible, `failure.json`; they return nonzero without a completed campaign inventory. Preserve incomplete output for diagnosis, and choose a new output directory for another attempt. Report/source measurements are not copied into Git.

## Recorded local evidence

The final full-plot campaign is in ignored `output/reports/e2e01-20261112/campaign-02/`. Its inventory covers every generated file, including nested workflow/provenance/report inventories. Nine retained bundles and their supplied records/drafts were read in place and audited before and after processing.

Acceptance totals: seven fresh synthetic cases, seven retained synthetic cases, two retained physical cases, and 16 richer report sets, each with PNG/SVG plots and a validated draft. Source preservation: 165 retained source files, all 27 retained provenance-export files, and all nine supplied draft files unchanged.

The hardware-denial canary passed in the parent, exec child, and spawned child, with eleven denied access paths in each. `tests/test_pipeline.py` adds 29 automated cases, including genuine subprocess CLI handoffs and deliberately inert hostile bundle code. The full local suite passed **555 tests with stress enabled**, including **29 pipeline tests** and all reporting/plot tests, on Python 3.14. A clean, non-editable wheel installation passed **63 pipeline/reporting tests** and repeated the entire **16-case campaign with plots** in `campaign-wheel/`. Wheel/sdist contents were checked, including the new runner/tests and the absence of raw measurements/publisher PDFs. Ruff, formatting, Markdown links/anchors/tables, original PDF hashes, and `git diff --check` passed. The CI reporting matrix now includes the pipeline suite on Python 3.11 and 3.14; hosted CI for these local changes has not been run.

## Acceptance disposition

E2E-01 and VAL-01 are complete for this **WF-01 / PROV-01 / REPORT-01 v1 profile**, completing Phase 3 within that declared scope. This is software-process acceptance and faithful reporting of retained evidence. It does not imply an external-radio result, external provider integration, unrestricted commands, blanket host compatibility, or unattended hardware recovery. Those future capabilities are not prerequisites for this completed profile.

Local evidence hashes:

| Artifact | SHA-256 |
| --- | --- |
| `campaign-02/acceptance.json` | `7c9925435fd571e8f14d4d0902408f1b878293f0ee3520f604be05142496eeaf` |
| `campaign-02/artifacts.json` | `22250ee167600748aa789f980d65a595ce36af3d2c93fded5e0e3b166f37c4e0` |
| `campaign-wheel/acceptance.json` | `81a61d16f859759a905b9b92925cbf39ef6bfaf62599bd71886f45bb34d7b86a` |
| `campaign-wheel/artifacts.json` | `53ea3660f85f16984cc59a54168a0e686d81e0b5b9e5e0efe2b8d7b88455b32c` |
