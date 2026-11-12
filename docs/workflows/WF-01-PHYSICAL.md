# WF-01 physical POWER REF integration

Prepared November 12, 2026. This extends [WF-01](POWER-REFERENCE-V1.md) from a synthetic prototype to an explicit physical runner, `tools/run_power_reference.py`. The selected current-Mac/meter POWER REF workflow completed, with owner final-state confirmation; results follow below. Ordinary `hp437b log`, runtime source, dependency pins, CLI defaults, and existing CSV/sidecar schema are unchanged.

## Fixed run and execution boundary

Use the current meter/sensor and already prepared direct POWER REF path, with POWER REF initially off. Owner confirmation covers Mac USB attachment, direct sensor path, warm-up, closed other control apps, and operator recovery availability. Retain the actual setup input file with identities, known issues, historical factor/preparation fields, and observation dates. The meter's documented supply issue is report provenance, not a software-development gate or a new accuracy test.

The fixed profile is source-off preflight and three-row baseline; OC1, twenty-second observation allowance and fresh status; three-row and 300-second source-on captures; OC0 with fresh source-off status; three-row final baseline; independent free-run/numeric OD and normal TR3/USB488 GTL closure. Confirm reference/correction/error/range/filter state before accepting each stage. No remote zero/CAL, factor/range/filter repair, preset/reset, induced timeout, clear/reset, or automatic measurement retry is included. Commands use existing [OC0/OC1](../inventory/COMMANDS.md#c065) and typed Instrument APIs.

Stage/RPC deadlines enforce the definition's finite profile; acquisition work stops before the 900-second outer ceiling to reserve cleanup/finalization. The supervisor signals the runner at 870 seconds and disposes its owned process group by approximately 900 seconds. The existing one-second failed-read allowance remains failure shutdown, not acceptance of a late sample. A workflow advisory resource lock excludes cooperating WF-01 runners; other applications still require owner-confirmed exclusivity.

Complete errors or policy mismatches can permit one bounded source-off cleanup if protocol state is known healthy. An uncertain read/write, failed close, or failed source-off never causes a blind reopen/OC0/retry. Source/local uncertainty is retained for operator recovery. An initial on-state is refused before activation without adopting the source. A complete source-off write followed by still-on status is a failure and is not automatically repeated.

## Outputs and reporting

The runner writes a continuously replaced owned workflow checkpoint and trace at stage boundaries, unchanged CSV/session pairs per capture, physical analysis JSON, Markdown report, finalized artifact inventory, and exact runner/helper/runtime/definition snapshots with licenses/notices. It records returned ID separately from supplied meter/sensor label identity. Calibration references and factors retain their provenance; unknown or historical values are not presented as freshly read settings.

Report outcome, saved-data integrity, and measurement criteria remain separate. Mean/min/max/peak-to-peak/sample SD, actual spacing, valid/failed counts, comparisons, and partial/skipped stages derive from retained rows. No accuracy or compliance threshold is invented. Source-off readings remain descriptive baselines. GTL acceptance and independent free-run/status checks are protocol observations; RMT off/live display and reference off receive a separate owner confirmation after Python closes.

Run only after selecting the physical setup and exclusive host environment. Example invocation (placeholders, not a discovery command):

```bash
.venv/bin/python tools/run_power_reference.py \
  --resource 'USB0::VENDOR::PRODUCT::SERIAL::0::INSTR' \
  --setup tmp/wf01-physical/setup.json \
  --output output/reports/NEW_WF01_RUN \
  --confirm-prepared-reference
```

The setup JSON must affirm `adapter_on_mac`, `direct_sensor_reference_path`, `reference_off`, `warmed_up`, `other_apps_closed`, and `operator_available`, and supply meter/sensor serials and a known-issues list. This is the fixed Mac integration; a Pi run requires its own selected host/setup record. Use offline QA with injected factories for tests; never remove guards to test a physical path. There is no automatic fallback from a failed physical run to synthetic results.

## Offline acceptance before opening

Integration tests exercise the actual runner through explicit fake factories: normal 300-row sustained capture, source-off/on/off sequencing, final free-run check, artifact hashes; malformed/timeout failures with no post-fault open/write/GTL; healthy between-read cancellation and instrument-error cleanup; failed source-off and still-on verification without a second OC0; initial-on refusal; failed-close uncertainty; input/output guards; deadline caps; and advisory ownership. Synthetic tool regressions remain separate.

## Observed USB identity change and scoped target preparation

The first selected resource, using the former `HEWLETT-PACKARD_437B_1.8` USB serial, failed during open with `No device found`; no instrument command or activation occurred. USB descriptor inspection found the same vendor/product profile under serial `GPIB_01_95032313036351A02290`. A new explicit resource is required; the failed artifact set is retained, not overwritten or counted as a measurement run.

The optional `tools/usbgpib_target.py` preparation is confined to the named adapter and explicitly supplied primary address. It verifies USB interface/framing, requires the pulse-indicator success byte before each internal command, reads adapter firmware `!ver?` and accepts the reviewed V2.4 profile, then writes only `!addr 13` for this setup. Normal instrument identity must subsequently match. No general G001 API is enabled, and no EEPROM/auto-ID/termination setting, reset, or firmware update is sent.

Primary evidence: publisher [Multi-device support](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#multi-device-support---setting-the-gpib-device-target-address) and [parser_finalize](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/miniparser.c#L271) assign the selected address to RAM `gpib_addr`; no EEPROM write occurs in that selector. This source review is not a binary firmware identity claim. Pulse/version/framing/error gates are tested through fake USB endpoints before physical use. The run setup explicitly records target selection/address; there is no automatic address scan or fallback.

## Current-meter physical result

**Completed November 12, 2026, on the current Mac/meter/sensor.** The corrected-resource run `run-002` completed every stage in 416.813 seconds (about 6 minutes 57 seconds), with 308 valid capture rows, no failed rows, one source-on/source-off pair, and no measurement retry. The nominal five-minute capture is a 300-second acquisition-start window, not a promise of 300 rows.

| Stage | Valid rows | Mean | Peak-to-peak | Median receipt spacing |
| --- | --- | --- | --- | --- |
| Baseline before (S10) | 3 | −0.0133333 µW | 0.01 µW | 7.43307 s |
| Short reference-on (S30) | 3 | 0.993667 mW | 0.001 mW | 1.00392 s |
| Sustained reference-on (S40) | 299 | 0.993843 mW | 0.001 mW | 1.00397 s |
| Baseline after (S60) | 3 | −0.01 µW | 0.03 µW | 7.43279 s |

S40 observed minimum/maximum were 0.993/0.994 mW; sample SD was approximately 0.000364591 mW. Mean versus declared nominal 1 mW was −0.615719%, reported descriptively with no accuracy/stability/compliance criterion. All numerical results were independently recomputed from saved rows. Baseline values remain descriptive below-normal-range observations; no subtraction or factor correction was applied.

Fresh source-off status, independent free-run/numeric OD, and accepted TR3/GTL cleanup passed. After Python closed, the owner confirmed live numeric readings, RMT off, and POWER REF off without pressing keys. The original automated report correctly retained front-panel confirmation as pending at creation; a separate operator attestation and completion summary were added without altering the sealed capture files.

Adapter firmware query returned V2.4; the scoped volatile selector targeted address 13, followed by expected HP 437B firmware 1.8 identity. Actual meter ID serial was blank, so supplied label identity is not promoted to an instrument-returned serial. The current meter/sensor labels, calibration references/hashes, known supply issue, and historical factor/preparation information remain provenance fields, not fresh calibration claims. No EEPROM, meter-address, firmware, zero/CAL, preset/reset, or induced fault operation occurred.

The first `run-001` artifact set is a retained failed-open result (`No device found` for the former USB serial), with every measurement/activation stage skipped. It was diagnosed by read-only USB inspection before resolving the explicit resource and preparing the target. It is not counted as measurement evidence or silently overwritten.

### Software and artifact checks

The complete hardware-blocked suite passed **450 tests**, including fake physical-runner failure/ownership/deadline checks and seven scoped target-helper cases. Lint, formatting, documentation/inventory checks, original reference checksums, and diff whitespace pass. The existing `src/hp437b/` files and dependency lock remain unchanged. No new remote CI result is claimed for this uncommitted work.

An independent audit passed **30 original artifact hashes**, raw/CSV/session/unit/sequence correspondence, Decimal statistics, receipt spacing, single OC1/OC0 sequencing, final source/free-run evidence, and report links. Raw physical output remains ignored under `output/reports/wf01-physical-20261112/run-002/`. The readable completion summary is `completion.md`, with `operator-confirmation.json` and `completion-artifacts.json`; original `report.md`, `workflow.json`, `analysis.json`, `trace.json`, CSV/sidecars, snapshots, and `artifacts.json` are unchanged.

| Artifact | SHA-256 |
| --- | --- |
| `report.md` | `8adbf17282cbcac80278c7d1285e4a1aadb39153ca181b3305109b6d46af6ba9` |
| `artifacts.json` | `97c7b131d9f59a7c102dbed1a9684983b17e8f4b0cb4b344891a8833e04f7b32` |
| `completion.md` | `480d9125ee9e4116ac2d1b6e4fcb5098f4c5313978b17647b270a29acc0ecb86` |
| `operator-confirmation.json` | `434f8885972e8aba31adbeed63ece67943b81f0a38d7e01536fe6c0c5c1144dd` |
| `completion-artifacts.json` | `479ef703ec0577564f1f892cc0717f0b2bd1ae17d093430ccf8754d2c113dcd6` |

This completes WF-01's first fixed supervised workflow on the selected current Mac/meter path. It does not certify the meter, establish absolute accuracy, enable the general guarded bus API, or qualify arbitrary hosts/faults/unattended continuation. Additional profiles, Pi workflow repetition, richer provenance tooling, plots, and external agent-assisted report integration are follow-on product work, not replacement-meter prerequisites.
