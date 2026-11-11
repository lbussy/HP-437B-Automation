# HP 437B command reference

Inventory reviewed November 11, 2026. Entries establish documented command occurrences and semantics to the extent specified by the supplied manuals. Open source conflicts are tracked in [ambiguities](AMBIGUITIES.md). Use the [coverage matrix](COVERAGE.md) for implementation and qualification status.

## Source and counting convention

Primary source: Operating Manual 00437-90047, January 1997. Table 3-5, printed 3-41–42/PDF 71–72, is the enumeration baseline; detailed remote-operation sections and examples add `LP2`, `*IDN?`, and table readback workflows. Explicit aliases receive separate IDs. The summary's `CT0–CT9`, `ET0–ET9`, `RF0–RF9`, and `SN0–SN9` expand to ten variants each. Numeric argument domains such as RE1–3 and RM0–5 stay parameters of one command. Frequency/percent terminators and binary prefixes are counted as documented syntax capabilities. “Family” means the functional grouping used in these entries; it is not a manufacturer count of parser opcodes. Measurement read without a command is counted in the GPIB reference.

## Shared input and output rules

All entries inherit these rules unless their entry specifies a different format or flags an ambiguity. Source: [§§3-19–21, printed 3-30–32/PDF 60–62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=60).

- Program strings use ASCII command codes; alphabetic command codes are case-insensitive, while zero and letter O are distinct. Use uppercase command codes and labels in generated traffic. Fixed, floating-point, and exponential numeric input are documented.
- Remote writes require REN asserted and the meter addressed to listen. Multiple commands may share a program string (manual example `PROC1LGCL100EN`). Respect message boundaries, and keep triggers last. Spaces appear in programming examples; arbitrary separator characters are not established.
- Numeric measurement entries use EN. Frequencies terminate with HZ/KZ/MZ/GZ. CL/KB/DY accept EN/%/PCT. Sensor-table entry follows its own paired grammar. Binary prefixes and summary-only IEEE-style setters need their individually documented framing.
- A write command completes without a dedicated acknowledgement unless it selects output or initiates a measurement. A response is transferred when the controller addresses the meter to talk. Output selection and response consumption are separate operations; follow-up output-mode persistence remains a qualification question.
- Ordinary measurement output is a signed five-digit mantissa in exponential notation, `±D.DDDDE±NN`, followed by CR LF and EOI on the final byte. Units follow configured LG/LN and REL state. Error sentinel `9.00XXE+40` carries error code XX, rather than a valid power result. Preserve negative/noise-floor results according to configured units.
- Exception formats include SM, identification, mask/status/error queries, OD, and learn snapshots. Query summary §3-34 gives three ASCII digits plus CR LF/EOI for *SRE?, *STB?, *ESR?, *ESE?, ERR?. Retain raw responses while resolving specific conflicts.
- Completion is operation-specific. Successful host write/transfer alone establishes neither settled power nor completed calibration. Changes to mode/range/filter can flush accumulated filter data. Use the trigger/zero/calibration completion rules below.

## Shared state and persistence

[§3-18, printed 3-29/PDF 59](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=59) sets turn-on interface state to local/unaddressed, cleared service mask/status, TR3, GT2, unassigned parallel-poll line, ESR128, and ESE0. Local/remote transitions preserve settings, with triggered operation returning to free-run on local operation as described in Triggering.

PRESET is defined by C entries for PR and [printed 3-73–74/PDF 103–104](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=103). ST/RC cover front-panel configurations, with RC0 at power-up. Zero data is retained through power-off separately from those registers. Sensor tables are RAM-backed; tables0/1 have ROM defaults, and error57 recovery can replace stored settings. For device clear, the manual guarantees aborting pending I/O; preservation beyond that guarantee is a qualification question. Persistence not expressly established for a command is uncertain, rather than inferred from its name.

## Status and error schemas

[Fig 3-5/Table 3-3, printed 3-33–34/PDF 63–64](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63) defines SM as `AAaaBBCCccDDddEFGHIJKLMNOP` (26 characters), CR LF/EOI:

| Field | Meaning |
| --- | --- |
| AA / aa | Measurement / entry error codes, TableA-1 |
| BB | Operating mode00 normal,06 zeroing,08 calibration |
| CC | Manual range01–05; auto range11–15 |
| cc / dd | Reserved, printed 0 fields |
| DD | Manual filter00–09 maps to1–512; auto10–19 maps to1–512 |
| E / F | E:0 linear,1 log; F: literal A |
| G / H | Reference output / REL:0 off,1 on |
| I / J | Trigger0 free-run,1 standby; GET policy0/1/2 |
| K / L | Limits checking0 off,1 on; result0 in,1 over,2 under |
| M / N / O | M reserved0; N offset enable; O duty enable |
| P | Units0 W,1 dBm,2 percent,3 dB |

SM updates after a measurement. Reserved-field widths require raw-frame validation; retain all26 characters rather than stripping zeros.

[Fig 3-6 and §§3-29–31, printed 3-37–39/PDF 67–69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=67): Status Byte weights1=data-ready,2=cal/zero complete,4=entry error,8=measurement error,16=limit violation,32=enabled ESR event,64=RQS,128=unused. Service mask gates RQS, not the existence of source bits. *STB? reads without clearing; serial poll has its own latched/buffered clearing sequence. CS clears Status Byte/SRQ; *CLS names all status registers. ESR uses128 power-on,32 command error,16 execution error,8 device-dependent error; ESE gates ESR contribution to bit5. Exact read-clear and mask-reset interactions are A06.

[AppendixA, printedA-1–4/PDF 151–154](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=151): measurement errors1–49, entry errors50–59/80–99, service errors60–79. Documented examples:1 cannot zero,5 calibration error,11 overload,15 please zero,17 up-range,21 over limit,23 under limit,31 no sensor,33 dual sensor input;50 KB,51 OS,52 RM,54 RC,55 ST,56 CL,57 RAM recall failure;80 empty table,81 DY,82 FR,85 RE,86 RF,87 SE,88 label,90 missing prefix,91 invalid code,92 ESE,93 service mask. See TableA-1 for recovery conditions. The latest SM error need not represent every event: latch behavior depends on mask/SRQ and whether error sentinel data was transferred. Remove cause and read SM according to AppendixA; preserve evidence before clearing.

## Command entries

Entry types: W=write/action, Q=output selection/query, P=contextual syntax/entry operation, B=binary transfer. Each variant has a separate ID. Shared source rules above apply to every entry.

### C001

`CL` — Calibration; type W.

- Syntax: `CL<ref_cf>EN`.
- Parameters and framing: 50.0–120.0 percent; EN, %, or PCT terminates. CLEN reuses the last value.
- Prerequisites and effects: Calibrate gain to the reference source; reference oscillator enabled during calibration, then restored. Connect the appropriate sensor/reference path and zero first; use actual sensor REF CF. OFFSET, REL, and duty correction are ignored; calibration autoranges and restores range.
- State, persistence, and completion: PR selects table REF CF but preserves calibrated gain. Entry value is retained if aborted; an incoming command aborts calibration. Internal gain is separate from stored front-panel configurations. The manual calibration example uses serial polling for completion (bit1) and error (bit3), with a10-second example timeout. ASCII status queries are incoming program commands and can abort calibration; use a validated bus-status route.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Prepared reference path; monitor completion/error, then compare to the known reference.
- Source: [00437-90047, CAL remote procedure; see also 3-46, 3-48–50, printed 3-47, PDF 77](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=77).
- Open issue: A04.

### C002

`*CLS` — Status clear; type W.

