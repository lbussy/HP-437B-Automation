# Bounded reconciliation supervisor: fake implementation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Delivery boundary

The [supervisor module](../../src/hp437b/reconciliation.py) provides `run_simulated()`. It requires an explicit `FAKE::` target, expected adapter/437B identification, a spawn-picklable factory marked `simulation=True`, a lock directory, the failed run's ID, and an explicit prior-worker-stopped prerequisite. There is no hardware factory, real-resource mode, logger hook, operator-interface hook, or CLI change. The simulated factory is trusted test code, not a security sandbox; checks run behind the repository's offline hardware-access guard.

Normal logger, transport, command guards, CLI defaults, physical runners, operator confirmations, and dependency pins remain unchanged. The supervisor neither opens the original capture nor changes its outcome. Choose a new receipt directory outside the original bundle. An existing output directory is refused before any connection is attempted.

## Implemented behavior

| Boundary | Implementation |
| --- | --- |
| Worker disposal and ownership | No attempt if prior-worker disposal is not explicitly asserted. A supervisor lease excludes competing supervisors for the same simulated resource and lock directory. Each child holds a separate worker lease through transport close, so another supervisor also refuses an orphaned child's lease |
| Budgets | Default: two attempts, twelve seconds total, four seconds of work per attempt, and 0.25-second retry delay. Policy validation bounds attempts to 1–5, total budget to 2–120 seconds, attempt budget to 0.1–30 seconds, and delay to 0–5 seconds. A 0.75-second disposal reserve is withheld from work time |
| Hung work | Each attempt runs in its own spawned process. Parent polling checks cancellation/deadlines, rejects late receipts, and uses bounded join/terminate/kill phases. A success receipt is insufficient if the child does not exit normally. No further attempt is released when disposal is unsuccessful |
| Retry classification | Retry only a missing-adapter exception during construction/open, followed by successful close and normal child exit. Permission errors, identity changes, malformed/protocol replies, absence after command dispatch, read/close failures, crashes, and expired attempts stop immediately |
| Identity | Match selected simulated resource and adapter identity before instrument commands. Parse the 437B reply and compare manufacturer, model, serial field, and firmware with the supplied baseline. An empty meter serial remains unknown; the receipt explicitly disclaims verified physical identity |
| Source/status | Read SM after identification. Source-on, measurement-error, or entry-error status stops without source writes or another attempt. Source-unknown/malformed status cannot qualify as reconciled |
| Healthy closure | Only an accepted probe proceeds to TR3 and negotiated G008 local return. An unsuccessful GTL reply, GTL exception, or transport-close failure prevents success. Failed probes close only the transport; they do not receive additional ASCII cleanup |
| Cancellation | Before launch, during worker I/O, between attempts, and during backoff. Worker disposal remains required. No subsequent capture/workflow is launched |
| Evidence | Write a separate `reconciliation.json` with baseline, policy, attempts, reasons, worker-disposal facts, timing, and outcome. `workflow_resumed` is always false; front-panel confirmation is never supplied by software |

Only `*IDN?`, `SM`, `TR3`, and negotiated local return occur in the healthy fake conversation. There are no measurement-trigger, source-on/off, preset, calibration, clear/reset, reboot, or cable actions. Outcomes are `communication_reconciled`, `operator_recovery_needed`, or `cancelled`. Reconciliation does not authorize another test or imply absolute measurement accuracy.
