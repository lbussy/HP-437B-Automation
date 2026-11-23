# Operator-guided radio sweeps

The software path is implemented. Physical interaction checks on the current meter, SN 3125U22346, remain pending. Configure the actual setup and obtain fresh operator confirmations before selected hardware use; simulation remains separate from physical evidence.

## Test series

Choose **Operator-guided radio sweep** in the local interface. Name the radio/DUT, choose a meter source, and select:

- **Frequency versus power:** every frequency label, with the first drive label held fixed.
- **Drive setting versus power:** every drive label, with the first frequency label held fixed.
- **Frequency × drive setting:** every frequency/drive combination, in frequency-first or drive-first order.

The default frequency labels are 2200m, 630m, 160m, 80m, 60m, 40m, 30m, 20m, 17m, 15m, 12m, 10m, 8m, 6m, 5m, 4m, and 2m. Plans support 1–32 distinct frequency labels and 1–16 distinct drive labels, each up to 60 characters. The default four drive labels are 2 mA, 4 mA, 8 mA, and 12 mA; a fifth or later label can be any supplied setting name. Seventeen frequencies and five drive labels produce 85 points. Labels do not imply a current-to-power conversion or measured frequency. Include exact frequency in the label when useful, such as `20m / 14.0971 MHz`.

In **Manual point confirmation**, Start waits for the first confirmation. At each point, set the radio, enable the prepared test signal, check both labels, and choose **Confirm labels & capture**. The confirmation is specific to that run, point, and a fresh token. Both checkboxes reset at every point and on browser reload. Once confirmed, the runner waits the specified settling period, captures a finite logger session, closes it, saves the result, and waits for the next confirmation.

The interface exposes sample count, interval, and settling time. Limits are 1–1000 samples, 0.1–60 seconds between acquisitions, 0–120 seconds settling, and at most one hour of requested sample time per point. The JSON plan additionally supports a 0.1–30 second operation timeout; the UI uses 10 seconds. Actual receipt timing remains in the native CSV and sidecar; it is not a guaranteed sampling rate.

## Automatic simulation

Select **Frequency × drive setting → Automatic simulation**, choose the nominal output profile, and review the dial and carrier table before Start. The simulation uses the [13 dial frequencies and five drive domains](AUTOMATIC-FREQUENCY-DRIVE-PLAN.md), with test RF calculated as dial + 1,500 Hz. It executes drive first without manual point confirmations and retains the full matrix and per-point outcomes. All readings and source setpoints in this mode are synthetic.

To create and use the same plan from the local client:

```bash
python -m hp437b.guided_client simulation-plan pico-gpio > tmp/pico-matrix.json
python -m hp437b.guided_client --url http://127.0.0.1:8765 start \
  --plan tmp/pico-matrix.json --pdf
python -m hp437b.guided_client --url http://127.0.0.1:8765 export --job-id JOB_ID --no-pdf
```

### Live control prerequisites

The automatic mode currently accepts only the simulated meter. Source inspection covered WsprryPico `05cc90d67442` and the WsprryPi worktree at `617831423808`, which also contains unrelated local edits.

- WsprryPico has authenticated Control/1 finite jobs and GPIO pad observation. A read-only finite-job admission operation and the Mac client for authenticated job control, revision-aware restart, and restoration remain open.
- WsprryPi accepts an absolute custom RF frequency over its bounded-tone command. Transient drive, generation-bound early stop, and read-only point admission remain open.
- The ordinary Pico Si5351 profile admits 8 mA. Extending that profile to 2, 4, and 6 mA requires qualification. RP1 drive masks and all hardware-policy refusals must come from the live owning controller.
- The constructed 52- and 104-point matrices exercise formatting and capture progression. Live ownership, fresh ZERO, RF-off baselines, timed acquisitions inside the active job, and verified device stop and restoration remain prerequisites for the conducted sweep.

## Meter setup

The simulated source is available without equipment configuration. To enable measured captures, launch the service from a qualified host environment with the selected report dependencies and an explicit, locally saved setup file:

