# Project provenance

Created November 9, 2026 after the user moved the chat into HP 437B Automation and requested repository setup, copied manuals, and redirects from Generic Radio Stuff.

## Imported references and planning

The three publisher PDFs, original `download-manifest.json`, and `SHA256SUMS.txt` were copied byte for byte from the sibling Generic Radio Stuff checkout. The PDFs were compared against source bytes and checked against the publisher-download SHA-256 list. The old copies remain intact. The original download manifest retains its historical project/storage fields; it has not been rewritten to describe this migration.

The separate [import manifest](import-manifest.json) records source paths, sizes, and checksums for all five copied files and a hash of the planning source before migration. The active plan and decision register were transferred into [PLAN.md](PLAN.md); manual context is maintained in [EQUIPMENT.md](EQUIPMENT.md). No exported chats, account-export material, or OCR artifacts were imported.

The HP topic note in the private Generic Radio Stuff checkout, `docs/topics/hp-437b-8482a.md`, directs automation work here. The public project is [lbussy/HP-437B-Automation](https://github.com/lbussy/HP-437B-Automation), with `devel` as its initial default branch.

## Owner-supplied calibration records

On November 11, 2026, the owner supplied complete calibration PDFs for 437B SN 3125U33223 and 8482A SN MY41094127 and explicitly requested storage, commit, and push. They were copied byte for byte into `output/pdf/hp-437b-8482a/calibration/`, visually inspected, and compared with the supplied originals. The separate [calibration import manifest](../output/pdf/hp-437b-8482a/calibration/import-manifest.json) records original filenames, sizes, SHA-256 hashes, and certificate identifiers. The original manual manifests remain unchanged. See [equipment references](EQUIPMENT.md#individual-calibration-records) for certificate dates, page references, and evidence limits.

## Evidence limits

Reference copying and repository checks establish file integrity, not equipment performance. There is no recorded adapter purchase, bench connection, software implementation, host qualification, or RF transmission in this project. Pricing, availability, and software claims preserved in the plan are dated discussion findings and must be rechecked before consequential use.
