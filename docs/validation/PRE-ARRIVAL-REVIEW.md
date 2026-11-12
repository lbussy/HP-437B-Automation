# Phase 3 pre-arrival readiness and evidence review

Status: ✅ Available pre-arrival preparation complete; ⏳ Phase 3 remains in progress awaiting replacement execution. November 11, 2026. The owner directed continuing as far as possible without further input before the new meter arrives. This review performed no new device I/O and made no production-code, default-setting, firmware, host-security, or RF-setup change.

## Decisions and prepared work

| Item | Current result |
| --- | --- |
| HP-02 adapter readiness | ✅ Current setup: owner-reported USBGpib V2, reported firmware V2.4 read directly over USB, Anker USB-C cable, and meter address 13 read from the front panel; scoped Mac/Pi cases recorded |
| Exact PCB revision | Accepted unknown; owner reports no revision marking and closed further investigation; not a Phase 3 blocker |
| DEC-01 hosts | ✅ Mac and Raspberry Pi have separate environment, access, installation/runtime, and physical evidence |
| DEC-02 initial policy | ✅ Owner selected W, automatic range/filter, one-second requested intervals, and finite five-minute runs; [policy and limits](MEASUREMENT-POLICY.md) record actual timing and unchanged CLI defaults |
| Replacement execution preparation | ✅ [Arrival/setup and per-host procedure](REPLACEMENT-ACCEPTANCE.md) prepared with prerequisites, tolerances, finite budgets, one-fault limits, restoration, and evidence requirements |
| Existing evidence reconciliation | ✅ Independent local CSV/hash audit, scoped matrix reconciliation, and review/reassessment complete |
| HP-01/replacement identity and calibration | ▧ Actual arriving meter and records unavailable; not inferred from original-unit documents |
| PHASE-03/VAL-01 final physical acceptance | ⏳ Repeat all mandatory declared-profile cases on replacement plus actual sensor on both hosts, then perform final acceptance reconciliation |

The initial application is the supervised internal-reference/readback profile. A future external radio/frequency/path needs separate applicable correction/measurement evidence; an unavailable radio does not prevent preparing or completing this declared reference profile. Absolute RF metrology, undocumented operations, already-wedged software-only repair, and unattended continuation remain outside current acceptance.

## Current-unit evidence index

These are completed case observations for original meter SN 3125U33223 and the actual recorded sensor/setup. Each linked record owns its exact tested runtime, environment, commands, setup, raw evidence, and limits. This index does not imply that every earlier sustained/control case was rerun after each later software commit; the integration records explicitly separate unchanged healthy paths from the later failed-read fix. Final replacement acceptance repeats the mandatory cases on its selected delivered runtime.