```bash
python -m hp437b.operator_ui \
  --runs-dir output/reports/guided-runs \
  --sweep-setup tmp/guided-meter-setup.json
```

Use `--no-plots` when Matplotlib is unavailable. Install the PDF extra for PDF-dependent actions. The combined sweep can run without ReportLab with **Include PDF** cleared. The existing POWER REF launch options can be supplied separately; its prepared direct-reference path is not reused as an external-radio setup.

The base setup JSON has these fields; replace placeholders with the actual resource, label identities, known issues, and RF path:

```json
{
  "resource": "USB0::VENDOR::PRODUCT::SERIAL::INSTR",
  "meter_serial": "Meter label serial",
  "sensor_serial": "Sensor label serial",
  "known_issues": ["Record applicable equipment issues"],
  "fixture": "Describe the actual radio-to-sensor path, attenuation, and limits"
}
```

Loading this file validates syntax without discovering or opening equipment. The service does not accept arbitrary device resources through the browser or HTTP start request. A measured run requires fresh RF-path, meter-preparation, reference-off, and operator-availability confirmations. Follow the [equipment manuals and individual records](../EQUIPMENT.md), including sensor input limits, warm-up, zero/CAL, and applicable frequency factors. Preparation booleans in an older run are not authorization for a new run.

Each point uses the existing `Instrument`, `VisaTransport`, and finite `logger.collect` implementation. It opens the configured meter only after point confirmation and settling, requests absolute W, records identity, transport, initial status, raw frames, receipt timing, cleanup, and closure. For the default external-radio source, POWER REF must be off; the explicit fixed-reference option below requires it on during capture. Reported meter errors stop the point. By default, the meter's existing calibration-factor, offset, and duty corrections are retained. Prepare and record the relevant corrections for each frequency before confirming, or select the optional [automatic 8482A frequency correction](#automatic-8482a-frequency-correction). The application does not apply additional fixture corrections, perform automatic zero/CAL, or subtract a baseline. Reports describe **meter-indicated power at sensor input**. Radio-output power requires the actual RF path and its correction basis to be established separately.

The bench integration is software-tested with injected transports; this is not a new physical host/backend or radio qualification claim. [Existing named Mac/Pi evidence](../VALIDATION.md) retains its recorded scope.

## Stop, failure, and saved evidence

**Stop series** interrupts a pending confirmation or settling wait, or stops before the next acquisition. An acquisition already in progress can take its configured timeout, followed by existing cleanup. The operator turns radio RF off when finished. Failed meter reads, invalid confirmations, and capture/storage failures do not advance to another point. Captured samples remain available; partial points are descriptive and do not count as completed points. Unvisited points remain in the requested denominator. This version does not retry, resume, or restart an interrupted series.

One active worker owns the operator run directory, including while waiting for confirmation. A managed physical sweep also holds the resource's workflow lease through capture closure. Use the same USB resource string and lock root for other HP 437B tools. The CLI uses `--reference-root` to locate `tmp/workflow-locks`; a matching preparation configuration supplies its existing lock root. Reloading the browser reconnects to that worker and pending token. After a service interruption, do not assume the active worker has released its lock or the bench state is restored; reconcile the recorded state before starting another session. A normal service shutdown requests cooperative cancellation.

A sealed capture includes `workflow.json` and each started point's `confirmation.json`, production `samples.csv`, and `samples.csv.session.json`, with a root artifact inventory. The capture binds exact labels/order, plan hash, confirmation timestamp/operator/token, physical or simulated mode, and equipment metadata. Saved-run import checks inventories, native raw values, session/sequence joins, settings, requested coverage, confirmation-before-capture chronology, cross-point closure order, and stop progression. Hashes detect modifications; they do not authenticate operators or equipment.

