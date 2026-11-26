# Explicit ZERO/CAL in the local operator interface

The software path is implemented. Physical interaction checks on the current meter, SN 3125U22346, remain pending. Configure the actual setup and obtain fresh operator confirmations before selected hardware use; simulation remains separate from physical evidence.

## Operator actions

Choose **Meter preparation**, select **Simulation — no hardware** or the explicitly configured local meter, and choose **ZERO** or **CAL**. Click **Run ZERO** or **Run CAL** only after reviewing the chosen operation. Simulation has its own clearly labeled Start action. Switching modes, changing action, checking preparation, or opening the page never starts a runner. The interface never chains ZERO/CAL, adds either before a workflow, changes the measurement CAL FAC, or retries a failed adjustment/read.

ZERO adjusts the stored sensor zero. For the configured meter, freshly confirm POWER REF off, no RF input, live readings, RMT off, no pending operation, warm equipment, closed other apps, operator availability, and authorization for one stored adjustment. It uses the existing 45/50-second work/total bounds and thirty-second completion window.

CAL changes stored calibration gain and its reference factor. Freshly confirm the common setup, direct sensor-to-POWER-REF/SENSOR connection, applicable prior ZERO on the unchanged setup, and the actual sensor REF CAL FACTOR/source. Enter the factor explicitly in 0.1% steps from 50.0% to 120.0%. Changing the factor or source clears its confirmation. Start with POWER REF off. The meter enables it during CAL and restores it afterward. CAL has a 30-second completion window, a 10-second follow-up read window, and 55/60-second work/total bounds, including return to free-run and local control. Run ZERO separately.

Progress reads the runner's native stage checkpoint. Cancellation writes the existing job marker, which the runner checks within its bounded supervision. An in-flight native call may finish or be disposed; cancellation is neither an immediate reference-off action nor proof that an adjustment did not start. Unknown completion permits no new ASCII/cleanup commands. The existing narrow CAL failed-read shutdown remains disposal-only, preserves failure, and never reuses the uncertain measurement stream.

## Configure a local meter explicitly

By default, only simulated preparation is available. Physical preparation is separately enabled with an operator-controlled setup file on the computer that owns the USB connection:

```bash
python -m hp437b.operator_ui --no-plots \
  --runs-dir output/reports/operator-runs \
  --meter-prep-setup path/to/meter-preparation.json
```

Setup fields (use the actual resource, identities, issues, and established shared lock directory):

```json
{
  "resource": "USB0::0x03EB::0x2065::ACTUAL_USB_SERIAL::0::INSTR",
  "expected_idn": "HEWLETT-PACKARD,437B,,2.0",
  "meter_serial": "3125U22346",
  "sensor_serial": "MY41094127",
  "workflow_lock_root": "/absolute/path/to/shared/workflow-locks",
  "known_issues": []
}
```

This is a setup template for the current meter. Replace the USB serial and lock path, and confirm the actual identification reply before use; software 2.0 is laboratory-recorded, not freshly queried. Record applicable limitations from the [current calibration review](../validation/CALIBRATION-REVIEW.md) in the setup’s known-issues list. No discovery, SSH execution, interpreter selection from the browser, reset, address change, backend upgrade, or access-rule installation is added. The service's Python runs the accepted diagnostic worker and retains its existing pin/descriptor/identity checks. Install the same optional interface/report dependencies already used by the operator service. If physical POWER REF workflows are enabled for the same resource in this service, their checkout lock root and this preparation lock root must match; other existing clients must use the same established resource lease.

## Closure and receipts

Only one job runs in the interface. Physical preparation blocks later starts until the separate front-panel confirmation is recorded after worker closure. The capture lock and shared resource lease prevent confirmation while a surviving native child still owns the meter. Recovery after a service restart retains the unfinished job and pending confirmation without resuming it.

Confirm actual live readings, RMT off, POWER REF off, and no ZEROING/CAL/TRIGGER HOLD/error indication after closure. Use documented manual recovery if necessary before confirming. This attestation is separate from the original runner receipt and binds its SHA-256 when present; it does not promote a failed operation to success. A missing receipt remains explicitly unknown rather than invented.

Each action saves its immutable request, native `capture/diagnostics.json`, a preparation summary, and the separate operator confirmation. **Open preparation receipt** shows a concise human-readable result; **Open raw receipt JSON** exposes original evidence, with a hash check on access. Receipts distinguish simulation, verified protocol observations, uncertainty, failed cleanup, and pending operator confirmation. They are preparation records, not RF Output Power Test reports or calibration-accuracy certificates. No extra PDF/ZIP deliverable is required. History labels preparation separately; it cannot be selected as a transmitter measurement, compared as another RF run, regenerated as a POWER REF report, or assigned DUT pass/fail criteria.
