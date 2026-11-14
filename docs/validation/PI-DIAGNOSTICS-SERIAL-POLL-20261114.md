# wspr5 single source-off serial-poll diagnostic

November 14, 2026. Status: **selected quiet-state USB488 diagnostic case complete, with separate owner final confirmation**. This accepts the recorded USB exchange and following ordinary communication, not independent proof of a fresh successful instrument poll or procedure completion. Normal logging and zero/CAL guards are unchanged. See the [investigation](SERIAL-POLL-INVESTIGATION.md) and [isolated worker](SERIAL-POLL-WORKER.md) for scope and evidence limits.

## Authorization and provenance

After publication/CI and guarded Pi preflight, the owner answered “Yes” to the fresh setup question covering unchanged wspr5 equipment/connections, live readings, RMT/POWER REF off, no pending trigger/zero/calibration, other control apps closed, and five-minute availability with PRESET/LOCAL accessible. The later no-key final-state question also received “Yes.” No retry, source switching, mask setter, zero/CAL, deliberate timeout, cable move, or recovery action was included.

The declared meter/sensor labels remain `3125U33223`/`MY41094127`. The observed ID was `HEWLETT-PACKARD,437B,,1.8` plus CR/LF, matching the expected response; its empty serial field does not independently establish the declared meter serial. The receipt's `physical_identity_verified` remains false. Exact resource: `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`.

One invocation used `/home/pi/hp437b-qualification/diagnostics-serial-poll-20261114T160536Z`, source/wheel built from clean commit `dde387be974943c39a59b4a1bc71d0e92c1758fe`. [All four exact-commit CI jobs](https://github.com/lbussy/HP-437B-Automation/actions/runs/43613646587) passed. Delivery SHA-256: `50955f6eac0aa686913bd396611f7ed6e211fe4200af3db76af7dc66345b0e5a`. Isolated installed-package preflight passed **509 guarded tests in 134.83 seconds**, with hash/pin and original logger/udev preservation checks. Host: Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41; pinned PyVISA 1.16.2, PyVISA-py 0.8.1, PyUSB 1.3.1; libusb package `2:1.0.28-1`.

## Observed sequence

The run lasted **0.413750 seconds**, from **16:16:25.550522 to 16:16:25.964232 UTC**. CLI exit was 0; all seven planned rows completed and were accepted before their deadlines. The established shared exact-resource lease and default 20/25-second work/total budgets were retained.

| Row | Observation |
| --- | --- |
| Baseline SM | Source off, free-run, W, no entry/measurement errors, normal operation, auto range 11/filter 17, no relative/offset/duty/limits flags |
| *SRE? | `000` plus CR/LF; mask zero, no mask changes |
| Before *STB? | `000` plus CR/LF |
| One USB488 poll | Actual interface 0, interrupt-IN endpoint `0x81`; fresh capabilities `010000010401000000000000000107070000000000000000`; control reply `01 02 00`, interrupt reply `82 00`, matching tag 2/status zero |
| After *STB? | `000` plus CR/LF |
| TR1/read | `-0.0200E-06` W plus CR/LF, parsed as **−0.020 µW**, with no error sentinel |
| Final SM | Source off, no entry/measurement errors, normal operation, auto range 11/filter 17, preserved interpretation flags; standby after TR1 as documented |
| Closure | Final TR3 and USB488 GTL accepted (`01`); transport closed; worker exited 0, stopped without force |

The selected diagnostic assessment has `accepted_full_case: true`, while **`instrument_poll_success_verified`, `freshness_verified`, and `procedure_completion_verified` all remain false**. The nested poll receipt is `adapter_reply_validated`, with one poll dispatched. Both raw USB replies were retained; no ordinary VISA read status was substituted for the native poll's evidence.

Matching success/zero frames do not distinguish a quiet successful instrument poll from the inspected firmware's hidden GPIB timeout path. The firmware can also merge cached SRQ bits. This case therefore does not establish nonzero status acquisition, clearing/buffering lifecycle, fresh zero/CAL completion, fault recovery, Mac support, SRQ-event handling, or a general serial-poll transport capability. No normal transport capability or bus guard is promoted.

## Evidence and final confirmation

Retrieved raw artifacts remain ignored at `output/logs/pi-diagnostics-serial-poll/poll-20261114T161625Z/`, matching remote `runs/poll-20261114T161625Z`. Receipt SHA-256: `afa856779c852a662cbaa2573840643067be2e5166b3e100b3151ecfd5a3d5f1`; wrapper summary SHA-256: `5724001e589d0d710ce1b9e3f45abc654f142165dbecea5d7fb828ac4bbb0f65`. Independent inspection verified the receipt hash, seven completed/timely rows, nested USB framing/status, following measurement/status, accepted local return, and normal closure. Original logger, permanent USB rule, and installed runtime hashes were unchanged before/after; local source/runtime/pins/udev remain unchanged from the published worker commit.

After closure, the owner answered **“Yes”** to the no-key question confirming live readings updating, RMT off, and POWER REF off. No additional indication was described. This separate observation completes the final-state check; it is not inferred from accepted GTL. It is retained in a separate owner-confirmation artifact; the machine receipt remains unchanged. No further hardware command was issued after this run.
