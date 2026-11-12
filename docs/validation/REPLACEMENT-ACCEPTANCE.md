# Replacement-meter acceptance procedure

Scope update, November 12, 2026: the [owner clarification](../PROJECT-SCOPE.md) supersedes this document's earlier blanket replacement-meter/Phase 3 release gates. Retain the procedures and evidence as scoped interaction/setup work. Replacement arrival does not block workflow, provenance, analysis, or reporting development; equipment-specific checks apply when that equipment is used. This update does not enable guarded commands or authorize new hardware actions.

Status: ✅ Preparation complete; ▧ Physical execution awaits the replacement meter. November 11, 2026. This procedure applies the [adopted initial policy](MEASUREMENT-POLICY.md) and reuses the reviewed current-unit cases. It does not count original meter SN 3125U33223 as replacement evidence. No physical steps in this document have been executed on a replacement.

## Arrival and shared setup gates

Record the replacement's actual model, serial, firmware, arrival condition, and complete supplied calibration records; preserve originals and their hashes. Review the actual results/limits, rather than relying only on a cover-page pass. In particular, resolve any supply-result contradiction like the original meter's 4.498 V entry against +5.0 V ±0.25 V. This is review of supplied records, not an instruction to open the meter or probe internal supplies. A wrong identity, unresolved out-of-tolerance result, or missing applicable evidence remains an HP-01 blocker.

Record the sensor actually present, its cable, label REF CAL FACTOR, applicable certificate/factors, and limits. If the existing 8482A SN MY41094127 is retained, its reported REF CAL FACTOR is 99%; verify the actual label/record at setup. Do not copy this factor or certificate to a different sensor. Record the meter's actual front-panel GPIB address; original address 13 is not a replacement assumption. Use USBGpib V2/firmware V2.4 and the recorded Anker USB-C cable unless the actual equipment changes. The unmarked exact PCB revision is an accepted metadata limitation and requires no further investigation.

Prepared RF path: sensor cable to SENSOR, sensor Type-N RF input directly to the specified POWER REF connector, no external source or attenuation, nominal reference 50 MHz/1 mW, and reference initially off. A different connector option or path requires a revised setup before source activation. Record automatic range/filter, absolute W, duty/offset/REL off, REF CF, measurement CAL FAC, warm-up, and manual preparation. Confirm operator access to PRESET/LOCAL and source-off recovery before USB opening. No unattended source-on or fault testing is included.

Warm up for at least thirty minutes before the preparation/accuracy-dependent observations ([operating manual, PDF 16](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=16)). The already reviewed manual preparation is retained: source off, sensor RF input disconnected from sources with SENSOR cable retained, one local ZERO, await completion without Python traffic; then the prepared direct reference connection and one local CAL using the actual sensor's reference factor. CAL enables the reference during its routine and restores the prior source state. Use [the source-backed preparation](PHASE-3-PLAN.md#p3-manual-zero-preparation) and [CAL procedure](PHASE-3-PLAN.md#p3-manual-cal-preparation), with actual replacement/sensor identities. Stop on an error or a routine still active after thirty seconds; do not retry, issue remote commands, or cycle power as an assumed remedy.

For the retained reference-readback profile, inspect and record active measurement CAL FAC separately from CAL's REF CF. The original profile used CAL FAC 100%; adopt that declared comparison setup only after the actual factors/manual preparation are recorded. It checks configured readback, not independently calibrated RF accuracy. Actual-frequency RF work outside this prepared reference path needs its own applicable factor and uncertainty evidence.

## Per-host cases and finite budgets

Run Mac first, then Pi, retaining separate environment/runtime/unit records. Each host has a maximum twenty-five minutes of active case time; warm-up and operator response time are excluded. Software-only preflight has a separate ten-minute total ceiling per host, with at most three minutes per command; stop and retain any dependency/environment failure instead of extending the budget silently. The explicit per-case limits below also apply. Maximum one forced-timeout attempt per host; no automatic sample retry. Stop at the first failed gate and retain failed/partial artifacts before planning a correction.

| Case | Required result | Case allowance |
| --- | --- | --- |
| RPL-00: identity/records/setup | Actual replacement and sensor identity/records, applicable limits/factors, GPIB address, prepared path, warm-up, source off, and operator recovery access recorded | Shared prerequisite; no hardware execution until resolved |
| RPL-01: host/runtime/access | Actual host/OS/architecture/Python/libusb, pinned package origin/hashes, full software checks/help, exactly intended USB identity/resource, exclusive ownership, and access verified | 120 seconds of device-access work; software checks separately bounded |
| RPL-02: source-off baseline | Fresh ID, serialized complete TR2/read, fresh SM, expected W/corrections/source/error flags, normal close, and separate free-run/numeric OD; retain raw framing | 120 seconds, operations at most 30 seconds |
| RPL-03: control/restoration | Prepared source-on W/dBm/W and OC0/OC1/OC0 checks with the adopted conversion/restoration/off tolerances; final source off and normal cleanup | 180 seconds plus 30 seconds cleanup |
| RPL-04: held display | Prepared reference-on sample and matching physical display within one predeclared display increment; matching units/corrections, complete raw response; source off after comparison | 120 seconds total; display hold at most 60 seconds |
| RPL-05: short log | Production CLI, W, count 3, interval 1, timeout 10, actual serials/resource, exactly three valid CSV rows, setup exclusion, final metadata/cleanup, and raw/parsed integrity | 90 seconds; prepared source-on path only |
| RPL-06: sustained log | Production CLI, W, duration 300, interval 1, timeout 10; actual row count/timing/overruns, valid raw/unit/session data, completion and normal cleanup; explicit final reference off | 420 seconds including setup/final read/cleanup |
| RPL-07: file protection | Completed CSV and sidecar hashes unchanged when reusing their path is refused before opening the adapter | 30 seconds; no device I/O |
| RPL-08: interruption | Reference off; process-directed SIGINT between completed reads, retained valid row(s), interrupted metadata/exit 130, normal cleanup, fresh protocol/free-run verification | 90-second interrupted run plus 120-second verification; use diagnostic interval 20 to create a between-read window |
| RPL-09: original deadline and shutdown | Reference off; one first-CSV acquisition with equal native/parent 0.5-second budgets after normal setup, failed row/sidecar, uncertainty/no extra I/O, disposed worker, bounded shutdown, actual backend abort trace | 90 seconds; normal diagnostic setup operations at most 30 seconds |
| RPL-10: fresh reconciliation | Only after exact abort/tag/status/drain/return evidence: fresh ID/status/source-off acquisition, normal close, independent free-run/numeric OD, and owner live/RMT-off/reference-off confirmation | 120 seconds plus operator observation |

