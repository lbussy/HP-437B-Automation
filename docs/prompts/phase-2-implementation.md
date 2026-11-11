# Phase 2 execution prompt: Python control interface and logging

Prepared November 11, 2026. Execute this prompt when the user explicitly requests Phase 2 execution. Saving, reviewing, or linking the prompt is document maintenance.

## Objective and boundary

Work in `/Users/lbussy/GitHub/HP 437B Automation`. Implement the source-backed Python interface and command-line logger using the completed Phase 1 inventory. Build in coherent batches, beginning with basic power logging, and account for every command/syntax variant and GPIB operation in the existing coverage matrix.

Phase 2 delivers software, meaningful software tests, packaging, usage documentation, and an accurate implementation-coverage record. Physical device interaction and Mac/Pi bench qualification belong to Phase 3. Validate software with scripted transports and protocol fixtures. Preserve physical acceptance statuses for later recorded bench evidence.

Completion requires a working, software-tested basic logger; typed encoding and appropriate parsing for all unambiguous documented capabilities; explicit capability guards for source-ambiguous or transport-unavailable operations; and one-to-one reconciliation with the inventory. Document each deferred capability, its concrete blocker, and the evidence or implementation required to enable it. A guarded placeholder is a deferred capability, rather than implemented command coverage. Report the usable software milestone and remaining coverage separately. If a required basic-logging feature remains incomplete, report Phase 2 as in progress with the precise remaining work.

## Read and inspect first

Read `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/PLAN.md`, `docs/OPEN-WORK.md`, `docs/RELEASE-CHECKLIST.md`, `docs/VALIDATION.md`, and every document under `docs/inventory/`. Inspect current source, tests, dependencies, branch, working tree, and remote before editing. Preserve unrelated changes and commits.

Use `COMMANDS.md` and `GPIB.md` as the reference starting point, and verify consequential syntax and behavior against the cited publisher manual pages. Phase 1 is a reviewed inventory with explicit ambiguities, rather than proof of hardware behavior. Correct source-backed defects found during implementation and carry the corrections through the reference and matrix. Keep publisher originals and their manifests byte-identical.

Review current released adapter/backend evidence and A01–A09 before selecting dependencies. Record exact released versions and reasons for the choice. Distinguish PyVISA from its PyVISA-py backend and USBTMC resources from native GPIB resources. Treat development-only backend features as candidates requiring a separate adoption decision. Retain the user's open-source direction; adopting a proprietary provider requires an explicit user decision.

## Repository and dependency structure

Use a small installable Python package with a `src/` layout, meaningful tests, `pyproject.toml`, and a documented command-line entry point. Select a supported Python baseline from current dependency evidence and record it. Keep environments, downloaded inspection material, scratch files, and generated measurements in ignored locations. Installation of development/test dependencies into a project-local virtual environment is authorized when executing this prompt.

Use a reproducible dependency strategy appropriate to the project, separating runtime and development dependencies. Record third-party licenses and preserve notices for any imported code. Use ordinary package dependencies in preference to vendoring. Build a wheel/source distribution and verify installation and CLI invocation in an isolated local environment.

## Architecture

Separate these responsibilities with a narrow transport contract:

1. Validated command encoding and operation metadata keyed to stable inventory IDs.
2. Raw response capture and typed parsing.
3. Instrument operations and sequencing/state management.
4. PyVISA USBTMC transport, explicit backend selection, deadlines, and capability reporting.
5. Logging/session lifecycle and a command-line interface.

Make software tests independent of a connected device. Constructing an object, displaying help, or importing the package must remain free of device I/O. Opening a resource is an explicit user action. Keep the initial interface command-line based and focused on the instrument and logger.

## Batch 1: basic measurement and logging

Implement and software-test:

- Resource selection and explicit open/close with configurable finite timeouts.
- Identification using a documented candidate spelling; preserve raw replies and report unresolved alias differences precisely.
- Explicit units and relevant measurement configuration, with parameter validation.
- Ordinary measurement reads and TR2-based acquisition with the trigger last in its program string.
- Numeric measurement parsing, including the `9.00XXE+40` error sentinel, exceptional/malformed replies, and units determined from known configuration.
- The 26-character SM parser and relevant status/error types, preserving raw content and handling reserved fields explicitly.
- Timestamped CSV output with clear fields, units, invalid/error indications, and provenance sufficient to associate readings with a session.
- Clean completion, interruption, timeout, partial-file handling, and resource release.

