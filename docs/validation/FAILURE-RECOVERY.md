# Interruption and bounded timeout/recovery

Status: ✅ Complete for the named interruption/timeout/manual-recovery cases on the current Mac/unit, November 11, 2026. Phase 3 remains ⏳ In progress. Owner explicitly authorized interruption and failure/recovery checks, confirmed POWER REF off, and confirmed availability to disconnect/reconnect only the adapter USB when prompted. Starting source `faacc44533874a20a8fd7fd8bf8cfe77e63b1422`, clean `devel`. Production code is unchanged at preparation. The planned profile permits operator-assisted recovery; no unattended recovery claim is intended.

## Setup and recovery boundary

Same identified original meter SN 3125U33223 (known supply discrepancy), sensor 8482A SN MY41094127 attached directly to front POWER REF, cable to SENSOR, source off, W, duty/offset/REL off, retained REF CF 99% and measurement CAL FAC 100%. No external RF source, transmission, source activation, wiring change, zero/calibration, preset/reset, firmware write, backend adoption, or persistent host change is allowed. The meter stays powered throughout; only adapter USB may be removed in the named manual step.

The pinned backend's device-clear path remains guarded. Its USB read may attempt transfer abort, but the parent deadline can terminate its worker before that path finishes; worker disposal cannot prove the instrument or message stream idle. The [pinned adapter source](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/TestAndMeasurement.c) includes bus discovery/identity and REN transitions during startup, and interface-state reset code. A physical USB disconnect/reconnect is selected to restart the adapter/USB context; startup source is a rationale, not proof of this unit's firmware or recovery. Fresh application identity, status, complete acquisition, source-off, and final normal display/local observations are the acceptance evidence. G011/device clear and explicit IFC support are not enabled or qualified by this route.

## Cases and finite budgets

| Case | Procedure | Expected evidence / stop condition |
| --- | --- | --- |
| P3-INT-WAIT | Production CLI, count 5, interval 30 s, timeout 30 s, W, source off. Parent waits for first flushed complete `ok` row, delays 0.2 s within the known inter-read gap, then sends one SIGINT to the CLI process only | Exit 130; one valid retained row; final metadata interrupted; accepted TR3/GTL cleanup, files complete/parseable. No interrupted acquisition row is expected because the signal is between completed transactions. This is process-directed SIGINT, not a claim about every terminal process-group/forced-kill pattern |
| P3-INT-RECHECK | Fresh open, identity, SM/OD, one TR2/read, fresh SM, corrected close | Valid known identity, reference/correction state, numeric acquisition, no errors; no USB cycle needed after between-read cancellation. Independent observation after a 10-second allowance establishes normal free-run/display before this recheck's cleanup |
| P3-TIMEOUT-READ | Test-harness Instrument subclass uses timeout 30 s for production collect setup, then 0.5 s on the first CSV TR2/read. One real trigger/read attempt, source off; no artificial reply/sleep | A real OperationTimeout before completed measurement, bounded host wait (<2 s for failed transaction/worker disposal), failed CSV row and metadata, diagnostic trace, closed worker. The original configured timeout and injected per-row override are recorded explicitly in context; no physical timeout claim from software fixtures |
| P3-GUARD | Immediately after the acquisition failure, before collect closes the Instrument, attempt an ID query through the uncertain-state guard | StateUncertain before any extra write/read; trace length unchanged. No TR3/GTL/source command or retry after uncertainty. Final close disposes resources only |
| P3-MANUAL-USB | After failed process has exited and evidence is saved, prompt owner to unplug adapter USB for at least 5 seconds, reconnect, and allow enumeration; leave meter powered, sensor connected, source off | Operator completion report; do not reopen beforehand. No meter power cycle, preset, or blind software retry. If unavailable, retain a pending manual-recovery gate |
| P3-RECOVER-VERIFY | After operator cycle, verify adapter discovery and explicit resource; fresh open and ID, source-backed SM, one complete TR2/read, fresh SM, corrected close; after 10 s independently observe free-run SM/OD | Correct ID, W/source/correction flags, no errors, valid complete measurement, normal free-run display and local controls. Reopening alone cannot pass. Stop on mismatch/timeout and do not repeat fault injection |

Each injection is attempted once only. Interruption controller waits at most 75 seconds for the first row, then permits up to 35 seconds for finalization after its one signal; an emergency process stop after that is a failed case with uncertain state, not successful cleanup. The verification batch has 120 seconds with 30-second operations and one 10-second no-traffic observation allowance. Timeout setup and fault batch has a 90-second ceiling and the one 0.5-second injected operation; if the expected fault does not occur, record that result and stop without repeated attempts. Manual operator wait is outside these device-I/O budgets; no commands are sent while awaiting it. Post-cycle recovery has 120 seconds, 30-second operation deadlines, and one 10-second observation allowance.

