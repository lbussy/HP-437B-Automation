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

## Current delivery and remaining scope

Updated November 13, 2026: human-started deterministic reporting is the owner's selected mode. WF-01–WF-03 POWER REF workflows, individual/combined local-interface runs, provenance, readable PDF/portable reports, cancellation and fresh restart, saved-data report regeneration/history/comparison, and optional attributed assessments are implemented. WF-04–WF-06 and shared transmitter/supply controls have synthetic/fake implementations. The [open-work register](OPEN-WORK.md) retains the scoped evidence; these workstreams are no longer proposals awaiting implementation.

No further mandatory POWER REF feature is identified. Actual remaining physical use is the existing guided path with a transmitter and suitable RF path, plus physical setting/frequency/voltage experiments when selected. A supply is needed only for the voltage experiment. Equipment changes require relevant provenance/setup updates, not blanket software requalification. Automatic DUT drivers are optional because human-guided operation exists.

The owner also requested investigation of unattended recovery and broader command support. These are optional extensions to the delivered supervised profile, not new release gates. The [plan](PLAN.md#requested-investigation-boundaries) bounds useful offline work and possible later current-meter trials. It does not authorize fault injection, automatic resumption, guarded commands, or changes to normal logging. AI/provider automation remains deferred. Additional features and extra POWER REF test combinations are not requirements unless selected by the owner.

## Existing foundation and change boundary

The interface/logger, named Mac/Pi interaction cases, and [offline tests](validation/OFFLINE-QUALIFICATION-RESULTS.md) remain useful accepted evidence within their recorded scopes. Qualification work is integrated into `devel` at `6bda91d`, with [Python 3.11/3.14 CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43214328205). This direction correction changes documentation and backlog only. It does not change runtime, authorize a hardware operation, enable guarded commands, or establish unattended hardware support.
