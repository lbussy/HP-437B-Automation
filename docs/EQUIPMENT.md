# Current equipment and references

Updated: November 24, 2026.

## Manual library

| Manual | Part number | Local reference |
| --- | --- | --- |
| HP 437B Operating Manual | 00437-90047 | [Operating manual](../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf) |
| HP 437B Service Manual | 00437-90076 | [Service manual](../references/manuals/hp-437b/HP-437B-Service-Manual-00437-90076.pdf) |
| 8480 Series Operating and Service Manual, covering 8482A | 08481-90173 | [Sensor manual](../references/manuals/hp-8480-series/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf) |

Publisher editions, source URLs, sizes, and hashes are in the [manual manifest](../references/manuals/download-manifest.json) and [checksum list](../references/manuals/SHA256SUMS.txt). These originals are unmodified. Use the operating manual for commands and procedures, the service manual for service/performance work, and the actual sensor label/certificate for correction data and limits. Do not assume modern SCPI syntax.

## Individual calibration records

| Equipment | Serial number | Certificate | Calibrated | Next due, as listed | Record |
| --- | --- | --- | --- | --- | --- |
| HP 437B meter | 3125U22346 | DXC-2026-3340-001 | 2026-11-11 | 2028-11-11 | [Meter, 4 retained pages](../references/calibration/hp-437b/3125U22346/2026-11-11/derived/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf) |
| Agilent 8482A sensor | MY41094127 | DXC-2026-3339-002 | 2026-10-15 | 2027-10-15 | [Sensor, 2 pages](../references/calibration/hp-8482a/MY41094127/2026-10-15/originals/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf) |
| Agilent 8482H sensor | 3318A09219 | DXC-2026-3360-001 | 2026-11-15 | 2027-11-15 | [8482H, certificate + calibration chart](../references/calibration/hp-8482h/3318A09219/2026-11-15/derived/HP-8482H-SN-3318A09219-Calibration-2026-11-15.pdf) |

DXCONNECTION / Valley Precision Instrument Calibration Services issued these records. The meter certificate reports Passed/In Tolerance as left, with **5.014 VDC** for its +5 V rail, within 4.75–5.25 V. The [calibration review](validation/CALIBRATION-REVIEW.md) records numeric results and printed-limit, reference-frequency, DVM-identification, and uncertainty limitations. The repository contains a four-page derived meter calibration record.

The 8482H record reports Passed/In Tolerance and a 99% reference calibration factor. Its certificate and calibration chart are dated **November 15, 2026**. The two-page record contains the signed certificate and serial-specific chart; the complete chart is also available separately. See the [8482H review](validation/8482H-CALIBRATION-20261122.md).

## Setup and identification

The owner confirms the **8482A SN MY41094127** is connected to the HP 437B. Its reference calibration factor is **99%**. The [supervised bench record](VALIDATION.md#8482a-zero-and-cal) documents completed ZERO and CAL for this connection. Confirm the RF path and sensor input limits for each run. See [meter preparation](workflows/METER-PREPARATION.md).

The meter's laboratory sheets list software **2.0** and HPIB address **13**. The [November 23 Mac bench run](validation/30M-POWER-20261123.md) observed firmware 2.0 and descriptor/resource serial `HEWLETT-PACKARD_437B_2.0`, with owner-confirmed 8482A connection and source state. Reconfirm the actual setup for subsequent runs; broader interaction checks remain pending. The front-panel address was not independently read in that run.

The adapter is XyphroLabs **USBGpib V2**, vendor/product **03eb:2065**, with recorded adapter firmware **V2.4**, an Anker USB-C cable, and no established exact PCB revision. Adapter firmware is separate from instrument software. Discover the actual USB descriptor/resource; do not assume it is a stable meter identifier. See [adapter details](validation/ADAPTER-IDENTIFICATION.md).

For internal-reference use, prepare the sensor cable to SENSOR and sensor RF input directly to POWER REF, initially off, with no external source or attenuation. Confirm the actual connector option, warm-up, factors, units, range/filter, duty/offset/REL state, and operator recovery access. A radio measurement needs its own documented load/attenuation path, applicable limits, factors, and uncertainty information. See the [measurement policy](validation/MEASUREMENT-POLICY.md) and [setup checks](validation/BENCH-ACCEPTANCE.md).
