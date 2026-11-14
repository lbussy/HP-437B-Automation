# Reversible acquisition controls: fake-first preparation

Historical version 1 preparation; the [version 2 investigation and revised candidate](RE-FILTER-RESTORATION-INVESTIGATION.md) supersede its RE/filter gate and restoration-trigger sequence for a repeat. Its recorded tests/delivery and failed bench receipt are preserved.

November 14, 2026. Owner-selected follow-up to the [command/backend review](../inventory/COMMAND-BACKEND-REVIEW.md). This prepares a small, separate supervised POWER REF batch for existing filter, resolution, range, and trigger commands. It changes no normal logger, defaults, dependency pins, or workflow behavior, and adds no mandatory completion gate. Preparation opened no meter session; the subsequent [partial supervised Pi run](PI-DIAGNOSTICS-ACQUISITION-20261114.md) is recorded separately.

## Manual findings and selected scope

| Source | Relevant behavior |
| --- | --- |
| [Status table, printed 3-34/PDF 64](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=64) | SM range codes 01–05 are manual ranges 1–5, 11–15 are automatic; filter codes 00–09 are manual counts 1–512, 10–19 are automatic counts 1–512. Counts follow powers of two. Standby/free-run is a separate field |
| [Filter, printed 3-62–64/PDF 92–94](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=92) | The local RESOLN-key description enables auto filtering; extending that expectation to remote RE is tested as a hypothesis, not guaranteed here. FM selects a manual count, FA selects auto, and FH holds the current length. Longer filters take longer to settle |
| [Resolution, printed 3-80/PDF 110](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=110) | RE1EN/RE2EN/RE3EN select resolution. View the current setting using SHIFT, dBm/W (RESOLN). Resolution is not a field of the documented SM frame; existing A04 rounding/format questions remain open |
| [Set range, printed 3-94–95/PDF 124–125](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=124) | RH holds current range, RM5EN selects the least sensitive range, and RA returns automatic mode. Range 5 avoids choosing a sensitive range for the approximately 1 mW reference |
| [Triggering, printed 3-103–104/PDF 133–134](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133) | TR0 holds published updates; TR1/TR2 take a measurement and finish in standby. TR1 does not clear the filter. TR2 waits internal settling, not sensor settling. TR3 restores continuous operation |
| [Status, printed 3-33/PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63) | SM updates after a measurement, so the profile consumes an ordinary acquisition before checking setter effects |

The starting profile is deliberately narrow: source off/live, absolute W, automatic range/filter, and no relative, duty-cycle, or offset correction. Baseline SM verifies those prerequisites before any setting or source change. Other flags are retained and compared. Manual starting modes are not silently converted; this batch stops instead. These restrictions apply to this selected experiment, not normal logging.

The original front-panel resolution **1, 2, or 3 must be supplied**. The software can verify SM's range/filter modes and command acceptance, but cannot directly verify which resolution was selected or restored. Resolution cases are accepted-write/auto-filter-side-effect observations, not full display-resolution qualification. A separate final front-panel comparison is required. Opaque LP2 data is not decoded or written back to supply a rollback mechanism.

## Fixed batch and restoration

The [new collector](../../src/hp437b/diagnostics_acquisition.py) uses existing typed Instrument commands and acquisitions. The standalone [diagnostic tool](../../tools/diagnose_meter.py) selects it with `--acquisition-settings --confirm-reference-control`, the normal supervision/prior-worker confirmations, and setup JSON containing the original resolution plus fresh direct-reference-path/warmed-up assertions. It cannot be combined with other diagnostic profiles, passive latch reads, or error-fixture confirmation.

