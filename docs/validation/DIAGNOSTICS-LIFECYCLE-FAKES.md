# Event read-clear and error-selection experiment: fake-first preparation

November 14, 2026. Owner-selected follow-up to the [passive wspr5 latch-read pass](PI-DIAGNOSTICS-LATCHES-20261113.md). This is a separately gated diagnostic experiment. Its software preparation does not establish physical read-clear or queue behavior, add a release requirement, or change normal logging.

## Fixed experiment and sources

The [lifecycle profile](../../src/hp437b/diagnostics_lifecycle.py) uses two deliberate invalid entries from the publisher manual: `QX` (command error) and `FR-3GZ` (invalid frequency entry/execution error), as described on [printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69). [Table A-1, printed A-4/PDF 154](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=154) identifies invalid-code error 91 and frequency-range error 82. These are expected observations to check, not assumed responses. The negative frequency is not a valid correction-frequency setting; the experiment does not write a valid measurement setting.

Both literal byte sequences are private fixed fixtures. The normal encoder still rejects `QX` and negative frequencies. The tool has no arbitrary raw-command argument, and no command registry/ambiguity guard is relaxed. No valid frequency, calibration factor, sensor table, saved state, reference output, or enable mask is written. Original diagnostic history may be consumed, and new entry/error event indications are deliberately generated; that is part of the selected experiment.

## Bounded sequence

The maximum is **69 uniquely identified steps: 62 queries and seven deliberate invalid-entry writes**, plus existing identity preflight and healthy cleanup. Repeated queries are intentional observations, never retries after failed communication.

| Phase | Fixed work | Purpose |
| --- | --- | --- |
| Baseline | Read ESE/SRE/STB; ESR three times; ERR three times; SM twice | Preserve prior evidence; require zero enable masks, quiet error replies/status, source off, and normal live mode before any stimulus |
| Event read-clear | QX once; ESR three times; ERR three times; SM twice | Observe a newly induced command-error bit before reading SM; distinguish disappearance, persistence, or inconclusive observations |
| Isolated A | QX once; ERR three times; ESR three times; SM twice | Establish whether ERR exposes code 91 with this query ordering |
| Isolated B | FR-3GZ once; ERR three times; ESR three times; SM twice | Establish whether ERR exposes code 82 before making a paired-error inference |
| A then B | QX, then FR-3GZ; ERR three times; ESR three times; SM twice | Preserve the two-error order and bounded reply sequence |
| B then A | FR-3GZ, then QX; same reads | Distinguish order-dependent hypotheses without assuming FIFO |
| Final | ESE/SRE/STB, three ERR reads, three ESR reads, two SM reads | Record remaining diagnostic state and verify observed enable masks/active status/configuration flags |

The baseline allows an observed Power On bit but stops before fixtures if preexisting error event bits, nonzero masks, nonzero error replies, or active status errors are present. No masks are reset to force the precondition. Each phase's last SM must show reference off, normal mode, not standby, and no active measurement/entry error; observed scale/relative/group-trigger/limit/offset/duty flags must match the baseline. Range/filter snapshots are retained without treating normal automatic changes as setter changes. SM updates may lag measurements; an unchanged error indication after the fixed status pair is a bounded observation stop, not a declaration of an instrument defect or proof that an error can never clear.

If the command-error event is unobservable, or isolated ERR replies do not expose the expected entry codes, the runner stops before further stimuli/pair inference. `observation_stop` is an incomplete experiment with retained data; it is not a successful qualification claim. Healthy communication can still perform TR3/GTL/raw close. If a transaction is malformed, partial, failed, late, or cancelled, no more queries, fixtures, or ASCII cleanup are sent; the existing native-finish/disposal path applies.

## Interpretation and limits

The result records bounded signatures: command bit disappears on subsequent reads, persists across three reads, or is inconclusive; paired ERR sequences may be FIFO-like, LIFO-like, latest-sticky, single-slot-like, or inconclusive. These labels do not create a production queue API or prove general queue capacity, other error classes/event bits, arbitrary timing, or all clearing semantics. Three zeros alone do not prove read-clear behavior. Known repeated-command IDs are distinct so no earlier reply is overwritten by a later read of the same query.

`accepted_full_case` is true only for a fully completed, timely, normally closed case; stopped/failed/cancelled cases keep it false. The original receipt still has no inferred physical identity or front-panel confirmation. New operator observations remain separate evidence. A06 and the Mac/Pi matrix are not promoted by fake results.

## Implementation boundaries and offline evidence

