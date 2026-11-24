# Reversible acquisition controls: fake-first preparation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Manual findings and selected scope

| Source | Relevant behavior |
| --- | --- |
| [Status table, printed 3-34/PDF 64](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=64) | SM range codes 01–05 are manual ranges 1–5, 11–15 are automatic; filter codes 00–09 are manual counts 1–512, 10–19 are automatic counts 1–512. Counts follow powers of two. Standby/free-run is a separate field |
| [Filter, printed 3-62–64/PDF 92–94](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=92) | The local RESOLN-key description enables auto filtering; extending that expectation to remote RE is tested as a hypothesis, not guaranteed here. FM selects a manual count, FA selects auto, and FH holds the current length. Longer filters take longer to settle |
| [Resolution, printed 3-80/PDF 110](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=110) | RE1EN/RE2EN/RE3EN select resolution. View the current setting using SHIFT, dBm/W (RESOLN). Resolution is not a field of the documented SM frame; existing A04 rounding/format questions remain open |
| [Set range, printed 3-94–95/PDF 124–125](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=124) | RH holds current range, RM5EN selects the least sensitive range, and RA returns automatic mode. Range 5 avoids choosing a sensitive range for the approximately 1 mW reference |
| [Triggering, printed 3-103–104/PDF 133–134](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=133) | TR0 holds published updates; TR1/TR2 take a measurement and finish in standby. TR1 does not clear the filter. TR2 waits internal settling, not sensor settling. TR3 restores continuous operation |
| [Status, printed 3-33/PDF 63](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=63) | SM updates after a measurement, so the profile consumes an ordinary acquisition before checking setter effects |

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
