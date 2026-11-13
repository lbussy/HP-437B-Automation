# DUT-CTRL-01: External transmitter control foundation, v1

Status: fake-control foundation and single-point capture-to-report implementation, November 12, 2026. Physical drivers, device-specific procedures, and hardware acceptance remain open. Normal logger, instrument/transport, existing workflows, dependencies, and CLI defaults are unchanged.

The new path treats an external transmitter as the DUT. Separate transmitter, supply, and voltage-observer interfaces provide identity, condition changes, acknowledgements, state readbacks, and voltage observations. The fake meter uses the existing `Instrument` and production `collect` APIs. POWER REF is never used as the transmitter or controlled by this workflow.

## Run the fake workflow

Use an isolated reporting environment with the optional `reports` extra. Outputs must be new, separate directories. The existing offline guard supplies an additional accident barrier:

```bash
python tools/offline_qa.py --seconds 120 -- python -m hp437b.transmitter_workflow synthetic \
  --scenario nominal --operator 'Bench operator' \
  --output output/reports/external-tx-demo \
  --report-output output/reports/external-tx-demo-report
```

Open `report.html`. Use `--no-plots` without Matplotlib; omit `--report-output` for capture only. Re-report saved evidence without controls or reacquisition:

```bash
python tools/offline_qa.py -- python -m hp437b.transmitter_workflow report \
  --bundle output/reports/external-tx-demo \
  --output output/reports/external-tx-demo-report-again --no-plots
```

Capture exit codes: 0 completed, 1 failed/interrupted, and 2 configuration/publication/storage error. Offline publication may successfully report a failed capture while retaining its failed execution and unavailable acceptance. There is no physical resource, discovery, driver registry, arbitrary command, shell, or AI-provider option.

## Reusable interfaces and ownership

[`dut_control.py`](../../src/hp437b/dut_control.py) defines structural protocols:

| Interface | Operations |
| --- | --- |
| Transmitter | identify, status, configure frequency/setting, set RF on/off |
| Supply | identify, status, set current limit, set voltage |
| Voltage observer | identify, measure voltage at a declared location |

Each operation receives an absolute monotonic deadline. Controls validate identities/types, distinguish command acknowledgement from state/readback verification, and retain every request/reply/error/time/deadline. `Controls` provides once-only preflight, configure, activate, verify, deactivate, and restore phases. `execute` composes these phases with a capture callback; saved-run validation uses the same phase contract with recorded receipts and saved logger sessions, without executing source files or invoking devices.

Only explicit endpoints marked as simulations are currently admitted. No physical endpoint implementation is included. Driver deadlines are cooperative: post-return checks reject late replies, but cannot preempt an uncooperative/blocking driver. A physical runner would need its own qualified timeout/process supervision and device shutdown path.

A session adopts the setup only after matching three expected identities, observing transmitter RF off, confirming enabled supply output/current-limit setting, and independently observing the declared restoration voltage. An initially on or unidentified source is refused and is **not automatically unkeyed or adopted**.

Condition changes require adopted, known source-off state. Configure current limit with readback, set voltage and observe it, configure frequency/setting and reread transmitter state, then permit keying. Acknowledged keying must be followed by an on-state readback; after settling, frequency/setting/on-state and voltage are checked again before plateau capture. Controller status does not independently measure RF frequency or prove absence of RF energy. A current-limit setting/readback is not a current measurement or proof of actual compliance.

These interfaces/guards are reusable for future drivers and workflows. WF-04–WF-06 are not silently migrated to a new runner; their existing synthetic implementations and evidence stay unchanged. This v1 controller deliberately represents one finite, adopted condition per session.

## Configuration and operating bounds

`--plan PLAN.json` accepts the structure returned by `dut_control.default_plan()`:

```bash
python -c 'import json; from hp437b.dut_control import default_plan; print(json.dumps(default_plan(), indent=2))'
```

