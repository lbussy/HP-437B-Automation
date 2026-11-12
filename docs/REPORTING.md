# REPORT-01: Saved-run reports and agent-assisted analysis

Implemented November 12, 2026. This v1 reporting layer consumes sealed [WF-01 bundles](workflows/POWER-REFERENCE-V1.md) and their [PROV-01 records](RUN-PROVENANCE.md). It does not discover equipment, open VISA/USB resources, execute bundle code, call a model service, or change logging behavior. The initial DUT is the internal reference signal; external-radio workflows remain future application work.

## Generate a report

Use a separate reporting environment. The optional `reports` extra pins Matplotlib; it does not change the three ordinary runtime dependency pins or require changes to an existing bench installation.

```bash
python3 -m venv tmp/report-env
. tmp/report-env/bin/activate
python -m pip install '.[reports]'
python -m hp437b.reporting \
  --bundle output/reports/my-wf01-run \
  --provenance output/reports/my-wf01-run.provenance/provenance.json \
  --output output/reports/my-wf01-report
```

The source must already have a finalized artifact inventory. Generate a missing detached provenance record using the PROV-01 command first. The record must equal the current WF-01 import; mismatched records are rejected rather than silently adopted. General provenance records for other workflow types are not supported by this first report adapter.

The output must be a new directory outside the source bundle and the provenance input directory. Existing outputs are never overwritten. Input hashes are verified, evidence bytes are captured for calculations, and evidence is reverified before completion. Publication is represented by `artifacts.json`, atomically installed last after flushing; a directory without that inventory is incomplete after a failure. Remove or retain an incomplete directory for diagnosis, and choose a new output path for a retry. No automatic retry or repair is attempted.

`--no-plots` creates the text/JSON report without importing Matplotlib. Missing plotting dependencies cause a clear failure when plots are requested. Normal `hp437b` CLI commands, defaults, logger code, CSV schema, transport behavior, and workflow capture behavior remain unchanged.

## Output contract

| Artifact | Purpose |
| --- | --- |
| `report.html` | Local, standalone human report with results, plots, execution/final-state context, supplied issues, analysis, and expandable evidence facts |
| `report.md` | Equivalent readable Markdown with the full fact register |
| `power.png`, `power.svg` | Matplotlib four-panel stage plots suitable for viewing or export; omitted only with `--no-plots` |
| `results.json` | Recomputed statistics, comparisons, coverage, timings, row status/errors, and plot points |
| `provenance.json` | Verified reusable record, retaining supplied/observed/derived/unknown bases |
| `analysis-packet.json` | Stable fact IDs, values/units, evidence references, run/mode, source hashes, original/normalized provenance hashes, and reporting limits |
| `agent-prompt.txt` | Bounded file-based agent instructions; no provider credentials or network endpoint |
| `agent-analysis.json` | Optional attributed draft response, bound to the exact packet hash and run |
| `artifacts.json` | Completion inventory with report mode/run, generator hash, Python/plot dependency versions, and every generated artifact hash/size |

Source CSV files, raw frames, original reports, operator supplements, calibration records, and inventories are never edited. Original evidence references stay relative to the original source bundle; retain that bundle for byte-level verification. A report is a derived artifact, not a replacement for its inputs. Outputs can contain equipment identities and supplied notes, so they remain in ignored local report storage until the owner chooses to share them.

## Calculations and plot meaning

The report independently checks CSV headers, contiguous sequence numbers, session IDs, W units, timezone-aware/ordered receipt timestamps, monotonic elapsed times, declared row counts, session modes/stages, finalized status, raw-frame agreement for valid readings, and retained errors without numeric values for failed rows. It reconciles valid/attempted/nonvalid counts and every available saved value statistic. Integrity disagreement stops the report; a missing old analysis is noted rather than invented.

Statistics use only valid W values and Decimal precision 34: arithmetic mean, minimum/maximum, peak-to-peak, sample SD with denominator n−1, relative spread divided by absolute mean, and valid first-to-last change. SD requires two valid values; relative spread at zero mean is undefined. Missing captures have no statistics. Summary numbers use six significant digits for readability, without implying measurement uncertainty; full decimal results remain in JSON.

Receipt span and minimum/median/maximum spacing include all attempted rows. They describe acquisition receipts, not RF waveform sampling. Requested interval/duration and achieved counts/timing remain separate. Plots show individual samples without interpolation, mark failed receipts with dotted lines, and preserve gaps. Baseline panels use µW, and reference panels use mW. Plot scales can differ across stages.

