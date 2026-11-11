# Mac reference-on Python readback, November 11, 2026

Status: reference-on acquisition, held-display comparison, and operator-confirmed local/reference-off restoration passed for this batch. Phase 3 remains ⏳ In progress. See the [case plan](PHASE-3-PLAN.md#p3-reference-read-python-versus-held-display), [earlier baseline](MAC-20261111-BASELINE.md), and [review](PHASE-3-REVIEW.md). Tested production source: `eb2057107798903ff088ae8fcb064a24b0ef080d`; only documentation and ignored scratch code changed.

## Setup and scope

Original meter SN 3125U33223 with the known supply discrepancy, and 8482A sensor SN MY41094127, cable to SENSOR, sensor directly attached to front POWER REF. Reference is nominally 50 MHz/1 mW, with no external RF source or attenuator. Owner-reported manual preparation: zero, CAL REF CF 99%, duty correction off, active measurement CAL FAC 100.0%. The owner first observed 0.989 mW with reference on, switched it off, and then explicitly requested Python readback. They confirmed the instructed reactivation/wait before this acquisition. No software reference, unit, correction, zero, or calibration setter was sent.

Host/runtime/resource match the [identification environment](MAC-20261111.md#setup-and-provenance): ARM64 MacBook Pro/macOS 27.0.1, Python 3.14.10, PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1, libusb 1.0.30, explicit `@py` and `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. Instrument firmware previously identified as 1.8; adapter revision/firmware remain unknown. No replacement or Pi qualification is implied.

## Captured result

One open, SM, TR2/read, SM, and finally-close ran 20:50:05.049587–20:50:05.451215 UTC (14:50:05 CST). Total including open/close: 0.40140 seconds. TR2/read: 0.23232 seconds; status queries approximately 0.016 seconds each. This is one operation duration, not a sustained rate.

| Operation | Exact ASCII payload with terminators | Interpretation |
| --- | --- | --- |
| SM before | `000000130011000A1002000000\r\n` | Normal, errors 0/0, absolute W, reference on, duty/offset/REL off, free-run, auto range 3, auto filter 2 readings, GET policy 2 |
| TR2/read | `+0.9880E-03\r\n` | +0.0009880 W = 0.9880 mW, no error sentinel |
| SM after | `000000130011000A1012000000\r\n` | Same flags/range/filter, with standby set after completed trigger/read |

SM frames contain 26 characters plus CRLF; the measurement frame contains 13 bytes including CRLF. Raw hex and parsed fields are preserved locally. Source read completed before the following SM. The returned value is the configured display-equivalent power, with CAL FAC 100.0% retained; it is not an independent measurement of reference accuracy. The earlier manual 0.989 mW reading is a different sample and is not the formal held-display comparison target. No factor adjustment was made to force 1 mW.

## Comparison and restoration

Before acquisition, the plan selected held-display agreement within 0.001 mW at a 0.001 mW display increment, matching units, with no errors. The owner reported the held display as 0.988 mW, then confirmed RMT and PWR REF both off. Compared with Python 0.9880 mW, the displayed numerical difference is 0.0000 mW, within the preselected 0.001 mW criterion at the observed display increment. This passes this held-display readback case. Local/reference-off restoration is operator-confirmed; USB close alone would not establish either. Failure recovery, absolute accuracy, calibrated sensor response, sustained logging, and unattended operation remain unqualified.

## Local evidence

Raw artifact: `output/logs/phase3-20261111/reference-readback.json`, SHA-256 `fe9b588b2aa99b2deac8d386edc6114d697ea7b13d2bd162225e4a8f66eab0bc`. Scratch capture: `tmp/phase3-reference-readback.py`, SHA-256 `9158a80c304295f4101aad9e27293d151966d2ae03ca6f95c6091296d80a5db7`. Both remain ignored. The artifact records exact command-stage replies, UTC/monotonic times, resource/dependencies, setup, tested source, and finally-close. Operator observations are recorded separately without amending raw artifacts.

C095/C113 and G002/G003/G004 retain partial physical coverage, now including this reference-on ASCII path; all broader tests and replacement/second-host acceptance remain explicit. No production code or dependency change was required.
