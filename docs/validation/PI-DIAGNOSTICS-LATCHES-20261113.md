# wspr5 error/event latch-read diagnostics

November 13, 2026 (capture November 14, 01:44:20–21 UTC). Status: **complete for one supervised passive latch-read pass**, including separate owner final-state confirmation. This follows the accepted [basic diagnostics pass](PI-DIAGNOSTICS-BASIC-20261113.md) through the same [physical runner](DIAGNOSTICS-PHYSICAL-RUNNER.md). It checks the selected query replies and closure; it does not qualify all error/event clearing behavior.

## Authorization and setup

The owner freshly confirmed the same wspr5 adapter, meter `3125U33223`, sensor `MY41094127`, and unchanged connections; live readings; POWER REF and RMT off; no pending trigger/zero/CAL; closed other control applications; and five-minute availability with PRESET/LOCAL accessible. The software-only readiness check found matching installed runtime hashes and pinned dependencies, no active control worker, and unchanged original logger/udev records. No USB discovery or register read was performed for that readiness check.

Exactly one subsequent authorized invocation used `--include-latched-reads`, fresh supervision/prior-worker confirmations, and the existing shared resource-lock directory. The source-off/idle assertion was supplied before opening; there was no automatic SM preflight. The selected resource remained `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`, without scanning or setting address 13. The matching meter identification was HP 437B firmware 1.8 with an empty serial field; label identities remain supplied facts.

The isolated package used Python 3.13.5 on Linux 6.18.60+rpt-rpi-2712/aarch64, with PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. The installed source bytes match the prepared delivery manifest; the code was subsequently committed in `e1729c6`, with CI-only budget follow-up `88849d5`. Capture-time build metadata still identifies its original `5200697` plus modified-source preparation, rather than claiming a later commit was installed for this run.

## Observed result

The collection returned `completed`, exit code 0, in **0.431457 seconds**. All seven rows had complete VISA framing and were accepted before their deadline.

| Order | Query | Observed result | Accepted scope |
| --- | --- | --- | --- |
| 1 | `*ESE?` | 0 | One zero event-enable-mask reply |
| 2 | `*SRE?` | 0 | One zero service-request-mask reply |
| 3 | `*STB?` | 0 | One zero ASCII status-byte reply; not serial polling |
| 4 | `OD` | Display text −0.02 µW | Numeric display text, including leading padding, ASCII `uW`, and CR/LF; not a fresh triggered measurement |
| 5 | `ERR?` | 0 | One zero error-query reply; queue/selection behavior not inferred |
| 6 | `*ESR?` | 128 | One nonzero event-register reply with the documented Power On bit set |
| 7 | `SM` | Measurement/entry errors 0; reference off; standby false; absolute W; range 11/filter 17 | One valid source-off status frame, read last; individual flag transitions and freshness not qualified |

All five byte-valued query replies used three ASCII digits plus CR/LF. The `SM` frame matched the existing 26-character status layout plus CR/LF. Raw replies are retained in order in the original receipt.

The publisher's [Figure 3-7, printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69) maps event value 128 to bit 7, Power On; command, execution, and device-dependent error bits have other weights. It describes that bit as set by the meter's LINE transition from standby to on. This single observation does not date the power-on event or show that the meter restarted during the test. The same section gates the status-byte event summary through the event-enable mask; an observed zero `*ESE?` is consistent with `*STB?` returning zero despite the event-register bit.

No repeated event/error read, intentional error, mask setter, clear/reset, zero/CAL, source switch, acquisition trigger, forced timeout, retry, or cable action was included. The nonzero event response is preserved as diagnostic evidence, not treated as a failed collection or a meter-health verdict.

## Closure and owner observation

After the queries, TR3/free-run and USB488 Go To Local were accepted through `xyphro-usb488-gtl-v1`. Raw transport close completed; the worker stopped with exit code 0 and no forced termination. No second session was opened.

The owner answered **Yes** to the no-key confirmation that live readings were updating, RMT was off, and POWER REF was off after Python closed. That observation is recorded separately. The original receipt retains `front_panel_confirmation: not_provided` and `physical_identity_verified: false`; it is not rewritten to manufacture physical observations or hardware serial provenance.

## Preservation and retained evidence

Before/after checks confirmed the original Pi logger's runtime bytes, dependency pins, and installation origin were unchanged. The udev rule and isolated installed runtime hashes were also unchanged. Normal logging and its settings were not modified.

The remote run is `/home/pi/hp437b-qualification/diagnostics-20261114T005719Z/runs/latches-20261114T014420Z`. The complete retrieved case remains ignored under `output/logs/pi-diagnostics/latches-20261114T014420Z/`. Its receipt hash matches the remote capture report; the exact seven-query plan, complete framing, deadlines, values, cleanup, worker exit, and preservation facts were independently checked locally.

| Artifact | SHA-256 |
| --- | --- |
| Original diagnostics receipt | `72c1c9a7aecd1fe71b46fac334458df8b00ffd48fc28a36f9205ce03cf6554c4` |
| Capture/preservation summary | `003ea1457f33523b741da318a32929198af238ebc348a23ddcec650cb173d589` |
| Separate supplied owner final observation | `6bd88f83b852ed0c5f337bcb1141555b046b8b1865dbddd0010d27b6cf6b5ee8` |

## Remaining evidence limits

This selected pass is complete. [A06](../inventory/AMBIGUITIES.md#a06) remains open for read-clear behavior, error selection/queue semantics, and controlled transitions. No second read was taken to determine whether event 128 persisted or cleared, and SM was not compared against a deliberately created/resolved error. Those would be separately selectable experiments, not new requirements for the current deliverable. Mac acceptance, additional modes/parameters, true serial polling, and automatic zero/CAL are not established by this Pi result.
