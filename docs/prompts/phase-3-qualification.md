# Phase 3 execution prompt: hardware qualification

Prepared November 11, 2026. Execute this prompt when the user explicitly requests Phase 3 execution. Saving, reviewing, or linking this prompt is document maintenance. This saved prompt awaits execution.

## Objective and completion boundary

Work in `/Users/lbussy/GitHub/HP 437B Automation`. Qualify the implemented Python interface and CSV logger through the actual USBGpib V2 adapter and selected open-source backend on the intended Mac and Raspberry Pi. Produce reproducible, source-backed physical evidence, correct defects within this repository, reconcile capability and host acceptance records, perform adversarial review and reassessment, and commit and push the resulting work to `devel`.

Qualify a declared application profile: explicit resource opening, identification, absolute units and status, serialized TR2/read acquisition, front-panel readback agreement, reversible control and restoration, finite and sustained logging, bounded failure handling and recovery, clean shutdown, and return to local control. Include Mac access and file retrieval for the Pi workflow. Define any additional trigger, status, bus, or calibration operations required by the chosen measurement sequence before testing them.

Phase 3 completion requires passing evidence for every mandatory case in the declared profile on both intended hosts using the replacement meter and actual sensor. Preserve per-host intermediate results. A passing initial-host batch is a completed batch within an in-progress phase. Broader command coverage retains explicit deferred entries and evidence requirements. Full instrument orchestration requires qualification of its additional operations. Keep profile exclusions explicit and maintain any required failing case as a blocker.

## Read and inspect first

Read `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/PLAN.md`, `docs/OPEN-WORK.md`, `docs/RELEASE-CHECKLIST.md`, `docs/EQUIPMENT.md`, `docs/VALIDATION.md`, `docs/SOFTWARE.md`, `docs/PHASE-2-REVIEW.md`, and every document under `docs/inventory/`. Inspect current source, tests, package pins, CI results, branch, working tree, and remote. Record the starting commit and preserve unrelated work and commits.

Use the command and GPIB inventory as the enumeration authority and consult the cited publisher manual pages for consequential commands, effects, limits, and procedures. Preserve publisher originals, original manifests, and calibration imports byte for byte. Keep derived inspection files and scratch material in ignored `tmp/` or `temp/`.

At preparation time, Phase 2 recorded 118 command/syntax variants: 78 implemented/software-tested, including eleven contextual helpers and two polling-dependent procedures; 40 have explicit ambiguity guards. Three bus entries have byte-transfer/framing paths, sixteen are deferred, and one is an instrument exclusion. Reconcile these historical counts with the checkout actually being qualified. A codec, guard test, simulated fixture, or successful CI run establishes its stated software evidence; physical acceptance requires a recorded device run.

## Readiness, decisions, and authorization

Reconcile HP-01, HP-02, DEC-01, and DEC-02 against current user instructions and equipment records. Record adapter arrival/model/firmware, meter and sensor serials, replacement status, applicable calibration records, the first host, and the measurement policy. Use established user choices directly. Ask only for missing information or physical actions that block the next batch, and continue independent preparation while waiting.

The current meter SN 3125U33223 has a documented +5 V discrepancy that the user reports the seller/calibrator considered unacceptable. Associate any explicitly selected interim development run with that identity and discrepancy. Final acceptance uses the replacement's recorded identity and applicable records, with acceptance checks repeated on that unit. Use factors and limits for the sensor actually connected; the recorded sensor SN MY41094127 remains subject to identity verification.

Execution authorizes repository-local preparation, project-local dependency installation, and the bounded communication, reversible configuration, and logging tests specified in the recorded batch plan for the identified setup. Arrange operator assistance for physical connections, front-panel observations, and restoration as needed. Equipment availability, operator confirmations, and existing user authorization determine which physical steps can proceed. Keep purchases, firmware flashing, persistent host/security changes, backend adoption, and changes to RF wiring or source output within explicit user authorization. Explain any additional decision in concrete terms and prepare its reviewable procedure before asking.

Before device I/O, record the signal path, source state, frequency, expected power, sensor limits, attenuation/load, correction factors, and initial instrument settings relevant to the batch. Derive numerical limits from the sensor manual, label/certificate, and actual path. Communication-only checks can use a confirmed prepared no-RF setup. Zeroing, calibration, reference-output activation, table mutation, preset/recall, reset/self-test, and snapshot restoration each require a named procedure and the appropriate setup/authorization. Operate within a documented restoration plan; ambiguous restore bytes remain guarded.

## Qualification plan and finite budget

Create `docs/validation/PHASE-3-PLAN.md` before physical testing. Define stable case IDs, linked C/G/A inventory IDs, host/unit applicability, exact commands or CLI arguments, initial state, expected effects, measurable pass/fail criteria, evidence paths, cleanup, and stop conditions. Establish a verified operator-accessible local-control/recovery procedure before the first resource open because USBTMC initialization may assert REN.

