# Open work

Updated: 2026-11-11. Task identifiers HP-01 and HP-02 are retained from Generic Radio Stuff. Planning and repository setup do not authorize hardware purchases, transmission, or implementation of the logger.

| ID | Status | Next result |
| --- | --- | --- |
| SETUP-01 | ✅ Complete | Initial repository structure, copied and verified manuals, migrated plan, and links from the old notes |
| PHASE-01 | ▧ Not started | Complete the command and GPIB inventory using the [prepared execution prompt](prompts/phase-1-command-inventory.md); execution awaits a separate request |
| PHASE-02 | ▧ Not started | Implement the Python interface in batches, starting with basic power logging |
| PHASE-03 | ▧ Not started | Qualify capabilities on each intended host using the coverage matrix and recorded bench evidence |
| HP-01 | ▧ Awaiting replacement | Seller/calibrator confirmed the +5 V discrepancy was unacceptable, per the user's November 11 report; user plans an exchange after a few development steps. Record replacement identity and calibration records, then derive a bench procedure, select applicable sensor factors, and record the measurement setup |
| HP-02 | ▧ Awaiting adapter | Confirm adapter arrival; establish and validate control and logging on the selected host |
| DEC-01 | ▧ Open | Choose first host and record Mac architecture/macOS or Pi model/OS |
| DEC-02 | ▧ Open | Define initial measurement sequence, interval, duration, units, averaging/range policy, and CSV fields |
| VAL-01 | ▧ Not started | Qualify the provisional backend against the [hardware validation plan](VALIDATION.md) |

The [decision register](PLAN.md#decision-register) distinguishes user requirements from proposed choices. There is no application implementation, dependency installation, bench qualification, or measured sampling rate yet. Hardware validation is required separately for Mac and Pi support.

The user intends to do a few development steps with the current meter before exchanging it; those steps have not yet been specified. Associate any resulting observations with the current serial number and known supply discrepancy, and validate the replacement separately.

See the [release checklist](RELEASE-CHECKLIST.md) for the three-phase sequence and release-readiness summary.
