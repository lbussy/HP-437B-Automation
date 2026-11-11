# Release checklist

Updated: 2026-11-11. Statuses: ✅ Complete, ⏳ In progress, and ▧ Open. Work proceeds through inventory, implementation, and qualification. The [open-work register](OPEN-WORK.md) owns detailed task status; this checklist summarizes release readiness and links execution prompts.

| Item | Status | Completion result or next action |
| --- | --- | --- |
| Repository setup | ✅ Complete | Project structure, manuals, provenance, and public GitHub repository established |
| Phase 1: Inventory | ✅ Complete | [Reference and matrix](inventory/README.md): 118 command/syntax variants in 50 functional families and 20 bus entries. [Review](inventory/REVIEW.md) records corrections and remaining source questions; [execution prompt](prompts/phase-1-command-inventory.md) retained |
| Phase 2: Implement | ▧ Open | Build the Python interface in batches, beginning with basic power logging; track complete coverage. [Prepared implementation prompt](prompts/phase-2-implementation.md) |
| Phase 3: Qualify | ▧ Open | Bench-verify required capabilities through the adapter/backend on Mac and Pi, with recorded results and limitations |
| HP-01: Equipment readiness | ▧ Open | Await the replacement, record its identity and calibration records, derive the bench procedure, and establish applicable sensor factors and measurement setup |
| HP-02: Adapter readiness | ▧ Open | Await the adapter, confirm arrival, identity, firmware, and cabling for control and logging |
| DEC-01: Initial host | ▧ Open | Choose Mac or Pi first and record host architecture/model and OS |
| DEC-02: Measurement and logging settings | ▧ Open | Define initial sequence, interval, duration, units, averaging/range policy, and CSV fields |
| VAL-01: Backend acceptance | ▧ Open | Qualify provisional PyVISA-py against the [hardware validation plan](VALIDATION.md) |

Phase 1 documentation is complete with source/transport ambiguities explicitly tracked for later evidence. Implementation and qualification can proceed in reviewed batches using the same coverage matrix. Current-meter observations must retain the unit identity and documented supply discrepancy; qualify the replacement separately.

The Phase 2 implementation prompt is saved for a separate execution request.
