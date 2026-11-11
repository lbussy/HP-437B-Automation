# Mac short CSV logging, November 11, 2026

Status: P3-SHORT passed for the recorded current-meter/reference setup; Phase 3 ⏳ In progress. Owner confirmed the final held display and RMT/reference off after cleanup. [Plan](PHASE-3-PLAN.md#p3-short-three-row-reference-csv), [reference readback](MAC-20261111-REFERENCE.md), and [review](PHASE-3-REVIEW.md) retain broader qualification limits. Tested source: `824fcf4e84a7e02dd8ece3679c25ef1ae60d70ef`; production source/dependencies unchanged during this batch.

## Setup and exact invocation

Original meter SN 3125U33223 with known supply discrepancy; sensor 8482A SN MY41094127 directly on front POWER REF, sensor cable to SENSOR. No external radio/source or attenuation. Operator activated internal nominal 50 MHz/1 mW reference and confirmed after the requested wait. Retained manual preparation: REF CF 99%, CAL FAC 100.0%, duty correction off. Captured initial status confirms absolute W, reference on, duty/offset/REL off, no errors, auto range 3, and auto filter 2 readings. Do not infer real-radio behavior, calibrated reference accuracy, or replacement acceptance.

The [Mac environment](MAC-20261111.md#setup-and-provenance) remains ARM64/macOS 27.0.1, Python 3.14.10, libusb 1.0.30, PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1, explicit `@py`, and instrument firmware 1.8. Adapter revision/firmware remain unverified.

```bash
.venv/bin/hp437b log \
  --resource 'USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR' \
  --output output/logs/phase3-20261111/reference-short.csv \
  --count 3 --interval 1 --timeout 10 --unit W \
  --meter-serial 3125U33223 --sensor-serial MY41094127
```

The production CLI opens once, identifies, sends RL0/LN (preserving established absolute linear state), consumes one setup TR2/read, reads fresh SM, then performs three serialized TR2/read pairs. It sends no zero, calibration, table, reference-output, or retry commands. The logger closes after collection. The setup reading is stored in metadata and excluded from the three CSV rows. This one-second/three-row policy is adopted only for this short reference batch, rather than a final general measurement policy.

## Physical and file results

Session `71ff19bb-5f52-43ff-852c-348f866960bd` ran 20:52:06.243092–20:52:08.934739 UTC (14:52:06–14:52:08 CST), 2.691647 seconds including setup and close. CLI exited 0 with `completed`, three rows, and `simulation: false`.

| Check | Result |
| --- | --- |
| Count and integrity | Three requested/recorded rows, sequences 1–3; zero missing, invalid, or instrument-error rows |
| Values and raw bytes | All rows +0.0009880 W = 0.9880 mW; each exact frame `+0.9880E-03\r\n` matches its CSV value independently |
| Initial state | `000000130011000A1012000000\r\n`; normal, no errors, W, reference on, duty/offset/REL off, standby after setup acquisition |
| Timing | UTC receipt spacing 0.999701 s and 1.002169 s; maximum recorded acquisition-start overrun 0.00134117 s |
| Time/session fields | Explicit UTC offset, increasing monotonic elapsed/UTC times, matching row/sidecar session IDs, expected count/settings/context/dependency provenance |
| Metadata and close | Completed final metadata, final raw reply matches last row, separate setup measurement retained; normal resource close returned |
| Existing-file protection | Repeating the same CLI against existing outputs exited 1 with FileExistsError before connect; CSV/sidecar SHA-256 unchanged |
| Held display | Owner reported 0.988 mW after close; matches final sample within the previously selected 0.001 mW criterion |
| Operator restoration | Owner explicitly confirmed RMT and PWR REF both off after PRESET/LOCAL and manual source-off |

These two receipt intervals are measured observations, not a sustained-rate or future deadline guarantee. Raw timestamps are host receipt times, not instrument sample times. The file-protection follow-up performs no device I/O because reservation fails before connect; it is not a physical communication-fault/recovery test. One complete session establishes normal cleanup, not automatic local restoration or unattended recovery.

## Evidence retention

Raw local artifacts and the independent verifier remain ignored. Reviewed summary only is committed.

| Path | SHA-256 |
| --- | --- |
| `output/logs/phase3-20261111/reference-short.csv` | `d116b41bf857066fd59a32572a2b47e02a8e324b5f66443f5d5e19771f893f16` |
| `output/logs/phase3-20261111/reference-short.csv.session.json` | `cc9b3051a3cfda82893057cf8ebae1167e857e66d0f992875ea4c80a6fa6236a` |
| `output/logs/phase3-20261111/reference-short-verification.json` | `196ae213d7afd024893fde7a10f671a481bc512c6576fae91c6488dee03247d6` |
| `tmp/verify-short-log.py` | `9b693f6b31ea0c45e77f68d250bd4e197082a16abb43e6a0f8a9a6be8c966143` |

The verification record captures restoration as pending at its creation; the later owner confirmation above is separate, and raw artifacts were not amended. The independent check validates numeric raw/value consistency, count, rows, provenance, parsed initial flags, timestamps, final metadata, and pre/post protection hashes. No production change or expanded unit-test run was necessary for this documentation/evidence batch.

## Next cases and limits

Next is a separately bounded sustained reference logging run, followed by planned interruption/timeout recovery and reversible unit-control checks. Those are not released by this short-run result. Pi access/retrieval, all mandatory replacement-meter cases, and final profile acceptance remain open. The present profile permits one manual PRESET/LOCAL operation after each remote session; the production logger uses one open connection across all samples. Automatic programmatic local return is unqualified with the pinned backend, and the assistant has not adopted a backend/firmware change.
