# Invalid numeric-entry ERR selection: fake-first preparation

November 14, 2026. Owner-selected follow-up to the [completed QX ordering/timing experiment](PI-DIAGNOSTICS-ERR-SELECTION-20261114.md). This prepares a separately selected numeric-entry diagnostic; it adds no mandatory feature/release requirement, changes no normal logging behavior, and does not establish physical ERR selection or queue semantics. The subsequent [supervised Pi pass](PI-DIAGNOSTICS-NUMERIC-ENTRY-20261114.md) is recorded separately.

## Manual findings and scope

The [operating manual, printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69), explicitly uses `FR-3GZ` as an execution-error example. The execution-error ESR bit has weight **16**, distinct from QX's command-error bit 32. [Table A-1, printed A-4/PDF 154](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=154), identifies **82** as entered frequency out of range. This supplies a documented numeric-entry stimulus and a candidate numeric error to observe; it does not guarantee that ERR returns 82, or establish ERR queue behavior.

[Appendix A-1/PDF 151](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=151) describes entry errors and SM/status-byte latches. It says entry errors require a new HP-IB entry, and that resolved status latches clear when SM is read. [Printed 3-33/PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63) says SM updates only after a measurement. These rules motivate ordered reads and fixed pauses; they do not justify assuming that a persistent entry error will clear on its own, or that ERR is a general SCPI-style queue.

A **valid** FREQ entry selects a sensor-specific calibration factor from the selected table, per [FREQ, printed 3-65/PDF 95](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=95). Therefore the diagnostic never writes a valid frequency to force recovery. Before/after front-panel FREQ and CAL FAC observations are required for this selected numeric-entry experiment; neither value has a qualified direct readback in this diagnostic. This is an experiment-specific preservation check, not a new normal-logging prerequisite. The negative entry is intended to be rejected, and restoration is never inferred merely from quiet SM fields.

## Fixed experiment

The existing [ordered collector](../../src/hp437b/diagnostics_err_selection.py) now supports an explicitly selected numeric-entry variant. It shares fixed query ordering and bounded wait/receipt handling with QX, while retaining QX as the unchanged default. The normal command encoder still rejects negative frequencies and QX. No arbitrary fixture string, valid frequency setter, valid CAL FAC setter, or automatic recovery entry is exposed.

| Phase | Work |
| --- | --- |
| Baseline | ESE/SRE/STB; ESR three times; ERR three times; SM twice; retain the existing quiet/source-off/mask/configuration guards |
| SM first | FR-3GZ; SM twice; ERR three times; ESR twice |
| ERR first | FR-3GZ; ERR three times; SM twice; ESR twice |
| ESR first | FR-3GZ; ESR twice; ERR three times; SM twice |
| Delayed SM first | FR-3GZ; wait two seconds without commands; SM twice; ERR three times; ESR twice |
| Delayed ERR first | FR-3GZ; wait two seconds without commands; ERR three times; SM twice; ESR twice |
| Final | ESE/SRE/STB; ESR three times; ERR three times; SM twice |

Maximum **64 identified steps: 57 queries, five copies of the single fixed invalid entry, and two cancellable waits**, plus the existing identity preflight and healthy TR3/GTL/raw-close cleanup. The last stimulus belongs to a delayed case so the tested one-second delayed-entry model finishes quiet. Two seconds remains an experimental window, not a proven firmware/filter timing bound.

A phase may expose 82 through ERR, SM, both, or neither; each raw reply and ordered numeric value is retained. `expected_numeric_code_observed` records visibility through either ERR or SM without turning an unobserved code into a fabricated fault. The causal field remains unresolved and queue behavior is explicitly not tested: there is only one error stimulus per case, with no QX, paired-error, or automatic follow-on experiment.

Before another stimulus, numeric cases require ESR exactly **16→0**, quiet final ERR and SM, source off/normal operation, and preserved observable configuration flags. Missing execution events, other/new Power On events, persistent event/error replies, active status errors, or changed flags cause an observation stop. No valid setting is written to force the guard to pass. An observation stop with healthy communication can perform the existing free-run/local-return/raw-close cleanup; failed/malformed/partial/cancelled/late communication stops commands and uses raw close only.

The [physical diagnostics runner](../../src/hp437b/diagnostics_physical.py) retains its spawned worker, shared exact-resource lease, identity checks, 20/25-second work/total budgets, native timeout cap/finish grace, cancellation, late-result rejection, and bounded disposal. This profile adds no measurement, source switch, mask change, clear/preset, zero/CAL, reset, cable, reboot, or retry operation. It cannot establish setting preservation from SM alone, and records `numeric_settings_verified: false`; later owner observations remain separate evidence.

## Selection and original settings

