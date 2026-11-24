# Implementation prompt: 56-point Pico Si5351 physical sweep

Implement the HP-side work defined by the [Si5351 physical sweep plan](SI5351-PHYSICAL-SWEEP-PLAN.md) in **HP 437B Automation only**. Deliver a human-started, bounded Si5351 sweep through the existing operator/client, worker, HP 437B acquisition, sealed-evidence, and reporting paths. The paired WsprryPico implementation belongs to a separate project and is an external contract dependency.

This prompt requests implementation and RF-free validation. It does not authorize hardware access, firmware installation, instrument adjustment, RF transmission, live review, a conducted test, commit, or push.

## 1. Read, preserve, and stay within scope

Read `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/PLAN.md`, `docs/OPEN-WORK.md`, `docs/VALIDATION.md`, the linked focused plan, and the relevant current source before editing. Inspect branch and staged, unstaged, and untracked status; preserve existing work. Do not discard, stage, commit, push, or publish changes, switch branches, or change remotes.

Use the focused plan and this prompt for the Si5351 campaign. Broader Pi/GPIO plans are context, not authority to implement extra profiles, reduce the matrix, or change the selected sampling. If a material conflict remains after inspecting owning sources, report it rather than silently choosing a different scope.

Reuse `sweep_matrix.py`, `pico_tone.py`, `pico_sweep.py`, `pico_pilot.py`, `live_sweep_review.py`, `live_sweep_window.py`, `guided_sweep.py`, `guided_report.py`, `sensor_correction.py`, `report_delivery.py`, and the existing client/operator/worker boundaries. Add source-specific code or small shared helpers where necessary; do not redesign the framework, report system, or operator interface.

Exclude WsprryPico/WsprryPi edits, firmware builds/deployment, Pi transmitter/gateway work, new transport/authentication systems, extra bands/drives/boards/sensors, engineering qualification overrides, automatic continuation/recovery, new acceptance criteria, fixture-loss or uncertainty models, persistent meter tables, and unrelated backlog. Read the paired Pico's delivered contracts and fixtures as inputs without modifying that project or contacting its hardware.

## 2. Exact requested campaign

Create a distinct versioned **physical Si5351** capture schema and source-specific matrix/plan builder. Use all 14 rows below at each drive, in order **2, 4, 6, 8 mA**, completing the frequency table before advancing drive. Assign deterministic P001–P056 IDs. Require 56 unique requested points.

| Band | Dial Hz | Absolute carrier Hz |
| --- | ---: | ---: |
| 2200 m | 136000 | 137500 |
| 630 m | 474200 | 475700 |
| 160 m | 1836600 | 1838100 |
| 80 m | 3568600 | 3570100 |
| 60 m | 5364700 | 5366200 |
| 40 m | 7038600 | 7040100 |
| 30 m | 10138700 | 10140200 |
| 20 m | 14095600 | 14097100 |
| 17 m | 18104600 | 18106100 |
| 15 m | 21094600 | 21096100 |
| 12 m | 24924600 | 24926100 |
| 10 m | 28124600 | 28126100 |
| 6 m | 50293000 | 50294500 |
| 2 m | 144489000 | 144490500 |

Keep frequencies as integer Hz and preserve large wire nHz/ns/revision values exactly. Send the absolute carrier once, with no second offset, random placement, WSPR dial conversion, or saved-frequency substitution.

Retain exactly **two readings per measured point**, using the existing **one-second logger interval**: 112 retained readings for a fully measured run. Preserve actual timestamps rather than promising one-second completion spacing. Setup, RF-off baseline, and the existing two-or-three settling readings remain separate from the retained sample count. Do not silently reduce sampling or relax settling.

Do not add 2 m to the shared `DIALS` dictionary or change existing schema meanings. Preserve the 52-point GP2 matrix, its IDs, existing simulation behavior, manual operation, reference workflows, and saved-capture loading/re-reporting.

Use these campaign inputs, not hardcoded global defaults:

