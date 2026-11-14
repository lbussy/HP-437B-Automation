# wspr5 QX ERR-selection observations

November 14, 2026. The owner-authorized [QX-only ordering/timing profile](DIAGNOSTICS-ERR-SELECTION-INVESTIGATION.md) completed on the current meter. This establishes the recorded observations and closure, not general ERR queue semantics or meter performance. Normal logging is unchanged.

## Setup and preparation

The owner freshly confirmed the same wspr5 adapter/meter/sensor connections, POWER REF and RMT off, live readings, no pending operation, closed other control apps, and five-minute availability with PRESET/LOCAL accessible. No cables, frequency setting, calibration, or RF configuration were changed. Supplied labels remain meter `3125U33223` and sensor `MY41094127`; the meter identified as HP 437B firmware 1.8 with a blank serial field. The exact expected USB resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`.

A new isolated non-editable installation was prepared at `/home/pi/hp437b-qualification/diagnostics-err-selection-20261114T122049Z`. Its delivered runtime hashes matched both the installed wheel and local source. Provenance is base commit `676e2915532ef1f5b8d9b9703090df9a00005adb` plus modified-source hashes; no later commit identity is fabricated. Delivery SHA-256: `44ec7c76f353c48e76d1c6c98269ee183a8050fa830462d91a86c846d1260cda`.

**278 installed-package offline tests passed in 73.16 seconds** under the hardware-blocking guard on Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41. Lint and formatting passed. Preflight loaded no native USB backend and performed no instrument access. The original logger environment and permanent udev rule were preserved. The physical pass reused the existing shared reconciliation workflow-lock root, checked no prior control worker was active, and verified pinned backend/runtime identity before opening.

## Physical result

The pass ran at **12:23:00.288524–12:23:05.705166 UTC**, completing in **5.416746 seconds**. All **64 steps** completed and were accepted before the deadline: 57 queries, five QX stimuli, and two no-command waits. CLI exit was 0, the worker exited normally with code 0, and no forced disposal occurred.

| Case | ERR replies | ESR replies | SM entry errors | SM measurement errors |
| --- | --- | --- | --- | --- |
| SM first | 0, 0, 0 | 32, 0 | 0, 0 | 0, 0 |
| ERR first | 0, 0, 0 | 32, 0 | 0, 0 | 0, 0 |
| ESR first | 0, 0, 0 | 32, 0 | 0, 0 | 0, 0 |
| Two-second wait, SM first | 0, 0, 0 | 32, 0 | 0, 0 | 0, 0 |
| Two-second wait, ERR first | 0, 0, 0 | 32, 0 | 0, 0 | 0, 0 |

Actual no-command waits were **2.000056** and **2.000059 seconds**. Baseline and final ESE/SRE/STB, three ESR reads, and three ERR reads were all zero. All SM frames showed reference off, normal mode, no standby, and zero measurement/entry errors; observed configuration flags matched baseline. Range/filter remained 11/17 and units W. No frequency fixture, paired-error case, source operation, clear, preset, zero/CAL, USB reset, reboot, retry, or cable operation occurred.

TR3/free-run and USB488 Go To Local were accepted, transport closed, and installed diagnostic runtime, original normal-logger runtime, and udev-rule hashes were unchanged afterward. These are protocol/process results; front-panel observation is recorded separately below.

## Interpretation

On this setup, QX repeatedly produced the documented command-event bit, but no numeric error was exposed by ERR or either SM field under any tested order/window. Reading ERR or ESR before SM is therefore unnecessary to obtain the zero SM result: SM-first was also zero. A delay of two seconds did not reveal a numeric entry indication. There is no evidence here of an ERR queue fault, and expecting a guaranteed ERR 91 from QX was not justified by the manual text.

Among the six specific fake models, the event-only QX model matches these observations; the simple ERR-clears, ESR-clears, SM-only, numeric-entry, and one-second delayed-entry models predict differing replies. This does not prove internal firmware behavior or eliminate all alternatives: for example, clearing on any valid query before its reply, different update timing, or ERR selecting only measurement/device errors remain observationally possible. The receipt appropriately retains `cause: unresolved` and `queue_observation: not_tested`.

A06 remains partially resolved for the observed command-event read-clear cases. General ERR selection, capacity, ordering, other event classes, and error latches remain unresolved. Any further selected experiment should first establish an independently visible non-QX error, such as a separately authorized invalid numeric-entry case, before attempting paired-error inference. No further hardware test was started automatically, and none becomes a release requirement.

## Front-panel confirmation and retained evidence

After Python closed, the owner separately confirmed: “Confirmed—live readings are updating, RMT is off, and POWER REF is off.” This answered the no-key final-state question. No additional error indication was separately reported. The selected supervised pass now has both protocol/process closure and owner final-state confirmation. The original receipt retains `front_panel_confirmation: not_provided` and `physical_identity_verified: false`; supplied labels and the separate owner observation do not rewrite those fields.

Remote capture: `/home/pi/hp437b-qualification/diagnostics-err-selection-20261114T122049Z/runs/err-selection-20261114T122300Z`. Retrieved raw records remain ignored under `output/logs/pi-diagnostics-err-selection/err-selection-20261114T122300Z/`; delivery, installed preflight evidence, and local verification remain ignored under `tmp/err-selection/`.

| Evidence | SHA-256 |
| --- | --- |
| Original `capture/diagnostics.json` | `79bde387faa0153a2a593c01dda116bac4e1fafc35565ab6974f435e09c3ab5f` |
| Wrapper `result.json` | `ba6cab429db4eb0bbbe53715bd81c6190ff423c94df62fdbc31059533d939051` |
| Separate `owner-final-confirmation.json` | `6487ffb458d2254805d11dfda3db9f14e676be2b4cdf41f27c1569f43b679617` |
| Unchanged permanent udev rule | `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be` |

Local verification independently checked receipt bytes against the wrapper hash, all 64 distinct timely completed steps, installed/delivered runtime hashes, worker exit, transport closure/local return, and preservation of the original logger/access rule. No raw local measurements or local tool state are committed.
