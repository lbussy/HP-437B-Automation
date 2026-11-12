# Human-started workflows with deterministic reports

Implemented November 12, 2026. The owner selected **human-started tests and deterministic reports only for now**. AI/provider integration is deferred. This feature joins the existing WF-01 capture, PROV-01 import, and REPORT-01 calculations/plots without requiring an analysis-file handoff. No model, API key, external provider, or automatic test scheduling is involved.

## One-command synthetic test

Use a separate development/reporting environment with the existing pinned dependencies and optional `reports` extra. From the repository checkout:

```bash
python tools/offline_qa.py --seconds 120 -- \
  python tools/exercise_workflow.py \
  --scenario nominal \
  --output output/reports/new-capture \
  --report-output output/reports/new-report
```

The explicitly synthetic workflow closes/seals its capture and prospective provenance sidecar, then creates the richer report automatically. Open `output/reports/new-report/report/report.html` afterward. `--report-no-plots` is the explicit text/JSON-only variant. Nominal and slow scenarios return zero; failed/interrupted scenarios can still produce useful partial reports but retain a nonzero workflow exit status.

The other synthetic scenarios are `slow`, `malformed`, `timeout`, `cancel`, `instrument-error`, and `source-off-failure`. They remain simulations, including source/local state and timing; none measures physical equipment.

## Report an existing bundle

A human can also select any sealed existing WF-01 bundle without specifying or moving a provenance/analysis file:

```bash
python -m hp437b.workflow_report \
  --bundle output/reports/my-capture \
  --output output/reports/my-deterministic-report
```

The command imports and verifies provenance automatically, then builds the HTML/Markdown/JSON report and PNG/SVG plots. `--no-plots` does not require Matplotlib. A completed capture returns zero; a failed/interrupted capture with a completed report returns one; a publication error returns two. Report completion does not change measurement execution or invent a DUT acceptance verdict.

## Optional physical post-capture reporting

The existing supervised physical WF-01 CLI accepts the same optional `--report-output` and `--report-no-plots` arguments. Add them to the already prepared physical invocation:

```bash
python tools/run_power_reference.py \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --setup tmp/my-prepared-setup.json \
  --output output/reports/new-physical-capture \
  --confirm-prepared-reference \
  --report-output output/reports/new-physical-report
```

This is a placeholder command, not authorization to operate the meter. Use the [existing physical setup/preconditions](WF-01-PHYSICAL.md) and an explicitly selected resource. The first physical runner remains the scoped Mac profile. No hardware run was performed for this reporting change; the added CLI hook was tested through explicit fake adapters, including a timeout and a report-write failure.

Reporting starts only after `execute()` returns with connections closed and capture files sealed. The original supervisor, stage deadlines, source/cleanup policies, setup confirmation, and no-retry behavior remain in place. Its outer deadline can also interrupt late report generation; a sealed capture can be reported later with the saved-bundle command. Reporting failure never reopens a device, repeats acquisition, switches POWER REF, or changes recorded final state. A report generated before an operator response correctly retains pending front-panel confirmation; it does not fabricate confirmation.

Without the new optional arguments, both existing workflow CLI paths retain their prior behavior. The ordinary `hp437b` CLI, logger, instrument/transport source, defaults, dependency pins, CSV schema, and `run()`/`execute()` capture behavior are unchanged.

## Output and failure contract

Capture and report outputs must be separate, non-nested, new directories, including separation from the capture's prospective `.provenance` sidecar. Output conflicts and a missing plotting package are checked before an optional physical capture starts. This availability check does not guarantee that every plotting dependency or later storage operation will succeed.

The richer-report directory contains:

| Path | Purpose |
| --- | --- |
| `provenance/` | Fresh verified PROV-01 export with its own inventory |
| `report/` | One-page RF output result sheet, separate technical appendix, JSON, plots when requested, provenance, fact packet, and inventory |
| `job.json` | Capture run/mode/execution, deterministic-only analysis, report outcome, and capture/provenance/report inventory hashes |
| `artifacts.json` | Root completion inventory, atomically installed after flushing |
| `failure.json` | Error-type diagnostic when publication fails after output allocation; no successful root completion inventory |

The existing REPORT-01 fact packet/prompt artifacts remain for format compatibility, but no agent response is supplied or generated. Report inventory `agent_analysis` is `not_supplied`; job `analysis` is `deterministic_only`. All values are computed from evidence. AI narration, model credentials, provider processes, and network clients are absent from the publisher.

The root inventory is the job completion boundary. A partial directory or `job.json` without a valid root inventory is not a completed job. Outputs are never overwritten. Preserve failed output for diagnosis, and choose a new report path when reporting a sealed capture again. A report failure does not require repeating a physical measurement. Original captures, reports, sidecars, calibration references, and operator supplements stay untouched.

## Verification and examples

The ignored local exercise in `output/reports/deterministic-run-20261112/` contains seven fresh, one-command synthetic runs and deterministic reports from all nine retained WF-01 bundles. All 16 produced richer reports/plots with no AI calls or hardware I/O. Expected failed/interrupted executions stayed failed/interrupted; all 165 retained source files and the original provenance records stayed unchanged.

The physical sample report is at `retained-physical-completed/report/report.html` beneath that exercise directory. It contains the saved 299-row sustained/308-row total physical capture, plots, provenance, and limitations. The nominal synthetic sample is `fresh-nominal/report/report.html`; the partial timeout example is `fresh-timeout/report/report.html`. They are locally generated artifacts, not committed measurements or new physical tests.

Automated checks cover all seven scenarios; root/child inventories and source preservation; absent AI processes/responses; path/conflict/dependency preflight; unsealed capture refusal; CLI status behavior; plot formats; and fake physical closure-before-reporting/failure-without-reacquisition. **Local verification:** 581 tests passed with stress enabled on Python 3.14. A clean, non-editable wheel installation passed all 38 deterministic-publication and fake-physical tests. Ruff, formatting, source/wheel builds, package-content checks, Markdown links, publisher PDF hashes, and `git diff --check` passed. The 16 job inventories were reverified, with no generated agent responses. CI reporting checks include the new deterministic suite and the physical fake tests; implementation commit `786d7a5` is pushed to `devel`, with [software/reporting CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43249946227) on Python 3.11 and 3.14.

## One-page RF result sheet

The primary HTML/Markdown report now presents what was tested, when, the measured output power, and the acceptance outcome. A compact plot and equipment traceability complete the sheet; the full diagnostic/provenance content is in `report/evidence.html` and `report/evidence.md`. See the [reader-facing report contract](../REPORTING.md#reader-facing-rf-report-contract). Existing source measurements are not relabeled as transmitter measurements.

Presentation verification uses the retained real POWER REF run plus synthetic/failure cases. The primary sheet prints on one page; the separate appendix retains all machine evidence. Ordinary logging and the measurement sequence remain unchanged.

## Operator name

Configure a persistent shell default with `export HP437B_OPERATOR="Your Name"`, or add `--operator "Your Name"` to a workflow invocation. The physical setup JSON can also supply an `operator` field. CLI overrides setup/captured attribution, which takes precedence over the environment; original saved captures are never modified by a report-time override. Both `python -m hp437b.workflow_report` and `python -m hp437b.reporting` accept `--operator` for saved inputs. The top section shows **Not recorded** when no name is available. See [operator attribution and precedence](../REPORTING.md#configurable-operator).