The [standalone tool](../../tools/diagnose_meter.py) requires `--numeric-entry --confirm-fixed-error-fixtures`, plus the existing supervised and prior-worker-stop confirmations. It rejects combining numeric entry with lifecycle, QX ERR-selection, or passive latch profiles. The API requires strict boolean selection and a `numeric_original_settings` object with exactly `frequency` and `cal_factor`, each a bounded printable ASCII display string. Setup JSON supplies that same object; values must be freshly observed rather than copied from examples or earlier runs. They are retained as operator-supplied metadata and are never turned into commands. Missing/invalid originals fail before output creation or USB access.

## Software evidence

**41 new guarded cases passed in 11.29 seconds.** Six independent fake mechanisms cover an event-only numeric response, SM-only/excluded ERR selection, ERR/ESR-related clearing, delayed status visibility, and consuming numeric ERR replies. Additional cases cover sticky error/event replies, wrong/mixed/new Power On events, preexisting evidence/masks, changed source/configuration flags, malformed framing, cancelled/deadline-expired waits, API/CLI gates, fixed-only command traces, explicit unverified settings, and normal close versus failure shutdown. These are countermodels of possible behavior, not claims about the actual meter.

The initial combined diagnostics run passed 144 cases before the final Power On countermodel was added; the final 41-case numeric run passed after that correction. Package builds, lint, formatting, Markdown links/IDs/original manual checksums, and `git diff --check` passed. All 50 top-level wheel runtime modules and the changed runtime/tool/test archive members match current source bytes. The final full Python 3.14 reporting-environment regression passed **1,720 tests**, with three opt-in stress cases skipped, in **314.26 seconds**. The hardware guard remained active, with existing loopback interface tests permitted outside the sandbox. No normal logger, instrument, transport, protocol, encoder, normal CLI, reconciliation, dependency-pin, or udev-rule change was made. Old QX physical receipts and their reported observations remain unchanged. No matrix or A06 hardware status is promoted by these fakes.

## Supervised wspr5 procedure

Use a new isolated non-editable installation, verify runtime/pins and guarded tests first, preserve the original logger/udev rule, and use the existing shared lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`. There is no USB discovery or instrument access during offline preparation. The older installed QX runner lacks this profile.

A new isolated installation is ready at `/home/pi/hp437b-qualification/diagnostics-numeric-entry-20261114T131236Z`. **319 installed-package guarded tests passed in 86.46 seconds**, with lint and formatting passing, on Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41. Delivery SHA-256 is `af75587925df4a9d80c64741ba6bcec8e870f9b4b2a8c0b73b00b49c437729a0`; its manifest records base commit `2e06392e43389730f2ba8f8588c2e9947d685b1e` plus modified runtime hashes, not a fabricated later commit identity. Retrieved preflight evidence was independently checked locally against the delivery and current source hashes. The original logger and permanent udev rule remain unchanged, and no native USB backend or instrument access was used. The prepared one-pass wrapper requires fresh setup confirmation and both original display values; it was staged without invocation during preparation and subsequently used for the separately authorized physical pass. Raw preflight logs, delivery artifacts, and manual previews remain ignored under `tmp/numeric-err-selection/`. No physical result or front-panel restoration is inferred from installation success.

For the later physical pass, the owner should freshly confirm the same wspr5 adapter/meter/sensor connections, POWER REF off, RMT off, live readings, no pending operation/prior worker, other control apps closed, and about five minutes at the meter with PRESET/LOCAL accessible. Leave all cables and settings unchanged. No radio or additional hardware is needed.

Before running, record the current **FREQ** and **CAL FAC** displays without changing them. Press FREQ to view frequency; use **SHIFT, ENTER (EXIT)** to leave. Press **SHIFT, FREQ (CAL FAC)** to view calibration factor; use **SHIFT, ENTER (EXIT)** to leave. Do not use arrow keys or ENTER alone. These procedures are supported by [CAL FAC, printed 3-51/PDF 81](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=81), FREQ above, and [EXIT, printed 3-59/PDF 89](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=89). CAL FAC is distinct from the sensor's REF CAL FACTOR label.

Run one pass with POWER REF off throughout. After Python closes, first record any remaining entry/error indication and confirm live readings, RMT off, and reference off without keys. Then view FREQ and CAL FAC again using EXIT, comparing them with the originals. If an error persists or a value differs, stop and record it. Any manual re-entry/recovery should use the recorded originals and be explicitly handled; do not press PRESET or automatically re-enter FREQ, since that may alter the active calibration factor. Do not retry or start paired-error tests automatically.

## Subsequent physical result

The [supervised wspr5 pass](PI-DIAGNOSTICS-NUMERIC-ENTRY-20261114.md) completed all 64 steps in 5.652 seconds. Every ordering/window gave ERR 0,0,0, SM entry 82→0, and ESR 16→0, with accepted cleanup/normal close and original logger/rule preservation. The owner separately confirmed live/local/reference-off state and unchanged FREQ 0.0500GZ/CAL FAC 100.0%. General ERR queue semantics remain unresolved; original receipts and normal logging are unchanged.