- RF output: `QRP Labs Si5351A Synthesizer and 25MHz TCXO module`.
- Controller: Pico C through the configured `wspr5` USB host; require a trusted explicit member/USB identity and rediscover the boot for future authorized operations.
- Source: explicitly selected Si5351 transmit clock and 25 MHz external reference, matching the operator-confirmed fixture.
- Fixture: selected clock output through the coax adapter directly into the 8482A, without an amplifier or attenuator chain.
- Meter: HP 437B SN 3125U22346. Sensor: 8482A SN MY41094127.
- Operator: Lee Bussy [AA0NT]. POWER REF off. Acceptance assessment: N/A.

## 3. Contract dependency: use delivered evidence, not assumptions

Obtain the paired project's delivered Control/1 schema, source revision, and RF-free request/response fixtures. Record their reproducible version/hash association in HP-side fixture metadata. A GP2-only handoff is insufficient. Do not freeze a previously observed boot, invent Si5351 fields, or declare an arbitrary revision sufficient for readiness.

Required contract behavior:

- Read-only discovery/admission for the exact Si5351 engine, selected clock, reference configuration, four drives, and 14 carriers. Include 5366200, 7040100, and 144490500 Hz explicitly.
- Authoritative saved and active settings and revisions, scoped drive mutation, restart/activation semantics, storage/fault state, and supported restoration of initial settings, including absence/unset values.
- Review, finite Start, exact-request/job Status, and exact-job Stop, with conditional revisions, unique request IDs, device/boot/authority-generation binding, and accepted source/settings/duration.
- Realization/quantization bounds, running observations, effective time limits, terminal outcomes, confirmed clock disable, and current RF inactivity.
- Lost-reply/reboot/receipt-expiry/authority-change/I2C-error behavior and conservative timing semantics.

GPIO pin/pad evidence is not Si5351 clock/drive evidence. A saved drive is not proof of an active drive. A terminal software state or local timer expiry is not proof of hardware clock disable after I2C failure.

If the final dependency is unavailable or incompatible, continue independent matrix/schema/report/test work, keep physical Si5351 unavailable, and report the exact missing contract elements. Do not manufacture a wire implementation from fakes, bypass guards, copy unrelated firmware into this repository, or report full completion. Reconcile fixture/version differences before declaring integration ready. No live probing is permitted during this implementation task.

If the delivered contract changes shared Test Tone requests or receipts, verify GP2 against the applicable delivered fixtures too. Bind accepted wire shapes to an explicitly verified contract and reject mismatches before mutation. Preserve GP2 behavior and sealed capture compatibility.

## 4. Implement the bounded HP path

### Matrix, schema, and adapter

Add explicit physical-Si5351 dispatch through plan validation, source selection, capture/import, reporting, and package verification. Define typed source context for engine, clock, reference, saved/active drive, and relevant revisions. Validate required fields strictly; do not overload GP2 fields or accept a loose unvalidated metadata dictionary.

Add a narrow Si5351 adapter beside `PicoTone`, sharing the existing authenticated `UsbLink` framing. The USB host transports direct Pico Control/1 requests; it is not a Pi RF-control adapter. Implement snapshot, admission, scoped drive change/restart/readback, finite Start, running observations, and exact-job Stop against the delivered paired contract. Preserve exact identities and conditional revisions.

Never reconstruct full configuration from redacted GET data, send dummy station identity, clear faults/ownership, or modify unrelated settings. Keep GP2-specific capability/pin/pad checks inside its own path.

### Runner, ownership, and public entry points

Reuse the native meter logger, `PilotMeter`, `ActiveWindow`, shared leases, unresolved-state markers, and seal-before-report behavior. Make only the source-specific changes needed for the Si5351 matrix, preparation, timing, transitions, and evidence validators.

Use one physical Pico device-wide lease, regardless of selected clock/engine, plus the shared meter-resource lease. Unresolved source/meter state must block competing GP2 and Si5351 work as applicable. Live review must not acquire RF ownership or mutate hardware.