- Syntax: `*CLS`.
- Parameters and framing: None.
- Prerequisites and effects: Clear all status registers and pending service request as documented; distinguish from device clear and preset.
- State, persistence, and completion: Scope beyond the named status registers and enable-mask persistence require confirmation; turn-on masks are zero.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Create controlled status conditions and verify clearing while recording masks.
- Source: [00437-90047, Table 3-5; see 3-36, 3-38, printed 3-42, PDF 72](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=72).
- Open issue: A06.

### C003

`CS` — Status clear; type W.

- Syntax: `CS`.
- Parameters and framing: None.
- Prerequisites and effects: Clear Status Byte and pending SRQ before a new trigger, limit, zero, or calibration completion check.
- State, persistence, and completion: Clears status rather than changing measurement configuration; later conditions can set bits again.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Compare *STB? before/after controlled event; verify later events remain observable.
- Source: [00437-90047, §3-30; see 3-69, 3-108, printed 3-38, PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68).
- Open issue: —.

### C004

`CT0` — Sensor table clear; type W.

- Syntax: `CT0`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C005

`CT1` — Sensor table clear; type W.

- Syntax: `CT1`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C006

`CT2` — Sensor table clear; type W.

- Syntax: `CT2`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C007

`CT3` — Sensor table clear; type W.

- Syntax: `CT3`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C008

`CT4` — Sensor table clear; type W.

- Syntax: `CT4`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C009

`CT5` — Sensor table clear; type W.

- Syntax: `CT5`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C010

`CT6` — Sensor table clear; type W.

- Syntax: `CT6`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C011

`CT7` — Sensor table clear; type W.

- Syntax: `CT7`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C012

`CT8` — Sensor table clear; type W.

- Syntax: `CT8`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C013

`CT9` — Sensor table clear; type W.

