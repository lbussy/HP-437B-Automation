# Current validation scope

Updated: November 23, 2026. The current meter is **SN 3125U22346**, with laboratory software **2.0** and HPIB address **13** listed in its calibration record. A [supervised Mac ZERO and 30 m power capture](validation/30M-POWER-20261123.md), a [native Pico Test Tone pilot](validation/30M-POWER-20261123.md#native-test-tone-pilot), and a [complete 52-point Pico sweep](validation/PICO-52-20261123.md) are recorded. Broader interaction checks and meter control from a Pi remain **pending**. Laboratory certification and software tests do not establish current host/backend compatibility or absolute RF accuracy.

## Record the environment

Record the actual meter/sensor labels, firmware reply, USB resource, adapter model/firmware, cable, front-panel GPIB address, host/OS/architecture/Python/libusb, package versions/origin, sensor corrections, and full signal path. Distinguish supplied labels, laboratory records, observed protocol replies, and operator confirmations. See [equipment](EQUIPMENT.md).

## Required checks

Choose only the checks relevant to the selected use, with explicit authorization, finite budgets, and fresh setup confirmation. The [prepared procedure](validation/REPLACEMENT-ACCEPTANCE.md) supplies bounded cases; it has not been executed on this meter.

1. Verify intended USB identity/access and exclusive ownership before opening through the pinned backend.
2. Check actual identification and source-off status, then one complete serialized acquisition and healthy closure.
3. For prepared reference use, compare matching display/readback settings and verify source switching/restoration. A matching display checks readback, not absolute calibration accuracy.
4. For logging, verify count/timing/units/raw frames, CSV/sidecar joins, output protection, and partial-evidence preservation.
5. Select interruption/failure cases only when needed, with separately declared authorization and recovery; do not inject faults for documentation cleanup.
6. Record independent live numeric readings, RMT off, and POWER REF off after closure. A process exit or accepted GTL is insufficient.
7. Keep Mac and Pi results separate; check actual Pi permissions and retrieval hashes before claiming Pi support.

## Software checks

Run tests under `tools/offline_qa.py`; see [installation and checks](SOFTWARE.md#installation-and-checks). The [coverage matrix](inventory/COVERAGE.md) and [parameter ledger](validation/OFFLINE-PARAMETER-COVERAGE.md) distinguish syntax/software coverage from current-meter host checks. Guarded or excluded capabilities remain so until their source/implementation and relevant hardware evidence support a change.

## Results to retain

For new runs, retain setup, identities, source/settings/factors, exact software/runtime origin, finite budgets, raw/parsed replies, CSV/sidecars, timing, failed/partial artifacts, shutdown/uncertainty outcomes, and separate operator confirmation. Use new paths for each acquisition. Reports derive from sealed evidence and never convert simulation into a physical pass.

## Backend decision

Use the pinned open-source backend and project-local conditional USB488 paths. General clear, bus trigger, SRQ, binary restore, already-wedged repair, and unattended continuation remain unqualified or guarded as described by the [inventory](inventory/README.md). Do not change firmware, dependencies, host security, or setup merely to validate these documents.
