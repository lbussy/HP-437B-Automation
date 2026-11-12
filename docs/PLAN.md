# Control and logging plan


Saved from the November 8, 2026 discussion at the user's request, and amended November 9 with the provisional open-source backend and validation plan. Phase 2 software was executed at the user's request on November 11; hardware qualification follows when the setup is ready.

### User requirements and current state

- Collect power readings from the 437B using a Mac or Raspberry Pi.
- Current-setup adapter readiness HP-02 is complete for the tested supervised Mac/Pi profile; the Phase 2 Python interface and logger are implemented, with replacement acceptance tracked under Phase 3.
- Phase 2 implementation was explicitly authorized on November 11. Phase 3 execution was explicitly authorized on November 11; the [batch plan](validation/PHASE-3-PLAN.md) records successive supervised Mac batches, and the [Pi plan](validation/PI-QUALIFICATION.md) defines second-host gates.
- On November 11, 2026, the user reported that the seller/calibrator confirmed the current meter's [documented +5 V supply discrepancy](EQUIPMENT.md#individual-calibration-records) was unacceptable. The user plans to exchange the meter after a few development steps with it. Current-unit Mac measurement, control, logging, and named manual-recovery batches have passed; Pi reference/control/logging and a [named manual Pi-only recovery](validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) are recorded, and the exchange remains pending. Keep current-unit observations separate from replacement qualification.

### Adapter recommendation

