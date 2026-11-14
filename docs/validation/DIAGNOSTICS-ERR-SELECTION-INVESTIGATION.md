# ERR selection after QX: manual review and fake-first follow-up

November 14, 2026. Owner-selected investigation of the zero `ERR?` replies in the [partial wspr5 lifecycle experiment](PI-DIAGNOSTICS-LIFECYCLE-20261114.md). This preparation preceded the separately recorded [supervised wspr5 pass](PI-DIAGNOSTICS-ERR-SELECTION-20261114.md). Physical cause and queue semantics remain unresolved; this work adds no release requirement and changes no normal logging behavior.

## What the manuals establish

| Source | Finding | Consequence |
| --- | --- | --- |
| [Operating manual, printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69) | `QX` is the example for command-error ESR bit 5, weight 32. Device-dependent errors and execution errors have separate event bits | QX→ESR 32 is documented; QX→numeric ERR 91 is not explicitly stated here |
| [Table 3-5, printed 3-41/PDF 71](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=71) | `ERR?` is labeled “Device error query” | It is unsafe to treat it as a modern SCPI all-error queue. The label alone does not prove that it excludes all entry errors |
| [Printed 3-33/PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63) | SM is updated after a measurement | Immediate SM snapshots may lag parser/event activity. A fixed wait can test a timing hypothesis, but cannot establish a universal update bound |
| [Printed 3-38/PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68) | ASCII `*STB?` does not clear the status byte | This is distinct from true bus serial polling; this follow-up adds no backend polling support |
| [Appendix A, PDF 151 and 154](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=151) | The manual describes SM/status-byte error latches and lists invalid-code error 91 separately | Neither the error list nor SM latch rules establish ERR queue order, capacity, clearing, or the exact numeric reply for QX |
| [Publisher manual change sheet, 00437-90029](https://www.keysight.com/content/dam/keysight/en/doc/gate/service-manuals/9018-40583.pdf) | All three pages were visually reviewed. Changes concern A3 power-supply parts/schematics for serial prefixes 2912U/3125U | It supplies no ERR-selection or firmware-parser correction; it is not evidence for a firmware bug |
| [EPM 437B/438A compatibility guide, Appendix A](https://www.keysight.com/ar/en/assets/9922-03818/training-materials/EPM-Series-437B-and-438A-Compatibility.pdf) | Also labels ERR as a device-error query, but describes later EPM meters emulating the language | Corroborating terminology only; its implementation cannot establish behavior of the current 437B firmware 1.8 |

The earlier lifecycle gate deliberately tested the hypothesis that QX would expose 91 through ERR. Its safe stop was correct, but a failed hypothesis is not a demonstrated meter fault. The original receipt and bench conclusions remain unchanged. The new experiment first investigates observability; it does not bypass the gate to manufacture a paired-error result.

## Competing explanations and countermodels

The prior physical trace contains two orderings: QX→ESR 32,0,0→ERR 0,0,0→SM entry 0,0, and QX→ERR 0,0,0→ESR 32,0,0→SM entry 0,0. Four independent fake mechanisms reproduce both complete orderings: an event-only QX; an ERR query that discards an entry indication while replying zero; an ERR query that excludes entry errors with ESR reading clearing the entry indication; and delayed entry visibility beyond the immediate snapshots. These are deliberately competing software models, not claims about undocumented meter internals. They demonstrate that the old trace cannot identify a unique cause.

Additional numeric-entry and SM-only models are controls. They predict different old observations and are not presented as explanations of the entire recorded trace. Fakes test the experiment and interpretation boundaries; only a new physical observation can discriminate among supported hypotheses. Even new order-dependent replies can indicate several mechanisms, so the receipt retains values and timing rather than naming a unique internal cause.

## Fixed follow-up profile

The [QX-only profile](../../src/hp437b/diagnostics_err_selection.py) is selected separately through [the diagnostic tool](../../tools/diagnose_meter.py): `--err-selection --confirm-fixed-error-fixtures`, together with the existing supervised/setup/prior-worker confirmations. It cannot be combined with the older lifecycle profile or passive latch option. Default basic/passive diagnostics and the old lifecycle plan are retained.

| Phase | Sequence |
| --- | --- |
| Baseline | ESE/SRE/STB; ESR three times; ERR three times; SM twice; require the existing quiet/source-off/configuration preconditions |
| SM first | QX; SM twice; ERR three times; ESR twice |
| ERR first | QX; ERR three times; SM twice; ESR twice |
| ESR first control | QX; ESR twice; ERR three times; SM twice |
| Delayed SM first | QX; wait two seconds without sending a command; SM twice; ERR three times; ESR twice |
| Delayed ERR first | QX; wait two seconds without sending a command; ERR three times; SM twice; ESR twice |
| Final | ESE/SRE/STB; ESR three times; ERR three times; SM twice |

Maximum **64 identified steps: 57 queries, five QX writes, and two waits**, plus the existing identity preflight and healthy TR3/GTL/raw-close cleanup. The two waits are deliberate observations, not communication retries. They check cancellation/deadline every 20 ms and record actual elapsed time. The last stimulus belongs to a delayed case so the tested delayed-entry model finishes clear. Two seconds is an experimental window, not a guaranteed full measurement/filter completion interval.

No frequency entry is used, so this profile needs no frequency restoration. There is no source, mask, preset, clear, zero/CAL, sensor-table, transport reset, reboot, or cable operation. The normal encoder continues to reject QX; the literal fixture remains private to this explicit diagnostic path. It never intentionally generates a measurement error by disconnecting the sensor or applying RF.

The existing spawned worker, exact-resource shared lease, adapter/instrument identity checks, 20/25-second work/total budgets, native timeout cap, late-result handling, and disposal rules are reused. Baseline errors/nonzero masks prevent stimuli. Each case must observe the command event and finish with quiet ERR/SM state and preserved configuration flags before another stimulus. A nonquiet result stops further cases and retains the trace. Failed/malformed/partial/cancelled/late communication stops commands and uses raw close only. An observation stop with healthy communication may use existing TR3/GTL cleanup. No inference is made from unattempted cases or failed transactions.

The receipt includes case completeness, ordered ERR and ESR replies, SM measurement/entry fields, raw query bytes, individual timing, and worker/cleanup evidence. Its causal result remains unresolved, and queue behavior is explicitly not tested: only one error is injected per case. A paired-error experiment should be selected only after independently establishing useful observable error stimuli; it is not automatically run by this profile.

## Software evidence

**30 new guarded fake/integration cases passed**, covering six independent countermodels, reproduction of both prior complete QX traces, fixed-only commands and distinct step IDs, explicit API/CLI selection gates, quiet-baseline/active-status stops, malformed replies, cancellable no-command waits, parent cancellation/deadlines during waits, normal cleanup versus raw-close-only failure behavior, and non-fabricated incomplete observations. The earlier combined diagnostics/instrument/transport focused run passed 178 cases before the final added cases/order correction; the final 30-case follow-up passed in 10.73 seconds. The final full Python 3.14 reporting-environment regression passed **1,679 tests**, with three opt-in stress cases skipped, in **268.48 seconds**. The hardware guard remained active; existing local loopback interface tests ran outside the sandbox.

Lint, formatting, Markdown links/IDs/original manual checksums, and `git diff --check` passed. Wheel/source builds passed; all 50 top-level wheel runtime modules and the follow-up source/tool/test archive members matched the current source bytes. Scratch logs/packages/manual previews remain ignored under `tmp/err-selection/` and `tmp/pdfs/err-selection/`. Fake results do not promote A06 or the Mac/Pi coverage matrix. The original logger, instrument, transport, protocol, command encoder, measurement workflows, and dependency pins remain unchanged. No native USB access is part of offline preparation.

## What is needed for a supervised wspr5 test

Prepare and verify a new isolated Pi installation, preserving the original logger and udev rule, and use the existing shared lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`. The old installed lifecycle runner does not contain this new profile. The subsequent isolated installation passed 278 guarded tests, and the [new physical pass](PI-DIAGNOSTICS-ERR-SELECTION-20261114.md) completed all 64 steps. Earlier hardware receipts remain unchanged.

Then obtain a fresh confirmation: same wspr5 adapter and meter/sensor connections, POWER REF off, RMT off, live readings, no pending operation or prior worker, other control apps closed, and an operator at the meter for about five minutes with PRESET/LOCAL accessible. Leave settings and all cables unchanged. The run may briefly generate command-error indications; POWER REF stays off throughout. No radio, new hardware, FREQ check, or warm-up wait is needed for these source-off parser/status observations.

After Python closes, separately confirm live readings updating, RMT off, and POWER REF off without pressing keys. If an indication remains or intervention is needed, record it and stop. Further stimuli or manual recovery are not implicit retries. This preparation does not authorize an unattended physical run. The subsequent supervised pass observed zero ERR/SM errors and ESR 32→0 under every selected order/window; separate owner confirmation of live readings, RMT off, and POWER REF off is recorded in its bench record.