Expose a clearly named physical Si5351 choice in the existing operator workflow and matching client plan/review/start support. Wire it through `guided_client.py`, `operator_ui.py`, `operator_jobs.py`, worker reconstruction, and the existing operator page. Persist source/schema, fixture, matrix, timing, reviewed authorization, report options, and trusted connection configuration in the job request. UI preflight, API validation, and the worker must enforce the same rules; direct API requests, worker invocation, or malformed persisted requests must not bypass capabilities, identity, preparation, matrix/schema, reviewed authorization, report-dependency, or timing checks. Unsupported features must show a precise unavailable reason.

The paired controller must already be configured for the selected Si5351 engine, clock, and reference. The HP runner must not install firmware, change engine/pin maps, or enable engineering modes. Reject automatic Si5351 continuation explicitly; preserve GP2 continuation and saved-data recovery.

## 5. Encode the physical state machine without exercising it

Implement and test this sequence using injected hardware boundaries only:

1. Validate new output paths and requested optional report dependencies. Check trusted identities, current preparation attestations, ownership, unresolved markers, schedules disabled, source idle/unowned/inactive, storage/fault health, and no unresolved restart. Si5351 preparation must affirm the selected clock-to-sensor path and independent operator shutdown, never a GP2 connection.
2. Freeze/hash the full matrix, fixture, sampling, source context, report options, and campaign authorization. Review all 56 settings before any ZERO, drive mutation, or RF Start. A supported future drive transition may require restart; record and budget it. An outright refusal blocks the full matrix, with no silent subset or omission.
3. Snapshot authoritative initial saved/active drive and relevant configuration. Require a bounded scoped restoration path for the exact initial state. Refuse before mutation if an absent/unset value cannot be restored; do not silently persist a nominal default or factory-reset settings.
4. Use the existing supervised ZERO preparation and RF-off baseline with POWER REF off. Introduce no automatic CAL, reference switching, or baseline subtraction.
5. For each drive group, confirm current RF off, mutate only the scoped drive, restart if required, rediscover the same device, and verify saved/active drive, schedules, and unrelated settings. Record only owned changes. Separate frozen campaign authorization from fresh per-boot/per-revision point admission; never reuse a pre-reboot assessment revision.
6. Durably record the frozen point, unique Start request ID, and pending/recovery state before dispatching Start; journal every owned setting mutation and pending transition before dispatch too. A process failure must leave enough identity to reconcile without another Start. Before each point, obtain fresh `ready` admission and program the existing sensor correction for that absolute carrier while RF is off. Start one bounded tone with a unique request ID and its exact assessment revision. Validate accepted source, clock, carrier, effective drive, duration, identity, and realization.
7. Require the existing settling comparison, then exactly two retained readings at the configured logger interval. Bracket each read with fresh exact-job running/source observations. Accept no sample outside the conservatively verified active interval.
8. Dispatch identified Stop immediately after the second retained read, independently of VISA cleanup. Require exact-job terminal clock-disable evidence and a fresh current inactive output snapshot before another point or setting change. Use healthy TR3/Go To Local cleanup and the existing uncertain-I/O policy.
9. On cancellation, instability, failure, or ambiguity, stop progression, preserve partial evidence and all requested rows, and classify measured, limited, failed, and not-reached outcomes accurately. Never blindly retry a drive/config mutation, restart, or Start after a lost reply. Reconcile authoritative settings or the original request/job under permitted authority before any further deliberate action. Do not automatically resume RF after a worker/service restart. Missing receipts or uncertain RF state retain recovery/pending state and prohibit the next Start.
10. Restore only this run's owned changes after known-safe closure, using conditional revisions and an owned-change journal. Do not overwrite external configuration changes or perform restorative writes while RF/controller state is unknown. Verify final saved/active state and RF off. Report failed restoration separately from capture/report status.

If I2C failure prevents confirmed clock disable, expose the need for the operator's prepared independent shutdown. Do not claim a host Stop thread, an old job's terminal state, or tone expiry can guarantee electrical shutdown.

## 6. Timing, calibration, and evidence invariants

