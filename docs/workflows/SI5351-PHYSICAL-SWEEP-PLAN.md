# Si5351 physical sweep implementation plan

The HP-side matrix and offline plan builder are available. The live adapter, runner, and evidence integration depend on the paired WsprryPico Control/1 contract and RF-free fixtures. This plan authorizes no hardware operation or firmware installation.

Use the [bounded implementation prompt](SI5351-PHYSICAL-SWEEP-IMPLEMENTATION-PROMPT.md) for HP-side implementation and RF-free validation.

## 1. Outcome and scope

Implement one human-started, conducted sweep from Pico C's Si5351 output through the existing HP 437B acquisition path. Run all 14 approved frequencies at each of 2, 4, 6, and 8 mA: 56 requested points, drive first, with two retained readings per measured point and the existing one-second logger interval. Actual acquisition times and spacing are retained in native receipts. A fully measured run contains 112 retained readings, plus separate setup, settling, and RF-off observations.

Use the existing authenticated Pico Control/1 connection through its configured USB host. The host transports Pico requests; it is not a WsprryPi transmitter or gateway integration. Keep the existing manual workflows, direct-GPIO sweep, simulation, reference workflows, meter backend, and calibration algorithms operational.

The selected run metadata is:

- RF output: `QRP Labs Si5351A Synthesizer and 25MHz TCXO module`.
- Controller: Pico C through `wspr5`; rediscover and verify the configured member identity and boot before operations.
- Source: the explicitly configured Si5351 transmit clock, with 25 MHz external reference; verify the actual clock and reference configuration against the fixture before Start.
- Fixture: Si5351 transmit output through the coax adapter directly into the 8482A, without an amplifier or attenuator chain.
- Meter: HP 437B SN 3125U22346; sensor: 8482A SN MY41094127.
- Operator: Lee Bussy [AA0NT].

These are run inputs, not global defaults for other equipment or operators. POWER REF must be off. The prepared physical path must satisfy the existing sensor-input and source-loading requirements.

Excluded: paired Pico firmware implementation or deployment, WsprryPi integration, additional boards or sensors, extra bands or drive levels, new transport/authentication systems, engineering admission overrides, unattended recovery, new acceptance limits, fixture-loss modeling, uncertainty modeling, persistent meter-table edits, and automatic RF qualification campaigns. Do not broaden this into a general controller framework or reporting redesign.

## 2. Frozen frequency and drive matrix

Use integer Hz end to end. The HP side supplies the absolute carrier; the controller must not add another WSPR offset or substitute a saved frequency.

| Band | Dial Hz | Carrier Hz |
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

Drive order is 2, 4, 6, then 8 mA. Frequency order within each group is the table order. Assign deterministic P001–P056 IDs. Freeze and hash the complete plan, fixture, sampling, source identity, report options, and reviewed settings.

In `sweep_matrix.py`, provide a source-specific physical Si5351 matrix and plan builder. Do not append 2 m to the shared `DIALS` dictionary: that would change the GP2 campaign. Keep existing physical GPIO and versioned simulation matrices and IDs readable with their defined frequencies and drive domains.

## 3. Paired Pico contract dependency

Obtain the paired project's delivered Control/1 schema, source revision, and RF-free request/response fixtures before finalizing wire code. Record a reproducible association between the paired source revision/schema and the versioned RF-free fixture set used by HP tests. If the delivered contract differs from the fixture version, keep integration pending until the adapter and fixtures are reconciled. Do not invent request fields or infer Si5351 behavior from the GP2 handoff.

The dependency must provide:

1. Read-only discovery and admission for the selected Si5351 engine, clock output, reference configuration, all four effective drive levels, and all 14 exact carriers. Specifically include 5366200, 7040100, and 144490500 Hz.
2. Authoritative saved and active settings, configuration revision, storage/fault state, restart requirements, and drive activation/readback semantics. A saved value alone is not active-drive evidence.
3. Review, finite Start, exact-job Status, and exact-job Stop; scoped target/device/boot and authentication generation; conditional revisions and unique request IDs.
4. Accepted engine/clock/carrier/drive/duration, immutable realization and quantization bounds, running state, effective duration limit, terminal outcome, and current output-inactive confirmation. GPIO pad readback is not Si5351 clock-drive evidence.
5. Explicit behavior for lost replies, reboot, expired authority, I2C errors, unavailable receipts, and configuration restoration. The duration ceiling and shutdown evidence must distinguish software job completion from confirmed clock disable.

HP preflight must fail before ZERO, drive changes, or RF Start if these requirements are missing, mismatched, refused, or incompatible with the acquisition window. Runtime capabilities and point admission remain authoritative even when a source revision is documented as delivered. Paired-project CI and HP-side fake tests are distinct from physical evidence.

