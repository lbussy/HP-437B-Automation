# Hardware validation plan

Status: ⏳ In progress, November 11, 2026. The [batch plan](validation/PHASE-3-PLAN.md), [Mac run record](validation/MAC-20261111.md), and [review](validation/PHASE-3-REVIEW.md) record execution and remaining gates. This document is the overall acceptance checklist. Derive actual commands and zero/calibration steps from the [manuals](EQUIPMENT.md) and the real signal path.

## Record the environment

Record meter and sensor identification, sensor calibration information, adapter model/firmware, host model/architecture/OS, Python and released dependency versions, USB cable, GPIB address, termination settings, and measurement configuration. Distinguish installed releases from unreleased backend changes.

The [individual calibration records](EQUIPMENT.md#individual-calibration-records) cover meter SN 3125U33223 and sensor SN MY41094127. The user reported on November 11, 2026, that the seller/calibrator confirmed the meter's documented +5 V supply discrepancy was unacceptable, and plans to exchange it after a few development steps. Do not count that supply entry as passing. Associate any interim development results with the current meter and its known discrepancy. Record the replacement meter's identity and applicable calibration records, and repeat hardware acceptance checks with it. Use correction factors for the sensor actually in use. Certificate results do not establish backend compatibility or replace local bench validation.

## Required checks

1. Discover and open the adapter through PyVISA-py using the USBTMC path. Record the resource identifier; use documented 437B commands rather than assuming SCPI examples apply.
2. Read power and compare with the front panel using matching units and correction settings. This comparison checks readback, not absolute calibration accuracy.
3. Change a reversible configuration setting, verify the effect, restore it, and confirm return to local control.
4. Exercise the trigger and status operations actually required by the chosen measurement sequence. Record which operations were tested and which remain unsupported or untested.
5. Verify response termination, expected invalid/overrange behavior, bounded timeouts, recovery after a timeout, and clean shutdown.
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
