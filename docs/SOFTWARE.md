# Python interface and logging

Phase 2 software milestone, November 11, 2026. The package provides validated command encoding, typed response parsing, serialized acquisition, a pinned open-source VISA transport, and finite CSV sessions. Hardware qualification follows [Phase 3](VALIDATION.md).

## Installation and checks

Python 3.11+ is the project baseline. Local software checks used Python 3.14.10 on macOS ARM64. The CI workflow targets Linux Python 3.11 and 3.14; consult its actual run before claiming CI success. Current-unit Mac measurement/logging and named recovery cases are recorded below. Pi software preflight and identification now pass; later Pi physical cases and replacement acceptance remain pending.

From a checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation -e .
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/python -m pytest -q
.venv/bin/python -m build --no-isolation
```

Runtime pins are PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. `requirements-dev.lock` also pins transitive and development packages for the software-check environment. The project uses the `@py` backend exclusively. A working libusb installation and appropriate device permissions are prerequisites for USB access. On a Mac, prepare libusb for the Python architecture in use; on Raspberry Pi OS, prepare libusb and appropriate USB device permissions. Those are Phase 3 host setup tasks. Keep any Linux kernel USBTMC driver contention distinct from device permissions and record the actual solution.

The worker checks the pinned Python package versions before opening a resource. Dependency changes require revisiting transport evidence and tests. Protocol and demo code import without opening USB or enumerating devices.

## Synthetic demonstration

```bash
mkdir -p output/logs
.venv/bin/hp437b capabilities
.venv/bin/hp437b demo --output output/logs/demo.csv --count 3 --interval 0
```

`capabilities` reports command IDs and explicit guards. `demo` uses synthetic values and writes `simulation: true` in the session metadata. Its firmware text and readings are fixtures for software behavior, rather than observations of the owner's equipment.

## Intended hardware invocation

After separately preparing and authorizing Phase 3, use the actual resource identifier:

```bash
.venv/bin/hp437b log \
  --resource 'USB0::0xVENDOR::0xPRODUCT::SERIAL::INSTR' \
  --output output/logs/run.csv --count 10 --interval 1 --timeout 10 \
  --unit dBm --meter-serial ACTUAL_METER --sensor-serial ACTUAL_SENSOR
```

The resource above is a placeholder. Obtain the actual identifier during explicit host/device setup. The transport accepts USB INSTR resources; a native GPIB resource such as `GPIB0::13::INSTR` uses a different path and is rejected.

Choose `--count` or `--duration` (seconds). The default is ten samples, one-second start-to-start spacing, dBm, and a ten-second operation timeout. `--interval 0` requests the next sample immediately after the preceding one. Duration limits the start of acquisitions; the last operation can extend beyond that duration by its timeout. An overrun starts the next acquisition without accumulating a catch-up backlog, then rebases its next target on the actual start time.

A session reserves a new CSV and `<name>.csv.session.json` before opening the transport. Existing files are protected. Choose an existing writable parent directory. The session explicitly identifies the instrument, sends RL0 and LG/LN, consumes a setup TR2/read, captures SM after that measurement has updated status, then performs serialized TR2/read pairs for CSV rows. The setup acquisition is retained in metadata and excluded from the requested row count. It preserves existing calibration, sensor factors, offset, duty, averaging, and range settings. Consequently CSV values are the meter's configured display-equivalent readings. Record the intended signal path, correction values, frequency, factors, and averaging in the bench record; the initial SM records flags/range/filter, rather than a complete numerical configuration. Full measurement policy remains DEC-02.

## CSV and provenance

| Field | Meaning |
| --- | --- |
| session_id / sequence | UUID shared with sidecar; one-based acquisition attempt |
| received_utc | Host UTC receipt/failure-record time with explicit offset; instrument sample time is unavailable |
| elapsed_s | Monotonic time since acquisition loop start, excluding initial setup |
| overrun_s | Acquisition-start lateness versus the next nominal start target |
| value / unit | Decimal instrument result and actual units; blank value for a measurement error sentinel |
| status | ok, instrument_error, failed, or interrupted |
| instrument_error / error | Instrument error code, or host error category/message |
| raw_hex | Exact completed reply bytes, including terminators, or available last reply on failure |

The sidecar records schema version, simulation flag, user-provided unit identities/resource, host/Python, dependency versions for VISA sessions, raw identification, raw setup measurement and initial SM, settings, row count, last raw reply, and completion/failure/interruption. CSV rows flush individually; sidecar replacement is atomic and occurs at setup milestones and finalization. A forced process termination or storage failure may leave a partial CSV and a starting/running metadata record. Inspect those artifacts before reuse; row count describes persisted attempts at finalization, including error rows, rather than only valid measurements.

Instrument error sentinels produce an `instrument_error` row and collection continues. Malformed responses, transport failures, unexpected unit changes, and cancellation stop the session and retain available diagnostics. Interrupt exits with code 130; ordinary application errors exit with code 1. Cleanup failures are recorded as failures when metadata storage remains available.

## Library usage

```python
from hp437b import Instrument, VisaTransport

