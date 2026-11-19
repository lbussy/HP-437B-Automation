# WF-02 physical POWER REF integration

The software path is implemented. Physical interaction checks on the current meter, SN 3125U22346, remain pending. Configure the actual setup and obtain fresh operator confirmations before selected hardware use; simulation remains separate from physical evidence.

## Prepared setup and fixed profile

Require the current Mac adapter, meter and sensor label identities, direct sensor RF input to POWER REF, initial reference off, warmed-up setup, other control applications closed, and an operator available for recovery. These are freshly supplied confirmations, not instrument observations. Retain the setup JSON, calibration references/hashes, applicable factors, and current equipment limitations. Use [WF-01 setup fields](WF-01-PHYSICAL.md#fixed-run-and-execution-boundary) and the existing named adapter target address when necessary. No transmitter, new signal path, remote zero/CAL, factor change, preset/reset, or induced fault belongs to this run.

The fixed sequence is source-off preflight; three baseline readings; OC1 with a completed setup probe/fresh source-on status; twenty seconds of retained settling observations; 1,800-second acquisition-start plateau; OC0 with fresh source-off status; three final baseline readings; independent free-run/status/numeric-display verification; healthy TR3/USB488 GTL close; sealed capture and optional deterministic report. Settling data is excluded from plateau drift. Reference nominal frequency/power remain declared, not independently calibrated observations.

Each fresh session records identification, raw protocol/status observations, transport metadata, and shutdown outcomes. Instrument firmware is checked against the setup; meter/sensor serial labels remain supplied and distinct from returned identity. Initial reference-on is refused without adopting/switching the source. Settings, source, errors, automatic range/filter, and absolute W preconditions are checked using existing APIs rather than silently repaired.

The acquisition requests one-second spacing and ten-second operation timeouts; actual spacing/counts are reported. Stage caps are 60 s preflight, 90 s per baseline, 30 s activation, 60 s settling, 1,840 s plateau including setup/closure, 20 s source-off, and 20 s final free-run. The 2,100 s whole-run ceiling takes precedence over their sum. Work stops at 2,010 s to reserve cleanup/finalization; a new duration capture requires its full window plus 30 s remaining stage budget. Cleanup gets at most 20 s and finalization reserves the last 30 s. The outer supervisor signals at 2,070 s and disposes its owned process group by approximately 2,100 s. A terminal output or returned USB status alone is not a front-panel observation.

## Failure policy

Reuse WF-01's recorded-wire and instrument policy without changing them. Complete instrument errors or a healthy between-transaction cancellation can permit one bounded source-off verification after owned activation. Uncertain read/write/close, failed source-off, or still-on verification never cause a blind reopen, OC0 retry, or automatic measurement restart. Source/local state and partial/skipped captures retain uncertainty. The named adapter target operation is confined to the existing reviewed volatile selection, not a meter address change or reset.

The shared advisory lock also excludes a cooperating WF-01 runner on the same explicit resource; other applications still require owner-confirmed exclusivity. Reporting starts after all capture sessions close and the resource lock is released. A report failure preserves the sealed capture, never reacquires or reopens hardware, and can be retried into a new report directory. A killed process/checkpoint without a final capture inventory is incomplete and needs operator source/local reconciliation.

## Invocation

Example placeholders; do not discover or open a resource merely to test documentation:

```bash
.venv/bin/python tools/run_stability_reference.py \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --setup tmp/my-prepared-wf02-setup.json \
  --output output/reports/new-wf02-physical-capture \
  --confirm-prepared-reference
```

Optional `--report-output NEW_DIRECTORY` publishes the deterministic report after closure. `--report-no-plots` avoids a Matplotlib requirement in the bench environment; a separate reporting environment may generate plots from the sealed capture afterward using `python -m hp437b.stability report --bundle CAPTURE --output NEW_REPORT`. Operator selection is explicit argument, setup record, then `HP437B_OPERATOR`; unknown remains unknown. Do not install or upgrade bench dependencies just to render a report.

Physical capture/import uses the WF-02 v1 schema with explicit physical mode, prepared setup, control-stage outcomes, returned session identity, final free-run evidence, and protocol versus front-panel confirmation separation. The report identifies POWER REF, carries actual meter/sensor labels and known issues, and never presents physical data as synthetic or as a transmitter test. Existing synthetic records and commands remain supported.
