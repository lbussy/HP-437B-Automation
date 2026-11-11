# Open work

Updated: 2026-11-11. Statuses: ✅ Complete, ⏳ In progress, and ▧ Open. Task identifiers HP-01 and HP-02 are retained from Generic Radio Stuff. The user authorized Phase 3 execution on November 11; the initial batch is supervised Mac identification without a sensor.

| ID | Status | Next result |
| --- | --- | --- |
| SETUP-01 | ✅ Complete | Initial repository structure, copied and verified manuals, migrated plan, and links from the old notes |
| PHASE-01 | ✅ Complete | [Inventory](inventory/README.md):118 command/syntax variants,50 functional families,20 bus entries; review/corrections complete. Source and transport questions remain tracked for later phases |
| PHASE-02 | ✅ Complete | [Software milestone](SOFTWARE.md): 78 command/syntax variants implemented and software-tested, 40 guarded/deferred; [review record](PHASE-2-REVIEW.md) links evidence and follow-ups |
| PHASE-03 | ⏳ In progress | Execute the [batch plan](validation/PHASE-3-PLAN.md), retain [Mac results](validation/MAC-20261111.md), and qualify the replacement/sensor on both hosts |
| HP-01 | ▧ Open | Seller/calibrator confirmed the +5 V discrepancy was unacceptable, per the user's November 11 report; user plans an exchange after a few development steps. Record replacement identity and calibration records, then derive a bench procedure, select applicable sensor factors, and record the measurement setup |
| HP-02 | ⏳ In progress | XyphroLabs GpibUsb `03eb:2065` detected on Mac; initial Python identification returned 437B firmware 1.8. Complete raw framing, recovery, control, and logging evidence; adapter firmware/revision remain unknown |
| DEC-01 | ✅ Complete | First batch: MacBook Pro Mac17,8, M5 Pro, ARM64, macOS 27.0.1. Pi identity/access remain P3-PI prerequisites |
| DEC-02 | ▧ Open | Define initial measurement sequence, interval, duration, units, averaging/range policy, and CSV fields |
| LOCAL-01 | ✅ Complete | [Corrected automatic cleanup](validation/AUTOMATIC-LOCAL.md) sends TR3 then GTL; independent status/display and owner checks pass after reproducing P3-R10. Failed/uncertain transfers retain manual recovery; replacement/Pi repetition remains PHASE-03 |
| SUSTAIN-01 | ⏳ In progress | [Five-minute Mac reference logging](validation/MAC-20261111-SUSTAINED.md): data/metadata checks passed, 299 valid rows, final owner live-display/source-off confirmation pending |
| VAL-01 | ⏳ In progress | Mac identification and [reference readback/display agreement](validation/MAC-20261111-REFERENCE.md) passed in scoped batches; [three-row reference logging](validation/MAC-20261111-SHORT-LOG.md) also passed; sustained-run data checks also passed, with final owner restoration confirmation pending; reversible control, recovery, replacement, and second-host acceptance remain pending |

The [decision register](PLAN.md#decision-register) distinguishes user requirements from proposed choices. The Python interface/logger has source-derived software tests and installed-package checks. Physical acceptance and measured rates follow the separate Mac/Pi qualification plan.

The user intends to do a few development steps with the current meter before exchanging it; the initial identification step used no sensor, followed by a [connected-sensor baseline](validation/MAC-20261111-BASELINE.md) with POWER REF off. Associate any resulting observations with the current serial number and known supply discrepancy, and validate the replacement separately.

See the [release checklist](RELEASE-CHECKLIST.md) for the three-phase sequence and release-readiness summary.

Phase 1 follow-ups: resolve [A01–A09](inventory/AMBIGUITIES.md) as needed for Phase 2 capabilities; use the [coverage matrix](inventory/COVERAGE.md) for per-capability implementation and qualification.

Phase 2 follow-ups: resolve guarded source ambiguities and the released-backend bus gaps; full device command coverage remains tracked in the matrix.
