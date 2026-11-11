# Phase 1 execution prompt: command and GPIB inventory

Prepared November 11, 2026. Execute this prompt only when the user explicitly requests Phase 1 execution. Saving, reviewing, or linking this file is document maintenance.

## Objective and completion boundary

You are working in `/Users/lbussy/GitHub/HP 437B Automation`.

Complete Phase 1: inventory every documented HP 437B remote command and required GPIB operation, including parameters, responses, prerequisites, and effects. Produce a source-backed reference and coverage matrix to guide Python implementation and Mac/Pi hardware qualification.

Phase 1 is complete when every manual-documented command variant and relevant GPIB operation has a source-verified inventory entry, the coverage matrix accounts for each entry, and adversarial review has resolved actionable documentation defects. Record genuine source ambiguities with precise evidence and follow-up requirements. Adapter/backend uncertainties remain explicitly tracked for implementation and qualification.

Phase 1 covers documentation and read-only source investigation. Implementation belongs to Phase 2; physical qualification belongs to Phase 3. Use local rendering/OCR tools as needed for documentation. Keep device interaction, calibration changes, reference-output activation, RF transmission, and application/dependency installation for their separately authorized execution contexts.

## Repository preparation

Read `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/PLAN.md`, `docs/OPEN-WORK.md`, `docs/RELEASE-CHECKLIST.md`, `docs/EQUIPMENT.md`, and `docs/VALIDATION.md` before beginning. Inspect the working tree, branch, and remote. Preserve unrelated work and reconcile the inventory with current decisions.

Record existing changes before editing. Plan a Phase 1-only commit. Use the existing repository and remote; the delivery target is `devel`.

## Primary evidence

Use the unmodified publisher manuals in `output/pdf/hp-437b-8482a/`:

- `HP-437B-Operating-Manual-00437-90047.pdf`
- `HP-437B-Service-Manual-00437-90076.pdf`
- `HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf`

Read the operating manual's complete remote-operation material, command summaries, detailed function descriptions, programming examples, status/error descriptions, and relevant appendices. Cross-check summaries against detailed entries and examples. Consult the service and sensor manuals for prerequisites, limitations, calibration effects, and hardware behavior. Clearly label command scope, including any service-only functions.

Render or OCR scanned pages as needed. Keep working extractions, scripts, and previews in ignored `tmp/` or `temp/`. Visually verify consequential syntax, symbols, numeric limits, and table entries against the original pages. Preserve publisher PDFs and original manifests byte for byte.

Cite manual part number, section or table, printed page, and one-based PDF page for every technical entry. Distinguish printed pagination from PDF pagination. Use repository-relative PDF links and page fragments where practical. Prefer paraphrased technical descriptions and precise citations over reproducing manual passages.

Use current primary adapter/backend documentation for readily available transport evidence. Record source URLs, retrieval dates, and applicable versions or commit identifiers. Separate manual-documented behavior, adapter claims, backend implementation evidence, and physical observations.

## Deliverables

Create maintainable documents under `docs/`, with links from the README, plan, open-work register, release checklist, and validation plan as appropriate:

1. Complete instrument command reference.
2. Separate GPIB operation reference.
3. Coverage matrix with stable capability identifiers.
4. Explicit unresolved-ambiguity register with required evidence.
5. Phase 1 completion/review record and recommended first implementation batch.

Choose filenames and organization that fit the repository. Keep syntax and semantics authoritative in the references; let the matrix link to them. Maintain one status record per task and summarize it consistently in the checklist.

## Instrument command inventory

Enumerate every documented remote command and variant, including queries, remote-only functions, prefixes, terminators, aliases, and documented compatibility or service functions. Establish exact scope from the manuals.

For each command or variant, record:

- Stable identifier, functional category, exact spelling, capitalization rules, and syntax.
- Parameters, types, units, legal values/ranges, defaults, and numeric formatting rules.
- Terminators, separators, command-combination rules, and applicable shared syntax.
- Operation type: write, query, trigger, output selection, or other documented behavior.
- Output behavior: direct response, queued output, changed subsequent-read behavior, or command completion without output.
- Response syntax, units, prefixes, numeric representation, termination, and exceptional values.
- Prerequisites: instrument modes, sensor requirements, physical connections, and setup conditions.
- Effects on measurement state, display, triggering, averaging, range, correction factors, reference output, stored configurations, sensor tables, calibration data, and other affected state.
- Persistence across subsequent commands, local/remote transitions, preset, device clear, and power cycling, where documented.
- Completion, settling, status indications, errors, and service-request interactions.
- Minimal manual-supported usage example where useful.
- Exact source references and remaining uncertainties.

Document shared rules once and link applicable entries to them. Distinguish reading the latest measurement from initiating a fresh measurement. Include documented physical-only functions and remote-control exclusions to define the automation boundary. Label unknown behavior as unknown and assign a follow-up question.

## GPIB operation inventory

Catalog supported, required, or relevant interface operations separately from instrument command strings. Cover addressing, reads/writes, end-of-message handling, remote/local control, clear, triggering, polling, and service requests according to the instrument's interface declarations and detailed documentation.

For each operation, record:

- Stable identifier and exact bus operation, message, or signal.
- Controller/listener/talker roles, addressing, and prerequisites.
- Instrument response and effects on pending input, output, or measurements.
- Relationships to instrument commands and trigger settings.
- Completion, status, and recovery behavior.
- Corresponding PyVISA API or underlying VISA operation, when established.
- Available evidence that normal USBGpib V2 USBTMC firmware exposes the operation.
- Available evidence of backend support, with the applicable released version.
- Configuration requirements, test needs, source references, and uncertainties.

