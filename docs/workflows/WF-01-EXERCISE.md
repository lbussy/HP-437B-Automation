# WF-01 synthetic workflow exercise

Executed November 12, 2026. Scope: an executable synthetic-only prototype of [POWER REF measurement and repeatability v1](POWER-REFERENCE-V1.md), using the real Instrument and collect implementations, explicit fake source/transport state, and a virtual clock. No USB enumeration, physical meter/RF command, external agent call, dependency change, or normal logger/runtime change occurred. This exercises measurement orchestration and produced reports rather than qualifying the meter.

## Results

| Scenario | Workflow outcome | S40 valid / nonvalid rows | Final source/local certainty | Interpretation |
| --- | --- | --- | --- | --- |
| nominal | Completed | 300 / 0 | Off/local, simulated | Full 300-second acquisition-start window; 1-second median receipt spacing |
| slow | Completed | 120 / 0 | Off/local, simulated | Same requested window; 2.5-second median spacing reported honestly; no invented missing samples or catch-up burst |
| malformed | Failed as injected | 2 / 1 | Unknown | Failed raw frame retained; subsequent measurement stages skipped; no post-fault write |
| timeout | Failed as injected | 2 / 1 | Unknown | Synthetic exception, not a real worker/USB timeout; no post-fault write or replay |
| cancel | Interrupted as injected | 2 / 0 | Off/local, simulated | Between completed samples; one bounded healthy source-off cleanup, partial CSV/report retained |
| instrument-error | Failed as injected | 2 / 1 | Off/local, simulated | Complete error sentinel halts workflow, retains raw frame/error diagnostic; healthy source-off cleanup permitted |
| source-off-failure | Failed as injected | 300 / 0 | Unknown | Source-off transfer failure stops progression; no blind retry or final-baseline capture |

The nominal run has 309 valid CSV rows across four acquisition stages (three baseline-before, three short, 300 sustained, and three baseline-after). Setup/probe acquisitions remain excluded. S40 mean is 0.000988 W (0.988 mW), peak-to-peak is 0.000002 W, and sample SD is approximately 0.000000817860820 W. Mean versus declared nominal 0.001 W is −0.000012 W (−1.2%); this is descriptive, not accuracy/compliance acceptance. The source-off fixture mean is −0.05 µW before and after. Synthetic outcomes establish no physical readings or source/local state.

Every scenario produced CSVs with existing sidecars, workflow/analysis JSON, a transaction trace, Markdown report, artifact inventory, and snapshots of the exact prototype/definition plus LICENSE. Software provenance records base commit `3b0c3b1`, dirty-tree state, Python/runtime versions, and source hashes. This is uncommitted prototype work; the base commit alone does not identify it. Snapshots allow inspection of the actual bytes used.

## Verification

- Ten end-to-end regressions: nominal/slow capture counts, row-derived mean, artifact hashes, five fault/cancellation outcomes, no post-uncertain writes, failed raw evidence, output protection, corruption rejection, and report-storage failure without a completed manifest.
- Full suite with opt-in stress: **431 passed**. Default suite would select the three stress cases as opt-in; no new remote CI result is claimed.
- Independently audited all seven produced bundles: **102 artifact hashes**, prototype/definition snapshots, report-relative links, and Decimal statistics recomputed directly from saved CSV rows.
- Lint/format, repository Markdown links/anchors, inventory IDs, reference checksums, and `git diff --check` pass. Existing `src/hp437b/`, dependency pins, and CLI/defaults remain unchanged.

Generated outputs are ignored under `output/reports/wf01-20261112/exercise-01/`, with scenario subdirectories containing `report.md` and `artifacts.json`; `exercise-summary.json` records the seven outcomes. The earlier `nominal/` sibling is a preliminary local exercise, not the reviewed seven-case set. Raw synthetic artifacts and local machine/run metadata are not committed. New tests and the prototype are maintained project files.

## Implementation boundary

The prototype is `tools/exercise_workflow.py`; its CLI offers only synthetic scenarios and refuses an existing output directory. All session operations use explicit fakes. Stage validation and fail-fast instrument-error policy are in a workflow-specific Instrument adapter; generic collect behavior remains unchanged. The sentinel is retained as a failed workflow row with raw frame and error diagnostic, rather than changing ordinary logger sentinel handling. Private Instrument uncertainty is observed by this prototype; that is an integration boundary to replace with a deliberate interface when building the physical runner.

This is not a finished physical workflow engine. Remaining work includes a physical stage-budget controller, arbitrary validated profiles, complete crash-safe stage checkpoints, richer equipment/calibration provenance, hardware source/local observation, plotted reports, report input revalidation as a supported user operation, and external agent commentary. Storage inability can prevent final artifacts; a missing/mismatched manifest or inventory is incomplete evidence, not a completed bundle. The prototype keeps an explicit starting checkpoint and writes the final workflow manifest after the other artifacts.

POWER REF can provide the real signal for a later selected supervised physical run with the prepared sensor. That needs the physical runner integration and current setup confirmation, not a radio or replacement-meter qualification campaign. Existing physical operation evidence remains separately scoped.
