# Offline software qualification results

Completed the bounded local software campaign on November 11, 2026; broader command/parameter and physical qualification remains partial. Baseline `9d84059cb7778cbd87f505159df52521003dca8a`; isolated branch `codex/offline-qualification-20261111`. No hardware access, USB enumeration, Pi access, or bench installation occurred. Artifact inspection found and fixed omission of the existing third-party notices from distributions by declaring both license files explicitly. No runtime defect was established, and all `src/hp437b/` files and dependency pins remain unchanged. Normal logging and the tested failed-read shutdown behavior are preserved.

## Evidence and reproduction

The [plan](OFFLINE-QUALIFICATION-PLAN.md) specifies case IDs, priorities, oracles, and limits. The [coverage ledger](OFFLINE-PARAMETER-COVERAGE.md) accounts for every 118 command and 20 bus IDs, distinguishing 78 encodable variants (including contextual helpers/procedures) from 40 guards. The [three assessments](OFFLINE-QUALIFICATION-REVIEW.md) record corrections and residual limits. Source/test support and an [execution prompt](../prompts/offline-qualification.md) are maintained for reproduction.

| Case | Result |
| --- | --- |
| OQ-01 guard/supervisor | Parent, exec, and spawn sentinel canaries pass; eleven denial paths each. Actual short command expiry, global-expiry/reserve refusal, invalid deadlines, and final-verification override pass |
| OQ-02 baseline | Unchanged 261 tests pass in 3.52 seconds; original lint/format and wheel/sdist build pass |
| OQ-03 parameter audit | All inventory IDs linked; finite register/range/resolution/sensor choices, 256 mask candidates, 512 filter candidates, decimal boundaries, four frequency scales, terminators, all 40 guards before I/O, all confirmation gates, no-argument arity, and display lengths checked |
| OQ-04 parser | Seed 4378482; 10,000 measurement inputs: 2,500 valid, 7,500 deliberately invalid; all correctly classified. Finite sentinel/byte/SM field tests and opaque-byte preservation pass |
| OQ-05 logger/storage | 5,000 synthetic rows: counts, sequence, session, units, raw/value consistency, monotonic elapsed times, and completion agree. Existing fake-clock overrun/duration tests pass. Task-local injected sample write/flush and metadata fsync/replace/finalization errors surface with cleanup and appropriate retained artifacts |
| OQ-06 deadlines/backend | 30 real IPC trials across late error/success/disconnect; original deadline remains failure, one request only, expected grace result, no surviving worker handle. Native-error, partial-write, oversized/incomplete fake backend replies rejected. Existing hang/non-read/cancellation/uncertainty tests pass |
| OQ-07 packaging | Wheel/sdist content, separate clean installations, parent/spawn installed origins, inherited canaries, help/capabilities, and default suites checked outside source; exact hashes retained in the ignored run manifest |
| OQ-08 optional hosts | No new Pi run; no Python 3.11/3.13 on the configured PATH. Only available Python 3.14.10 exercised. Existing CI/bench results remain historical evidence |
| OQ-09 review/delivery | Exactly three self-assessments; scoped local branch commits only. No push, PR, merge, deployment, or new remote CI |

Default final suite: **418 passed, three opt-in stress cases skipped**. Explicit stress run: **three passed** (separate campaign, not hidden skips). Lint, formatting, build, clean installs, documentation links, diff whitespace, and reference checks pass. The first expanded sandboxed run's test pass was followed by supervisor cleanup denial; its nonzero exit is retained in ignored diagnostics and is not counted as a fully supervised pass. Owned-group-capable local execution passes; no sandbox rule or device access was changed.

The environment is a separate Python 3.14.10 virtual environment on macOS ARM64 with the exact repository lock: PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. Dependency installation used existing cached wheels, without network or upgrades. Wheel and sdist each use a separate non-editable QA environment; verified package paths end in their own `lib/python3.14/site-packages/hp437b/__init__.py`, including spawn children. The main editable bench environment continues to resolve the original checkout.

Run diagnostics, artifact hashes/versions, and install origins are kept locally in ignored `tmp/offline-qualification-20261111/`. New synthetic stress files are task-owned pytest temporary files, never physical evidence. Each command/campaign has a supervising 180-second ceiling, within the four-hour task ceiling and thirty-minute final reserve. Parser inputs stay below 65,537 bytes, the campaign row/trial bounds are 5,000/30, no more than two test processes perform work concurrently, and generated output remains below 1 GiB with more than 2 GiB free. Memory is bounded by input/workload design; a portable 512 MiB process cap was not enforced.

## Remaining work

This completes the declared finite software cases, not all parameter/state combinations. Identification grammar, reserved/opaque semantics, guarded table/reset/poll/bus functions, settling, electrical behavior, physical fault recovery, and absolute accuracy retain their existing limits. No source discrepancy is resolved by simulation. The physical [coverage matrix](../inventory/COVERAGE.md), HP-01/VAL-01, the original meter's supply discrepancy, and [replacement acceptance](REPLACEMENT-ACCEPTANCE.md) remain unchanged. The replacement still requires actual identity/calibration/setup and the declared supervised profile on both hosts.
