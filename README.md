# HP 437B Automation

Automated control and power logging for an HP 437B power meter and HP 8482A sensor, using a Mac or Raspberry Pi and a proposed XyphroLabs USBGpib V2 adapter.

## Status

Phase 2 software milestone completed November 11, 2026. The Python package provides typed command encoding, serialized control, a finite CSV logger, and an explicit synthetic demo. Software coverage includes 78 command/syntax variants; 40 source-ambiguous variants have explicit guards. [Phase 3 qualification](docs/validation/PHASE-3-PLAN.md) is in progress. This Mac detects the adapter, and an initial Python identification returned HP 437B firmware 1.8; raw-frame capture and local restoration are tracked in the [run record](docs/validation/MAC-20261111.md). The sensor is now connected with POWER REF off; one [baseline TR2/read and status sequence](docs/validation/MAC-20261111-BASELINE.md) succeeded. Owner-assisted zero/CAL preparation was followed by a [reference-on Python/display comparison](docs/validation/MAC-20261111-REFERENCE.md): both read 0.988 mW, and the owner confirmed RMT/reference off afterward. A [three-row reference CSV session](docs/validation/MAC-20261111-SHORT-LOG.md) also passed with approximately one-second sample spacing. [Automatic return to local](docs/validation/AUTOMATIC-LOCAL.md) now sends explicit TR3 free-run followed by GTL after healthy sessions with the identified adapter on this Mac; identification and logger cleanup were verified without PRESET/LOCAL. [Five-minute reference logging](docs/validation/MAC-20261111-SUSTAINED.md) produced 299 valid rows with passing data/timing checks; the owner confirmed live readings and RMT/reference off without PRESET/LOCAL. [Reversible W/dBm control and remote reference switching](docs/validation/MAC-20261111-CONTROL.md) also passed, ending reference off and live local. [Between-read interruption and one induced timeout/manual USB-reconnect recovery](docs/validation/FAILURE-RECOVERY.md) passed. [Pi qualification](docs/validation/PI-QUALIFICATION.md) now records 237 software tests, ordinary-user USB identification/control, three-row and five-minute reference logs (300 valid sustained rows), and matching retrieved CSV/sidecar hashes. The owner-authorized permanent USB access rule and setup instructions are included. Pi display comparison, interruption/timeout handling, and an expanded manual LOCAL/Mac-host-assisted recovery passed. Post-timeout USB-only reconnect failed on Pi; the manual and software-only shutdown routes below have separate acceptance records. Root cause, unattended recovery, and replacement qualification remain unresolved.

The [Pi-only recovery investigation](docs/validation/PI-ONLY-RECOVERY.md) is in progress. USB port reset remains unqualified, and USBTMC clear passed healthy checks but failed after a timeout. The experimental clear helper has 18 targeted tests; its bus/CLI recovery path remains guarded. A [manual full-adapter USB+GPIB isolation/reconnect](docs/validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) now passed on Pi, followed by fresh protocol and owner live/local checks, without Mac or Pi reboot. Repair of an already wedged adapter and the cause remain unresolved. The subsequent [integrated failed-read shutdown fix](docs/validation/PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) passed 261 local/Pi software tests, ordinary installed CLI logging, one real forced timeout with complete backend abort, and fresh communication without cable recovery. Only failed-read shutdown gains up to one second; successful logging, defaults, CLI, and CSV stay unchanged. The owner confirmed final live readings, RMT off, and reference off. The matching [Mac verification](docs/validation/MAC-FAILED-READ-SHUTDOWN.md) subsequently passed ordinary logging, the original forced timeout with complete abort, fresh acquisition/free-run, and owner final-state confirmation. This named shutdown route is verified on both hosts with the current unit; replacement acceptance and unattended recovery remain open.

Equipment update, November 11: the user reports that the seller/calibrator confirmed the current meter's [+5 V supply discrepancy](docs/EQUIPMENT.md#individual-calibration-records) was unacceptable. An exchange is planned after a few development steps with this unit. Replacement receipt and qualification remain pending.