The versioned plan records DUT name, expected transmitter/supply/observer asset IDs/models/serials, fixed frequency/setting/mode, comparison plane, maximum declared RF output, sensor operating ceiling, fixture identity/input limit/minimum attenuation, optional reported fixture correction/source, supply envelope/condition/current limit/restoration values/observation location, and bounded timing. Names/identities are bounded single-line text. Asset IDs must be distinct, including reserved fake meter/sensor identities.

Default fictional profile: declared 14 MHz, nominal setting, 13 V with a 2 A current-limit setting; initial/restoration state 12 V and 1.5 A current limit. RF bound 10 W, fixture input bound 20 W, minimum attenuation 30 dB, nominal correction 30 dB, and sensor operating ceiling 0.1 W. These are **fictional supplied operating limits, not actual equipment ratings, damage limits, or connection authorization**. Reference/calibration preparation, real sensor limits, and rated fixtures still require device-specific evidence before physical work.

Before output allocation or control operations, validation checks requested/restoration voltages inside the declared envelope, positive bounded current limits, identity separation, RF versus fixture input bound, and worst-case sensor power `max_RF_W / 10^(minimum_loss_dB / 10)` against the supplied operating ceiling. Numeric fields are finite decimal strings; frequency is an integer within the synthetic 100 kHz–4.2 GHz profile. Supply/model bounds are 0.1–100 V and 0.01–100 A. These numerical bounds do not establish hardware support.

Reported fixture correction and minimum safe attenuation are separate facts. Missing correction/source can leave upstream power unavailable while a supplied minimum attenuation still supports the **fake** activation gate. A supplied correction cannot contradict that minimum. DUT-plane watts apply the reported fixture loss once; sensor-plane watts use the already calibrated sensor reading directly. No second sensor factor or baseline subtraction is applied.

The fixed RF simulator generates 5 W (4.8 W for `low-output`) through a fictional 30 dB path. Profiles conflicting with that fake hardware model are rejected before activation; the model is not automatically changed to make a supplied correction look right. Corrections implying upstream power above the declared RF bound cannot pass an upstream criterion. All simulation assumptions remain distinct from returned samples and supplied corrections.

## Finite capture and cleanup

The nominal sequence is:

1. Identify/verify and adopt the source-off setup; capture three source-off baseline rows.
2. Configure/verify supply and transmitter conditions; acknowledge keying and verify on-state.
3. Capture 20 seconds of settling observations, reverify conditions, then capture a 30-second plateau at requested one-second intervals.
4. Make one unkey attempt and verify source-off readback.
5. Restore original declared current-limit setting and voltage, with supply readback and independent voltage observation.
6. Capture three final source-off baseline rows only after successful capture/cleanup.

There are 56 valid logged rows in a nominal run: 3 baseline + 20 settling + 30 plateau + 3 final baseline. Each session also consumes the production logger's setup measurement before initial status. The fake clock advances explicitly; this is neither achieved real-host timing nor a native backend timeout test. Default whole-run ceiling is 120 virtual seconds, RF-on ceiling 60 seconds, per-control deadline 5 seconds, and at most 48 control operations. Finite profiles are validated before operation; guards check deadlines, monotonic clock, and budgets before further work.

Normal meter sessions retain the unchanged TR3/free-run then GTL cleanup. The fake meter rejects OC0/OC1, always reports POWER REF off, and keeps external RF state separate. Signed pre-RF zero is a descriptive indication, never automatic zero or subtraction.

Failed controls are never retried. Uncertain transfers, late replies, malformed control readbacks, or meter timeout/malformed frames block subsequent control operations; active RF becomes unqualified and supply restoration is not asserted. No reopen, clear/reset, blind unkey, or supply change is attempted after that uncertainty. The last observed voltage/current-limit values remain evidence, **not a claim of current restored state**.

Complete instrument errors, sensor-overrange frames, and between-read cancellation can retain healthy protocol state, permitting one owned-source unkey/verification and distinct restoration action. Accepted source-off followed by still-on readback remains known ON; it is not retried and prevents supply changes. Restoration mismatch/failure fails overall execution even when all plateau samples are valid. An initial unowned on-state is left alone.