## Preflight adversarial review

Signal only after a completed flushed row and before the next scheduled start, preserving the distinction between safe between-read cancellation and in-flight uncertainty. All normal steps keep POWER REF off; do not add recovery writes to a failed/uncertain Instrument. Keep synthetic fixtures, test-harness deadline selection, real USB transfer failures, manual adapter action, fresh protocol evidence, and operator observations separate. Preserve partial CSV/final sidecars, raw bytes, trace, operation timing, exact revisions/versions, and hashes under ignored local paths. Commit only reviewed summaries. Do not silently extend counts, repeat faults, clear software uncertainty, or treat software close as physical recovery.

No source correction or extra unit tests are required unless these checks expose an actionable defect. Review artifacts independently and reassess all outcome claims after each batch; mark external/hardware prerequisites pending rather than passing by inference.

## Recorded interruption result

P3-INT-WAIT passed on source `faacc44533874a20a8fd7fd8bf8cfe77e63b1422`. The production CLI started November 11, 21:37:40.207191 UTC and finalized 21:37:55.637494 UTC (15:37 CST), 15.43007 seconds total. The controller observed the first flushed row 0.049948 seconds after receipt, waited 0.2 seconds, and sent its one process-directed SIGINT at 21:37:55.602460 UTC. Independent timing reconstruction places the signal about 7.686585 seconds after loop start, before the next scheduled acquisition at 30 seconds: no measurement transaction was pending.

The CLI exited 130 with its interruption notice. CSV retained one valid `ok` W row; sidecar finalized `status: interrupted`, `rows: 1`, and KeyboardInterrupt diagnostics. No interrupted acquisition row was expected or fabricated. TR3/GTL cleanup was accepted, files parse correctly, raw/value/unit/session data match, and initial SM confirms source/corrections off without errors. A fresh-session recheck at 21:38:12–21:38:30 UTC independently read correct identity, free-run SM, numeric display, one complete +0.0100E-06 W reply, and fresh error-free/source-off status, followed by healthy cleanup. This qualifies this between-read SIGINT path, not every in-flight cancellation, process-group signal, forced kill, or storage failure.

## Recorded in-flight timeout result

P3-TIMEOUT-READ and P3-GUARD passed for the induced failure on the same source/runtime/setup. Normal collect setup completed identification, RL0/LN, one TR2/read, and fresh source-off SM. The harness changed only the first CSV acquisition's `Instrument.timeout` to 0.5 seconds; the initial configured 30-second setup timeout and explicit injected override both appear in sidecar context. The real TR2 write completed, the following USB-backed read was still pending, and the host deadline raised `OperationTimeout: read deadline expired; no automatic retry` after 0.503513 seconds. This is an intentionally short application deadline with real hardware, not an observed spontaneous device defect or a synthetic malformed reply.

The trace, recorded before Instrument close, shows uncertainty true, closed false, and worker already disposed. An attempted identity query through that still-open-but-uncertain Instrument raised StateUncertain with zero additional trace entries. No TR3, GTL, source-off write, or retry followed the fault. Production collect finalized one `failed` attempt row with blank value/raw fields and OperationTimeout text, final session status failed, preserved setup reply, and no automatic-local/normal-cleanup metadata. Blank value is not zero power; no completed reply was available to the driver. The harness caught the expected exception to save evidence; this case does not claim a production CLI exit-code test. Requested remaining acquisitions were deliberately not attempted.

The fault batch ran 21:38:52.466944–21:39:00.601255 UTC, 8.14539 seconds including normal setup and cleanup/disposal. The expected failed row and failed metadata are a passing failure-handling outcome, not a successful measurement. No subsequent device traffic occurred until the owner completed the named USB step.

## Manual recovery and fresh verification

The owner confirmed the instructed adapter-only USB disconnect/reconnect while keeping the meter powered, sensor connections unchanged, and POWER REF off. Read-only discovery then found one XyphroLabs GpibUsb `03eb:2065` with serial string `HEWLETT-PACKARD_437B_1.8`. The action is recorded as a USB disconnect/reconnect; actual adapter firmware/power-reset behavior was not independently instrumented.

P3-RECOVER-VERIFY passed 21:40:25.365613–21:40:43.136189 UTC (15:40 CST), 17.77037 seconds total. Fresh *IDN?/read returned the correct HP 437B/firmware 1.8 frame, followed by source-off W status, one complete `-0.0300E-06\r\n` acquisition, and fresh error-free/source-off SM. The first status still indicated standby, demonstrating that reconnect/identity alone was not treated as restored live operation. Corrected TR3/GTL close was followed by a 10-second no-traffic allowance; a second independent session observed standby false and display `     -0.01 uW` before its own cleanup. Both normal cleanup sequences were accepted.