Define a coherent initial CSV schema and explain each field. Distinguish host acquisition time from instrument measurement time. Use a monotonic clock for scheduling/deadlines and an explicitly zoned wall clock for recorded timestamps. Document interval overruns and finite-run behavior. Expose unsettled product choices such as interval, duration/count, output path, and units as explicit options or documented defaults. Keep hardware acceptance decisions open until the user selects the actual host/setup.

Retain raw evidence sufficient to diagnose parsing errors without silently treating instrument errors as power values. Protect existing output files from accidental overwrite. Describe whether raw data lives in CSV fields or a separate session record and keep that choice consistent.

## Batch 2: remaining documented commands

Implement unambiguous configuration, range/filter, correction, relative mode, limits, display, status/mask, trigger-policy, storage/recall, sensor-table, and learn/restore capabilities using the inventory as the enumeration source.

For each supported operation:

- Validate values, units, numeric finiteness, framing, and relevant prerequisites before transport writes.
- Expose semantic operations with explicit parameters; retain inventory traceability for aliases and syntax helpers.
- Define whether it writes, selects output, reads a response, or begins an operation whose completion requires a later action.
- Preserve ASCII versus binary boundaries. Keep learn snapshots opaque and exact-length, with source-supported prefix and completion semantics.
- Encode only source-backed syntax. Handle unresolved semantics through a specific unavailable/ambiguous capability result that identifies its issue and performs zero I/O.
- Provide deliberate APIs for state-changing operations such as zero, calibration, reference-output activation, table edits/clear, snapshot restore, and configuration recall. Require an explicit call and the documented setup prerequisites; expose their effects clearly.

Application startup, discovery, and ordinary logging must issue only the commands required by their documented user-selected behavior. Calibration, zeroing, resets, table mutation, reference output, and stored-state restoration require explicit operations. Keep a low-level raw diagnostic path, if useful, clearly separate from typed capability guarantees; raw access does not close a coverage gap.

Apply whole-operation serialization where needed so concurrent callers cannot interleave writes with binary transfers, table editing, or pending trigger/calibration results. Avoid generic automatic retries of commands whose effects may already have occurred. Track uncertain state after interrupted operations and require an explicit recovery path.

## Batch 3: bus operations and transport limitations

Map every GPIB inventory ID to an implemented operation, documented instrument exclusion, or explicit deferred capability. Support checks must reflect the selected resource type, backend/version evidence, and available adapter capabilities; a method name or request constant alone establishes insufficient evidence.

Address the known gaps in released PyVISA-py 0.8.1 for serial polling, explicit remote/local control, bus triggering, clear, and event handling. Recheck current releases before deciding the implementation. Prefer supported released open-source paths. Document a gap and fail clearly when required functionality is unavailable. Treat source changes to external backend/firmware projects as a separately scoped proposal rather than expanding this implementation into an unbounded compatibility project.

Keep these semantic distinctions intact:

