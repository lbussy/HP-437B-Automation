# Current equipment and references

Updated: November 19, 2026.

## Manual library

| Manual | Part number | Local reference |
| --- | --- | --- |
| HP 437B Operating Manual | 00437-90047 | [Operating manual](../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf) |
| HP 437B Service Manual | 00437-90076 | [Service manual](../output/pdf/hp-437b-8482a/HP-437B-Service-Manual-00437-90076.pdf) |
| 8480 Series Operating and Service Manual, covering 8482A | 08481-90173 | [Sensor manual](../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf) |

Publisher editions, source URLs, sizes, and hashes are in the [manual manifest](../output/pdf/hp-437b-8482a/download-manifest.json) and [checksum list](../output/pdf/hp-437b-8482a/SHA256SUMS.txt). These originals are unmodified. Use the operating manual for commands and procedures, the service manual for service/performance work, and the actual sensor label/certificate for correction data and limits. Do not assume modern SCPI syntax.

## Individual calibration records

| Equipment | Serial number | Certificate | Calibrated | Next due, as listed | Record |
| --- | --- | --- | --- | --- | --- |
| HP 437B meter | 3125U22346 | DXC-2026-3340-001 | 2026-11-11 | 2028-11-11 | [Meter, 4 retained pages](../output/pdf/hp-437b-8482a/calibration/replacement-2026-11-19/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf) |
| Agilent 8482A sensor | MY41094127 | DXC-2026-3339-002 | 2026-10-15 | 2027-10-15 | [Sensor, 2 pages](../output/pdf/hp-437b-8482a/calibration/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf) |

DXCONNECTION / Valley Precision Instrument Calibration Services issued these records. The meter certificate reports Passed/In Tolerance as left, with **5.014 VDC** for its +5 V rail, within 4.75–5.25 V. The [current review](validation/REPLACEMENT-CALIBRATION-20261119.md) records numeric results and remaining printed-limit, reference-frequency, DVM-identification, and uncertainty limitations. The repository copy retains source pages 1–4 after owner-directed removal of duplicate pages 5–6; it is not an unmodified complete original.

## Setup and identification

The meter's laboratory sheets list software **2.0** and HPIB address **13**. Actual firmware/resource discovery, front-panel address, sensor connection, source state, and correction settings require confirmation before a selected hardware run. Project interaction checks for this meter remain pending.

The adapter is XyphroLabs **USBGpib V2**, vendor/product **03eb:2065**, with recorded adapter firmware **V2.4**, an Anker USB-C cable, and no established exact PCB revision. Adapter firmware is separate from instrument software. Discover the actual USB descriptor/resource; do not assume it is a stable meter identifier. See [adapter details](validation/ADAPTER-IDENTIFICATION.md).

For internal-reference use, prepare the sensor cable to SENSOR and sensor RF input directly to POWER REF, initially off, with no external source or attenuation. Confirm the actual connector option, warm-up, factors, units, range/filter, duty/offset/REL state, and operator recovery access. A radio measurement needs its own documented load/attenuation path, applicable limits, factors, and uncertainty information. See the [measurement policy](validation/MEASUREMENT-POLICY.md) and [setup checks](validation/REPLACEMENT-ACCEPTANCE.md).