The owner then confirmed live numeric reading −0.05 µW, RMT off, and POWER REF off without any keys. The recovery procedure is therefore accepted for this one induced timeout on the recorded Mac/current-unit setup: manual adapter USB reconnect, fresh protocol verification, normal TR3/GTL restoration, and owner observation. No meter power cycle, preset, zero, calibration, source activation, settings recall, device-clear API, or automatic retry was used. This does not qualify unattended recovery, generic USB unplug during active transfers, G011/device clear, G019/IFC API support, other host/adapter versions, or replacement acceptance.

## Local evidence

The raw artifacts below remain ignored; only reviewed evidence summaries are committed. Hashes are SHA-256, and paths are relative to this repository.

| Artifact | SHA-256 |
| --- | --- |
| `output/logs/phase3-20261111/interrupted-wait.csv` | `19098c7730b46cf7b8c7eba7529de1c8def92770f4cda19ae2a301c75fac95e6` |
| `output/logs/phase3-20261111/interrupted-wait.csv.session.json` | `9326a22f311dd220af1ac240ce057cd767295008c04503006830f8cf0cff0bbc` |
| `output/logs/phase3-20261111/interrupted-wait-controller.json` | `efce86cba3f7fbc57ae87ef5ffbb2076dea3ebb321a5235d4f4c26dbded48cdc` |
| `output/logs/phase3-20261111/interruption-recheck.json` | `f1630d1a31960e753abfacb9dd0a2dcd559179de571d000d5d63ff6e5a5d8e76` |
| `output/logs/phase3-20261111/inflight-timeout.csv` | `9b20c7d2ea0a8eca240841831fbd73ed8c01be8580456978188946416b943b07` |
| `output/logs/phase3-20261111/inflight-timeout.csv.session.json` | `08c6295d564c82bf76cc970d41fa8fc8d94290dcb3330c0126c22dc5b34eecbd` |
| `output/logs/phase3-20261111/inflight-timeout-trace.json` | `bd9da5c9458cfa088ed3de99f75361d0b6467f7519fe721875eaf58c0dbd4323` |
| `output/logs/phase3-20261111/manual-usb-recovery-verification.json` | `2bf300cf44dfbbdaf666cb57a1f19e37179bae78baaa92ab142f4e81debbe38e` |
| `tmp/local-return/check-interruption.py` | `c96019f5cf05b1045a00f61fefd9abc8f0b7c0e3fde725e94f2867150b55c669` |
| `tmp/local-return/check-real-timeout.py` | `28ab3642a3ea216059f3cda989303ed722c48860fccfccf86e4ca68ad3dde7f5` |
| `tmp/local-return/verify-manual-recovery.py` | `b35f5073e301b47593153d303c4fe5f0feb1e11e5ad5768f183643f8ea95a84b` |

The recovery artifact retains its capture-time pending operator field; the later owner confirmation is separate above. Runtime matches the [recorded Mac environment](MAC-20261111.md#setup-and-provenance): macOS 27.0.1 ARM64, Python 3.14.10, libusb 1.0.30, pinned PyVISA 1.16.2/PyVISA-py 0.8.1/PyUSB 1.3.1, explicit @py, and the negotiated local profile. Adapter revision/firmware remain unknown. No production code/pin changed, and no unrelated software checks were rerun to imply additional physical coverage.

## Fresh reassessment and acceptance

Review independently checked signal timing versus the next scheduled acquisition, retained partial data, final metadata semantics, real completed trigger write/in-flight read timeout, exact injected deadline and host wait, pre-close uncertainty/blocked reuse, absence of post-fault recovery traffic, manual-step ordering, fresh identity/acquisition rather than reopen alone, status freshness, standby versus free-run, raw numeric consistency, local/source-off observations, artifact hashes, and current-unit/host limits. No actionable repository defect was exposed in these delivered cases. Accept P3-INT-WAIT, P3-INT-RECHECK, P3-TIMEOUT-READ, P3-GUARD, P3-MANUAL-USB, and P3-RECOVER-VERIFY within their named scope. Synthetic sentinel/malformed-response coverage remains software-only. Phase 3 still requires intended second-host and replacement qualification; no broader orchestration/unattended-fault support is implied.

The exact tested source revision’s [software CI](https://github.com/lbussy/HP-437B-Automation/actions/runs/43103841151) passed before this batch. Maintained Markdown links/anchors, matrix enumeration, whitespace, all eleven listed local hashes, and the nine preserved reference files were checked before delivery. New delivery CI is reported separately; neither CI nor a source-level guard substitutes for the physical case evidence above.
