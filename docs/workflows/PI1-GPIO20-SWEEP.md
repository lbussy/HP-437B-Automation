# Conducted Pi 1 GPIO20 sweep

The Mac command runs the fixed drive-first matrix for `wspr1.local` (Pi 1 Model A+, BCM2835 GPIO20/GPCLK0), HP 437B SN 3125U22346 over USBGpib V2, and 8482A SN MY41094127. The matrix has 80 points, with all ten bands at each nominal drive setting from 2 to 16 mA in 2 mA steps. Each group has a disposable loopback-only owner process. The carrier is the configured WSPR dial plus 1,500 Hz.

```console
python -m hp437b.pi1_sweep plan
python -m hp437b.pi1_sweep report --capture tmp/pi1-capture --output tmp/pi1-report
```

Plan is offline. Report validates a finalized capture and exports all 80 rows to HTML, JSON, and CSV. Add `--pdf` to export a PDF with the optional PDF dependencies. Keep fixture notes, review files, captures, and reports under ignored `tmp/` or `temp/` paths. The software reports indications at the sensor input, where harmonics can contribute. Independent frequency accuracy and acceptance criteria remain unevaluated.

## Live readiness

Live Review and Start require a WsprryPi owner CLI on the Pi that implements `wsprrypi.pi1-gpio20-owner.v1`. The installed pilot controller lacks that contract. Its bounded-tone watchdog is armed after requesting Start, `tone_end` is not generation-scoped, and the BCM2835 transmit path writes the shared GPIO0–27 pad bank without recording its original writable fields and verifying restoration. The Mac runner requires the owning implementation for RF-free admission and verified shutdown. See the [pilot record](../VALIDATION.md#raspberry-pi-1-gpio20-pilot) for the physical evidence.

After a compatible owner is implemented, tested, and separately authorized for installation, prepare a private JSON fixture file with `signal_path`, `shutdown`, `maximum_indication_w`, `peak_w`, `dc_v`, and `confirm`. Use descriptive text for the conducted path and independent shutdown, and decimal strings for numeric bounds. The indication and peak bounds may be at most 0.1 W. Record a DC-free fixture with `"dc_v": "0"`. The confirmation object contains these five explicit booleans, all true for the prepared fixture.

- `conducted_gpio20_fixture_through_16ma_all_ten_carriers`
- `meter_437b_3125u22346_and_8482a_my41094127`
- `meter_prepared_cal_at_99_percent_and_power_ref_off`
- `rf_off_other_apps_closed_ready_for_supervised_zero`
- `independent_shutdown_ready_operator_present`

```console
python -m hp437b.pi1_sweep review --fixture tmp/pi1-fixture.json --output tmp/pi1-review.json
python -m hp437b.pi1_sweep start --review tmp/pi1-review.json --authorize REVIEW_AUTHORIZATION --output tmp/pi1-capture
```

Review uses read-only SSH with strict host-key checking, compares all 80 native plans against the selected correction, and exposes each refusal. The authorization expires ten minutes after Review and permits one Start. Start revalidates the matrix, runs a supervised ZERO with RF off, and takes three signed RF-off readings before requesting a tone. Each point verifies numeric CAL FAC from the 8482A certificate, takes up to three settling readings, and retains two distinct TR1 readings. The source has a maximum 50-second cutoff. The Mac uses a separate Stop request scoped to the pending or accepted owner transaction. The complete run budget is displayed by Plan.

The bench operator remains available to use the documented independent shutdown. A lost or ambiguous owner receipt can leave a durable owner or meter recovery marker. Reconcile the actual hardware state and retain the evidence before removing a marker. Preserve a sealed partial capture for reporting and obtain a fresh Review and explicit Start for another attempt.

## Owner integration

The consumer uses a fixed SSH command with the host's existing authentication and known host key. The candidate helper path is `/usr/local/libexec/wsprrypi-pi1-gpio20-owner`. Every invocation receives exactly one JSON request on stdin and returns one compact JSON reply on stdout. Replies echo `contract`, `operation`, and `request_sha256` (the SHA-256 of the actual input bytes), plus a `receipt` object. Contract field validation lives in `pi1_owner.py` and `pi1_sweep.py`.

| Operation | Authority and required behavior |
| --- | --- |
| `review`, `admit` | Inspect model, backend, normal unit, boot, station and executable identity, and selected correction without launching a process or accessing the meter. Use the native exact-carrier planner. Report a concrete refusal if unavailable, including low-band divider refusals. |
| `claim`, `admit_matrix` | Reserve the device-wide bench lease and pad bank, persist recovery state, take an original drive/hysteresis/slew snapshot, and verify the complete matrix again before ZERO. |
| `open_group`, `close_group` | Launch an isolated IPv4 loopback process with immutable GPIO20 and drive settings, a bounded lifetime, and no ancillary outputs or scheduled transmissions. On close, confirm native GPCLK idle, GPIO input, pad restoration, and process exit. |
| `start`, `status`, `stop` | Bind the request, plan, and finite lifetime to the unique process and generation. Enforce cutoff before GPCLK can enable, verify native active pad/clock state, and serialize identified Stop with Start, including when the Start reply is lost. A Stop before Start acceptance must prohibit a later start of the same request. |
| `release` | Confirm native output inactive, bank restored, and lease released with the normal service still inactive and disabled. Reconcile or keep the Pi-local pending record when a result is unknown. |

The owner binds receipts to the host's device and boot and to the run. The owner must verify the boot, build, executable, clock selection, and original station configuration at each admitted transition. Reported realization bounds are mathematical and must be within 1 Hz of the requested carrier with the same rounded CAL FAC throughout. This consumer freezes one selected correction per Review. The owner must preserve and independently verify native inactivity and pad restoration on connection loss or missed deadlines, protect against other local bank users, and avoid overwriting an external pad change. The owner command and deployment remain open, so WsprryPi support is a prerequisite for live use.
