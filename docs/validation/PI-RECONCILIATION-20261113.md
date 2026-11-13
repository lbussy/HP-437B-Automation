# wspr5 bounded reconciliation checks

November 13, 2026. Owner requested healthy and single post-timeout checks on wspr5, with the adapter moved from the Mac only after Pi readiness. Status: ✅ both named supervised physical cases complete, including separate owner final confirmations. Preparation, actual fault/abort evidence, and physical reconciliation results retain their separate scopes below.

## Isolated delivery and software evidence

Existing SSH configuration outside the execution sandbox reached wspr5 without new credentials. Read-only preflight found aarch64, kernel `6.18.60+rpt-rpi-2712`, Debian 13, and Python 3.13.5. No active meter-control worker was found; the adapter was absent from Pi enumeration while retained on the Mac.

The existing logger at `/home/pi/hp437b-qualification/20261111/.venv` was snapshotted before and after preparation. Its installed source files, package origin, and PyVISA 1.16.2/PyVISA-py 0.8.1/PyUSB 1.3.1 pins remained unchanged. The owner-authorized `03eb:2065` udev rule remains byte-identical (SHA-256 `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be`); the ordinary `pi` account is already in `plugdev`. No host access rule, group, system package, service, or other radio application was changed.

Source and a pure-Python wheel were built from clean commit `0aaccfa1301755bc26bbf118d50bf9355b083c85`. The source archive and delivery bundle were checked for safe relative regular-file/directory entries, with no publisher PDFs, raw CSV, local state, or credentials. The received delivery and each contained artifact/helper hash were verified before safe extraction and installation into a new non-editable environment:

- Workspace: `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z`.
- Test Python: workspace `.venv/bin/python`.
- Source/tools: workspace `source/hp437b_automation-0.1.0`.
- All installed runtime Python hashes match the delivered source manifest. Every runtime module shared with the original Pi logger remains byte-identical to that original installation.

**154 tests passed in 34.66 seconds** in the new Pi environment, under the hardware-access guard. They include all 71 supervisor/physical-bridge fake cases, transport/instrument/logger cases, and twelve Pi-specific diagnostic-helper/auditor cases. The helper auditor uses synthetic complete/mutated exchanges for offline controls; actual abort evidence will be required from the physical run. Lint, format, and installed CLI-help checks passed. The libusb backend loaded without device discovery/open; the installed system libusb package reports `2:1.0.28-1`.

| Prepared artifact | SHA-256 |
| --- | --- |
| Delivery bundle | `c71c2d97ea36b5c0d1514ef7f7b6955d62c12b09e735eda55779aea2e171ee53` |
| Wheel | `8f622e651d4f09756db8d2b85e19cb4a453c8a7db0137ae4d83f165c5dc5b77a` |
| Retrieved software-preflight record | `bafd5f42913c2a1ccfe151d80e960a4669355e71cafe7dcb020312846faaf407` |

Local delivery/helper/preflight records remain ignored under `tmp/pi-reconciliation/`; remote logs, old-logger snapshot, and `preflight.json` remain in the isolated workspace. Fake receipts are labeled injected evidence, not Pi hardware acceptance. The original logging environment remains available and untouched.

## Healthy physical result

After software readiness, the owner moved only the USB host connection to wspr5 and confirmed LED lit, live numeric readings, RMT off, POWER REF off, other control apps closed, and fifteen-minute availability with PRESET/LOCAL accessible. No active meter-control process was found. The selected adapter enumerated at `1-1.4`, node `/dev/bus/usb/001/006`, root:plugdev mode 0660, with ordinary-user read/write access and initial `usbtmc` binding. The exact descriptor/profile checks and unchanged udev rule passed before open.

The one authorized healthy attempt ran at **2026-11-13 23:40:58–59 UTC**, using the isolated installed package and Python 3.13.5. It returned `communication_reconciled`, reason `verified`, in **0.314614 seconds**. The matched identity was 437B/1.8 with an empty serial field; label serials remain supplied equipment facts. SM reported POWER REF off, zero measurement/entry errors, standby false, absolute W, range 11, and filter 17. TR3/GTL was accepted, raw transport closed, and the child exited with code 0 and no forced termination. No workflow resumed or source switch occurred.

