# SUITE-01: Human-started fake test suites, v1

Status: implemented locally. Reuses [PROFILE-01](DUT-TEST-PROFILES-V1.md) and the [WF-04–WF-06 shared controls](CONTROLLED-SWEEPS-V1.md). Normal logging, physical runners, dependencies, and existing command defaults remain unchanged. There are no physical endpoints or AI-provider calls.

The suite runs selected transmitter workflows in order, preserves their individual captures/provenance/reports, and produces a compact **RF Output Power Test** summary. Shared fake transmitter, supply, and meter state carries across workflows. A failed control transfer is never followed by a fresh simulated setup or automatic retry.

## Run a suite

Use a reporting environment and a copy of the [fictional example profile](examples/dut-test-profile-v1.json):

```bash
python tools/offline_qa.py --seconds 180 -- python -m hp437b.test_suite run \
  --profile docs/workflows/examples/dut-test-profile-v1.json \
  --operator 'Example operator' \
  --output output/reports/example-suite \
  --report-output output/reports/example-suite-report --no-plots
```

Open `example-suite-report/report.html`. It links to individual workflow reports. Omit `--no-plots` with the optional `reports` extra; plots appear in the individual reports. Omit `--report-output` for capture only.

By default, all workflows present in the profile run in WF-04, WF-05, WF-06 order. `--workflows WF-06 WF-04` selects a distinct subset in that explicit order. Each selected workflow must exist in the profile. Every profile plan, criteria object, fault selector, and adjacent restoration condition is validated before capture output is allocated. Outputs must be new, separate, non-nested directories.

Re-report without the original profile or any acquisition:

```bash
python tools/offline_qa.py --seconds 180 -- python -m hp437b.test_suite report \
  --bundle output/reports/example-suite \
  --output output/reports/example-suite-report-again --no-plots
```

Exit codes: 0 for completed capture without a failed criterion (NOT EVALUATED is allowed), 1 for failed execution or failed criteria, 130 for interrupted capture, and 2 for configuration/storage/publication errors. The `report` command returns 0 when publication succeeds, even when the evidence records a failed or interrupted suite.

## State continuity and failure policy

Only explicit fake profiles are accepted. One in-memory hardware object spans all workflows; each workflow's first point inherits the prior workflow's final frequency, setting, voltage/current-limit, RF state, and meter-factor state. Child context records bind suite ID, ordinal, initial state, and profile. Native meter session IDs and workflow run IDs must remain unique. Virtual timelines are sequential and nonoverlapping, with a 2,700-virtual-second whole-suite ceiling in addition to existing point/workflow budgets. This is not a wall-clock watchdog or achieved host timing claim.

Each workflow must finish with RF verified off and restoration verified before another workflow starts. Adjacent restored voltage/current-limit conditions must be compatible; the suite never silently changes the initial state to accommodate another workflow. The fictional profile template sets WF-06's current-limit/restoration value to **1.5 A** to match the existing WF-04/WF-05 fake restoration condition. Earlier standalone profiles using 2 A remain valid individually but need explicit compatible configuration before joining those workflows. This changes the fictional profile template, not standalone workflow defaults or real equipment settings.

Progression stops after any failed/interrupted workflow, unknown/ON RF state, unverified restoration, or failed supplied acceptance criterion. Later workflows are skipped with no invented measurements. Criteria failure and control/execution failure remain distinct stop reasons. Individual control sessions retain their existing uncertainty/ownership/cleanup rules. There is no retry, reopen, reset, resume, or blind shutdown added by the suite.

A suite PASS requires every selected workflow to complete safely and PASS its supplied criteria. A known failed criterion produces FAIL; otherwise incomplete execution or missing criteria produces NOT EVALUATED. Execution and acceptance are separate: a criterion failing in the final workflow can leave all captures completed while the suite acceptance is FAIL; an earlier criterion failure leaves the remaining workflows skipped and suite execution failed. A completed default example is NOT EVALUATED because it has no supplied limits.

## Cancellation and fake fault exercises

During CLI acquisition, Ctrl-C requests cooperative cancellation at the next workflow boundary. The active finite workflow finishes its existing acquisition/shutdown/restoration before the next is skipped. This is not immediate RF shutdown or hard preemption. API callers can supply a `cancelled` predicate, checked before each workflow. `--stop-before WF-05` exercises the same boundary deterministically, including cancellation before the first workflow. Cancellation after all workflows have already finished does not undo their results.

To exercise an in-workflow fake cancellation/timeout, select a fault explicitly:

```bash
python tools/offline_qa.py --seconds 180 -- python -m hp437b.test_suite run \
  --profile docs/workflows/examples/dut-test-profile-v1.json \
  --fault meter-timeout --fault-workflow WF-05 --fault-point P02 \
  --output output/reports/example-suite-timeout \
  --report-output output/reports/example-suite-timeout-report --no-plots
```

The expected failed capture exits 1 and stops before WF-06. `--fault cancel` exercises native child cancellation. Fault workflow and point must be selected/requested; factor mismatch is limited to WF-05. No fault reaches a device. Abrupt termination or capture-storage failure may leave an unsealed root: diagnostics and completed native children are retained, but no successful suite inventory or summary is asserted. Completed child bundles can still be inspected with their workflow reader. A suite report-storage error preserves the sealed capture; retry publication to a fresh report directory without recapturing.

## Evidence and reports

Capture root schema: `hp437b.test-suite.v1`, mode synthetic. Files include frozen `starting.json`, full `test-profile.json` binding, finalized `suite.json`, nested `captures/WF-04/` etc., and the final atomic `artifacts.json` inventory. Each child remains a controlled-sweep bundle and retains native production logger CSV/session files, control receipts, simulation model, and profile snapshot. Suite context is additive; older profile-free and standalone captures remain readable.

Import revalidates every child, plan/profile/operator join, expected fault request, shared initial/final hardware state, unique identities, sequential timing, failure stopping, and recomputed summary. Hidden/post-failure child evidence and inconsistent summaries are rejected. Hashes detect changed evidence; they authenticate neither the operator nor equipment. Re-reporting uses saved evidence only and never edits source bundles.

Report root includes one-page `report.html` and `report.md`, complete `results.json`, producer `metadata.json`, individual `workflows/WF-04/` reports/provenance/appendices/plots, and a final report inventory. The summary shows DUT identity, operator, time, profile revision, execution/acceptance, stop reason, final shared controls, headline power range/measurement plane and spread or voltage sensitivity where available, each workflow's signed pre-RF zero, and links to details. Missing zero is Not captured, never zero; no baseline subtraction is applied. Footer order remains Equipment, Report Harness, Record. Detailed conditions, points, corrections, and provenance remain in individual reports and source captures.

## Acceptance boundary

Tests cover selection/order, shared state including meter-factor carry, criteria fail-fast, cancellation callbacks and the registered SIGINT handler, child timeout/malformed/shutdown/restoration faults, partial/no-data reports, profile/state/timing/summary corruption, storage failures, report-only recovery, optional plots, escaped supplied identity, and CLI exits. The SIGINT unit test invokes the installed handler; it is not a physical shutdown or operating-system latency qualification. See [validation results](../VALIDATION.md).

This completes fake suite orchestration and reporting. Physical transmitter/supply/observer drivers, independent shutdown qualification, rated fixture/calibration records, workflow-specific hardware execution, and user interfaces remain future work. AI/provider automation remains deferred.
