# Release checklist

Updated: 2026-11-11. Statuses: ✅ Complete, ⏳ In progress, and ▧ Open. Work proceeds through inventory, implementation, and qualification. The [open-work register](OPEN-WORK.md) owns detailed task status; this checklist summarizes release readiness and links execution prompts.

| Item | Status | Completion result or next action |
| --- | --- | --- |
| Repository setup | ✅ Complete | Project structure, manuals, provenance, and public GitHub repository established |
| Phase 1: Inventory | ✅ Complete | [Reference and matrix](inventory/README.md): 118 command/syntax variants in 50 functional families and 20 bus entries. [Review](inventory/REVIEW.md) records corrections and remaining source questions; [execution prompt](prompts/phase-1-command-inventory.md) retained |
| Phase 2: Implement | ✅ Complete | [Software milestone and limits](SOFTWARE.md): 78 command/syntax variants implemented/tested; 40 explicitly deferred; [review](PHASE-2-REVIEW.md). [Execution prompt](prompts/phase-2-implementation.md) retained |
| Phase 3: Qualify | ⏳ In progress | Bench-verify required capabilities through the adapter/backend on Mac and Pi, with recorded results and limitations; [qualification prompt](prompts/phase-3-qualification.md) execution started November 11; [batch plan](validation/PHASE-3-PLAN.md) and [Mac results](validation/MAC-20261111.md) |
| HP-01: Equipment readiness | ▧ Open | Await the replacement, record its identity and calibration records, derive the bench procedure, and establish applicable sensor factors and measurement setup |
| HP-02: Adapter readiness | ⏳ In progress | Adapter detected and initial Python identification returned HP 437B firmware 1.8; adapter firmware/revision, control, and logging qualification remain pending |
| DEC-01: Initial host | ✅ Complete | Mac first: MacBook Pro Mac17,8, M5 Pro, ARM64, macOS 27.0.1; Pi prerequisites tracked separately |
| DEC-02: Measurement and logging settings | ▧ Open | Define initial sequence, interval, duration, units, averaging/range policy, and CSV fields |
| VAL-01: Backend acceptance | ⏳ In progress | Initial Mac identification recorded; qualify remaining requirements against the [hardware validation plan](VALIDATION.md) |

Phase 1 documentation is complete with source/transport ambiguities explicitly tracked for later evidence. Implementation and qualification can proceed in reviewed batches using the same coverage matrix. Current-meter observations must retain the unit identity and documented supply discrepancy; qualify the replacement separately.

Phase 2 software delivery is complete with deferred capabilities tracked explicitly. Phase 3 will establish physical compatibility and measured behavior.