transport = VisaTransport(actual_usb_resource)
device = Instrument(transport, timeout=10)
try:
    transport.open(timeout=10)  # Explicit device access.
    identity = device.identify()
    device.configure_absolute("dBm")
    reading = device.acquire("TR2")
finally:
    device.close()
```

This illustrates the intended Phase 3 invocation. `Instrument` and `VisaTransport` construction are I/O-free. Typed operations are:

- `command(code, value=None, confirmed=False, ...)`: validated whole-command actions/setters. Example: `command("FM", 128)` or `command("FR", 300, unit="MZ")`.
- `query(code)`: an atomic output-select/read/parse transaction returning `Reply(raw, value)`. Available candidates include SM, *IDN?, OD, LP2, and the documented ASCII status/mask/error queries. It preserves side-effect uncertainty rather than assuming a generic error queue or read-clear policy.
- `identify()` and `read_status()`: typed convenience queries with raw bytes retained.
- `configure_absolute(unit)`: serialized RL0 plus LG/LN; `acquire("TR1"/"TR2")` performs trigger/read under one lock, and `acquire(None)` reads the current output without triggering.
- `zero(confirmed=True)` and `calibrate(reference_factor, confirmed=True)`: prepared-setup procedures requiring a transport with an actual `serial_poll` method and advertised capability. They guard before I/O with the supplied VISA transport because released PyVISA-py 0.8.1 lacks that route.
- `bus(id)`: G008 requests Go To Local only with a negotiated USB488 transport profile; other deferred bus operations and the G020 exclusion remain guarded. G002/G003/G004 use byte transactions. Healthy `Instrument.close()` first requests TR3 free-run and then G008 before closing, so ordinary logger sessions need no separate local-return call.
- `encode(code, value, ...)`: pure byte encoding keyed to stable registry IDs. Contextual EN/unit/percent/cursor tokens are encoder helpers, not standalone device transactions.

`command("PR")`, RC, ST, OC1, and RF table reference-factor writes require `confirmed=True` because they alter configuration, output, or storage. DD requires identification establishing firmware 1.5+. Pure encoding performs zero I/O, and its availability establishes syntax support rather than a physical result. Numeric setters require exact legal grid values; callers select rounding explicitly. FM accepts the ten exact powers of two. Arbitrary command concatenation and free-form menu entry are outside the typed API.

The seven contextual P tokens and four cursor codes have encoding coverage while standalone driver calls are rejected. Among the other variants, zero/calibration procedures are implemented against a scripted polling-capable transport but guarded with the supplied production transport. See the [coverage matrix](inventory/COVERAGE.md) for the precise distinction.

## Deadlines and recovery

The driver serializes complete query/acquisition/binary transactions. It awaits a triggered response without sending ASCII *STB? or SM during the pending interval. Those incoming commands can abort an unfinished operation. Calibration/zero completion uses serial polling only with a capable transport. A source-level method stub or a named USB request constant establishes insufficient support.

VISA runs in a spawned worker process. Each RPC has a monotonic deadline; an error, timeout, or cancellation terminates the worker, with bounded process cleanup (up to approximately one additional second). This bounds the host wait even if the backend stalls. Terminating the worker cannot retract an accepted instrument command or prove that the meter is idle. No automatic retry, reset, zero, reference restoration, or status query is sent during recovery/shutdown.

The instrument enters uncertain state after an interrupted/failed transaction and rejects further transactions. Reconcile the device and message stream explicitly using a Phase 3-approved procedure; reopen the transport if needed. `acknowledge_external_recovery(confirmed=True)` then clears the software uncertainty and requires units/firmware to be re-established. A closed Instrument requires a new instance. Output preflight failures retain caller ownership of an already-connected library transport; after successful file reservation, collection owns cleanup. Keep separate driver instances away from the same physical device during acquisition.

## Coverage and qualification

Software coverage is 78 implemented/tested command or syntax variants and 40 explicitly deferred variants. Eleven of the 78 are contextual encoder helpers; two more are zero/calibration procedures whose required polling transport is unavailable in the pinned production path. These counts describe software components, not 78 proven device operations. Bus coverage is three byte-transfer/framing paths, one conditional USB488 Go To Local path, fifteen explicit deferrals, and one instrument exclusion.

Deferred commands cover CT/ET/SN table operations, identification aliases, bare LP, legacy RV/@1/@2 framing/restore, reset/self-test/menu operations, and DF. Each guard cites the relevant [A01–A09 source issue](inventory/AMBIGUITIES.md). RF table reference writes use the detailed documented syntax and require explicit confirmation; structured table traversal/restore remains deferred. The public library uses source-backed candidate grammar pending actual firmware/transport validation.

The initial Mac batch established resource access, identification, and operator-confirmed local restoration. Subsequent records establish units/status framing, TR2/read, reference logging, and one named timeout/manual-recovery case; retain their version/host/setup limits. Record the actual meter and sensor identities; qualify the replacement meter separately from current-unit observations with the known supply discrepancy.

## Phase 3 host-access observation

The November 11 [Mac identification batch](validation/MAC-20261111.md) found that the restricted execution process could see macOS USB registry information while PyUSB enumerated no adapter. Read-only discovery outside that restriction found the adapter, and the pinned production transport then returned HP 437B firmware 1.8. Keep process access separate from libusb installation, device permissions, and backend compatibility; do not change host security settings or dependency pins to work around this observation. Subsequent Mac qualification records cover reference logging and one manual recovery path; Pi/replacement acceptance remains pending.

## Qualified short reference session and local return

The [November 11 Mac short session](validation/MAC-20261111-SHORT-LOG.md) produced three valid reference readings, complete CSV/metadata, and a passing existing-file protection check. This is current-meter evidence, not sustained logging, real-radio input, or replacement/Pi acceptance. The logger uses one connection for the whole run. The new [automatic-local extension](validation/AUTOMATIC-LOCAL.md) negotiates Go To Local for XyphroLabs `03eb:2065` and requests it before closing a healthy Instrument session. Identification and a production reference-off logger session passed on the current Mac/unit, including owner confirmation of local control without PRESET/LOCAL. Keep the operator available for failure recovery. Unknown adapters/capabilities still require manual restoration. Failed or uncertain instrument transactions skip automatic local return. Automatic failed-transfer recovery remains unqualified; the [manual USB-reconnect recovery case](validation/FAILURE-RECOVERY.md) is separately verified. Merely closing USB does not prove local restoration.

The extension is project-local code over the exact pinned backend session and its existing PyUSB handle; PyVISA-py itself is unchanged. It validates adapter identity, interface, capability/status framing, and GO_TO_LOCAL acceptance under the worker deadline. Logger sidecars include `local_return` with accepted/failed request evidence; a cleanup failure marks the session failed. USB acceptance is distinguished from front-panel verification. Cleanup can consume an additional operation timeout before bounded worker disposal. No reference-source switching or failed-transfer recovery is part of Go To Local.

Normal cleanup explicitly sends `TR3` before USB488 GTL: the initial GTL-only path cleared RMT but could leave TRIGGER HOLD displayed. The [corrected physical cases](validation/AUTOMATIC-LOCAL.md#p3-r10-corrected-results-and-final-reassessment) verify standby false and numeric display after close, followed by owner confirmation. Sidecars add `instrument_cleanup` to distinguish the free-run command from the separate local request. Failed TR3 suppresses GTL and fails cleanup; uncertain transactions send neither. `bus("G008")` remains a pure GTL operation and does not imply TR3.

## Qualified remote reference control

The [Mac unit/reference batch](validation/MAC-20261111-CONTROL.md) verified LG/LN restoration and `command("OC0")` / `command("OC1", confirmed=True)` on the prepared internal reference/sensor path, ending source off and live local. No manual source switching is required for a procedure that explicitly uses this route and verifies its final state. The generic logger preserves source state; its TR3/GTL cleanup does not turn POWER REF off. Keep source control explicit and separate from uncertain-state recovery.

## Qualified interruption and manual failure recovery

The [November 11 failure cases](validation/FAILURE-RECOVERY.md) verified a single SIGINT sent to the CLI between completed reads: exit 130, one retained valid row, interrupted final metadata, healthy TR3/GTL cleanup, and fresh-session acquisition. An induced 0.5-second deadline during a real TR2/read failed after 0.504 seconds, saved a blank-value failed row and failed sidecar, disposed the worker, blocked reuse before extra I/O, and skipped normal cleanup commands. The configured setup timeout and harness override were recorded explicitly; the induced deadline is not evidence of a spontaneous meter fault.

For that tested timeout, operator-assisted recovery used only adapter USB disconnect/reconnect with meter power retained and POWER REF off, followed by fresh identity, status, complete acquisition, corrected free-run/local cleanup, independent free-run/display verification, and owner confirmation. This is a qualified named manual procedure on the recorded setup, not unattended recovery or device-clear support. Do not replace the physical/protocol reconciliation with reopening or `acknowledge_external_recovery` alone, and do not silently retry.

## Raspberry Pi USB permissions

The [Pi qualification record](validation/PI-QUALIFICATION.md) found the XyphroLabs `03eb:2065` USB device root-owned without user write access on Debian 13.7. PyUSB/libusb needs read/write access to its `/dev/bus/usb` node; access to `/dev/usbtmc0` alone does not supply that. The owner authorized a permanent vendor/product-scoped rule, provided in [70-hp437b-usbgpib.rules](../config/udev/70-hp437b-usbgpib.rules), granting the existing `plugdev` group mode 0660. This grants members access to matching adapters, rather than granting all users access or running the logger as root.

On a Linux host with that group, review the rule, confirm the logging account is already a member (`id`), and install it with administrator authorization:

```bash
sudo install -m 0644 config/udev/70-hp437b-usbgpib.rules /etc/udev/rules.d/70-hp437b-usbgpib.rules
sudo udevadm control --reload-rules
```

Reconnect only the adapter USB cable while no control session is open, or trigger a change event for the specifically identified USB sysfs device. Inspect the current device node after enumeration and verify ordinary-user read/write access before opening it. USB bus/device numbers change across reconnects. Any group-membership change is a separate host administration step and may require a fresh login; no such change was needed on the tested Pi. Removing the installed rule, reloading rules, and reconnecting reverses this configuration. Do not overwrite an existing rule without review.

On this Pi the kernel `usbtmc` driver was initially bound. The pinned PyVISA-py USB path detaches interface 0 when opening, then disposes resources on close without explicitly reattaching the kernel driver. The identification run succeeded with ordinary-user permissions after rule activation; no module blacklist, service change, or manual unbind was required. Record binding/reconnect behavior separately from instrument TR3/Go To Local cleanup. This identification result does not qualify the remaining Pi logging/recovery cases.

## Pi-only recovery candidate status

The [USB port-reset experiment](validation/PI-ONLY-RECOVERY.md) is not a qualified recovery procedure: healthy reset verification passed, but the post-timeout run was followed by loss of Pi reachability and an owner restart before protocol verification. Cause remains unproven. No reset command or implicit retry has been added to this package; retain uncertainty and the documented manual routes. USBTMC/device clear remains separately guarded while its source-backed procedure is prepared.