Remote and retrieved receipt SHA-256 matched: `653c78ea2f1174f750e798950a3d6a7ad2fdae3381f25814b7f0c373e3679b7c`. Ignored local evidence is under `output/logs/pi-reconciliation/20261113T234050Z/`; the corresponding remote run is workspace `runs/20261113T234050Z`. An offline audit verified source/error/closure fields, normal child exit, and original logger/udev preservation. The kernel interface was unbound afterward, consistent with the pinned backend's ordinary detach/dispose behavior; no reset, rebind, or access-rule change was performed.

After Python closed, the owner confirmed live readings updating, RMT off, POWER REF off, and another ten minutes of availability. The separate healthy-confirmation SHA-256 is `479e536d9954f2cedda8d3714eff0abdfdec2cc6611b21698301b56e4a07d3af`. This closed the healthy host gate before the fault was released. The original supervisor receipt retains `front_panel_confirmation: not_provided`.

## Single post-timeout physical result

The owner explicitly authorized the single timeout/reconciliation sequence after confirming the healthy final state. Frozen installed runtime and helper hashes matched before release. The external helper ran one first-CSV 0.5-second acquisition deadline; no production-file change or second induced fault occurred. The original logger's completed setup acquisition and source-off/error-free status preceded the fault.

| Check | Observed result |
| --- | --- |
| Fault | Original `OperationTimeout` retained; acquisition failed after 0.534888 seconds; complete fault helper took 8.316313 seconds |
| Failed-read finish | Existing one-second allowance received the native VisaIOError after 0.032611 seconds; original worker disposed and uncertain-state guard made zero extra I/O |
| Actual USB abort | Endpoint 130 (`0x82`), tag 10, successful initiation `010a`, completed empty input drain, successful eight-byte status `0100000000000000`, and original abort return |
| Failure record | One failed row with blank value/raw and a matching failed sidecar; no late value accepted, sample retry, or normal ASCII cleanup on the uncertain session |
| Independent gate | Complete abort, row, uncertainty, and disposal audit released exactly one fresh physical-supervisor attempt |
| Fresh reconciliation | `communication_reconciled`, reason `verified`, in 0.313163 seconds, at **2026-11-13 23:46:30 UTC** |
| Fresh status | 437B/1.8 matched; POWER REF off, measurement/entry errors zero, absolute W, range 11, filter 17 |
| Closure ordering | SM was observed before cleanup and showed standby true after the interrupted TR2. The bridge then issued TR3 and accepted GTL; the later owner observation establishes the live final display |
| Worker | Stopped, exit code 0, no forced termination; no workflow resumed |
| Preservation | Every original failure-artifact hash and installed runtime hash matched after reconciliation; the original logger and USB rule also matched their preflight snapshots |
| Owner final observation | Owner confirmed live readings updating, RMT off, and POWER REF off after Python closed, without a requested key or cable action |

The failed session is `e729738e-cc35-4903-aa49-b3dc6fa53994`; the new receipt links to it while retaining the failed sample as failed. No source switch, clear/reset, USB reset, reboot, host move, GPIB target change, zero/CAL, firmware operation, or post-fault cable disconnect occurred. The adapter remains on wspr5. Kernel binding remained absent after the pinned backend's ordinary detach/dispose; no separate reset/rebind action was performed.

## Physical evidence and retrieval

The remote run is workspace `runs/20261113T234050Z`. Complete raw evidence, both owner confirmations, and final `result.json` were bundled with SHA-256 `6447e267eec7c87caa579c011301042a330c4987d6b14231b88210c231d7ec89`, retrieved, safely extracted, and independently checked against every listed artifact hash. Ignored complete local evidence is under `output/logs/pi-reconciliation/20261113T234050Z/complete-capture/`; the earlier healthy receipt is also preserved in its original local location.