| Phase | Selected work and observation |
| --- | --- |
| Baseline | SM; gate source-off/live/W/auto modes and existing error/correction state |
| Reference | OC1, one cancellable 20-second no-command wait, TR1/read, SM; observe reference on |
| Resolution 1, then 2 | Each starts with FM4EN, then RE1EN or RE2EN, TR1/read, SM; verify auto filtering re-enabled rather than merely already present |
| Manual filters | FM1EN then FM4EN, each with TR2/read and SM; require manual filter codes 00 and 02 |
| Auto/hold filter | FA, TR1/read, SM; then FH, TR1/read, SM; require held count to match the last observed auto count |
| Range hold/manual/auto | RH, RM5EN, then RA, each with TR1/read and SM; verify held index, manual range 5, then automatic mode |
| Hold/immediate | FM1EN, TR0, then TR1/read and SM; record hold-command acceptance followed by a completed immediate acquisition/standby |
| Delayed | TR2/read and SM while the filter remains manual count 1; record completed delayed acquisition/standby |
| Free-run | TR3, one ordinary read without a trigger, then SM; require free-run state |
| Restoration | OC0 first, original RE entry, RA, FA, TR1/read, SM; verify reference off, automatic modes, and preserved flags, then existing TR3/GTL/raw-close cleanup |

Maximum **49 distinct profile rows: 19 commands, 14 acquisitions, 15 SM queries, and one wait**, plus identity preflight and existing healthy cleanup. Every triggered reply is consumed before any later ASCII query. TR2 is used only at the selected short manual counts, avoiding a delayed acquisition after restoring a potentially long original automatic filter. TR1 readings after setting changes check communication/status; they are not settling/accuracy measurements. Automatic counts and range indices can change normally; restoration means restoring the original resolution command and auto modes, not reproducing initial dynamic indices or an LP2 hash.

TR0 is scoped to accepted hold command followed by successful triggered resumption. Constant POWER REF cannot prove freeze behavior under changing RF. Single acquisitions/elapsed times do not establish general cadence, bandwidth, filter response, numeric resolution, or RF accuracy. No transmitter, supply, sensor-table, correction-factor, zero/CAL, preset, clear/reset, stored-state, bus-trigger, or serial-poll operation is added.

## Bounds and failure behavior

The profile requires fixed **60-second work / 65-second total budgets**. Main work stops before the final **20-second restoration reserve**, including refusing to start a wait that would consume that reserve. A healthy observation mismatch or soft main-budget stop skips remaining cases and attempts only the fixed known-setting restoration. This is not a retry or automatic fault repair. The source is switched off before the remaining restoration commands. Native calls retain the existing two-second cap, finish grace, shared exact-resource lease, and bounded worker disposal.

If communication fails, is malformed/partial, is cancelled, or reaches its native/global deadline, **no further commands or restoration writes are sent**; raw close/disposal applies. POWER REF and changed settings may remain active. The receipt conservatively records possible reference-on state and unverified restoration, including when the worker never returns a final receipt. A late/unaccepted restoration SM cannot establish source-off/restoration success. An accepted OC0 write alone is not treated as verified source-off. The supervisor does not reconnect or retry automatically.

The supervising operator must therefore be able to turn POWER REF off and restore the recorded resolution/auto modes if a fault prevents normal cleanup. The prepared bench wrapper is one pass only; no fault is induced in the real run. Fault scenarios are injected only in fakes. A source-on failure must be reported immediately for manual action, not presented as a closed, restored setup.

## Evidence and provenance

The receipt records exact typed commands/arguments, unique phase/step IDs, raw acquisition/status replies, native framing status, timing, supplied original resolution, source/setting/restoration observations, and normal worker/closure evidence. `resolution_usb_verified` remains false even on an otherwise completed pass. Original before/after operator observations remain separate. Defaults and normal logging are unchanged.

The initial 37-case fake pass completed in 6.95 seconds. A subsequent trigger-state countermodel adds detection of a returned measurement with the wrong standby state. The final **38 new cases** are included in the combined diagnostic/instrument/transport suite, which passed **264 cases in 62.47 seconds**. Stateful fakes exercise resolution's auto-filter side effect, delayed SM refresh, manual/automatic code mappings, all three original resolutions, source-on/source-off state, typed-only fixed writes, consumed-before-query ordering, known restoration after logical failures, wrong/ignored controls, measurement sentinels, native framing/partial writes, cancellation during settling/acquisition/restoration, reserved restoration time, failed OC0, late restoration, and a forced-stopped worker with no false source-off claim.

