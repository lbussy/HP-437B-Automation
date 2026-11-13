# OPERATOR-REF-01: POWER REF in the local interface

Status: implemented locally and tested offline; [current-Mac WF-01 browser execution passed](../validation/OPERATOR-WF01-20261113.md), including owner final-state confirmation. [Current-Mac WF-03 browser execution also passed](../validation/OPERATOR-WF03-20261113.md), including owner final-state confirmation. WF-02 browser execution remains pending. Delivered to `devel` at `80f625d`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43427245573). The [local operator interface](OPERATOR-UI-V1.md) now offers the existing supervised current-Mac [WF-01](WF-01-PHYSICAL.md), [WF-02](WF-02-PHYSICAL.md), and [WF-03](WF-03-PHYSICAL.md) runners, alongside the unchanged fake transmitter suites. Normal logging, main CLI, physical runner source, transport, and base dependency pins are unchanged.

## Enable the selected bench path

This integration requires the trusted source checkout, existing bench Python, a retained equipment/setup JSON, and an explicit USB resource. It does not discover devices, scan GPIB addresses, or install/upgrade the bench environment. Use the existing optional reporting environment to serve the page; the separately selected bench Python performs capture.

```bash
python -m hp437b.operator_ui --port 8765 \
  --runs-dir output/reports/operator-runs \
  --power-ref-setup path/to/retained-setup.json \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --bench-python /absolute/path/to/bench/.venv/bin/python \
  --reference-root /absolute/path/to/trusted/source/checkout
```

Install the existing optional `reports,pdf` extras in the reporting environment; `--no-plots` omits individual plots. A wheel can serve fake suites independently, but POWER REF execution requires this source checkout and a bench interpreter able to import its current `hp437b.operator_reference` module. Keep the checkout/environment operator-controlled. The browser supplies no script paths, interpreter, resource, address, or timing overrides. Normal startup without the three explicit bench options remains fake-only.

The retained setup supplies meter/sensor label identities, known issues, firmware expectations, factors/calibration history, and the existing explicitly selected volatile adapter target if applicable. It must satisfy the same source runner validation. Historical preparation booleans do not authorize a new run: every browser start supplies fresh confirmations and records its UTC time and origin alongside the retained facts. The page shows the configured resource, serials, and known issues. This does not establish their present physical validity.

## Run from the page

Choose **POWER REF — current meter**, then one workflow:

| Workflow | Fixed existing profile |
| --- | --- |
| WF-01 | Source-off zero, short/reference-on output, five-minute plateau, reference-off baseline, and final free-run/local checks; typically about seven minutes |
| WF-02 | Source-off zero, settling, thirty-minute plateau, reference-off baseline, and final checks; typically about thirty-two minutes, 2,100-second outer ceiling |
| WF-03 | Source-off zero, five reference on/off cycles, final baseline/free-run/local checks; 900-second outer ceiling |

Confirm all six setup items for each run: USB on this Mac; sensor cable on SENSOR and sensor RF input directly on POWER REF; reference initially off; warmed up; other control apps closed; operator at the meter and able to use PRESET/LOCAL recovery. Enter an operator name if desired, then press **Start POWER REF workflow**. Checking items or changing mode never starts capture. Confirmations clear after Start or switching mode.

One workflow runs at a time. Progress reports native stage starts/completion from the atomic checkpoint; it does not invent live samples. Source switching, automatic range/filter/unit preconditions, timeout policy, TR3/GTL closure, and uncertain-I/O handling remain in the existing runner. There is no transmitter/supply control, zero/CAL, factor adjustment, retry, reset, or fallback to synthetic data.

## Cancellation and closure

**Request cancellation** writes a marker checked before the next native stage begins. The current acquisition stage completes first; **WF-02 may therefore continue its current plateau for up to thirty minutes**. The runner then applies its existing bounded healthy source-off cleanup policy. Cancellation is not an immediate RF-off control. Uncertain I/O still forbids blind source-off/reopen/retry and requires the documented manual recovery.

The bridge retains each runner's outer budget: signal the owned capture child thirty seconds before the 900/2,100-second ceiling; reserve bounded cleanup, then dispose the still-running owned group if needed. This existing deadline policy is separate from an ordinary cancellation request. Expiry/forced disposal is uncertain, not proof of source off or local control. The inherited root lock and separate capture lock prevent a still-running child from being mistaken for a closed run. Ctrl-C on the service requests cancellation and waits up to thirty seconds; a finishing worker can continue, retaining ownership. Keep the service and operator present through closure.

After Python closes, inspect the actual display and record **live numeric readings, RMT off, and POWER REF off** in the separate confirmation panel. Use PRESET/LOCAL/manual recovery if necessary before confirming. Protocol observations and this operator attestation remain distinct. The pending physical result stays visible, and no further job may start until confirmation is recorded. No automatic resume occurs after a service failure.

## Reports and provenance

Native capture files and their original inventories remain unchanged. After closure, verified native readers produce the existing full report plus a compact one-page **RF Output Power Test** PDF and portable ZIP. The summary includes the signed pre-RF zero, measured output/stability/repeatability, operator/time, protocol final state, known equipment limitations, and Report Harness identity. It identifies internal POWER REF rather than implying a transmitter test or accuracy/compliance verdict. Acceptance remains NOT EVALUATED for these fixed profiles.

The portable manifest and readme retain physical mode, not synthetic labeling. Native reports/provenance remain linked under `native/`; saved evidence is under `evidence/` in the ZIP. Hash/path/identity checks and no-overwrite publication remain required. `operator-confirmation.json` is a separate job-level attestation tied to the capture inventory hash (or explicitly no sealed capture after failure). It is outside the sealed capture/report/ZIP, which continue to record front-panel confirmation as pending at report creation; no existing result is silently rewritten.

A failed report preserves the capture and does not repeat measurement. Publish into a fresh destination without hardware access:

```bash
python -m hp437b.reference_report --workflow WF-01 \
  --bundle output/reports/operator-runs/JOB_ID/capture \
  --output output/reports/recovered-reference-report --no-plots
```

This creates the PDF and sibling ZIP. Verify packages with the existing `python -m hp437b.report_delivery verify --package FILE.zip`. Unsealed captures require inspection and source/local reconciliation, not blind re-report or restart.

## Validation boundary

Injected transports exercised all three actual physical runners, signed baseline/results, closure, stage-boundary cancellation, immutable evidence, native readers, one-page PDF text, physical-mode package verification, tamper refusal, bridge publication after closure, HTTP confirmation, and root/capture ownership gates. Browser checks used an explicitly injected preview and never clicked physical Start. See [validation results](../VALIDATION.md#power-ref-operator-integration--november-13-2026).

The current-Mac WF-01 and WF-03 browser routes now have completed captures, verified reports/packages, independent audits, and separate owner front-panel attestations. Existing command-line bench evidence remains valid within its recorded scope; WF-02 browser execution remains a separate future exercise. Pi execution, external DUT controls, remote access, and unattended hardware recovery remain outside this integration.
