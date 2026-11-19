# Bounded ZERO automation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Manual and adapter review supporting this one path

The [ZERO procedure, printed 3-106/PDF 136](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=136), requires no power at the sensor and describes typical 5–20-second operation. The [program example, 3-107/PDF 137](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=137), sends CS then ZE and polls completion bit 1 (value 2) and measurement-error bit 3 (value 8), with a 30-second limit. Error takes precedence over completion in this implementation. The pages were visually reviewed using unchanged publisher originals and derived previews. No ASCII program command is sent while ZERO is pending, because it can abort the operation.

The source review extended the prior pinned adapter review to [`gpib_priv.h` at 88a1383](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/gpib_priv.h). Its receive helper initializes the byte to zero and samples it only after DAV is asserted; timeout before data therefore does not create a completion-looking byte. A timeout after sampling can retain that sampled byte. [`gpib_readStatusByte`](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/gpib.c#L149) and the [USB handler](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/TestAndMeasurement.c#L669) still do not propagate every bus error; the handler ORs cached SRQ bits, then clears that cache. These are source-bound findings, not proof of the exact installed firmware binary. Raw primary headers were retained only in ignored `tmp/zero-freshness/` after the web renderer could not fetch the pinned page.

For this named single-meter/no-competing-controller setup, zero ESE/SRE masks suppress new enabled SRQ conditions during the run. A distinct initial poll consumes any adapter cache, CS clears meter status, and a second uniquely tagged poll must report zero before ZE can start. This is the selected cache/freshness control, not a promise to detect arbitrary firmware failure. Remaining firmware error-reporting limitations stay in the receipt, without creating another checklist item.

## One fixed bounded sequence

The existing isolated diagnostic child, pinned backend, shared resource lease, native cap, grace/disposal logic, and raw-close path are reused. Its physical work/total budgets are **45/50 seconds**. At least 30 seconds plus an eight-second finish reserve must remain before ZE is sent; otherwise no ZERO starts.

| Order | Action |
| --- | --- |
| Preparation | Exact adapter/meter identity; SM source-off/free-run/no-error; ESE?/SRE? both zero. No mask setter |
| Consume old cache | One tagged native poll; only status 0 or an old completion 2 is accepted here, without attributing it to a new ZERO |
| Establish clear baseline | CS, then a new tagged poll requiring status 0. ZE is never issued with an unclear baseline |
| Start once | One ZE write; a partial/failed write means ZERO may have started. No resend |
| Wait | Native polls only, using increasing tags, at most 60 polls and 30 seconds; half-second spacing after incomplete polls. Accept only 0 or completion 2; measurement error 8, including 8+2, wins over completion |
| After known completion | CS and a new native poll must report 0, then SM, one consumed TR1/read, and final source-off/error-free SM with preserved interpretation flags |
| Healthy closure | TR3, accepted GTL, raw close, and separate owner live/local/reference-off observation |

[The runner](../../src/hp437b/diagnostics_zero.py) has thirteen fixed receipt rows. The poll window streams compact raw control/interrupt/capability samples into its existing row so partial evidence survives failure without unbounded messages. Tags start at 2, increase through the run, never wrap, and cannot be reused after failure. At most 63 polls are possible in the fixed sequence, below tag exhaustion. The prior one-shot helper keeps its original default behavior; its private exchange is reused with distinct tags here instead of falsely asserting that an in-progress ZERO is idle.

Native/partial/protocol failures, cancellation, or missing completion stop all later commands, including CS, status queries, and TR3/GTL. Raw close/disposal is still allowed. ZERO may still be running or partially applied; no automatic retry or reversal is attempted. The parent rejects late/missing completion receipts. An unexpected baseline mask/source/cache state stops before ZE. A complete post-operation measurement/status mismatch is retained and cannot claim full-case acceptance. Source/measurement accuracy, all five range residuals, CAL, general serial polling, and unattended fault repair are outside this one interaction case.
