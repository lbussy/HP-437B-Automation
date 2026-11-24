# Read-only LP2 snapshot: fake-first preparation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Manual and existing implementation

The [operating manual, Learn Mode, printed 3-32/PDF 62](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=62), specifies an uninterrupted LP2 result of **two ASCII bytes `@2`, followed by 58 binary bytes**, with EOI on the last byte. It lists configuration categories but gives no byte layout on that page. It separately describes returning the binary string to change the meter; this implementation provides no such write/restore operation.

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

The LP2 operation is read-only with respect to settings. The follow-up acquisition uses TR1 and existing healthy cleanup uses **TR3/free-run, USB488 Go To Local, and raw close**. These trigger/local operations are explicit parts of the communication check, not configuration restore. SM reads can consume resolved error latches, per [Appendix A-1/PDF 151](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=151); selecting this profile explicitly includes those observations. It does not query ERR/ESR or clear registers.

The existing physical runner retains identity checks, pinned dependencies, shared exact-resource leases, one spawned worker, native timeouts, 20/25-second work/total budgets, cancellation/late-result rejection, and bounded finish/disposal. There are no retries, source switches, persistent writes, reset/clear, sensor-table operations, zero/CAL, valid correction-setting changes, or cable/reboot operations.

A nonquiet baseline prevents LP2/acquisition. A fully framed measurement-error sentinel or changed source/status/configuration observation stops the case without further capture commands; healthy communication may still perform existing cleanup. A malformed, short, oversized, wrong-prefix, incomplete-EOM, failed, late, or cancelled transaction stops commands and uses raw close only. No follow-up acquisition is sent after a failed LP2 read. Per [Triggering, printed 3-104/PDF 134](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=134), TR1 adds one filter point and reverts to standby after readout. Standby is rejected at baseline but allowed in the post-TR1 SM observation; existing TR3 cleanup then requests free-run. The test does not infer live operation from a pre-cleanup status frame. TR1 intentionally avoids waiting for a full delayed averaging cycle; this checks ordinary communication, not settling, cadence, repeatability, or accuracy.

## Capture artifacts and result boundaries

The new output directory contains the existing `diagnostics.json` receipt and, when LP2 was complete and timely, **`snapshot.bin` containing the exact 60-byte frame**, including its prefix. The receipt records the artifact's relative path, length, SHA-256, source step, raw hex, identity/equipment/host/pin provenance, timing, native status, and worker/closure evidence. The binary is never transmitted back to the meter.

A valid timely snapshot is retained even if a later acquisition/status/cleanup fails. Artifact presence is not a completed-profile verdict: check overall status and `snapshot_assessment.accepted_full_case`. Failed/incomplete/late LP2 rows do not produce an accepted binary artifact. Export failure records `artifact_failed` and cannot claim full completion; a partial artifact may remain as failure evidence. Unchanged original receipts and raw local captures remain separate from later operator observations.
