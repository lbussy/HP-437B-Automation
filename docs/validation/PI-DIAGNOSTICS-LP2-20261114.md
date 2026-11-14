# wspr5 read-only LP2 snapshot and post-read check

November 14, 2026. The owner-authorized [LP2 profile](DIAGNOSTICS-LP2-SNAPSHOT-FAKES.md) completed on the current meter, with separate owner final live/local/reference-off confirmation. This establishes one opaque binary capture and subsequent ordinary communication/closure on the recorded Pi setup. It adds no setting decoder, restore operation, normal-logging change, general backend claim, or meter-performance claim.

## Setup and provenance

The owner freshly confirmed unchanged settings/connections, adapter on wspr5, POWER REF/RMT off, live readings, no pending operation, other control apps closed, and five-minute availability with PRESET/LOCAL accessible. No source operation, correction entry, calibration, persistent setting, cable, or power change was performed. Supplied labels remain meter `3125U33223` and sensor `MY41094127`; the actual identification was HP 437B firmware 1.8 with an empty serial field.

The exact expected resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. The isolated installation was `/home/pi/hp437b-qualification/diagnostics-lp2-20261114T134530Z`. Its preparation passed **349 installed-package guarded tests in 97.09 seconds**, with lint/formatting, installed/delivered/source runtime hashes, and original logger/udev-rule preservation verified. The one-pass wrapper rechecked runtime hashes and absence of prior control workers, then used the existing shared exact-resource workflow lock.

Capture-time build provenance is base `e0d853f78f3cfae20db90d7efbe70a327fa4751d` plus modified-source hashes, not a fabricated later commit identity. Delivery SHA-256 is `8e97b6f6fe59bdc1b5350b80d927de4667d6887099a47125d25375846ad74f7c`. The host was Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41, with pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1.

## Actual sequence

The pass ran at **13:50:53.124912–13:50:53.520757 UTC**, completing in **0.395879 seconds**, with CLI exit 0. All four distinct capture/check rows completed and were accepted before deadline, following instrument/adapter identity checks.

| Step | Observation |
| --- | --- |
| SM before | Reference off, no measurement/entry errors, normal operation, not standby; W/linear/nonrelative, range 11/filter 17 |
| LP2 once | Exactly **60 bytes**, prefix `@2` plus 58 opaque binary bytes; backend-reported complete/EOM status 0; artifact matches retained raw bytes |
| TR1 acquisition | Complete ordinary measurement `+0.0100E-06` W, parsed as `1.00E-8` W (0.01 µW); no error sentinel |
| SM after | Reference off, no measurement/entry errors, normal mode; preserved configuration flags/range/filter; standby true as documented after TR1 readout |

No ASCII status query interrupted the LP2 or acquisition reply. The expected post-TR1 standby state was observed and allowed. Existing cleanup then accepted TR3/free-run and USB488 Go To Local; transport closed and the worker exited normally with code 0, without forced disposal. The owner subsequently confirmed live operation. The measurement is a post-snapshot communication check, not a zero, accuracy, settling, or transmitter result.

The original normal logger, permanent udev rule, and installed diagnostic runtime remained byte-for-byte unchanged. There was no repeated LP2, restore/writeback, ERR/ESR read, deliberate error, source switch, valid correction setter, clear/preset, zero/CAL, reset, reboot, cable operation, or retry.

## Opaque artifact and interpretation

The retained `capture/snapshot.bin` is the exact 60-byte response, including `@2`. Its SHA-256 is **`bc75507c2f27d91384ae5e401d721c8bbee05084a49e670fa3e655c811a5dd00`**. Local verification matched artifact bytes against the receipt's raw hex and recomputed hash, rather than accepting the filename/size alone.

No fields were decoded, no snapshot bytes were sent back, and no restore capability is claimed. The manual lists configuration categories but does not provide their byte layout on the cited Learn Mode page. This single capture does not establish repeatability of snapshot bytes, semantic equivalence from hashes, completeness of configuration coverage, or compatibility with another firmware/host. A02 remains open for decoding, restore framing, and legacy forms. C064 Pi coverage is scoped to this complete opaque read and post-read communication case; Mac LP2 remains untested.

## Owner final observation

After Python closed, the owner answered **“Yes”** to the no-key confirmation of live readings updating, RMT off, and POWER REF off. No additional unexpected indication was separately reported. This observation is retained separately; the original receipt still has `front_panel_confirmation: not_provided` and `physical_identity_verified: false`. Supplied labels and owner evidence do not rewrite those fields. No manual recovery was requested or reported.

## Retained evidence

Remote capture: `/home/pi/hp437b-qualification/diagnostics-lp2-20261114T134530Z/runs/lp2-20261114T135053Z`. Raw local evidence, including the binary artifact, remains ignored under `output/logs/pi-diagnostics-lp2/lp2-20261114T135053Z/`; delivery, preflight, package checks, and verification remain ignored under `tmp/lp2-snapshot/`.

| Evidence | SHA-256 |
| --- | --- |
| Original `capture/diagnostics.json` | `3447dbc66c4224c1922e80059732a9e71814fdabc1ff5caf0c66691356b27ee5` |
| Opaque `capture/snapshot.bin` | `bc75507c2f27d91384ae5e401d721c8bbee05084a49e670fa3e655c811a5dd00` |
| Wrapper `result.json` | `9efe13ce2f09582488a7334409f169e3a34292ae61c3f0afb454393fbecdea8b` |
| Separate owner final confirmation | `7fd6bf730cae3050850d03a7f006b17183a6773d04e1be50da143c40e5a66382` |
| Unchanged permanent udev rule | `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be` |

Local verification independently checked original receipt bytes/hash, all four timely rows, exact binary framing/bytes/hash, successful post-read acquisition, native statuses, worker exit/local return/closure, and original logger/rule/runtime preservation. Raw local measurements and tool state are not committed.
