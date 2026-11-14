# wspr5 basic diagnostics: current-meter result

November 13, 2026 (capture November 14, 01:06:34–35 UTC). Status: **complete for one supervised basic pass**, including a separate owner final-state confirmation. The owner authorized the run with POWER REF and RMT off, live readings updating, unchanged connections, other control applications closed, no pending operation, and five-minute availability. The [physical runner preparation](DIAGNOSTICS-PHYSICAL-RUNNER.md) and its fake/Pi software checks remain separate evidence.

## Setup and invocation

The adapter remained connected to wspr5. Declared label identities are meter `3125U33223` and sensor `MY41094127`; the existing GPIB address remains 13, without scanning or setting it. The selected resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. The matched identification was HP 437B firmware 1.8, with an empty meter-serial field. Supplied labels remain distinct from observed protocol identity.

The isolated installed package ran on Python 3.13.5, Linux 6.18.60+rpt-rpi-2712/aarch64, using PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. Its runtime hashes matched the delivered manifest before and after testing. The source base is `5200697` plus the prepared uncommitted runner changes, identified by the preparation's delivery/runtime manifest; this does not attribute the new runner to that base commit alone.

A control/worker process check found no active prior meter worker before opening. Exactly one standalone basic invocation used the prior-worker/supervision flags and the existing reconciliation installation's shared workflow-lock directory. There was no `--include-latched-reads` flag. Work/total budgets were 20/25 seconds, with the documented native finish allowance and bounded disposal. No retry or second meter session followed.

## Observed result

The collection returned `completed`, exit code 0, in **0.377248 seconds**.

| Operation | Observed result | Accepted scope |
| --- | --- | --- |
| C030 `*ESE?` | 0 | One zero event-enable-mask response; three ASCII digits plus CR/LF, complete VISA framing |
| C108 `*SRE?` | 0 | One zero service-request-mask response; three ASCII digits plus CR/LF, complete VISA framing |
| C110 `*STB?` | 0 | One zero ASCII status-byte response; three ASCII digits plus CR/LF; not serial polling |
| C067 `OD` | Display text −0.03 µW | Numeric display reply with five leading spaces, ASCII `uW`, and CR/LF; not a fresh triggered power measurement or independent front-panel numeric comparison |
| Cleanup | TR3 followed by USB488 Go To Local accepted | Local profile `xyphro-usb488-gtl-v1`; raw transport closed |
| Worker | Stopped, exit code 0, no forced termination | All four query rows accepted before the deadline |

No error/event/status-latch query (`ERR?`, `*ESR?`, or `SM`), mask setter, clear/reset, zero/CAL, source switch, acquisition trigger, fault injection, or cable action was included. The basic pass does not prove nonzero enable masks, actual event/error clearing behavior, sensor accuracy, or additional commands/parameters.

After Python closed, the owner answered **Yes** to the no-key confirmation of live numeric readings updating, RMT off, and POWER REF off. That supplied observation completes the final-state check; it is stored separately from the original runner receipt. No recovery key or cable action was requested.

## Preservation and evidence

The original Pi logger's runtime bytes, dependency pins, and installation origin matched its pre-run snapshot. The existing udev rule was unchanged, and the isolated installed runtime still matched its delivery manifest. The normal logging implementation, settings, and behavior were not changed for this test.

The remote run is `/home/pi/hp437b-qualification/diagnostics-20261114T005719Z/runs/basic-20261114T010634Z`. The complete retrieved case remains ignored under `output/logs/pi-diagnostics/basic-20261114T010634Z/`, including setup, raw receipt, stdout/stderr, preservation result, and separate owner final confirmation. The local receipt hash matches the remote capture's reported hash, and its exact four-query plan, complete framing, deadline acceptance, successful cleanup, and normal worker exit were independently checked.

| Artifact | SHA-256 |
| --- | --- |
| Original diagnostics receipt | `0f57a75505c98a7e6b4574d5ad4a8d11bb7ecdbd75caff2dc004e8afeb69f10f` |
| Capture/preservation summary | `a8e5b557cb46bf58f138fe1fc461e8f91e4ce1529ccebef397cbcf211ad4cc18` |
| Separate supplied owner final observation | `650414c511dd2e6e01fb52b0e6b9dfa5b52455ad5ad682374bb33a6ff1c05b36` |

The runner receipt retains `front_panel_confirmation: not_provided` and `physical_identity_verified: false`; the later owner observation and declared equipment labels are separate facts. No original receipt was rewritten to manufacture physical evidence.

## Remaining scope

The basic wspr5 case is complete. Optional error/event/status-latch reads require a separately selected pass and retain [A06 lifecycle questions](../inventory/AMBIGUITIES.md#a06). This test does not establish true serial polling, automatic zero/CAL, new recovery cases, binary readback/restore, or Mac acceptance of these added diagnostics queries. Those remain optional scopes from the [review](../inventory/COMMAND-BACKEND-REVIEW.md), not new release requirements.
