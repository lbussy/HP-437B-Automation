# GPIB operation reference

Reviewed November 11, 2026. Table 3-2 declares twelve message classes: Data, Trigger, Clear, Remote, Local, Local Lockout, Clear Lockout/Set Local, Pass/Take Control (excluded), Require Service, Status Byte, Status Bit, and Abort. This reference expands them into20 operational entries, including addressing, EOI, transfer direction, poll lifecycle, and unaddressing. Numeric IDs are stable. One entry is an explicit instrument exclusion.

The instrument declares SH1, AH1, T5, TE0, L3, LE0, SR1, RL1, PP1, DC1, DT1, C0 in [Table 3-2, printed 3-25–27/PDF 55–57](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=55). Adapter transport claims and backend implementation are separate evidence layers; see the profiles below.

## Transport evidence profiles

Sources inspected November 11, 2026:

- A: [USBGpib V2 manual, revision June 9, 2026](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/Tutorials/UsbGpibV2_manual.md), “Technical specifications,” “Using the adapter,” and VISA FAQ. Claims normal USBTMC support for read/write, device clear, trigger, status byte, and service requests, dedicated controller role, and limitations in PyVISA-py. [Pinned project README](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md), “Read termination method,” documents EOI default and configurable CR/LF handling.
- B: [PyVISA-py 0.8.1 release](https://github.com/pyvisa/pyvisa-py/releases/tag/0.8.1), published September 4, 2025, latest published release reported by GitHub at inspection. [usb.py](https://github.com/pyvisa/pyvisa-py/blob/0.8.1/pyvisa_py/usb.py): USBSession.read/write and USBInstrSession enumeration. [protocols/usbtmc.py](https://github.com/pyvisa/pyvisa-py/blob/0.8.1/pyvisa_py/protocols/usbtmc.py): USBTMC initialization, EOM bulk transfer, automatic REN enable, timeout abort. [sessions.py](https://github.com/pyvisa/pyvisa-py/blob/0.8.1/pyvisa_py/sessions.py): default unsupported clear/read_stb/gpib_control_ren/gpib_command/IFC; assert_trigger raises NotImplementedError. USBSession/USBInstrSession in this release do not override those methods.
- D: [development changelog](https://github.com/pyvisa/pyvisa-py/blob/main/CHANGES) lists added USBTMC read_stb/assert_trigger/gpib_control_ren under0.9.0 unreleased at inspection. Recheck release status during Phase 2. Development functionality is a research lead, not accepted released support.

| Profile | Adapter evidence | Backend0.8.1 evidence | Phase 2 implication |
| --- | --- | --- | --- |
| T1 | A: documented read/write claim | B: source-inspected USB INSTR reads/writes and discovery | Candidate for ASCII commands and raw binary; qualification pending |
| T2 | A: dedicated one-instrument controller/discovery | B: USB resource discovery; explicit GPIB addressing not exposed by USB resource name | Record actual address/discovery; adapter-specific control uncertain |
| T3 | A: EOI/termination documented | B: EOM bulk transfer implemented; write() reads send_end attribute but transport uses EOM on final chunk, read requests use no device termchar in BulkInMessage | Validate actual EOI and binary framing; host termination alone differs from device termination |
| T4 | A: remote control standard claim | B: initialization invokes REN_CONTROL when capabilities advertise it | Automatic REN is source-inspected; explicit user REN control is T5 |
| T5 | A: broad USB488 compatibility claim; explicit mode details require checking | B: explicit gpib_control_ren inherits unsupported operation; initialization REN assertion is the limited exception | Local restoration/lockout need another released backend or later verified backend support |
| T6 | A: device clear claim | B: USB clear inherits unsupported operation | Plan a backend decision for reliable device-clear recovery |
| T7 | A: trigger/status byte claims | B: USB assert_trigger lacks implementation; read_stb inherits unsupported operation | ASCII TR1/TR2 and *STB? can use T1, but have different bus semantics; query polling during an unfinished trigger or calibration can abort it |
| T8 | A: explicit raw addressing, universal clear, IFC, and parallel-poll exposure uncertain | B: general raw bus/IFC methods unsupported in USB session | Record as unresolved transport/API coverage; parallel polling may require another controller |
| T9 | A: service-request/interrupt claim | B: interrupt endpoint discovered, but USB SRQ event delivery not established by focused inspection | Event API and end-to-end SRQ remain uncertain; do not equate polling to events |
| T10 | Firmware source queues GO_TO_LOCAL and advertises USB488 bit 1 | Project-local extension reuses the pinned session’s PyUSB handle; native VISA bus methods unchanged | [Implementation, software tests, and physical cases](../validation/AUTOMATIC-LOCAL.md); conditional G008 only |
| EX | Meter C0 exclusion | Not applicable | Model as documented instrument exclusion |

These source findings are bounded to normal firmware and released backend 0.8.1; installed versions remain a future environment choice. A declared enum/request constant alone does not establish an exposed backend method. Byte-command transport support also does not prove instrument-level command execution.

## Operations

### G001

Addressing / handshake — `ATN, device talk/listen address; SH1/AH1, T5/L3, TE0/LE0`.

- Roles, prerequisites, response, and effects: ATN true and IFC false selects command interpretation; address enables TLK/LSN. Address set locally0–30; default13; 40 listen-only and50 talk-only are special modes, not normal primary addresses. No extended addressing declared. Adapter handles electrical handshake.
- Proposed API: open_resource USB…INSTR plus adapter discovery/configuration; GPIB-address API is not automatically applicable to a USB resource.
- Transport evidence: T2 (profiles above).
- Future qualification: Confirm actual address, adapter discovery and TLK/LSN; avoid assuming controller select code713 is a VISA address.
- Source: [00437-90047, §§3-17–18; valid addresses3-99/PDF 129, printed 3-29/PDF 59](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=59).
- Open issue: A09.

### G002

Receive data — `Meter addressed to listen, ATN false, REN true`.

- Roles, prerequisites, response, and effects: Accept program data and binary restores. Listen until its talk address, IFC, or universal unlisten. Command execution and measurement completion are separate.
- Proposed API: write()/write_raw(); viWrite
- Transport evidence: T1 (profiles above).
- Future qualification: Apply reversible setting, inspect state, preserve binary framing.
- Source: [00437-90047, §§3-19–20, printed 3-30/PDF 60](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=60).
- Open issue: —.

### G003

Send data / ordinary measurement read — `Meter addressed to talk, ATN false`.

- Roles, prerequisites, response, and effects: Send current selected output; default is exponential measurement. Reading alone does not guarantee a fresh trigger. Send CRLF with EOI, except binary/legacy formats.
- Proposed API: read()/read_raw(); viRead; query() combines write plus read where appropriate.
- Transport evidence: T1 (profiles above).
- Future qualification: Compare raw ordinary read to display; distinguish TR0 held result and TR3 free-run.
- Source: [00437-90047, §3-21, printed 3-31/PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### G004

End of message — `EOI on last byte; ASCII CR LF versus binary framing`.

- Roles, prerequisites, response, and effects: Use final EOI to delimit complete output. Binary learn data contains arbitrary CR/LF bytes, so count60 and preserve EOI semantics.
- Proposed API: read_raw(), read_bytes(), write_raw(); read_termination/write_termination and send_end require transport-specific validation.
- Transport evidence: T3 (profiles above).
- Future qualification: Verify ASCII CRLF/EOI and exact60-byte binary handling; test adapter termination configuration.
- Source: [00437-90047, §3-21; learn3-32/PDF 62, printed 3-31/PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: A02.

### G005

Unlisten — `UNL or own talk address`.

- Roles, prerequisites, response, and effects: Ends meter listening; IFC also unaddresses. Universal command affects bus participants.
- Proposed API: Adapter-managed addressing; gpib_command() requires a supported GPIB resource path.
- Transport evidence: T8 (profiles above).
- Future qualification: Observe LSN/next transfer; establish whether adapter exposes explicit command.
- Source: [00437-90047, §3-20, printed 3-30/PDF 60](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=60).
- Open issue: —.

### G006

Untalk — `UNT, another talk address, or own listen address`.

- Roles, prerequisites, response, and effects: Ends meter talking; IFC also unaddresses.
- Proposed API: Adapter-managed addressing; gpib_command() on appropriate resource.
- Transport evidence: T8 (profiles above).
- Future qualification: Observe TLK and next transfer; verify complete response first.
- Source: [00437-90047, §3-21, printed 3-31/PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### G007

Remote enable — `REN asserted then meter listen address; RL1 interface capability`.

- Roles, prerequisites, response, and effects: First addressed listen while REN true enters remote. Measurement settings preserved; front-panel keys except LOCAL disabled.
- Proposed API: USBTMC initialization may assert REN automatically; explicit control_ren()/viGpibControlREN is a separate capability.
- Transport evidence: T4 (profiles above).
- Future qualification: Open/write and observe RMT; record capability flags and automatic behavior.
- Source: [00437-90047, §3-15; §3-24 PDF 65, printed 3-28/PDF 58](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=58).
- Open issue: A09.

### G008

Go to local — `GTL addressed to meter`.

- Roles, prerequisites, response, and effects: Returns front-panel control without clearing remembered lockout; RMT off, configuration preserved. Triggered operation returns to normal free-run according to Triggering.
- Implemented API: `Instrument.bus("G008")` and automatic healthy `Instrument.close()`, through negotiated profile `xyphro-usb488-gtl-v1`; see [evidence and physical cases](../validation/AUTOMATIC-LOCAL.md). Native VISA control_ren remains unavailable.
- Transport evidence: T10 (project-local negotiated extension), with native T5 limitations (profiles above).
- Qualification: [Mac ID and logger normal-close cases](../validation/AUTOMATIC-LOCAL.md) passed, including owner-observed local controls without PRESET/LOCAL. Lockout behavior, other hosts, and replacement acceptance remain untested.
- Source: [00437-90047, §3-25; Triggering3-103/PDF 133, printed 3-35/PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: A09.

### G009

Local lockout — `LLO`.

- Roles, prerequisites, response, and effects: Disables LOCAL in remote; if issued while local/REN true, next listen address enters locked remote.
- Proposed API: control_ren() lockout mode / USB488 LOCAL_LOCKOUT via supported backend.
- Transport evidence: T5 (profiles above).
- Future qualification: Verify LOCAL lockout only with a tested software restoration route.
- Source: [00437-90047, §3-26, printed 3-36/PDF 66](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=66).
- Open issue: A09.

### G010

Clear lockout / set local — `REN deasserted`.

- Roles, prerequisites, response, and effects: Clears local lockout and returns full front-panel control. Distinct from GTL.
- Proposed API: control_ren(deassert) / USB488 REN_CONTROL via supported backend.
- Transport evidence: T5 (profiles above).
- Future qualification: Verify clear lockout, local controls, and next remote transition.
- Source: [00437-90047, §3-27, printed 3-36/PDF 66](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=66).
- Open issue: A09.

### G011

Selected device clear — `SDC to addressed listener; DC1`.

- Roles, prerequisites, response, and effects: Abort pending HP-IB input/output. This is transport clear, distinct from CS/*CLS status clear and PR.
- Proposed API: clear()/viClear (USBTMC clear translation requires adapter/backend support).
- Transport evidence: T6 (profiles above).
- Future qualification: Exercise pending I/O then SDC and successful next transfer; record preserved settings.
- Source: [00437-90047, §3-22, printed 3-35/PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: —.

### G012

Universal device clear — `DCL addressed or unaddressed; DC1`.

- Roles, prerequisites, response, and effects: Abort pending input/output regardless of meter address. Universal bus scope differs from SDC.
- Proposed API: gpib_command(DCL) on supported controller resource; USB clear mapping alone does not prove DCL exposure.
- Transport evidence: T8 (profiles above).
- Future qualification: Verify unaddressed behavior and distinguish clear scope.
- Source: [00437-90047, §3-22, printed 3-35/PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: —.

### G013

Group execute trigger — `GET to remote addressed listener; DT1`.

- Roles, prerequisites, response, and effects: Apply GT0 ignore, GT1 immediate, or default GT2 delayed behavior. Pending trigger may be aborted/replaced. This bus command differs from ASCII TR1/TR2.
- Proposed API: assert_trigger()/viAssertTrigger with supported USB488 trigger translation.
- Transport evidence: T7 (profiles above).
- Future qualification: Test each GT policy and compare bus GET with ASCII trigger commands.
- Source: [00437-90047, §3-23 Table 3-4; Triggering3-104/PDF 134, printed 3-35/PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: A09.

### G014

Require service — `SRQ assertion; SR1`.

- Roles, prerequisites, response, and effects: Local or remote, meter asserts SRQ for enabled source events. Mask gates RQS; serial poll/CS/*CLS can clear request. Event, latch, and source-condition behavior must be distinguished.
- Proposed API: enable_event()/wait_on_event() for service_request; status polling via *STB? is a different strategy.
- Transport evidence: T9 (profiles above).
- Future qualification: Controlled source event; verify request notification, source decode, clearing, and masked behavior.
- Source: [00437-90047, §3-29 and Fig 3-6/PDF 67, printed 3-36/PDF 66](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=66).
- Open issue: A09.

### G015

Serial poll enable / status byte — `SPE then meter talk address`.

- Roles, prerequisites, response, and effects: Send one binary Status Byte. While poll enabled, new events buffer; poll completion and unaddressing clear sent status under described conditions. *STB? ASCII query preserves status instead.
- Proposed API: read_stb()/viReadSTB; USB488 READ_STATUS_BYTE adapter translation.
- Transport evidence: T7 (profiles above).
- Future qualification: Compare one-byte poll to *STB? and verify latch/buffer behavior.
- Source: [00437-90047, §3-30, printed 3-38/PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68).
- Open issue: A06.

The subsequent [serial-poll investigation](../validation/SERIAL-POLL-INVESTIGATION.md) provides a fake-tested one-shot USB488 prototype only. Native normal-backend support remains absent; firmware can hide an internal GPIB timeout and merge cached SRQ bits, so a valid adapter reply is not independent proof of a fresh successful poll.

The [single quiet-state wspr5 USB488 diagnostic](../validation/PI-DIAGNOSTICS-SERIAL-POLL-20261114.md) completed matching status-zero control/interrupt frames and following ordinary communication, with separate owner final confirmation. This is scoped USB exchange/followup evidence, not independent proof of fresh successful GPIB polling or status lifecycle; G015 normal support remains guarded.

### G016

Serial poll disable — `SPD / unaddress talk / IFC`.

- Roles, prerequisites, response, and effects: End serial polling and clear sent Status Byte; buffered later events remain available for next poll.
- Proposed API: Normally internal to read_stb(); explicit SPD needs supported bus-controller path.
- Transport evidence: T8 (profiles above).
- Future qualification: Verify second event survives completion of first poll.
- Source: [00437-90047, §3-30, printed 3-38/PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68).
- Open issue: —.

### G017

Parallel poll configure / enable — `PPC + PPE; PP1`.

- Roles, prerequisites, response, and effects: Controller assigns data line and logic sense; meter asserts assigned status bit when it is requiring service, without needing talk address.
- Proposed API: Parallel-poll controller operations; VISA/PyVISA mapping remains an API-design question.
- Transport evidence: T8 (profiles above).
- Future qualification: Configure line/sense and verify service/nonservice response with suitable controller.
- Source: [00437-90047, §3-32; Table 3-2/PDF 57, printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69).
- Open issue: A09.

### G018

Parallel poll disable / unconfigure — `PPD / PPU`.

- Roles, prerequisites, response, and effects: Table 3-2 lists PPD; §3-32 specifies PPU clears assigned line. Power-on leaves line unassigned. Detailed PPD granularity is unresolved.
- Proposed API: Supported controller-specific poll API or raw bus commands; mapping uncertain.
- Transport evidence: T8 (profiles above).
- Future qualification: Verify PPD versus PPU scope and no response after unconfigure.
- Source: [00437-90047, §3-32; Table 3-2/PDF 57, printed 3-40/PDF 70](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=70).
- Open issue: A09.

### G019

Interface clear / abort — `IFC`.

- Roles, prerequisites, response, and effects: Meter becomes unaddressed, stops talking/listening; affects bus addressing, distinct from device clear.
- Proposed API: send_ifc()/viGpibSendIFC on controller resource; USB abort bulk-in is not evidence of IFC.
- Transport evidence: T8 (profiles above).
- Future qualification: Observe TLK/LSN cleared; readdress and recover valid transfer.
- Source: [00437-90047, §3-33, printed 3-40/PDF 70](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=70).
- Open issue: —.

### G020

Pass/take control exclusion — `TCT / controller capability C0`.

- Roles, prerequisites, response, and effects: Meter cannot act as controller and does not respond to pass-control message. Inventory exclusion, not an implementation goal for the meter.
- Proposed API: gpib_pass_control() excluded for this instrument.
- Transport evidence: EX (profiles above).
- Future qualification: Confirm documented C0 exclusion in capability model; hardware test unnecessary.
- Source: [00437-90047, §3-28; Table 3-2/PDF 56, printed 3-36/PDF 66](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=66).
- Open issue: —.
