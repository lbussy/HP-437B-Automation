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
| `report.html` | One-page RF output result sheet: tested device/source, test time/frequency, power results, execution/acceptance, key limitations, and concise equipment traceability |
| `report.md` | Concise Markdown result sheet |
| `evidence.html`, `evidence.md` | Separate technical appendix: full facts, provenance, calculation methods, phase plots, execution/final-state detail, and any supplied draft agent commentary |
| `power-trend.png` | Compact sustained/short-capture plot for the result sheet |
| `power.png`, `power.svg` | Four-panel phase/baseline plots retained in the technical appendix; plots are omitted with `--no-plots` |
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

**Local verification:** 526 tests passed with stress enabled on Python 3.14, including 34 reporting cases. A clean, non-editable wheel installation also passed all 34 reporting cases and the physical saved-bundle CLI smoke test. Ruff, Markdown/link checks, publisher PDF hashes, and source/wheel builds passed. Implementation commit `69cdbd3` is pushed to `devel`; [hosted CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43240463152) for the software and reporting jobs on Python 3.11 and 3.14.

`tests/test_reporting.py` uses small independent fictional captures. It checks statistics, zero/undefined cases, malformed/resealed evidence, stale provenance and saved metrics, agent binding/citations, literal hostile text, output protection, real plot formats, and failure without a completion inventory. A separate CI reporting job installs the optional extra and runs these checks on Python 3.11 and 3.14; [hosted execution passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43240463152) for implementation commit `69cdbd3`. The original software CI job remains intact.

This completes REPORT-01 v1 for saved WF-01/PROV-01 inputs and interactive file-based agent analysis. Additional workflow adapters, user-specified DUT acceptance/uncertainty models, external provider automation, and broader end-to-end application acceptance remain separately scoped follow-ups. None requires waiting for the replacement meter.

## Human-started deterministic publication

The owner selected deterministic reports only for now. Use the [human-started workflow/report integration](workflows/DETERMINISTIC-RUN.md) to produce provenance and richer reports after capture without analysis-file handoffs. Existing file-based agent support remains available, but automated AI/provider integration is deferred and no model calls were made for this feature.

## Reader-facing RF report contract

The owner clarified that the primary report is a concise answer about the equipment being tested, not pages of software diagnostics. The result sheet leads with **what was tested, when, conditions, RF power results, and the acceptance outcome**. The meter/sensor/fixture is a compact traceability footer. Detailed hashes, raw evidence links, provenance fact bases, calculation methods, stage records, and any agent draft remain in the separate technical appendix.

A transmitter report needs the transmitter name/model and serial, test purpose, recorded time, frequency/signal conditions, measured power at the stated measurement point, applicable limits and verdict, and relevant fixture/measurement limitations. Missing limits mean acceptance is not evaluated; a completed acquisition is not a DUT pass. Missing captures stay “not measured,” and interrupted/failed tests retain that outcome even when useful readings exist.

For retained WF-01 data, the tested source is **POWER REF**, not a transmitter. The sheet preserves that identity; a supplied transmitter name cannot relabel an internal-reference capture. The view supports named DUT/serial metadata for future non-reference records, but the existing WF-01 importer and physical sequence remain reference-source-specific. No new transmitter workflow or fictitious transmitter measurement is claimed.

Human-facing units scale to W, mW, or µW. Positive mean power is also shown as `10 log10(mean_W / 0.001)` dBm; this is dBm of the linear mean, not the mean of sample dBm. Zero/negative/missing power has no dBm conversion. Full-precision W statistics remain in `results.json`. Test times use explicitly labeled UTC from the original capture, not report-generation time. Test frequency is marked declared, not measured by the power meter.

The new sheet and compact plot are derived presentation only. Raw measurements, the run/DUT/equipment record, acceptance criteria, and normal logging are unchanged. The report inventory now records a presentation version and module hash. Earlier generated reports remain sealed and are not overwritten.

The revised result sheets were regenerated for all nine retained bundles, preserving all 165 source files. Print-layout verification covers completed, failed-open, partial, interrupted, and shutdown-failure cases on both Letter and A4. HTML-to-PDF tools used for this check are isolated QA dependencies, not application or logger requirements. The sample PDF is a derived preview outside the sealed report directories.

Local verification for the result-sheet revision: **591 full-suite tests** passed with stress enabled; the final presentation/pipeline subset and a clean-wheel installation each passed **111 tests**. All **18 Letter/A4 PDF checks** (nine retained cases) were one page. Failure/partial/empty layouts were visually reviewed. The revised sample jobs are under ignored `output/reports/one-page-report-20261112/sample-reports/`; `POWER-REF-result-sheet.pdf` is the derived one-page preview. The deterministic workflow and report updates are pushed at `786d7a5`, with [software/reporting CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43249946227) on Python 3.11 and 3.14.

