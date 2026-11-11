# Phase 2 implementation and review record

Date: November 11, 2026. Starting commit: `908567f`; branch: `devel`; starting working tree: clean. The user explicitly authorized execution of the saved Phase 2 prompt, including software checks, commit, and push. Work used scripted transports, synthetic protocol fixtures, fake VISA resources, and IPC workers without device access.

## Delivered software

| Area | Result |
| --- | --- |
| Package | Installable `hp437b-automation` 0.1.0, src layout, wheel and source distribution |
| Command layer | Stable registry matching all 118 inventory IDs; 78 implemented codec/procedure variants and 40 ambiguity guards |
| Driver | Whole-operation locking, typed query parsing, explicit units, TR1/TR2/read sequencing, confirmation checks, firmware eligibility, uncertain-state handling |
| Transport | Explicit @py USB INSTR access, dependency-version checks before opening, raw message framing, isolated worker with deadlines and termination; unsupported bus operations guarded |
| Logger | Finite count/duration, UTC receipt times, monotonic scheduling, corrected overrun accounting, CSV plus session metadata, raw replies, errors, interruption, and cleanup outcomes |
| CLI | I/O-free help/capability report, explicitly synthetic demo, and explicit hardware log command |
| Software verification | Encoder/parser/driver/logger/CLI tests, real IPC deadline tests with fake workers, fake-resource VISA contract tests, installed-wheel smoke and suite checks |
| CI | Linux Python 3.11/3.14 software workflow; actual run status is verified separately after push |

See [software usage](SOFTWARE.md) for installation, APIs, defaults, schema, and recovery. [Coverage matrix](inventory/COVERAGE.md) retains per-capability implementation, software tests, and separate Mac/Pi physical columns.

## Coverage definitions and totals

