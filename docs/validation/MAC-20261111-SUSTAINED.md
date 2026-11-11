# Five-minute Mac reference logging, November 11, 2026

Status: ✅ Complete for this Mac/current-unit five-minute reference batch; owner confirmed live numeric readings, RMT off, no TRIGGER HOLD, and PWR REF off without PRESET/LOCAL. Phase 3 remains ⏳ In progress. [Plan](PHASE-3-PLAN.md#p3-sustain-five-minute-reference-logging) and [cleanup correction](AUTOMATIC-LOCAL.md#p3-r10-corrected-results-and-final-reassessment) define scope. Tested revision: `8e29186a3e5f3e0565727294799611ffc9e9945f`; production cleanup code is the verified TR3-before-GTL correction from `e8d1da5`.

## Setup and procedure

Same identified original meter SN 3125U33223, with known unacceptable supply discrepancy, and sensor 8482A SN MY41094127. Sensor attached directly to internal POWER REF, cable to SENSOR; no radio, external RF source, attenuation, or wiring change. Nominal internal reference 50 MHz/1 mW. Owner confirmed source on after waiting and reported 0.988 mW before acquisition. Retained REF CF 99%, active CAL FAC 100%, duty/offset/REL off, automatic range/filter, and absolute W. This is sustained configured readback evidence, not absolute accuracy, real-radio/modulation performance, or replacement acceptance.

Host/runtime: same ARM64 MacBook Pro/macOS 27.0.1, Python 3.14.10, libusb 1.0.30, PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1, instrument firmware 1.8, and explicit @py resource as [previous runs](MAC-20261111.md#setup-and-provenance). Adapter revision/firmware remain unknown. The project-local cleanup profile is `xyphro-usb488-gtl-v1` with explicit TR3 beforehand.

```bash
.venv/bin/hp437b log \
  --resource 'USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR' \
  --output output/logs/phase3-20261111/reference-five-minute.csv \
  --duration 300 --interval 1 --timeout 10 --unit W \
  --meter-serial 3125U33223 --sensor-serial MY41094127
```

Production CLI: one open, identification, RL0/LN preserving established units, one setup TR2/read excluded from rows/duration, fresh SM, then serialized TR2/read acquisitions during a 300-second acquisition-start window. Normal close sends TR3 followed by negotiated USB488 GTL; no reset, zero, gain calibration, correction, or source switch. One attempt; no physical fault injection or automatic retry. Owner source-off confirmation is a separate final step.

## Recorded results

Session `9a97e87f-9660-490d-b5a5-d16357d17277` started `2026-11-11T21:14:12.196505+00:00` and finished `2026-11-11T21:19:12.650483+00:00` (UTC; local zone America/Chicago, UTC−06:00). Final metadata: completed, non-simulated. Initial status raw `000000130011000A1012000000` confirms reference on, W, corrections off, no instrument errors, and auto range/filter; it is a setup observation, not continuous independent monitoring of physical output.

| Check | Observed result |
| --- | --- |
| Requested duration/spacing | 300 seconds, one-second start spacing; 10-second operation timeout |
| CSV count/integrity | 299 valid contiguous rows; 0 invalid rows; 0 missing sequence IDs |
| Values, configured mW | Minimum 0.988, maximum 0.989, arithmetic mean 0.988003 |
| Host receipt spacing | Minimum 0.998679 s, maximum 1.012312 s, mean 1.003768 s |
| Reconstructed acquisition latency | Minimum 0.230255 s, maximum 0.234132 s, mean 0.232143 s |
| Maximum start overrun | 0.010039 s; 0 above 0.1 s |
| Last acquisition start / receipt | Reconstructed start 299.123998 s, monotonic receipt elapsed 299.355805 s |
| Loop window through finalization | 300.036129 s, estimated from UTC receipt minus matching monotonic elapsed |
| Whole session | 300.453978 s including setup and cleanup |
| Normal cleanup | `instrument_cleanup`: accepted, TR3 then USB488 GTL; local request accepted with exact response `01` |

Each row's raw ASCII numeric value was independently compared with the CSV value/unit; timestamps have explicit UTC offsets, elapsed/UTC times increase, identities/sequences/session metadata match, setup capture is separate, and final raw bytes match the last row. Initial reference/correction flags and declared dependency versions pass. A timestamp is host receipt time, not the instrument's internal sample time.

Acquisition-start offsets are reconstructed from the documented scheduler recurrence: first start equals its recorded overrun, then each start equals preceding actual start plus one-second interval plus its overrun. Each reconstructed start falls below the 300-second cutoff, and each receipt lies within its operation deadline. Loop-start UTC is estimated by subtracting the first receipt's monotonic elapsed from its UTC timestamp. Those calculations validate the finite duration against artifacts; they do not create a hardware timestamp or prove an unconditional future one-Hz rate. Automatic range/filter and the retained factors bound interpretation. No reading was adjusted to force 1 mW. The last acquisition started at 299.123998 seconds; its next nominal start would be 300.123998 seconds, beyond the 300-second cutoff. Thus 299 rows are consistent with the requested duration and measured scheduling delays; there is no missing sequence or failed 300th acquisition.

## Evidence and limits

Raw artifacts remain ignored; selected summary only is committed. SHA-256 values:

| Local path | SHA-256 |
| --- | --- |
| `output/logs/phase3-20261111/reference-five-minute.csv` | `f317588c05767e34c4c18fae7971f001c103f9c52dd51a46c0391ec6d62cf4c7` |
| `output/logs/phase3-20261111/reference-five-minute.csv.session.json` | `58048452b0fb8633a21b3d9fb0caa43305ce1bf2fa9433edd1606df390952d9d` |
| `output/logs/phase3-20261111/reference-five-minute-verification.json` | `6d30671c6e930fa13d0cdcb8af3b325813b9f75c376ba187d909c47c56f6949d` |
| `tmp/local-return/verify-sustained.py` | `36775e7307c85e833df8b4253baf5d2a831772f41b943e3ee765b8b2997160a9` |

The verifier records operator restoration pending as of its creation; later owner observations are retained separately without modifying raw evidence. Automatic request acceptance alone is not final source-off or front-panel proof. Interruption, physical timeout/disconnection recovery, reversible unit changes, Pi access/retrieval, and all mandatory replacement-meter cases remain open. No extra hardware case was silently bundled with sustained collection.

## Software and delivery checks

The exact tested revision’s [software CI](https://github.com/lbussy/HP-437B-Automation/actions/runs/43101396677) passed. Corrected source and separate installed-wheel environments each passed 237 tests, lint/format, and package builds before this sustained run. No code changed during acquisition. Markdown links/anchors, matrix IDs, whitespace, and the nine original reference files were checked before delivery; raw local artifacts remain ignored. Software checks do not replace physical host/unit acceptance.

## Final operator confirmation

The owner confirmed that numeric readings resumed with RMT off and no TRIGGER HOLD, then PWR REF was switched off and its indicator was off, without pressing PRESET/LOCAL. This completes the specified operator restoration gate for P3-SUSTAIN. Accept the five-minute run on the recorded current-meter/Mac setup only; Phase 3 remains in progress for interruption/failure recovery, reversible control, Pi/retrieval, and replacement acceptance. Raw artifacts retain their capture-time pending field and were not amended.
