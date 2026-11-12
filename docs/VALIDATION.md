# Hardware validation plan

Updated November 12, 2026. This document covers software/adapter interaction checks and measurement provenance, not certification of the meter. The [project scope](PROJECT-SCOPE.md) and [current checklist](RELEASE-CHECKLIST.md) govern application acceptance. The [batch plan](validation/PHASE-3-PLAN.md) and run/review records preserve historical scoped evidence. Replacement arrival is not an overall software gate.

Workflow, provenance, analysis, and report acceptance (WF-01/PROV-01/REPORT-01/E2E-01) can proceed using synthetic and retained bench data within their limits. Additional physical checks are needed for particular new hardware interactions or measurement claims, not for every software task. Derive actual commands and zero/calibration procedures from the [manuals](EQUIPMENT.md) and actual setup.

## Record the environment

Record meter and sensor identification, sensor calibration information, adapter model/firmware, host model/architecture/OS, Python and released dependency versions, USB cable, GPIB address, termination settings, and measurement configuration. Distinguish installed releases from unreleased backend changes.

The [individual calibration records](EQUIPMENT.md#individual-calibration-records) cover meter SN 3125U33223 and sensor SN MY41094127. The user reported on November 11, 2026, that the seller/calibrator confirmed the meter's documented +5 V supply discrepancy was unacceptable, and plans to exchange it after a few development steps. Do not count that supply entry as passing. Associate any interim development results with the current meter and its known discrepancy. Record the replacement meter's identity and applicable calibration records, and check the setup/compatibility assumptions relevant to its use. This equipment follow-up does not block software development. Use correction factors for the sensor actually in use. Certificate results do not establish backend compatibility or replace local bench validation.

## Required checks

1. Discover and open the adapter through PyVISA-py using the USBTMC path. Record the resource identifier; use documented 437B commands rather than assuming SCPI examples apply.
2. Read power and compare with the front panel using matching units and correction settings. This comparison checks readback, not absolute calibration accuracy.
3. Change a reversible configuration setting, verify the effect, restore it, and confirm return to local control.
4. Exercise the trigger and status operations actually required by the chosen measurement sequence. Record which operations were tested and which remain unsupported or untested.
5. Verify response termination, the declared bounded failure/recovery cases, and clean shutdown. Distinguish software invalid/overrange parsing tests from any physically required case; the adopted internal-reference profile excludes unsafe overload testing and does not claim instrument-generated invalid/overrange evidence.
6. Run sustained CSV logging for an agreed duration and interval. Check timestamps, explicit units, missing/invalid samples, interruption handling, and output completeness. Record measured behavior without claiming a rate from configuration alone.
7. For Pi operation, verify Mac access and file retrieval. Repeat relevant checks on every additional host before claiming support there.

## Backend decision

PyVISA-py remains provisional until required checks pass. An unrelated missing feature need not disqualify it. If a required operation fails, isolate configuration issues from reproducible defects, then decide whether to fix the backend or adopt another transport/backend. R&S VISA is a proprietary fallback requiring a separate adoption decision.

## Results to retain

For each validation run, record date, operator, environment, exact procedure/commands, expected and observed behavior, pass/fail for each required check, and remaining limits. Raw local measurements belong in ignored `data/` or `output/logs/`; deliberately selected, reviewed evidence may be added under `docs/validation/` when available. No passing result is implied by this document.

## Capability-by-capability qualification

Use the [coverage matrix](inventory/COVERAGE.md) to select capability IDs and their linked prerequisites, expected results, and source questions. Record implementation, software-test, Mac, and Pi status independently. Resolve ambiguous reset/self-test, table-edit, binary-restore, and status lifecycle behavior before accepting those APIs.

The [bus evidence](inventory/GPIB.md#transport-evidence-profiles) identifies limitations in released PyVISA-py 0.8.1. Demonstrate the selected released solution for serial polling, device clear, local restoration, and any required bus trigger or SRQ events. Follow the documented trigger/calibration ordering: await completion or use a verified serial-poll route, because an incoming ASCII program command can abort unfinished work.

## Phase 2 handoff

Use the [installed software and CLI](SOFTWARE.md) and [Phase 2 review](PHASE-2-REVIEW.md) to prepare the first hardware batch. Scripted transports, IPC timeout tests, and synthetic demo output establish software behavior. Physical results belong in the Mac/Pi columns after identifying the actual meter, sensor, adapter, firmware, OS, and dependency versions.

## Automatic local-return follow-up

The owner requested automatic local return after normal sessions. The [versioned extension and cases](validation/AUTOMATIC-LOCAL.md) keep the pinned open-source stack and add a narrowly negotiated USB488 GTL path. Required physical acceptance distinguishes accepted USB control status from RMT off and working front-panel controls. Failed/uncertain transactions retain manual recovery requirements. No Pi or replacement support follows from a Mac current-unit result.

## Named interruption and recovery evidence

The [failure/recovery record](validation/FAILURE-RECOVERY.md) accepts between-read process-directed SIGINT and one induced in-flight acquisition timeout with subsequent manual adapter USB reconnect and fresh protocol verification on the current Mac/unit. Partial-data integrity, uncertainty blocking, no unsafe post-fault traffic, and final source-off/live-local state are recorded separately. Other fault patterns, unattended recovery, device clear, second-host behavior, and replacement acceptance are not inferred.

## Pi preflight

[Pi qualification](validation/PI-QUALIFICATION.md) records the isolated Raspberry Pi 5/aarch64 environment and passing 237-test installed-package suite, lint/format/build, CLI checks, exact runtime pins, and native libusb loading. Ordinary-user USB identification, owner local confirmation, baseline/control, short/five-minute reference logging, and CSV/sidecar hash retrieval passed under the owner-authorized permanent USB permission rule. The owner confirmed final live/local/reference-off operation after sustained logging; display agreement (0.989 mW), between-read SIGINT, and induced timeout handling passed; Pi-only reconnect failed enumeration. An expanded manual LOCAL/Mac-host-assisted return to Pi passed fresh ID/acquisition/free-run checks, with owner confirmation of final live/local/reference-off state; root cause and Pi-only recovery remain unresolved. These version/current-unit cases do not establish replacement or unattended support.

The subsequent [Pi-only recovery investigation](validation/PI-ONLY-RECOVERY.md) stopped its USB port-reset candidate after host reachability was lost following the post-timeout reset and the owner restarted the Pi. A returned reset status is not a recovery pass. Host logs and protocol reconciliation remain pending; no automatic recovery API is enabled.

Reconciled host logs show orderly restart and accepted SSH sessions before adapter unplug; no reset-caused crash is established. The separate USBTMC-clear candidate passed healthy/protocol checks but timed out after the approved fault, with host liveness retained. Manual full USB+GPIB isolation/reconnect is the next named Pi-only route awaiting owner completion; no new fault or Mac action is included.

The [P3-PI-R4 manual full-adapter isolation case](validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) subsequently passed with correct re-enumeration, new-node permissions, fresh ID/status/source-off acquisition, independent free-run, and owner live/local/reference-off confirmation. Boot identity was unchanged; no Mac move or new fault was used. Accept this named supervised Pi-only route only. The long response interval prevents a required-step or recovery-latency claim; software-only candidates, root cause, repeatability, replacement, and unattended recovery stay open.

## Integrated failed-read shutdown

The owner authorized the failure-only transport fix after the original forced-timeout/USB-only failure was reproduced. The [integrated Pi case](validation/PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) passed exact installed-package provenance, 261 local/installed software tests, ordinary CLI logging, one original forced deadline with actual backend abort trace, fresh ID/status/acquisition/free-run verification, and owner final live/local/reference-off confirmation. An expired dispatched read now allows up to one second for existing backend shutdown, while retaining the failed sample, uncertainty, no automatic retry, and bounded worker disposal. Normal logging code/defaults/CSV are unchanged. Already-wedged repair, other fault patterns, replacement, and unattended acceptance remain separate.

The [Mac repetition](validation/MAC-FAILED-READ-SHUTDOWN.md) subsequently passed with the same committed runtime, the declared Mac source-import origin/pins/libusb, ordinary logging, one original forced timeout, exact backend abort trace, fresh protocol/free-run verification, and owner final live/local/reference-off confirmation. Both current-unit host records now support the named failed-read shutdown route. Application acceptance now follows the workflow/provenance/reporting scope; replacement identity/setup is a separate equipment follow-up.

## Pre-arrival readiness

The [adopted initial policy](validation/MEASUREMENT-POLICY.md), [replacement acceptance procedure](validation/REPLACEMENT-ACCEPTANCE.md), and [pre-arrival evidence review](validation/PRE-ARRIVAL-REVIEW.md) complete the available preparation. Scope is supervised internal-reference/readback logging with explicit wider-operation exclusions. These records do not complete the automation/reporting product. The earlier replacement-gate policy is superseded: equipment onboarding and applicable measurement limitations are separate from workflow-to-report software acceptance.
