# Conducted Pi 1 BCM2835 GPIO sweep

The Mac command runs the fixed drive-first matrix for `wspr1.local` (Pi 1 Model A+, BCM2835 GPCLK0), HP 437B SN 3125U22346 over USBGpib V2, and 8482A SN MY41094127. Select GPIO4/ALT0 or GPIO20/ALT5 for the entire run. The matrix has 80 points, with all ten bands at each nominal drive setting from 2 to 16 mA in 2 mA steps. Each group has a disposable loopback-only owner process. The carrier is the configured WSPR dial plus 1,500 Hz.

```console
python -m hp437b.pi1_sweep plan --gpio 20
python -m hp437b.pi1_sweep report --capture tmp/pi1-capture --output tmp/pi1-report
```

Plan is offline. Report validates a finalized capture and exports the authorized one-point or 80-point scope to HTML, JSON, and CSV. Add `--pdf` to export a PDF with the optional PDF dependencies. Keep fixture notes, review files, captures, and reports under ignored `tmp/` or `temp/` paths. The software reports indications at the sensor input, where harmonics can contribute. Independent frequency accuracy and acceptance criteria remain unevaluated.

## Live readiness

Live Review and Start require the matching WsprryPi qualification owner and ordinary binary with cooperative GPCLK0 lease enforcement. The owner command is separately provisioned at `/usr/local/libexec/wsprrypi-gpio-qualification-owner` and implements `wsprrypi.gpio-qualification-owner.v1`. See the [pilot record](../VALIDATION.md#raspberry-pi-1-gpio20-pilot) for the earlier conducted GPIO20 observation. Install the matching artifacts only during separately authorized deployment.

Before an authorized live Review, prepare a private JSON fixture file with `signal_path`, `shutdown`, `maximum_indication_w`, `peak_w`, `dc_v`, and `confirm`. Use descriptive text for the conducted path and independent shutdown, and decimal strings for numeric bounds. The indication and peak bounds may be at most 0.1 W. Record a DC-free fixture with `"dc_v": "0"`. The confirmation object contains these five explicit booleans, all true for the prepared fixture.

- `conducted_gpio20_fixture_through_16ma_all_ten_carriers` for GPIO20 or `conducted_gpio4_fixture_through_16ma_all_ten_carriers` for GPIO4
- `meter_437b_3125u22346_and_8482a_my41094127`
- `meter_prepared_cal_at_99_percent_and_power_ref_off`
- `rf_off_other_apps_closed_ready_for_supervised_zero`
- `independent_shutdown_ready_operator_present`

```console
python -m hp437b.pi1_sweep review --gpio 20 --fixture tmp/pi1-fixture.json --output tmp/pi1-review.json
python -m hp437b.pi1_sweep start --review tmp/pi1-review.json --authorize REVIEW_AUTHORIZATION --output tmp/pi1-capture
```

For the separately authorized GPIO20 pilot, use `review --pilot` and the `pilot` action. This scope permits one tone at 475,700 Hz and nominal 2 mA, followed by group and owner release. The same native matrix admission verifies the owner before the pilot. Its capture and report have one requested point.

```console
python -m hp437b.pi1_sweep review --pilot --gpio 20 --fixture tmp/pi1-fixture.json --output tmp/pi1-pilot-review.json
python -m hp437b.pi1_sweep pilot --review tmp/pi1-pilot-review.json --authorize REVIEW_AUTHORIZATION --output tmp/pi1-pilot
```

Review uses one read-only SSH request, compares all 80 native plans against the selected correction, and exposes each refusal. The request has a 15-second deadline. The budget rounds the slowest measured cold request on `wspr1` (9.31 seconds) up to 10 seconds, adds two seconds of connection reserve, and includes the owner's three-second matrix budget. The signed Review has no wall-clock expiry. It binds the scope, target boot, executable, station state, fixture, and correction, and its authorization is consumed at run admission. A changed source or matrix requires a new Review. Start establishes two independent authenticated SSH connections before the initial source guard. Each handshake has a fixed 12-second limit within run preparation. Subsequent exchanges use the existing operation deadlines, and a lost connection fails the exchange without cold fallback. Stop and its confirmation use the separate connection. Start revalidates the matrix, runs a supervised ZERO with RF off, and takes three signed RF-off readings before requesting a tone. Each point verifies numeric CAL FAC from the 8482A certificate, takes up to three settling readings, and retains two distinct TR1 readings. The owner arms a 50-second cutoff before native enable, with 1.5 seconds reserved for cleanup. The Review records the run budget.

The bench operator remains available to use the documented independent shutdown. A lost or ambiguous owner receipt can leave a durable owner or meter recovery marker. Reconcile the actual hardware state and retain the evidence before removing a marker. Preserve a sealed partial capture for reporting and obtain a fresh Review and explicit Start for another attempt.

## Owner integration

The consumer uses the Mac's existing `wspr1` SSH alias for `wspr1.local` with strict host-key checking and batch authentication. The bench account invokes the fixed `/usr/local/libexec/wsprrypi-gpio-qualification-owner` through noninteractive `sudo`. Review uses one JSON request on stdin and one reply on stdout. Start uses two authenticated `--runtime-stream` connections with one compact, newline-delimited request and reply at a time on each connection. Replies echo `contract`, `operation`, `call`, and `request_sha256` (the SHA-256 of the actual input bytes), plus a `receipt` object. Contract field validation lives in `pi1_owner.py` and `pi1_sweep.py`.

| Operation | Authority and required behavior |
| --- | --- |
| `review_matrix` | Observe model, backend, normal unit, boot, station and executable identity, and selected correction before and after planning all 80 carriers and drives. Returns the source and ordered admissions, including native refusals. |
| `review`, `admit` | Recheck identity and the exact native carrier plan at runtime. |
| `claim`, `admit_matrix` | Reserve the device-wide bench lease and pad bank, persist recovery state, take an original drive/hysteresis/slew snapshot, and verify the complete matrix again before ZERO. |
| `open_group`, `close_group` | Launch an isolated IPv4 loopback process with immutable selected GPIO and drive settings, a bounded lifetime, and no ancillary outputs or scheduled transmissions. On close, confirm native GPCLK idle, both GPIO pins in input mode, pad restoration, and process exit. |
| `reserve`, `start`, `status`, `stop` | Issue and record a short-lived reservation before Start. Bind the request, plan, and finite lifetime to the unique process and generation. Enforce cutoff before GPCLK can enable, verify native active pad/clock state, and serialize identified Stop with Start, including when the Start reply is lost. A Stop before Start acceptance must prohibit a later start of the same request. |
| `lookup`, `release` | Resolve lost replies by original identifiers without replaying Start. Confirm native output inactive, bank restored, and lease released with the normal service still inactive and disabled. Reconcile or keep the Pi-local pending record when a result is unknown. |

The owner binds receipts to the host's device and boot and to the run. The owner must verify the boot, build, executable, clock selection, and original station configuration at each admitted transition. Reported realization bounds are mathematical and must be within 1 Hz of the requested carrier with the same rounded CAL FAC throughout. This consumer freezes one selected correction per Review. The owner must preserve and independently verify native inactivity and pad restoration on connection loss or missed deadlines, protect against other local bank users, and avoid overwriting an external pad change. The one-second Status budget for each sample bracket requires confirmation on `wspr1.local` before acquisition. Each pin requires its own conducted fixture, Review, authorization, and physical qualification. Historical sealed GPIO20 captures remain readable with their original evidence rules.
