# Isolated serial-poll diagnostic worker

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

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
