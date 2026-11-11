# Release checklist

Updated: 2026-11-11. Statuses: ✅ Complete, ⏳ In progress, and ▧ Open. Work proceeds through inventory, implementation, and qualification. The [open-work register](OPEN-WORK.md) owns detailed task status; this checklist summarizes release readiness and links execution prompts.

| Item | Status | Completion result or next action |
| --- | --- | --- |
| Repository setup | ✅ Complete | Project structure, manuals, provenance, and public GitHub repository established |
| Phase 1: Inventory | ✅ Complete | [Reference and matrix](inventory/README.md): 118 command/syntax variants in 50 functional families and 20 bus entries. [Review](inventory/REVIEW.md) records corrections and remaining source questions; [execution prompt](prompts/phase-1-command-inventory.md) retained |
| Phase 2: Implement | ✅ Complete | [Software milestone and limits](SOFTWARE.md): 78 command/syntax variants implemented/tested; 40 explicitly deferred; [review](PHASE-2-REVIEW.md). [Execution prompt](prompts/phase-2-implementation.md) retained |
| Phase 3: Qualify | ⏳ In progress | Bench-verify required capabilities through the adapter/backend on Mac and Pi, with recorded results and limitations; [qualification prompt](prompts/phase-3-qualification.md) execution started November 11; [batch plan](validation/PHASE-3-PLAN.md) and [Mac results](validation/MAC-20261111.md) |
| HP-01: Equipment readiness | ▧ Open | Await the replacement, record its identity and calibration records, derive the bench procedure, and establish applicable sensor factors and measurement setup |
| HP-02: Adapter readiness | ⏳ In progress | Current Mac/unit identification, reversible control, reference logging, corrected local cleanup, and named interruption/manual-recovery checks passed; adapter revision/firmware, Pi, and replacement acceptance remain pending |
| DEC-01: Initial host | ✅ Complete | Mac first: MacBook Pro Mac17,8, M5 Pro, ARM64, macOS 27.0.1; Pi 5/Debian 13.7 prepared; per-case results tracked separately |
| DEC-02: Measurement and logging settings | ▧ Open | Reference-test policies are recorded; define the final measurement/application policy, including range/filter, interval, and duration |
| VAL-01: Backend acceptance | ⏳ In progress | Scoped current-Mac batches passed, including [interruption and manual timeout recovery](validation/FAILURE-RECOVERY.md); complete Pi/replacement qualification and preserve unattended/bus exclusions |

Phase 1 documentation is complete with source/transport ambiguities explicitly tracked for later evidence. Implementation and qualification can proceed in reviewed batches using the same coverage matrix. Current-meter observations must retain the unit identity and documented supply discrepancy; qualify the replacement separately.

Phase 2 software delivery is complete with deferred capabilities tracked explicitly. Phase 3 will establish physical compatibility and measured behavior.

Current-unit Mac batches: identification/readback, reversible W/dBm control, remote reference switching, finite/five-minute logging, corrected TR3/local restoration, between-read SIGINT, and one real short-deadline timeout with operator USB-reconnect recovery passed. These are version/setup-scoped physical observations; unattended recovery, other fault patterns, Pi, and replacement acceptance are not implied.

[Pi software preflight](validation/PI-QUALIFICATION.md) passed on Raspberry Pi 5/aarch64 Debian 13.7 with the isolated pinned stack, 237 tests, lint/format/build, CLI checks, and libusb loading. Pi identification/owner local confirmation, baseline/control, three-row and five-minute logging (300 valid sustained rows), and CSV/sidecar retrieval passed after the owner-authorized permanent access rule; Pi display comparison (0.989 mW), between-read interruption, and timeout/uncertainty handling passed; initial Pi-only reconnect failed enumeration; expanded LOCAL/Mac-host-assisted Pi protocol recovery passed, with owner final live/local/reference-off confirmation. Root cause/Pi-only recovery remain unresolved; Phase 3 remains in progress.

[Manual Pi-only recovery](validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) passed once using full adapter USB+GPIB isolation/reconnect, fresh protocol/free-run checks, and owner final live/local/reference-off confirmation, with no Mac move or Pi reboot. This closes Mac dependence for that supervised route; software-only recovery, cause/latency/repeatability, adapter firmware/revision, replacement, and final application policy remain open. Phase 3 stays in progress.
