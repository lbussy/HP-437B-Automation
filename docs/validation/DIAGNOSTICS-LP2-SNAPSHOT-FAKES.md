# Read-only LP2 snapshot: fake-first preparation

November 14, 2026. Owner-selected next batch from the [command/backend review](../inventory/COMMAND-BACKEND-REVIEW.md), following the recorded error-selection investigations. This adds a separate opt-in diagnostic capture, not a normal-logger hook, configuration decoder/restore API, new release requirement, or claim of meter performance. Preparation opened no meter session; the subsequent [supervised Pi pass](PI-DIAGNOSTICS-LP2-20261114.md) is recorded separately.

## Manual and existing implementation

The [operating manual, Learn Mode, printed 3-32/PDF 62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=62), specifies an uninterrupted LP2 result of **two ASCII bytes `@2`, followed by 58 binary bytes**, with EOI on the last byte. It lists configuration categories but gives no byte layout on that page. It separately describes returning the binary string to change the meter; this implementation provides no such write/restore operation.

Existing `Instrument.query("LP2")` and `protocol.snapshot` already require exactly 60 bytes and the `@2` prefix, preserving all bytes. They are reused unchanged. The diagnostic bridge disables read/write text termination and requires a backend-reported complete/EOM reply; incomplete transfers are not followed by continuation/recovery reads. Embedded CR/LF, NUL, and high-bit bytes are payload. No text decoding or newline stripping is applied to LP2.

The captured data remains **opaque**. A hash identifies exact captured bytes; equal/different hashes do not prove equivalent/different operating settings, complete configuration coverage, or rollback capability. No fields are inferred from byte offsets. Original publisher files are unchanged.

## Selected profile and bounded sequence

The [snapshot collector](../../src/hp437b/diagnostics_snapshot.py) is selected through the [standalone diagnostic tool](../../tools/diagnose_meter.py) with `--lp2-snapshot`, the existing resource/setup/output arguments, and explicit supervised/prior-worker-stop confirmations. It is mutually exclusive with basic-plus-latch, lifecycle, QX-selection, and invalid-numeric profiles. It requires no deliberate-error fixture confirmation, and rejects supplying one. The normal CLI/default basic profile and normal logging are unchanged.

After adapter/instrument identity checks, the fixed four-row plan is:

| Step | Purpose |
| --- | --- |
| SM before | Record units/configuration flags; require reference off, normal mode, no standby, and no measurement/entry error |
| LP2 once | Read and validate the complete 60-byte binary frame; retain raw hex, size, and SHA-256 without decoding fields |
| TR1 acquisition | Request and fully consume one immediate ordinary measurement, using units established by SM; send no ASCII status query while its reply is pending |
| SM after | Verify observed source/operation/error state and preserved scale/relative/unit/group-trigger/limit/offset/duty flags; retain automatic range/filter observations without treating ordinary automatic changes as faults |

The LP2 operation is read-only with respect to settings. The follow-up acquisition uses TR1 and existing healthy cleanup uses **TR3/free-run, USB488 Go To Local, and raw close**. These trigger/local operations are explicit parts of the communication check, not configuration restore. SM reads can consume resolved error latches, per [Appendix A-1/PDF 151](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=151); selecting this profile explicitly includes those observations. It does not query ERR/ESR or clear registers.

The existing physical runner retains identity checks, pinned dependencies, shared exact-resource leases, one spawned worker, native timeouts, 20/25-second work/total budgets, cancellation/late-result rejection, and bounded finish/disposal. There are no retries, source switches, persistent writes, reset/clear, sensor-table operations, zero/CAL, valid correction-setting changes, or cable/reboot operations.

A nonquiet baseline prevents LP2/acquisition. A fully framed measurement-error sentinel or changed source/status/configuration observation stops the case without further capture commands; healthy communication may still perform existing cleanup. A malformed, short, oversized, wrong-prefix, incomplete-EOM, failed, late, or cancelled transaction stops commands and uses raw close only. No follow-up acquisition is sent after a failed LP2 read. Per [Triggering, printed 3-104/PDF 134](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=134), TR1 adds one filter point and reverts to standby after readout. Standby is rejected at baseline but allowed in the post-TR1 SM observation; existing TR3 cleanup then requests free-run. The test does not infer live operation from a pre-cleanup status frame. TR1 intentionally avoids waiting for a full delayed averaging cycle; this checks ordinary communication, not settling, cadence, repeatability, or accuracy.

## Capture artifacts and result boundaries