If the delivered Control/1 contract changes shared Test Tone requests or receipts, verify the GP2 path against the applicable delivered fixtures as part of the same integration. Bind each client to an explicitly verified contract and reject mismatches before mutation. Preserve GP2 behavior and sealed capture compatibility.

## 4. HP implementation boundaries

Implement in small, reviewable steps:

1. **Matrix and schema.** Add a distinct versioned physical Si5351 capture schema. Update plan validation, point generation, mode guards, source selection, and source-specific preparation fields. Preserve strict loading of existing GP2, manual, and synthetic schemas. Add typed source context for engine, clock, reference, drive settings, and their revisions; do not overload GP2 pin/pad fields or accept an unvalidated metadata dictionary. The Si5351 preparation must describe the selected clock-to-sensor path, not affirm a GP2 connection.
2. **Pico adapter.** Add a narrow Si5351 adapter beside `PicoTone`, sharing `UsbLink` and authenticated request framing. Implement snapshot, read-only admission, scoped drive change/restart/readback, finite Start, running observations, and exact-job Stop against the delivered contract. Keep engine/clock/ref configuration and large wire integers exact. Do not reconstruct full configuration from redacted reads, send station placeholders, or modify unrelated settings.
3. **Physical orchestration.** Extend `pico_sweep.py` only where needed to select source-specific configuration, preparation, matrix, timing, and evidence validation. Reuse `PilotMeter`, `ActiveWindow`, native acquisition, exclusive resource leases, pending-state markers, and report-after-seal behavior. Keep GP2 adapter assumptions inside its source-specific path. Extract only helpers needed by both paths.
4. **Public entry points.** Wire the Si5351 plan and target through `guided_client.py`, `operator_jobs.py`, `operator_ui.py`, and the existing operator page. Add a clearly named physical Si5351 choice and matching client plan/review/start support. Persist source/schema, reviewed plan, timing, report options, and connection configuration into the worker request; construct the same adapter in the worker. Expose unsupported capabilities as unavailable with a reason. Do not add unrelated UI features.
5. **Evidence and reporting.** Extend `guided_sweep.py`, `guided_report.py`, and `report_delivery.py` narrowly for the new schema and native Si5351 receipts. Report from validated results rather than UI state or cached review responses. Keep raw evidence under ignored local run storage.

## 5. Physical execution contract

### Preparation and review

Validate output paths and optional report dependencies before acquisition. Acquire the shared meter-resource lease and one physical Pico device-wide lease, independent of output/engine selection. Honor unresolved meter/source markers across GP2 and Si5351 paths. Live review is observational and cannot reserve or bypass ownership. Verify the intended meter resource and label identities, sensor, fixture, operator, and authenticated Pico identity. Both native schedules must be disabled; the source must be idle, unowned, RF inactive, and free of unresolved restart/fault state.

The Pico must already be configured for the selected Si5351 output and reference. Do not install firmware, change its engine/pin map, or enable an engineering bypass as part of this runner. Bind the review digest to the entire 56-point request and current configuration. Require all 56 points to be reviewable before any RF Start. A future drive group may require a supported save/restart transition; record that disposition and include its budget rather than requiring every group to be simultaneously active. An outright refusal blocks the full run. Each point must be freshly `ready` after its required transition. Do not silently omit refused settings or run a smaller matrix.

Snapshot the authoritative initial saved/active drive, clock selection, relevant source configuration, and revision. Define restoration according to the paired contract, including absent/unset saved values. If the contract cannot restore an allowed initial state exactly through a bounded scoped operation, refuse before the first mutation; do not silently persist a nominal default or reset configuration. A reboot changes the boot binding, so rediscover the same device, verify active settings and schedules, and obtain fresh point admission before Start. The frozen campaign authorization identifies the requested matrix and fixture; it is separate from each boot/revision-bound point admission. After an expected drive/restart transition, verify only the authorized changes and obtain a new point assessment revision. Unexpected configuration, reference, clock, device, or fixture changes invalidate the run. Never reuse a pre-reboot assessment revision.

### Measurement and shutdown

Use the existing supervised ZERO preparation and RF-off baseline capture with POWER REF off. Do not introduce automatic CAL, reference switching, or new baseline subtraction.

For each drive group, require current RF-off confirmation before changing drive. Save only the scoped setting, restart if required, rediscover, and verify saved/active drive and unchanged unrelated configuration. Immediately before each tone, perform fresh source admission and program the existing sensor correction for that point's absolute carrier while RF is off.