Injected backends shorten only the fake reference wait and are labeled `injected_fake`; physical waiting is fixed at 20 seconds with no public override. Fakes do not establish physical settings, real timing/settling, or hardware acceptance. The full Python 3.14 reporting-environment regression passed **1,788 tests**, with three opt-in stress cases skipped, in **296.96 seconds**. The hardware guard stayed active, while existing loopback interface tests ran outside the sandbox. Lint, formatting, documentation links/IDs/original manual checksums, and `git diff --check` passed. Wheel/source builds passed; all 52 top-level wheel runtime modules and the changed runtime/tool/test archive members matched current source bytes. Existing normal logger, instrument, transport, parser, encoder, reconciliation, normal CLI, pins, and udev rule remain unchanged.

## Supervised wspr5 preparation

Prepare a new isolated installation with installed-package guarded tests and runtime/hash checks, retain the original logger and access rule, and use the existing shared workflow-lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`. Offline preparation opens no instrument. The older installed diagnostics do not contain this profile.

A new isolated installation is ready at `/home/pi/hp437b-qualification/diagnostics-acquisition-20261114T142141Z`. **387 installed-package guarded tests passed in 107.77 seconds**, with lint and formatting passing, on Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41. Delivery SHA-256 is `6a1c9fd28054975ab1c8a3a3e5a95334191be4da530ca7d3fe1d826518080c26`; the manifest records base `7dcf815e4da16991289ca597ddb5a10853c4ce46` plus modified-source runtime hashes, not a fabricated later commit identity. Retrieved preflight evidence was independently verified against delivery/current-source hashes and showed the original logger and permanent udev rule unchanged. No native USB backend/discovery/instrument access occurred. The fixed one-pass wrapper was staged without invocation during preparation, then used for the separately authorized partial Pi run. Delivery, preflight, package, raw fake evidence, and manual previews stay ignored under `tmp/acquisition-settings/`.

For the later physical run, record the current **RESOLN** value first: with RMT off, press **SHIFT, dBm/W**, note RES1/RES2/RES3, then **SHIFT, ENTER (EXIT)** without arrows or ENTER alone. This supplies the exact restoration value; do not infer it from the number of displayed digits. [EXIT, printed 3-59/PDF 89](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=89), supports leaving without entry.

Freshly confirm the same wspr5 adapter, meter, and sensor; the sensor cable on SENSOR and sensor RF input directly on POWER REF; warmed-up setup; POWER REF/RMT off and live readings; no pending operation/prior worker; other control apps closed; and about five minutes available with PRESET/LOCAL accessible. Leave settings and cables unchanged. The software checks initial auto range/filter and other prerequisites rather than asking the operator to enter settings menus. It will switch POWER REF on/off remotely.

After closure, separately confirm live readings, RMT off, and POWER REF off, then view/exit RESOLN again and compare with the original. If a setting/source operation fails or restoration is unverified, turn POWER REF off as instructed, stop, and handle the recorded setup recovery separately. Do not press PRESET or re-run automatically. No physical run is authorized by this fake-first preparation.

## Subsequent physical observation

The [single supervised Pi run](PI-DIAGNOSTICS-ACQUISITION-20261114.md) did not pass the batch. After FM4/RE1/TR1, SM still showed manual filter count 4; the planned restoration began, but its TR1 read timed out after accepted OC0/RE2/RA/FA writes. No retry or later case ran. Separate owner observations record RES2 and POWER REF/RMT/RNG HLD/SPCL off; live updating was not explicitly confirmed. The original receipt retains unverified restoration. The remote resolution/filter hypothesis and restoration-read timeout need investigation before another selected physical pass; original normal logging is unchanged.
