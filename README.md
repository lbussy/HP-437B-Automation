# HP 437B Automation

Control, finite CSV logging, supervised test workflows, and traceable reports for an HP 437B power meter and 8482A sensor, using a XyphroLabs USBGpib V2 adapter.

## Current equipment

Meter **SN 3125U22346**, certificate **DXC-2026-3340-001**, calibrated November 11, 2026, next due November 11, 2028. The laboratory reports Passed/In Tolerance; its +5 V result is **5.014 V**, within the printed tolerance. The repository stores the owner-selected four-page [calibration PDF](references/calibration/hp-437b/3125U22346/2026-11-11/derived/HP-437B-SN-3125U22346-Calibration-2026-11-11.pdf). The lab lists software **2.0** and HPIB address **13**. The November 23 Mac bench run confirmed firmware 2.0; the front-panel address remains unverified.

Sensor **SN MY41094127** has a recorded **99% reference calibration factor**. The applicable sensor reference factor is 99%. See [equipment and manuals](docs/EQUIPMENT.md) and [current calibration review](docs/validation/CALIBRATION-REVIEW.md) for limits and remaining documentation ambiguities. A [supervised Mac ZERO and 30 m measurement](docs/validation/30M-POWER-20261123.md) recorded 24.500 mW at the sensor input; broader interaction checks remain pending, and laboratory certification does not establish Mac/Pi/backend compatibility.

An additional **8482H sensor, SN 3318A09219**, has a complete [calibration record and review](docs/validation/8482H-CALIBRATION-20261122.md): certificate dated November 15, 2026, due November 15, 2027, and reference factor 99%. Its calibration chart is dated November 15, 2026. The selected measurement sensor is the 8482A SN MY41094127.

## Software

The Python package implements typed commands, serialized acquisition, bounded worker shutdown, finite CSV/sidecar logging, and an explicit synthetic demo. It uses pinned PyVISA/PyVISA-py/PyUSB dependencies. The local operator interface supports supervised POWER REF workflows, guided radio sweeps, explicit ZERO/CAL, reports, saved-run browsing, and optional supplied-limit assessments. WF-04–WF-06 provide synthetic/shared-fake setting, frequency, and supply-voltage workflows; automatic physical DUT drivers are optional.

Human-started tests and deterministic reports are the selected mode. AI/provider automation is deferred. Software implementation and synthetic tests do not establish physical performance or absolute RF accuracy.

## Start here

| Document | Purpose |
| --- | --- |
| [Software](docs/SOFTWARE.md) | Install, test, simulate, and configure logging |
| [Operator interface](docs/workflows/OPERATOR-UI-V1.md) | Launch and use the local interface |
| [Meter preparation](docs/workflows/METER-PREPARATION.md) | Explicit ZERO/CAL and setup configuration |
| [Plan](docs/PLAN.md) / [open work](docs/OPEN-WORK.md) | Current decisions and remaining work |
| [Validation](docs/VALIDATION.md) | Current equipment checks and evidence boundaries |
| [Command inventory](docs/inventory/README.md) | Syntax, software coverage, and guards |
| [Reporting](docs/REPORTING.md) / [run provenance](docs/RUN-PROVENANCE.md) | Evidence-backed results and artifacts |
| [Release checklist](docs/RELEASE-CHECKLIST.md) | Current readiness |
| [Reference library](references/README.md) | Manuals, current calibration records, originals, and derived documents |
| [Reference provenance](docs/PROVENANCE.md) | Current reference files and hashes |
| [Contributing](CONTRIBUTING.md) | Repository conventions |

## Repository layout

- `src/hp437b/`, `tests/`, and `tools/`: package, software tests, and workflow/check tools.
- `docs/`: current requirements, operation, references, and validation specifications.
- [`references/`](references/README.md): publisher manuals, calibration records by model/serial/date, manifests, checksums, and source attribution.
- `tmp/` or `temp/`: ignored scratch files.
- `data/`, `output/logs/`, and `output/reports/`: ignored local evidence and generated artifacts.

Original project work is [MIT-licensed](LICENSE). Publisher manuals and laboratory records retain their own rights; see [third-party notices](THIRD_PARTY_NOTICES.md).