Use a new filename/session for each run. Discover the replacement's actual USB resource: the serial descriptor incorporates instrument identification and may differ from the original. Record the actual firmware instead of hard-coding 1.8. Require the intended 437B model and appropriate parser/capability support; stop on an unexpected identity or response rather than assuming a modern SCPI command set. Ordinary session timeout is ten seconds; explicitly recorded diagnostic/control budgets may differ as listed.

After arrival/setup gates pass, use these production CLI forms, replacing every `ACTUAL_*` placeholder with verified values and a new per-host output path. They select the adopted profile without changing defaults; source preparation/control remains the supervising procedure's separate responsibility.

```bash
hp437b log --resource 'ACTUAL_USB_RESOURCE' --output 'ACTUAL_NEW_SHORT_CSV' \
  --count 3 --interval 1 --timeout 10 --unit W \
  --meter-serial 'ACTUAL_METER_SERIAL' --sensor-serial 'ACTUAL_SENSOR_SERIAL'

hp437b log --resource 'ACTUAL_USB_RESOURCE' --output 'ACTUAL_NEW_SUSTAINED_CSV' \
  --duration 300 --interval 1 --timeout 10 --unit W \
  --meter-serial 'ACTUAL_METER_SERIAL' --sensor-serial 'ACTUAL_SENSOR_SERIAL'
```

Prepare the diagnostic harness from the reviewed production-transport cases with actual identities/resource, unique paths, current runtime hashes, and declared budgets before opening hardware. Historical scratch scripts contain original-unit constants and must not be executed unchanged for a replacement. The meter's ID reply may omit its serial; physical label/certificate evidence must supply the logger's actual serial context rather than copying 3125U33223 or treating an empty reply field as identity verification.

Reference activation is limited to the named prepared cases and existing reviewed OC1 confirmation path. Generic `hp437b log` preserves source state; the supervising reference procedure must explicitly verify final OC0 while transactions remain known/healthy. Any uncertain transfer stops further commands and requires operator source-off/recovery. Do not interpret process exit or accepted USB local status as proof of source off or physical local operation. Fault/interruption cases begin only after reference off has been verified.

Healthy cleanup is TR3 then USB488 GTL. Verify actual live numeric display/local control separately, including an independent session before cleanup can mask a lingering standby state. For RPL-09, the failed Instrument stays blocked and receives no normal ASCII cleanup; native backend abort is distinct from a new parent recovery command. A late reply remains failed/discarded. If the acquisition unexpectedly succeeds, the required failure path was not exercised; record it and stop without consuming extra attempts.

The fault harness must use the delivered production transport/worker with pass-through tracing, not the earlier prototype RPC override, reduced native timeout option, fake reply, delay, or alternate backend. Require real INITIATE_ABORT_BULK_IN tag/status, completed drain, CHECK_ABORT_BULK_IN_STATUS completion, backend return, and worker error within the bounded shutdown path before RPL-10. An exhausted grace, incomplete abort, wrong tag/status, USB enumeration failure, or host issue leaves the case failed/unqualified. A clear/reset return value alone is not recovery evidence.

## Pi access and file retrieval

Move only the USB host connection after the Mac session is closed and reference off; retain warmed meter/sensor setup where practical. Recheck actual Pi enumeration/resource, kernel-driver binding, and ordinary-user access on the new node. The existing vendor/product-scoped plugdev 0660 udev rule is the approved persistent access setup; do not silently change host security, drivers, services, or firmware. Record current Pi kernel/Python/libusb rather than copying historical versions. A USB-only reconnect failure is not a new hardware identity merely because Linux assigned a different device number.

Repeat every required per-host case on Pi. Verify Mac SSH access, starting/observing the bounded Pi run, and retrieval of CSV, sidecar, and selected trace with matching SHA-256 and session identity. Keep credentials, private network addresses, boot IDs, and raw local measurements outside Git. Existing current-unit Pi permission/retrieval evidence remains useful preparation; it does not replace the new-unit cases.

## Final acceptance and report

Require every mandatory declared-profile case to pass on both intended hosts with the actual replacement and sensor. Retain all failures/corrections, exact tested runtime/pins/artifact hashes, physical path/settings/factors, raw/value/unit/session checks, measured timing, reference control/restoration, interruption, failure shutdown, and final operator observations. Record new certificate identity and review outcomes independently of readback agreement. No pass is implied by this prepared checklist.

Perform initial adversarial assessment and a fresh reassessment after corrections. Reconcile case results, current/replacement identity, command/bus matrix scope, software/installed/CI evidence, and any remaining required blocker. Then update HP-01, PHASE-03, VAL-01, the release checklist, inventory links, and final backend acceptance for the declared supervised profile. Preserve all broader command, bus, absolute-metrology, already-wedged, and unattended exclusions. A clean document review alone cannot close a missing physical case.