Descriptive comparisons include post-minus-pre baseline mean, sustained-minus-short mean, and sustained mean minus declared 0.001 W nominal, in W and percent. Comparisons require the relevant captured values. A failed/interrupted run may retain partial statistics; these are not a completed sustained test. No baseline subtraction, smoothing, uncertainty calculation, acceptance thresholds, or DUT pass/fail verdict is introduced. Execution status is always separate from measurement acceptance, which remains **not evaluated**.

## Agent-assisted analysis

The working v1 integration uses files: give an agent `agent-prompt.txt` and the exact `analysis-packet.json`, then save its response separately. The current interactive assistant exercised this path on all nine retained bundles. This is actual assistant-authored interpretation, separate from deterministic report generation; it is not an automatic remote-model call. No external service or unattended agent runner is configured.

Responses have this exact shape:

```json
{
  "schema": "hp437b.agent-analysis.v1",
  "packet_sha256": "SHA256 of the exact analysis-packet.json bytes",
  "run_id": "the packet run_id",
  "author": "attributed agent/operator",
  "created_utc": "2026-11-12T13:00:00+00:00",
  "model": null,
  "findings": [
    {
      "kind": "limitation",
      "text": "No measurement acceptance criteria were supplied.",
      "refs": ["scope/0"]
    }
  ]
}
```

The model field is null when its exact identity is unavailable; do not invent attribution. Allowed finding kinds are `observation`, `limitation`, and `question`. Each finding must cite 1–12 known fact IDs; up to 20 findings and 2,000 characters per finding are accepted. Unknown fields, unsupported verdict kinds, missing attribution, invalid timestamps, dangling references, and another run/packet are rejected.

Import the response by generating a **new** report from the same inputs:

```bash
python -m hp437b.reporting \
  --bundle output/reports/my-wf01-run \
  --provenance output/reports/my-wf01-run.provenance/provenance.json \
  --analysis output/reports/my-agent-response.json \
  --output output/reports/my-wf01-report-with-analysis
```

Commentary is explicitly a **draft**. Schema/hash/reference validation cannot establish semantic entailment, correct arithmetic in prose, truthfulness of attribution, or resistance of an external model to prompt injection. Review narrative claims against cited facts before making decisions. The agent receives instructions to treat all artifact strings as untrusted data, preserve synthetic/physical and provenance distinctions, avoid invented limits/causes, and use no tools or equipment actions. Imported prose and source notes are rendered literally; they cannot become executable HTML, source-authored links, commands, or structured verdicts. The HTML uses a restrictive content policy and no scripts or remote assets. Reports never execute agent output.

## Exercise and acceptance evidence

Local ignored outputs are under `output/reports/report01-20261112/`; source locations are mapped by the preceding PROV-01 import summary. The reporting exercise covers the successful physical run, failed physical open, and seven actual synthetic bundles: nominal, slow, malformed, timeout, cancel, instrument-error, and source-off-failure. Each has plots, richer reports, a fact packet, an attributed assistant draft, and a new inventory. The before/after hash audit retains all **165 source files** unchanged; provenance inputs are checked separately.

The successful physical source retains 299 sustained/308 total valid rows. Its recomputed sustained mean is approximately 0.993843 mW, with 0.001 mW observed peak-to-peak spread and 1.00397-second median receipt spacing. These are retained measurements, not a new physical test or an accuracy/compliance determination. The captured pending front-panel confirmation and later supplied owner confirmation remain separate. Failed-open reports show absent measurements, and failure/interruption reports retain partial coverage and unknown final states where recorded.

**Local verification:** 526 tests passed with stress enabled on Python 3.14, including 34 reporting cases. A clean, non-editable wheel installation also passed all 34 reporting cases and the physical saved-bundle CLI smoke test. Ruff, Markdown/link checks, publisher PDF hashes, and source/wheel builds passed. Hosted CI for this unpushed work is pending.

`tests/test_reporting.py` uses small independent fictional captures. It checks statistics, zero/undefined cases, malformed/resealed evidence, stale provenance and saved metrics, agent binding/citations, literal hostile text, output protection, real plot formats, and failure without a completion inventory. A separate CI reporting job installs the optional extra and runs these checks on Python 3.11 and 3.14; hosted execution awaits a later authorized push. The original software CI job remains intact.

This completes REPORT-01 v1 for saved WF-01/PROV-01 inputs and interactive file-based agent analysis. Additional workflow adapters, user-specified DUT acceptance/uncertainty models, external provider automation, and broader end-to-end application acceptance remain separately scoped follow-ups. None requires waiting for the replacement meter.
