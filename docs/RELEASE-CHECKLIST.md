# Release checklist

Updated: 2026-11-11. Work proceeds through inventory, implementation, and qualification. The [open-work register](OPEN-WORK.md) owns detailed task status; this checklist summarizes release readiness and links execution prompts.

| Item | Status | Completion result or next action |
| --- | --- | --- |
| Repository setup | ✅ Complete | Project structure, manuals, provenance, and public GitHub repository established |
| Phase 1: Inventory | ▧ Not started | Catalog every documented command variant and required GPIB operation; produce source-verified references and a coverage matrix. [Prepared execution prompt](prompts/phase-1-command-inventory.md) |
| Phase 2: Implement | ▧ Not started | Build the Python interface in batches, beginning with basic power logging; use the inventory to track complete command coverage |
| Phase 3: Qualify | ▧ Not started | Bench-verify required capabilities through the adapter/backend on Mac and Pi, with recorded results and limitations |
| HP-01: Equipment readiness | ▧ Awaiting replacement | Record replacement meter identity and calibration records, derive the bench procedure, and establish applicable sensor factors and measurement setup |
| HP-02: Adapter readiness | ▧ Awaiting adapter | Confirm adapter arrival, identity, firmware, and cabling for control and logging |
| DEC-01: Initial host | ▧ Open | Choose Mac or Pi first and record host architecture/model and OS |
| DEC-02: Measurement and logging settings | ▧ Open | Define initial sequence, interval, duration, units, averaging/range policy, and CSV fields |
| VAL-01: Backend acceptance | ▧ Not started | Qualify provisional PyVISA-py against the [hardware validation plan](VALIDATION.md) |

The Phase 1 prompt is prepared for a separate execution request. Implementation and qualification can proceed in reviewed batches using the same coverage matrix. Current-meter observations must retain the unit identity and documented supply discrepancy; qualify the replacement separately.