Reuse the two-or-three-reading settling comparison and retain exactly two subsequent readings using the existing one-second logger interval. Preserve the current parsed TR2/status behavior, signed readings, overrange/error handling, and limited-indication rules. Settling and baseline observations never count toward the two retained readings. Stop at the first failed, cancelled, unstable, or ambiguous point; keep every requested row and distinguish measured, limited, failed, and not reached.

Bracket each retained reading with fresh observations of the exact running job, engine, clock, carrier, and effective drive. No reading outside its verified active window is valid. Send exact-job Stop immediately after the second retained reading and independently of VISA closure. Verify both that job's terminal clock-disable evidence and the fresh current output state before proceeding. Reuse healthy TR3/Go To Local meter cleanup and the existing uncertain-I/O policy.

Never retry a possibly accepted Start automatically. Reconcile its original request/job under the same permitted authority. Missing receipts, boot changes, lost control, or unknown shutdown retain pending/recovery state and block another point. Do not clear controller faults, reset ownership, or use GPIO evidence as proof of Si5351 inactivity. If I2C failure prevents confirmed clock disable, require the prepared operator-controlled independent shutdown; a timer expiry alone does not prove hardware off.

After known-safe closure or an early stop, restore only the source settings changed by this run, using an owned-change journal and conditional revisions, and verify their final saved/active state with RF off. Verify all unrelated configuration remains equal to the initial snapshot. Do not overwrite an external concurrent change or reconstruct a complete configuration for restoration. Do not attempt restorative writes while RF or controller state is unknown. Preserve the actual failed restoration or unresolved state in the capture and UI; never force a success outcome.

### Timing and calibration

Preserve two retained samples and the one-second logger interval; do not assert exactly one-second completion spacing when settling, source status, and meter readout determine actual timing. Reuse the existing finite timing model; its current matrix proposal is 8 s startup, up to three 18 s settling reads, two 18 s retained reads, 1 s spacing, and 8 s stop reserve: 107 s per tone. This is a budget to validate against Si5351 admission, not a hardware timing claim. Include source observations, launch/transport age, correction/setup work, drive transitions, preparation, cleanup, and restoration in the appropriate point or whole-run deadlines without double-counting.

Derive the active deadline conservatively from the accepted RF interval and effective controller ceiling. Map remote monotonic/RF timestamps into a conservative host-monotonic window using the delivered timing contract and measured request/response bounds; never compare different clock domains directly or infer RF start solely from a phase label. Admit no new read unless its full bounded acquisition and stop reserve fit. Stop must remain timely with an in-flight source status request or blocked meter call. If the timing cannot accommodate two readings, refuse the run; do not reduce samples, increase native limits, lengthen an active tone, or relax settling automatically.

Use the existing serial-specific 8482A profile, certificate hash/page, reference factor, linear-Hz interpolation, and meter 0.1% rounding. Preserve the 1 Hz realization tolerance and calibration-step boundary checks. Retain exact nHz wire values; check fractional realization bounds exactly or round outward before an integer-Hz check, never truncate inward. At 2 m, apply correction at 144490500 Hz. Preserve the sensor-input measurement plane, native correction receipts, and sensor limits. Add no fixture correction, absolute accuracy claim, acceptance threshold, or persistent meter table.

## 6. Evidence, compatibility, and reports

Freeze the exact matrix and preserve per-point authorization, source/config/boot identity, setting changes, accepted tone, running observations, settling/read brackets, raw meter CSV/sidecars, terminal receipts, baseline, final state, and restoration. Retain partial and failed data; never fabricate operator confirmations or substitute review metadata for execution evidence.

The loader must reconstruct all 56 requested rows, exact source schema/matrix identity, statistics, and coverage from the frozen plan and native evidence, including partial runs; worker progress and summary counts are not authoritative. It must reject altered matrix/order/drive/clock/ref/carrier, wrong-job or wrong-boot receipts, duplicate sessions, invalid timestamps/windows, changed correction factors or source hashes, and false shutdown/restoration claims. Source-specific validation must not relax GP2 evidence requirements. Sealed capture success and report-generation success are separate.

Preserve saved-data loading and re-reporting for existing schemas, including certificate-path compatibility. Avoid changing shared schema semantics by using a new physical Si5351 schema and explicit dispatch. Existing GP2 continuation remains supported. Automatic Si5351 continuation is not part of this implementation; reject it clearly rather than using GP2 continuation checks on Si5351 records.

Apply the current shared report preferences:

- Per-run identities and source description in the opening HTML/PDF summary table.
- Both charts on PDF page one, using available space above the footer; complete results start on page two, with repeated table headings.
- Solid lines, with circles and then squares when colors repeat; deterministic additional marker choices if needed.
- All 56 rows, actual coverage/status, sample counts, sensor-input mW/dBm statistics, and applied factors from the same validated data.
- Concise notes, meaningful supplied metadata, actual issues/failures, and no generic measurement-note placeholders or routine success/continuation boilerplate. Keep a PDF-only note about harmonic contributions using source-appropriate wording. Si5351 reports, chart labels, and provenance must identify the configured Si5351 clock; they must not label its power as GPIO/GP2 or treat pad readback as its drive evidence.
- `Execution: Completed; Acceptance: N/A` only for a completed run without supplied acceptance assessment. Other execution outcomes must remain truthful; native statistics retain their acceptance semantics.
- One HTML entry point, `report.html`; no duplicate appendix. Supporting-file guidance follows tables and notes. Validate portable ZIP hashes, source binding, and actual PDF page count.
- PDF-on/off and saved-data re-reporting remain available. A report failure never starts another tone or invalidates an intact sealed capture.

## 7. Verification and acceptance

Run all automated tests through `tools/offline_qa.py`; use injected Pico and meter boundaries. Do not contact hardware, transmit RF, install firmware, or change the bench during software validation.

Required tests:

1. Exact 56-point uniqueness/order and all 14 dial/carrier pairs; legal 2/4/6/8 mA and rejection of invalid/boolean values. Preserve the GP2 52-point matrix and existing simulation/schema behavior.
2. Delivered-contract fixtures for authentication/target/revisions, selected Si5351 clock/reference, drive save/activation, restart/readback, admission, unique Start, running evidence, exact-job Stop, and configuration restoration. Reject GP2-only, wrong-clock/ref/engine, unavailable, refused, or stale capabilities.
3. End-to-end physical-schema capture using fake hardware through the actual client/API/worker path: 56 completed points, 112 retained samples, correct drive groups, no premature sampling, verified source off between points, and final restoration.
4. Failure cases: lost mutation/Start/Stop replies, same request reconciliation, reboot/authority changes, source restart, I2C/clock-disable failure, blocked reads or source status, lock contention, cancellation at preparation/drive/start/read/stop boundaries, insufficient tone budget, instability, limited output, sensor overrange, storage/report failure, and failed restoration. Assert no extra Start, continued point, or unsafe restorative write.
5. Tampered or swapped matrix/config, receipts, clocks, drive, timing, statistics, correction source/hash, shutdown, and restoration fail validation; legitimate partial captures remain reportable.
6. Saved GP2/manual/simulation captures and report packages still load, verify, and re-report without equipment. Exercise PDF-on/off, absent optional dependencies, and failed report regeneration independently of capture.
7. Render complete and partial 56-point reports. Inspect all PDF pages and HTML charts/table at practical viewport sizes; check first-page charts, marker differentiation, row coverage, summary identity, missing values, and absence of duplicate appendix or broken links. Preserve actual page-count receipts; do not force a fixed page count when legitimate text needs more space.

Run focused adapter, matrix, review, active-window, runner, import, operator/client, recovery, and reporting suites, then the full existing offline suite once after relevant checks pass. Include the client/API/worker and localhost HTTP tests; sandbox restrictions require the permitted test environment, not a permanent test exclusion. Run Ruff lint/format, `tools/check_docs.py`, reference checksum verification, and `git diff --check`. Broaden or repeat checks only for new changes, failures, or unresolved concerns.

HP software acceptance requires the exact requested matrix and sampling, delivered-contract conformance, evidence integrity, failure containment, report fidelity, and passing relevant regression checks. Paired Pico changes and required cross-project contract/integration checks must be available before declaring the combined path ready. Report that status explicitly if the dependency is pending.

Physical acceptance is separate: after the paired firmware is installed and the operator confirms the current conducted fixture and independent shutdown, obtain explicit authorization for scoped live validation and the 56-point run. Establish actual admission, timing, drive application, meter samples, stop/inactivity, and restoration on that device. Retain measured coverage and faults; neither CI nor a fake run establishes RF power or shutdown qualification. This implementation plan does not start that campaign.

## 8. Delivery

Deliver the matrix/schema, narrow Pico Si5351 adapter and runner integration, current operator/client path, import and report support, RF-free tests, and current-state documentation. Update [the current plan](../PLAN.md), [open work](../OPEN-WORK.md), and [guided sweep workflow](OPERATOR-GUIDED-SWEEPS.md) with accurate implementation/dependency status. Keep firmware edits, deployments, new sensor profiles, and unrelated backlog outside this work. Do not commit or push without a separate instruction.
