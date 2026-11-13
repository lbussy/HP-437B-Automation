# REF-SUITE-01: Reusable POWER REF suite

Status: implemented and tested offline; [combined current-Mac browser execution passed](../validation/REF-SUITE-20261113.md), including 3/3 workflows, 2,395 valid readings, report/audit, and separate owner final-state confirmation. Existing individual WF-01–WF-03 records retain their original scope. Ordinary logger, instrument, transport, CLI, physical runner source, and dependency pins are unchanged.

## Operator flow

Choose **POWER REF suite** in the local interface. Choose **Simulated reference — no hardware** or an explicitly configured **Current meter**. Select any nonempty subset of WF-01 output/baseline, WF-02 sustained stability, and WF-03 five-cycle repeatability. They always run once each in that order. Optional operator identity is recorded; unknown remains unknown.

One Start launches the selected workflows. Setup and selection lock while active; the page shows the current workflow/native stage and completed-workflow count. Reload reconnects to the existing job and selection rather than starting another run. The final page offers the concise suite PDF and portable ZIP. Detailed child reports remain linked from the suite HTML/appendix and included in the package.

Simulation uses the existing virtual-time WF-01–WF-03 generators over fake instruments/logger captures. It never accepts a physical resource or backend. Synthetic labels and simulated equipment remain explicit throughout reports and packaging. Virtual-time completion does not establish bench timing, source control, or hardware compatibility. The source checkout is required for the existing WF-01 prototype generator; standalone installed-wheel capture is not declared. Saved suite reporting is independent of that capture helper.

## Prepared physical path

Use the existing [POWER REF launch configuration](OPERATOR-POWER-REF-V1.md#enable-the-selected-bench-path): trusted checkout, explicit USB resource, pinned bench interpreter, and equipment/setup JSON. No resource discovery or browser-supplied resource is added. The physical choice is disabled without this configuration.

Before every suite Start, freshly confirm adapter USB on the current Mac, direct sensor input to POWER REF/cable to SENSOR, reference initially off, warm-up, other control applications closed, and operator availability for PRESET/LOCAL recovery. Keep the prepared path/settings unchanged for the suite. All three typically take about fifty minutes; per-runner ceilings total sixty-five minutes, excluding report-only work. Remain available throughout. The existing fixed runner profiles, deadlines, source-control policy, zero/CAL/factor behavior, and native sample counts/timing remain authoritative.

Each child uses the original supervisor and runner. Its sealed native evidence must show completion, reference off, accepted local return, and independent free-run/numeric-display checks before the next workflow starts. The next runner also performs its own native preflight. Initial preparation is a suite-start attestation retained for the declared unchanged setup; it is not relabeled as a fresh operator check between children. Native protocol source-off/local observations remain distinct from an actual front-panel observation.

One worker owns the operator run directory across capture and reporting. The suite capture lock is inherited by the native child, in addition to existing worker/native ownership locks. A parent failure cannot release that child lock and permit false final-state confirmation. Existing native resource locks still apply per runner; this does not add a universal lock excluding unrelated applications across workflow boundaries. The fresh other-applications-closed confirmation remains required.

After Python closes, separately confirm live numeric readings, RMT off, and POWER REF off in the interface. Until supplied, the physical suite remains pending final front-panel confirmation and prevents another operator run. That later supplement binds the root capture inventory; it never rewrites sealed child captures, suite reports, or packages. No front-panel attestation is requested for simulation.

## Cancellation and failure

Cancellation does not mean immediate RF off. In the physical path, the shared cancellation marker is checked by the existing native observer before the next capture/control stage. A WF-02 plateau already in progress can take thirty minutes. Existing healthy cleanup then handles source-off/local return. Cancellation between workflows prevents the next child from starting; a request after all children finished does not retroactively interrupt the completed suite. Simulated generators finish their current virtual workflow before checking the next workflow boundary.

A failed/interrupted child, unverified source-off/local state, failed read, supervisor deadline, invalid evidence, or storage error stops progression. There is no automatic measurement retry, resume, fallback source, or blind cleanup/reopen added by the suite. Existing uncertain-I/O policy and operator recovery apply. Valid failed-child samples remain available in native sealed evidence. An unsealed child/checkpoint is retained under the job's operational `steps/` or `unfinished/` directory; it is not represented as a verified child or silently promoted into the portable package. Reports identify skipped workflows and retain the full requested denominator. Unknown final state remains unknown until reconciled separately.

Reporting begins after native acquisition closes and the suite capture lock releases. A report failure leaves the sealed capture intact. Regenerate into a new output directory without opening any equipment:

```bash
python -m hp437b.reference_suite \
  --bundle output/reports/operator-runs/JOB_ID/capture \
  --output output/reports/reference-suite-report-again
```

Use `--no-plots` if Matplotlib is unavailable. The existing optional PDF dependency is required; no bench dependency upgrade is needed for report generation in a separate environment.

## Capture, report, and package

The versioned `hp437b.reference-suite.v1` capture contains `reference-suite.json`, a root inventory, and original child bundles under `captures/WF-01`, `captures/WF-02`, and `captures/WF-03` as selected/visited. Each child keeps its own run ID and native inventory. The parent binds selected order, mode, resource, equipment/preparation, operator, software identity, child inventory hashes, recomputed summaries, stop reason, and final state. Operational requests/logs and later operator attestations stay outside sealed evidence.

Import revalidates native results/provenance, child mode/equipment/resource, order and unique identities, summary/hash equality, stop progression, final-state consistency, and completion coverage. An incomplete suite cannot become completed by editing its summary. Inventories detect changes; they do not authenticate an operator or equipment.

The one-page **RF Output Power Test** lists the test as **POWER REF suite**, source, operator, time, execution and coverage, each workflow's signed pre-RF zero, mean, and useful result: reading count, endpoint drift, or cycle spread/count. Baselines are not subtracted. Equipment issues, Report Harness, and Record remain traceable. The appendix links full child reports. Acceptance remains **NOT EVALUATED**, because no transmitter limits/decision rule were supplied. Reference-path measurements do not certify the meter or constitute transmitter, calibration, or compliance results.

The existing portable-report verifier supports the suite root and its child reports; the ZIP includes original evidence, summaries, provenance, individual PDFs/native reports, and the suite PDF/HTML. No acquisition occurs when opening, verifying, relocating, or regenerating these artifacts.

## Local orchestration endpoint

The loopback-only, same-origin, session-token-protected `POST /api/reference-suite` accepts exactly `workflows`, `meter_mode`, `operator`, and `prepared`. `meter_mode` is `synthetic` or `physical`. Simulated requests require empty preparation and retain no physical configuration; physical requests require all six fresh setup checks and the launch-configured resource. Existing state, cancellation, artifact delivery, and separate reference-confirmation endpoints are reused. No automatic scheduling or remote endpoint is added.

## Current-Mac cancellation/restart evidence

The [November 13 browser cases](../validation/REF-SUITE-CANCEL-20261113.md) exercised a cancellation request during WF-01's five-minute S40 plateau, healthy stage-boundary cleanup, retained interrupted reports, and stopped WF-02/WF-03 progression. Following owner final-state confirmation, a fresh WF-01-only suite completed and passed capture/report audit; its owner final live-reading/RMT-off/reference-off confirmation was recorded separately through the interface. This does not establish WF-02/WF-03-specific cancellation, forced-fault recovery, Pi-suite behavior, or unattended operation.
