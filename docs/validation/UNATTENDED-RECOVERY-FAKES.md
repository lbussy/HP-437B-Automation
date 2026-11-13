# Unattended recovery: first fake investigation

November 13, 2026. Owner-requested investigation under PI-RECOVER-01. This is software-only evidence and a candidate direction, not unattended hardware acceptance or a change to the supervised profile.

## Starting point and scope

The documentation scope correction was committed and pushed to `devel` at `7c948e0749e873492c55ce38119b09895313f876`. All four Python 3.11/3.14 software/reporting jobs [passed CI](https://github.com/lbussy/HP-437B-Automation/actions/runs/43506268796) before this investigation began. The investigation files described here were subsequent local work, not evidence from that earlier CI run. They were later committed at `ca80ee1`; [all four investigation CI jobs passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43507916420). The subsequently authorized [bounded fake supervisor implementation](BOUNDED-RECONCILIATION-FAKES.md) has its own local record; the candidate discussion below preserves the initial investigation boundary.

The [integrated failed-read shutdown](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) and [Mac verification](MAC-FAILED-READ-SHUTDOWN.md) already establish a named timeout/abort/fresh-session route on both hosts. They do not establish all-fault recovery. This first investigation tests how the existing logger, physical workflow, and operator job supervisor behave around a fault and subsequent session. It adds no production supervisor, automatic reconnection, test continuation, or hardware access.

## Reproducible fake cases

The new [investigation tests](../../tests/test_recovery_investigation.py) exercise production entry points with ordered fake conversations, the existing virtual POWER REF bench, and temporary job records. Twelve restart cases prohibit subprocess launches. The entire run uses the repository's offline hardware-access guard.

| Cases | Fault or boundary | Observed result |
| --- | --- | --- |
| 3 | Timeout, USB-disconnect exception, and malformed measurement after one valid sample | Original CSV retains the valid and failed rows; failed value stays blank; malformed raw bytes remain diagnostic. The session closes, reuse is rejected, and no retry/cleanup commands follow the uncertain transfer. A separate fake session succeeds with a new session ID and accepted TR3/GTL cleanup; all original file hashes remain unchanged |
| 2 | Selected adapter absent or permission denied during fresh connection | One explicit connection attempt fails, with zero measurement rows and no command traffic. Existing logging does not discover an alternative adapter or retry |
| 2 | Wrong model and changed firmware/blank meter serial | A wrong model is rejected. A syntactically valid 437B reply with different firmware is parsed, and its serial can be empty: parsing alone does not establish continuity of the expected physical setup |
| 1 | Fresh communication succeeds while POWER REF status is on | The generic logger reports its observed status and can collect data; it does not impose a recovery-specific source-off policy or switch the source. That is intentional general logger behavior |
| 2 | Timeout or malformed reply while the simulated reference is on | The failed workflow records source state as unknown and closes all fake sessions. The simulator shows the source still on. A fresh workflow refuses it at S00 and never reaches source activation. After an explicit external source-off action in the simulator, a separate workflow succeeds; the failed capture's hashes remain unchanged |
| 12 | Service restarts during starting, waiting, running, or reporting, across physical capture, reference-suite, and report-regeneration records | Previous active state becomes failed. No worker launches, no front-panel confirmation is fabricated, and original request/capture bytes remain unchanged |

The external source-off action above is a test fixture mutation, not a software repair. A fake backend that accepts a fresh connection does not prove that a real wedged adapter will do so. These tests also do not simulate electrical USB/GPIB behavior, actual abort completion, continuous RF state, or a physically live front panel.

## What this establishes

The existing boundaries support preserving a failed run and performing a separate reconciliation session. They correctly prevent an uncertain connection from being reused and prevent service restart from silently continuing a test. The important gap is orchestration and authorization of the next action, not a demonstrated defect in successful logging.

Restoring communication and resuming a test need separate outcomes. A connection that answers identification does not prove that POWER REF is off, the former worker is gone, settings are unchanged, or a connected transmitter has stopped. The meter's identification reply can lack a serial number, so matching model/firmware alone cannot prove continuity of all equipment. An adapter fingerprint and the recorded setup have their own limits.

## Candidate next experiment

The smallest useful next software experiment is a separate, opt-in reconciliation supervisor exercised entirely with fakes. It would stop and preserve the failed run, wait for confirmed worker disposal/exclusive ownership, and try a selected fresh connection within an explicit attempt count and total deadline. It would record identity/setup checks, protocol validity, source state, and healthy closure separately. Missing access, cancellation, changed identity, malformed replies, exhausted budgets, or unsuccessful cleanup would stop it without launching a workflow.

For a future POWER REF-only candidate, switching the reference off through a verified fresh connection could be investigated separately when the failed run demonstrably owned that reference. This would be a new recovery action, not blind cleanup on the uncertain connection. Source-on, source-unknown, stale worker, and ownership-change cases belong in its fake matrix before any physical trial. The present investigation neither implements nor tests that action.

The proposed result is either communication reconciled or operator recovery needed. It would leave the original test failed and preserve the current fresh-preparation/front-panel requirements. Automatic test resumption, reset/clear commands, host reboot, and cable handling are not included. A disconnected or already-wedged adapter may still need the existing manual fallback. These are candidate experiment boundaries, not new project completion requirements.

Broader command support remains a separate requested review; this work does not enable guarded commands or change dependency pins.

## Verification

Using the existing Python 3.14 reporting environment, the following hardware-guarded command passed **136 tests**, including all **22 new investigation cases**, with no skips:

```sh
tmp/report01/py314/bin/python tools/offline_qa.py --seconds 180 -- \
  tmp/report01/py314/bin/python -m pytest -q \
  tests/test_recovery_investigation.py tests/test_transport.py \
  tests/test_instrument.py tests/test_logger.py tests/test_physical_workflow.py \
  tests/test_operator_ui.py tests/test_operator_reference.py
```

The initial base-environment run passed ten cases and skipped twelve because it lacked ReportLab. A sandboxed reporting-environment run then passed 126 cases and hit ten localhost-bind permission failures in existing UI tests. The final run above was outside the sandbox to allow loopback HTTP, retained the offline hardware-access guard, and passed all 136 cases in 21.11 seconds. No physical measurement, USB connection, SSH session, source command to real equipment, or production runtime change occurred.

Ruff lint/format checks and repository documentation/link/checksum checks also passed. Normal logger, CLI, transport, workflow, and interface behavior remain unchanged.
