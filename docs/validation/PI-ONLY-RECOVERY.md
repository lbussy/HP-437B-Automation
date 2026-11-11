# Pi-only recovery investigation

Status: ⏳ In progress, November 11, 2026. The owner explicitly requested recovery without moving USB to Mac and confirmed POWER REF off. Starting revision `2478d564bc5b54b638a8a63cab24e670a42cd28f`; no production/dependency change at preparation. Retain original meter SN 3125U33223 with its documented supply discrepancy, sensor MY41094127, unchanged direct sensor/reference path, W, manual REF CF 99%, active CAL FAC 100%, corrections off, and current direct Pi USB connection. Previous [Pi-only reconnect failure and expanded recovery](PI-QUALIFICATION.md#post-timeout-usb-enumeration-blocker) remain separate evidence.

## Candidate and sources

Use the pinned PyUSB/libusb stack to reset only the still-enumerated `03eb:2065` adapter after all VISA workers are gone. [libusb reset documentation](https://libusb.sourceforge.io/api-1.0/group__libusb__dev.html) describes a USB port reset and possible handle invalidation/re-enumeration; [Linux USB documentation](https://docs.kernel.org/6.12/driver-api/usb/usb.html) warns about interface/driver synchronization for USBDEVFS_RESET. Mitigate that risk by requiring exclusive ownership, the known adapter serial, interface 0 FE/03/01, no active kernel interface driver, no other claimed interfaces/session, disposal of old handles, and fresh discovery/protocol verification afterward. Stop rather than detaching an unexpected driver or resetting another USB device. The installed udev rule permits the ordinary logging user to access the adapter. No privileged hub/controller reset, host reboot, service stop, persistent setting, instrument reset/preset, calibration, RF-source change, or firmware operation is included.

PyUSB 1.3.1 Device.reset opens its handle, releases its interface resources, calls the libusb backend reset, then disposes its context. This resets USB state, not proof of idle GPIB, valid stream, source state, or local control. A fresh Instrument must establish those properties. USB reset is an explicit diagnostic/recovery action, never an implicit retry on the uncertain Instrument. Native backend device-clear, serial-poll, IFC, and adapter-specific reset commands remain guarded/unqualified.

## Finite release and stop conditions

| Case | Procedure | Acceptance / finite limit |
| --- | --- | --- |
| P3-PI-R2-PREFLIGHT | Existing source-off fresh identity/status/acquisition/normal close; record current USB identity, permissions, bindings, and versions | Known unit/pins, no errors/corrections/reference, numeric W, healthy close. 120 seconds maximum; stop on mismatch |
| P3-PI-R2-HEALTHY | With no VISA worker/session, select exactly one known adapter and interface, require kernel driver inactive, perform one PyUSB/libusb reset in an isolated subprocess, dispose handle | 20-second reset worker allowance plus bounded disposal, one reset/no retry. Capture outcome. No further device commands after unexpected reset failure |
| P3-PI-R2-HEALTHY-VERIFY | Fresh discovery and existing ID/SM/TR2/read/SM, corrected close, then ten-second allowance and independent free-run SM/numeric OD | 120 seconds, 30-second operations. Reset status alone cannot pass. Only a pass releases the fault case |
| P3-PI-R2-FAULT | One new real 0.5-second first-CSV-read deadline, normal setup timeout 30 seconds, same trace/uncertainty/partial-data checks as previous case | At most one injection, 90 seconds total. Preserve failed row and absent normal cleanup, no post-fault ASCII/normal close or automatic retry |
| P3-PI-R2-RECOVER | After worker disposal and fault artifact review, reselect the still-enumerated adapter and perform one identical isolated USB reset, without unplugging or Mac | Same reset identity/exclusivity/binding gates and 20-second allowance. If not enumerated, stop: no guessed-node or controller reset |
| P3-PI-R2-VERIFY | Fresh discovery, known ID, error-free W/source-off acquisition/status, TR3/GTL, independent free-run/display, owner final RMT/reference-off/live confirmation | 120-second protocol budget, then owner observation. Accept only this named route/setup/version; do not infer unplug, other faults, replacement, or unattended recovery |

Initial release is preflight plus one healthy reset/verification. The owner's new recovery request authorizes the one additional fault case only after that prerequisite passes. Overall active bench allowance is ten minutes, excluding operator response time; each stage has its smaller bound. Keep raw artifacts under ignored local/remote qualification output. Stop at the first failed required stage, preserve evidence, and investigate before adding actions or attempts. Manual PRESET/LOCAL once while RMT is lit remains available to the owner; it is a separately reported step and is not a substitute for protocol/USB reconciliation.

## Preflight review

Challenge wrong/duplicate USB target, serial-string mismatch, interface mismatch, kernel-driver contention, retained VISA worker, reset-induced handle invalidation, timeout at reset, stale raw replies/status, blind retries after uncertainty, misleading power/local assumptions, and effects on other radio devices. Exact identity/interface gates, ordinary-user scope, inactive-driver requirement, isolated bounded helper, fresh handles, unchanged source/corrections, independent free-run verification, and separate owner observation constrain the candidate. If a reset reports re-enumeration-required, retain that result and rediscover before assessing any further step; do not rewrite an error into success. No production API or automatic recovery claim is enabled by this plan.

## Healthy reset prerequisite result

Preflight passed fresh identity, source-off W acquisition/status, corrected cleanup, and independent free-run/display in 18.062048 seconds. The ordinary-user reset helper selected bus 3/address 96, verified exact serial/interface and inactive kernel driver, obtained/released an exclusive interface claim, then performed one reset. USB reset returned in 0.287472 seconds (0.415654 seconds including helper lifecycle), with handle disposed and helper exit 0. Fresh discovery retained the original serial and ordinary-user access on the same USB node. The separately captured fresh protocol/independent free-run verification passed in 18.075699 seconds. No unplug, Mac move, source activation, privilege escalation on the Pi, or production/dependency change was used. This released the one new fault case; healthy reset alone is not failed-transfer recovery evidence.

## Failed recovery release: host reachability loss

The one new fault completed normal setup and a real TR2 write, then its read exceeded the injected 0.5-second deadline after 0.502608 seconds. The worker was gone, uncertainty guard blocked reuse with zero extra I/O, no TR3/GTL cleanup followed, and trace retained remote CSV/sidecar hashes. The explicit post-timeout reset still found bus 3/address 96, correct serial/interface, no kernel driver, and an obtainable exclusive interface claim. Its USB reset returned in 0.290451 seconds, helper exit 0, with handle disposed (0.409720 seconds total).

**Do not count this as successful recovery.** Subsequent outside-restriction SSH attempts could not resolve the saved hostname, and a strictly host-key-checked attempt to an existing associated IP timed out. A bounded direct Bonjour lookup supplied no address. No post-reset meter session was opened and no fresh protocol reconciliation occurred. The owner subsequently reported restarting the Pi after lost responsiveness. A following SSH attempt resolved the hostname but timed out, including an explicit IPv4 retry. No prior-boot log or post-restart USB state has yet been captured, so neither a kernel crash nor a reset-caused outage is established. The timing and reported restart are nevertheless sufficient to stop this candidate; no repeat USB reset/fault or production API is released.

The next requested diagnostic is to unplug only adapter USB and leave it disconnected on the Pi side, retaining meter power, GPIB/sensor path, and reference-off state. Check SSH reachability before any further hardware action. The owner has not been asked to move to Mac, reboot again, change host configuration, or alter other USB/radio devices. Preserve volatile/previous-boot logs if access returns. Actual post-restart boot identity, network availability, device enumeration, final local state, and any subsequent route remain pending.

## Evidence retained locally

Raw complete JSON captures from the remote scripts' stdout remain ignored under `output/logs/pi-only-recovery-20261111/`; they preserve capture-time fields without claiming later confirmations. Source installed on Pi remains the verified `d2f44df19ce8d293d040dd1303b09849feb9b972` archive; repository start was `2478d564bc5b54b638a8a63cab24e670a42cd28f`, and the candidate ran only as an ignored test harness. No production code, pins, or automatic-recovery behavior changed.

| Ignored capture | SHA-256 |
| --- | --- |
| `output/logs/pi-only-recovery-20261111/fault.json` | `243e637970d0e9febe6c33017fe5632b28422141516c87e0517bcd4915002256` |
| `output/logs/pi-only-recovery-20261111/healthy-reset.json` | `4c5cbd08a6db3d972e25a43c99fe20fe5b20a40f203f49b11bb5e85b14d09163` |
| `output/logs/pi-only-recovery-20261111/healthy-verify.json` | `68e53223a30eeb73fb1040c41182b8df6cba4d5012fbcfb8703fb4365ba666d3` |
| `output/logs/pi-only-recovery-20261111/post-timeout-reset.json` | `b98b669af5b39ff68d91f2d8f26bb549afc3a33cc9e23b258dbe3817d3d96a43` |
| `output/logs/pi-only-recovery-20261111/preflight.json` | `38d56ae9ebfcb5914cc11b9865305c7e15188addef0ab6d8e257f96b93511efa` |

The fault capture's saved CSV/sidecar hashes identify remote artifacts, but those new CSV/sidecar files have not yet been retrieved or independently validated after the reboot. Local SSH/Bonjour failures are retained in ignored `tmp/pi-only-recovery/`; private network addresses and host-key associations are excluded from published summaries.

## Next source-backed candidate, not released

Investigate explicit USBTMC INITIATE_CLEAR/CHECK_CLEAR_STATUS rather than another USB port reset. The pinned adapter source sets handleSDC on INITIATE_CLEAR, then sends GPIB selected device clear and resets transfer state/IFC; this is more than clearing a USB pipe. [Operating manual §3-22, PDF page 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65) defines the meter's clear-message response as aborting pending HP-IB input/output. Review actual status/poll/drain/halt sequencing against primary USBTMC/Linux sources, prepare typed implementation/meaningful rejection/deadline tests, and bound a separate clear procedure before physical execution. Do not send ASCII clear aliases, conflate SDC with a preset, enable G011 based only on source, or silently run another fault/reset while host reachability is unresolved.