- Commands: 78 variants have byte encoding/procedure implementation and passing software cases. Eleven are contextual encoder helpers (seven P tokens plus four cursor codes) whose standalone driver invocation is rejected. Two are zero/calibration procedures tested with a scripted polling-capable transport; the supplied production transport guards them before I/O because it lacks the required serial-poll route. The other 65 have high-level operation paths, subject to documented configuration/firmware eligibility and later physical qualification.
- Deferred commands: 40 variants retain explicit pre-I/O ambiguity guards. They cover CT/ET/SN (30), ID/IDN? aliases (2), LP/RV/@1/@2 (4), *RST/*TST?/SP (3), and DF (1). Each guard points to A01, A02, A03, A05, or A07. Guard tests establish predictable rejection rather than supported command behavior.
- Bus operations: G002/G003/G004 have byte-transfer/framing paths with software tests. Sixteen entries are explicitly deferred in the supplied transport. G020 is a documented instrument exclusion with an exclusion test.
- Physical evidence: Mac and Pi columns remain open. Scripted simulations and package tests establish software behavior, and qualification must record actual adapter/firmware/host and replacement-meter identities.

Every inventory ID has a corresponding matrix entry. Existing Phase 1 counts and IDs are preserved. Numeric setters intentionally use exact legal grid values; ambiguous rounding, sensor-table traversal, opaque restore framing, and reset/self-test semantics retain their evidence requirements. Full instrument orchestration therefore remains a broader coverage target beyond this software milestone.

## Dependency and platform decisions

Current package metadata was retrieved from PyPI on November 11. The published selections are PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1, with typing_extensions 4.16.0. The backend release remains 0.8.1; Phase 1's documented bus gaps still apply. Source-backed read/write and automatic initialization REN behavior do not establish explicit bus-control support. Development-only methods were excluded from the release contract.

Python 3.11+ is a project baseline compatible with the dependencies' published Python requirements and standard-library choices. Local software execution used CPython 3.14.10 on macOS 27.0.1 ARM64. Package pins and the complete local development dependency snapshot are recorded in `pyproject.toml` and `requirements-dev.lock`. Runtime metadata checks enforce the inspected VISA/PyUSB versions before opening the resource. System libusb installation and Pi/Mac USB access remain host qualification tasks.

The source distribution includes authored Markdown references and tests; the wheel packages the software. Publisher manuals, calibration originals, scratch environments, synthetic measurements, and downloaded inspection material remain outside the software distributions. Original source artifacts remain unchanged in the repository.

## Adversarial round 1 and corrections

| Finding | Severity | Correction and regression evidence | Status |
| --- | --- | --- | --- |
| P2-R01: A VISA transfer can stall beyond a per-transfer library timeout | High | Isolated worker, parent monotonic RPC deadline, termination on timeout; actual IPC hang-worker test verifies bounded host wait and disposal | Closed |
| P2-R02: A named backend method or enum could imply unavailable bus control | High | Published 0.8.1 pins, explicit bus guard table, polling-method/capability check before cal/zero writes; every deferred command and bus guard has a rejection test | Closed |
| P2-R03: Broken worker pipes could leak low-level EOF errors and retain uncertain connections | Medium | IPC errors mapped to TransportError and worker disposed; success/disconnect tests plus fake-resource contract verify raw transfers and cleanup | Closed |
| P2-R04: A late polling reply could be accepted after a calibration/zero deadline | High | Deadline checked after serial poll; delayed completion test raises timeout and taints state | Closed |
| P2-R05: Unbounded numeric exponents or command text could create invalid traffic or excessive formatting work | Medium | Finite/range/grid/precision checks before encoding; injection, NaN/infinity, huge-exponent, label, terminator, and domain-boundary tests | Closed |
| P2-R06: Parser/transport errors could lose raw evidence or allow accidental reuse | High | Last complete reply retained, failure/error CSV rows, uncertain-state guard and explicit reconciliation; malformed/sentinel/disconnect/cancellation tests | Closed |

## Reassessment and further corrections

Round 2 reviewed data integrity, cleanup, scheduling, software claims, and public packaging after the initial corrections.

| Finding | Severity | Correction and regression evidence | Status |
| --- | --- | --- | --- |
| P2-R07: Resource or CSV close failures could leave completed metadata | Medium | Cleanup/file failures set failed status with diagnostics while preserving resource cleanup; close-failure and metadata-storage-failure regressions | Closed |
| P2-R08: Rebased schedule hid interval overruns | Medium | Next target is based on actual preceding acquisition start; injected-clock slow-read test verifies lateness and duration behavior | Closed |
| P2-R09: Unit changes between samples could create mislabeled values | High | Persist actual parsed units, detect requested-unit mismatch, stop collection, and retain the reading/error evidence; changed-unit regression verifies W data is labeled W | Closed |

## Final adversarial assessment and acceptance

Round 3 identified a source-sequencing issue: SM updates only after a measurement (00437-90047, printed 3-33/PDF 63), so an immediate SM after a unit change could return stale units. P2-R10 (High, closed): the logger now consumes a setup TR2/read before SM, retains the setup reading in metadata, and keeps it outside the requested CSV row count. The independent scripted setup conversation and explicit freshness-order test verify this sequence.

Round 4 rechecked command enumeration, source-limited behavior, unsupported/conditional APIs, parser framing, mutation confirmation, trigger/calibration ordering, concurrent callers, actual units, timeouts, process disposal, file ownership, interrupted sessions, dependency selection, packaging, documentation, and status claims. The pass found no remaining actionable Phase 2 defects. Later evidence requirements remain explicit deferrals rather than silently enabled stubs. The saved prompt's software-milestone stopping rule is satisfied.

The basic logger and unambiguous command codecs have passing software tests. Full command/bus coverage and physical acceptance remain tracked in the matrix. Initial hardware host selection and final measurement policy remain DEC-01/DEC-02; the implemented CLI defaults are overridable software choices.

## Checks and evidence

- 223 source-environment tests passed; Ruff lint and formatting checks passed.
- Wheel and source distribution built successfully with the pinned build environment.
- Separate wheel environment imported the installed package, ran CLI help and a two-row explicitly synthetic demo, and passed the software suite after installation.
- Independent inventory/matrix reconciliation, local Markdown links/anchors, Markdown table structure, whitespace, and source-artifact integrity checked before delivery.
- The nine tracked manual/calibration/reference files remain byte-identical to the starting commit; the publisher manual SHA-256 list passes.
- The software CI workflow is part of this delivery. Report its observed result separately from local checks.

## First Phase 3 qualification batch

Record actual host/OS/architecture, libusb/USB permissions, adapter model/firmware, meter/sensor identity, and applicable calibration records. Establish real resource opening, raw *IDN?/SM framing, explicit units, one TR2/read, a short logged run, failure/timeout recovery, and a route back to local control. Resolve required released-backend bus operations before qualification of zero/calibration or broader orchestration. Keep current-meter observations associated with its known supply discrepancy, and repeat acceptance on the replacement.
