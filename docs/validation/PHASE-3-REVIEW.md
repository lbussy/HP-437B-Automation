# Phase 3 review and reassessment

Date: November 11, 2026. Phase status: ⏳ In progress. Review performed by the executing assistant in successive passes; no independent reviewer is claimed. [Batch plan](PHASE-3-PLAN.md) and [Mac evidence](MAC-20261111.md) establish the delivered scope.

## Initial assessment and corrections

| Finding | Severity / evidence | Correction and verification | Status |
| --- | --- | --- | --- |
| P3-R01: USB descriptor mistaken for Python identification or adapter firmware | High; USB serial string incorporates instrument model/version | Separate descriptor evidence from actual C055 raw response. Adapter revision/firmware remain unknown; successful query records meter firmware 1.8 | Closed |
| P3-R02: Restricted execution hides USB from libusb | Medium; macOS registry sees device, restricted PyUSB finds zero, open fails before command write | Read-only outside-restriction discovery found one matching adapter. Explicit plan correction then permitted one bounded query, which succeeded without dependency/security changes | Closed for identification; no broader host-support claim |
| P3-R03: Scratch evidence writer serializes raw bytes as JSON | Medium; partial artifact ends at identity raw field after successful query and finally-close | Preserve incomplete file, omit duplicate bytes from identity metadata, store raw hex separately. Hardware-free serialization check and one explicitly planned recapture produce complete JSON/hash; operator confirms local control before and after recapture | Closed |
| P3-R04: Identification batch could imply sensor/measurement/replacement acceptance | High; no sensor connected, current serial not freshly verified, supply discrepancy and exchange pending | Constrain plan/summary/matrix to observed Mac identification. Hold seven later case groups and final replacement/Mac/Pi acceptance. No power/SM/calibration command sent | Closed in delivered claims; hardware prerequisites remain open |
| P3-R05: Close could imply programmatic local control or stream recovery | High; production backend has guarded bus operations | Two explicit owner confirmations of RMT off and working controls after successful queries; manual route only. Fault recovery, GTL, device clear, lockout, and serial poll remain unqualified | Closed in delivered claims; recovery gate remains open |

## Fresh reassessment

After the writer/access corrections, reassessment checked identity/version attribution, no-sensor scope, source-backed command spelling, automatic REN, local-key semantics, trigger exclusion, raw ASCII framing versus electrical EOI, bounded attempts, preservation of failed/partial evidence, software/package origin, matrix counts, and replacement/Pi limits. The final pass found no remaining actionable defect in the delivered communication batch or its evidence claims. The incomplete scratch artifact remains identified as incomplete; it is not a passing raw-frame record.

P3-ENV, P3-ID, and normal supervised P3-LOCAL are accepted only within the run record's scope. Measurement, control restoration, front-panel comparison, finite/sustained logging, physical failure/recovery, Pi retrieval, and final replacement acceptance remain untested. No clean review or successful CI run completes these physical gates. A01–A09 remain open to the extent previously documented, with the C055 observation linked under A01.

## Verification and delivery

The starting commit's 223 software tests pass, Ruff lint and formatting pass, and CLI help/capabilities work. No production source, tests, or package pins changed. All nine tracked reference files are checked against the starting commit, publisher/calibration checksums are verified, and maintained Markdown links/anchors, matrix enumeration, and whitespace are checked before commit. The starting commit's [software CI](https://github.com/lbussy/HP-437B-Automation/actions/runs/43060588712) passed; delivery CI is inspected separately after push.

Commit/push of this truthful partial-result handoff is authorized by the executed prompt. Raw local artifacts, scratch scripts, private machine identity, and measurements remain outside Git. The next concrete batch is the prepared sensor/settings/setup handoff identified in the [run record](MAC-20261111.md#acceptance-and-next-batch).

## Connected-sensor baseline assessment

The P3-BASELINE follow-up retains the original meter/sensor identities, reference-off path, and all existing settings. Initial assessment held configuration, zero/calibration, quantitative comparison, and logging gates; source sequencing permits SM in free-run, TR2/read, and post-completion SM. Fresh reassessment of the captured frames confirms 26-character status, absolute W, reference off, no instrument errors, and expected post-trigger standby. C095/C113 receive partial Mac evidence; G002/G003/G004 remain partial. No production code change was needed.

P3-R06 (Medium): duty correction is enabled and its numeric factor is unknown, and auto averaging is 128 readings. Preserve both observations; do not claim calibrated power, a sustained sample rate, or numerical panel agreement. The baseline summary records these limits and the 7.43-second trigger duration. Closed for delivered evidence claims; measurement-policy prerequisites remain open. The owner subsequently confirmed approximate held-display agreement at −0.006 mW, RMT off, and resumed updating; the [baseline record](MAC-20261111-BASELINE.md) retains this operator evidence separately from raw capture. Reassessment accepts normal supervised local restoration and this qualitative observation; formal quantitative comparison and failure recovery remain open.

## Duty-cycle value follow-up

The owner inspected DUTY CYCLE and reported 1%. Combined with the previously captured enabled flag, this identifies a ×100 mathematical pulse-power correction. The operator was instructed to inspect without editing and exit using SHIFT, then ENTER; exit confirmation remains pending. No setter, reference activation, zeroing, or calibration was executed. The numeric uncertainty in P3-R06 is resolved by owner observation; an appropriate correction policy for the planned continuous reference remains to be established before interpreting power.

## Manual zero preflight

The owner confirms duty correction off and reference off; retain the prior enabled/1% observations as history. The local ZERO procedure was checked visually against manual PDF 136: sensor RF input disconnected from sources, sensor cable retained, one unshifted ZERO, completion observed without further commands. Warm-up and zero completion remain pending. The named plan excludes remote zero, reference activation, gain calibration, automatic retry, and power interruption. This addresses the prepared-setup boundary while preserving the production serial-poll guard.

## Post-zero operator observation

The owner reported −0.009 µW after the warm-up reminder/manual-zero instructions. Unit conversion is −9 nW; preserve the explicit µW unit rather than the earlier mW baseline. This is operator-reported preparation evidence, not remote zero qualification or a specification pass. No zero duration/error history or all-range test was supplied. Calibration remains pending the actual reference calibration factor and prepared path.

## Post-CAL reassessment

The owner reports reference off and −0.08 µW following manual CAL instructions. Preserve the correct −80 nW conversion and avoid treating a reference-off residual as a 1 mW comparison. Reference gain calibration and active measurement CAL FAC have different roles; the next read-only front-panel inspection resolves the latter before reference-on interpretation. Remote calibration remains guarded; no Python I/O or independent accuracy verification occurred.

## Reference-on readback review

P3-REFERENCE-READ preserved REF CF 99%, active CAL FAC 100%, and operator source control. Preflight selected a held-display comparison rule before acquisition and gated reference/units/corrections/errors without configuration changes. Captured SM/TR2/read/SM shows 0.9880 mW, reference on, duty/offset/REL off, no errors, and expected standby after acquisition. Fresh reassessment confirms exact bytes, operation ordering, one-attempt deadlines, source identity, and retained factor. The earlier 0.989 mW manual sample cannot substitute for held-display evidence. The owner then reported held display 0.988 mW and RMT/PWR REF both off. Difference from Python 0.9880 mW is zero at the display increment, within the preselected 0.001 mW criterion; accept this readback comparison and supervised restoration in the [reference record](MAC-20261111-REFERENCE.md). No absolute-accuracy, rate, replacement, Pi, or recovery acceptance is inferred.
