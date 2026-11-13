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

## Brand Commitments

Use HP 437B Automation as the project name and retain the existing report styling. Reports remain titled RF Output Power Test, with operator, signed pre-RF zero, and Report Harness provenance.

## Evidence on Hand

See docs/OPEN-WORK.md, docs/VALIDATION.md, docs/workflows/DUT-TEST-PROFILES-V1.md, docs/workflows/TEST-SUITES-V1.md, and docs/workflows/PDF-EXPORT-V1.md. Example profiles and synthetic reports are clearly fictional; no DUT performance claims may be inferred from them.

## Product Principles

Make the next action obvious. Show recorded truth rather than invented results. Preserve native evidence and distinguish test failure, cancellation, and report errors. Keep external transmitter/supply controls and AI automation outside this interface’s scope.
