# Open work

Updated: 2026-11-11. Statuses: ✅ Complete, ⏳ In progress, and ▧ Open. Task identifiers HP-01 and HP-02 are retained from Generic Radio Stuff. The user authorized Phase 2 software execution; physical qualification remains Phase 3 work.

| ID | Status | Next result |
| --- | --- | --- |
| SETUP-01 | ✅ Complete | Initial repository structure, copied and verified manuals, migrated plan, and links from the old notes |
| PHASE-01 | ✅ Complete | [Inventory](inventory/README.md):118 command/syntax variants,50 functional families,20 bus entries; review/corrections complete. Source and transport questions remain tracked for later phases |
| PHASE-02 | ✅ Complete | [Software milestone](SOFTWARE.md): 78 command/syntax variants implemented and software-tested, 40 guarded/deferred; [review record](PHASE-2-REVIEW.md) links evidence and follow-ups |
| PHASE-03 | ▧ Open | Qualify capabilities on each intended host using the coverage matrix and recorded bench evidence |
| HP-01 | ▧ Open | Seller/calibrator confirmed the +5 V discrepancy was unacceptable, per the user's November 11 report; user plans an exchange after a few development steps. Record replacement identity and calibration records, then derive a bench procedure, select applicable sensor factors, and record the measurement setup |
| HP-02 | ▧ Open | Confirm adapter arrival; establish and validate control and logging on the selected host |
| DEC-01 | ▧ Open | Choose first host and record Mac architecture/macOS or Pi model/OS |
| DEC-02 | ▧ Open | Define initial measurement sequence, interval, duration, units, averaging/range policy, and CSV fields |
| VAL-01 | ▧ Open | Qualify the provisional backend against the [hardware validation plan](VALIDATION.md) |

The [decision register](PLAN.md#decision-register) distinguishes user requirements from proposed choices. The Python interface/logger has source-derived software tests and installed-package checks. Physical acceptance and measured rates follow the separate Mac/Pi qualification plan.

The user intends to do a few development steps with the current meter before exchanging it; those steps have not yet been specified. Associate any resulting observations with the current serial number and known supply discrepancy, and validate the replacement separately.

See the [release checklist](RELEASE-CHECKLIST.md) for the three-phase sequence and release-readiness summary.

Phase 1 follow-ups: resolve [A01–A09](inventory/AMBIGUITIES.md) as needed for Phase 2 capabilities; use the [coverage matrix](inventory/COVERAGE.md) for per-capability implementation and qualification.

Phase 2 follow-ups: resolve guarded source ambiguities and the released-backend bus gaps; full device command coverage remains tracked in the matrix.
