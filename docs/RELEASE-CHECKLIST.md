# Release checklist

Updated: 2026-11-12. ✅ Complete, ⏳ In progress, and ▧ Open/deferred. The [project scope](PROJECT-SCOPE.md) reflects the owner's clarification: deliver automated measurement/test workflows and agent-assisted reports using the meter/sensor. Equipment provenance supports those results. Replacement-meter qualification is not a software-project gate.

| Item | Status | Result or next action |
| --- | --- | --- |
| Repository setup | ✅ Complete | Manuals, source references, licensing, and project structure retained |
| Phase 1: Inventory | ✅ Complete | [Inventory](inventory/README.md): 118 command/syntax variants, 50 families, and 20 bus entries; source ambiguities remain explicit |
| Phase 2: Interface/logger foundation | ✅ Complete | [Software](SOFTWARE.md): 78 encodable/software-tested variants, including contextual helpers/procedures, and 40 guarded variants; this foundation does not complete the orchestration/reporting product |
| Phase 3: Application/workflow acceptance | ⏳ In progress | Validate required software interactions and the workflow-to-report pipeline; see the [current direction](PROJECT-SCOPE.md#next-software-work) |
| Existing Mac/Pi interaction profile | ✅ Complete | Named identification, readback/control, finite/sustained logging, local restoration, interruption, and failed-read shutdown cases are recorded; broader capabilities are not implied |
| Adapter and initial logging policy | ✅ Complete | [Adapter](validation/ADAPTER-IDENTIFICATION.md) recorded; [initial policy](validation/MEASUREMENT-POLICY.md) adopted as a test profile |
| Offline software campaign | ✅ Complete | [Results](validation/OFFLINE-QUALIFICATION-RESULTS.md): 421 tests with stress enabled, clean installs, parameter/parser/logger/process checks, and three reviews |
| Qualification branch integration | ✅ Complete | `devel` at `6bda91d`, pushed; [CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43214328205) on Python 3.11 and 3.14; normal logging/runtime unchanged |
| WF-01: First fixed workflow | ✅ Complete | [Current-Mac physical POWER REF workflow](workflows/WF-01-PHYSICAL.md#current-meter-physical-result) and synthetic scenarios exercised; 299 sustained/308 total valid physical rows, report/audit, and owner final-state confirmation |
| PROV-01: Run/DUT/equipment provenance | ✅ Complete (v1) | [Versioned models and WF-01 integration](RUN-PROVENANCE.md), evidence-bound facts, history, and additive exports; original measurement files and normal logging unchanged; implementation pushed with [Python 3.11/3.14 CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43229676050) |
| REPORT-01: Analysis and agent-assisted reports | ✅ Complete (v1) | [Saved-run reporting](REPORTING.md): verified WF-01/PROV-01 inputs, PNG/SVG plots, HTML/Markdown/JSON reports, and file-based attributed agent drafts; nine retained scenarios exercised. External provider automation is a follow-up |
| E2E-01 / VAL-01: End-to-end software acceptance | ⏳ In progress | First fixed current-Mac physical and synthetic workflow/report paths passed; broader application acceptance remains open |
| HP-01: Equipment exchange/onboarding | ▧ Equipment follow-up | Record replacement identity/records and check relevant setup assumptions when used; does not block the software work above |
| Wider bus capabilities and unattended hardware recovery | ▧ Deferred | Enable only when a selected workflow requires them and appropriate evidence supports them |

The completed [pre-arrival review](validation/PRE-ARRIVAL-REVIEW.md), [replacement procedure](validation/REPLACEMENT-ACCEPTANCE.md), and earlier Phase 3 records remain useful history/prepared work. Their previous statements that all software progress or Phase 3 completion must wait for the replacement are superseded by the owner clarification. Preserve the current meter's known discrepancy in measurement provenance; do not convert a readback test into an absolute-accuracy claim.

The [open-work register](OPEN-WORK.md) retains detailed foundation results and owns task status. Broader end-to-end workflow/provenance/report acceptance is the next software step; no replacement arrival or radio is required for that development.
