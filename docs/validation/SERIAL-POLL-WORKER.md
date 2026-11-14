# Isolated serial-poll diagnostic worker

November 14, 2026. Status: **implemented with fakes first; software validation passed; no physical acceptance**. The owner requested this integration after publication and exact-commit CI verification of the [serial-poll investigation](SERIAL-POLL-INVESTIGATION.md). Investigation commit `c3e6d2fc895a7bdf5728162ca77c45529a44401a` was pushed to `devel`; [all four software/reporting CI jobs](https://github.com/lbussy/HP-437B-Automation/actions/runs/43610466653) passed on Python 3.11/3.14 before this worker integration began. Those CI results cover that commit, not this subsequent working-tree implementation.

## Integrated scope

The standalone diagnostics tool now accepts **`--serial-poll-probe`** as one mutually exclusive experiment. It reuses the [existing disposable diagnostic worker](DIAGNOSTICS-PHYSICAL-RUNNER.md), exact-resource shared lease, pin/descriptor/identity checks, parent deadlines, native-finish grace, process disposal, atomic receipt, and raw-close path. No discovery/open occurs in this module at import, from help, or during fake-only QA. Setup and fresh supervision/prior-worker-stop checks are still required before any open.

The diagnostic bridge's private `poll_once` method reuses its existing pinned VISA session/PyUSB interface inside the child. It retains the same one-shot probe across calls, so a second attempt is rejected rather than constructing a new transaction. It does **not** advertise a `serial_poll` capability, alter the production transport or Instrument, remove G015/zero/CAL guards, or hook into normal logging. POWER REF remains off; no reference/mask/correction/resolution setter is introduced.

| Order | Fixed operation | Gate/evidence |
| --- | --- | --- |
| Preflight | Exact adapter and meter identity | Explicit resource and expected ID, no fallback |
| 1 | SM | Source off, free-run, normal operation, measurement/entry errors zero; retain baseline flags/units |
| 2 | *SRE? | Must be zero. A nonzero mask stops before polling; do not change it |
| 3 | *STB? | Retain ASCII byte and raw framing; do not interpret this as true polling |
| 4 | One USB488 probe | Fresh GET_CAPABILITIES, one READ_STATUS_BYTE, one matching interrupt response; preserve nested raw probe receipt even on failure |
| 5 | *STB? | Only after validated USB replies; retain differences without requiring static equality |
| 6 | TR1/read | Consume one ordinary source-off acquisition; reject malformed replies and retain complete instrument-error sentinels |
| 7 | SM | Source off, normal/no-error state; standby after TR1 allowed, interpretation flags match baseline |
| Healthy closure | TR3, GTL, raw close | Accepted local return is not inferred front-panel confirmation |

All seven rows are separate and have unique IDs. Ordinary VISA status metadata is absent on the USB poll row, so the previous ASCII query's status is not mislabeled as the poll result. The physical default remains a 20-second work/25-second total budget, existing two-second native cap, and bounded finish/disposal grace. Fake tests shorten deadlines within the existing runner’s validated bounds. Polling does not add a new dependency or change the normal acquisition/CSV path.

## Failure and acceptance boundaries

Healthy logical stops (nonquiet baseline, nonzero mask, complete measurement error, or changed observed flags) skip the remaining experiment and attempt existing free-run/local cleanup. Native/protocol failures, malformed/mismatched control/interrupt replies, unexpected SRQ tag 1, cancellation, and expired calls send no later experiment or cleanup commands. Raw close/disposal remains permitted. Parent cancellation/deadline wins over a later child reply; all rows must be completed and accepted before deadline, closure must succeed, and the worker must stop without force for `accepted_full_case`.

The top-level `serial_poll_assessment` keeps instrument-poll success, freshness, and procedure completion **false**, even when the selected diagnostic case completes. A valid zero or bit 1 does not prove fresh completion because the inspected adapter firmware can hide GPIB timeout and merge cached SRQ bits. A forced/hung worker may leave only a running/incomplete poll row; absence of a final probe receipt is unknown evidence, not a validated poll. No automatic retry, interrupt drain, reconnect, recovery, or second poll is provided.

Physical final state remains separately operator-observed. The assessment does not claim unattended safety, SRQ-event handling, status-clear/buffer semantics, new host support, or automatic zero/CAL support. No new mandatory release gate is created.

## Fake verification

The new integration tests inject only PyUSB/VISA/backend-version doubles under the hardware-denying QA guard, through the actual bridge and spawned worker. They cover successful zero/nonzero USB frames, before/after ASCII status differences, baseline and service-mask gates, capability/endpoint rejection, malformed/tag-mismatched/rejected/unsolicited replies, native timeouts, failed followup acquisitions/status, changed flags, failed GTL/raw close, cancellation while each native stage is pending, late returns, hard hangs, worker crash, ownership conflicts, lease retention through close, a direct second-poll rejection, CLI/profile/preparation guards, and conservative final assessment.

The first run passed 48 cases, but the sandbox denied the QA launcher's final process-group cleanup. It is not recorded as a clean QA-launcher pass. Two further one-shot/lease cases were added, and the final guarded run is performed outside the sandbox so owned subprocesses can be reaped, without permitting test hardware access. The clean outside-sandbox guarded run passed **289 focused tests in 46.46 seconds**, including **50 new worker/bridge cases**. Full guarded regression passed **1,910 tests in 282.00 seconds**, with three opt-in synthetic stress tests skipped. Guarded wheel/source builds passed; all **54 wheel runtime modules** and changed source-archive runtime/tool/test members matched current source. The final worker-only check passed **50 cases in 18.06 seconds**, including generation of the clarified source-off receipt description. Lint/formatting, Markdown links/IDs, five publisher-manual checksums, and `git diff --check` passed. Normal logger/transport/instrument/CLI, USB488 local-return helper, reconciliation, pins, and udev files remain unchanged. Logs and artifacts remain ignored under `tmp/serial-poll/`. No hosted CI result is claimed for this subsequent uncommitted worker integration.

## Supervised wspr5 preparation

No physical connection was opened, no wspr5 installation was modified, and no bench test was run in this implementation batch. Prepare a fresh isolated source/wheel installation, test its installed package with injected fakes under the offline guard, record runtime hashes/pins, preserve the original logger and permanent USB rule, and ensure all earlier control workers are stopped. Retain the established shared lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`; do not give the new installation a separate lock domain.

Then obtain fresh owner confirmation: adapter USB remains on wspr5, the same meter `3125U33223` and sensor `MY41094127`/connections are unchanged, readings are live, RMT/POWER REF are off, no trigger/zero/calibration is pending, other control apps are closed, and the owner is available about five minutes with PRESET/LOCAL accessible. No resolution-menu check, source activation, radio, extra hardware, or cable move is needed for this source-off case.

Populate the existing setup JSON with explicit expected ID, meter/sensor labels, and the six true `prepared` fields from the runner. Run the standalone tool with exact resource, setup, fresh output path, established shared lock root, `--confirm-supervised`, `--confirm-prior-worker-stopped`, and **only `--serial-poll-probe`** as the experiment. Do not include reference control, latch reads, fixed-error fixtures, or other experiment flags. Do not reuse setup-only assertion text as proof of actual host state.

After Python closes, obtain separate no-key owner confirmation of live numeric readings, RMT off, and POWER REF off. If a transfer fails, stop without a fresh probe; report the receipt and request only the needed front-panel recovery. Success accepts this selected USB exchange/followup on that host, not broad serial-poll semantics or zero/CAL enablement.
