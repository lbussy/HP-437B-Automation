# Current-Mac post-timeout reconciliation

November 13, 2026. Status: ✅ named supervised current-Mac case complete: protocol/abort checks, preserved failure evidence, fresh reconciliation, and separate owner final front-panel confirmation passed. This is one supervised source-off timeout case on the current Mac/meter, not universal or unattended recovery acceptance.

## Authorization and scope

The owner freshly confirmed the [prepared case](RECONCILIATION-POST-TIMEOUT-PLAN.md): USB on this Mac, meter `3125U33223`, sensor `MY41094127`, unchanged direct POWER REF fixture, warmed-up setup, other control apps closed, live display/RMT off, POWER REF off, and availability at the meter for ten minutes. The owner explicitly authorized the single post-timeout test with normal logging unchanged.

Runtime/source hashes matched the frozen manifest at commit `19434103ab448f8e5dc64d29ac4a0a729e5a4300`; pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1 were verified. No meter-control process was active before the case. Fresh source-off healthy preflight passed with normal worker exit. Each phase used the existing shared resource lease and an external process-group ceiling.

Only the external diagnostic Instrument subclass changed its first CSV acquisition deadline to 0.5 seconds; production logger, transport, dependency pins, and normal defaults remained unchanged. The original worker and native abort routine were forwarded by the previously reviewed pass-through USB tracing wrapper. No fake reply, artificial transport delay, additional recovery command, or sample retry was introduced.

## Observed physical results

The captures are under `output/logs/reconciliation-post-timeout/20261113T225803Z/` (ignored). The failed session ID is `5b16494a-c9e1-416d-a5a4-e12273c0bb8c`; the new reconciliation receipt links to that session rather than rewriting its outcome.

| Check | Result |
| --- | --- |
| Healthy preflight | One physical bridge attempt passed in 0.183348 seconds; source off, error-free/free-run status, accepted local return, normal worker exit |
| Fault scope | Exactly one first-CSV 0.5-second acquisition; ordinary setup completed before the fault |
| Original failure | `OperationTimeout` retained; failed acquisition 0.593684 seconds; full fault helper 8.235890 seconds |
| Failed-read shutdown | Existing one-second allowance received the native VisaIOError in 0.087914 seconds; worker disposed, uncertain-state guard made zero extra I/O, normal ASCII cleanup skipped |
| Actual abort | USB input timeout, endpoint 130 (`0x82`), tag 10, successful initiation `010a`, completed empty input drain, exact successful eight-byte status `0100000000000000`, and return from the original backend abort routine |
| Original sample | Exactly one failed CSV row, blank value/raw fields, matching failed sidecar/session; no accepted late measurement |
| Audit release | Complete independent abort/row/disposal audit released exactly one fresh reconciliation attempt |
| Fresh reconciliation | Actual physical bridge, one attempt, `communication_reconciled`, reason `verified`, 0.146450 seconds; matched 437B/1.8 identity, source off and zero measurement/entry errors |
| Status/closure ordering | Pre-cleanup SM showed standby true after the interrupted TR2; the healthy bridge then issued TR3 and accepted GTL before raw close. This SM observation is not an after-cleanup display observation |
| Final worker | Stopped with exit code 0 and no forced termination; no workflow resumed |
| Preservation | All four original fault-artifact hashes and all runtime hashes matched after reconciliation |
| Owner final observation | Owner confirmed live numeric readings updating, RMT off, and POWER REF off after Python closed; recorded separately from the original receipts |

POWER REF remained off throughout. There was no clear/reset, adapter-target change, zero/CAL, correction change, firmware operation, USB/GPIB disconnection, host move, reboot, second fault, or retry of the failed measurement. The new supervisor performed only its named identity/status and healthy TR3/GTL closure sequence. No extra hardware session was opened after the fresh reconciliation.

## Evidence

Raw preparation, frozen hashes, helper copies, USB trace, failed CSV/sidecar, audits, and separate preflight/reconciliation receipts remain ignored in the capture directory. These are current physical results, distinct from the earlier fake cases and earlier healthy-only Mac exercise.

| Artifact | SHA-256 |
| --- | --- |
| Preflight receipt | `ee21214ae4e05ed4436ca166578b5496ddabeb92f9462a1c93b2ebb317152b7f` |
| Fault record | `0032721b3e0e2e1e8256278183e21404457f5b1b820dbdf07765ac6f82efd29c` |
| Failed CSV | `2f578a269b0b24d19b5f3f737de7f52ea4ef188d76b6959fd18453e45fdc33fe` |
| Failed sidecar | `e06e13d0b65c5b85e67517f0fba391f5570d2af9cf8f3db6d05ae46334e5b3ad` |
| USB trace | `4517ae7bd277db164fbae2504e695b4de74bdc6174c239601ce2fa00ad59b966` |
| Fresh reconciliation receipt | `036428c34b3d905611972c10dd12c1e9eb2286ea0944964498b9a0c73147ab1c` |

The supervisor receipt retains its capture-time `front_panel_confirmation: not_provided`. The owner subsequently confirmed live numeric readings updating, RMT off, and POWER REF off. That separate observation closes the named supervised case; it is not a software-generated front-panel claim. `owner-confirmation.json` has SHA-256 `1de30d72f8f467184e181e0786df6aff1390940f688ea5356b4e9aef67649bad`; `audit-final.json` links it to the unchanged reconciliation receipt, original result, and all original failure hashes. No additional hardware session was needed to record this confirmation.

This result does not establish repair of an already-wedged adapter, Pi bridge acceptance, source-on fault recovery, arbitrary USB/host failures, a universal abort-duration bound, automatic continuation, or unattended RF safety. The original failed measurement remains failed. Normal logging remains unchanged.
