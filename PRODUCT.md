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

The Python logger, fake transmitter/supply controls, profiles, suites, provenance, and PDF/ZIP delivery already exist. Current physical workflows and named Mac/Pi interactions have separate evidence. This first interface executes fakes only; it provides no physical endpoint or RF controls.

## Capabilities and Constraints

- User-initiated runs; no automatic test start on page load.
- One active suite at a time. Cancellation is cooperative between workflows: the active workflow finishes and verifies RF off/restoration first.
- Existing runner/reporting APIs remain authoritative. UI progress is operational information, not measurement evidence.
- PDF and ZIP delivery use existing optional reporting dependencies. Normal logging and base runtime pins remain unchanged.
- No remote service, external assets, AI provider, credential setup, or physical device discovery.

## Brand Commitments

Use HP 437B Automation as the project name and retain the existing report styling. Reports remain titled RF Output Power Test, with operator, signed pre-RF zero, and Report Harness provenance.

## Evidence on Hand

See docs/OPEN-WORK.md, docs/VALIDATION.md, docs/workflows/DUT-TEST-PROFILES-V1.md, docs/workflows/TEST-SUITES-V1.md, and docs/workflows/PDF-EXPORT-V1.md. Example profiles and synthetic reports are clearly fictional; no DUT performance claims may be inferred from them.

## Product Principles

Make the next action obvious. Show recorded truth rather than invented results. Preserve native evidence and distinguish test failure, cancellation, and report errors. Keep hardware access and AI automation outside this interface's scope.