The existing [physical diagnostics runner](../../src/hp437b/diagnostics_physical.py) now has a separate `lifecycle=True, confirmed_error_fixtures=True` profile; ordinary basic/passive defaults remain unchanged. The [standalone tool](../../tools/diagnose_meter.py) requires both `--lifecycle` and `--confirm-fixed-error-fixtures`, in addition to its existing supervision/prior-worker confirmations. Combining it with the passive latch flag is rejected before setup-file/hardware access. The child streams individual steps; its final message omits the duplicate full step list, keeping IPC bounded for repeated reads and partial replies.

The same worker, exact-resource shared lease, descriptor/identity checks, pinned dependencies, native timeouts, cancellation ownership, and 20/25-second work/total budgets are reused. No hardware retry, source switch, clear/reset, preset, zero/CAL, reboot, or cable operation is added. The logger, production transport/instrument/protocol/codec, normal CLI, measurement workflows, and reconciliation code remain unchanged.

**34 new stateful fake tests** exercise independent clearing/sticky event models, FIFO/LIFO/latest-only/sticky error hypotheses, ambiguous observations, prior evidence/mask guards, invisible/rejected fixtures, changed status/configuration, partial/malformed writes/reads, unique repeated-read records, cancellation/late replies, hung/crashed workers, and explicit API/CLI fixture gates. Original basic/passive tests remain in the regression. The focused lifecycle/diagnostics/instrument/transport suite passed **157 tests** through the hardware-blocking launcher. Initial test-only fixture-count/keyword expectations were corrected; no normal API was loosened to make them pass.

The full local Python 3.14 reporting-environment regression passed **1,649 tests**, with three opt-in stress cases skipped, in 268.73 seconds. It retained the hardware-blocking guard while allowing the existing loopback interface tests outside the sandbox. Lint, formatting, documentation links/IDs/manual checksums, `git diff --check`, source/wheel builds, and package/source byte comparisons passed.

A new isolated non-editable Pi installation is ready at `/home/pi/hp437b-qualification/diagnostics-lifecycle-20261114T114137Z/.venv`, with source/tools under its `source/hp437b_automation-0.1.0` directory. Delivery SHA-256 is `01816a47a5b0a78096d99914c4730c0a572054b3e52f6e24160bd36de0c91623`; its manifest records base `dc75cda` plus modified-source runtime hashes. **248 selected Pi tests passed in 60.59 seconds** on Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64, under the hardware-blocking launcher. Installed runtime hashes match the delivered manifest, and retrieved preflight/test records were independently checked locally. The original logger and udev rule remain unchanged; dependencies were installed only in the new virtual environment. No native USB backend load, discovery, or instrument access occurred. Prior diagnostics environments and sealed captures remain intact. Local artifacts/logs stay ignored under `tmp/diagnostics-lifecycle/`.

Use the existing shared lock root `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks` when invoking the new isolated source tree. This retains cooperation with other runners using the same exact resource; it does not replace fresh other-app/prior-worker checks. The staged invocation requires a fresh setup confirmation and an actual supplied original FREQ value before it can run.

## Supervised wspr5 preparation and operator needs

Prepare a new isolated Pi source/wheel installation and run the selected tests under the hardware guard, retaining the original normal logger, existing diagnostics captures/install, udev rule, and shared lock root. No USB discovery or meter session is part of preparation. Any physical run requires a fresh check of the same expected adapter/meter, no active prior worker, closed other control apps, source off/live-local state, and idle trigger/zero/calibration state.

For the later supervised run, the owner should remain at the current meter for about five minutes with PRESET/LOCAL accessible, keep POWER REF off and connections unchanged, and note the current front-panel FREQ setting beforehand. That value is for precise manual restoration if the documented invalid-frequency entry leaves an entry indication requiring re-entry; no valid frequency or preset will be written automatically. The meter may show brief deliberate entry-error indications. A radio, new RF hardware, calibration, or warm-up wait is not needed for these source-off diagnostic observations.

After closure, obtain separate confirmation of live readings updating, RMT off, and POWER REF off. If the meter needs intervention or a setting must be re-entered, stop and record it rather than claiming automatic restoration. No physical stimulus, error read, event read, reset, or source operation has occurred during this fake-first preparation. The subsequent [supervised Pi case](PI-DIAGNOSTICS-LIFECYCLE-20261114.md) observed event read-clear and the planned invisible-entry-error stop after 29 steps; no frequency/pair cases ran. The complete experiment is not accepted, and error selection/queue behavior remains inconclusive. This result remains separate from completion of the current POWER REF deliverable.
