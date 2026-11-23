# Python interface and logging

The package provides typed command encoding, response parsing, serialized acquisition, bounded worker shutdown, and finite CSV sessions. See [current validation](VALIDATION.md) for equipment-specific checks.

## Installation and checks

Python 3.11+ is the project baseline. The CI workflow targets Linux Python 3.11 and 3.14; inspect its actual result before claiming CI success. Physical interaction checks on the current meter remain pending on both selected hosts.

From a checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation -e .
.venv/bin/ruff check src tests tools
.venv/bin/ruff format --check src tests tools
.venv/bin/python tools/offline_qa.py -- .venv/bin/python -m pytest -q
.venv/bin/python tools/offline_qa.py -- .venv/bin/python -m build --no-isolation
```

The offline QA launcher blocks inspected VISA/USB/serial entry points before application imports and supervises spawned processes. It is an accident guard, not containment of arbitrary native code. Use it for software tests. Set `HP437B_STRESS=1` for opt-in bounded synthetic campaigns.

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

A session reserves a new CSV and `<name>.csv.session.json` before opening the transport. Existing files are protected. Choose an existing writable parent directory. The session explicitly identifies the instrument, sends RL0 and LG/LN, consumes a setup TR2/read, captures SM after that measurement has updated status, then performs serialized TR2/read pairs for CSV rows. The setup acquisition is retained in metadata and excluded from the requested row count. By default, it preserves existing calibration, sensor factors, offset, duty, averaging, and range settings. Explicit serial-specific sensor correction can instead set CAL FAC before acquisition, as described below. Consequently CSV values are the meter's configured display-equivalent readings. Record the intended signal path, correction values, frequency, factors, and averaging in the bench record; the initial SM records flags/range/filter, rather than a complete numerical configuration. See the [measurement policy](validation/MEASUREMENT-POLICY.md).

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

VISA runs in a spawned worker process. Each RPC has a monotonic deadline. If a dispatched read exceeds that deadline, the parent allows up to one additional second for the existing backend read/abort handling to finish before disposing the worker. This separate failure-shutdown allowance does not extend the deadline for accepting a measurement: a late successful reply is discarded, the timeout still fails the acquisition, and the Instrument remains uncertain. Successful reads, native read budgets, logging defaults, and non-read timeout behavior are unchanged. An error, timeout, or cancellation still disposes the worker, with existing bounded process cleanup (up to approximately one further second). Terminating the worker cannot retract an accepted instrument command or prove that the meter is idle. No new parent recovery command, automatic retry, reset, zero, reference restoration, or status query is sent during shutdown; the backend may complete its existing USB abort sequence.

The instrument enters uncertain state after an interrupted/failed transaction and rejects further transactions. Reconcile the device and message stream explicitly using a Phase 3-approved procedure; reopen the transport if needed. `acknowledge_external_recovery(confirmed=True)` then clears the software uncertainty and requires units/firmware to be re-established. A closed Instrument requires a new instance. Output preflight failures retain caller ownership of an already-connected library transport; after successful file reservation, collection owns cleanup. Keep separate driver instances away from the same physical device during acquisition.

## Coverage and qualification

Software coverage is 78 implemented/tested command or syntax variants and 40 explicitly deferred variants. Eleven of the 78 are contextual encoder helpers; two more are zero/calibration procedures whose required polling transport is unavailable in the pinned production path. These counts describe software components, not 78 proven device operations. Bus coverage is three byte-transfer/framing paths, one conditional USB488 Go To Local path, fifteen explicit deferrals, and one instrument exclusion.

Deferred commands cover CT/ET/SN table operations, identification aliases, bare LP, legacy RV/@1/@2 framing/restore, reset/self-test/menu operations, and DF. Each guard cites the relevant [A01–A09 source issue](inventory/AMBIGUITIES.md). RF table reference writes use the detailed documented syntax and require explicit confirmation; structured table traversal/restore remains deferred. The public library uses source-backed candidate grammar pending actual firmware/transport validation.

## Raspberry Pi USB permissions

PyUSB/libusb needs ordinary-user read/write access to the adapter’s `/dev/bus/usb` node. The supplied [vendor/product-scoped udev rule](../config/udev/70-hp437b-usbgpib.rules) grants the `plugdev` group mode 0660 access to matching `03eb:2065` adapters. Review actual host group membership and permissions before use; `/dev/usbtmc0` access alone is insufficient.

On a Linux host with that group, review the rule, confirm the logging account is already a member (`id`), and install it with administrator authorization:

```bash
sudo install -m 0644 config/udev/70-hp437b-usbgpib.rules /etc/udev/rules.d/70-hp437b-usbgpib.rules
sudo udevadm control --reload-rules
```

Reconnect only the adapter USB cable while no control session is open, or trigger a change event for the specifically identified USB sysfs device. Inspect the current device node after enumeration and verify ordinary-user read/write access before opening it. USB bus/device numbers change across reconnects. Any group-membership change is a separate host administration step and may require a fresh login.  Removing the installed rule, reloading rules, and reconnecting reverses this configuration. Do not overwrite an existing rule without review.

The pinned USB backend may detach a kernel USBTMC driver during open. Record actual binding/permissions behavior on the selected host; do not infer instrument local/source state from USB ownership.

## Reusable provenance

The hardware-free [PROV-01 module](RUN-PROVENANCE.md) adds reusable run/DUT/equipment records and a separate `python -m hp437b.provenance --bundle EXISTING_WF01_BUNDLE --output NEW_DIRECTORY` command. This reads finalized evidence and creates a detached export. New WF-01 runners emit a sibling `.provenance` directory after sealing the capture. Ordinary logger/demo behavior, CLI defaults, CSV/session schema, and dependency pins are unchanged.

## Offline reports and agent-assisted analysis

Use the separate [REPORT-01 reporting module](REPORTING.md) for existing WF-01 bundles and PROV-01 records. The optional `reports` extra provides plotting; ordinary logger dependencies, CLI behavior, CSV output, and physical workflow capture remain unchanged. Reports and analysis drafts are derived artifacts with their own inventories.

## Offline pipeline acceptance

The [E2E-01/VAL-01 runner](validation/PIPELINE-ACCEPTANCE.md) executes seven fresh synthetic cases and can replay explicit retained bundles through provenance, analysis, and reports. Use `tools/offline_qa.py` with a finite deadline. Scripted analysis fixtures test the handoff; supplied agent drafts retain their exact bindings and attribution. Ordinary runtime and defaults remain unchanged.

## Human-started deterministic reports

Use [RUN-01](workflows/DETERMINISTIC-RUN.md) for the optional `--report-output` workflow argument or `python -m hp437b.workflow_report` saved-bundle command. It generates provenance and a richer report automatically after capture closes. No model/provider integration is involved; normal logger behavior and defaults remain unchanged.

## Operator-guided series

[GUIDED-01](workflows/OPERATOR-GUIDED-SWEEPS.md) adds a separate guided runner and local interface mode for frequency, drive-setting, and combined radio sweeps. The existing finite logger performs each confirmed capture. `python -m hp437b.operator_ui --sweep-setup FILE.json` enables an explicitly configured bench meter; simulated operation remains available without that option. `python -m hp437b.guided_client --help` exposes local orchestration actions, and `python -m hp437b.guided_report --help` supports report-only regeneration. Read the linked setup/evidence limits before measured captures; new physical sweep acceptance remains pending.

## Automatic serial-specific sensor correction

For sensor **8482A MY41094127**, supply both `--sensor-correction 8482a-MY41094127-20261015` and `--frequency-hz` to `hp437b log`, with matching `--sensor-serial MY41094127`. For example, add `--frequency-hz 10140200` for the 30 m test. Profile/frequency/sensor validation occurs before opening the meter. This selects **101.1% CAL FAC**, preserves the completed ZERO/CAL, and records the calculation and certificate hash in the session receipt. It does not infer the transmitter frequency or change stored sensor tables.

The same correction is available per confirmed frequency in [guided sweeps](workflows/OPERATOR-GUIDED-SWEEPS.md#automatic-8482a-frequency-correction). Lookup uses linear interpolation in Hz, rounds half up to 0.1%, and rejects extrapolation. Corrected captures require error-free post-command SM, with offset and duty correction off; the receipt distinguishes command completion/status checking from independent numeric factor readback. These are sensor-input indications, without automatic fixture corrections, baseline subtraction, or a complete uncertainty budget.
