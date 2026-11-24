# Reference provenance

The [reference library](../references/README.md) contains publisher manuals and serial-specific calibration records. The [equipment index](EQUIPMENT.md) identifies the applicable manuals, meter, and sensors.

## Publisher manuals

The manuals are unmodified publisher PDFs. The [download manifest](../references/manuals/download-manifest.json) records editions, publisher URLs, sizes, and SHA-256 hashes. The [checksum list](../references/manuals/SHA256SUMS.txt) identifies the manual files.

## Calibration records

| Equipment | Document | Source metadata | Checksums |
| --- | --- | --- | --- |
| HP 437B SN 3125U22346 | [Four-page derived calibration record](../references/calibration/hp-437b/3125U22346/2026-11-11/derived/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf) | [Manifest](../references/calibration/hp-437b/3125U22346/2026-11-11/derived/import-manifest.json) | [SHA-256](../references/calibration/hp-437b/3125U22346/2026-11-11/derived/SHA256SUMS.txt) |
| Agilent 8482A SN MY41094127 | [Complete certificate and chart](../references/calibration/hp-8482a/MY41094127/2026-10-15/originals/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf) | [Manifest](../references/calibration/hp-8482a/MY41094127/2026-10-15/originals/import-manifest.json) | [SHA-256](../references/calibration/hp-8482a/MY41094127/2026-10-15/originals/SHA256SUMS.txt) |
| Agilent 8482H SN 3318A09219 | [Two-page derived certificate and chart record](../references/calibration/hp-8482h/3318A09219/2026-11-15/derived/HP-8482H-SN-3318A09219-Calibration-2026-11-15.pdf) | [Manifest](../references/calibration/hp-8482h/3318A09219/2026-11-15/import-manifest.json) | [SHA-256](../references/calibration/hp-8482h/3318A09219/2026-11-15/SHA256SUMS.txt) |

The complete [8482H calibration chart](../references/calibration/hp-8482h/3318A09219/2026-11-15/originals/HP-8482H-SN-3318A09219-Calibration-Chart-2026-11-15.pdf) is available separately. Manifests provide document identity, source-page attribution, byte counts, and hashes. Publisher PDFs, supplied source documents, manifests, and checksum lists retain their exact recorded bytes.

## Verification

The [source index](../references/relocation-index.json) associates source identities and hashes with repository paths. The [library checksum list](../references/SHA256SUMS.txt) covers all seven PDFs. Run `python tools/check_docs.py` from the repository root to verify links, retained file identities, and checksum entries.

Sensor-correction receipts identify the certificate, page, serial number, frequency, factor calculation, and source hash. Import validation checks the complete receipt against the serial-specific correction profile. Sealed measurement evidence and report packages retain their recorded provenance.

File integrity does not establish equipment performance. Record limitations are in the [meter calibration review](validation/CALIBRATION-REVIEW.md) and [8482H calibration review](validation/8482H-CALIBRATION-20261122.md). Measurement-run evidence is governed by [run provenance](RUN-PROVENANCE.md) and [validation](VALIDATION.md).