The assistant recommended the **XyphroLabs USBGpib V2**, a USB-C to GPIB controller, for this single-instrument setup. [Binho's product listing](https://binho.io/test-measurement/products/usbgpib-v2/) showed **US$59 and in stock** when checked during the November 8 discussion. Price and availability are historical observations and should be checked before purchase. The [developer's project](https://github.com/xyphro/UsbGpib) identifies Binho as a distribution partner.

The [adapter manual](https://github.com/xyphro/UsbGpib/blob/master/Tutorials/UsbGpibV2_manual.md), sections “Advantages of UsbGpib V2 adapter,” “Using the adapter,” and “Technical specifications,” documents controller operation, GPIB reads, writes, and triggering, USBTMC communication, macOS and Linux support, and PyVISA/PyVISA-py integration. See the [developer's setup tutorials](https://github.com/xyphro/UsbGpib/tree/master/Tutorials) for platform-specific setup. These are manufacturer/developer claims, not local validation of this adapter with the user's 437B, Mac, or Pi.

The adapter supports **control as well as data collection**. The 437B operating manual, §3-14, Table 3-2, printed page 3-25, states that measurement results are available over HP-IB and that operations other than the LINE switch and HP-IB address setting are bus programmable. Use the meter's own command reference for implementation; a USBTMC adapter does not change the meter's command language to modern SCPI.

The adapter can plug directly into the meter's rear HP-IB connector. Plan for a USB data cable matching the host connector and the adapter's USB-C socket; use a GPIB extension cable only if physical clearance requires it. Confirm the purchased model is **USBGpib V2**, since other adapters and later versions may require different setup.

An alternative discussed was the [Prologix GPIB-USB controller](https://prologix.biz/product/gpib-usb-controller/), listed at **US$299.95** during the same discussion. It supports macOS and Linux through a virtual serial interface and would require a different software transport from the USBGpib V2. The USBGpib V2 remains the saved recommendation. A XyphroLabs GpibUsb adapter is now present; exact PCB revision is unmarked/unverified and accepted as a metadata limitation at the owner's direction.

### Proposed Mac/Pi workflow

The assistant proposed leaving a Pi beside the meter for longer runs:

437B → USBGpib V2 → USB data cable → Raspberry Pi → timestamped CSV files

The Mac would start collection and retrieve files over the local network, for example through SSH and file transfer. Direct USB connection to the Mac is also an intended option. A small Python logger would configure the meter, trigger or request readings using its documented commands, and record results. Mac and Pi are the selected hosts. The [adopted initial policy](validation/MEASUREMENT-POLICY.md) uses W, automatic range/filter, a one-second requested interval, finite five-minute runs, and the existing CSV/sidecar fields. Actual achieved timing is reported; production CLI defaults remain unchanged.

### Provisional open-source software choice

The user asked for an open-source alternative to R&S VISA and approved adding a provisional-backend validation plan on November 9. The proposed stack is:

Python logger → PyVISA → PyVISA-py → PyUSB/libusb → USBGpib V2 → 437B

[PyVISA-py](https://github.com/pyvisa/pyvisa-py) is an MIT-licensed Python backend for PyVISA; it is separate from PyVISA itself. Its [USB installation documentation](https://github.com/pyvisa/pyvisa-py/blob/main/docs/source/installation.rst) describes PyUSB and a USB backend such as libusb. The adapter's normal USBTMC firmware uses this USB path, rather than the native GPIB-driver path. Select the backend explicitly with `pyvisa.ResourceManager("@py")` during validation.

**The stack has named current-unit Mac/Pi evidence; final replacement acceptance remains pending.** In the adapter manual's FAQ, under “Do I really need to use a VISA library?”, the author describes PyVISA-py's USBTMC implementation as incomplete and mentions version queries and advanced features. That is the adapter author's assessment, not an independently reproduced failure with the latest released backend or this 437B. It does not establish that ordinary control and logging will fail or that the adapter is unsuitable. The [backend changelog](https://github.com/pyvisa/pyvisa-py/blob/main/CHANGES) also contains ongoing USBTMC work; unreleased improvements must not be treated as capabilities of an installed release.

Keep the USBGpib V2 recommendation. Accept PyVISA-py for this application only after the required operations pass hardware testing: configuration, power readback against the front panel, required trigger and status operations, termination, timeout recovery, and sustained logging. Record exact released package and adapter firmware versions, tested operations, and results. An unrelated unsupported feature need not disqualify a stack that passes these requirements.

If a required operation fails, investigate configuration or a reproducible backend defect before deciding whether to fix it or change backends. R&S VISA remains a possible proprietary fallback, not the selected open-source solution. Its royalty-free object-code license and platform compatibility would need consideration before adopting it. Do not promise full orchestration through PyVISA-py until the operations actually required have been validated.

### Decision register

| Decision | Current position | Still needed |
| --- | --- | --- |
| Instrument and goal | Initial supervised reference-bench absolute-power readback/logging on Mac and Pi | Future external-radio/frequency/path or multi-instrument orchestration is separate from this initial profile |
| Adapter | Arrived: XyphroLabs USBGpib V2 (owner-reported marking), USB `03eb:2065`, detected on this Mac November 11 | Adapter firmware `V2.4` was read through the [documented internal query](validation/ADAPTER-IDENTIFICATION.md); Anker USB-C cable and front-panel meter GPIB address 13 are owner-reported; exact PCB revision is an accepted unknown. Recheck the replacement meter's identity and address during acceptance. Instrument USB identification content is not adapter firmware |
| Language and API | Python/PyVISA interface/logger and named current-unit physical cases implemented and recorded | Repeat required declared-profile cases on replacement and actual sensor |
| Open-source backend | Pinned PyVISA-py 0.8.1 with named current-unit Mac/Pi cases and explicit bus guards | Final replacement acceptance for the adopted profile; unrelated bus gaps retain deferrals |
| Host | MacBook Pro ARM64/macOS and Pi 5/aarch64 Debian with separate per-case environments; current-unit shutdown fix verified on both | Repeat mandatory cases on replacement; broad recovery and unattended operation remain outside profile |
| Logging behavior | [DEC-02 complete](validation/MEASUREMENT-POLICY.md): W, automatic range/filter, interval 1 second requested, duration 300 seconds, actual timing reported, existing CSV/sidecar | Run adopted settings on the actual replacement; CLI defaults remain unchanged |
| Measurement setup | Prepared internal-reference path and actual sensor/factor policy recorded; [replacement procedure ready](validation/REPLACEMENT-ACCEPTANCE.md) | Verify actual arriving meter/sensor identity, applicable records/factors, warm-up and preparation; final physical acceptance pending |

### Qualification sequence after adapter arrival

1. Record the actual adapter model/firmware, Mac architecture and macOS version, or Pi model and OS. Confirm USB cabling and the meter's configured GPIB address.
2. Follow the adapter's platform tutorial, install and record the candidate software versions, and establish basic communication with the provisional PyVISA-py USB backend. Confirm the 437B's command syntax, output format, termination, and trigger/read behavior from its operating manual before writing the logger.
3. Verify a software reading against the front-panel display and exercise a reversible remote setting. Confirm units, status/error handling, and return to local operation. Do not assume calibration or zeroing should run automatically; derive any such procedure from the manuals and the actual bench setup.
4. Choose the host, logging interval, duration, and CSV fields. Account for meter averaging, range changes, and settling; the current Mac/unit achieved approximately one-second receipt spacing in the recorded five-minute reference case; additional hosts and other range/filter/signal conditions require their own evidence.
5. Implement and validate the Python logger on the selected host, including timestamps, explicit units, timeouts, invalid readings, and clean shutdown. Test required triggering/status operations, recovery after a timeout, and a sustained logging run before accepting the backend. For Pi logging, verify Mac access and file retrieval. Validate each additional host before claiming support. Record actual bench results and any adapter-specific limitations here.


## Three-phase execution

1. ✅ Complete — Phase 1: Inventory; use the [command and GPIB reference](inventory/README.md) and [coverage matrix](inventory/COVERAGE.md).
2. ✅ Complete — Phase 2: Implement; the [software milestone](SOFTWARE.md) provides the interface/logger and records deferred coverage in the [review](PHASE-2-REVIEW.md). The [execution prompt](prompts/phase-2-implementation.md) is retained. Resolve transport requirements using the [released-backend evidence](inventory/GPIB.md#transport-evidence-profiles) and [source questions](inventory/AMBIGUITIES.md).
3. ⏳ In progress — Phase 3: Qualify; execution started November 11 with the [communication-only batch](validation/PHASE-3-PLAN.md). Verify required capabilities on Mac and Pi with recorded results and limitations; replacement/sensor acceptance remains pending.

The [Phase 1 review](inventory/REVIEW.md) recommends the first batch and documents command sequencing constraints. Preserve separate documentation, implementation, software-test, Mac, and Pi statuses. PyVISA-py remains provisional for complete bus control.

## Related records

See [open work](OPEN-WORK.md), [equipment references](EQUIPMENT.md), and the [hardware validation plan](VALIDATION.md).

## Phase 2 software choices

Python 3.11+ is the baseline; local checks used Python 3.14.10 on macOS ARM64. Runtime pins are PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1, with @py selected explicitly. The finite logger defaults are ten samples, one-second interval, dBm, and ten-second operation timeout; user options override these software defaults. DEC-01 and DEC-02 record the selected hosts and explicit initial run policy; the software defaults remain unchanged. See [usage](SOFTWARE.md) for exact behavior and qualification limits.

## Automatic local-return implementation

The owner requested removing the manual PRESET/LOCAL step after runs. The [project-local USB488 extension](validation/AUTOMATIC-LOCAL.md) retains dependency pins and reuses the existing USB handle to request Go To Local on healthy Instrument close. Other bus features and uncertain-state recovery remain guarded. Initial Mac physical verification is tracked separately from software tests, Pi, and replacement acceptance.

## Pre-arrival completion boundary

The owner selected the initial reference-bench logging policy and directed completing all available Phase 3 work without further input before replacement arrival. [Pre-arrival review](validation/PRE-ARRIVAL-REVIEW.md) closes current-setup metadata, policy, local evidence auditing, matrix/status reconciliation, and [replacement execution preparation](validation/REPLACEMENT-ACCEPTANCE.md). No new production change or current-meter experiment is required for this preparation. HP-01, PHASE-03, and VAL-01 stay open for actual replacement identity/calibration/setup, mandatory cases on both hosts, and final acceptance review. Exact PCB revision is an accepted unknown, and the lack of an external radio does not block the adopted internal-reference profile.

## Hardware-free software qualification

The [offline software campaign](validation/OFFLINE-QUALIFICATION-RESULTS.md) extends parameter, parser, synthetic logger, storage-fault, process/deadline, and clean-install evidence on an isolated local branch. It changes no runtime source or physical qualification status. Replacement identity/setup and declared-profile acceptance on both hosts remain required.
