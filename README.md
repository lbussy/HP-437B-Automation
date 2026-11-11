# HP 437B Automation

Automated control and power logging for an HP 437B power meter and HP 8482A sensor, using a Mac or Raspberry Pi and a proposed XyphroLabs USBGpib V2 adapter.

## Status

Planning and repository setup, November 9, 2026. The proposed stack is Python, PyVISA, and PyVISA-py. Next, choose the initial host and logging settings, then validate adapter communication and backend compatibility on the bench.

Equipment update, November 11: the user reports that the seller/calibrator confirmed the current meter's [+5 V supply discrepancy](docs/EQUIPMENT.md#individual-calibration-records) was unacceptable. An exchange is planned after a few development steps with this unit. Replacement receipt and qualification remain pending.

## Start here

| Document | Purpose |
| --- | --- |
| [Plan and decision register](docs/PLAN.md) | Requirements, adapter recommendation, software candidate, unresolved decisions, and steps to resume |
| [Open work](docs/OPEN-WORK.md) | Task status and next results |
| [Equipment and manuals](docs/EQUIPMENT.md) | Official manuals, serial-specific calibration records, and operating references |
| [Hardware validation](docs/VALIDATION.md) | Evidence required before claiming control or unattended logging support |
| [Project provenance](docs/PROVENANCE.md) | Migration from Generic Radio Stuff and manual verification |
| [Contributing](CONTRIBUTING.md) | Repository conventions and review checks |

## Proposed operation

Python logger → PyVISA → PyVISA-py → PyUSB/libusb → USBGpib V2 → HP 437B

The Pi could remain beside the meter and write timestamped CSV files, with the Mac used for network access and retrieval. Direct USB operation on the Mac is another option. The first host, measurement sequence, and logging settings remain open decisions.

The adapter transports the meter's original HP commands. Validate read/write support and the required triggering, status checks, and recovery on each host.

## Repository layout

- `docs/`: maintained requirements, decisions, references, backlog, and validation plan.
- `output/pdf/hp-437b-8482a/`: unmodified publisher manuals and their original download manifest/checksums; `calibration/` holds complete individual calibration records and separate import checksums.
- `.github/`: issue and pull request templates.
- `tmp/` or `temp/`: ignored scratch files and previews.
- `data/`, `output/logs/`, and `output/reports/`: ignored local measurement/generated output locations when needed.

Add source, tests, package metadata, dependency pins, and automation when implementation is requested and requirements are settled.

## Licensing

Original work owned by lbussy is [MIT-licensed](LICENSE). Publisher manuals and third-party calibration records retain their original rights and are excluded from that grant; see [third-party notices](THIRD_PARTY_NOTICES.md).
