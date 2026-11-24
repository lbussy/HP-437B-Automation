# Reference library

Permanent publisher manuals and individual calibration records live here. Generated measurement reports remain under `output/reports/`; local acquisition evidence remains outside this library.

## Publisher manuals

| Document | Publisher part number | File |
| --- | --- | --- |
| HP 437B operating manual | 00437-90047 | [Operating manual](manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf) |
| HP 437B service manual | 00437-90076 | [Service manual](manuals/hp-437b/HP-437B-Service-Manual-00437-90076.pdf) |
| 8480 Series operating and service manual, covering 8482A | 08481-90173 | [Sensor manual](manuals/hp-8480-series/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf) |

The manuals are unmodified publisher PDFs. The preserved [download manifest](manuals/download-manifest.json) and [original checksum list](manuals/SHA256SUMS.txt) cover all three manuals. The source index associates manifest entries with repository paths.

## Current calibration records

Folders are organized by model, serial number, and calibration date. Dates identify the calibration event rather than the import date. These records do not select a sensor, change instrument settings, or establish present measurement accuracy.

| Equipment | Serial number | Calibration date | Current document | Supporting record |
| --- | --- | --- | --- | --- |
| HP 437B | 3125U22346 | 2026-11-11 | [Four-page calibration record](calibration/hp-437b/3125U22346/2026-11-11/derived/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf) | [Preserved manifest](calibration/hp-437b/3125U22346/2026-11-11/derived/import-manifest.json), [review](../docs/validation/CALIBRATION-REVIEW.md) |
| Agilent 8482A | MY41094127 | 2026-10-15 | [Original certificate and chart](calibration/hp-8482a/MY41094127/2026-10-15/originals/HP-8482A-SN-MY41094127-Calibration-2026-10-15.pdf) | [Preserved manifest](calibration/hp-8482a/MY41094127/2026-10-15/originals/import-manifest.json), [review](../docs/validation/CALIBRATION-REVIEW.md) |
| Agilent 8482H | 3318A09219 | 2026-11-15 | [Certificate and calibration chart](calibration/hp-8482h/3318A09219/2026-11-15/derived/HP-8482H-SN-3318A09219-Calibration-2026-11-15.pdf) | [Preserved assembly manifest](calibration/hp-8482h/3318A09219/2026-11-15/import-manifest.json), [review](../docs/validation/8482H-CALIBRATION-20261122.md) |

Within each event, `originals/` contains complete supplied source documents, and `derived/` contains the current calibration records with source attribution in their manifests.

The HP 437B calibration record has four pages. The Agilent 8482A record has two pages. The Agilent 8482H record has two pages, with its [complete calibration chart](calibration/hp-8482h/3318A09219/2026-11-15/originals/HP-8482H-SN-3318A09219-Calibration-Chart-2026-11-15.pdf) available separately.

## Software correction data

The machine-readable 8482A calibration profile is currently embedded in [sensor_correction.py](../src/hp437b/sensor_correction.py), rather than stored as a separate data file. It contains the 14 certificate-derived frequency/factor pairs, sensor serial number, reference factor, source page/hash, and interpolation rules. The selected profile is specific to MY41094127; the 8482H review records its factors but does not provide an active software correction profile.

## Preservation and verification

The [source index](relocation-index.json) records source identities, repository paths, sizes, and SHA-256 hashes. The 15 retained PDFs, manifests, and original checksum lists retain their exact recorded bytes. The library contains seven PDFs.

Run the complete link, file-integrity, and checksum check from the repository root:

```bash
python tools/check_docs.py
```

For a direct check of the seven PDFs:

```bash
cd references
shasum -a 256 -c SHA256SUMS.txt
```

The library [SHA256SUMS.txt](SHA256SUMS.txt) uses repository-library paths. Original checksum lists and manifests identify their source files through the source index. Calibration receipts include source hashes, and sealed captures retain their recorded provenance.

See [equipment and setup](../docs/EQUIPMENT.md), [reference provenance](../docs/PROVENANCE.md), [validation scope](../docs/VALIDATION.md), and [third-party notices](../THIRD_PARTY_NOTICES.md). Keep source documents unchanged and store derived documents separately.
