# REPORT-RECOVERY-01: Saved POWER REF report regeneration

Status: implemented locally. This adds a report-only action to the existing local operator interface. Normal logging, the main CLI, transport, physical runners, measurement timing, and dependency pins are unchanged.

## Operator use

Open the local interface and find **Regenerate saved POWER REF reports** below the run panel. Select a saved capture by its original start time, selected workflows, original outcome, and job ID, then choose **Regenerate PDF & package**. Progress and errors identify this as report regeneration, with links to the regenerated PDF and portable ZIP. Recent history labels report attempts separately from measurement runs.

Eligible sources are individual physical WF-01/WF-02/WF-03 operator jobs and physical or simulated combined POWER REF suites in the configured `--runs-dir`. A source must have a sealed capture inventory, a closed operational worker, and valid native evidence. Missing or failed original reports are supported. Completed and interrupted captures keep their original execution, selection denominator, skipped workflows, readings, zero, equipment facts, and measurement identity. A seal alone is not enough: the existing owning reader validates native hashes and evidence consistency before publication. Failed captures are eligible only if that reader accepts their sealed evidence; unsealed operational checkpoints are not recovered as verified measurements.

No bench configuration, USB resource, meter session, fresh setup attestation, or RF switching is needed for this action. You can launch the interface on an existing run directory without `--power-ref-setup`, `--resource`, or `--bench-python`. Optional reporting/PDF dependencies are still required. Arbitrary filesystem paths, uploaded bundles, guided sweeps, and transmitter fake suites are outside this first interface recovery scope.

## Preservation and failure handling

Each accepted request creates a new job directory with mode `report_recovery`, its original `source_job_id`, and the expected source capture inventory SHA-256. Reports go into the new job's `report/` directory and `report.zip`; existing captures, reports, partial outputs, and later front-panel attestations are not overwritten. Repeated attempts get different IDs and destinations. The regenerated report records current report-producer provenance while retaining original acquisition provenance and run identity. The report worker does not adopt a different operator from the reporting machine's environment.

One operator worker runs at a time. A measurement or report worker blocks a second Start. Regeneration holds the existing source capture lock and validates the source inventory again in the child before and after publishing. A still-running capture, invalid source ID, unsupported job mode, missing seal, symlink capture, changed evidence, or inconsistent metadata is refused. Source and destination paths are server-selected; the browser supplies only a job ID. The existing loopback, Host, session cookie/token, same-origin, bounded JSON, and artifact verification rules apply.

A report error retains the source and failed destination. Select the source and explicitly request another attempt after addressing the reporting issue; there is no automatic retry or reacquisition. Report generation has no measurement to cancel, and the UI does not offer capture cancellation for it. If the service stops, existing ownership rules retain the finishing child lock; startup never restarts measurement or reporting automatically.

An original physical front-panel attestation remains separate. Recovery may run while that attestation is pending, but never records it, clears the original pending state, or authorizes another measurement. Dedicated regenerated-report links remain available alongside the original run's pending confirmation panel. Sealed reports/packages retain their original protocol observations and distinguish later owner observations outside the package.
