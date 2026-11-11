# Automatic return to local

Status: implementation/software tests complete; physical verification pending. November 11, 2026. The owner explicitly requested removal of the PRESET/LOCAL step after normal runs. Starting commit `17daed824a92a721ab24e8209209fbbb85666325`, clean `devel`. Scope: project-local adapter transport extension and normal session cleanup, no firmware flashing or dependency/backend replacement. POWER REF stays off during these tests.

## Source-backed route

The latest published [PyVISA-py release](https://github.com/pyvisa/pyvisa-py/releases/tag/0.8.1), rechecked November 11, remains 0.8.1. Its USB session does not expose working VISA gpib_control_ren or USB control transfers. Its [USBTMC implementation](https://github.com/pyvisa/pyvisa-py/blob/0.8.1/pyvisa_py/protocols/usbtmc.py) defines GET_CAPABILITIES/GO_TO_LOCAL and the advertised capability bit, and already uses the claimed PyUSB handle for automatic REN. The project extension reuses that same version-pinned session/interface rather than opening another USB handle or modifying installed packages.

The adapter [firmware source at inspected commit 88a1383](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/TestAndMeasurement.c), control requests near lines 942–949 and main-loop handling near 1222–1236, accepts GO_TO_LOCAL and queues GPIB GTL until transfers finish. A successful control status acknowledges acceptance, not electrical or front-panel proof. The [meter manual, printed 3-35/PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65), specifies GTL returning front-panel control with settings preserved; [triggering, PDF 133–134](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133) specifies local returns triggered operation to free-run. GTL is distinct from REN deassertion and clearing lockout.

## Implementation contract

`usb488.py` is original project code for profile `xyphro-usb488-gtl-v1`. It accepts only vendor/product `03eb:2065` and a USBTMC interface class/subclass/protocol FE/03/01, reads the actual interface number, validates the exact 24-byte capability reply/status and USB488 bit 1, and exposes conditional local return after successful negotiation. At shutdown it rechecks support and sends class/interface IN GO_TO_LOCAL (`bmRequestType=0xA1`, `bRequest=0xA1`, wValue 0, actual interface, length 1), requiring exactly `01` back. The pinned dependency gate remains unchanged. Other adapters without the profile retain manual local restoration.

A healthy `Instrument.close()` requests local once before closing USB, under its normal operation deadline and worker-process bound. Close is idempotent and resource close still runs if GTL fails. Explicit `bus("G008")` uses the same negotiated operation; all other bus guards remain. Driver uncertainty after failed parsing/transfers/cancellation suppresses automatic local return; it is not used to recover or abort pending work. Logger metadata records accepted/failed local-return evidence after cleanup, and failed local cleanup makes the session failed rather than completed. The method changes neither POWER REF state nor measurement corrections and does not issue reset, zero, calibration, lockout, clear, retry, or REN deassertion.

## Cases, setup, and budgets

Existing identified setup: original meter SN 3125U33223 with known supply discrepancy, firmware 1.8; sensor 8482A SN MY41094127 attached to reference; reference off, duty/offset/REL off, W, CAL FAC 100%, manual CAL REF CF 99%. Same Mac/pins/libusb/resource as [prior runs](MAC-20261111.md). No RF is applied, and no source activation or wiring change is needed. Operator remains the fallback if automatic return fails; send no lockout command. Preserve exact local raw evidence and operator observations separately.

| Case | Procedure | Pass criteria and stop/cleanup |
| --- | --- | --- |
| P3-LOCAL-SW | Capability/status/interface tests, clean/uncertain/failing driver close, worker timeout, logger metadata/error propagation | Software only; no hardware claim. Unsupported device/capability never sends GTL; failed/malformed status cannot pass; close always releases resources; uncertain state skips control traffic |
| P3-LOCAL-ID | One explicit open, *IDN?/read, `Instrument.close()` with negotiated GTL; source off | 10-second open/query/cleanup deadlines, 35-second total budget, one attempt/no retry. Retain identity and USB capability/status bytes; owner observes RMT off and working controls without pressing PRESET/LOCAL. Failure requires recorded manual recovery before reuse |
| P3-LOCAL-LOG | Production `hp437b log` with source off, count 1, interval 0, timeout 30, unit W, actual serials, new output path | At most 120 seconds, one setup acquisition plus one CSV sample; verify completed CSV/metadata including accepted local request, reference/duty flags, no errors, owner observes RMT off and resumed updates without PRESET/LOCAL. This is no-RF cleanup evidence, not accuracy or reference-rate acceptance |

Both physical cases require operator observation; accepted USB status alone cannot pass them. No physical fault injection is released. Timeout/error stops the case, preserves uncertain state, and leaves manual recovery necessary; do not press a local key until the failed outcome has been noted. No program command follows the local request before USB close. Additional hosts and the replacement require separate qualification.

## Review and verification

Preflight challenged version drift, device/interface mismatch, missing USB488 support, accepted versus completed GTL, duplicate USB claims, in-flight commands, cleanup failure suppression, and uncertain-state recovery. Corrections include dynamic capability negotiation on each open, resetting negotiated state before reopen, rechecking capability/status at request time, driver uncertainty gating, idempotent close, bounded RPC, and logger cleanup provenance. Initial local suite: 236 tests passed, lint/format passed. Physical outcomes and fresh reassessment are recorded below after execution.

## First physical result

P3-LOCAL-ID at implementation commit `c0ed20d`, November 11, 21:00:16 UTC (15:00:16 CST), identified HP 437B firmware 1.8 and completed normal close in 0.11665 seconds total. Negotiated interface 0, capabilities `010000010401000000000000000107070000000000000000`, GO_TO_LOCAL reply `01`. Local artifact `output/logs/phase3-20261111/automatic-local-id.json`, SHA-256 `6f8fb250800e016199d1c1189498b34d6904cccc4b3ea3cf84f356051c856c57`. This establishes accepted control transfer; the owner has been asked to confirm RMT off/front-panel control without pressing PRESET/LOCAL. No measurement, RF output, zero, or calibration command was sent.

## Packaging and pending operator gate

Wheel and source distribution build successfully; a separate wheel-installed environment imports the new module from site-packages and passes all 236 tests, with CLI capabilities working. This supplements source-environment lint/format/tests. No physical follow-up is attempted while the owner confirmation for P3-LOCAL-ID is pending; it would be incorrect to accept local restoration from USB status alone or to start the next batch without an established normal outcome.
