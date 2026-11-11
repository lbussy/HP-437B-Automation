# Mac reversible units and remote reference control

Status: ✅ Complete for the recorded current-meter/Mac setup, November 11, 2026. Owner confirmed final live numeric display, RMT off, and PWR REF off without any keys. Phase 3 remains ⏳ In progress. [Batch plan](PHASE-3-PLAN.md#p3-control-reversible-units-and-remote-reference-switching) and [cleanup correction](AUTOMATIC-LOCAL.md#p3-r10-corrected-results-and-final-reassessment) define the exact scope. Tested revision `70e13acb83cb62bb04c071f239155b91365fd759`, plus documentation-only preparation; no production code/pin changes.

## Setup and authorization

The owner explicitly requested remote POWER REF control and authorized the unit test, reporting source on and 0.988 mW. Original meter SN 3125U33223 retains its documented supply discrepancy; sensor 8482A SN MY41094127 is connected directly to front POWER REF, with its cable to SENSOR. Internal nominal 50 MHz/1 mW reference, no external radio/source or attenuation. Retained manual CAL REF CF 99%, active measurement CAL FAC 100%, duty/offset/REL off, and initial absolute W. Automatic range/filter policy was preserved, while effective range/filter naturally changed with level/units. No zero, calibration, preset/reset, table, resolution, or numerical-correction command was sent.

Same ARM64 Mac/macOS 27.0.1, Python 3.14.10, libusb 1.0.30, pinned PyVISA 1.16.2/PyVISA-py 0.8.1/PyUSB 1.3.1, instrument firmware 1.8, and [explicit @py USB resource](MAC-20261111.md#setup-and-provenance). Adapter revision/firmware remain unknown. This demonstrates configured control/readback and source switching on this path; it does not establish absolute RF accuracy, rear-reference option behavior, other-adapter/host support, or replacement acceptance.

## Physical sequence and results

One resource open; no retry or fault injection. The script used up to 30 seconds per operation under a 180-second action window plus 30 seconds reserved for cleanup. It captured an initial SM, then completed each TR2/read before further SM/OD or programming. Exact stages:

| Stage | Observed result / verification |
| --- | --- |
| Initial W baseline | +0.0009880 W; OD `     0.988 mW`; source on, absolute W, corrections off, no errors |
| LG | −0.0500 dBm; OD `    -0.05 dBm`; fresh SM identifies dBm, source on |
| LN restoration | +0.0009880 W; OD `     0.988 mW`; fresh SM identifies W, source on |
| OC0 remote off | 0.0000 W; fresh SM source off, no errors |
| OC1 remote on, explicitly confirmed | +0.0009880 W; fresh SM source on, no errors |
| Final OC0 | −0.0000000100 W (−0.010 µW); fresh SM source off, W, corrections off, no errors |
| Normal cleanup | Accepted TR3 free-run write, then USB488 GTL/status `01`; connection closed |
| Owner observation | Live numeric display, RMT off, PWR REF off; no key presses needed |

Run: 21:29:37.756042–21:29:58.955493 UTC (15:29:37–15:29:58 CST), 21.19910 seconds total. Six measurement replies and seven status replies completed; OD captured all three unit-cycle displays. The preselected logarithmic tolerance was 0.02 dB: converting baseline W gives −0.05243055 dBm, and the observed −0.0500 dBm differs by 0.00243055 dB. W restoration and remote-on repeat both exactly matched the baseline at recorded precision, inside the preselected 0.002 mW allowance. Both off measurements were below 1% of baseline magnitude, accompanied by fresh source-off flags. These are consistency/switching checks, not source-calibration or RF leakage specifications.

Raw frames include `+0.9880E-03\r\n` for reference-on W, `-0.0500E+00\r\n` for dBm, and `-0.0100E-06\r\n` for final off. Initial SM `000000130011000A1002000000\r\n`; final post-measurement off SM `000000110017000A0012000000\r\n`. Standby in the final SM is the expected TR2 post-read state, captured before cleanup; subsequent TR3/GTL and owner observation establish normal live local operation. This distinction prevents repeating P3-R10's accepted-status-only mistake.

## Evidence and review

Ignored local artifact: `output/logs/phase3-20261111/remote-units-and-reference.json`, SHA-256 `13cd421bfc8596f41a8636bf466f7782e7dc5e829c70a36b2064a6fd91a42826`. Scratch procedure: `tmp/local-return/control-and-reference.py`, SHA-256 `28e1b37021b7a13feac5bd5df21287bdd69e5e91baadf1b8857b8a361aea158c`. The JSON retains each command stage, raw replies/hex, parsed values/status, timing, tolerances, conversions, source revision, and cleanup. Its owner-confirmation field remains pending as of capture; the later explicit confirmation is recorded above without modifying raw evidence.

Independent verification checked all six raw numeric replies against parsed values/units, LG/LN/OC0/OC1/OC0 order, each fresh status's correction/error fields, preselected conversion/restoration/off tolerances, final source-off verification, and separate TR3/GTL metadata. Preflight and fresh reassessment found no actionable defect in the delivered batch. No production change or extra unit-test run was necessary; this is new physical evidence for existing implemented operations. C057/C058 and C065/C066 receive narrowly scoped Mac passes in the matrix; other command, host, fault-recovery, and replacement limits remain.

## Ongoing reference-control policy

Remote `Instrument.command("OC1", confirmed=True)` and `command("OC0")` are now bench-verified for this prepared sensor/internal-reference path. Follow-up qualification procedures can use them with an explicit final-off plan; no manual source toggle is intrinsically required. Ordinary `hp437b log` still preserves the source state unless a procedure explicitly controls it; healthy close restores free-run/local, not POWER REF off. After a failed/uncertain transaction, source-off and recovery must not be assumed from process exit or a blind retry. Interruption/failure recovery, Pi/retrieval, and replacement qualification remain open.
