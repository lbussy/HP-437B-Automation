# WF-02 physical POWER REF integration

Prepared November 12, 2026. The explicit `tools/run_stability_reference.py` runner integrates the [WF-02 stability analysis/report](SUSTAINED-STABILITY-V1.md) with the existing supervised Mac POWER REF control path. Offline integration and actual bench evidence are recorded separately below. Ordinary logger/CLI/defaults, transport, dependency pins, and WF-01 behavior remain unchanged.

## Prepared setup and fixed profile

Require the current Mac adapter, meter and sensor label identities, direct sensor RF input to POWER REF, initial reference off, warmed-up setup, other control applications closed, and an operator available for recovery. These are freshly supplied confirmations, not instrument observations. Retain the setup JSON, calibration references/hashes, factor history, and known meter supply discrepancy. Use [WF-01 setup fields](WF-01-PHYSICAL.md#fixed-run-and-execution-boundary) and the existing named adapter target address when necessary. No transmitter, new signal path, remote zero/CAL, factor change, preset/reset, or induced fault belongs to this run.

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

## Verification and bench record

**Offline integration passed: 700 tests with stress enabled**, including 13 physical-path cases and the unchanged synthetic/WF-01 regressions. The injected-adapter cases cover full capture/report/provenance, source switching and closure, failed reads/malformed responses with no post-fault commands, healthy cancellation, failed/still-on source-off without retry, failed close/open, initial-on refusal, output guards, shared ownership, deadlines, and report failure after sealed closure. Source/wheel builds and an isolated installed-wheel physical-format saved-report check passed without device access. Physical-format layout fixtures remain separate from bench evidence. Lint, formatting, Markdown links, original PDF hashes, and `git diff --check` passed; hosted CI is pending these local changes.

## Current-Mac physical result

Executed November 12, 2026, after the owner freshly confirmed the prepared setup and availability. The named adapter descriptor was read without instrument commands, then the actual bench run used the existing pinned `.venv` (Python 3.14.10, PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1). Resource: `USB0::0x03EB::0x2065::GPIB_01_95032313036351A02290::0::INSTR`. The reviewed volatile target selection used the owner-reported address 13. Returned instrument firmware 1.8 and supplied labels for meter SN 3125U33223 and sensor SN MY41094127 remain distinct observations. Adapter V2.4/factor/calibration history is retained from setup, not falsely marked freshly queried.

Run `75017c9c-a375-482f-894d-da57c90ede77` started **19:22:16.627 UTC** and finished **19:54:13.696 UTC**, with 1,917.021 s elapsed inside the 2,100 s ceiling. Capture, text report, plotted report, independent audit, and PDF preview are ignored local artifacts under `output/reports/wf02-physical-20261112/` and `tmp/wf02-physical/`; the published repository keeps this reviewed summary, not raw measurements.

| Observation | Recorded result |
| --- | --- |
| Source-off baseline before RF | Three valid rows; mean −0.0100000 µW, retained as the report's “zero”; no subtraction |
| Settling observations | Twenty valid rows, excluded from plateau statistics |
| Thirty-minute plateau | **1,792 valid / 1,792 attempted**, zero failed samples; all six bins populated |
| Five-minute bin counts | 299, 299, 298, 298, 299, and 299 |
| Mean sensor-input power | **0.988984933 mW** |
| Observed minimum / maximum | **0.988 / 0.990 mW**; 0.002 mW peak-to-peak |
| First / last bin means | 0.989020067 / 0.988859532 mW |
| Endpoint change | **−0.0162317351%**, relative to the positive first-bin mean |
| Sampled least-squares slope | −0.00000523902 mW/min, using actual host receipt times |
| Actual timing | Median valid spacing 1.00406825 s; receipt span 1,799.12846042 s; maximum gap including edges 1.01229296 s; no post-window receipts |
| Source-off baseline afterward | Three valid rows; mean −0.0366667 µW |
| Source/control closure | All acquisition/control stages completed; one OC1 and one OC0; source-off status verified, independent free-run/numeric display passed, and healthy TR3/GTL closure accepted |
| Measurement acceptance | **Not evaluated**; no DUT drift limits/uncertainty rule supplied; internal reference-path observations, not transmitter or absolute-accuracy results |
| Front-panel state | Owner separately confirmed live readings, RMT off, and POWER REF off after closure, in reply to the no-keypress confirmation request |

The 50-digit independent audit recomputed means, bin means/counts, endpoint change, and actual-time regression from the original CSV, with agreement to the reporting precision. It verified all capture/report hashes, stage/session/raw-frame/value/unit/time joins, source snapshots, allowed command set, single activation/deactivation, absence of transport errors, free-run evidence, and accepted local return for every session. The actual report remains **one page on Letter and A4**, including the pre-RF baseline, current meter issue, and Equipment traceability → Report Harness → Record footer.

Capture inventory SHA-256: `1ed54858dd5f2e9c49fe102077f7f9ea8d4b4bf2d8e869c8db7fc21aac16a950`. Plotted report inventory SHA-256: `b531388176502fa8b33f07dd21929280240262fce8d1c431bb73ef9d9e4d1657`.

The current meter's documented +5 V discrepancy remains visible in setup, provenance, and the one-page report. This accepts the named current-Mac software/source-control/stability-report path within its recorded evidence; it does not isolate reference versus sensor/meter drift, certify calibration, qualify a transmitter, or imply a Pi/unattended profile. Preserve the sealed capture's pending front-panel field; any later owner confirmation is a separately timestamped, hash-bound supplement.

## Owner final-state confirmation

The owner subsequently confirmed live readings, RMT off, and POWER REF off after Python closed. This completes the selected supervised current-Mac WF-02 POWER REF case. The supplied confirmation is separate from protocol observations; original sealed captures/reports retain their initial pending field. The ignored `run-001-operator-confirmation.json` supplement binds that statement to the capture inventory above and records receipt at `2026-11-12T19:58:41.541456+00:00`. Supplement SHA-256: `e2d63a3f9c28581054880c24e0e42f89f16578b4d084c68263cef9f2e1d28d7e`. No additional meter command, manual recovery, or measurement run was needed.

Pre-push compatibility review retained the initial WF-02 v1 synthetic run/DUT/equipment IDs while adding distinct physical identities. All twelve retained synthetic provenance records re-import identically. A dedicated regression check covers those IDs; **701 tests passed with stress enabled** in the final pre-push run. Source/wheel builds and documentation/lint checks passed again. The existing physical capture/report inventories and audit remain unchanged.
