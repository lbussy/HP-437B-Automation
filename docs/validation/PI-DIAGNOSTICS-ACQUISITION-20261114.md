# wspr5 acquisition-setting batch: partial result and restoration-read timeout

November 14, 2026. Status: **partial physical observations; batch not accepted**. The [fake-first profile](DIAGNOSTICS-ACQUISITION-SETTINGS-FAKES.md) stopped after its first remote-resolution/filter expectation failed, attempted known-setting restoration, and then encountered a native timeout. No retry or fresh instrument probe was performed. Normal logging is unchanged.

## Authorization, setup, and provenance

The owner supplied original **RES2**, viewed and exited without changes, then confirmed unchanged wspr5 connections, POWER REF/RMT off, live readings, other apps closed, and five-minute availability. The prepared direct-reference/warmed-up setup and remote reference control were confirmed in context. Supplied labels remain meter `3125U33223` and sensor `MY41094127`; actual ID was HP 437B firmware 1.8 with an empty serial field. Expected resource: `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`.

One invocation used `/home/pi/hp437b-qualification/diagnostics-acquisition-20261114T142141Z`, after runtime/pin and no-prior-worker checks, with the existing shared exact-resource workflow lock. Build provenance is base `7dcf815e4da16991289ca597ddb5a10853c4ce46` plus modified runtime hashes, not a fabricated later commit. Delivery SHA-256: `6a1c9fd28054975ab1c8a3a3e5a95334191be4da530ca7d3fe1d826518080c26`. The isolated installation previously passed **387 guarded tests in 107.77 seconds**, with original logger/udev preservation verified.

Host: Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41; pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. No dependency or normal-logger change was made.

## Exact observed sequence

The pass ran at **14:27:52.299189–14:28:15.010277 UTC**, ending in **22.711192 seconds**, CLI exit 1, status `query_failed`. Of 49 planned rows, **13 completed, one failed, and 35 were not attempted**. The process returned a failed-case receipt normally; its worker exited 0, was not forced, and transport closed. A normal worker exit is not a successful experiment.

| Phase | Actual observation |
| --- | --- |
| Baseline SM | Reference off, normal operation, no errors, free-run, absolute W, no offset/duty correction; auto range code 11 and auto filter code 17 |
| Reference | OC1 accepted; fixed 20-second wait completed; TR1/read returned `+0.9950E-03` W (0.9950 mW), without error sentinel |
| Reference SM | Reference on, standby after TR1, no errors; auto range 13 and auto filter 11 |
| First resolution case | FM4EN and RE1EN writes accepted; TR1/read again returned `+0.9950E-03` W |
| Resolution-case SM | Reference on, standby, no errors; auto range 13, **manual filter code 02 (count 4)** rather than the expected auto-filter mode |
| Restoration writes | OC0, RE2EN, RA, and FA writes accepted, in that order |
| Restoration acquisition | TR1 read failed with `VisaIOError: VI_ERROR_TMO (-1073807339)`; no reply bytes captured and no VISA success/read-status value available |
| Remaining work | No restoration SM, no global TR3/GTL cleanup, no subsequent main cases, and no retry/probe after the timeout |

The initial status mismatch caused the planned healthy-communication restoration attempt. The later native timeout stopped further commands and used raw close. Its failed row arrived before the global deadline; that is a timely error receipt, not a successful acquisition. No main/total budget exhaustion is inferred. The receipt conservatively retains `reference_may_be_on: true`, `auto_modes_reference_off_verified: false`, and `accepted_full_case: false`, despite the earlier accepted OC0/RE2/RA/FA writes.

## Interpretation and remaining scope

The **remote RE1 write did not produce the anticipated auto-filter observation in this sequence**. Its effective resolution value was not independently read between RE1 and restoration, so the cause is unresolved. The [filter manual, printed 3-62/PDF 92](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=92), describes auto-filter enabling when resolution is modified using the RESOLN key. Extending that local-key description to a guaranteed remote-RE side effect was a hypothesis, not a demonstrated firmware contract. This result does not establish a faulty meter or justify changing normal logging.

The timeout occurred after source-off and auto-mode restoration writes, during the following TR1 read. The cause is not established: the trace alone does not distinguish meter settling/ranging behavior, command-state interaction, or backend behavior. Accepted writes do not independently verify the restored modes or a completed measurement. The bounded stop worked, but this is not successful automatic recovery/restoration.

No RE2 test phase, selected FM1/FM4 verification phases, FA/FH/RH/RM5/RA test phases, or TR0/TR2/TR3 test phases ran. Restoration RA/FA writes are not acceptance of those test phases. Only initial reference control/readback and the FM4/RE1/TR1/status sequence have observations here. Full setting/trigger behavior remains unqualified. The selected batch needs a revised expectation/investigation before a separately authorized repeat; no extra release gate or general parameter campaign is created.

## Operator observations and recovery boundary

Immediately after closure, the operator was asked to use PRESET/LOCAL if RMT remained lit and turn POWER REF off if on. The first reply, “Go,” was not treated as a final-state confirmation or authorization to retry. Subsequent replies were:

- **“RES2 = 0.1%RNG HLD is not lit”**: original resolution restored according to the owner; RNG HLD off.
- **“POWER REF off, RMT off, SPCL off”**: reference off and local-mode indicators confirmed; SPCL off.

These support the recorded resolution/source/local/indicator state after the manual-recovery request. Exact keys used were not reported, live readings updating were not explicitly confirmed, and no later USB status probe was performed. RNG HLD/SPCL observations are retained as owner evidence, not a substitute for decoded filter/range status or proof of the interrupted automatic restoration sequence. No further action/session was running after those observations.

The separate owner record does not rewrite the original receipt's unverified restoration, missing local-return result, `resolution_usb_verified: false`, `front_panel_confirmation: not_provided`, or `physical_identity_verified: false` fields. No full live/local automatic-restoration acceptance is claimed.

## Retained evidence

Remote capture: `/home/pi/hp437b-qualification/diagnostics-acquisition-20261114T142141Z/runs/settings-20261114T142752Z`. Retrieved raw evidence stays ignored under `output/logs/pi-diagnostics-acquisition/settings-20261114T142752Z/`; preparation, delivery, package checks, and local verification stay ignored under `tmp/acquisition-settings/`.

| Evidence | SHA-256 |
| --- | --- |
| Original `capture/diagnostics.json` | `7789e556ab4bfa77ff5f99072ccd3f1588a7ff168653369cfb307b06007480d2` |
| Wrapper `result.json` | `4e439694e6ae675a622f68a948e77640f8f1b040462212248e315e3ae29899be` |
| Separate owner recovery observations | `8c802a4781309ced0a20e904d1fb88f408aff7a8cf9ae1923705c0fa4a6f339e` |
| Unchanged permanent udev rule | `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be` |

Local verification checked the original receipt hash, completed/failed/unattempted counts, each ordered raw reply and accepted write, native failure and worker/closure evidence, and wrapper-reported original logger/rule/installed-runtime preservation. All three preservation checks were true. Raw local measurements and tool state are not committed.

The subsequent [version 2 manual/fake investigation](RE-FILTER-RESTORATION-INVESTIGATION.md) prepares a revised diagnostic. It does not rewrite or promote this failed physical case.
