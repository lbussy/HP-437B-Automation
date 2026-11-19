# Current plan

Updated: November 19, 2026. The [project scope](PROJECT-SCOPE.md) governs development.

## Decision register

| Item | Current decision |
| --- | --- |
| Operating mode | Human-started measurement and deterministic reporting; AI/provider automation deferred |
| Instrument/backend | HP 437B with USBGpib V2 and pinned open-source PyVISA/PyVISA-py/PyUSB stack |
| Hosts | Mac and Raspberry Pi; current-meter interaction checks required before claiming scoped host support |
| Measurement profile | Supervised internal-reference/readback profile in the [measurement policy](validation/MEASUREMENT-POLICY.md); explicit options preserve logger defaults |
| Equipment | Meter SN 3125U22346 and sensor SN MY41094127; [current records](EQUIPMENT.md) |
| Hardware scope | Relevant checks when equipment/operations are used; no blanket software-development gate |
| Reporting | Traceable saved evidence, descriptive statistics, optional attributed criteria, PDF/portable delivery |
| DUT control | Human-guided operation supported; automatic transmitter/supply drivers optional |

## Implemented capabilities

The typed command interface, bounded logger/transport, synthetic demos, provenance, analysis/reporting, WF-01–WF-03 reference runners, combined reference suites, saved-data reporting/history/comparison, supplied-limit assessments, profiles, guided captures, and explicit ZERO/CAL interface are implemented. WF-04–WF-06 and shared controls support synthetic/fake execution. Implementation is distinct from physical qualification of the current meter.

## Remaining work

- Confirm current meter identity/resource, sensor/factors, and actual setup, and perform relevant interaction checks for its selected use. Laboratory software 2.0/address 13 are not fresh project observations.
- Use the guided path with an actual transmitter and suitable documented RF measurement path when selected.
- Perform physical setting, frequency, or voltage experiments when selected; supply control is needed only for voltage experiments.
- Fix demonstrated defects. No further mandatory POWER REF feature is identified.

## Requested investigation boundaries

Bounded reconciliation and diagnostics exist as isolated, explicit paths. Broader/unattended recovery, general bus coverage, persistent table edits, binary restoration, and unresolved status/error semantics retain their documented guards and limits. Do not infer physical support from codecs, fakes, method names, or the laboratory's HPIB test. The [command inventory](inventory/README.md) describes the current software/source boundary. Further investigations remain optional unless selected.

See [open work](OPEN-WORK.md) and the [release checklist](RELEASE-CHECKLIST.md).