Record finite sample counts, sustained-run duration, interval, operation timeout, maximum failure-injection attempts, and total bench budget. Use the selected DEC-02 policy and explain averaging/range/settling implications. Treat Phase 2 defaults as software defaults until the chosen bench plan adopts them. Select front-panel comparison tolerance and observation timing from display resolution, stability, and averaging before collecting results. This comparison qualifies readback consistency; absolute power accuracy requires its own applicable reference and uncertainty evidence.

Perform a preflight adversarial review of the concrete plan for source errors, unintended output/state changes, missing recovery, unbounded runs, and unsupported capability assumptions. Correct actionable plan defects before their affected physical steps. Mark unavailable prerequisites with their required next action. An execution request can yield a prepared plan and partial evidence while equipment or operator input remains pending; preserve truthful phase status.

## Batch 1: host and transport readiness

Record host model, architecture, OS, Python, released Python package versions, libusb version/backend, USB permissions/driver binding, cable, GPIB address, adapter identity/firmware, resource identifier, and meter/sensor identities. Keep Mac and Pi records separate. Use the existing pinned open-source stack first and explicitly select `@py` USB INSTR access.

Inspect current official released adapter/backend evidence when required to explain an observed failure or propose a change; cite versions, release/source references, and inspection dates. The Phase 2 transport checks exact package versions before opening. Dependency changes require a deliberate versioned code/pin/evidence update and relevant regression checks. Keep external backend/firmware development a separately scoped proposal, and retain proprietary-provider adoption as an explicit user decision.

Verify installation, package origin, help/capability commands, and software tests before opening hardware. Discover only the intended resources, select the actual adapter explicitly, and ensure a single controller/application owns the device. Capture resource opening and raw framing evidence. Retain distinctions among USB transfer completion, message EOI/EOM, ASCII CR/LF, and binary payload boundaries.

## Batch 2: minimal measurement and reversible control

Begin with the documented `*IDN?` candidate and capture exact raw reply, termination, firmware, and observed behavior. Treat a timeout or unexpected reply as evidence requiring controlled recovery before further commands. Exercise alternate spellings only through separately planned A01 cases; preserve guards until evidence and regression tests justify an API change.

Record initial settings by source-backed observation/readback and operator observation where necessary. Exercise RL0 plus LG/LN and TR2/read using the implemented sequence. The logger consumes a setup measurement before SM because status updates after measurement. Verify the 26-character layout, flags, units, and errors against physical captures; retain unexpected layouts for A06 investigation.

Compare raw parsed readings and displayed readings with matching units and correction settings under the preselected stability/tolerance rule. Verify a planned reversible setting change, observe its effect, restore the original setting, and verify restoration. Record how the logger's absolute-unit selection and retained offset, duty, calibration, averaging, and range affect the result. Derive settling observations from the actual setup: TR2's internal completion behavior leaves sensor settling to the measurement policy.

