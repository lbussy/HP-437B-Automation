# Control and logging plan


Saved from the November 8, 2026 discussion at the user's request, and amended November 9 with the provisional open-source backend and validation plan. Resume when an adapter is available and the user requests implementation.

### User requirements and current state

- Collect power readings from the 437B using a Mac or Raspberry Pi.
- The user does not yet have a GPIB adapter. No purchase, adapter connection, logging implementation, or bench validation is recorded.
- Preserve this recommendation and plan for later work; saving it does not authorize purchasing hardware or implementing the logger now.

### Adapter recommendation

The assistant recommended the **XyphroLabs USBGpib V2**, a USB-C to GPIB controller, for this single-instrument setup. [Binho's product listing](https://binho.io/test-measurement/products/usbgpib-v2/) showed **US$59 and in stock** when checked during the November 8 discussion. Price and availability are historical observations and should be checked before purchase. The [developer's project](https://github.com/xyphro/UsbGpib) identifies Binho as a distribution partner.

The [adapter manual](https://github.com/xyphro/UsbGpib/blob/master/Tutorials/UsbGpibV2_manual.md), sections “Advantages of UsbGpib V2 adapter,” “Using the adapter,” and “Technical specifications,” documents controller operation, GPIB reads, writes, and triggering, USBTMC communication, macOS and Linux support, and PyVISA/PyVISA-py integration. See the [developer's setup tutorials](https://github.com/xyphro/UsbGpib/tree/master/Tutorials) for platform-specific setup. These are manufacturer/developer claims, not local validation of this adapter with the user's 437B, Mac, or Pi.

The adapter supports **control as well as data collection**. The 437B operating manual, §3-14, Table 3-2, printed page 3-25, states that measurement results are available over HP-IB and that operations other than the LINE switch and HP-IB address setting are bus programmable. Use the meter's own command reference for implementation; a USBTMC adapter does not change the meter's command language to modern SCPI.

The adapter can plug directly into the meter's rear HP-IB connector. Plan for a USB data cable matching the host connector and the adapter's USB-C socket; use a GPIB extension cable only if physical clearance requires it. Confirm the purchased model is **USBGpib V2**, since other adapters and later versions may require different setup.

An alternative discussed was the [Prologix GPIB-USB controller](https://prologix.biz/product/gpib-usb-controller/), listed at **US$299.95** during the same discussion. It supports macOS and Linux through a virtual serial interface and would require a different software transport from the USBGpib V2. The USBGpib V2 remains the saved recommendation, not a confirmed user purchase decision.

### Proposed Mac/Pi workflow

The assistant proposed leaving a Pi beside the meter for longer runs:

437B → USBGpib V2 → USB data cable → Raspberry Pi → timestamped CSV files

The Mac would start collection and retrieve files over the local network, for example through SSH and file transfer. Direct USB connection to the Mac is also an intended option. A small Python logger would configure the meter, trigger or request readings using its documented commands, and record results. The host choice, collection interval, run duration, and final CSV fields remain to be decided with the user.

### Provisional open-source software choice

The user asked for an open-source alternative to R&S VISA and approved adding a provisional-backend validation plan on November 9. The proposed stack is:

Python logger → PyVISA → PyVISA-py → PyUSB/libusb → USBGpib V2 → 437B

[PyVISA-py](https://github.com/pyvisa/pyvisa-py) is an MIT-licensed Python backend for PyVISA; it is separate from PyVISA itself. Its [USB installation documentation](https://github.com/pyvisa/pyvisa-py/blob/main/docs/source/installation.rst) describes PyUSB and a USB backend such as libusb. The adapter's normal USBTMC firmware uses this USB path, rather than the native GPIB-driver path. Select the backend explicitly with `pyvisa.ResourceManager("@py")` during validation.

**This is a candidate stack, not verified compatibility.** In the adapter manual's FAQ, under “Do I really need to use a VISA library?”, the author describes PyVISA-py's USBTMC implementation as incomplete and mentions version queries and advanced features. That is the adapter author's assessment, not an independently reproduced failure with the latest released backend or this 437B. It does not establish that ordinary control and logging will fail or that the adapter is unsuitable. The [backend changelog](https://github.com/pyvisa/pyvisa-py/blob/main/CHANGES) also contains ongoing USBTMC work; unreleased improvements must not be treated as capabilities of an installed release.

Keep the USBGpib V2 recommendation. Accept PyVISA-py for this application only after the required operations pass hardware testing: configuration, power readback against the front panel, required trigger and status operations, termination, timeout recovery, and sustained logging. Record exact released package and adapter firmware versions, tested operations, and results. An unrelated unsupported feature need not disqualify a stack that passes these requirements.

If a required operation fails, investigate configuration or a reproducible backend defect before deciding whether to fix it or change backends. R&S VISA remains a possible proprietary fallback, not the selected open-source solution. Its royalty-free object-code license and platform compatibility would need consideration before adopting it. Do not promise full orchestration through PyVISA-py until the operations actually required have been validated.

### Decision register

| Decision | Current position | Still needed |
| --- | --- | --- |
| Instrument and goal | User wants automated 437B data collection from Mac or Pi; remote control is also of interest | Define the initial measurement sequence and any other instruments to coordinate |
| Adapter | USBGpib V2 remains the recommendation; the Amazon listing shared November 9 is [ASIN B0GF2D6VJW](https://www.amazon.com/dp/B0GF2D6VJW) | Confirm purchase/arrival, model, firmware, and cable; no purchase is recorded |
| Language and API | Python with PyVISA is proposed | Confirm during implementation; no logger exists yet |
| Open-source backend | PyVISA-py is the provisional first candidate | Pass the hardware validation above on each intended host |
| Host | Mac direct USB or Pi beside the meter, with Mac network access, are proposed options | Choose the first host and record Mac architecture/macOS or Pi model/OS |
| Logging behavior | Timestamped CSV is proposed | Choose interval, duration, units, averaging/range policy, and output fields |
| Measurement setup | Manuals and [saved serial-specific calibration records](EQUIPMENT.md#individual-calibration-records) govern the procedure | Record frequency, signal path, applicable correction factors, and zero/calibration procedure before quantitative bench work |

### Resume when the adapter arrives

1. Record the actual adapter model/firmware, Mac architecture and macOS version, or Pi model and OS. Confirm USB cabling and the meter's configured GPIB address.
2. Follow the adapter's platform tutorial, install and record the candidate software versions, and establish basic communication with the provisional PyVISA-py USB backend. Confirm the 437B's command syntax, output format, termination, and trigger/read behavior from its operating manual before writing the logger.
3. Verify a software reading against the front-panel display and exercise a reversible remote setting. Confirm units, status/error handling, and return to local operation. Do not assume calibration or zeroing should run automatically; derive any such procedure from the manuals and the actual bench setup.
4. Choose the host, logging interval, duration, and CSV fields. Account for meter averaging, range changes, and settling; no sustained sampling rate has been established.
5. Implement and validate the Python logger on the selected host, including timestamps, explicit units, timeouts, invalid readings, and clean shutdown. Test required triggering/status operations, recovery after a timeout, and a sustained logging run before accepting the backend. For Pi logging, verify Mac access and file retrieval. Validate each additional host before claiming support. Record actual bench results and any adapter-specific limitations here.


## Related records

See [open work](OPEN-WORK.md), [equipment references](EQUIPMENT.md), and the [hardware validation plan](VALIDATION.md).
