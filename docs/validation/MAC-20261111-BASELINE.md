# Mac connected-sensor baseline, November 11, 2026

Status: read sequence passed; owner confirmed the held display matched approximately −0.006 mW, RMT went off, and updating resumed after return to local. Phase 3 remains ⏳ In progress. This extends the [identification run](MAC-20261111.md) under the [P3-BASELINE plan](PHASE-3-PLAN.md#p3-baseline-connected-sensor-reference-off). Production source: `8c75c45997704764647f4ff5979cd579372cf59b`; only documentation and ignored scratch capture code changed. Host/runtime/resource match the identification record: ARM64 MacBook Pro, macOS 27.0.1, Python 3.14.10, PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1, libusb 1.0.30, explicit `@py`.

## Setup and procedure

The owner confirms original meter SN 3125U33223 and 8482A sensor SN MY41094127, sensor cable connected to SENSOR, sensor RF connector directly connected to POWER REF, and reference output off. Initial owner-observed display: −0.009 mW. The current meter retains its known supply discrepancy; these are interim development observations. No external RF source is connected. No RF-output, correction, range, filter, unit, zero, calibration, preset, or table-setting command was sent.

One explicit open, `Instrument.query("SM")`, one `Instrument.acquire("TR2")`, then `Instrument.query("SM")`, and finally close. Each operation had a 10-second deadline; total batch budget was 45 seconds with no retries or faults. The initial status gate required normal mode, absolute linear W, free-run, and reference off. The trigger reply was consumed before the second SM. Local operation restores free-run; the operator was asked to record the held reading before pressing PRESET/LOCAL once while remote.

## Physical observations

Acquisition ran 20:06:01.282014–20:06:08.889934 UTC (14:06:01–14:06:08 CST). Total including open/close: 7.6077 seconds. Initial SM: 0.01695 seconds; TR2/read: 7.43105 seconds; final SM: 0.01661 seconds. One valid numeric reading and no instrument-error sentinel were returned. This single duration establishes neither a sustained rate nor a general timeout guarantee.

| Operation | Raw ASCII, with explicit terminators | Observed interpretation |
| --- | --- | --- |
| SM before | `000000110017000A0002000010\r\n` | Normal; measurement/entry errors 0/0; absolute W; reference off; free-run; range 11; filter 17; offset off; duty correction on; GET policy 2 |
| TR2/read | `-0.0060E-03\r\n` | −0.0000060 W = −0.0060 mW = −6.0 µW |
| SM after | `000000110017000A0012000010\r\n` | Same settings/flags, with standby set after completed TR2/read |

Both SM payloads contain 26 characters followed by CRLF; the measurement reply contains 13 bytes including CRLF. The existing parser accepted all three frames. Filter 17 represents auto averaging of 128 readings, and range 11 is automatic range 1 under the inventory schema. The observed 7.43-second TR2 completion is recorded alongside those settings, without assigning a causal timing model from one sample. No electrical EOI trace or binary-framing test was performed.

The initial SM showed duty-cycle correction enabled. During subsequent front-panel inspection using DUTY CYCLE, the owner reported 1%. This corresponds to a mathematical ×100 average-to-pulse-power correction (+20 dB). Exit was instructed using SHIFT, then ENTER, without committing an entry; the later owner confirmation below establishes exit and disabling. No software duty-setting command was sent. Sensor correction values, zero/calibration state, and quantitative accuracy remain unqualified. The −0.009 mW pre-run display and −0.006 mW triggered reading were not simultaneous or governed by a stability/tolerance rule. They cannot establish display agreement or absolute power accuracy. The subsequent owner report confirms approximately −0.006 mW on the held display before return to local, followed by RMT off and resumed updating. This is one qualitative held-display agreement observation, not the formal quantitative comparison gate, which still requires a preselected tolerance/stability rule. Negative baseline power is retained rather than clamped to zero. This batch verifies the selected byte sequence and status interpretation with the reference off.

## Evidence and acceptance boundaries

Raw evidence remains ignored at `output/logs/phase3-20261111/sensor-baseline.json`, SHA-256 `7f5d101e67fdc22c043972809feaedace0bad87e7af292b0c9e88cd561021d4b`. It contains exact hex/ASCII bytes, parsed results, UTC times, elapsed durations, source revision, setup, resource, dependencies, and finally-close outcome. The local scratch script is `tmp/phase3-baseline.py`, SHA-256 `9038d36aa0b5a78286273a6b9003b467fd0f0e63f5b0b98217fce10624c5cfdd`. Operator follow-up is recorded separately; raw evidence is not amended after capture.

C095 and C113 have passing Mac reference-off frame/sequence observations; complete status lifecycle, error semantics, trigger settling, corrected power, and replacement qualification remain open. G002/G003/G004 remain partial, with ASCII status/measurement-path evidence. Unit configuration, reversible LG/LN control, short/sustained logging, failure recovery, Pi qualification/retrieval, and replacement acceptance are pending. No remote zero or calibration has been performed; subsequent manual preparation is recorded below.

## Duty correction disabled by operator

The owner subsequently confirms DTY CY is off after SHIFT, then DUTY CYCLE, with POWER REF still off. This establishes the instructed local toggle and exit from percentage entry, not remote DC0 qualification. The previously observed 1% value remains recorded; no new percentage was entered. The subsequent manual-zero observation is recorded below; gain calibration remains pending.

## Owner-reported post-zero reading

After the 30-minute warm-up reminder and the [manual-zero instructions](PHASE-3-PLAN.md#p3-manual-zero-preparation), the owner reported −0.009 µW (−9 nW). Record this as the reported post-procedure residual, not an independent all-range zero/performance pass. No error or timing detail was supplied, and no Python command was issued. The instructed setup keeps POWER REF off, duty correction off, sensor RF input disconnected, and the sensor cable attached. Gain calibration remains pending verification of the sensor reference calibration factor and the prepared reference path; remote C116 remains guarded.