- ASCII TR1/TR2 versus bus GET and its GT policy.
- ASCII *STB? versus serial polling and its clearing behavior.
- Status polling versus SRQ event delivery.
- Device clear versus CS/*CLS, interface clear, and USB transfer abort.
- Automatic REN assertion versus explicit local restoration and lockout control.
- Host read termination versus device EOI/message boundaries.

The 437B can abort an unfinished trigger or calibration upon receiving an incoming program command. Await the expected measurement/read completion or use a supported serial-poll route; keep ASCII status queries out of that pending interval. Design timeout/recovery and shutdown around that constraint. A successful USB write alone establishes neither completed calibration nor settled power.

## Software verification

Write meaningful tests against independently specified behavior and source-derived fixtures. Test actual emitted bytes and complete operation sequences, rather than generating expected values from the same encoder under test.

Cover at least:

- Legal parameter boundaries and invalid inputs, including NaN/infinity and text injection into labels/messages.
- ASCII numeric, status, error, and identification parsing; truncated, malformed, and unexpected responses.
- Binary snapshots containing CR/LF and exact-length handling.
- Command ordering, deferred reads, trigger/calibration abort avoidance, and incompatible concurrent operations.
- Unsupported/ambiguous capability rejection before I/O.
- Backend failures, bounded deadlines, disconnection, cancellation, and uncertain-state recovery.
- Logger timestamps, scheduling overruns, error rows, output-file protection, interruption, and completed/partial session records.
- CLI parsing/help, package installation, dependency selection, and clean shutdown.

Scripted transports test software behavior and expected conversations. Name fixtures and reports so simulated results remain distinguishable from physical observations. Run appropriate formatting, lint/type checks, tests, documentation checks, and packaging checks. Add lightweight CI for reproducible software checks where appropriate to the chosen dependency strategy; keep CI independent of instruments and credentials.

Update coverage with separate implementation, software-test, Mac bench, and Pi bench fields. Qualify software-test claims by the tests actually run and the local/CI environment observed. Keep all Phase 3 statuses tied to real recorded bench evidence. Preserve the current meter's known supply discrepancy and replacement requirements from the equipment records.

## Documentation and completion reconciliation

Document installation on the intended Mac/Pi environments, backend prerequisites, CLI examples, supported capabilities, unresolved source questions, recovery behavior, and expected output. Label untested platform instructions as setup guidance awaiting qualification. Choose APIs and defaults consistently, and explain consequential choices in the plan/decision register.

Reconcile every inventory ID exactly once to implementation evidence or a named exclusion/deferred capability. Test command/syntax aliases and contextual encoders according to their actual meaning. Guard ambiguous reset/self-test, sensor-label framing, legacy masks, and table traversal until adequate evidence resolves them. Keep basic logging the first usable milestone while tracking complete coverage separately.

Use `✅ Complete`, `⏳ In progress`, and `▧ Open` in task/phase lists. Retain stable task and capability IDs. Update the README, plan, open-work register, release checklist, coverage matrix, and validation guidance to agree with final software scope. Add a Phase 2 implementation/review record with dependency versions, checks, decisions, deferred coverage, and the first recommended Phase 3 batch.

Write direct prose around established behavior and intended actions. Use Oxford commas, proper Markdown headings, and source-backed claims. Preserve the distinction between user requirements, implementation choices, software observations, and physical qualification.

## Adversarial review, corrections, and reassessment

Review the completed implementation as an adversarial maintainer and operator. Challenge:

- Missing capabilities or matrix entries, unsupported aliases, and invented syntax/semantics.
- Range, unit, precision, encoding, and source-citation errors.
- Silent error-sentinel acceptance or misleading output units/timestamps.
- Binary truncation, termination errors, and corrupted snapshot/table boundaries.
- Commands interleaved into unfinished operations, unintended reference/calibration/storage changes, and unsafe automatic retry/restore behavior.
- API/backend capability claims exceeding released implementation evidence.
- Tests that mirror implementation, bypass real sequencing, or misrepresent simulation as qualification.
- Unbounded waits, cancellation leaks, output-file loss, uncertain-state reuse, packaging/installation defects, and platform assumptions.
- Documentation/status mismatches, private information, changed publisher originals, and scope expansion.

Record findings with stable IDs, severity, reproduction/evidence, and concrete corrections. Fix actionable defects, add or adjust meaningful regression coverage where justified, rerun affected checks, and close findings with evidence. Run a fresh adversarial assessment after corrections.

Use an initial review plus reassessment after correction as the minimum. Repeat for material defects affecting correctness, operation ordering, data integrity, coverage, reproducibility, or claims. Finish when a complete assessment finds no remaining actionable Phase 2 defects. Questions requiring hardware or external evidence remain precise deferred items. If such a question blocks required basic logging or an acceptance criterion, report Phase 2 as in progress rather than relabeling the gap as complete.

## Commit, push, and report

This prompt authorizes the Phase 2 implementation work, its relevant software checks, and commit/push when the user explicitly requests execution.

Before committing, inspect the full diff, reconcile the matrix and checklist, verify local links/anchors and Markdown structure, run `git diff --check`, and verify source artifacts against their original checksums and starting committed bytes. Preserve unrelated work and keep temporary data, credentials, local tool state, and generated measurements out of Git.

Stage only Phase 2 changes and source-backed documentation corrections. Commit with descriptive messages and push the completed work to the existing remote's `devel` branch using a normal push. Inspect current remote history first. Resolve clear conflicts confined to this work; preserve unrelated history. If delivery would require force-pushing, altering unrelated work, or guessing at ambiguous concurrent edits, retain the completed changes and report the precise push blocker and required decision.

Then report:

- Implemented API, CLI, logging behavior, and usage examples, with links.
- Inventory coverage counts: implemented, software-tested, excluded, and deferred, with exact definitions.
- Dependency/backend choices and unresolved transport/source questions.
- Adversarial review rounds, findings, corrections, and stopping-rule result.
- Checks actually run, environment, results, and evidence limits.
- Phase/checklist status and the next Phase 3 qualification batch.
- Commit hashes, branch, push result, and final working-tree state.
