# Operator-guided radio sweeps

Status: delivered to `devel` at `d64617f`, November 13, 2026; [Python 3.11/3.14 software/reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43433860223). Physical bench execution remains a separate acceptance step. The guided runner uses the production meter logger, with a fresh operator confirmation before every point. The earlier WF-04/WF-05 synthetic workflows retain their existing five-point contracts.

## Test series

Choose **Operator-guided radio sweep** in the local interface. Name the radio/DUT, choose a meter source, and select:

- **Frequency versus power:** every frequency label, with the first drive label held fixed.
- **Drive setting versus power:** every drive label, with the first frequency label held fixed.
- **Frequency × drive setting:** every frequency/drive combination, in frequency-first or drive-first order.

The default frequency labels are 2200m, 630m, 160m, 80m, 60m, 40m, 30m, 20m, 17m, 15m, 12m, 10m, 8m, 6m, 5m, 4m, and 2m. Plans support 1–32 distinct frequency labels and 1–16 distinct drive labels, each up to 60 characters. The default four drive labels are 2 mA, 4 mA, 8 mA, and 12 mA; a fifth or later label can be any supplied setting name. Seventeen frequencies and five drive labels produce 85 points. Labels do not imply a current-to-power conversion or measured frequency. Include exact frequency in the label when useful, such as `20m / 14.0971 MHz`.

Start never captures the first point automatically. At each point, set the radio, enable the prepared test signal, check both labels, and choose **Confirm labels & capture**. The confirmation is specific to that run, point, and a fresh token. Both checkboxes reset at every point and on browser reload. Once confirmed, the runner waits the specified settling period, captures a finite logger session, closes it, saves the result, and waits for the next confirmation.

The interface exposes sample count, interval, and settling time. Limits are 1–1000 samples, 0.1–60 seconds between acquisitions, 0–120 seconds settling, and at most one hour of requested sample time per point. The JSON plan additionally supports a 0.1–30 second operation timeout; the UI uses 10 seconds. Actual receipt timing remains in the native CSV and sidecar; it is not a guaranteed sampling rate.

## Meter setup

The simulated source is available without equipment configuration. To enable measured captures, launch the service from a qualified host environment with the optional PDF/report dependencies and an explicit, locally saved setup file:

```bash
python -m hp437b.operator_ui \
  --runs-dir output/reports/guided-runs \
  --sweep-setup tmp/guided-meter-setup.json
```

Use `--no-plots` when Matplotlib is unavailable. ReportLab remains required by the operator service. The existing POWER REF launch options can be supplied separately; its prepared direct-reference path is not reused as an external-radio setup.

Setup JSON has these exact fields; replace placeholders with the actual resource, label identities, known issues, and RF path:

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

Each point uses the existing `Instrument`, `VisaTransport`, and finite `logger.collect` implementation. It opens the configured meter only after point confirmation and settling, requests absolute W, records identity, transport, initial status, raw frames, receipt timing, cleanup, and closure. POWER REF must be off, and reported meter errors stop the point. The meter's existing calibration-factor, offset, and duty corrections are retained. Prepare and record the relevant corrections for each frequency before confirming. The application does not interpolate factors, apply additional fixture corrections, perform automatic zero/CAL, or subtract a baseline. Reports describe **meter-indicated power at sensor input**. Radio-output power requires the actual RF path and its correction basis to be established separately.

The bench integration is software-tested with injected transports; this is not a new physical host/backend or radio qualification claim. [Existing named Mac/Pi evidence](../VALIDATION.md) retains its recorded scope.

## Stop, failure, and saved evidence

**Stop series** interrupts a pending confirmation or settling wait, or stops before the next acquisition. An acquisition already in progress can take its configured timeout, followed by existing cleanup. The operator turns radio RF off when finished. Failed meter reads, invalid confirmations, and capture/storage failures do not advance to another point. Captured samples remain available; partial points are descriptive and do not count as completed points. Unvisited points remain in the requested denominator. This version does not retry, resume, or restart an interrupted series.

One active worker owns the operator run directory, including while waiting for confirmation. Reloading the browser reconnects to that worker and pending token. After a service interruption, do not assume the active worker has released its lock or the bench state is restored; reconcile the recorded state before starting another session. A normal service shutdown requests cooperative cancellation.

A sealed capture includes `workflow.json` and each started point's `confirmation.json`, production `samples.csv`, and `samples.csv.session.json`, with a root artifact inventory. The capture binds exact labels/order, plan hash, confirmation timestamp/operator/token, physical or simulated mode, and equipment metadata. Saved-run import checks inventories, native raw values, session/sequence joins, settings, requested coverage, confirmation-before-capture chronology, cross-point closure order, and stop progression. Hashes detect modifications; they do not authenticate operators or equipment.

Reports include mean W/mW and dBm where positive, minimum/maximum, population standard deviation, sample count, and largest recorded receipt gap per point. The full HTML report and CSV retain every requested point. Optional plots show frequency versus power per drive label and drive versus power per frequency label, with categorical label axes and gaps for uncaptured points. The one-page PDF summarizes coverage and observed point means; the portable ZIP includes the full reports and sealed original evidence. Acceptance remains **NOT EVALUATED** because no acceptance-limit contract is added here.

Regenerate reports from sealed capture without acquiring again:

```bash
python -m hp437b.guided_report \
  --bundle output/reports/guided-runs/JOB_ID/capture \
  --output output/reports/guided-report-again
```

Use a new output directory. Re-reporting does not change source files.

## External orchestration interface

The UI and external clients share the same point-level service API. The runner accepts a `PointGate` interface with `confirm(point, token)` and `cancelled()` methods; `FileGate` bridges the local job supervisor. Future orchestration can coordinate radio changes, then explicitly authorize the pending point through this boundary. There is no radio-specific dependency in the runner or report model.

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
| Start | `POST /api/guided` | `plan`, `operator`, `meter_mode`, `prepared` |
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