Preserve the existing finite timing model and sample count. Its proposed matrix budget is 8 s startup + up to 3 × 18 s settling reads + 2 × 18 s retained reads + 1 s spacing + 8 s Stop reserve = **107 s per tone**. Validate this against the actual delivered source ceiling; it is not a measured timing result or permission to increase native limits.

Count source observations, launch/transport age, setup/correction work, preparation, transitions, cleanup, and restoration in point/whole-run bounds without double-counting. Translate remote RF/monotonic intervals into conservative host-monotonic deadlines using the delivered contract and measured request/response bounds. Never compare different clock domains directly or infer RF start solely from a phase label. Start another read only if its complete acquisition and Stop reserve fit. Refuse an incompatible budget; do not alter sampling, settling, active-tone length, or controller limits automatically.

Stop must remain timely with a blocked VISA call and an in-flight source Status request. A thread that waits behind an unbounded shared transport lock is not independent Stop; bound and test source transport contention.

Preserve the serial-specific 8482A certificate/hash/page, 99% reference factor, linear-Hz interpolation, meter 0.1% rounding, 1 Hz realization tolerance, calibration-step boundary checks, signed/limited readings, and sensor-input limits. At 2 m, use **144490500 Hz**. Keep nHz realization values exact; compare fractional bounds exactly or round outward, never inward. Add no new factor, correction model, acceptance limit, or persistent meter-table operation.

Seal the frozen request, source/config/revision/boot identities, mutation/restore journal, point authorization, accepted tone, running observations, settling/read brackets, native meter CSV/sidecars and correction receipts, terminal state, baseline, and final state. Do not fabricate operator confirmations or substitute review metadata for execution evidence.

The loader must reconstruct all 56 requested rows and exact matrix/schema identity, recompute statistics/coverage, and reject tampered/swapped settings, wrong-job/boot/clock/drive evidence, duplicate sessions, invalid windows, changed correction source/hash, and false shutdown/restoration claims. Treat worker summaries as operational information, not evidence. Preserve strict GP2 validation and certificate-path compatibility for existing captures. Capture success, restoration outcome, and report-generation success are separate.

## 7. Preserve report behavior

Use the shared HTML/PDF report templates and validated source-specific metadata:

- Opening summary table containing actual run identity, RF output, equipment, report harness, and record ID. Use the supplied campaign inputs; do not hardcode personal/device values into global templates.
- Both frequency and drive comparison charts on PDF page one, sized within its available space; complete data begins on page two, with repeated table headings. Record actual page count rather than forcing a fixed number of pages.
- Solid lines, circles for the first color cycle, squares for the second, and deterministic further markers where necessary. Include all 14 frequency series and all 56 requested rows.
- Sensor-input mW/dBm statistics, sample counts, statuses, applied factors, and actual coverage from the same validated results.
- Concise notes, meaningful supplied metadata, actual issues/failures, and no redundant subtitle, generic measurement-note placeholder, empty equipment-issues line, protocol-verification boilerplate, routine successful restoration, or continuation history. Retain a source-appropriate PDF-only harmonic-contribution note; do not call Si5351 output GPIO/GP2.
- Truthful execution labels and `Acceptance: N/A` when no assessment is supplied. Use `Completed` only when execution is complete; preserve native acceptance semantics and all evidence.
- One HTML entry point, `report.html`, and no duplicate `appendix.html`. Supporting-file guidance follows tables and notes.
- HTML/CSV/JSON with PDF off; selected PDF/ZIP with verified hashes, source binding, and actual page count. Preserve existing default report choices. Check optional dependencies before acquisition when selected.
- Re-report solely from sealed saved data without a device connection. Reporting failure must never reacquire samples, key RF, or rewrite the sealed capture.

## 8. Required RF-free validation

