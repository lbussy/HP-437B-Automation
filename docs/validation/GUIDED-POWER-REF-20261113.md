# GUIDED-01 fixed POWER REF browser exercise — November 13, 2026

**Completed: the selected current-Mac fixed-reference point-capture/report exercise, independent audit, and owner final-state confirmation passed.** External-radio frequency/drive sweeps remain separate acceptance work. Ordinary logger, instrument, transport, main CLI, existing physical reference runners, and dependency pins are unchanged.

## Source option and scope

The existing guided external-radio path requires POWER REF off. This exercise added an explicit launch-only `signal_source: power_ref` option with native reference-on checks and matching saved-import guards. Its plan is constrained to the single label `50 MHz nominal (POWER REF)`, drive-series ordering, and one to three ordered `Repeat` labels. Caps are thirty samples, one-second intervals, twenty-second settling, and ten-second operation timeouts per point. These repeat labels identify capture order; they do not claim changed frequency or drive.

Source switching remained manual and supervised. The owner confirmed the current Mac, meter label SN 3125U33223, sensor label SN MY41094127, sensor cable to SENSOR, sensor RF input directly on POWER REF, warmed-up setup, closed other control applications, reference initially off, and availability for recovery. Existing preparation/factors were retained as historical/supplied facts, not freshly queried or changed. Known meter issues remain in configuration, provenance, and the full report. No zero/CAL, factor adjustment, preset/reset, software source switch, fault injection, or automatic measurement retry occurred. No operator name was inferred.

The configured resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. The pinned environment used Python 3.14.10, PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. The report identifies commit `2459a2bb6fdd4a50bb0326755b0e0b459d6e0fea` with a modified working tree for this local extension; it does not claim a clean released implementation.

## Initial refusal retained

The first series, job `3785d035bbf64b7da97c486331e7a824`, stopped at P001 before any counted readings. After the owner supplied a generic reference-on confirmation without a numeric reading, the consumed setup probe was −0.0100 µW and the native status indicated reference off, zero measurement errors, and zero entry errors. The source-state guard rejected capture; P002 and P003 were skipped. Existing healthy TR3/GTL closure succeeded. The owner subsequently confirmed live readings, RMT off, and reference off. Its sealed failure/report/package and separate final-state supplement remain retained locally. No automatic retry or resumed series occurred.

A new series was explicitly initiated through the page, again starting at the waiting boundary. The owner then supplied **0.993 mW** before the first capture. That reported indication is distinct from the three logged point means below. No meter session was opened while waiting for authorization.

## Completed three-point exercise

Job `ef27a6f27f744cd4839d796c52c1a9f0`; native run `2af89a23-d6ae-4fa9-9567-bf79f6a0592d`. The series record started **15:52:30.478 UTC / 09:52:30.478 CST** and finished **15:56:45.404 UTC / 09:56:45.404 CST**; this interval includes operator waiting and settling, not continuous acquisition. Each point requested ten readings at one-second spacing after five-second settling.

| Point | Valid readings | Mean | Minimum / maximum | Largest receipt gap |
| --- | --- | --- | --- | --- |
| Repeat 1 | 10 / 10 | **0.9927 mW** | 0.992 / 0.993 mW | 1.00609429 s |
| Repeat 2 | 10 / 10 | **0.9927 mW** | 0.992 / 0.993 mW | 1.00408683 s |
| Repeat 3 | 10 / 10 | **0.9925 mW** | 0.992 / 0.993 mW | 1.00426508 s |

All **30 counted readings were valid**, with no failed samples. Every point's native status showed POWER REF on, absolute W, and no entry/measurement errors. Each independent session recorded returned firmware 1.8 and accepted TR3/USB488 GTL cleanup. The interface waited before the first point and between points, reset both checkboxes at each boundary, and issued a fresh token per point. Based on the unchanged fixed source and the owner's exercise request, the assistant individually confirmed each pending point through the page; no external radio settings were changed or claimed.

The page reached **Series complete, 3 / 3**, and exposed full HTML, one-page PDF, and portable-package links. Measurement acceptance remains **NOT EVALUATED**, because no limits/decision rule were supplied. These are meter-indicated observations of the fixed internal source, not an absolute-accuracy, transmitter, frequency-sweep, or drive-sweep verdict.

## Audit and final state

The independent audit recomputed each mean, minimum/maximum, and population standard deviation with 50-digit Decimal arithmetic, checked native raw-frame/value/unit/sequence/status/error joins and count coverage, and verified reference-on status, firmware, confirmation-before-session chronology, and every session's healthy shutdown evidence. The saved native reader, report/provenance equality, physical package inventories, and one-page PDF text checks passed. The actual PDF was rendered and visually inspected. All eleven original capture files remained byte-for-byte unchanged through verification.

After Python closed, the owner turned POWER REF off and confirmed live updating numeric readings, RMT off, and PWR REF off. The later supplied observation is stored in a separate, capture-inventory-bound supplement recorded at `2026-11-13T15:57:47.475801+00:00`. It is not a protocol source-off measurement, and the sealed capture/report/package were not rewritten to include it.

Raw measurements, local service state, reports, and packages remain ignored under `output/reports/guided-power-ref-demo/`; audit/configuration scratch remains under `tmp/guided-power-ref/`. Only this reviewed summary is intended for source control.

| Artifact | SHA-256 |
| --- | --- |
| Capture inventory | `35c205f40daba01fb510c421f3a98d0a1c47a7126f35e8d7d24a0dc176051f40` |
| Report inventory | `44194df40baff0954dc49b9155eaf98d58d62b0e4cac54284afce58e33842c3f` |
| One-page PDF | `34e6d3e1c8896afe75a0ec89fc2e3e118124b217e1bbb34fc4d9841328424adc` |
| Portable ZIP | `3fb8c5c9c878621c5d991ff41affba4c9619bca006f0286e5ac2a41c67a67476` |
| Separate owner confirmation | `6f10fb703e79bab9185b11d053012ab72f838a8be2091196ce67c084ddadc852` |

## Software checks

The guarded focused guided/reference/interface regression passed **66 tests**. The complete hardware-blocked regression passed **1,304 tests**, with three opt-in stress cases skipped; these are separate runs. Ruff, formatting, JavaScript syntax, Markdown links/anchors/tables, inventory IDs, original PDF hashes, and `git diff --check` passed. These are local checks; delivery and CI verification are reported separately from the bench evidence.

This completes the selected fixed-reference browser exercise. External-radio frequency/drive sweep acceptance, actual radio/supply drivers, physical cancellation/fault exercises, Pi guided-browser operation, and unattended source recovery remain separate work.
