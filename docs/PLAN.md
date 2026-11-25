# Current plan

Updated: November 24, 2026. The [project scope](PROJECT-SCOPE.md) governs development.

## Decision register

| Item | Current decision |
| --- | --- |
| Operating mode | Human-started measurement and deterministic reporting; AI/provider automation deferred |
| Instrument/backend | HP 437B with USBGpib V2 and pinned open-source PyVISA/PyVISA-py/PyUSB stack |
| Hosts | Mac and Raspberry Pi; current-meter interaction checks required before claiming scoped host support |
| Measurement profile | Supervised internal-reference/readback profile in the [measurement policy](validation/MEASUREMENT-POLICY.md); explicit options preserve logger defaults |
| Equipment | Meter SN 3125U22346 and sensor SN MY41094127; [current records](EQUIPMENT.md) |
| Hardware scope | Relevant checks when equipment/operations are used; no blanket software-development gate |
| Reference library | Permanent manuals and calibration records live under [references](../references/README.md); document bytes, checksums, and receipt provenance are verified |
| Reporting | Traceable saved evidence, descriptive statistics, optional attributed criteria, PDF/portable delivery; [guided report presentation conventions](workflows/OPERATOR-GUIDED-SWEEPS.md#report-presentation) use concise prose and actual per-run identities |
| DUT control | Human-guided operation, automatic simulation, and optional combined PDF are available. The conducted Pico direct-GPIO campaign captured all 52 points and verified restoration to 12 mA. Pi control remains open. Supply control remains optional |

## Implemented capabilities

The typed command interface, bounded logger/transport, synthetic demos, provenance, analysis/reporting, WF-01–WF-03 reference runners, combined reference suites, saved-data reporting/history/comparison, supplied-limit assessments, profiles, guided captures, and explicit ZERO/CAL interface are implemented. WF-04–WF-06 and shared controls support synthetic/fake execution. Implementation is distinct from physical qualification of the current meter.

The 8482H SN 3318A09219 [calibration record](validation/8482H-CALIBRATION-20261122.md) contains a certificate and chart dated November 15, 2026, with a 99% reference factor. The selected measurement sensor is the 8482A SN MY41094127.

Serial-specific Mac-controlled 8482A MY41094127 factor correction is implemented for explicit-frequency logging and configured guided points. It uses certificate interpolation and records correction provenance; the [November 23 30 m bench record](validation/30M-POWER-20261123.md) reports one physical point at 24.500 mW indicated at sensor input, with stated limits.

## Remaining work

- The Mac CLI supports the fixed 80-point Pi 1 GPIO20 matrix, sealed acquisition evidence, and offline report export. Live Review and Start require the WsprryPi owner contract. See the [Pi 1 workflow](workflows/PI1-GPIO20-SWEEP.md).
- Confirm fresh setup for subsequent selected use and perform relevant additional checks when selected. Firmware 2.0/resource and the owner-supplied sensor setup were observed in the Mac bench run; laboratory address 13 remains unverified.
- Extend conducted transmitter measurements to additional source profiles when selected.
- Perform physical setting, frequency, or voltage experiments when selected; supply control is needed only for voltage experiments.
- Fix demonstrated defects. No further mandatory POWER REF feature is identified.

## Requested investigation boundaries

Bounded reconciliation and diagnostics exist as isolated, explicit paths. Broader/unattended recovery, general bus coverage, persistent table edits, binary restoration, and unresolved status/error semantics retain their documented guards and limits. Do not infer physical support from codecs, fakes, method names, or the laboratory's HPIB test. The [command inventory](inventory/README.md) describes the current software/source boundary. Further investigations remain optional unless selected.

See [open work](OPEN-WORK.md) and the [release checklist](RELEASE-CHECKLIST.md).
