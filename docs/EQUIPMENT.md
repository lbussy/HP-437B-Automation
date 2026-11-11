# HP 437B and HP 8482A references

Updated: 2026-11-11. The user identified an HP 437B power meter and an HP 8482A sensor and requested their manuals be saved locally. The three official PDFs are present, and their sizes and SHA-256 hashes matched the download manifest during the October 31 verification.

## Manual library

| Manual | Part number | Pages | Local original |
| --- | --- | --- | --- |
| HP 437B Operating Manual | 00437-90047 | 157 | [Operating manual](../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf) |
| HP 437B Service Manual | 00437-90076 | 58 | [Service manual](../output/pdf/hp-437b-8482a/HP-437B-Service-Manual-00437-90076.pdf) |
| 8480 Series Operating and Service Manual covering 8482A | 08481-90173 | 87 | [Sensor family manual](../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf) |

Edition and publisher URL details are in the [download manifest](../output/pdf/hp-437b-8482a/download-manifest.json). The sensor manual is edition 9, August 29, 2025. It is a family manual, not the individual sensor's calibration certificate.

## Individual calibration records

The owner supplied these complete, unmodified laboratory records on November 11, 2026. Both certificates report “Passed” and “In Tolerance” as left. These are laboratory-reported results, separate from this project's future bench and automation validation.

| Equipment | Serial number | Certificate | Calibration date | Next due, as listed | Original record |
| --- | --- | --- | --- | --- | --- |
| HP 437B power meter | 3125U33223 | DXC-2026-3339-001 | 2026-10-15 | 2028-10-15 | [Meter calibration, 4 pages](../output/pdf/hp-437b-8482a/calibration/HP-437B-SN-3125U33223-Calibration-2026-10-15.pdf) |
| Agilent 8482A power sensor | MY41094127 | DXC-2026-3339-002 | 2026-10-15 | 2027-10-15 | [Sensor calibration, 2 pages](../output/pdf/hp-437b-8482a/calibration/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf) |

DXCONNECTION / Valley Precision Instrument Calibration Services issued both records. Original source filenames, sizes, and SHA-256 hashes are retained in the separate [calibration import manifest](../output/pdf/hp-437b-8482a/calibration/import-manifest.json) and [checksum list](../output/pdf/hp-437b-8482a/calibration/SHA256SUMS.txt). The November 11 source filenames identify the supplied files; the certificates themselves are dated October 15.

Use these records alongside the manuals whenever calibration criteria or correction data are needed. In the meter PDF, page 1 is the certificate, pages 2–3 contain adjustment and calibration checks, and page 4 contains the performance test record with limits and results. In the sensor PDF, page 2 contains the serial-specific frequency/calibration-factor table, the stated 99% reference C.F., and typical calibration-factor measurement uncertainties. Verify values directly against the scanned page before using them; text extraction can misread numbers or table alignment. Record the selected frequency, factor, uncertainty, and source page in any future bench procedure.

One meter-report discrepancy needs clarification before adopting its supply checks as acceptance criteria: PDF page 2 lists **4.498 VDC** for the **+5.0 VDC bus (+/-0.25 V)**, outside the printed tolerance, while the certificate reports a pass. Preserve the report as issued, and confirm this entry with the laboratory rather than silently correcting it or treating it as a verified passing value.

## Using these references

Use the operating manual for front-panel operation, zeroing, meter calibration, frequency correction, and measurements. Use the service manual for troubleshooting and performance verification. Consult the sensor manual and the individual sensor label or certificate for the applicable limits and calibration data.

The original conversation, retained privately in Generic Radio Stuff as `HP-437B-Documentation--6ae604c9-e5d0-83e8-a89f-0f103663e32b.txt`, turns 1–2, contains an assistant quick-start sequence followed by the user's sensor identification. That sequence has not been promoted to a bench procedure. The chat's closing statement that saving was unconfirmed is historical; the local files and verified manifests now establish that the manuals are saved.

The operating and service manuals are scanned. Use the PDFs, with rendering or OCR as needed. Earlier incomplete extractions remain in Generic Radio Stuff and were not copied here.


## Automation work

The [plan](PLAN.md) and [open work](OPEN-WORK.md) are maintained in this project. Sensor-specific calibration factors must come from the individual sensor label or certificate. Serial numbers and individual laboratory calibration records are indexed above. No project bench measurement or automation validation results are recorded yet.