Distinguish instrument-trigger commands, Group Execute Trigger, and USBTMC/VISA triggering. Distinguish serial polling, reading an instrument status response, and service-request event delivery.

Support claims must cite corresponding implementation or documentation. Label development-branch capabilities separately from released capabilities. Record unsupported and uncertain operations explicitly.

## Bound transport research

Complete instrument/bus coverage is the Phase 1 acceptance criterion. Use primary adapter documentation and readily available backend documentation or focused source inspection to map evidence. When support remains unclear after that focused check, record the exact operation, evidence inspected, and Phase 2 investigation needed, then continue the inventory.

Deep firmware tracing, backend patches, exhaustive VISA conformance assessment, dependency experiments, and device tests belong to later phases. Backend uncertainty alone does not block completion of an accurate inventory.

## Coverage matrix and status model

Assign a stable capability identifier to every command variant and bus operation. Track:

- Capability/category and authoritative reference link.
- Manual verification status and evidence.
- Proposed Python exposure or API-design question.
- Adapter evidence and its source/version.
- Backend evidence and its source/released version.
- Implementation status.
- Software-test status.
- Mac bench-qualification status.
- Pi bench-qualification status.
- Required test conditions, expected observable result, and linked issues.

Use separate fields for manual verification, implementation, software tests, and bench qualification. Document inspection can establish an accurate inventory; physical evidence establishes hardware behavior. Keep adapter/backend evidence labels distinct: documented claim, source-inspected support, uncertain, unsupported, and bench-verified. Define each label.

Use the project status symbols consistently: `✅` complete, `⏳` in progress, and `▧` not started. Set each field from actual evidence. Retain traceability to the specific meter, sensor, firmware, host, OS, backend, and package versions for any existing observations.

## Reconciliation and writing

Cross-check completeness against command summaries, detailed entries, examples, status tables, and interface capability declarations. Explain the counting convention for families, variants, aliases, queries, and bus operations. Record applicability for every enumerated interface operation, including documented exclusions.

Reconcile the plan and checklist with three phases:

1. Inventory.
2. Implement.
3. Qualify.

Retain basic power logging as the proposed first implementation milestone and complete documented command coverage as the broader target. Preserve PyVISA-py's provisional status. Account for current equipment/replacement context from the live records when identifying future qualification needs.

Write around established facts and intended actions. Use Oxford commas, proper Markdown headings, and readable tables. Support compatibility claims with evidence specific to the claim. Keep proposals, source findings, and measured results clearly identifiable.

## Adversarial review and iteration

Perform an adversarial review of the completed inventory from the perspective of an implementer relying on it. Challenge:

- Missing command variants, queries, prefixes, terminators, aliases, and remote-only functions.
- Syntax incorrectly borrowed from other HP models or SCPI.
- OCR mistakes, numeric ranges, symbols, citations, and page mappings.
- Response expectations and distinctions among triggering, requesting output, and reading output.
- State dependencies, persistence, completion, settling, and physical prerequisites.
- Separation of command strings, bus operations, and API abstractions.
- Adapter/backend support claims and released-versus-development distinctions.
- Calibration, stored-data, and reference-output effects.
- Status claims exceeding evidence.
- Counting discrepancies, duplicated authority, broken links, formatting, and inconsistent terminology.

Record each finding with a stable issue identifier, severity, evidence, and concrete resolution. Correct actionable defects, verify the correction, and close each resolved finding with evidence. Run a fresh adversarial assessment after corrections.

The stopping rule is an initial review plus a fresh assessment after correction, with further rounds for material defects affecting completeness, syntax, semantics, traceability, or scope. Finish once a full assessment identifies no remaining actionable Phase 1 documentation defects. If progress on an ambiguity requires external evidence or hardware, record that dependency and carry it forward. If external evidence prevents source verification of a required entry, report the inventory as incomplete and identify the precise gap. Avoid repeated unchanged assessments of externally blocked questions.

## Validation and delivery

Before committing:

- Reconcile every documented command variant and applicable bus operation with the inventory and matrix.
- Verify source references, local links, anchors, Markdown formatting, and `git diff --check`.
- Run appropriate available documentation checks.
- Verify publisher originals and original manifests remain unchanged.
- Review the complete diff for scope, private data, temporary artifacts, and evidence quality.
- Confirm the plan, backlog, checklist, and validation references agree.

Commit completed Phase 1 documentation with a descriptive message and push to the existing repository's `devel` branch. This execution prompt authorizes that Phase 1 commit and push when execution is explicitly requested.

Stage only Phase 1 files and relevant edits. Preserve unrelated changes and commits. Inspect current remote state before delivery and use a normal push. Resolve conflicts confined to Phase 1 where the resolution is clear. If delivery would require altering unrelated work/history, force-pushing, or resolving an ambiguous concurrent edit, preserve the completed work and report the blocked push with its concrete cause and required decision. Accurately distinguish completion of inventory work from completion of delivery.

Then report:

- Deliverables, with links.
- Command-family, command-variant, and GPIB-operation counts, with the counting convention.
- Findings affecting implementation and backend choice.
- Remaining ambiguities, external dependencies, and decisions.
- Adversarial-review rounds, findings, resolutions, and stopping-rule outcome.
- Validation performed and evidence limits.
- Commit hash, branch, push result, and final working-tree state.
- Recommended first Phase 2 implementation batch.