Run tests through `tools/offline_qa.py` using the repository's pinned environments and optional-dependency rules, with injected Pico and meter boundaries. Trap the SSH/subprocess/network/USB/VISA boundaries so an unexpected real-I/O attempt fails the test; an injected meter alone is insufficient. Reuse existing test isolation rather than creating a new containment framework. Do not change dependency pins, weaken guards, skip mandatory checks, or substitute unsupported runtimes to hide a failure. Report unavailable prerequisites precisely. Do not perform SSH/USB/VISA discovery, live review, calibration, ZERO, firmware installation, or a sweep against actual equipment. Injected tests must still exercise the planned ZERO, source-change, Start/Stop, restoration, and failure paths without physical access. Preserve original reference files and existing sealed captures.

Cover at least:

1. Exact 14 dial/carrier pairs, 56 unique ordered points, 112 retained samples in a complete fake run, legal drive domain, and rejection of boolean/invalid inputs. Preserve GP2 52-point and versioned simulation behavior.
2. Versioned paired-contract fixtures for discovery, authorization/target/revisions, engine/clock/ref, drive transition/restart/readback, admission, unique Start, running state, exact-job Stop, and restoration. Reject GP2-only, wrong engine/clock/ref/drive, stale, refused, or unavailable capabilities.
3. Complete and partial physical-schema runs through the real plan/client/API/worker/report path with fake hardware. Verify entry-point parity, stable source selection, source off between points, final restoration, and no premature sampling.
4. Lost mutation/Start/Stop replies; request reconciliation and receipt expiry; reboot/authority changes; worker/process failure with durable pending state and no automatic RF resume; concurrent configuration; cross-engine lease contention and unresolved markers; cancellation at every stage; blocked meter/Status calls; I2C shutdown failure; insufficient timing; unstable/limited/overrange readings; storage/report failure; failed restoration; and unsupported absent-state restoration. Assert no duplicate Start, unverified next point, unsafe restore, or automatic qualification override.
5. Tampering and evidence swaps across points/runs/boots, matrix/config/clock/ref/drive changes, sample/timing/statistics manipulation, wrong correction/hash, and false inactive/restored state. Reject corruption while allowing truthful partial reports.
6. Existing GP2/manual/simulation capture loading, continuation where supported, certificate-path compatibility, recovery/re-report, PDF-on/off, absent optional dependencies, and package verification without hardware. Assert that re-reporting and verification preserve source-capture bytes and original manifests/inventories.
7. Render and inspect every page of complete and partial 56-point PDFs and the HTML at practical widths. Check summary identity, both first-page charts, all 14 legend series, marker differences, row/status coverage, missing values, page count, readable tables, canonical HTML links, and absence of duplicate appendix.

Run focused adapter/matrix/admission/window/runner/import/client/API/worker/recovery/reporting checks, then the full existing offline suite once after those pass. Include localhost HTTP tests; use the permitted environment if sandbox restrictions prevent binding, rather than treating those tests as optional. Run Ruff lint and format checks, `python tools/check_docs.py`, the reference checksums, and `git diff --check`. Report optional-test skips and concrete limitations. Repeat or broaden tests only for changed code, failures, or unresolved concerns.

## 9. Assess, fix, and finish

Before declaring completion, perform an adversarial assessment of the actual implementation against every requirement above and the focused plan. Examine the source and validators, not just passing tests. Correct in-scope defects and add meaningful regression coverage. Reassess the entire changed path after fixes; repeat until no further actionable in-scope issues remain. Keep contract or physical-evidence dependencies explicit rather than concealing them as completed checks.

Update current-state workflow, plan, backlog, and applicable validation documentation. Describe only current behavior, equipment, and limitations; omit development chronology. Put scratch logs in ignored `tmp/` or `temp/`; keep credentials, raw local measurements, and local tool state out of tracked files.

Finish with a concise report listing changed files, exact matrix/sampling behavior, paired source/schema/fixture versions and digests, tests and results, visual verification, compatibility status, and unresolved dependency elements if any. Distinguish source/contract identity from installed-device identity; report installed firmware only when separately supplied authorized evidence establishes it. Distinguish HP implementation complete, paired contract integration verified, and physical qualification; do not claim the latter from CI or fake tests. Live validation and the 56-point conducted run require a separate explicit instruction and fresh prepared fixture confirmation.

Do not commit, push, publish, install firmware, contact hardware, or start the sweep.
