# WF-03 physical POWER REF integration

The software path is implemented. Physical interaction checks on the current meter, SN 3125U22346, remain pending. Configure the actual setup and obtain fresh operator confirmations before selected hardware use; simulation remains separate from physical evidence.

## Setup and fixed sequence

Require fresh owner confirmation of Mac USB attachment, direct sensor RF input to POWER REF and sensor cable to SENSOR, reference initially off, warm-up, closed other control apps, and available front-panel recovery. Retain actual meter/sensor labels, firmware expectation, calibration/factor history, adapter/address/cable, and known issues using the [existing prepared-setup fields](WF-01-PHYSICAL.md#fixed-run-and-execution-boundary). Do not infer labels from USB identity or silently change factors, zero/CAL, preset, reset, range, filter, or correction settings. Record applicable current equipment limitations in measurement provenance.

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