The new output directory contains the existing `diagnostics.json` receipt and, when LP2 was complete and timely, **`snapshot.bin` containing the exact 60-byte frame**, including its prefix. The receipt records the artifact's relative path, length, SHA-256, source step, raw hex, identity/equipment/host/pin provenance, timing, native status, and worker/closure evidence. The binary is never transmitted back to the meter.

A valid timely snapshot is retained even if a later acquisition/status/cleanup fails. Artifact presence is not a completed-profile verdict: check overall status and `snapshot_assessment.accepted_full_case`. Failed/incomplete/late LP2 rows do not produce an accepted binary artifact. Export failure records `artifact_failed` and cannot claim full completion; a partial artifact may remain as failure evidence. Unchanged original receipts and raw local captures remain separate from later operator observations.

## Offline evidence and Pi preparation

**30 new guarded fake/integration cases passed**, including the documented TR1 standby transition. They exercise the actual diagnostic bridge through injected USB/VISA, with a 60-byte payload containing embedded/terminal CR/LF, NUL, and high-bit bytes. Cases cover exact bytes/hash export, binary-read-before-acquisition ordering, source/error baseline gates, post-read sentinel/malformed measurement, changed status/flags, short/long/wrong-prefix/oversized/incomplete-EOM transfers, partial writes, no retry or later command on failed framing, late/cancelled/hung/crashed workers, profile/API/CLI guards, and export failure after normal transport close. The earlier combined diagnostics run passed **173 cases** before the last export-failure test was added; the subsequent 30-case snapshot run also covers the manual-supported post-TR1 standby state and rejects standby at baseline.

Lint, formatting, Markdown links/IDs/original manual checksums, and `git diff --check` passed. Wheel/source builds passed; all 51 top-level runtime modules in the wheel and the changed snapshot runtime/tool/test archive members match current source bytes. The final full Python 3.14 reporting-environment regression passed **1,750 tests**, with three opt-in stress cases skipped, in **288.92 seconds**. The hardware guard remained active, while existing local loopback interface tests ran outside the sandbox. The logger, production instrument/transport/parser/encoder, normal CLI, reconciliation, pins, and permanent access rule are unchanged. No hardware coverage is promoted by fake results.

## What is needed for a supervised wspr5 test

Prepare and verify a new isolated Pi installation and guarded tests first, retaining the original logger and udev rule. Use the existing shared lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`. Older diagnostic installations lack this profile. Offline preparation must not discover/open the instrument.

A new isolated non-editable installation is ready at `/home/pi/hp437b-qualification/diagnostics-lp2-20261114T134530Z`. **349 installed-package guarded tests passed in 97.09 seconds**, with lint and formatting passing, on Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41. Delivery SHA-256 is `8e97b6f6fe59bdc1b5350b80d927de4667d6887099a47125d25375846ad74f7c`. Its manifest records base commit `e0d853f78f3cfae20db90d7efbe70a327fa4751d` plus modified runtime hashes, not a fabricated later commit identity. Retrieved preflight records were independently verified against the delivery and current source. The original logger and permanent udev rule remain unchanged; preflight used no native USB backend/discovery/instrument access. The fixed one-pass wrapper was staged without invocation during preparation, then used in the separately authorized physical pass. Delivery, packages, logs, and manual previews remain ignored under `tmp/lp2-snapshot/`.

For the later single pass, freshly confirm the same wspr5 adapter/meter/sensor connections, POWER REF and RMT off, live readings, no pending operation/prior worker, other control apps closed, and about five minutes available with PRESET/LOCAL accessible. Leave settings and cables unchanged. No radio, extra hardware, POWER REF signal, fresh zero/CAL, or FREQ/CAL FAC entry is needed. The sensor stays connected and POWER REF stays off.

After Python closes, obtain a separate no-key confirmation of live readings, RMT off, and POWER REF off. Record any unexpected indication/intervention separately; no automatic retry or subsequent snapshot/restore is authorized by this preparation. A physical pass must independently establish real LP2 framing, post-read ordinary communication, and closure before Pi support for this profile is claimed.

## Subsequent physical result

The [supervised wspr5 pass](PI-DIAGNOSTICS-LP2-20261114.md) completed all four rows in 0.396 seconds: an exact 60-byte opaque LP2 artifact, a valid following TR1 measurement, documented standby, and accepted TR3/GTL/raw-close cleanup. The owner separately confirmed live readings, RMT off, and POWER REF off. Original logger/rule/runtime bytes were preserved; decoding, writeback/restore, and Mac LP2 support remain unqualified.
