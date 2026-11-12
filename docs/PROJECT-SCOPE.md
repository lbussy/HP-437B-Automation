# Project scope and development direction

Owner clarification, November 12, 2026. This is the current project direction and supersedes earlier statements that made replacement-meter qualification a prerequisite for software progress or overall Phase 3 completion. Historical procedures and results retain their original dates and evidence limits.

## Product goal

Orchestrate and automate measurement/test processes using the HP/Agilent 437B and its sensor, with agent-assisted analysis and reports about the equipment being tested. The meter/sensor is the measurement system used by those processes. Maintaining its identity, settings, calibration records, and known limitations provides provenance for those results.

Control and CSV logging are implemented foundations. A successful reference readback or five-minute log validates a software interaction; it is not the complete automation/reporting product. The initial supervised reference-bench profile was an incremental test profile, not the boundary of the project's goal.

## Three distinct evidence questions

| Question | Evidence and treatment |
| --- | --- |
| Does the software implement the intended workflow correctly? | Source-backed command sequences, automated tests, failure handling, reproducible analysis, and end-to-end workflow/report checks |
| Can the software perform a particular operation through this adapter/backend on a named host? | Existing scoped Mac/Pi bench records, with additional hardware checks when a new operation actually requires them; retain capability guards until supported |
| What measurement claims does a result support? | Actual meter/sensor identity, applicable calibration information and factors, signal path/settings, units/timing, and known issues; state limits and unknowns instead of inventing accuracy or pass/fail criteria |

The current meter's documented supply discrepancy remains an equipment fact. It must accompany affected measurements and their interpretation. It does not invalidate established software behavior or block workflow, provenance, analysis, reporting, or simulated end-to-end development. Synthetic results must remain explicitly synthetic and cannot establish DUT performance.

Replacing the meter requires recording the new identity and applicable records and checking the software/setup assumptions relevant to its use. That is an equipment onboarding task, not a new instrument-certification project or a blanket requirement to repeat every software/host case. The prepared [replacement procedure](validation/REPLACEMENT-ACCEPTANCE.md) remains available; its previous blanket release-gate status is superseded.

## Next software work

The following breakdown is a development proposal derived from the owner's stated goal. Detailed APIs, report formats, persistence choices, and DUT-specific criteria are not yet decided, and the rows do not claim implementation.

| ID | Workstream | Next concrete result |
| --- | --- | --- |
| WF-01 | Measurement workflow definition and orchestration | Define a representative test of equipment using the meter/sensor: inputs, setup/preconditions, ordered actions/acquisitions, stop/cancel/failure behavior, and outputs. Then implement execution over the existing interface without silently changing logger behavior |
| PROV-01 | Test/run provenance | Define a run record linking the DUT/test intent, workflow/software versions, actual meter/sensor/adapter identity, calibration references, factors/settings/path, known issues, and raw evidence; distinguish supplied, observed, derived, and unknown fields |
| REPORT-01 | Analysis and agent-assisted reporting | Define a report contract and produce a report from an existing or synthetic run: traceable calculations, summaries/plots where useful, failure/incomplete-data treatment, and narrative conclusions tied to evidence. User-defined criteria govern DUT comparisons; no invented thresholds or measurement claims |
| E2E-01 | Automated process acceptance | Reproduce a workflow-to-data-to-analysis-to-report result, exercise cancellation/failures, and preserve evidence links. Use synthetic cases now, existing bench data within its limits, and targeted physical cases when necessary |

The first concrete design is [POWER REF measurement and repeatability](workflows/POWER-REFERENCE-V1.md), with a [worked synthetic report](workflows/examples/POWER-REFERENCE-V1-SYNTHETIC.md). A [synthetic prototype](workflows/WF-01-EXERCISE.md) now exercises the first workflow/report boundary. The [first physical POWER REF workflow](workflows/WF-01-PHYSICAL.md#current-meter-physical-result) also completed on the current Mac/meter with generated report, independent audit, and owner final-state confirmation. [PROV-01 v1](RUN-PROVENANCE.md) now supplies reusable run/DUT/equipment records, evidence checks, history, and WF-01 sidecars. [REPORT-01 v1](REPORTING.md) provides plots, richer reports, and file-based agent analysis; [E2E-01/VAL-01](validation/PIPELINE-ACCEPTANCE.md) accepts that first profile using fresh synthetic and retained evidence. Future workflow/provider capabilities retain separate scopes.

These workstreams can proceed now. A radio or replacement meter is needed only for a particular physical experiment that depends on it. They do not block implementing and testing the software pipeline. Broader recovery, additional instruments, and every guarded command are not automatically required by this scope clarification.

## Existing foundation and change boundary

The interface/logger, named Mac/Pi interaction cases, and [offline tests](validation/OFFLINE-QUALIFICATION-RESULTS.md) remain useful accepted evidence within their recorded scopes. Qualification work is integrated into `devel` at `6bda91d`, with [Python 3.11/3.14 CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43214328205). This direction correction changes documentation and backlog only. It does not change runtime, authorize a hardware operation, enable guarded commands, or establish unattended hardware support.