CSV reservation/finalization failures still close the owned meter session and run permitted control cleanup. Missing/unfinalized session evidence produces no successful capture inventory; preserved workflow/control evidence can be inspected, but that unsealed capture is not accepted for reporting. A report storage error preserves the sealed capture and can be retried to a new report directory, without reacquisition.

## Results, provenance, and reports

Capture includes an immutable starting record, finalized workflow, control receipts/phase outcomes/final state, meter trace, original production CSV/session pairs under `stages/`, and a final atomic artifact inventory. Import validates file hashes, schema/mode, external-DUT/source/session/run joins, exact logger settings/counts/units/raw frames, meter reference/correction state, healthy versus uncertain cleanup, control requests/replies/deadlines/phase order, skipped stages, and final state. It replays **data receipts**, not physical commands. Hashes detect changed evidence; they do not authenticate devices or calibration.

PROV-01 records retain supplied DUT/fixture/condition facts separately from simulated identity readbacks, with stable equipment IDs and evidence pointers. The DUT kind is `external_device`, not the internal reference source. Missing identities/corrections remain unknown. A POWER REF bundle cannot be reinterpreted as transmitter evidence.

Analysis retains sensor mean/range/sample SD, corrected comparison-plane mean, receipt spacing, valid/failed counts, all stage results, and pre-RF baseline. A complete plateau has 30 valid samples. Partial samples remain descriptive, and failed controls/cleanup prevent overall PASS. Default acceptance is **NOT EVALUATED**. Optional `--criteria CRITERIA.json`:

```json
{
  "source": "Fictional DUT specification r1",
  "target_W": "5",
  "max_abs_error_percent": "5",
  "min_samples": 30,
  "max_gap_s": "1",
  "decision_rule": "inclusive-no-guard-band"
}
```

Targets are watts at the declared comparison plane. Percent error is `100 × (measured − target) / target`. Limits are inclusive; criteria also require complete execution, supported corrections, positive power in the nominal sensor range/operating ceiling, and sufficient sample/timing coverage. No uncertainty/accuracy verdict is implied by this unguarded rule. The nominal oracle is 0.005 W sensor input → 5 W at the DUT with 30 dB correction; low-output is 4.8 W, −4% versus 5 W. Sensor-plane results never receive fixture multiplication.

Publication produces one-page `report.html`/`report.md`, PNG/SVG when requested, deterministic `results.json`, `provenance.json`, producer metadata, complete `appendix.html`, and final artifact inventory. The **RF Output Power Test** page shows DUT/operator/time, declared condition/plane, signed pre-RF zero, output/count/acceptance, control limitations, final RF state, and restoration. Equipment → Report Harness → Record footer order and tag-aware producer identity remain unchanged. Full commit/source hashes remain in metadata.

## Validation and remaining work

Twenty-one end-to-end scenarios: nominal, low-output, missing-loss, sensor-plane, identity-mismatch, initial-on, current-mismatch, voltage-missing, frequency-mismatch, key-rejected, source-still-on, source-off-failure, restore-mismatch, restore-failure, observer-timeout, late-reply, meter-timeout, meter-malformed, instrument-error, cancel, and sensor-overrange. Tests additionally cover ownership, once-only actions, deadlines/RF-on budget, clock validation, real logger/session/raw-frame use, criteria, unsealed capture storage failure, saved-evidence replay/corruption, output protection, and installed reporting.

Local campaign evidence is ignored under `output/reports/dut-ctrl01-synthetic-20261112/`; totals are in [VALIDATION](../VALIDATION.md). This work is local until separately committed/pushed and checked in hosted CI.

Next physical work requires selected transmitter/supply/observer hardware and documented driver commands, actual fixture/sensor ratings/corrections, device-specific observation and safe-shutdown procedures, timeout/resource supervision, and scoped hardware acceptance. Independent shutdown after a meter fault is **not qualified** by these fakes. Manual-control UI/acknowledgement flows and physical drivers are not implemented here. Equipment exchange does not block this fake-control software milestone; normal logging and the existing physical POWER REF workflows remain unchanged.
