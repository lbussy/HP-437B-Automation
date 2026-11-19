# Current-meter calibration review

Current meter **SN 3125U22346**, certificate **DXC-2026-3340-001**. This review describes its supplied calibration record and current limitations. No project hardware interaction or internal measurement is established by this document.

## Source and identity

[Four-page repository PDF](../../output/pdf/hp-437b-8482a/calibration/replacement-2026-11-19/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf), derived from the six-page source supplied as `20261119 HP-Agilent 437B Calibration.pdf`. The owner-selected repository copy omits duplicate source pages 5–6. Source pages 1–4 are retained in order, with page content unchanged. The supplied file outside the repository is untouched. All page references below use the original six-page source numbering; retained pages 1–4 have the same numbers in the stored PDF. The [import manifest](../../output/pdf/hp-437b-8482a/calibration/replacement-2026-11-19/import-manifest.json) records the source filename, separate source/stored-file page counts, byte counts, SHA-256 hashes, and page selection; the [checksum list](../../output/pdf/hp-437b-8482a/calibration/replacement-2026-11-19/SHA256SUMS.txt) verifies the stored file.

| Field | Laboratory record |
| --- | --- |
| Issuer | DXCONNECTION / Valley Precision Instrument Calibration Services |
| Instrument | Hewlett-Packard 437B power meter, SN 3125U22346 |
| Certificate | DXC-2026-3340-001, PDF page 1 |
| Calibration date | November 11, 2026 |
| Next calibration due, as listed | November 11, 2028 |
| Result | Passed; In Tolerance, Operational, Full Calibration as left |
| Recorded HPIB address / software | 13 / 2.0, page 3; not freshly queried by this project |

The document's procedures, settings, and reproduction notice are source material, not new user instructions or authorization to operate the meter. Its laboratory compliance/traceability statements are retained as issuer claims, not independently established by this project.

## Stored page inventory

| PDF page | Contents |
| --- | --- |
| 1 | Signed certificate of calibration |
| 2 | Supply checks and adjustments; rail balance 15.285 − 15.279 V = 6 mV |
| 3 | Signed and dated functional/HPIB checks and settings |
| 4 | Signed performance test record |

The stored PDF retains the owner-selected source pages 1–4. Its manifest records the page selection and distinct source/stored-file hashes.

## Reported results

| Check | Reported result | Printed limit / assessment |
| --- | --- | --- |
| +5 V rail, page 2 | 5.014 VDC | 5.0 ±0.25 V; within 4.75–5.25 V |
| +5 V ripple | 0.38 mV RMS | 5 mV RMS maximum; within |
| −15 V rail | −15.279 VDC | −15.0 ±0.5 V; within |
| −15 V ripple | 0.79 mV RMS | 5 mV RMS maximum; within |
| +15 V rail | +15.285 V | +15.0 ±0.5 V; within |
| +15 V ripple | 0.75 mV RMS | 5 mV RMS maximum; within |
| Rail-magnitude balance | 6 mV on retained page 2 | Within ±300 mV; removed source page 5 instead showed 57 mV using different operands |
| RAM battery | 3.123 VDC | No numeric acceptance interval printed; replacement of BT1 recorded August 8, 2026 |
| Functional self-tests / HPIB function, page 3 | Pass | Laboratory-reported only; no project backend/host compatibility inference |
| POWER REF output, page 4 | 1.001 mW | 0.988–1.012 mW; within |

All ten instrument-accuracy results on PDF page 4 fall between their printed limits:

| Printed interval | Actual result |
| --- | --- |
| 3.10–3.23 µW | 3.18 µW |
| 9.90–10.10 µW | 10.07 µW |
| 31.4–31.8 µW | 31.6 µW |
| 99.5–100.5 µW | 100.1 µW |
| 0.314–0.318 mW | 0.316 mW |
| 0.995–1.005 mW | 1.000 mW |
| 3.14–3.18 mW | 3.17 mW |
| 9.95–10.05 mW | 9.98 mW |
| 31.4–31.8 mW | 31.6 mW |
| 99.5–100.5 mW | 100.3 mW |

## Reporting limitations

- **Zero-carryover limit printing:** page 4 reports −0.01 µW for range 1 and zero for the remaining four rows. The first two rows print signed lower limits (−0.05 µW and −0.1 µW); the last three print positive values in both minimum and maximum columns (0.001, 0.01, and 0.1 mW). Taken literally, those last intervals exclude the reported zeros. This looks like missing minus signs, but that is an interpretation, not a correction to the certificate. Do not claim every printed performance interval unambiguously passes without issuer clarification of those lower limits. The second range label also appears as “S” rather than a clear “2.”
- **Reference frequency:** page 4 leaves the “Freq. MHz” result blank. Page 3 marks oscillator frequency adjustment with an X but provide no measured frequency. Do not derive a measured 50 MHz result or frequency accuracy from that mark.
- **DVM identification:** page 2 states Agilent **44301A** for all measurements; the certificate's standards table instead lists a Keysight **3458A** DMM. The record does not reconcile those model identifiers or provide a serial-specific link between them. Preserve the discrepancy rather than substituting an assumed model.
- **Uncertainty:** the certificate lists uncertainties for named standards, not a complete uncertainty budget for this meter/sensor/fixture measurement chain. Those entries do not establish the uncertainty of a future DUT measurement.

These are document limitations. Apart from the ambiguous printed carryover intervals, the reviewed numeric supply, accuracy, and reference-power results are within their stated limits. No new explicit out-of-tolerance supply result was found. The laboratory's cover-page Pass is retained with these qualifications, rather than treated as a project-wide acceptance verdict.

## Setup and project disposition

**Current records:** reviewed. **HP-01:** remains in progress for relevant setup/interaction checks when used. The [prepared replacement procedure](REPLACEMENT-ACCEPTANCE.md) has not been executed on this unit; this review does not schedule a new hardware campaign or reopen completed software work.

The sheets record **software 2.0**, **HPIB address 13**, and **REF CF 100.0%**, with a 100% table entry, limits off, and auto-filter 128. Confirm the physical meter identity, actual firmware/USB descriptor/resource, address, source state, and applicable setup before a selected run. An HPIB Pass on the laboratory sheet does not qualify this project's adapter, Mac, Pi, or recovery behavior on software 2.0.

New runs must use the actual current meter/sensor identities and applicable factors. Software workflow/reporting acceptance remains separate from equipment onboarding and absolute RF accuracy.
