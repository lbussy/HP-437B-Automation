# E2E-01 / VAL-01: WF-01 v1 pipeline acceptance

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Requirements and acceptance assertions

The runner's scenario oracles were defined before the campaign from the existing workflow contract and retained evidence. They are software outcome/count assertions, not DUT measurement acceptance limits.

The independent mean check uses 50-digit arithmetic and a relative rounding allowance of `1e-32` for comparison with 34-digit reporting arithmetic. That is a numerical implementation check, not an equipment tolerance, uncertainty estimate, or DUT limit.

## Reproduce the acceptance campaign

```bash
python tools/offline_qa.py --seconds 180 -- \
  python tools/accept_pipeline.py \
  --output output/reports/my-pipeline-acceptance
```

This creates seven fresh synthetic cases and checks their entire pipeline. `--no-plots` is an explicit text-only variant; plots are enabled unless explicitly disabled. The runner refuses optimized Python because the existing synthetic helper uses assertions. Run UUIDs and creation times differ on repetition; the required outcomes, counts, calculations, and graph relationships are reproducible.

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
