# WF-01 physical POWER REF integration

The software path is implemented. Physical interaction checks on the current meter, SN 3125U22346, remain pending. Configure the actual setup and obtain fresh operator confirmations before selected hardware use; simulation remains separate from physical evidence.

## Fixed run and execution boundary

Use the current meter/sensor and already prepared direct POWER REF path, with POWER REF initially off. Owner confirmation covers Mac USB attachment, direct sensor path, warm-up, closed other control apps, and operator recovery availability. Retain the actual setup input file with identities, known issues, historical factor/preparation fields, and observation dates. Record applicable calibration limitations; software implementation does not establish measurement accuracy.

The fixed profile is source-off preflight and three-row baseline; OC1, twenty-second observation allowance and fresh status; three-row and 300-second source-on captures; OC0 with fresh source-off status; three-row final baseline; independent free-run/numeric OD and normal TR3/USB488 GTL closure. Confirm reference/correction/error/range/filter state before accepting each stage. No remote zero/CAL, factor/range/filter repair, preset/reset, induced timeout, clear/reset, or automatic measurement retry is included. Commands use existing [OC0/OC1](../inventory/COMMANDS.md#c065) and typed Instrument APIs.

Stage/RPC deadlines enforce the definition's finite profile; acquisition work stops before the 900-second outer ceiling to reserve cleanup/finalization. The supervisor signals the runner at 870 seconds and disposes its owned process group by approximately 900 seconds. The existing one-second failed-read allowance remains failure shutdown, not acceptance of a late sample. A workflow advisory resource lock excludes cooperating WF-01 runners; other applications still require owner-confirmed exclusivity.

Complete errors or policy mismatches can permit one bounded source-off cleanup if protocol state is known healthy. An uncertain read/write, failed close, or failed source-off never causes a blind reopen/OC0/retry. Source/local uncertainty is retained for operator recovery. An initial on-state is refused before activation without adopting the source. A complete source-off write followed by still-on status is a failure and is not automatically repeated.

## Outputs and reporting

The runner writes a continuously replaced owned workflow checkpoint and trace at stage boundaries, unchanged CSV/session pairs per capture, physical analysis JSON, Markdown report, finalized artifact inventory, and exact runner/helper/runtime/definition snapshots with licenses/notices. It records returned ID separately from supplied meter/sensor label identity. Calibration references and factors retain their provenance; unknown or historical values are not presented as freshly read settings.

Report outcome, saved-data integrity, and measurement criteria remain separate. Mean/min/max/peak-to-peak/sample SD, actual spacing, valid/failed counts, comparisons, and partial/skipped stages derive from retained rows. No accuracy or compliance threshold is invented. Source-off readings remain descriptive baselines. GTL acceptance and independent free-run/status checks are protocol observations; RMT off/live display and reference off receive a separate owner confirmation after Python closes.

Run only after selecting the physical setup and exclusive host environment. Example invocation (placeholders, not a discovery command):

```bash
.venv/bin/python tools/run_power_reference.py \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --setup tmp/wf01-physical/setup.json \
  --output output/reports/NEW_WF01_RUN \
  --confirm-prepared-reference
```

The setup JSON must affirm `adapter_on_mac`, `direct_sensor_reference_path`, `reference_off`, `warmed_up`, `other_apps_closed`, and `operator_available`, and supply meter/sensor serials and a known-issues list. This is the fixed Mac integration; a Pi run requires its own selected host/setup record. Use offline QA with injected factories for tests; never remove guards to test a physical path. There is no automatic fallback from a failed physical run to synthetic results.

## Offline acceptance before opening

Integration tests exercise the actual runner through explicit fake factories: normal 300-row sustained capture, source-off/on/off sequencing, final free-run check, artifact hashes; malformed/timeout failures with no post-fault open/write/GTL; healthy between-read cancellation and instrument-error cleanup; failed source-off and still-on verification without a second OC0; initial-on refusal; failed-close uncertainty; input/output guards; deadline caps; and advisory ownership. Synthetic tool regressions remain separate.