Reports include mean W/mW and dBm where positive, minimum/maximum, population standard deviation, sample count, and largest recorded receipt gap per point. The full HTML report and CSV retain every requested point. Optional plots show frequency versus power per drive label and drive versus power per frequency label, with categorical label axes and gaps for uncaptured points. The combined workflow defaults **Include PDF** off. Selecting it produces a complete, paginated point table and a portable ZIP. Older callers that omit the PDF choice retain the one-page summary and portable ZIP. HTML, CSV, and JSON are available with either choice. Acceptance remains **NOT EVALUATED** because no acceptance-limit contract is added here.

Regenerate reports from sealed capture without acquiring again:

```bash
python -m hp437b.guided_report \
  --bundle output/reports/guided-runs/JOB_ID/capture \
  --output output/reports/guided-report-again
```

Use a new output directory and pass `--pdf` for the complete combined PDF or `--no-pdf` for HTML, CSV, and JSON only. The operator page can regenerate from the saved combined capture with a fresh PDF choice. Re-reporting does not change source files.

## External orchestration interface

The UI and external clients share the same point-level service API. The runner accepts a `PointGate` interface with `confirm(point, token)` and `cancelled()` methods; `FileGate` bridges the local job supervisor. Future orchestration can coordinate radio changes, then explicitly authorize the pending point through this boundary. The automatic simulation follows a fixed matrix with separate simulated authorization records.

The local HTTP API retains its loopback-only, same-origin, cookie/session-token protections. An external local program can use `hp437b.guided_client.Client`, which establishes the session and supplies those headers:

```python
from hp437b.guided_client import Client
from hp437b.guided_sweep import example

client = Client("http://127.0.0.1:8765")
plan = example()
plan["drives"].append("Custom setting")
job = client.start(plan, operator="Bench operator", meter_mode="synthetic")
state = client.state()
# Poll state for this job until phase == "waiting".
# After the caller verifies the radio's requested frequency and drive:
# client.confirm(job["job_id"], pending_job["prompt"], operator="Bench operator")
# client.stop(job["job_id"])
```

A physical start additionally passes `meter_mode="physical"` and `prepared={key: True for key in PREPARED}` from `hp437b.guided_sweep`, only after freshly checking those setup items. A start returns a job; it does not authorize any point capture. Each confirmation authorizes exactly one point. Cancellation, stale tokens, changed labels, omitted checks, and duplicate confirmations are rejected. The service assigns the authorization timestamp. Inspect `phase`, `prompt`, `point_results`, `outcome`, and `error`; a `finished` report can describe an interrupted or failed series.

| Action | Endpoint | JSON body |
| --- | --- | --- |
| Inspect | `GET /api/state` | None |
| Start | `POST /api/guided` | `plan`, `operator`, `meter_mode`, `prepared`, optional combined `include_pdf` boolean |
| Re-export | `POST /api/report-recovery` | `source_job_id`, optional combined `include_pdf` boolean |
| Confirm point | `POST /api/guided-confirm` | `job_id`, `confirmation` |
| Stop | `POST /api/cancel` | `job_id` |

`confirmation` contains the exact pending `point_id`, `frequency`, `drive`, and `token`, plus `operator`, `frequency_confirmed: true`, and `drive_confirmed: true`. Each POST requires the session cookie, `X-Operator-Token`, JSON content type, and the service's exact Origin/Host. No remote deployment or unauthenticated control endpoint is added.

The CLI client supports explicit external control as well:

```bash
python -m hp437b.guided_client --url http://127.0.0.1:8765 state
python -m hp437b.guided_client --url http://127.0.0.1:8765 start \
  --plan tmp/guided-plan.json --operator 'Bench operator'
python -m hp437b.guided_client --url http://127.0.0.1:8765 confirm \
  --job-id JOB_ID --point-id P001 --frequency 2200m --drive '2 mA' \
  --operator 'Bench operator'
python -m hp437b.guided_client --url http://127.0.0.1:8765 stop --job-id JOB_ID
```

The CLI confirmation checks the supplied point ID and labels against the pending token before posting. It does not advance other points or infer that a radio has changed settings.

## Supervised fixed POWER REF exercise