- Syntax: `CT9`.
- Parameters and framing: The trailing digit selects table 0–9; detailed procedure uses CTn without EN. Summary footnote differs.
- Prerequisites and effects: Erase table data before loading new pairs. Protect a backup before modifying stored factors. Local clearing retains REF CF; verify remote equivalent.
- State, persistence, and completion: PR preserves tables; edited data persists in RAM. Factory tables 0/1 have ROM defaults; cleared 2–9 factory contents are not recoverable directly.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify intended table only is cleared and inspect REF CF.
- Source: [00437-90047, Sensor Data remote procedure; see 3-85, 3-92, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C014

`DA` — Display; type W.

- Syntax: `DA`.
- Parameters and framing: None.
- Prerequisites and effects: Illuminate display segments for visual check; remote-only display selection.
- State, persistence, and completion: DE, another display function, PR, or local operation restores ordinary display.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Observe all segments and restore DE.
- Source: [00437-90047, Display remote procedure, printed 3-53, PDF 83](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=83).
- Open issue: —.

### C015

`DC0` — Duty correction; type W.

- Syntax: `DC0`.
- Parameters and framing: 0 disables; 1 enables using last entered duty percentage.
- Prerequisites and effects: Apply or remove average-to-rectangular-pulse power correction; correct pulse shape and duty are prerequisites.
- State, persistence, and completion: PR sets off and duty value 1.000%; value/status can be stored and recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known average power; verify correction and DTY CY indication, then restore.
- Source: [00437-90047, DUTY CYCLE remote procedure; see 3-56, printed 3-55, PDF 85](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=85).
- Open issue: —.

### C016

`DC1` — Duty correction; type W.

- Syntax: `DC1`.
- Parameters and framing: 0 disables; 1 enables using last entered duty percentage.
- Prerequisites and effects: Apply or remove average-to-rectangular-pulse power correction; correct pulse shape and duty are prerequisites.
- State, persistence, and completion: PR sets off and duty value 1.000%; value/status can be stored and recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known average power; verify correction and DTY CY indication, then restore.
- Source: [00437-90047, DUTY CYCLE remote procedure; see 3-56, printed 3-55, PDF 85](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=85).
- Open issue: —.

### C017

`DD` — Display; type W.

- Syntax: `DD`.
- Parameters and framing: DD: firmware 1.5 or later according to summary; DF listed as disable alias.
- Prerequisites and effects: Blank display while bus readings remain valid; remote-only.
- State, persistence, and completion: Another display function, PR, or local operation restores display.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Compare bus reading while blank, then restore DE.
- Source: [00437-90047, Display; aliases in Table 3-5, printed 3-41/PDF 71, printed 3-53, PDF 83](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=83).
- Open issue: A07.

### C018

`DF` — Display; type W.

- Syntax: `DF`.
- Parameters and framing: DD: firmware 1.5 or later according to summary; DF listed as disable alias.
- Prerequisites and effects: Blank display while bus readings remain valid; remote-only.
- State, persistence, and completion: Another display function, PR, or local operation restores display.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Compare bus reading while blank, then restore DE.
- Source: [00437-90047, Display; aliases in Table 3-5, printed 3-41/PDF 71, printed 3-53, PDF 83](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=83).
- Open issue: A07.

### C019

`DE` — Display; type W.

- Syntax: `DE`.
- Parameters and framing: None.
- Prerequisites and effects: Enable normal display of results and operating state.
- State, persistence, and completion: Turn-on, PR, and local mode use enabled display.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Restore display after DA/DD/DU and compare front panel.
- Source: [00437-90047, Display remote procedure, printed 3-53, PDF 83](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=83).
- Open issue: —.

### C020

`DN` — Cursor; type W.

- Syntax: `DN`.
- Parameters and framing: DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive.
- Prerequisites and effects: Emulate arrow keys during numeric/SPECIAL entry. RE, RM, and SE use UP/DN and ignore LT/RT.
- State, persistence, and completion: Entry state changes until EN commits or EX cancels; shifted key functions are described locally, without a separate remote SHIFT code.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Use a reversible entry; compare cursor/value movement and cancel EX.
- Source: [00437-90047, Arrows program codes, printed 3-44, PDF 74](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=74).
- Open issue: —.

### C021

`LT` — Cursor; type W.

- Syntax: `LT`.
- Parameters and framing: DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive.
- Prerequisites and effects: Emulate arrow keys during numeric/SPECIAL entry. RE, RM, and SE use UP/DN and ignore LT/RT.
- State, persistence, and completion: Entry state changes until EN commits or EX cancels; shifted key functions are described locally, without a separate remote SHIFT code.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Use a reversible entry; compare cursor/value movement and cancel EX.
- Source: [00437-90047, Arrows program codes, printed 3-44, PDF 74](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=74).
- Open issue: —.

### C022

`RT` — Cursor; type W.

- Syntax: `RT`.
- Parameters and framing: DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive.
- Prerequisites and effects: Emulate arrow keys during numeric/SPECIAL entry. RE, RM, and SE use UP/DN and ignore LT/RT.
- State, persistence, and completion: Entry state changes until EN commits or EX cancels; shifted key functions are described locally, without a separate remote SHIFT code.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Use a reversible entry; compare cursor/value movement and cancel EX.
- Source: [00437-90047, Arrows program codes, printed 3-44, PDF 74](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=74).
- Open issue: —.

### C023

`UP` — Cursor; type W.

- Syntax: `UP`.
- Parameters and framing: DN/UP change selected digit/value; LT/RT move selected digit. Context-sensitive.
- Prerequisites and effects: Emulate arrow keys during numeric/SPECIAL entry. RE, RM, and SE use UP/DN and ignore LT/RT.
- State, persistence, and completion: Entry state changes until EN commits or EX cancels; shifted key functions are described locally, without a separate remote SHIFT code.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Use a reversible entry; compare cursor/value movement and cancel EX.
- Source: [00437-90047, Arrows program codes, printed 3-44, PDF 74](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=74).
- Open issue: —.

### C024

`DU` — Display; type W.

- Syntax: `DU<message>`.
- Parameters and framing: Up to 12 characters from 0–9, A–Z, and spaces; message-boundary parsing needs verification.
- Prerequisites and effects: Display user text in remote mode.
- State, persistence, and completion: Another display function, PR, or local operation restores display.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Send a bounded message, observe display, restore DE.
- Source: [00437-90047, Display user message, printed 3-53, PDF 83](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=83).
- Open issue: A07.

### C025

`DY` — Duty correction; type W.

- Syntax: `DY<percent>EN`.
- Parameters and framing: 0.001–99.999%; EN, %, or PCT terminates.
- Prerequisites and effects: Enter duty percentage and enable mathematical pulse-power correction.
- State, persistence, and completion: PR sets 1.000%, off; retained for DC1 and configuration store/recall.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known duty/average input; confirm corrected reading and restore.
- Source: [00437-90047, DUTY CYCLE; see 3-56, printed 3-55, PDF 85](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=85).
- Open issue: —.

### C026

`EN` — Entry; type P.

- Syntax: `EN`.
- Parameters and framing: Commits the active numeric entry or advances a SPECIAL/table entry; bare EN reuses the current value where described.
- Prerequisites and effects: Terminate/commit data. In ET mode, commits a frequency/factor pair and advances display.
- State, persistence, and completion: State depends on active function. EX cancels uncommitted entry.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Reversible numeric edit and EX cancellation; test table traversal on a backed-up table.
- Source: [00437-90047, ENTER remote procedure; see 3-87, 3-91, printed 3-58, PDF 88](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=88).
- Open issue: —.

### C027

`ERR?` — Error query; type Q.

- Syntax: `ERR?`.
- Parameters and framing: None in summary.
- Prerequisites and effects: Request device error information; detailed semantics are limited to the summary/output rules.
- State, persistence, and completion: Consumption/clearing behavior remains unspecified.
- Response: XXX CR LF with EOI; common query summary gives ASCII 000–255. Exact error-selection/queue behavior is unresolved.
- Future qualification: Controlled recoverable entry error; compare ERR?, SM, and *STB?; record side effects.
- Source: [00437-90047, §3-34 output formats; Table 3-5 PDF 71, printed 3-40, PDF 70](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=70).
- Open issue: A06.

### C028

`*ESR?` — Event status; type Q.

- Syntax: `*ESR?`.
- Parameters and framing: None.
- Prerequisites and effects: Read weighted Event Status Register: power-on 128, command error 32, execution error 16, device-dependent measurement error 8; other bits reserved in the diagram.
- State, persistence, and completion: Turn-on value 128; read-clear behavior is not explicitly established in the supplied description.
- Response: ASCII register value 000–255, CR LF, EOI.
- Future qualification: Read twice after a controlled event and determine clearing without assuming generic IEEE semantics.
- Source: [00437-90047, §3-31; definitions Fig.3-7 printed 3-39/PDF 69, printed 3-38, PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68).
- Open issue: A06.

### C029

`*ESE` — Event enable; type W.

- Syntax: `*ESE<mask>`.
- Parameters and framing: ASCII weighted 8-bit mask; usable event bits 128,32,16,8. No EN is specified for this setter in summary.
- Prerequisites and effects: Enable corresponding ESR conditions to set Status Byte bit 5.
- State, persistence, and completion: Turn-on mask 0; error 92 reports invalid entry. Exact framing and reset interactions require confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Set/read back an isolated mask; provoke a controlled event; restore mask.
- Source: [00437-90047, §3-31 and Fig.3-7; error 92 in A-4/PDF 154, printed 3-39, PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69).
- Open issue: A06.

### C030

`*ESE?` — Event enable; type Q.

- Syntax: `*ESE?`.
- Parameters and framing: None.
- Prerequisites and effects: Read Event Status Enable mask.
- State, persistence, and completion: Read operation; clearing side effects not stated.
- Response: ASCII mask 000–255, CR LF, EOI.
- Future qualification: Read back each allowed mask and record unchanged measurement settings.
- Source: [00437-90047, §3-31; output summary 3-40/PDF 70, printed 3-39, PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69).
- Open issue: —.

### C031

`ET0` — Sensor table edit; type W.

- Syntax: `ET0 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C032

`ET1` — Sensor table edit; type W.

- Syntax: `ET1 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C033

`ET2` — Sensor table edit; type W.

- Syntax: `ET2 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C034

`ET3` — Sensor table edit; type W.

- Syntax: `ET3 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C035

`ET4` — Sensor table edit; type W.

- Syntax: `ET4 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C036

`ET5` — Sensor table edit; type W.

- Syntax: `ET5 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C037

`ET6` — Sensor table edit; type W.

- Syntax: `ET6 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C038

`ET7` — Sensor table edit; type W.

- Syntax: `ET7 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C039

`ET8` — Sensor table edit; type W.

- Syntax: `ET8 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C040

`ET9` — Sensor table edit; type W.

- Syntax: `ET9 <f><unit> <cf>% EN ... EX`.
- Parameters and framing: n=0–9; 40 pairs for 0–7, 80 for 8–9. Frequencies use HZ/KZ/MZ/GZ; factors use %. Follow FR/KB domains pending confirmation of table-entry-specific limits.
- Prerequisites and effects: Enter table-edit state, then insert/replace frequency/factor pairs; EN commits each pair, EX leaves edit mode.
- State, persistence, and completion: Numeric data is directed to the table until EX. PR preserves tables; keep backup. Remote deletion semantics need confirmation.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read one pair, verify table selection and EX.
- Source: [00437-90047, Sensor Data remote procedure; capacities 3-84/PDF 114; example 3-89/PDF 119, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C041

`EX` — Exit; type W.

- Syntax: `EX`.
- Parameters and framing: None.
- Prerequisites and effects: Leave SPECIAL/table editing and return to measurement; cancel uncommitted function entry.
- State, persistence, and completion: Required to leave ET entry mode; prior committed values remain.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Open a reversible entry, alter without EN, exit, and verify prior value.
- Source: [00437-90047, EXIT; see 3-60, printed 3-59, PDF 89](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=89).
- Open issue: —.

### C042

`FA` — Filter; type W.

- Syntax: `FA`.
- Parameters and framing: None.
- Prerequisites and effects: Select automatic averaging by range/resolution; auto filter may flush on significant signal change.
- State, persistence, and completion: PR enables auto; changing resolution also enables auto filtering.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify SM filter field, change range/resolution, observe auto setting.
- Source: [00437-90047, Filter remote procedure; see 3-61–64, printed 3-63, PDF 93](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=93).
- Open issue: —.

### C043

`FH` — Filter; type W.

- Syntax: `FH`.
- Parameters and framing: None.
- Prerequisites and effects: Freeze the current automatic filter length by entering manual filter mode; already-manual setting stays unchanged.
- State, persistence, and completion: PR returns auto; selected filter is a configuration value.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Start auto, issue FH, verify SM and fixed length across range change.
- Source: [00437-90047, Filter hold comments, printed 3-64, PDF 94](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=94).
- Open issue: —.

### C044

`FM` — Filter; type W.

- Syntax: `FM<count>EN`.
- Parameters and framing: Binary progression 1,2,4,8,16,32,64,128,256,512; other entries rounded to nearest permitted count. Tie/out-of-domain handling unresolved.
- Prerequisites and effects: Select manual averaging. Longer filter increases settling; mode/range/filter changes can clear accumulated data.
- State, persistence, and completion: PR returns auto; resolution changes enable auto. Store/recall preserves filter setting.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify each legal count via SM; test rounding cautiously and measure settling.
- Source: [00437-90047, Filter remote procedure; see 3-61–64, printed 3-63, PDF 93](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=93).
- Open issue: A08.

### C045

`FR` — Frequency; type W.

- Syntax: `FR<f><unit>`.
- Parameters and framing: 0.0001–999.9999 GHz, 100 kHz resolution. Units HZ/KZ/MZ/GZ terminate frequency.
- Prerequisites and effects: Select frequency-specific calibration factor from the SE-selected sensor table; interpolate linearly between entries and clamp to endpoint factor outside table span.
- State, persistence, and completion: PR sets 50 MHz. Empty table gives error 80. Frequency is a correction lookup, not a sensor bandwidth extension.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known sensor table; verify endpoints/interpolation and actual sensor range.
- Source: [00437-90047, FREQ; see 3-66–67, printed 3-65, PDF 95](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=95).
- Open issue: A04.

### C046

`GT0` — Group-trigger policy; type W.

- Syntax: `GT0`.
- Parameters and framing: 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior.
- Prerequisites and effects: Configure response to a later bus GET; writing GTn itself is separate from issuing GET.
- State, persistence, and completion: Turn-on and PR select GT2.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Configure each policy then separately test bus GET with readback/status.
- Source: [00437-90047, §3-23 Table 3-4; PRESET 3-73, printed 3-35, PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: —.

### C047

`GT1` — Group-trigger policy; type W.

- Syntax: `GT1`.
- Parameters and framing: 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior.
- Prerequisites and effects: Configure response to a later bus GET; writing GTn itself is separate from issuing GET.
- State, persistence, and completion: Turn-on and PR select GT2.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Configure each policy then separately test bus GET with readback/status.
- Source: [00437-90047, §3-23 Table 3-4; PRESET 3-73, printed 3-35, PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: —.

### C048

`GT2` — Group-trigger policy; type W.

- Syntax: `GT2`.
- Parameters and framing: 0 ignore GET; 1 apply TR1 behavior; 2 apply TR2 behavior.
- Prerequisites and effects: Configure response to a later bus GET; writing GTn itself is separate from issuing GET.
- State, persistence, and completion: Turn-on and PR select GT2.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Configure each policy then separately test bus GET with readback/status.
- Source: [00437-90047, §3-23 Table 3-4; PRESET 3-73, printed 3-35, PDF 65](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=65).
- Open issue: —.

### C049

`GZ` — Frequency unit; type P.

- Syntax: `<f>GZ`.
- Parameters and framing: GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component.
- Prerequisites and effects: Supply frequency scale; numeric formatting accepts fixed/floating/exponential values.
- State, persistence, and completion: Applies to the active entry; ET still requires factor plus EN.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Encode one equivalent frequency in all units; compare selected correction.
- Source: [00437-90047, §3-20; FREQ 3-65/PDF 95 and Sensor Data 3-87/PDF 117, printed 3-31, PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### C050

`HZ` — Frequency unit; type P.

- Syntax: `<f>HZ`.
- Parameters and framing: GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component.
- Prerequisites and effects: Supply frequency scale; numeric formatting accepts fixed/floating/exponential values.
- State, persistence, and completion: Applies to the active entry; ET still requires factor plus EN.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Encode one equivalent frequency in all units; compare selected correction.
- Source: [00437-90047, §3-20; FREQ 3-65/PDF 95 and Sensor Data 3-87/PDF 117, printed 3-31, PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### C051

`KZ` — Frequency unit; type P.

- Syntax: `<f>KZ`.
- Parameters and framing: GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component.
- Prerequisites and effects: Supply frequency scale; numeric formatting accepts fixed/floating/exponential values.
- State, persistence, and completion: Applies to the active entry; ET still requires factor plus EN.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Encode one equivalent frequency in all units; compare selected correction.
- Source: [00437-90047, §3-20; FREQ 3-65/PDF 95 and Sensor Data 3-87/PDF 117, printed 3-31, PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### C052

`MZ` — Frequency unit; type P.

- Syntax: `<f>MZ`.
- Parameters and framing: GHz, Hz, kHz, MHz respectively; suffix terminates FR frequency or ET frequency component.
- Prerequisites and effects: Supply frequency scale; numeric formatting accepts fixed/floating/exponential values.
- State, persistence, and completion: Applies to the active entry; ET still requires factor plus EN.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Encode one equivalent frequency in all units; compare selected correction.
- Source: [00437-90047, §3-20; FREQ 3-65/PDF 95 and Sensor Data 3-87/PDF 117, printed 3-31, PDF 61](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=61).
- Open issue: —.

### C053

`ID` — Identification; type Q.

- Syntax: `ID`.
- Parameters and framing: ID and IDN? appear in Table 3-5; *IDN? appears in §3-21.
- Prerequisites and effects: Select model/firmware identification output.
- State, persistence, and completion: Output-mode persistence after read is not specified.
- Response: Detailed form: HEWLETT-PACKARD,437B,,X.X (spacing/termination to verify); empty serial field and firmware version. Preserve raw response.
- Future qualification: Read all documented spellings, compare raw bytes, firmware, and next read behavior.
- Source: [00437-90047, §3-21 Identification; Table 3-5 printed 3-41/PDF 71, printed 3-33, PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63).
- Open issue: A01.

### C054

`IDN?` — Identification; type Q.

- Syntax: `IDN?`.
- Parameters and framing: ID and IDN? appear in Table 3-5; *IDN? appears in §3-21.
- Prerequisites and effects: Select model/firmware identification output.
- State, persistence, and completion: Output-mode persistence after read is not specified.
- Response: Detailed form: HEWLETT-PACKARD,437B,,X.X (spacing/termination to verify); empty serial field and firmware version. Preserve raw response.
- Future qualification: Read all documented spellings, compare raw bytes, firmware, and next read behavior.
- Source: [00437-90047, §3-21 Identification; Table 3-5 printed 3-41/PDF 71, printed 3-33, PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63).
- Open issue: A01.

### C055

`*IDN?` — Identification; type Q.

- Syntax: `*IDN?`.
- Parameters and framing: ID and IDN? appear in Table 3-5; *IDN? appears in §3-21.
- Prerequisites and effects: Select model/firmware identification output.
- State, persistence, and completion: Output-mode persistence after read is not specified.
- Response: Detailed form: HEWLETT-PACKARD,437B,,X.X (spacing/termination to verify); empty serial field and firmware version. Preserve raw response.
- Future qualification: Read all documented spellings, compare raw bytes, firmware, and next read behavior.
- Source: [00437-90047, §3-21 Identification; Table 3-5 printed 3-41/PDF 71, printed 3-33, PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63).
- Open issue: A01.

### C056

`KB` — Calibration factor; type W.

- Syntax: `KB<cf>EN`.
- Parameters and framing: 1.0–150.0%; 0.1% resolution, remote entry rounded; EN, %, or PCT terminates.
- Prerequisites and effects: Set active measurement correction, distinct from reference CAL factor and stored sensor-table factors.
- State, persistence, and completion: PR selects factor from current table. FR can select a table-derived factor.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Apply known factor and verify readback/display; use intended sensor-specific factor.
- Source: [00437-90047, CAL FAC; see 3-52, printed 3-51, PDF 81](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=81).
- Open issue: A04.

### C057

`LG` — Units; type W.

- Syntax: `LG`.
- Parameters and framing: LG log; LN linear.
- Prerequisites and effects: Select absolute dBm/watts, or relative dB/percent with REL enabled.
- State, persistence, and completion: PR selects log dBm; configuration store/recall includes units.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify absolute and relative units alongside SM P field.
- Source: [00437-90047, Table 3-5; REL 3-78/PDF 108, printed 3-41, PDF 71](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=71).
- Open issue: —.

### C058

`LN` — Units; type W.

- Syntax: `LN`.
- Parameters and framing: LG log; LN linear.
- Prerequisites and effects: Select absolute dBm/watts, or relative dB/percent with REL enabled.
- State, persistence, and completion: PR selects log dBm; configuration store/recall includes units.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify absolute and relative units alongside SM P field.
- Source: [00437-90047, Table 3-5; REL 3-78/PDF 108, printed 3-41, PDF 71](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=71).
- Open issue: —.

### C059

`LH` — High limit; type W.

- Syntax: `LH<dBm>EN`.
- Parameters and framing: −299.999 to +299.999 dBm.
- Prerequisites and effects: Set high display-power limit; LM1 controls checking.
- State, persistence, and completion: PR sets +90.000 dBm and disables checking; limits can be stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known input and correction settings; compare threshold, error21, and status bit4.
- Source: [00437-90047, Limits remote procedure; range 3-68/PDF 98, printed 3-69, PDF 99](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=99).
- Open issue: —.

### C060

`LL` — Low limit; type W.

- Syntax: `LL<dBm>EN`.
- Parameters and framing: −299.999 to +299.999 dBm.
- Prerequisites and effects: Set low display-power limit; LM1 controls checking.
- State, persistence, and completion: PR sets −90.000 dBm and disables checking; limits can be stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known input and correction settings; compare threshold, error23, and status bit4.
- Source: [00437-90047, Limits remote procedure; range 3-68/PDF 98, printed 3-69, PDF 99](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=99).
- Open issue: —.

### C061

`LM0` — Limits enable; type W.

- Syntax: `LM0`.
- Parameters and framing: 0 disable; 1 enable with existing thresholds.
- Prerequisites and effects: Check displayed corrected value (includes offset/REL/duty), not raw input. Monitor bit4; clear stale status using CS before measurement.
- State, persistence, and completion: PR disables; local transition retains enable; limits/status can be stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Cross known high/low thresholds, verify indication and recovery.
- Source: [00437-90047, Limits; see 3-70, printed 3-69, PDF 99](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=99).
- Open issue: —.

### C062

`LM1` — Limits enable; type W.

- Syntax: `LM1`.
- Parameters and framing: 0 disable; 1 enable with existing thresholds.
- Prerequisites and effects: Check displayed corrected value (includes offset/REL/duty), not raw input. Monitor bit4; clear stale status using CS before measurement.
- State, persistence, and completion: PR disables; local transition retains enable; limits/status can be stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Cross known high/low thresholds, verify indication and recovery.
- Source: [00437-90047, Limits; see 3-70, printed 3-69, PDF 99](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=99).
- Open issue: —.

### C063

`LP` — Learn; type Q.

- Syntax: `LP`.
- Parameters and framing: LP summary; LP2 detailed invocation. Use LP2 as documented candidate while testing bare LP.
- Prerequisites and effects: Select configuration learn output for raw binary capture and later restore.
- State, persistence, and completion: Snapshot includes units, REL, oscillator, factors, offset, range/filter, sensor ID, duty, resolution, frequency, limits. Exact byte layout is undocumented.
- Response: 60 bytes: ASCII @2 followed by 58 arbitrary binary bytes, EOI on final byte; preserve uninterpreted bytes.
- Future qualification: Capture exact length without text termination; restore only a backed-up known snapshot.
- Source: [00437-90047, §3-21 Learn Mode; summary 3-40–41, printed 3-32, PDF 62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=62).
- Open issue: A02.

### C064

`LP2` — Learn; type Q.

- Syntax: `LP2`.
- Parameters and framing: LP summary; LP2 detailed invocation. Use LP2 as documented candidate while testing bare LP.
- Prerequisites and effects: Select configuration learn output for raw binary capture and later restore.
- State, persistence, and completion: Snapshot includes units, REL, oscillator, factors, offset, range/filter, sensor ID, duty, resolution, frequency, limits. Exact byte layout is undocumented.
- Response: 60 bytes: ASCII @2 followed by 58 arbitrary binary bytes, EOI on final byte; preserve uninterpreted bytes.
- Future qualification: Capture exact length without text termination; restore only a backed-up known snapshot.
- Source: [00437-90047, §3-21 Learn Mode; summary 3-40–41, printed 3-32, PDF 62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=62).
- Open issue: A02.

### C065

`OC0` — Reference output; type W.

- Syntax: `OC0`.
- Parameters and framing: 0 off; 1 on.
- Prerequisites and effects: Control 50 MHz nominal 1 mW reference at front connector, or rear REF OSC for option003. Use an appropriate connected reference path.
- State, persistence, and completion: PR off; ZE temporarily off; CL temporarily on; both restore previous state. Store/recall includes oscillator state.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Observe output with suitable load/sensor; verify restore after authorized ZE/CL.
- Source: [00437-90047, PWR REF, printed 3-75, PDF 105](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=105).
- Open issue: —.

### C066

`OC1` — Reference output; type W.

- Syntax: `OC1`.
- Parameters and framing: 0 off; 1 on.
- Prerequisites and effects: Control 50 MHz nominal 1 mW reference at front connector, or rear REF OSC for option003. Use an appropriate connected reference path.
- State, persistence, and completion: PR off; ZE temporarily off; CL temporarily on; both restore previous state. Store/recall includes oscillator state.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Observe output with suitable load/sensor; verify restore after authorized ZE/CL.
- Source: [00437-90047, PWR REF, printed 3-75, PDF 105](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=105).
- Open issue: —.

### C067

`OD` — Display output; type Q.

- Syntax: `OD`.
- Parameters and framing: None.
- Prerequisites and effects: Select ASCII display text, including table REF CF or pair currently displayed.
- State, persistence, and completion: In table-reading example: RFnOD reads REF CF; ETn then OD/EN traverses pairs, and EX exits. EN commits/advances, so preserve table data.
- Response: Display text; example allocates 14 characters. REF CF parsed positions8–12; pair frequency1–5, units6, factor9–13 (one-based). Exact framing is a qualification question.
- Future qualification: Read known REF CF and table pairs, preserve raw output, verify traversal termination.
- Source: [00437-90047, Sensor Data read-table example 3-90–92; Table 3-5 PDF 72, printed 3-91, PDF 121](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=121).
- Open issue: A03.

### C068

`OF0` — Offset enable; type W.

- Syntax: `OF0`.
- Parameters and framing: 0 disable; 1 enable using last offset.
- Prerequisites and effects: Toggle dB offset added to measured result; works in watts through conversion.
- State, persistence, and completion: PR value0/off; store/recall preserves value/status.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known signal; compare enabled/disabled reading and restore.
- Source: [00437-90047, OFFSET; see 3-72, printed 3-71, PDF 101](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=101).
- Open issue: —.

### C069

`OF1` — Offset enable; type W.

- Syntax: `OF1`.
- Parameters and framing: 0 disable; 1 enable using last offset.
- Prerequisites and effects: Toggle dB offset added to measured result; works in watts through conversion.
- State, persistence, and completion: PR value0/off; store/recall preserves value/status.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known signal; compare enabled/disabled reading and restore.
- Source: [00437-90047, OFFSET; see 3-72, printed 3-71, PDF 101](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=101).
- Open issue: —.

### C070

`OS` — Offset; type W.

- Syntax: `OS<dB>EN`.
- Parameters and framing: −99.99 to +99.99 dB, step0.01 dB.
- Prerequisites and effects: Enter/enable gain/loss correction added to displayed power.
- State, persistence, and completion: PR value0/off; store/recall preserves value/status.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: OS3.0EN is manual-supported example; verify correction then restore.
- Source: [00437-90047, OFFSET remote procedure; see 3-72, printed 3-71, PDF 101](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=101).
- Open issue: —.

### C071

`PCT` — Percent terminator; type P.

- Syntax: `<percent>PCT`.
- Parameters and framing: Alternative to EN for CL, KB, DY; table RF and factor syntax described in Sensor Data.
- Prerequisites and effects: Terminate percentage entry. ET pairs still require EN after frequency/factor.
- State, persistence, and completion: Parser-context effect only.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Equivalent percentage entries; verify %, PCT, and EN in documented contexts.
- Source: [00437-90047, CAL; Table 3-5 PDF 72 and Sensor Data 3-87/PDF 117, printed 3-47, PDF 77](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=77).
- Open issue: A03.

### C072

`%` — Percent terminator; type P.

- Syntax: `<percent>%`.
- Parameters and framing: Alternative to EN for CL, KB, DY; table RF and factor syntax described in Sensor Data.
- Prerequisites and effects: Terminate percentage entry. ET pairs still require EN after frequency/factor.
- State, persistence, and completion: Parser-context effect only.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Equivalent percentage entries; verify %, PCT, and EN in documented contexts.
- Source: [00437-90047, CAL; Table 3-5 PDF 72 and Sensor Data 3-87/PDF 117, printed 3-47, PDF 77](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=77).
- Open issue: A03.

### C073

`PR` — Preset; type W.

- Syntax: `PR`.
- Parameters and framing: None.
- Prerequisites and effects: Set known measurement state: 50MHz, RES2, duty1% off, REL0 off, offset0 off, reference off, auto range/filter, dBm, limits−90/+90 off, TR3, GT2, DE.
- State, persistence, and completion: Preserves sensor tables, storage registers, zero/cal gain; previous configuration can be recalled through RC0EN. Factors reset from selected sensor table.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Record initial state and permitted snapshot; verify fields and documented retained data.
- Source: [00437-90047, PRESET conditions; see 3-74, printed 3-73, PDF 103](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=103).
- Open issue: —.

### C074

`RA` — Auto range; type W.

- Syntax: `RA`.
- Parameters and framing: None.
- Prerequisites and effects: Enable autorange; if already auto and in bottom20% overlap, may step down one range.
- State, persistence, and completion: PR auto; manual RM/RH exits auto. A repeated RA can change range rather than being fully idempotent.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known borderline input; check range transitions and resolution.
- Source: [00437-90047, AUTO RANGE, printed 3-45, PDF 75](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=75).
- Open issue: —.

### C075

`RC` — Recall; type W.

- Syntax: `RC<n>EN`.
- Parameters and framing: Integer register0–10; error54 for invalid register.
- Prerequisites and effects: Restore stored front-panel configuration, including oscillator, limits, and correction settings.
- State, persistence, and completion: Register0 provides previous configuration; power-up recalls0. Calibration gain and zero data are separate; error57 resets configurations.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up configuration; verify all restored fields and unchanged calibration identity.
- Source: [00437-90047, RECALL; see 3-77, printed 3-76, PDF 106](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=106).
- Open issue: —.

### C076

`RE` — Resolution; type W.

- Syntax: `RE<n>EN`.
- Parameters and framing: n=1,2,3: log0.1/0.01/0.001 dB; linear1/0.1/0.01% full scale.
- Prerequisites and effects: Set display resolution; changing resolution enables auto filtering, with settling consequences.
- State, persistence, and completion: PR RES2; stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Select each resolution; check display precision and SM filter mode.
- Source: [00437-90047, RESOLN; see Filter 3-62/PDF 92, printed 3-80, PDF 110](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=110).
- Open issue: A04.

### C077

`RF0` — Table reference factor; type W.

- Syntax: `RF0<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C078

`RF1` — Table reference factor; type W.

- Syntax: `RF1<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C079

`RF2` — Table reference factor; type W.

- Syntax: `RF2<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C080

`RF3` — Table reference factor; type W.

- Syntax: `RF3<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C081

`RF4` — Table reference factor; type W.

- Syntax: `RF4<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C082

`RF5` — Table reference factor; type W.

- Syntax: `RF5<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C083

`RF6` — Table reference factor; type W.

- Syntax: `RF6<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C084

`RF7` — Table reference factor; type W.

- Syntax: `RF7<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C085

`RF8` — Table reference factor; type W.

- Syntax: `RF8<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C086

`RF9` — Table reference factor; type W.

- Syntax: `RF9<ref_cf>%`.
- Parameters and framing: Table digit0–9 immediately followed by factor50.0–120.0%; % or EN in detailed procedure. RFnOD accesses displayed value in read example.
- Prerequisites and effects: Update stored table REF CF; distinct from running CL calibration.
- State, persistence, and completion: Table data survives PR; invalid table clears to100% on INIT/power-on checksum failure. Snapshot before change.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; write/read REF CF with OD and verify other tables.
- Source: [00437-90047, Sensor Data RF; error86 A-4/PDF 154, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C087

`RH` — Range hold; type W.

- Syntax: `RH`.
- Parameters and framing: None; captures current range.
- Prerequisites and effects: Hold current range instead of autoranging.
- State, persistence, and completion: RA or RM0EN returns auto; PR auto.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Known input; hold and vary within safe sensor limits; observe range/status.
- Source: [00437-90047, SET RANGE program codes; see 3-95, printed 3-94, PDF 124](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=124).
- Open issue: —.

### C088

`RL0` — Relative; type W.

- Syntax: `RL0`.
- Parameters and framing: 0 off; 1 use current displayed value as new reference; 2 reuse previous reference.
- Prerequisites and effects: Select absolute or relative measurement; LG/LN select relative dB/percent. Reference cannot be read directly by a dedicated scalar query.
- State, persistence, and completion: PR off/reference0; store/recall includes reference/status. Snapshot learn data also contains reference.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Stable reference input; verify RL1 baseline, changed input, RL0, and RL2.
- Source: [00437-90047, REL; see 3-79, printed 3-78, PDF 108](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=108).
- Open issue: —.

### C089

`RL1` — Relative; type W.

- Syntax: `RL1`.
- Parameters and framing: 0 off; 1 use current displayed value as new reference; 2 reuse previous reference.
- Prerequisites and effects: Select absolute or relative measurement; LG/LN select relative dB/percent. Reference cannot be read directly by a dedicated scalar query.
- State, persistence, and completion: PR off/reference0; store/recall includes reference/status. Snapshot learn data also contains reference.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Stable reference input; verify RL1 baseline, changed input, RL0, and RL2.
- Source: [00437-90047, REL; see 3-79, printed 3-78, PDF 108](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=108).
- Open issue: —.

### C090

`RL2` — Relative; type W.

- Syntax: `RL2`.
- Parameters and framing: 0 off; 1 use current displayed value as new reference; 2 reuse previous reference.
- Prerequisites and effects: Select absolute or relative measurement; LG/LN select relative dB/percent. Reference cannot be read directly by a dedicated scalar query.
- State, persistence, and completion: PR off/reference0; store/recall includes reference/status. Snapshot learn data also contains reference.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Stable reference input; verify RL1 baseline, changed input, RL0, and RL2.
- Source: [00437-90047, REL; see 3-79, printed 3-78, PDF 108](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=108).
- Open issue: —.

### C091

`RM` — Manual range; type W.

- Syntax: `RM<n>EN`.
- Parameters and framing: n=0–5; 0 auto, 1 most sensitive through5 least. Sensor power limits govern actual input.
- Prerequisites and effects: Select range/hold; overrange reports17.
- State, persistence, and completion: PR auto; RA returns auto; selected range stored/recalled.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify each legal range with suitable input and SM range encoding.
- Source: [00437-90047, SET RANGE; error52 A-3/PDF 153, printed 3-94, PDF 124](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=124).
- Open issue: —.

### C092

`*RST` — Soft reset; type W.

- Syntax: `*RST`.
- Parameters and framing: None listed.
- Prerequisites and effects: Summary documents soft reset; equivalence to PR, INIT, or power cycle is unspecified.
- State, persistence, and completion: Capture state and backups before qualification; treat calibration/storage effects as uncertain.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Determine changed state against documented PR/INIT behavior on backed-up setup.
- Source: [00437-90047, Table 3-5, printed 3-42, PDF 72](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=72).
- Open issue: A05.

### C093

`RV` — Mask read; type Q.

- Syntax: `RV`.
- Parameters and framing: None.
- Prerequisites and effects: Read service-request mask using legacy output selection.
- State, persistence, and completion: Mask remains configured until altered/turn-on reset.
- Response: Prose describes ASCII0–255; summary describes 1 byte with EOI for service mask. Capture raw bytes before choosing parser.
- Future qualification: Set known mask, compare raw RV and *SRE? bytes.
- Source: [00437-90047, §3-29; conflicting format §3-34 printed 3-40/PDF 70, printed 3-37, PDF 67](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=67).
- Open issue: A02.

### C094

`SE` — Sensor selection; type W.

- Syntax: `SE<n>EN`.
- Parameters and framing: n=0–9.
- Prerequisites and effects: Select matching sensor data table for frequency correction. Nominal factory table2 covers8482A/B/H, but individual factors govern accuracy.
- State, persistence, and completion: Last selected table used if selection omitted; empty table error80; configuration store/recall includes selection.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Verify table label and correction selection with actual sensor data.
- Source: [00437-90047, SENSOR; see 3-83, printed 3-82, PDF 112](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=112).
- Open issue: —.

### C095

`SM` — Status message; type Q.

- Syntax: `SM`.
- Parameters and framing: None.
- Prerequisites and effects: Read 26-character state string, updated after a measurement; shared status schema defines fields. Reading can clear error latches after cause removed.
- State, persistence, and completion: Error-latch behavior depends on SRQ mask and whether sentinel output occurred.
- Response: 26 ASCII characters + CR LF, EOI; see shared status schema.
- Future qualification: Parse exact length, change reversible settings, and verify stale-versus-updated state.
- Source: [00437-90047, §3-21 Fig 3-5/Table 3-3; Appendix A-1/PDF 151, printed 3-33, PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63).
- Open issue: —.

### C096

`SN0` — Sensor label; type W.

- Syntax: `SN0<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C097

`SN1` — Sensor label; type W.

- Syntax: `SN1<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C098

`SN2` — Sensor label; type W.

- Syntax: `SN2<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C099

`SN3` — Sensor label; type W.

- Syntax: `SN3<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C100

`SN4` — Sensor label; type W.

- Syntax: `SN4<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C101

`SN5` — Sensor label; type W.

- Syntax: `SN5<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C102

`SN6` — Sensor label; type W.

- Syntax: `SN6<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C103

`SN7` — Sensor label; type W.

- Syntax: `SN7<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C104

`SN8` — Sensor label; type W.

- Syntax: `SN8<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C105

`SN9` — Sensor label; type W.

- Syntax: `SN9<label>`.
- Parameters and framing: Table 0–9 then label0–9/A–Z/underscore; detailed max7 characters, summary footnote6.
- Prerequisites and effects: Change persistent table ID label. Treat framing/short-label padding as unresolved.
- State, persistence, and completion: PR preserves table data; backup before editing labels.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up spare table; verify six/seven/short-label framing with raw OD readback.
- Source: [00437-90047, Sensor Data SN; conflicting Table 3-5 footnote PDF 72, printed 3-87, PDF 117](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=117).
- Open issue: A03.

### C106

`SP` — Special menu; type W.

- Syntax: `SP<function>EN`.
- Parameters and framing: SPECIAL function selection and necessary parameters; local menu0 status,1 sensor data,2 limits,3 filter,4 address,5 self-test,6 INIT. Remote domain is bounded by explicit exclusions.
- Prerequisites and effects: Enter SPECIAL context. Direct commands exist for sensor data, limits, and filters; local status/address/self-test/INIT descriptions impose exclusions.
- State, persistence, and completion: EN advances selected level; EX exits. Exact remote function selection semantics require verification.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Use supported reversible menu context only, then EX; resolve ambiguity before destructive options.
- Source: [00437-90047, SPECIAL remote procedure; exclusions 3-98–100, printed 3-97, PDF 127](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=127).
- Open issue: A05.

### C107

`*SRE` — Mask set; type W.

- Syntax: `*SRE<mask>`.
- Parameters and framing: ASCII integer0–255; explicit mask byte framing differs from @1 binary example.
- Prerequisites and effects: Enable selected status conditions to assert RQS/SRQ. Bit7 unused; bit6 is RQS; event sources at0–5.
- State, persistence, and completion: Turn-on mask0; status bits can become set even when masked.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Set mask, query *SRE?, produce controlled source, restore mask.
- Source: [00437-90047, §3-29 Fig 3-6, printed 3-37, PDF 67](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=67).
- Open issue: A02.

### C108

`*SRE?` — Mask read; type Q.

- Syntax: `*SRE?`.
- Parameters and framing: None.
- Prerequisites and effects: Read current service-request mask.
- State, persistence, and completion: Read operation leaves selection configured.
- Response: ASCII000–255 + CR LF/EOI in §3-34; compare with RV legacy framing.
- Future qualification: Read known values0,4,32 and compare raw response length.
- Source: [00437-90047, §3-34; description3-37/PDF 67, printed 3-40, PDF 70](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=70).
- Open issue: A02.

### C109

`ST` — Store; type W.

- Syntax: `ST<n>EN`.
- Parameters and framing: Integer register1–10; register0 reserved for previous configuration.
- Prerequisites and effects: Save front-panel configuration, including reference output/correction states; excludes actual internal calibration/zero settings.
- State, persistence, and completion: Survives PR; registers retained for recall; error57/INIT changes storage. Store selection auto-increments in menu workflow.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Save backed-up configuration into selected expendable register, modify, recall, compare.
- Source: [00437-90047, STORE; see 3-102, printed 3-101, PDF 131](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=131).
- Open issue: —.

### C110

`*STB?` — Status byte query; type Q.

- Syntax: `*STB?`.
- Parameters and framing: None.
- Prerequisites and effects: Read Status Byte as ASCII; unlike serial poll this query does not clear it.
- State, persistence, and completion: Latched conditions/CS/SM interactions described in shared status rules.
- Response: ASCII000–127 + CR LF/EOI; not a binary serial-poll byte.
- Future qualification: Read twice after controlled event, compare CS effect; use separate serial-poll test.
- Source: [00437-90047, §3-30; summary3-40/PDF 70, printed 3-38, PDF 68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=68).
- Open issue: —.

### C111

`TR0` — Trigger; type W.

- Syntax: `TR0`.
- Parameters and framing: 0 hold; 1 immediate; 2 delayed; 3 free-run.
- Prerequisites and effects: TR0 freezes published updates while internal measurement continues. TR1 inserts one filter point without clearing filter. TR2 waits internal settling, not sensor settling. TR3 continuously updates.
- State, persistence, and completion: TR1/TR2 finish in standby; put trigger last in command string. New commands before completion abort trigger. TR3/local free-run does not update data-ready bit. PR TR3. For TR1/TR2, await the read or use a validated serial-poll route; an ASCII *STB?/SM command before completion is subject to the documented abort rule.
- Response: TR1/TR2 produce a measurement for subsequent read, not a dedicated acknowledgement. TR0/TR3 use ordinary measurement output when read.
- Future qualification: Stable input; compare TR0 stale data, TR1/TR2 results, TR3 updates and completion/status.
- Source: [00437-90047, Triggering 3-103–105/PDF 133–135, printed 3-103, PDF 133](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133).
- Open issue: —.

### C112

`TR1` — Trigger; type W.

- Syntax: `TR1`.
- Parameters and framing: 0 hold; 1 immediate; 2 delayed; 3 free-run.
- Prerequisites and effects: TR0 freezes published updates while internal measurement continues. TR1 inserts one filter point without clearing filter. TR2 waits internal settling, not sensor settling. TR3 continuously updates.
- State, persistence, and completion: TR1/TR2 finish in standby; put trigger last in command string. New commands before completion abort trigger. TR3/local free-run does not update data-ready bit. PR TR3. For TR1/TR2, await the read or use a validated serial-poll route; an ASCII *STB?/SM command before completion is subject to the documented abort rule.
- Response: TR1/TR2 produce a measurement for subsequent read, not a dedicated acknowledgement. TR0/TR3 use ordinary measurement output when read.
- Future qualification: Stable input; compare TR0 stale data, TR1/TR2 results, TR3 updates and completion/status.
- Source: [00437-90047, Triggering 3-103–105/PDF 133–135, printed 3-103, PDF 133](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133).
- Open issue: —.

### C113

`TR2` — Trigger; type W.

- Syntax: `TR2`.
- Parameters and framing: 0 hold; 1 immediate; 2 delayed; 3 free-run.
- Prerequisites and effects: TR0 freezes published updates while internal measurement continues. TR1 inserts one filter point without clearing filter. TR2 waits internal settling, not sensor settling. TR3 continuously updates.
- State, persistence, and completion: TR1/TR2 finish in standby; put trigger last in command string. New commands before completion abort trigger. TR3/local free-run does not update data-ready bit. PR TR3. For TR1/TR2, await the read or use a validated serial-poll route; an ASCII *STB?/SM command before completion is subject to the documented abort rule.
- Response: TR1/TR2 produce a measurement for subsequent read, not a dedicated acknowledgement. TR0/TR3 use ordinary measurement output when read.
- Future qualification: Stable input; compare TR0 stale data, TR1/TR2 results, TR3 updates and completion/status.
- Source: [00437-90047, Triggering 3-103–105/PDF 133–135, printed 3-103, PDF 133](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133).
- Open issue: —.

### C114

`TR3` — Trigger; type W.

- Syntax: `TR3`.
- Parameters and framing: 0 hold; 1 immediate; 2 delayed; 3 free-run.
- Prerequisites and effects: TR0 freezes published updates while internal measurement continues. TR1 inserts one filter point without clearing filter. TR2 waits internal settling, not sensor settling. TR3 continuously updates.
- State, persistence, and completion: TR1/TR2 finish in standby; put trigger last in command string. New commands before completion abort trigger. TR3/local free-run does not update data-ready bit. PR TR3. For TR1/TR2, await the read or use a validated serial-poll route; an ASCII *STB?/SM command before completion is subject to the documented abort rule.
- Response: TR1/TR2 produce a measurement for subsequent read, not a dedicated acknowledgement. TR0/TR3 use ordinary measurement output when read.
- Future qualification: Stable input; compare TR0 stale data, TR1/TR2 results, TR3 updates and completion/status.
- Source: [00437-90047, Triggering 3-103–105/PDF 133–135, printed 3-103, PDF 133](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=133).
- Open issue: —.

### C115

`*TST?` — Self-test query; type Q.

- Syntax: `*TST?`.
- Parameters and framing: None listed.
- Prerequisites and effects: Summary lists self-test query while detailed SELF TEST says no remote self-test procedure.
- State, persistence, and completion: Whether query runs tests or reports a result, its output, and state effects require evidence.
- Response: Response format is unspecified by the supplied command summary.
- Future qualification: Resolve semantics before invoking; preserve state/calibration and record raw reply.
- Source: [00437-90047, Table 3-5; SPECIAL SELF TEST3-99–100/PDF 129–130, printed 3-42, PDF 72](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=72).
- Open issue: A05.

### C116

`ZE` — Zero; type W.

- Syntax: `ZE`.
- Parameters and framing: No RF power at sensor; zero all5 ranges; typically5–20s sensor-dependent.
- Prerequisites and effects: Adjust zero; temporarily disable reference and restore its prior state. Poll completion bit1 and error bit3; manual example starts CS and allows30s.
- State, persistence, and completion: Zero data retained through power-off but excluded from ST/RC; PR does not initiate zero. Power interruption can cause error57.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Prepared no-RF path; completion/error check, record residual reading for all ranges.
- Source: [00437-90047, ZERO3-106–108/PDF 136–138, printed 3-106, PDF 136](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=136).
- Open issue: —.

### C117

`@1` — Legacy mask prefix; type B.

- Syntax: `@1<mask-byte>`.
- Parameters and framing: One binary mask byte in HP BASIC USING "2A,B" example; prose calls subsequent value ASCII.
- Prerequisites and effects: Set service mask; preserve exact byte transport and distinguish from decimal ASCII *SRE setter.
- State, persistence, and completion: Turn-on mask0; stream framing must remain intact.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Write binary mask4, compare RV/*SRE?; qualify framing before wider use.
- Source: [00437-90047, §3-12 Require Service example printed 3-22; also3-37/PDF 67, printed 3-22, PDF 52](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=52).
- Open issue: A02.

### C118

`@2` — Learn restore prefix; type B.

- Syntax: `@2<58 binary bytes>`.
- Parameters and framing: Return captured 60-byte learn message uninterrupted, EOI on final byte; no text termination.
- Prerequisites and effects: Restore captured configuration as documented by learn-mode procedure.
- State, persistence, and completion: Restores snapshot fields; byte offsets undocumented. Treat as opaque snapshot rather than invented schema.
- Response: Command completion without a dedicated response; subsequent ordinary reads follow the shared measurement-output rules.
- Future qualification: Backed-up configuration and exact60-byte capture; restore and compare listed fields.
- Source: [00437-90047, §3-21 Learn Mode; Table 3-5 PDF 72, printed 3-32, PDF 62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=62).
- Open issue: A02.

## Physical and service boundaries

| Capability | Documented boundary | Source |
| --- | --- | --- |
| LINE power control | Operated physically; excluded from remote programming | 00437-90047 §3-20, printed 3-30/PDF 60 |
| GPIB address | Set locally, valid0–30 with40 listen-only and50 talk-only; default13 | 00437-90047 SPECIAL HP-IB ADDRESS, printed 3-98–99/PDF 128–129 |
| SPECIAL STATUS | Detailed text supplies no remote procedure; SM exposes selected status fields | 00437-90047 printed 3-98/PDF 128 |
| SELF TEST / INIT | Detailed local procedures and remote exclusions; summary *TST?/*RST ambiguity remains A05 | 00437-90047 printed 3-99–100/PDF 129–130 |
| Service-function switches and service LEDs | Internal physical service controls and diagnostic indications; keep separate from bus commands | 00437-90076 Service Sheet BD1, printed 8-17/PDF 35 and8-23–26/PDF 41–44 |

The service manual review identified physical adjustments, switch-driven self-tests, service LEDs, and fault codes rather than an additional remote-command table. Its serial applicability and safety instructions govern service work. This inventory covers documented commands in the supplied library; undocumented firmware opcodes remain outside the source-backed target.

## Sensor and measurement prerequisites

[08481-90173, Introduction, printed/PDF 15](../../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf#page=15) identifies437B compatibility and sensor-specific calibration-factor use. [Operation, printed/PDF 25](../../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf#page=25) directs meter/sensor calibration to the meter's own procedure and notes temperature sensitivity. Apply the actual8482A limits and serial-specific factors indexed in [equipment records](../EQUIPMENT.md#individual-calibration-records).

The operating manual's performance-test preconditions include a half-hour warm-up (00437-90047 §4-1, printed 4-1/PDF 139). Its nominal20 readings/s figure and conditional settling tables (printed 1-9–10/PDF 19–20) are specification context, rather than a validated host/backend logging rate. Qualification must account for sensor, range, averaging, resolution, and signal changes. Record current-unit observations with the documented supply discrepancy and repeat acceptance on the replacement.
