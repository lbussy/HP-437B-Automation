# Invalid numeric-entry ERR selection: fake-first preparation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Manual findings and scope

The [operating manual, printed 3-39/PDF 69](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=69), explicitly uses `FR-3GZ` as an execution-error example. The execution-error ESR bit has weight **16**, distinct from QX's command-error bit 32. [Table A-1, printed A-4/PDF 154](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=154), identifies **82** as entered frequency out of range. This supplies a documented numeric-entry stimulus and a candidate numeric error to observe; it does not guarantee that ERR returns 82, or establish ERR queue behavior.

[Appendix A-1/PDF 151](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=151) describes entry errors and SM/status-byte latches. It says entry errors require a new HP-IB entry, and that resolved status latches clear when SM is read. [Printed 3-33/PDF 63](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=63) says SM updates only after a measurement. These rules motivate ordered reads and fixed pauses; they do not justify assuming that a persistent entry error will clear on its own, or that ERR is a general SCPI-style queue.

A **valid** FREQ entry selects a sensor-specific calibration factor from the selected table, per [FREQ, printed 3-65/PDF 95](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=95). Therefore the diagnostic never writes a valid frequency to force recovery. Before/after front-panel FREQ and CAL FAC observations are required for this selected numeric-entry experiment; neither value has a qualified direct readback in this diagnostic. This is an experiment-specific preservation check, not a new normal-logging prerequisite. The negative entry is intended to be rejected, and restoration is never inferred merely from quiet SM fields.

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