An explicit launch configuration may additionally contain `"signal_source": "power_ref"`. The default, including older setup files, remains external RF with POWER REF off. This option is confined to GUIDED-01; ordinary logging and the WF-01–WF-03 reference runners are unchanged. A reference-configured service accepts only a drive-series plan with frequency label `50 MHz nominal (POWER REF)` and one to three labels `Repeat 1`, `Repeat 2`, and `Repeat 3`, in that order. Each point permits at most thirty samples, one-second spacing, twenty-second settling, and ten-second operation timeouts.

This is a fixed-source exercise of point authorization, production capture, closure, and reporting. Repeat labels indicate capture order, not changed drive or independently measured frequency. The report explicitly identifies POWER REF and the supplied fixture/known issues. It does not establish physical frequency/drive sweeps or external radio integration.

Start with the reference off and freshly confirm the prepared direct sensor-to-reference path, warm-up/correction history, closed other control applications, and operator availability. Start only allocates the series and waits. The operator then turns POWER REF on, allows twenty seconds to settle, and confirms each specific repeat before capture. Native status must indicate reference **on**, with no meter errors. External-radio captures still require reference **off**. Sealed import enforces the same source-specific status and plan rules. No source-control command, zero/CAL, correction change, preset, retry, or automatic restart is added.

The operator must turn POWER REF off after finishing, stopping, or failure and confirm live readings/RMT off/reference off. Stop does not switch RF off. Keep the operator present throughout; no unattended reference-source profile is declared. The normal healthy logger close provides its existing TR3/GTL behavior, while uncertain I/O retains the existing shutdown policy. Capture/report evidence records status at acquisition; final front-panel/source-off observations remain a separate supplement and never rewrite sealed files.

## Automatic 8482A frequency correction

An optional `sensor_correction` field in the physical setup applies the serial-specific chart for **8482A MY41094127** before every confirmed point:

```json
"sensor_correction": {
  "profile": "8482a-MY41094127-20261015",
  "frequency_hz": {
    "30m": 10140200,
    "20m": 14097100
  }
}
```

Add this field alongside `resource`, `meter_serial`, `sensor_serial`, `known_issues`, and `fixture`. Each plan frequency label must have an explicit integer frequency in Hz. No band center is guessed. A mismatched sensor/profile, missing label, or frequency outside the chart's 100 kHz–4.2 GHz span is rejected before the run opens equipment. The chart span does not establish safe input power or extend the sensor's specifications.

Factors come from [certificate page 2](../../output/pdf/hp-437b-8482a/calibration/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf#page=2), linearly interpolated in Hz and rounded half up to the meter's 0.1% grid. At 10.1402 MHz the interpolated factor is 101.098598%, commanded as **101.1%** using `KB101.1EN`. The logger waits for a complete delayed-trigger (`TR2`) setup measurement, then requires error-free SM with offset and duty correction off before retaining samples. Session receipts record the exact frequency, interpolation bracket, unrounded and commanded factors, command, certificate path/page/SHA-256, command completion, and status check. This is an entry-error check, not independent numeric factor readback.

This option does not rerun ZERO/CAL, modify stored sensor tables, change the 99% reference calibration factor, tune the transmitter, apply fixture-loss correction, or subtract RF-off readings. It is available for external RF captures; the fixed POWER REF exercise retains its prior behavior. Without the option, existing correction settings remain unchanged. The Mac must be told each new transmitter frequency through the next point's exact mapping.

Acquisition readiness comes from each complete, parsed numeric reply, not a fixed delay or successful command write. `TR2` waits for internal settling; it does not guarantee external sensor settling after a large RF step. The [manual, printed 3-104/PDF 134](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=134), recommends comparing successive measurements in that case. Its [timing table, printed 1-10/PDF 20](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=20), lists 6.9 s for 128 averages and 27 s for 512 under the stated manual-filter/range-hold conditions. Select an adequate operation timeout (30 s for the current bench run); timeout means uncertain communication and stops progression, rather than indicating readiness or triggering a retry.
