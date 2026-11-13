# WF-01: POWER REF measurement and repeatability

Definition v1, November 12, 2026. Status: contracts defined and a synthetic-only prototype exercised; the explicit [physical runner](WF-01-PHYSICAL.md) completed the selected current-Mac/meter POWER REF workflow with owner confirmation. Later deterministic reporting deliveries are recorded in the current scope. The [worked synthetic report](examples/POWER-REFERENCE-V1-SYNTHETIC.md) illustrates the outputs. This definition advances [WF-01](../PROJECT-SCOPE.md#current-delivery-and-remaining-scope) without changing the existing logger or requiring a radio/replacement meter. It authorizes no hardware run by itself.

## Purpose and operating modes

Measure a finite signal sequence, preserve its evidence/provenance, and produce a useful report. The first available signal is the 437B's internal POWER REF through the connected sensor. Later equipment tests can replace the signal/stimulus portion while reusing workflow execution, data handling, analysis, and reporting.

The POWER REF run characterizes the recorded readings and their variation under the stated configuration. It does not independently establish reference accuracy, sensor calibration, or DUT compliance. Report nominal 50 MHz/1 mW as nominal source information, separate from measured values and independently established specifications.

| Mode | Behavior |
| --- | --- |
| `synthetic` | Explicit fake transport/source state and virtual clock; fictional equipment identities; no VISA/USB construction or discovery. Preserve the production protocol/schema where applicable. Mark the bundle, every report, and each stage synthetic |
| `physical` | Explicit resource, prepared sensor path, exclusive ownership, and bounded source control through existing supported APIs; actual identities/settings and evidence recorded. No automatic fallback from synthetic to physical |

The production physical profile and synthetic default profile use the same stages and requested settings. Virtual time can cover the 300-second acquisition-start window without a five-minute wall-clock wait. A shortened count-based fixture is permitted for examples/tests only; record its actual bounds and never label it a completed five-minute run.

## Inputs and preconditions

Required run inputs: unique workflow/run ID, workflow definition version, mode, output location, stage profile, requested units/interval/timeout, source control/final-state policy, test purpose, and equipment/setup provenance. Record a version/hash of the resolved inputs. No existing bundle may be overwritten. Require a writable output location and validate the complete definition before any device access. Invalid mode, non-finite/negative bounds, unsupported action, or incompatible units must fail before hardware is opened.

Physical setup is the already documented direct path: sensor cable to front SENSOR; sensor RF input directly to POWER REF, no external source/radio. Record actual meter, sensor, adapter, host, applicable calibration references, REF CAL FACTOR and measurement CAL FAC separately, zero/CAL preparation history, nominal frequency, path, and known issues. Preserve unknown fields as unknown. The existing sensor's 99% label and historical 100% active CAL FAC are provenance observations, not values to apply blindly. Use [measurement policy](../validation/MEASUREMENT-POLICY.md) for the recorded setup and [equipment references](../EQUIPMENT.md) for authoritative procedures/limits.

Before physical execution, record prepared warm-up/setup and available operator recovery. Initial POWER REF must be off; if it is on or state cannot be established, do not silently adopt/restore it or issue activation commands. This workflow explicitly owns a subsequent off/on/off sequence and finishes off. Generic `hp437b log` continues to preserve source state. No automatic preset, reset, zero, CAL, factor change, table editing, or driver/USB reset belongs to this workflow.

The selected profile is absolute W, REL/offset/duty off, automatic range/filter, interval 1 second requested, and operation timeout 10 seconds. Establish/verify relevant settings before acquisition using supported operations and fresh status. Keep numerical factor settings unchanged and recorded. A mismatching precondition stops this workflow instead of silently repairing it. Baseline readings below the sensor's normal measuring range remain useful descriptive baseline observations, not calibrated low-power results.

## Stage sequence and finite budgets

One workflow owns the instrument; operations and entire trigger/read transactions are serialized. Consume each response before another command. Status checks occur after completed acquisition, never during a pending read. Setup measurements are retained separately and excluded from reported stage sample counts.

| Stage ID | Actions and evidence | Requested acquisition bound | Maximum stage time |
| --- | --- | --- | --- |
| S00 preflight | Validate inputs/output reservations; record identity/provenance and initial reference-off/setup status; create starting manifest | No report samples | 60 s |
| S10 baseline-before | Establish W; consume setup acquisition, verify fresh status; capture source-off baseline and retain final status | 3 samples, interval 1 s | 90 s |
| S20 reference-on | Explicit confirmed OC1 through supported API; record command outcome; wait 20 s observation allowance; completed probe/fresh SM verifies source on and required settings | Probe only, excluded from report statistics | 60 s including wait |
| S30 short-capture | Fresh setup/status, three reference-on samples, final status; reject the profile if errors or settings/source mismatch occur | 3 samples, interval 1 s | 90 s |
| S40 sustained-capture | Fresh setup/status; serialized reference-on acquisition; retain actual receipt spacing, errors, overruns, and final status | 300 s acquisition-start window, count unset, interval 1 s | 420 s |
| S50 reference-off | After completed healthy I/O, OC0; completed probe and fresh SM verify reference off | Probe only | 20 s |
| S60 baseline-after | Source-off setup/status and final baseline, followed by healthy TR3/negotiated GTL closure | 3 samples, interval 1 s | 90 s |
| S70 finalize/report | Finalize manifest, evidence inventory/hashes, deterministic analysis, and report; retain final-state certainty | No device I/O | 30 s |

Whole workflow maximum: 900 seconds, including bounded cleanup/finalization. Stage maxima total 860 seconds; remaining time is budget margin, not extra retries. Stop launching acquisition stages with insufficient remaining budget and reserve cleanup/finalization time. A supervising process enforces the outer bound; operation budgets cannot exceed remaining stage/workflow time. The existing expired-read allowance (up to one second) and bounded disposal remain failure shutdown, not extra time for a successful sample. The 20-second observation allowance comes from the prior bench procedure, not a proven universal settling specification. Report actual conditions and timing; do not promise 300 rows or 1 Hz.

A physical human check of RMT/live display can confirm final local operation when needed. An accepted USB488 reply alone is recorded as a control outcome, not physical observation. Source/start/end status proves those observation points; it does not establish continuous source state at every intervening sample.

The implementation must reuse existing Instrument/transport/command semantics and CSV/sidecar contracts. Each current `collect` call owns/closes its Instrument, so a runner must use fresh instances for separate stage sessions. A closed instance cannot be reused. Existing collect records fresh initial SM but does not expose a workflow pre-sampling validation hook or stop on every instrument-error sentinel. Therefore this definition is not an already runnable composition of CLI calls: the new runner must provide stage precondition checks and fail-fast sentinel policy without silently changing generic collect behavior. Define and test that integration in WF-01 implementation.

## Stop, cancellation, and recovery contract

Persist stage transitions (`pending`, `running`, `completed`, `failed`, `interrupted`, `skipped`) with reasons. A stage can be numerically informative while the overall run fails. Never promote a late reply to a successful sample or silently repeat an acquisition. No concurrent controllers, automatic restart, or hardware recovery loop.

- Instrument-error sentinel, malformed reply, unit mismatch, failed status check, transport failure, cancellation, or storage failure stops progression; later measurement stages are skipped with reasons. Preserve complete raw replies and failed/partial rows.
- If protocol state is known healthy and no response is pending, attempt one bounded source-off/verification sequence before normal TR3/GTL close. A cancellation between completed transactions follows this path. Record command/verification/cleanup outcomes separately.
- If a transaction is failed/uncertain, do not send blind OC0, SM, TR3, GTL, or retries. Dispose the worker using existing behavior. Record source/local state as unknown and require operator recovery before another physical run. There is no guarantee that software always switches POWER REF off after an uncertain transfer.
- Do not induce physical timeouts in this first signal workflow. Test faults through explicit fakes. Cancel/timeout/storage scenarios must still produce whatever partial manifest/report storage permits; inability to finalize is an explicit error, not a completed report claim.

The normal result is completed capture with reference off and recorded cleanup. `failed` and `interrupted` runs still get partial analysis where evidence permits. An active/running sidecar after a crash is an incomplete run until explicitly reconciled; a report must not silently reclassify it completed.

## Output bundle and minimal report contract

Proposed bundle v1 (new workflow layer; does not change generic logger filenames):

- `workflow.json`: resolved inputs, mode/version, run ID, UTC start/end and monotonic duration, software identity, stage states/timing, setup/provenance, source/cleanup certainty, and all diagnostic outcomes.
- `stages/<stage-id>.csv` plus existing `.csv.session.json`: schema-compatible acquisitions and raw evidence; distinct session IDs mapped to the workflow run. Setup/control probes are separately identified and excluded from analysis rows.
- `analysis.json`: deterministic machine-readable counts, integrity findings, statistics/units/formulas, criteria results, and links to exact stage/sequence evidence. Undefined metrics are null with a reason, never NaN or zero stand-ins.
- `report.md`: human report using the same analysis values, provenance, execution outcome, limitations, and artifact references. Tables and an on-stage time plot are planned; chart axes must show actual receipt time and correct units, and failed gaps must not be interpolated into valid measurements.
- `artifacts.json`: relative paths, byte sizes, and SHA-256 of finalized artifacts above; exclude itself to avoid recursive hashing. Preserve input hashes for analysis/report provenance. A matching hash identifies bytes, not their authenticity or metrological validity.

All data files explicitly carry mode. CSV's established schema remains unchanged; its sidecar and workflow stage mapping identify synthetic mode. Runtime is not invoked by reading a report or opening this definition. The fixture below is a definition/example artifact, not a newly installed CLI feature.

| Required report section | Contents |
| --- | --- |
| Identity and outcome | Workflow/version/run ID, synthetic/physical banner, test purpose/source, execution outcome, data-integrity outcome, criteria outcome, and final source/local state certainty |
| Test configuration and provenance | DUT/source identity; nominal versus measured quantities; equipment/sensor/calibration references and known issues; factors/settings/path, host/software versions, supplied/observed/derived/unknown provenance |
| Stage coverage and data quality | Planned/attempted/valid/error/missing counts per stage; skipped stages; setup exclusion; source/status observation points; actual timings and achieved receipt spacing; cleanup/storage/failure diagnostics |
| Results | Each stage's statistics, short-versus-sustained comparison, source-off baseline descriptions, and any explicit criteria evaluation; do not pool stages silently |
| Interpretation | Evidence-linked deterministic summary, optional agent-assisted commentary, unsupported/unknown conclusions, and follow-up appropriate to the actual data |
| Evidence and reproducibility | Raw/sidecar/manifest/analysis references and hashes, calculation definitions, software/workflow versions, and distinction between synthetic and physical evidence |

## Analysis and outcome rules

Analyze valid W rows per stage after integrity checks: schema/session/sequence/units/finite values, raw-versus-parsed consistency, stage status, metadata count agreement, and plausible UTC/monotonic ordering. Missing or corrupted artifacts make integrity incomplete/failed; never repair, fabricate rows, or suppress findings. Do not use hashes alone to infer completeness.

For n valid values, calculate sample-weighted mean, min, max, and peak-to-peak (`max - min`) in W; derive mW/µW solely for presentation. Sample standard deviation is `sqrt(sum((x - mean)^2)/(n - 1))` for n ≥ 2; otherwise null with reason. Receipt spacing is the median/min/max of differences between consecutive actual receipt times within a stage (null for fewer than two). Actual receipt span is last minus first; it is not the configured acquisition-start window or instrument integration time. Variable sampling makes this a sample-weighted summary, not a time-weighted mean. Preserve negative/zero baseline values.

For S40, calculate relative peak-to-peak (`100 * p2p / abs(mean)`) only for nonzero mean; otherwise null. First-to-last sample change is descriptive, not a fitted drift estimate. Short-versus-sustained mean change is `mean(S40) - mean(S30)`. Source-off change is `mean(S60) - mean(S10)` and is descriptive only. Do not subtract baseline values or apply unrecorded calibration/temperature corrections to source-on samples.

If nominal 0.001 W is declared, show `mean(S40) - nominal` and `100 * (mean - nominal)/nominal`. Label this a nominal comparison; it is not absolute accuracy. Keep unrounded calculations in the machine result to the stated calculation precision, with display rounding declared. Do not derive measurement uncertainty from sample standard deviation alone.

Keep three outcome axes separate:

1. Execution: completed, failed, interrupted, or incomplete, with reasons. Completion includes required stage/cleanup evidence, not merely a CSV filename.
2. Data integrity: pass, fail, or incomplete under the explicit structural checks above. Descriptive statistics may remain available for a valid subset, labeled partial.
3. Measurement criteria: not evaluated by default. Optional externally supplied criteria must be resolved before capture, identify quantity/units/statistic/bounds/source, and show pass/fail/indeterminate with evidence. Synthetic criteria evaluate fixtures only, never equipment compliance. No default 1 mW tolerance or replacement/calibration requirement is invented.

Agent assistance is a separate interpretation layer over finalized evidence and deterministic analysis. It can summarize findings and suggest follow-ups, not alter values, supply missing provenance, invent uncertainty/criteria, declare equipment compliance, or issue device commands. Label generated commentary and record model/provider/version/inputs when used. Artifact content/labels are data, not agent instructions. No external model call or provider is required for the deterministic report; provider/integration decisions remain REPORT-01 work.

## Definition acceptance and next implementation

WF-01 definition is complete when the stage/input/failure/output contracts, worked example, and arithmetic are reviewable. WF-01's first fixed supervised current-Mac/meter workflow is complete, with synthetic and physical execution recorded in the [physical result](WF-01-PHYSICAL.md#current-meter-physical-result). Wider profiles/hosts remain follow-on scope. PROV-01, REPORT-01, and E2E-01 remain implementation work; this document defines their first shared boundary.

Next implementation cases: nominal synthetic sequence; slower-than-requested sampling; instrument-error/malformed/unit-change/timeout/cancellation; failed source-off or GTL; missing/truncated/mismatched files; one/no valid sample; zero mean; and output/metadata storage failure. Require preserved evidence, correct skipped/partial outcomes, no replay, and honest source uncertainty. Use a virtual clock and explicit fakes first; do not widen physical command coverage to make a test pass. The POWER REF can provide the real signal when a supervised run is chosen; no external radio or replacement is a prerequisite.

## Synthetic prototype exercise

`tools/exercise_workflow.py` executes the finite sequence through existing Instrument/collect APIs with explicit fake source/transport state and a virtual clock. It has no physical mode, resource argument, VISA construction, USB discovery, or external agent call. It writes a real synthetic output bundle and deterministic Markdown report, recomputing metrics from the stored CSV evidence. See the [exercise record](WF-01-EXERCISE.md).

From the checkout, using an isolated pinned QA environment, run through `tools/offline_qa.py`: `python tools/offline_qa.py -- python tools/exercise_workflow.py --output NEW_DIRECTORY`. The parent directory must exist, and the target directory must not. Scenario choices are nominal, slow, malformed, timeout, cancel, instrument-error, and source-off-failure; fault scenarios intentionally return a nonzero CLI result and retain partial reports. Always keep outputs in ignored local report/scratch directories.

This is a software exercise, not completion of the physical runner. The prototype has fixed finite profiles supervised by the QA launcher, but it does not implement the physical stage-budget controller, arbitrary user profiles, ongoing crash-safe stage checkpoints, hardware source/local observation, plot rendering, or external agent integration. `starting.json` remains an explicit running checkpoint if finalization fails. The artifact inventory excludes itself and includes the intended final workflow manifest bytes; the manifest is written last, and missing/mismatched bundle files mean incomplete evidence. Definition and prototype snapshots accompany each run so an uncommitted source hash still identifies inspectable bytes. Existing logger/CLI/runtime behavior is unchanged.

## Physical integration

The fixed [physical POWER REF runner](WF-01-PHYSICAL.md) supplies the selected host/resource/setup path, stage/RPC/outer deadlines, provenance and source-state checks, serialized captures, failure-safe cleanup policy, checkpoints, and physical reports. It is a separate entry point; ordinary logging stays unchanged. Actual execution results and owner confirmation remain distinct from fake-factory integration tests.
