# wspr5 revised acquisition-setting batch

November 14, 2026. Status: **selected revised Pi batch complete, with separate final front-panel confirmation**. The owner authorized one revised run with original RES2, unchanged connections, live readings, RMT/POWER REF off, other control apps closed, and five-minute availability. The [manual/fake investigation](RE-FILTER-RESTORATION-INVESTIGATION.md) defines plan version 2 and its limits. The earlier [failed version 1 receipt](PI-DIAGNOSTICS-ACQUISITION-20261114.md) remains unchanged. Normal logging is unchanged.

## Provenance and bounds

The adapter remained on wspr5 with the same prepared warmed-up direct POWER REF path, meter label `3125U33223`, and sensor label `MY41094127`. Actual identification matched `HEWLETT-PACKARD,437B,,1.8`; the empty instrument serial field is not the supplied equipment label. The exact resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`.

One invocation used `/home/pi/hp437b-qualification/diagnostics-re-filter-20261114T144409Z`, its existing shared resource lock, and the prepared isolated installation. Delivery SHA-256: `19f74eb6062d8f0bf5fc994d0630bc8540d23708872e5a2666c94c4db51a086c`; base commit `7dcf815e4da16991289ca597ddb5a10853c4ce46` plus manifest hashes identifies modified source. Host: Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41; pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. Installed-package preflight passed 401 guarded tests. Work/total budgets remained 60/65 seconds, with a 20-second reference wait and four-second restoration refresh; native timeouts were unchanged.

## Observations

The run completed at **14:51:20.940064–14:51:48.263075 UTC**, in **27.323104 seconds**, CLI exit 0. All **50 rows** completed before their deadlines: 20 commands, 13 acquisitions, 15 SM queries, and two waits. No retry, reconnect, additional probe, or cable recovery occurred.

| Selected phase | Observation |
| --- | --- |
| Baseline | Reference off, free-run, W, errors 0, automatic range 11/filter 17 |
| Reference on | OC1 and 20-second wait; TR1 returned 0.9940 mW; SM verified reference on |
| FM4 → RE1 / FM4 → RE2 | Both accepted sequences returned measurements, then SM manual filter code 02 (count 4), errors 0. Intermediate effective resolution values were not independently verified |
| FM1 / FM4 | TR2 acquisitions completed; SM manual filter codes 00/02 respectively |
| FA / FH | Measurements completed; automatic filter code 11 after FA and manual filter code 01 after FH |
| RH / RM5 / RA | Measurements completed; SM range codes 03/05/13 respectively |
| FM1 / TR0 → TR1 / TR2 | Replies consumed; SM standby true, filter code 00, errors 0. No independent dynamic hold-duration claim |
| TR3 / read | Numeric reply consumed; SM free-run, reference on, errors 0 |
| Restoration | OC0 → RE2EN → RA → FA → TR3 → four-second refresh → SM completed. SM verified reference off, free-run, automatic range 11/filter 17, and errors 0 |
| Closure | Final healthy TR3/GTL accepted, transport closed, worker exited 0 without force |

Acquisitions were 0.9930–0.9940 mW except the deliberately selected manual range 5 reading of 1.0000 mW. These are interaction observations, not an RF-accuracy comparison or recommended operating range. The assessment records `accepted_full_case: true`, `auto_modes_reference_off_verified: true`, `reference_may_be_on: false`, and `resolution_usb_verified: false`. Accepted RE writes do not establish intermediate numeric resolution values. The owner separately confirmed final original RES2, as recorded below.

This verifies the revised restoration sequence in this one current-Pi case. It does not identify the original timeout's cause, establish all parameter combinations, prove unattended recovery, or qualify another meter/host. No change to normal logging or a new release requirement follows.

## Evidence and final observation

Retrieved raw artifacts remain ignored at `output/logs/pi-diagnostics-acquisition/settings-v2-20261114T145120Z/`, matching remote `runs/settings-v2-20261114T145120Z`. Receipt SHA-256: `f62b5ac40d9fa2a8bfaeed29b172b95c34b925edbcfd957d2a527f89a30623fa`; wrapper summary SHA-256: `e2b6534f632d63745e0d5555b9ddd94e564ef21839bab937d94de3e337e0cb04`. Independent inspection verified all 50 completed/timely rows, restoration assessment, transport closure, and accepted GTL. The wrapper verified original logger, USB rule, and installed runtime bytes unchanged; the local normal logger, transport, instrument, protocol, encoder, CLI, reconciliation, dependencies, and udev files also remain unchanged from HEAD.

After Python closed, the owner explicitly confirmed: “Confirmed—live readings are updating, RMT and POWER REF are off, RESOLN is still RES2, and RNG HLD and SPCL are off.” This separate observation completes the final front-panel comparison; it is not inferred from accepted GTL or SM. The machine receipt remains unchanged, and the observation is retained separately. No further physical operation was performed.