The [adapter-internal USB query](docs/validation/ADAPTER-IDENTIFICATION.md) now confirms adapter-reported firmware **V2.4**. The USB serial string's 1.8 is the meter firmware; the owner reports an Anker USB-C cable, meter GPIB address 13 read from the front panel, and no hardware-revision marking. Exact PCB revision is retained as an accepted metadata limitation, not a Phase 3 blocker.

Available [Phase 3 pre-arrival preparation](docs/validation/PRE-ARRIVAL-REVIEW.md) is complete: adapter readiness, the owner-selected [initial logging policy](docs/validation/MEASUREMENT-POLICY.md), evidence/matrix reconciliation, and a [replacement acceptance procedure](docs/validation/REPLACEMENT-ACCEPTANCE.md). Final Phase 3 acceptance still requires the arriving meter and actual sensor on both hosts.

## Start here

| Document | Purpose |
| --- | --- |
| [Plan and decision register](docs/PLAN.md) | Requirements, adapter recommendation, software candidate, unresolved decisions, and steps to resume |
| [Open work](docs/OPEN-WORK.md) | Task status and next results |
| [Initial measurement policy](docs/validation/MEASUREMENT-POLICY.md) | Adopted W/automatic-range/filter/one-second-request/five-minute profile and limits |
| [Replacement procedure](docs/validation/REPLACEMENT-ACCEPTANCE.md) | Arrival gates, both-host physical cases, budgets, restoration, and final acceptance |
| [Release checklist](docs/RELEASE-CHECKLIST.md) | Three-phase readiness and prepared execution prompts |
| [Software usage](docs/SOFTWARE.md) | Installation, API/CLI, output schema, guards, and recovery |
| [Phase 2 review](docs/PHASE-2-REVIEW.md) | Implementation evidence, adversarial corrections, and deferred coverage |
| [Capability inventory](docs/inventory/README.md) | Command and bus references, coverage matrix, source ambiguities, and review results |
| [Equipment and manuals](docs/EQUIPMENT.md) | Official manuals, serial-specific calibration records, and operating references |
| [Hardware validation](docs/VALIDATION.md) | Evidence required before claiming control or unattended logging support |
| [Project provenance](docs/PROVENANCE.md) | Migration from Generic Radio Stuff and manual verification |
| [Contributing](CONTRIBUTING.md) | Repository conventions and review checks |

## Proposed operation

Python logger → PyVISA → PyVISA-py → PyUSB/libusb → USBGpib V2 → HP 437B

The Pi could remain beside the meter and write timestamped CSV files, with the Mac used for network access and retrieval. Direct USB operation on the Mac is another option. Both hosts are selected, and the initial measurement sequence/settings are adopted in DEC-02; actual replacement qualification remains pending.

The adapter transports the meter's original HP commands. Validate read/write support and the required triggering, status checks, and recovery on each host.

## Repository layout

- `docs/`: maintained requirements, decisions, references, backlog, and validation plan.
- `output/pdf/hp-437b-8482a/`: unmodified publisher manuals and their original download manifest/checksums; `calibration/` holds complete individual calibration records and separate import checksums.
- `.github/`: issue and pull request templates.
- `tmp/` or `temp/`: ignored scratch files and previews.
- `data/`, `output/logs/`, and `output/reports/`: ignored local measurement/generated output locations when needed.

The installable package lives under `src/hp437b/`, software tests under `tests/`, and the pinned development environment in `requirements-dev.lock`. See [software usage](docs/SOFTWARE.md) for checks and the hardware-free demo.

## Licensing

Original work owned by lbussy is [MIT-licensed](LICENSE). Publisher manuals and third-party calibration records retain their original rights and are excluded from that grant; see [third-party notices](THIRD_PARTY_NOTICES.md).
