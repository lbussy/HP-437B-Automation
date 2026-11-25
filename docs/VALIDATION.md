# Current validation scope

Updated: November 24, 2026. The current meter is **SN 3125U22346**, with laboratory software **2.0** and HPIB address **13** listed in its calibration record. A [supervised Mac ZERO and 30 m power capture](validation/30M-POWER-20261123.md), a [native Pico Test Tone pilot](validation/30M-POWER-20261123.md#native-test-tone-pilot), and a [complete 52-point Pico sweep](validation/PICO-52-20261123.md) are recorded. Broader interaction checks and meter control from a Pi remain **pending**. Laboratory certification and software tests do not establish current host/backend compatibility or absolute RF accuracy.

The 8482H SN 3318A09219 [calibration review](validation/8482H-CALIBRATION-20261122.md) records laboratory evidence from the certificate and calibration chart dated November 15, 2026. Physical project qualification for this sensor remains pending.

## Pico Si5351 Test Tone

Pico C (`wpicoc.local`, USB serial `1545B6EFBF78028C`) runs ordinary WsprryPico `0.0.0-devel` from `b0edc0ddd2b5ff686b22a9274c617653214346dd`. The Control/1 profile is `qrp-labs-rev6-25mhz-clk0`. Both experimental-frequency flags are false. [Pico PR #30](https://github.com/WsprryPi/WsprryPico/pull/30)

Pico C admitted **all 56 points** in read-only Review using HP adapter `e2dcbee78fa23f977f80132db87d281b79d6089b` over authenticated USB through `wspr5`. Review returned 14 `ready`, 42 `requires_restart`, and zero refusals. At **144.490500 MHz**, the 8 mA point was ready and the 2, 4, and 6 mA points had valid realizations with a required drive restart. The before-and-after readback matched at 8 mA saved and boot-active, both schedules disabled, and idle, unowned, inactive output. The assessment revision matched across Review.

The Review was bound to Control/1 device `c2a3a2a314c948b50a8562a1aeb69669` and boot `f4343446af695f63f8597c3cd123db43`. The installed UF2 has SHA-256 `44e380d88d04a94b3ac8eebb66e3eaa8ae2698f54d67aba2ba1c7b994aa67794`. The retained `hp-56-review-evidence.json` has SHA-256 `24a230efd0115b25a8c06210a3c5e6b6b755003fd1246a7d9c2ac96e58ffc393`.

RF-free Pico tests cover native Start and finite shutdown at 144.490500 MHz for all four nominal drives. The conducted 2 m result applies to its recorded 8 mA setup. Separate conducted tests at 14.0971 MHz cover 10 ms, identified Stop, and 120-second cases at all four drives. Register shutdown depends on the I²C bus. [Exact-source Pico CI](https://github.com/WsprryPi/WsprryPico/actions/runs/45426556062) · [Conducted 2 m qualification](https://github.com/WsprryPi/WsprryPico/blob/b0edc0ddd2b5ff686b22a9274c617653214346dd/engineering/development/si5351.md#qualified-ordinary-profile) · [Conducted 20 m lifecycle checks](https://github.com/WsprryPi/WsprryPico/actions/runs/45415392232)

The supervised HP Si5351 sweep retained **112 readings at 56 points**, with all four drives measured at 144.490500 MHz. The sealed report record is `f2d3366439c743f99dcd5ccebc7a44c0`. It includes verified meter closure and Pico restoration to 8 mA with both schedules disabled and RF inactive. The HP runner requires a fresh full Review before meter preparation, drive changes, or Start. The [HP RF-free contract fixtures](../tests/test_si5351_sweep.py) cover the 56-point operator-to-report path, bounded status retries, supervised continuation, and unconfirmed shutdown.

## Raspberry Pi 1 GPIO20 pilot

The November 24, 2026 conducted pilot used `wspr1.local` (Raspberry Pi Model A+, BCM2835), the 8482A SN MY41094127, and the Mac-controlled HP 437B. A temporary loopback-only WsprryPi process used native GPIO20 at a configured **2 mA** and requested **475,700 Hz**. The controller confirmed GPCLK0 on GPIO20 and committed **0.0 ppm additional clock correction**. The meter display readback verified **100.7% CAL FAC**. Both settling reads and the retained read indicated **3.0100 mW (4.79 dBm)** at the sensor input. RF-off readings were **−0.17 µW** before the tone and **−0.27 µW** afterward. The meter indication can include harmonics. The configured drive and carrier are controller evidence, with no independent current or frequency measurement for this point.

The bounded request had a **50-second cutoff**. The controller confirmed shutdown after **6.18 s**, released ownership, and returned GPIO20 to input mode. The temporary process exited with the normal `wsprrypi.service` stopped and disabled. The meter accepted free-run and return to local. The local receipts are under `tmp/wspr1-gpio20-disabled-pilot.8lvyk3ni/capture/` as `pilot.json` (SHA-256 `1b63f5fab169d9e330d5333128708a83c1cb82c6c121d27563c893ccaf11ea4e`) and `pi-events.jsonl` (SHA-256 `c453831592612de44dbd49834775b3f24570440bfd481acbba8054f88fb1f520`). The [Mac sweep runner](workflows/PI1-GPIO20-SWEEP.md) has RF-free evidence for all eight drive groups and 160 retained samples. The WsprryPi owner contract and physical full-matrix qualification remain open. [Sweep plan](workflows/AUTOMATIC-FREQUENCY-DRIVE-PLAN.md#2-device-controls)

## Record the environment

Record the actual meter/sensor labels, firmware reply, USB resource, adapter model/firmware, cable, front-panel GPIB address, host/OS/architecture/Python/libusb, package versions/origin, sensor corrections, and full signal path. Distinguish supplied labels, laboratory records, observed protocol replies, and operator confirmations. See [equipment](EQUIPMENT.md).

## Required checks

Choose only the checks relevant to the selected use, with explicit authorization, finite budgets, and fresh setup confirmation. The [prepared procedure](validation/BENCH-ACCEPTANCE.md) supplies bounded cases; it has not been executed on this meter.

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
