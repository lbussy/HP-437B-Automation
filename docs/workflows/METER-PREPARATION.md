# Explicit ZERO/CAL in the local operator interface

Status: implemented with fakes first; software/browser verification recorded below. This is the owner-selected usability extension of the existing local interface, not a new requirement for the POWER REF deliverable. The accepted supervised wspr5 [ZERO](../validation/PI-ZERO-20261114.md) and [CAL](../validation/PI-CAL-FIX-20261114.md) cases remain closed. No new physical run is performed by this implementation work, and normal logging remains unchanged.

## Operator actions

Choose **Meter preparation**, select **Simulation — no hardware** or the explicitly configured local meter, and choose **ZERO** or **CAL**. Click **Run ZERO** or **Run CAL** only after reviewing the chosen operation. Simulation has its own clearly labeled Start action. Switching modes, changing action, checking preparation, or opening the page never starts a runner. The interface never chains ZERO/CAL, adds either before a workflow, changes the measurement CAL FAC, or retries a failed adjustment/read.

ZERO adjusts the stored sensor zero. For the configured meter, freshly confirm POWER REF off, no RF input, live readings, RMT off, no pending operation, warm equipment, closed other apps, operator availability, and authorization for one stored adjustment. It uses the existing 45/50-second work/total bounds and thirty-second completion window.

CAL changes stored calibration gain and its reference factor. Freshly confirm the common setup, direct sensor-to-POWER-REF/SENSOR connection, applicable prior ZERO on the unchanged setup, and the actual sensor REF CAL FACTOR/source. Enter the factor explicitly: 50.0–120.0% in 0.1% steps; there is no default 100% or assumed sensor identity. Changing factor/source clears its confirmation. POWER REF begins off; the existing CAL runner enables/restores it internally. CAL uses the accepted ten-second completion and followup-read windows, 35/40-second work/total bounds, and existing bounded free-run/local handling. It does not repeat ZERO.

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
  "resource": "USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR",
  "expected_idn": "HEWLETT-PACKARD,437B,,1.8",
  "meter_serial": "3125U33223",
  "sensor_serial": "MY41094127",
  "workflow_lock_root": "/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks",
  "known_issues": ["Retain the current meter's documented supply discrepancy in equipment provenance"]
}
```

This example records the existing wspr5 setup, not automatic evidence that those connections are presently correct. No discovery, SSH execution, interpreter selection from the browser, reset, address change, backend upgrade, or access-rule installation is added. The service's Python runs the accepted diagnostic worker and retains its existing pin/descriptor/identity checks. Install the same optional interface/report dependencies already used by the operator service. If physical POWER REF workflows are enabled for the same resource in this service, their checkout lock root and this preparation lock root must match; other existing clients must use the same established resource lease.

## Closure and receipts

Only one job runs in the interface. Physical preparation blocks later starts until the separate front-panel confirmation is recorded after worker closure. The capture lock and shared resource lease prevent confirmation while a surviving native child still owns the meter. Recovery after a service restart retains the unfinished job and pending confirmation without resuming it.

Confirm actual live readings, RMT off, POWER REF off, and no ZEROING/CAL/TRIGGER HOLD/error indication after closure. Use documented manual recovery if necessary before confirming. This attestation is separate from the original runner receipt and binds its SHA-256 when present; it does not promote a failed operation to success. A missing receipt remains explicitly unknown rather than invented.

Each action saves its immutable request, native `capture/diagnostics.json`, a preparation summary, and the separate operator confirmation. **Open preparation receipt** shows a concise human-readable result; **Open raw receipt JSON** exposes original evidence, with a hash check on access. Receipts distinguish simulation, verified protocol observations, uncertainty, failed cleanup, and pending operator confirmation. They are preparation records, not RF Output Power Test reports or calibration-accuracy certificates. No extra PDF/ZIP deliverable is required. History labels preparation separately; it cannot be selected as a transmitter measurement, compared as another RF run, regenerated as a POWER REF report, or assigned DUT pass/fail criteria.

## Verification

Simulation executes the actual bounded diagnostic supervisor/collector with an explicitly injected software transport, without loading VISA/USB or opening equipment. Its native receipt retains `evidence_origin: injected_fake`; the wrapper/HTML labels the source as synthetic. The configuration, HTTP schema/auth, operation/factor/preparation guards, native success/failure/cancellation, shared-lock confirmation gate, hash-bound receipts, and unchanged workflow behavior are tested with fakes. Final verification passed: **2,025 full-regression tests**, with three explicitly opt-in synthetic stress cases skipped, in 370.65 seconds; **96 focused tests** passed. Both source distribution and wheel built under the offline guard. The wheel runtime and all browser assets matched the final source bytes; an offline-installed wheel outside the checkout completed simulated ZERO/CAL through spawned workers and rendered receipts. Its pip installation used the legacy certificate option to avoid the offline guard's rejection of macOS Security-framework loading; no hardware guard or dependency pin was changed. Ruff lint/format, JavaScript syntax, Markdown links/anchors/tables, command matrix/ledger checks, publisher PDF checksums, and `git diff --check` passed. The existing reporting CI matrix now includes the new preparation tests; no push or new hosted CI run was performed in this step.

The real loopback page completed simulated ZERO/CAL HTTP flows and receipt/history access, validated disabled physical Start, reset confirmations on action/mode/factor changes, and retained readable desktop/mobile layouts without page overflow. Final screenshots and logs are retained locally under ignored `tmp/operator-preparation/`. The post-run physical-confirmation screenshots used an explicitly fabricated state, with neither hardware execution nor operator attestation. Independent visual review returned **ship** across the existing direction contract, with no material issues after correcting screenshot capture artifacts. The original palette, typography, tokens, DESIGN.md, and design-system metadata are preserved; the documenter recorded this narrow extension. The preview service was closed after verification.

A later browser-to-meter check, if selected, needs a supervised setup confirmation and the configured local service on the USB host. It is separate UI-route evidence and does not reopen the already closed ZERO/CAL cases or create a new required hardware campaign.
