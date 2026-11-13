# Bounded reconciliation supervisor: fake implementation

November 13, 2026. Continuation of the owner-requested [fake recovery investigation](UNATTENDED-RECOVERY-FAKES.md), under PI-RECOVER-01. This implements the selected fake-only supervisor experiment; it does not add a release requirement or qualify unattended hardware operation.

The later [supervised physical bridge preparation](RECONCILIATION-PHYSICAL-BRIDGE.md) extends the core through a separate gated entry point. This record preserves the original fake-only delivery evidence; it does not claim hardware acceptance of that later bridge.

## Delivery boundary

The first investigation was committed and pushed to `devel` at `ca80ee18f2ee2639f930a06888430ada8689d9b7`. All four Python 3.11/3.14 jobs [passed CI](https://github.com/lbussy/HP-437B-Automation/actions/runs/43507916420) before supervisor implementation began. The new implementation and checks below are subsequent work, not results from that earlier CI run.

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

The parent bounds worker activity and backoff, including uncooperative fake open/read/close operations. As with existing process supervision, operating-system scheduling, process creation, local file operations, and caller-supplied cancellation code are not hard real-time guarantees. If worker death cannot be confirmed, the result remains operator recovery needed and its worker lease must not be bypassed.

## Fake exercise

The [exercise tool](../../tools/exercise_reconciliation.py) supports three entirely simulated scenarios. Use a fresh output directory each time:

```sh
.venv/bin/python tools/offline_qa.py --seconds 30 -- \
  .venv/bin/python tools/exercise_reconciliation.py \
  --output tmp/reconciliation-demo/example --scenario absent-then-healthy
```

| Exercised scenario | Recorded result |
| --- | --- |
| `healthy` | Communication reconciled, one attempt |
| `absent-then-healthy` | Communication reconciled, two attempts; first attempt sent no instrument command |
| `source-on` | Operator recovery needed, reason `reference_on`, one attempt; reference left unchanged |

All three were exercised with the hardware-access guard enabled. Receipts remain ignored under `tmp/reconciliation-demo/`.

## Verification and limits

The [41 focused cases](../../tests/test_reconciliation.py) passed with real spawned IPC workers and injected transports. They cover successful closure, absent-then-present, attempt exhaustion, denied access, changed adapter/resource/model/firmware/serial, malformed source status, source on, instrument errors, missing/failed/rejected local return, close failure, worker crash, hung open/read/close, late reply, receipt-before-worker-exit, total-budget backoff, cancellation, held supervisor/worker leases, an independently running old child, invalid policies, real-resource rejection, and output preservation. An original failed-evidence file remains byte-for-byte unchanged after a successful reconciliation.

The full hardware-guarded Python 3.14 reporting-environment regression passed **1,513 tests**, with three opt-in stress cases skipped, in 236.09 seconds. It ran outside the filesystem/network sandbox for existing localhost UI checks, with VISA/USB access still blocked by the QA guard.

```sh
tmp/report01/py314/bin/python tools/offline_qa.py --seconds 600 -- \
  tmp/report01/py314/bin/python -m pytest -q
```

Source-distribution and wheel builds passed. A hardware-guarded import from the built wheel then completed the absent-then-healthy scenario with two disposed workers and no workflow resumption. Ruff lint/format checks, Markdown links/anchors/tables, inventory IDs, the five preserved PDF checksums, and `git diff --check` passed.

The reporting CI selection now includes both recovery test files, so the investigation's ReportLab-dependent service-restart cases are selected in that environment as well as the default software suite. CI results must be associated with the supervisor delivery commit; the local checks above are separate evidence from the earlier investigation CI run.

No Mac/Pi USB recovery, already-wedged repair, physical source state, live front-panel behavior, or automatic test continuation is established by these results. A physical adapter bridge and a separately bounded supervised trial remain possible later work if selected. POWER REF-off recovery through a fresh verified connection is also not implemented here. The existing supervised workflow and manual fallback remain available.