| Artifact | SHA-256 |
| --- | --- |
| Fault record | `4965198551cc80bcf16f99abb23bd18f90109547434a723b17e4c6d1910027f4` |
| Failed CSV | `0d64470badeafc599d220d3923811a12f22e9ae6b3862606a3ce5b22a380f25e` |
| Failed sidecar | `ac500eba9bd589b7588bcce1d2ccffc1d7860eabe1ea526e52c1289e51264867` |
| USB trace | `7ffa51969a15c3b953fa085cc5011acf6fe8a3cd261d4afde500e6ce334e0da6` |
| Audit releasing one reconciliation | `30abda5411bab35ea9541f4d53d31215976a60d8d0f415a3e3d6915042ecac1c` |
| Fresh reconciliation receipt | `7765f9da38717fb66d889a3b8b8fc239f8323d936c9f0044ce4594a05250831a` |
| Post-timeout owner confirmation | `6b079008c2679f82509fbc523e1ae6f61b6a2c3c95dee735c2ba2f59f850b3d7` |
| Final result | `8cea181957e4b60948051eeabed6e81f8cdfbe8e8d4bf43372f07c14284d9133` |

Both supervisor receipts retain capture-time `front_panel_confirmation: not_provided`. The separate supplied owner observations close the physical cases without rewriting those receipts or manufacturing front-panel evidence. No additional meter session was opened for retrieval or final record checks.

## Owner-assisted move

The Mac has no active meter-control process. Move only the adapter's USB host connection from the Mac to a direct USB **data** port on wspr5. Leave the meter powered, GPIB and sensor/RF connections unchanged, and POWER REF off. Wait about fifteen seconds for enumeration. Confirm the adapter LED is lit, live readings/RMT off/POWER REF off, unchanged warmed-up setup and equipment, other control apps closed, and availability at the meter for about fifteen minutes with PRESET/LOCAL accessible.

After that confirmation, inspect only the selected `03eb:2065` descriptor/node, ordinary-user read/write permissions, existing rule, and kernel binding before opening. No new permission changes or root logging are planned. Use the same named USB serial `HEWLETT-PACKARD_437B_1.8` and expected `HEWLETT-PACKARD,437B,,1.8` reply, with owner-supplied meter `3125U33223` and sensor `MY41094127` labels.

## Bounded physical sequence

1. Run one healthy physical-supervisor attempt in the isolated installed environment, with the existing one-attempt/30-second work/three-second native-finish/60-second total policy and a 70-second external process-group ceiling. Verify actual identity/source/error status, TR3/GTL, and normal worker exit; retrieve and hash its separate receipt. Ask for owner final live/RMT-off/POWER-REF-off confirmation before releasing the fault on this newly tested host.
2. After the healthy case passes and the owner remains available, release exactly one controlled first-CSV 0.5-second acquisition deadline through the unchanged production transport and logger. Ordinary setup/open operations retain 30-second budgets. The external diagnostic subclass validates source-off/error-free setup before the fault. `count=1` prevents another acquisition/fault even if the short read unexpectedly succeeds. The helper is capped at ninety seconds plus bounded disposal.
3. Independently audit the original timeout, blank failed value/raw row, failed sidecar/session, uncertain-state guard with zero extra I/O, skipped ASCII cleanup, and disposed worker. Require actual USB timeout, matching-tag abort initiation, completed empty drain, successful eight-byte completion, and original abort return. A diagnostic worker error alone cannot release a fresh connection.
4. Only that complete audit releases one fresh physical-supervisor attempt, linked to the failed session and saved separately. Verify healthy closure and normal exit, then recheck every original failure hash. The failed measurement remains failed, with no automatic sample retry or workflow continuation.
5. Ask the owner separately for final live readings, RMT off, and POWER REF off. Preserve that observation separately from protocol receipts. Record kernel binding and verify the original logger/udev hashes again. Leave the adapter on the Pi unless the owner requests otherwise.

The post-timeout portion has an eight-minute active budget, excluding owner responses, with a maximum of one newly induced fault. Stop on a failed gate or unexpected success without repeating the fault or switching to another backend. There is no POWER REF switching, clear/reset, USB port reset, reboot, GPIB target change, calibration, firmware operation, or post-fault cable action in the case. If manual recovery becomes necessary, stop and request only the known recovery action actually needed.

## Acceptance limits

The Pi healthy and single post-timeout cases passed with separate owner final confirmations. Mac passes, software-only Pi preparation, and these physical results retain separate evidence. This establishes only the named supervised source-off route on this current Pi/kernel/setup, not already-wedged repair, source-on recovery, arbitrary host/USB faults, unattended RF safety, or automatic continuation. Normal logging remains unchanged; these selected checks do not introduce new mandatory POWER REF features.