| Required profile gate | Mac evidence | Pi evidence |
| --- | --- | --- |
| Opening, identification, ASCII read/framing | [Mac identification](MAC-20261111.md), [latest source-off/shutdown case](MAC-FAILED-READ-SHUTDOWN.md) | [Pi qualification](PI-QUALIFICATION.md), [installed shutdown case](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) |
| Serialized measurement, fresh status, numeric display | [Baseline](MAC-20261111-BASELINE.md), [independent free-run](MAC-FAILED-READ-SHUTDOWN.md) | [Baseline/control](PI-QUALIFICATION.md), [independent free-run](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) |
| Physical display agreement | [Held reference sample](MAC-20261111-REFERENCE.md) | [0.989 mW held comparison](PI-QUALIFICATION.md) |
| Reversible W/dBm and source control/restoration | [Control record](MAC-20261111-CONTROL.md) | [Control record](PI-QUALIFICATION.md) |
| Three-row logging and file protection | [Short session](MAC-20261111-SHORT-LOG.md) | [Short session and retrieval](PI-QUALIFICATION.md) |
| Five-minute reference logging | [299 valid rows](MAC-20261111-SUSTAINED.md) | [300 valid rows](PI-QUALIFICATION.md) |
| Healthy free-run/local shutdown | [Corrected TR3/GTL](AUTOMATIC-LOCAL.md), [latest owner confirmation](MAC-FAILED-READ-SHUTDOWN.md) | [Pi normal cleanup](PI-QUALIFICATION.md), [latest owner confirmation](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) |
| Between-read SIGINT and partial data | [Interruption](FAILURE-RECOVERY.md) | [Interruption](PI-QUALIFICATION.md) |
| Original forced deadline, actual abort, failed data, fresh session | [Integrated fix, about 102 ms shutdown wait](MAC-FAILED-READ-SHUTDOWN.md) | [Integrated fix, about 52 ms shutdown wait](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) |
| Named manual fallback | [USB reconnect case](FAILURE-RECOVERY.md) | [Full adapter isolation](PI-ONLY-RECOVERY.md#full-adapter-isolation-after-the-repeated-failure) |
| Mac access and matching file retrieval | Local files; cross-host retrieval not applicable | [Pi workflow](PI-QUALIFICATION.md) and [integrated files](PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) |

## Independent local evidence audit

A read-only scratch audit independently decoded numeric ASCII raw bytes with Decimal, rather than calling the production measurement parser. It checked unique headers, sequence/session consistency, timezone-aware receipt timestamps, finite nonnegative monotonic elapsed values, raw/value/unit correspondence, row/sidecar counts and terminal status, preserved failed-row semantics, and explicit filename/path SHA-256 mappings in procedure captures. Scope is the available local evidence set, not every remote diagnostic file ever created.

| Audit result | Count |
| --- | --- |
| Local CSV sessions checked | 23 |
| Completed / failed / interrupted sessions | 11 / 10 / 2 |
| Valid numeric rows / preserved failed rows | 624 / 10 |
| Explicit stored artifact-hash comparisons | 50 |
| Unresolved explicit hashes / new integrity errors | 0 / 0 |
| Known nonqualifying incomplete capture retained | 1 |

The failed/interrupted session counts are expected diagnostic outcomes, not failures of this audit or passing hardware-case counts. The known incomplete `identification-host-access.json` is the documented P3-R03 serialization failure, exact SHA-256 `b0d10c324054cf9d8b2d701a0c4f72d9ba72d532287bf890c1cba8f394fab70a`. The audit initially surfaced it, verified the recorded fingerprint, and classified only those exact bytes as nonqualifying. It was not repaired or used as acceptance evidence; the corrected capture and physical observation remain authoritative. No other JSON parsing failure was exempted. Raw evidence remains ignored and unchanged.

## Coverage counts and interpretation

The inventory remains 118 command/syntax variants and 20 bus entries. Software implementation remains 78 implemented/tested variants and 40 guarded variants, with 261 current software tests. The normal bus surface remains three byte-transfer paths, one conditional local-return path, fifteen deferred/guarded entries, and one instrument exclusion. No new command or bus capability was implemented by this review.

| Matrix physical status | Mac | Pi |
| --- | --- | --- |
| Command variants with a scoped pass | 6 | 6 |
| Command variants with partial observations | 4 | 4 |
| Command variants without physical acceptance | 108 | 108 |
| Bus entries with a scoped pass | 1 | 1 |
| Bus entries with partial observations | 3 | 4 |
| Bus entries without physical acceptance | 15 | 14 |
| Bus entries explicitly excluded | 1 | 1 |

These are inventory-row counts under [the matrix status model](../inventory/COVERAGE.md#status-model), not counts of mandatory application cases. Scoped passes include their named limits. Partial observations include the broader SM/TR2/TR3/retained-RL0 and ASCII bus paths; required reference-profile behavior can have a passing named case while the broader row stays partial. The additional Pi bus partial is G011's healthy experimental handshake; its recovery failed and its API remains guarded. Numeric OD evidence does not qualify sensor-table/binary OD behavior or close A03. Broader untested variants remain outside the declared profile, not silently accepted or additional replacement prerequisites.

## Assessment and final reassessment

Initial assessment checked stale adapter/PCB/address status, incomplete policy, original-unit results presented as replacement acceptance, stale matrix labels, premature or unsupported recovery claims, software evidence mistaken for physical error/overrange behavior, and damaged/partial artifacts hidden by success counts. Corrections recorded V2/V2.4/Anker/address 13 with their distinct evidence sources, accepted the owner's PCB limitation, adopted the selected initial policy, prepared the replacement procedure, narrowed updated matrix labels, and classified the exact historical incomplete capture without rewriting it.

Fresh reassessment checked all local audit results, matrix totals and source links, owner versus software observations, exact host/version scope, failed-row/uncertain-state semantics, actual abort traces versus mere error replies, active source/cleanup limitations, and replacement/no-radio boundaries. Original reference artifacts remain byte-identical to the starting records; Markdown/link/whitespace checks apply to the delivered documents. No actionable defect remains in this pre-arrival preparation/reconciliation. Existing transport software and its physical tests/CI remain separately recorded; this document adds no hardware run or new reliability guarantee.

Remaining mandatory work requires the arriving replacement: review its identity/calibration/setup, verify actual sensor/factors/address, execute the prepared profile on both hosts, and reconcile the final acceptance record. The pre-arrival work item can close while HP-01, PHASE-03, and VAL-01 remain open. No further current-meter experiment or owner input is needed to finish this preparation.

The ignored independent audit script SHA-256 is `92d2dc2e3718e417514bec1882790f2a21de201a64d1480bab953d3f1f9247e7`; its local report `output/reports/prearrival-evidence-audit.json` SHA-256 is `d69074d2b08ba6def392726fb875ec852b375069d5540ef58571680e35dd6ce3`. These identify the audited local run without committing raw measurements or local tool state.
