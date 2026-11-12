# WF-03 physical POWER REF integration

Prepared November 12, 2026. `tools/run_cycle_reference.py` integrates the [WF-03 repeatability analysis/report](TRANSMISSION-CYCLES-V1.md) with the existing supervised Mac POWER REF path. Offline injected-adapter checks and actual bench evidence are recorded separately below. Ordinary logging, WF-01/WF-02 runners, defaults, dependencies, and transport shutdown remain unchanged.

## Setup and fixed sequence

Require fresh owner confirmation of Mac USB attachment, direct sensor RF input to POWER REF and sensor cable to SENSOR, reference initially off, warm-up, closed other control apps, and available front-panel recovery. Retain actual meter/sensor labels, firmware expectation, calibration/factor history, adapter/address/cable, and known issues using the [existing prepared-setup fields](WF-01-PHYSICAL.md#fixed-run-and-execution-boundary). Do not infer labels from USB identity or silently change factors, zero/CAL, preset, reset, range, filter, or correction settings. The current meter's known supply discrepancy remains measurement provenance.

The sequence is source-off preflight and three initial baseline readings, followed by five numbered cycles. Each cycle verifies OC1/source on; captures twenty seconds of settling observations excluded from aggregate statistics; captures a thirty-second plateau; verifies one OC0/source off; retains at least twenty seconds of off dwell; captures three off-baseline readings; and closes normally. After C05, independently check free-run/status and numeric OD, then perform normal TR3/USB488 GTL closure. Retain source/local protocol outcomes separately from the owner's later front-panel confirmation.

Each stage uses the existing serialized APIs and ten-second operation timeout; requested sampling is one second. Record actual sample counts/spacing rather than promising 30 rows or 1 Hz. Source/status/correction/error/automatic-range/filter preconditions are verified using fresh consumed acquisitions. The twenty-second settling/off allowances are declared profile conditions, not universal sensor/source specifications or transmitter duty-cycle claims.

## Bounds, ownership, and failure policy

A cooperating WF-01/WF-02/WF-03 runner on the same explicit resource shares one advisory lock. Other applications still require owner-confirmed exclusivity. The workflow ceiling is 900 s, normal work stops by 810 s, and each cycle is capped at 180 s. A new cycle needs at least 150 s remaining before activation. Stage caps are 60 s preflight, 90 s per baseline, 30 s source-on, 60 s settling, 70 s plateau, 20 s source-off, 30 s off dwell, and 20 s final free-run. The earlier cycle/workflow deadline always takes precedence; acquisition stages reserve their complete requested window plus 30 s for setup/closure. Cleanup has at most 20 s with finalization reserved before the last 30 s. Parent supervision signals at 870 s and disposes its owned process group by about 900 s.

Stop at the first failed stage/control/cancel, retain every requested cycle, and skip later cycles with reasons. A cycle is complete only after its verified off/dwell/baseline closure; a full plateau followed by failed off remains incomplete and excluded from aggregate statistics. Known-healthy interruption or complete instrument/policy errors can permit one bounded off verification after owned activation. Failed/uncertain read/write/close, failed off, or still-on verification never causes another open/write/GTL or OC0 retry. Initial-on is refused without adoption/deactivation. No actual fault injection, automatic restart, port reset, USB clear, or broader bus feature is included.

The runner checkpoints owned stage/cycle/control state and trace at boundaries, retaining raw CSV/session data, setup, source/module/definition snapshots, returned identity, transport metadata, and cleanup. Final capture inventory is written after closure; an unsealed checkpoint is incomplete. Report generation starts only after sealing and releasing the resource lock. A report error preserves the capture and never repeats acquisition or reopens hardware.

## Invocation

Placeholders, not an instruction to discover hardware while testing documentation:

```bash
.venv/bin/python tools/run_cycle_reference.py \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --setup tmp/my-prepared-wf03-setup.json \
  --output output/reports/new-wf03-physical-capture \
  --confirm-prepared-reference
```

Optional `--report-output NEW_DIRECTORY` publishes after closure; `--report-no-plots` avoids a Matplotlib requirement in the bench environment. A separate isolated reporter can subsequently run `python -m hp437b.repeatability report --bundle CAPTURE --output NEW_REPORT` for plots, without hardware I/O or changing capture provenance. Do not install/upgrade bench dependencies for presentation. Operator precedence is explicit argument, setup name, then `HP437B_OPERATOR`; absent names stay unknown.

Physical import uses explicit mode, prepared setup, firmware/session observations, per-cycle source/dwell evidence, fixed capture bounds, and final free-run/closure validation. Synthetic WF-03 provenance IDs and records remain compatible. Real meter/sensor IDs use the established physical label hashes, while the source identity includes its meter serial to distinguish internal references. The report names POWER REF, retains known issues and the zero baseline, and computes the same equal-cycle statistics without claiming transmitter repeatability or calibration accuracy.

## Verification and selected bench result

**Offline acceptance passed: 761 tests with stress enabled**, including 15 physical-path cases and the unchanged synthetic/WF-01/WF-02 regressions. Injected adapters exercise complete cycling, partial/failure reporting, read/malformed/instrument/policy errors, healthy cancellation, failed/still-on off without retry, failed open/close, initial-on refusal, output/prepared guards, shared locks, stage/cycle/whole deadlines, short-dwell/free-run forgery refusal, and report failure after closure. All fourteen retained WF-03 synthetic provenance records re-import identically. Source/wheel builds and an isolated installed-wheel physical-format saved-report check passed without hardware. Lint, formatting, Markdown links, five original PDF checksums, and `git diff --check` passed. Hosted CI is pending these local changes.

## Current-Mac physical result

Executed November 12, 2026, after fresh owner setup/recovery confirmation. The named adapter descriptor was read without instrument commands; the real run then used the unchanged pinned bench `.venv`: Python 3.14.10, PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. Resource: `USB0::0x03EB::0x2065::GPIB_01_95032313036351A02290::0::INSTR`. The reviewed volatile adapter target operation used owner-reported address 13. Returned instrument firmware 1.8 remains distinct from supplied meter SN 3125U33223 and sensor SN MY41094127. Adapter V2.4, historical factors, and calibration references remain supplied/historical rather than falsely marked freshly queried.

Run `ba164db1-73a5-4745-962c-6f2a64b978c0` started **20:56:38.789 UTC** and finished **21:07:31.832 UTC**, with **652.990 s elapsed** inside the 900 s ceiling. Capture, text/plotted reports, audit, PDF preview, and confirmation supplement are ignored local artifacts under `output/reports/wf03-physical-20261112/` and `tmp/wf03-physical/`; the repository retains this reviewed summary, not raw measurements.

| Observation | Recorded result |
| --- | --- |
| Initial source-off “zero” | Three valid readings; mean −0.0133333 µW; retained, never subtracted |
| Settling observations | Twenty valid rows per cycle; 100 total, excluded from plateau statistics |
| Completed cycles | **5 / 5**, with all source-on, source-off, dwell, baseline, and closure steps complete |
| Plateau samples | **30 valid / 30 attempted in every cycle**, 150 total; zero failed samples |
| Off baselines | Three valid rows per cycle; 15 total, retained separately |
| All measurement rows | 268 valid, including initial baseline and settling/off data |
| C01 mean / min / max | 0.990000 / 0.990 / 0.990 mW |
| C02 mean / min / max | 0.990000 / 0.990 / 0.990 mW |
| C03 mean / min / max | 0.990000 / 0.990 / 0.990 mW |
| C04 mean / min / max | 0.989966667 / 0.989 / 0.990 mW |
| C05 mean / min / max | 0.989900 / 0.989 / 0.990 mW |
| Equal-cycle mean | **0.989973333 mW** |
| Cycle-mean spread | **0.000100000 mW (0.0101012822%)** |
| Sample SD of cycle means | **0.0000434613 mW**, using `n−1` over five means |
| Timing | Each cycle completed in 121.414–121.535 s, within its 180 s cap; every measured off dwell was at least 20 s; maximum plateau gap including window edges 1.011763 s |
| Source/control closure | Exactly five OC1 and five OC0 commands; no retries/transport errors; final source-off, independent free-run/numeric display, and healthy TR3/GTL closure passed |
| Owner final state | Separately confirmed live readings, RMT off, and POWER REF off after closure, in reply to the no-keypress request |
| Measurement acceptance | **Not evaluated**; no DUT spread limits/uncertainty rule supplied; internal-reference-path observations, not transmitter repeatability or absolute accuracy |

The independent 50-digit audit recomputed each mean and the equally weighted aggregate, spread/percent, and sample SD from the original CSV, agreeing to the reporting precision. It verified capture/report hashes, stage/session/raw-frame/value/unit/time joins, source snapshots, cycle budgets, actual off dwell, allowed command set, one activation/deactivation per cycle, absence of transport errors, free-run evidence, and accepted local return in every session. The actual result sheet remains **one page on Letter and A4**, with the pre-RF zero, all cycle rows, plot, current meter issue, and Equipment traceability → Report Harness → Record footer.

Capture inventory SHA-256: `1faa4cd54ff694a019243070ef58ae95227fdf43f0843146a799e670884f77a4`. Plotted report inventory SHA-256: `47ef7e1f420e594875e6a3f1637444664dd4600a51b00da3e677db0f2b485e5a`.

The meter's documented +5 V discrepancy remains visible in setup, provenance, and the one-page report. This completes the selected supervised current-Mac WF-03 POWER REF case. It does not isolate sensor/meter versus reference variation, certify calibration, measure fast keying/PEP/leakage, qualify a transmitter, or imply a Pi/unattended profile.

## Owner confirmation supplement

The owner's supplied final-state confirmation is separate from captured protocol observations. Original sealed records retain their initial pending field; no captured data/report was rewritten to add the later statement. The ignored `run-001-operator-confirmation.json` binds the statement to the capture inventory above. Receipt timestamp and supplement hash follow below.

Confirmation recorded at `2026-11-12T21:09:36.435699+00:00`; supplement SHA-256: `8706877e2e8003bfc5f292c605ba19b2c950d4eab3ce28794443beb44bafc7cf`. No manual recovery or additional meter command was needed after closure.
