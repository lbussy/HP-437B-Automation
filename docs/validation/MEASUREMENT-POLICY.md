# Initial supervised measurement and logging policy

Status: ✅ DEC-02 complete for the initial reference-bench profile, November 11, 2026. The owner selected the existing bench profile: watts, automatic range/filter, one-second requested intervals, finite five-minute runs, and explicit reporting of slower achieved sampling. This is an explicit run policy; production CLI defaults and normal logging behavior are unchanged. The owner directed completing available Phase 3 preparation without further input before the replacement meter arrives.

## Application boundary and settings

The initial application is supervised absolute-power readback and finite CSV logging on Mac and Pi through the identified USBGpib V2, firmware V2.4, Anker USB-C cable, and pinned open-source stack. Use the prepared internal POWER REF path for a known source-on state and a source-off baseline. No external radio, new RF wiring, or external-source performance claim is required for this initial profile. A future radio/frequency/path introduces a separate setup and correction policy; it does not block completion of this declared reference-bench profile.

| Setting | Adopted policy |
| --- | --- |
| Units | Absolute linear W in CSV; convert to mW/µW only for presentation; preserve negative and zero readings |
| Range/filter | Automatic, as established and recorded in each physical setup; retain effective range/filter from fresh SM, rather than forcing the original meter's codes onto a replacement |
| Requested interval | 1 second; serialized acquisitions never overlap, and overruns rebase the schedule without catch-up bursts |
| Short run | 3 CSV acquisitions, plus the separately recorded setup acquisition excluded from CSV count |
| Sustained run | `--duration 300`, with actual row count/timing reported; duration bounds acquisition starts, not a promise of 300 rows or 1 Hz |
| Normal operation timeout | 10 seconds; an expired pending read additionally permits up to 1 second of failed-read shutdown, then existing bounded worker disposal |
| Source | Internal nominal 50 MHz/1 mW only for the prepared reference-on cases; POWER REF off for interruption and timeout cases |
| Corrections | Absolute mode, duty/offset/REL off; retain and explicitly record numerical calibration factors instead of silently changing them |
| CSV/provenance | Existing schema: session/sequence, UTC receipt, monotonic elapsed/overrun, numeric value, units, row status/error, and raw hex, with setup/identity/settings/dependencies/cleanup in the sidecar |
| Ownership/files | One explicit controller/session; new output filename each run; existing CSV/sidecar refusal before opening hardware |
| Failure | Preserve failed/partial data, leave failed/uncertain Instrument blocked, dispose worker, and do not silently retry a sample or send blind restoration commands |
| Healthy shutdown | TR3 then negotiated USB488 GTL, with independent free-run/numeric display and actual local confirmation in physical qualification |

The current meter's source-off range 11/filter 17 produced approximately 7.43-second sample spacing despite the one-second request; reference-on sustained logs achieved approximately one-second spacing. Record both behaviors. Source-off readings below the sensor's normal measuring range are baseline/communication observations, not calibrated low-power measurements. The filter/range selection for a replacement is a setup gate; no new remote range/filter setters were qualified by this policy.

For each prepared path, record warm-up, meter/sensor identity, nominal frequency/power, signal path, attenuation/load, zero/CAL history, and applicable factors. The current sensor is 8482A SN MY41094127, label REF CAL FACTOR 99%; its cable connects to SENSOR and its Type-N RF input connects directly to front POWER REF. The nominal 1 mW reference is inside the documented 8482A 1 µW–100 mW measurement range ([operating manual Table 3-1, PDF 35](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=35)). No attenuator or external source is involved. This range statement does not substitute for maximum-input limits or authorize another RF source.

The recorded CAL REF CF 99% and active measurement CAL FAC 100% serve different purposes. Retaining CAL FAC 100% reproduces the existing readback-consistency profile; it is not a claim that 100% is the sensor's measured calibration factor at every frequency. Use the actual sensor's label/certificate when preparing the replacement, and record the selected factors and their provenance. Absolute RF accuracy, independent reference uncertainty, and performance at a future radio frequency require their own evidence.

## Sequence and acceptance

1. Confirm actual identity/resource, exclusive access, prepared source/path, applicable factors, and intended source state. In normal logging the CLI identifies, issues RL0/LN, consumes setup TR2/read, then reads fresh SM; do not insert SM or other ASCII commands during a pending triggered response. Changed corrections, wrong units/source, or instrument errors stop acceptance even if a CSV was created.
2. Use the three-row run before sustained logging. Require exactly three valid measurement rows, correct raw/value/unit/session correspondence, setup exclusion, completed metadata, accepted cleanup, and separate free-run/local evidence.
3. For the 300-second run, require valid sequential rows, preserved raw/unit/session data, consistent monotonic timing, a finite start window, completed metadata, and cleanup. Inspect actual spacing, overruns, row count, and run coverage; record performance limits rather than declaring 1 Hz from the requested interval. The original Mac/Pi reference cases yielded 299/300 valid rows respectively; those are observations, not replacement row-count requirements.
4. Compare one held Python sample with the physical display in matching units, using at most one observed display increment. The tested reference display increment was 0.001 mW; establish actual resolution before the replacement capture and revise the tolerance first if it differs. A reading from a different time is not a held-sample agreement result.
5. Reversible W/dBm/W and OC0/OC1/OC0 checks use the existing preselected consistency tolerances: 0.02 dB for conversion, 0.002 mW for restored W/reference-on repeat, and off magnitude below 1% of the reference-on baseline with fresh source-off status. These check conversion/restoration/switching consistency, not absolute source accuracy or leakage specifications.
6. Source control is explicit and separate from ordinary logging. The generic logger preserves source state. A named healthy reference procedure uses the verified OC0 final-off plan and confirms it; uncertain transfers skip blind source-off/local commands and require the named operator recovery route. Physical fault cases begin with POWER REF verified off.
7. Between-read interruption, file protection, and the one original forced read deadline are separate diagnostic cases with their own finite budgets. They do not change normal settings. Timeout acceptance requires preserved failure/uncertainty, actual abort evidence, fresh-session reconciliation, and final physical local state; a late result never becomes a successful sample.

After healthy reference activation, allow the previously used twenty-second initial observation window and record behavior; that interval is not a demonstrated universal settling specification. Unstable or changed conditions stop the comparison before collecting a passing sample; do not widen tolerances after seeing a result. Normal source-on work remains supervised. A sustained case has a 420-second outer allowance covering setup, the 300-second start window, final acquisition, and cleanup. Short logging has a 90-second allowance; reversible control retains 180 seconds plus 30 seconds for cleanup. A display hold is at most 60 seconds. Diagnostic setup may use the previously declared 30-second operation budget, with the original first-CSV timeout deliberately shortened to 0.5 seconds under a separate 90-second fault ceiling and 120-second reconciliation allowance. Stop at the first failed gate; do not add attempts without a revised recorded scope.

## Explicit limits and remaining work

Remote zero/CAL, tables, binary restoration, preset/reset/self-test, GET/SRQ/serial polling, broader bus control, already-wedged software-only repair, and unattended continuation remain excluded or guarded. Instrument-generated overrange/error responses retain software parsing/error-row tests; no unsafe power/overload test or new physical invalid-response case is implied. The reference-profile failure evidence covers the named interruption and timeout cases only. Accepting this policy does not close the replacement qualification gates.

The [replacement procedure](REPLACEMENT-ACCEPTANCE.md) applies these settings to the actual arriving meter and sensor on both hosts. Existing passes remain associated with original meter SN 3125U33223 and its documented supply discrepancy.
