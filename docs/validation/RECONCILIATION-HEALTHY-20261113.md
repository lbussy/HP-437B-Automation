# Current-Mac healthy reconciliation

November 13, 2026. Status: ✅ healthy current-Mac case complete, including separate owner final front-panel confirmation. This is one supervised healthy physical-bridge case, not post-fault or unattended recovery acceptance.

## Authorization and setup

After [physical bridge preparation and fake checks](RECONCILIATION-PHYSICAL-BRIDGE.md), the owner freshly confirmed the same Mac, meter `3125U33223`, sensor `MY41094127`, direct sensor-to-POWER-REF connection, warmed-up setup, POWER REF off, live numeric readings/RMT off, closed other control applications, and availability at the meter for five minutes. The owner explicitly authorized the healthy reconciliation with normal logging unchanged.

Four task-owned operator servers remained from earlier exercises. Their saved job states contained no active starting/waiting/running/reporting jobs. Those idle servers were stopped before opening USB, and the reconciliation child acquired the same configured-resource lease used by WF-01–WF-03. No existing capture or logger implementation was changed.

The resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. The expected 437B identification was `HEWLETT-PACKARD,437B,,1.8`. The USB descriptor string is not a unique adapter hardware serial; meter/sensor label identities remain owner-supplied. Existing equipment records and the current meter's known supply discrepancy retain their provenance roles; this case establishes no measurement-accuracy claim.

## Physical result

The standalone supervised tool completed at **2026-11-13 21:46:48 UTC** (15:46:48 CST), using Python 3.14.10 on macOS 27.0.1 ARM64 and pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1.

| Check | Result |
| --- | --- |
| Attempt/policy | One attempt; maximum one, 30-second work allowance, three-second native finish allowance, 60-second total policy ceiling |
| Selected USB/profile | Named descriptor preflight and opened-device check passed; qualified `xyphro-usb488-gtl-v1` negotiated |
| Meter identification | `HEWLETT-PACKARD,437B,,1.8` matched the supplied baseline; meter serial field remained empty |
| Status observation | POWER REF off, measurement error 0, entry error 0, standby false, absolute W, range 11, filter 17 |
| Healthy closure | TR3 and negotiated GTL accepted, raw transport closed |
| Worker disposal | Stopped, exit code 0, no forced termination |
| Timing | Attempt 0.177632 s; total supervisor 0.195519 s; native-finish join 0.012242 s |
| Outcome | `communication_reconciled`, reason `verified`; actual physical bridge, not an injected backend |
| Original test handling | No failed sample retried, no workflow resumed, no measurement CSV created |
| Owner final observation | Owner confirmed live numeric readings updating, RMT off, and POWER REF off after Python closed. Recorded separately; the original receipt retains `front_panel_confirmation: not_provided` |

The healthy probe sends the reviewed `*IDN?`, `SM`, TR3, and negotiated local-return sequence. No source-on/off, zero/CAL, correction, preset, adapter-target, clear/reset, reboot, cable, or forced-timeout action occurred. The idle operator servers were not restarted during the case. No additional hardware session was opened after this successful attempt.

## Evidence

Raw setup, receipt, audit, source copies, and software provenance remain ignored under `output/logs/reconciliation-healthy/20261113T214622Z/`. The source baseline is `fd924644540599832e84dca00213e018a2e2c645` with the physical-bridge working changes; source files were hashed/copied before USB access and matched after closure. The stored patch captures tracked differences, and source copies include the new bridge/tool files.

The physical receipt SHA-256 is `dc28946d165ccd7a69fcf0cf5662352e4e281b77f7b6ade5deb1de3c87ca3ad6`. Its exact IDN and SM bytes were decoded independently; source-off/error-free status, single attempt, real-bridge evidence origin, accepted GTL, and normal worker exit passed the audit. The supervisor receipt is preserved; the owner observation is separate evidence, not a software-generated front-panel claim. The owner-confirmation sidecar SHA-256 is `36b1c20e9fd13ff74571de2c7b954f2086d81983a3e3156a8e07367030457406`; `audit-final.json` links the two preserved records and marks the healthy case passed.

Healthy communication and GTL acceptance alone do not establish physical display/indicator behavior. The owner subsequently confirmed the requested live numeric readings, RMT-off, and POWER-REF-off state, closing this healthy case. No additional hardware session or front-panel action was requested to record that confirmation. This case does not establish native-abort handling under a new physical fault, repair of an already-wedged adapter, Pi bridge acceptance, or unattended test continuation. Normal logging remains unchanged.