Keep each trigger last in its program string and consume its expected reply before sending further ASCII commands. Incoming program commands can abort unfinished trigger/calibration work. Serial polling, ASCII *STB?, SRQ delivery, GET, ASCII TR1/TR2, CS/*CLS, device clear, interface clear, transfer abort, automatic REN, and explicit local control each retain their own semantics and case evidence.

## Batch 3: logging, failure handling, and restoration

Run the planned short acquisition first, then the finite sustained session once its prerequisites pass. Verify the requested count/duration behavior, setup-reading exclusion, explicit actual units, raw bytes, instrument-error handling, UTC host receipt times, monotonic elapsed time, interval overruns, row completeness, session identity/provenance, final metadata, and clean resource release. Measure achieved timing and invalid/missing readings from the artifacts. Record the range/filter/settling policy that bounds interpretation of those measurements.

Exercise interruption and output-file protection. Plan a bounded timeout/disconnection case with an identified recovery path and operator involvement where required. Prefer controlled communication faults and safe conditions for invalid-reading observations. Preserve sensor limits and the existing RF path throughout testing. Synthetic malformed replies and sentinels remain software evidence when a physical condition cannot be produced within the authorized setup.

After a failed/interrupted transfer, treat device state and the message stream as uncertain. Verify reconciliation and successful subsequent identification/acquisition through the documented recovery procedure before clearing the software uncertainty. Reopening USB or terminating a worker alone establishes neither device idleness nor local restoration. Keep automatic command retry, calibration, reset, and opaque snapshot replay outside recovery unless a specific approved procedure requires them.

Verify settings restoration and actual return to local operation after normal completion and the planned failure cases. Name any manual operator step explicitly. Accept a manual route only for a profile that explicitly permits it; profiles requiring programmatic local restoration or unattended recovery require that actual capability. Record unresolved required serial-poll, clear, local-control, GET, or SRQ gaps as acceptance blockers. Optional unrelated bus gaps retain their deferred coverage entries.

## Batch 4: second host and capability reconciliation

Repeat required profile cases on the other host with its own environment and evidence. For Pi logging, verify Mac login/access, starting and observing a bounded run, and retrieving the completed CSV and sidecar with matching checksums and session identity. Preserve credentials and private network details in local configuration. Describe any process-lifetime or reconnect behavior actually tested before claiming unattended operation.

Account for every inventory ID exactly once in the matrix. Link passing physical statuses to run/case evidence for the actual host, firmware, adapter, backend, and meter. Identify contextual helpers, conditional procedures, documented exclusions, failed cases, untested operations, and deferrals precisely. Source questions A01–A09 close only to the extent established by the recorded evidence. A hardware observation on one version establishes a version-scoped result.

Enabling a previously guarded capability requires sufficient source/physical evidence, typed implementation, meaningful regression tests, and the appropriate physical case. Limit code changes to defects and capability work necessary for the declared qualification profile. Prepare a separately scoped follow-up for broader transport rewrites, external backend patches, firmware work, or destructive ambiguity investigations.

## Evidence and documentation

Keep raw local measurements under ignored `data/` or `output/logs/`. Record exact artifact paths and SHA-256 hashes in local run records. Commit deliberately selected, reviewed evidence summaries under `docs/validation/`, including run/case IDs, tested commit, operator/date/time zone, environment, physical setup, commands, expected/observed outcomes, timing/tolerance rules, errors, recovery, restoration, and remaining limits. Public summaries must support their claims and identify any raw evidence retained locally; include reviewed minimal excerpts where useful. Keep credentials, private chat exports, local tool state, and bulk measurements out of commits.

Create `docs/validation/PHASE-3-REVIEW.md` for findings, corrections, reassessments, acceptance decisions, and residual blockers. Update README, plan/decision register, open work, release checklist, validation guidance, software instructions, and inventory/matrix where the results require it. Use `✅ Complete`, `⏳ In progress`, and `▧ Open`, with stable task/capability IDs. Keep each prose paragraph and prose list item on one physical line, use Oxford commas and proper Markdown headings, and state established behavior directly.

## Adversarial review, corrections, and reassessment

Review the completed batches as an adversarial maintainer, operator, and evidence reviewer. Challenge wrong device/host identity, stale calibration factors, current-meter evidence attributed to the replacement, unsafe signal assumptions, missing setup/restoration, command ordering and aborts, framing/truncation, stale SM, mislabeled units/errors, timing/rate claims, interrupted data loss, uncertain-state reuse, unsupported bus semantics, and unattended-operation claims. Reconcile every acceptance claim with a case, exact tested software, physical evidence, and declared profile.

Record stable P3-R finding IDs, severity, reproduction/evidence, affected claims/cases, correction, verification, and status. Correct actionable repository defects, add meaningful regression coverage, and rerun affected software checks and physical cases within the remaining authorized budget. Cross-cutting fixes invalidate every affected result until rechecked. Record the new tested commit or exact source diff for reruns. Request only the additional setup or budget actually needed when the existing scope is exhausted.

Run an initial assessment and a fresh reassessment after corrections as the minimum. Repeat while material correctness, data integrity, recovery, evidence, or qualification-claim defects remain. Close findings with verification evidence. Finish the review when a complete assessment finds no remaining actionable defects in the delivered work and all residual hardware/external blockers are accurately recorded. Phase completion additionally requires the mandatory acceptance gates above; a clean documentation review alone completes neither host qualification nor a failing case.

## Commit, push, and report

Explicit user execution of this prompt authorizes scoped qualification work and commit/push of its reviewed repository changes, including a truthful partial-result handoff when a prerequisite blocks further work. Saving the prompt leaves that execution authorization pending. Preserve all earlier user constraints and the physical scope established for each batch.

Before committing, inspect the full diff and current remote history, reconcile evidence and statuses, check Markdown links/anchors and structure, run `git diff --check`, verify original artifact checksums and bytes against the starting commit, and run relevant lint/tests/package checks for software changes. Inspect staged paths/content for measurements, credentials, private information, and unrelated changes. Commit only the scoped implementation, selected evidence, and maintained documentation with descriptive messages.

Push normally to the existing origin's `devel` branch. Preserve unrelated remote history; resolve clear conflicts within this work. If delivery requires force-pushing or guessing about concurrent unrelated edits, retain the completed commits and report the precise blocker. Verify remote commit identity and working-tree state. Inspect applicable CI runs and distinguish their software results from physical acceptance.

Report tested hosts and physical setup, software/adapter versions, accepted profile and actual limits, pass/fail/untested/deferred counts with definitions, measured logging behavior, recovery/local-restoration outcomes, adversarial rounds/findings/corrections/reassessment, remaining decisions/blockers, phase/checklist status, evidence links, software/CI results, commit hashes, push result, and final working-tree state. Identify the next concrete batch whenever qualification remains in progress.
