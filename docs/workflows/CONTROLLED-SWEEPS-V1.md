# WF-04–WF-06: Shared-control fake sweeps, v1

Status: implemented, November 12, 2026. Fake-only integration; physical drivers and hardware evidence remain open. Delivered to `devel` at `d2f5584`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43337194421). Normal logging, physical workflow runners, dependencies, and existing CLI defaults are unchanged.

WF-04 output versus setting, WF-05 output versus frequency, and WF-06 supply-voltage sensitivity now reuse the [DUT-CTRL-01 control foundation](EXTERNAL-TRANSMITTER-V1.md). An explicit `controlled` command runs ordered points through transmitter, supply, and voltage-observer fakes, the production `Instrument`/`collect` interfaces, and a fake meter. There is no USB/VISA discovery, physical endpoint, POWER REF control, radio, supply, or AI-provider access. Existing `synthetic` commands continue generating their original v1 fixtures; saved fixtures remain readable.

## Exercise and re-report

Use an isolated environment with the optional `reports` extra. Each output directory must be new:

```bash
python tools/offline_qa.py --seconds 120 -- python -m hp437b.power_setting controlled \
  --scenario compressed --operator 'Example operator' \
  --output output/reports/controlled-setting \
  --report-output output/reports/controlled-setting-report

python tools/offline_qa.py --seconds 120 -- python -m hp437b.frequency_sweep controlled \
  --scenario unequal-corrections --operator 'Example operator' \
  --output output/reports/controlled-frequency \
  --report-output output/reports/controlled-frequency-report

python tools/offline_qa.py --seconds 120 -- python -m hp437b.supply_sensitivity controlled \
  --scenario droop --operator 'Example operator' \
  --output output/reports/controlled-voltage \
  --report-output output/reports/controlled-voltage-report
```

Use `--no-plots` without Matplotlib. `--plan` and `--criteria` retain each workflow's existing structures and decision rules. See [WF-04](POWER-SETTING-V1.md), [WF-05](FREQUENCY-SWEEP-V1.md), and [WF-06](SUPPLY-SENSITIVITY-V1.md) for point inputs, calculations, and criteria. Timing is bounded virtual time, not achieved host performance. Plans and every translated control/model specification are validated before allocating capture output.

Re-report without control calls or reacquisition:

```bash
python tools/offline_qa.py -- python -m hp437b.frequency_sweep report \
  --bundle output/reports/controlled-frequency \
  --output output/reports/controlled-frequency-report-again --no-plots
```

Capture exits 0 on completion, 1 on failed/interrupted execution, and 2 on configuration/storage/publication error. A report of failed evidence can publish successfully while retaining failed execution and unavailable acceptance.

## Shared state and bounded point execution

One in-memory hardware state spans the sweep. Each point first adopts a verified source-off setup, validates identities and restoration conditions, captures a signed pre-RF baseline, configures current limit/voltage/frequency/setting, verifies keying, captures settling and plateau samples, unkeys with readback, captures final baseline, and verifies restoration. The next point inherits the previous final hardware state; the runner does not silently reset it. Repeated anchors remain separate ordered points with distinct run/session IDs.

Every point is a separate finite control session. RF is off and the supply restored between points, including WF-06; this does not model a continuous keyed voltage ramp. Control deadlines, operation limits, RF-on limits, and session limits remain active. The whole sweep is bounded to 900 virtual seconds. Cooperative driver deadlines are not a hard process watchdog.

Failure or interruption stops the sweep immediately. Later points remain unattempted; partial native evidence is retained. There is no automatic retry, reopen, bus clear, or recovery. Existing DUT-CTRL-01 rules govern permitted cleanup: uncertain transfers block later controls, known still-on remains ON, and unverified restoration cannot pass. Initially on RF is neither adopted nor automatically switched off.

`--fault FAULT --fault-point P02` selects an explicit fake fault; `--stop-before P02` tests an ordered interruption. Available faults appear in `controlled --help`. Examples include meter timeout/malformed data, rejected keying, condition mismatch, uncertain shutdown, and restoration failure. No fault injection touches real hardware.

## Evidence, corrections, and provenance

The root format is `hp437b.controlled-sweep.v1`, backend `dut-ctrl01-fake`. Each `points/P01/` child uses the additive external-transmitter v2 format: native production CSV/session pairs, meter trace, replayable control receipts, parent/point joins, simulation model, and initial/final fake hardware snapshots. The original external-transmitter v1 format remains supported.

Root `samples.csv` is a derived analysis projection from saved native rows. It retains the first prebaseline, all point settling/plateau rows, and the last final baseline. Intermediate per-point baselines stay in child evidence. A nominal three-point sweep has 168 native rows and 156 projected rows; neither number includes each logger session's setup acquisition. Import verifies inventories, native frames/settings/counts, control receipt replay, model/context joins, state continuity, chronology, failure stopping, and exact regenerated projection bytes. Evidence hashes detect changed files; they do not authenticate equipment.

WF-05 separates simulated sensor response from supplied calibration factors. Analysis-applied factors are applied once; meter-applied factors are modeled once and checked against the expected fake readback. Model preparation occurs only after source-off preflight and before baseline capture. It changes in-memory simulation state, **not a vendor CAL FAC command or the real meter**. This does not qualify physical calibration programming/readback. Fake source/loss/rating values are simulation inputs, not manufacturer equipment ratings. WF-06 analysis uses observed voltage, not the requested value, and reports RF completion separately from restoration failure.

Reusable PROV-01 records include configured equipment identities, simulated reported identities, supply/observer evidence, point/session references, and producer identity. The compact **RF Output Power Test** report retains operator, DUT, time, signed pre-RF zero, point results, acceptance, shared-control final RF/restoration state, and Equipment → Report Harness → Record footer. Technical evidence stays in the appendix. Zero is descriptive, with no automatic zeroing or subtraction; unavailable baseline remains unavailable. Default acceptance is NOT EVALUATED.

## Acceptance scope and next work

Automated tests cover all three controlled paths, independent numeric oracles, single-application corrections, shared state, repeated anchors, observed-voltage results, failed/unattempted points, cleanup uncertainty, empty baselines, tamper rejection, immutable re-reporting, CLI compatibility, plots, and storage failures. See the [validation record](../VALIDATION.md#shared-control-sweep-integration--november-12-2026) for current results.

This establishes fake control/capture/provenance/report integration only. Physical transmitter/supply/observer drivers, rated fixtures, shutdown qualification, sensor correction programming, and hardware acceptance remain separate work. Normal logger behavior is unchanged.