The sheet title is **RF Output Power Test**. A single **RF-off baseline ("zero")** row displays the mean of valid S10 readings taken before RF activation, in µW, with the sample count. Small negative values are preserved; a missing baseline is “Not captured,” not zero. This is the recorded RF-off indication, not a claim that a zero-adjustment procedure was performed, and it is not subtracted from the RF-on results. Additional DUT test types are tracked in [WF-CATALOG-01](PLAN.md#additional-dut-test-workflows).

The final title/RF-off-baseline revision passed 114 targeted presentation/pipeline tests and one-page Letter/A4 checks. Implementation and the additional-workflow TODO were delivered in `786d7a5`; normal logger/instrument/transport source and dependency pins remain unchanged.

## Report harness footnote

The result sheet places **Report Harness** above **Record** in the footer. A clean, unambiguously tagged release shows its semantic version; a development build shows its 12-character commit and modification state. This identifies the software generating this report; the software recorded during the original measurement stays unchanged in capture provenance. The report inventory retains the full commit, declared package version, semantic tags, release identity, identity basis, and modification state.

For a source checkout, identity comes from the package’s own project directory, not the current working directory or an input bundle. Bounded, read-only local Git queries identify the commit, modification state, and semantic tags pointing exactly to that commit. Uncommitted changes are labeled **modified working tree**, and an unavailable status is not reported as clean. Built distributions preserve this snapshot as described below. Older VCS-install metadata can supply a recorded commit; an unstamped package without VCS information explicitly shows **commit unavailable**. It never borrows a nearby repository or capture commit. Existing report hashes remain available for exact artifact verification. No credentials, origin URLs, model calls, or device operations are included in the identity query.

## Configurable operator

An **Operator** row appears in the top section. Pass `--operator "Your Name"` to either workflow CLI or the saved-bundle/report commands. For a host-level default, set `HP437B_OPERATOR` in your shell environment. No login, Git author, account profile, or hostname is used to infer an operator.

For new captures, the workflow records the selected name before device work: CLI argument overrides a physical setup file's `operator` value, which overrides the environment default. Synthetic captures store the name in `workflow.operator`; physical captures store it in `workflow.setup.operator`. PROV-01 retains it as a supplied fact with an evidence pointer. Names are trimmed, single-line, nonempty, and limited to 120 characters; invalid configured names fail before a new CLI capture starts.

For reporting, precedence is an explicit argument, then the captured operator, then the environment default. Without any name, the sheet says **Not recorded**. Attribution supplied while reporting a historical capture is recorded separately in report context, with its origin/basis; it does not rewrite original capture provenance or claim independent identity verification. The selected report attribution is included in the report inventory and deterministic job summary.

The redundant **PHYSICAL - recorded test** line is removed from the primary sheet. Mode stays in the source, provenance, report inventory, and technical appendix. Synthetic reports retain the prominent simulation warning so examples cannot be confused with measured transmitter results.

Local operator/header verification: **620 tests passed with stress enabled**, including CLI-to-capture-to-provenance attribution, fake physical setup precedence, unchanged legacy imports, and rendering. Physical and synthetic samples remain one page on Letter/A4; no hardware or model calls were performed. Source/wheel builds, lint, Markdown links, PDF checksums, and `git diff --check` passed. Hosted CI for these local changes is pending.

The **Report Harness** label identifies the generator using the tag-aware policy below. Tagging/publishing and changing the Python package version remain explicit release actions; this feature performs none of those actions itself.

## Tagged releases and development builds

- A clean checkout at an exact semantic-version tag shows, for example, **Report Harness: HP 437B Automation v1.2.3**. Annotated and lightweight tags are supported. Tags may use `v1.2.3` or `1.2.3`, including valid prerelease/build identifiers.
- Untagged commits, commits after a tag, modified tagged sources, unavailable cleanliness, or ambiguous distinct semantic versions at one commit use the **commit** development label. A nearest/older tag is never presented as the current release. Non-semantic tags are ignored. Two spellings of the same version (`1.2.3` and `v1.2.3`) are treated as aliases.
- The full Git commit remains in `artifacts.json` under `report_producer.commit`, including when the displayed release label omits it. The captured measurement's software identity is independent.
- Wheels and source archives include `_report_build.json`, generated only in build staging directories. This carries the full producer identity and Python-source checksums. An installed copy can identify its release without Git or the original checkout; changed package sources fall back to development identity. Editable checkouts continue to use live source metadata. The build does not write generated metadata into the live source package.
- Package identity checks are consistency checks, not artifact authentication. The declared Python package version remains controlled by `pyproject.toml`; align it during release preparation. This feature changes report labeling and preserves build provenance, without automatically bumping versions, creating tags, publishing artifacts, or changing normal logging.

The build hooks subclass the existing [Setuptools build/sdist commands](https://setuptools.pypa.io/en/latest/userguide/extension.html). Existing dependency pins remain unchanged. CI checkout fetches full history/tags so exact tag information is available to the checks. Release tests create tags only in disposable test repositories; no tag was created in this project.

Local tag-aware verification: **645 tests passed with stress enabled**, including clean annotated/lightweight release tags, untagged/dirty/ambiguous cases, full-commit retention, source-archive → wheel → installed identity, and modified installed-source fallback. Source/wheel builds, lint, formatting, Markdown links, PDF checksums, and `git diff --check` passed. A newly rendered retained-data report stays one page on Letter and A4, with Report Harness above Record. No hardware access, normal-logger changes, project tags, or publication were involved. Hosted CI remains pending for these uncommitted changes.
