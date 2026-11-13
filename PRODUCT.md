# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Confirmed by the owner: single-user, loopback-only browser interface using the existing Python application and the reports' clean visual style. Use plain HTML/CSS/JavaScript over the Python service; no frontend framework is required.

## Users

A local operator selecting a DUT profile and transmitter workflows, starting a finite suite, observing progress, requesting cancellation, and opening the resulting PDF or portable package.

## Product Purpose

Orchestrate RF-output measurement workflows and produce human-readable, traceable reports about the DUT. The meter/sensor supports the workflow; qualifying the meter is not the product goal.

## Operating Context

The Python logger, fake transmitter/supply controls, profiles, suites, provenance, and PDF/ZIP delivery already exist. Current physical workflows and named Mac/Pi interactions have separate evidence. The original fake-only interface is now extended at the owner’s request with explicitly enabled, supervised current-Mac POWER REF workflows WF-01–WF-03. Physical runs require fresh setup confirmation, stage-boundary cancellation, and separate post-run front-panel confirmation.

## Capabilities and Constraints

- User-initiated runs; no automatic test start on page load.
- One active job at a time. Fake-suite cancellation is between workflows; POWER REF cancellation is before the next capture/control stage, using existing runner cleanup.
- Existing runner/reporting APIs remain authoritative. UI progress is operational information, not measurement evidence.
- PDF and ZIP delivery use existing optional reporting dependencies. Normal logging and base runtime pins remain unchanged.
- No remote service, external assets, AI provider, credential setup, or physical device discovery. Physical mode uses a trusted checkout, selected USB resource, bench interpreter, and retained equipment setup.

## POWER REF suites

POWER REF suite mode groups selected WF-01–WF-03 captures into one explicit start, shared progress, results, PDF, and portable package. Simulation is the default source; the current-meter source becomes available only when configured at service launch and requires fresh setup confirmation. Simulated time is distinct from elapsed bench time. Bench cancellation waits for the current capture stage and existing cleanup; a separate front-panel confirmation remains required after closure.

## Saved POWER REF report recovery

REPORT-RECOVERY-01 regenerates PDF and ZIP reports from sealed individual physical WF-01–WF-03 captures and combined physical or synthetic POWER REF jobs in the configured run directory. Each regeneration creates a separate `report_recovery` attempt with its own UUID and output, preserves original captures, reports, and attestations, and shows progress, errors, and ready download links. It takes no measurements, changes no USB configuration, and neither requires nor clears a pending original front-panel confirmation; normal logging remains unchanged.

## Operator-guided sweeps

The owner authorized frequency, drive-setting, and combined measurement series on November 13, 2026. Support all 17 requested band labels and at least five drive labels; the implemented limits are 32 frequencies and 16 drive labels. Pause for fresh operator label confirmation before every capture. Use the production meter logger with an explicitly configured bench source, retain a simulated path, and expose equivalent local orchestration actions. Labels are declarations, separate from measured power.

## Saved run history and comparison

RUN-HISTORY-01 adds read-only saved history, twenty runs per page, with measurement/report-attempt filters, report links, verified native POWER REF details, and original front-panel attestation bound to the source inventory hash. Compare two to four distinct acquisitions for matching WF-01–WF-03 workflows: signed zero (µW), mean (mW), endpoint change (%), and cycle spread (µW) retain native definitions. Context, profile, resource, mode, and completeness differences remain visible; unknown, different, or partial evidence withholds arithmetic mean changes (µW). Report attempts trace their acquisition source and cannot count as new measurements. This extends the existing interface without new measurements, hardware qualification, or changes to normal logging; see [the workflow contract](docs/workflows/RUN-HISTORY-V1.md).

## Saved POWER REF acceptance assessments

ACCEPT-01 lets the operator supply optional criteria for sealed POWER REF captures through the local interface, with no default DUT limits. Each immutable post-capture assessment records criteria source, optional assessor, criteria/result/source hashes, and the inclusive-no-guard-band rule; coverage gates Pass, Fail, or Not evaluated for mean-power bounds, WF-02 absolute endpoint drift (%), and WF-03 cycle-mean spread (%). A one-page PDF/HTML, decision JSON, and portable ZIP preserve the original measurements, reports, and attestations. History identifies the assessment as derived evidence rather than a new measurement. Examples are illustrative software checks, not DUT specifications; no hardware, new capture, or normal logging behavior changes. See [the acceptance contract](docs/workflows/ACCEPTANCE-V1.md).

## Reusable POWER REF profiles

PROFILE-01 saves immutable named revisions of WF-01–WF-03 selections, an optional operator, and optional attributed acceptance criteria for Internal POWER REF. An explicit profile-started capture freezes the selected revision and automatically publishes a separate assessed PDF/package after the original measurement reports. Matching profiles can also assess saved captures, with selection explicitly recorded as post capture; assessment computation always follows capture. Existing physical-source configuration, fresh setup confirmations, and separate front-panel confirmation still apply. Original evidence, fake DUT profiles, and normal logging remain unchanged; no new hardware run was performed. See [the profile contract](docs/workflows/REFERENCE-TEST-PROFILES-V1.md).

## Brand Commitments

Use HP 437B Automation as the project name and retain the existing report styling. Reports remain titled RF Output Power Test, with operator, signed pre-RF zero, and Report Harness provenance.

## Evidence on Hand

See docs/OPEN-WORK.md, docs/VALIDATION.md, docs/workflows/DUT-TEST-PROFILES-V1.md, docs/workflows/TEST-SUITES-V1.md, and docs/workflows/PDF-EXPORT-V1.md. Example profiles and synthetic reports are clearly fictional; no DUT performance claims may be inferred from them.

## Product Principles

Make the next action obvious. Show recorded truth rather than invented results. Preserve native evidence and distinguish test failure, cancellation, and report errors. Use generic radio terminology. Operator-guided sweeps confirm every point through a shared browser/local-client API; future orchestration can coordinate that boundary. Radio-specific drivers and AI automation remain separate work.
