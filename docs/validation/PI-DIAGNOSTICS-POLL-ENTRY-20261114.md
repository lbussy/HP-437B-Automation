# wspr5 controlled nonzero entry-error poll

November 14, 2026. Status: **selected controlled entry-error case complete, with separate owner final-state and unchanged-setting confirmation**. The [fake-first profile](SERIAL-POLL-NONZERO-FAKES.md) observed native status value **4** correlated with one fixed invalid-frequency stimulus, followed by retained entry-error status and successful bounded cleanup. This is scoped interaction evidence, not general fresh-poll or zero/CAL completion support. Normal logging and guards are unchanged.

## Authorization and provenance

The owner freshly reported FREQ **0.0500GZ**, CAL FAC **100.0%**, live readings, RMT/POWER REF off, unchanged connections, other apps closed, and five-minute availability on wspr5. One invocation used the prepared source-off/idle setup, declared meter `3125U33223` and sensor `MY41094127`, exact resource `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`, and the established shared resource lease. Actual ID matched `HEWLETT-PACKARD,437B,,1.8` plus CR/LF; the empty instrument serial field does not independently establish the supplied meter label.

Installation: `/home/pi/hp437b-qualification/diagnostics-poll-entry-20261114T163057Z`. Delivery SHA-256: `12ea9024338a85ec7352d3d5dd946d50b5b01a406c0a551ad6bfcd86a1bb8d51`. Its manifest identifies base `35e4781b075d5729051eea874bf6bbc59a868968` plus modified-source hashes, not a fabricated later commit. [CI for that base](https://github.com/lbussy/HP-437B-Automation/actions/runs/43614965552) passed all four jobs; it does not cover the subsequent uncommitted profile. The profile's separate evidence is 45 new fake cases, 323 focused passes, 1,955 full regression passes with three opt-in stress skips, builds/archive checks, and **554 installed-package guarded tests in 158.35 seconds** on Pi.

Host: Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41; pinned PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1; libusb package `2:1.0.28-1`. No dependency, normal-logger, or USB-rule change was made. POWER REF remained off; no valid numeric setter, mask setter, status clear, zero/CAL, reset, reconnect, recovery action, or retry was included.

## Observed sequence

The machine capture ran at **19:23:40.045127–19:23:40.837293 UTC** (13:23:40 America/Chicago), in **0.792226 seconds**. CLI exit was 0. All **21 rows** completed and were accepted before their deadlines; default work/total budgets were 20/25 seconds.

| Phase | Actual observation |
| --- | --- |
| Baseline | SM source off/free-run/W/normal operation, measurement and entry errors 0, auto range 11/filter 17, no correction/relative/limit flags; ESE, SRE, both ESR reads, and STB all 0 |
| Stimulus | One accepted private `FR-3GZ` write |
| Before poll | Two ASCII `*STB?` replies both `004` plus CR/LF |
| Native poll | Interface 0, interrupt-IN `0x81`; control reply `01 02 04`, interrupt reply `82 04`, matching tag 2/status **4** (entry-error bit 2, weight 4) |
| After poll | Both ASCII `*STB?` replies still `004` plus CR/LF |
| Read cleanup | SM entry error **82→0**, with source off/normal operation; ESR **16→0**; subsequent STB **0**, ESE **0**, SRE **0** |
| Followup | TR1/read `-0.0200E-06` W plus CR/LF (**−0.020 µW**), no error sentinel; final SM source off/error-free with preserved flags and documented TR1 standby |
| Closure | Healthy TR3/GTL accepted (`01`), raw transport close successful, worker exited 0 without force |

The assessment records `accepted_full_case: true`, `nonzero_entry_poll_observed: true`, `before_status_bytes: [4,4]`, `after_status_bytes: [4,4]`, `entry_bit_observation: entry_bit_present_on_both_post_poll_ASCII_reads`, and `quiet_cleanup_verified: true`. Machine `numeric_settings_verified` remains false; the independent owner comparison is recorded below.

The entry-error indication remained visible on the two immediate ASCII reads after the native poll. This is consistent with the separately documented entry-error latch and does not support an assumption that polling alone removes the visible entry bit. Later STB zero was observed after **both SM and ESR read sequences**; this experiment does not isolate which individual read cleared the status byte. SM 82→0 and ESR 16→0 are their actual ordered observations, not a general queue/clear implementation claim.

The native nonzero value is correlated with this selected stimulus, but firmware-hidden GPIB timeout and cached-SRQ merging remain evidence limits. `instrument_poll_success_verified`, `freshness_verified`, and `procedure_completion_verified` remain false. No general G015 capability, fresh zero/CAL completion, other lifecycle/error condition, unattended recovery, or other host/meter support is promoted.

## Evidence and operator confirmation

Ignored raw artifacts: `output/logs/pi-diagnostics-poll-entry/entry-poll-20261114T192339Z/`, matching remote `runs/entry-poll-20261114T192339Z`. The run-directory label precedes the capture start by about one second; the machine timestamps above identify actual capture. Receipt SHA-256: `5a1b216b6ced1043b3a62da1b3e3d4f40def7bb4b412c1887ccc1b66c34f9b48`; wrapper summary SHA-256: `c1e7c6706396c44a7d33fdff1aef468574a4d916a1a2079c2edd4e0678652dbe`. Independent local inspection verified the receipt digest, all 21 completed/timely rows, exact USB frames, subsequent cleanup/acquisition/status, and accepted closure. The wrapper verified original logger, permanent USB rule, and installed runtime hashes unchanged before/after; local normal runtime/pins/udev bytes are unchanged from the published base.

After Python closed, the owner answered **“Yes”** to the explicit no-key live-readings/RMT-off/POWER-REF-off question and the subsequent comparison with **0.0500GZ/100.0%** using EXIT without changes. No additional indication was described. That separate owner observation completes the selected final-state/settings comparison; it is retained separately and does not rewrite the machine receipt as USB-verified numeric readback. No further meter command was issued after the run.
