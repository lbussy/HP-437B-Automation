# WF-CATALOG-01: Transmitter test catalogue

Definition v1, November 12, 2026. **Catalogue and priorities defined.** [WF-02 now has a synthetic implementation](SUSTAINED-STABILITY-V1.md); its physical POWER REF integration/exercise and the other new implementations remain open. WF-01 remains the only physically exercised workflow. This document defines the recommended next work, its reports, and useful synthetic/POWER REF development paths. It changes no logger behavior and starts no hardware operation.

## Recommended order

Keep the existing **RF Output Power Test** page title. The **Test** row names the selected test below. Each run is human-started and produces a deterministic report; AI/provider automation remains deferred.

| Priority | ID and test | Question answered | Develop without a transmitter | Later transmitter requirement |
| --- | --- | --- | --- | --- |
| 1 | WF-02: Sustained output stability | How much does measured output change during a finite transmission? | Synthetic ramps/steps/gaps; POWER REF time series at one fixed condition | Prepared continuous transmission into a rated fixture; source control or supervised manual operation |
| 2 | WF-03: Transmission-cycle repeatability | Does each separate transmission return to the same sustained power? | Synthetic cycle plateaus; slow POWER REF off/on cycles | Bounded key/unkey control or timestamped manual acknowledgements; validated dwell and duty limits |
| 3 | WF-04: Output power versus setting | Does the transmitter deliver the requested power at each setting? | Synthetic multilevel plateaus and target errors; POWER REF supplies a single-point acquisition rehearsal only | Recorded power-setting control/acknowledgement and rated output path |
| 4 | WF-05: Output power versus frequency | How consistent is output across selected frequencies/bands? | Synthetic frequency points, factor/path tables, and missing points; POWER REF supplies one nominal 50 MHz anchor only | Recorded tuning control/acknowledgement; sensor factors and fixture loss at each frequency |
| 5 | WF-06: Supply-voltage sensitivity | Does output change as the transmitter supply changes within its allowed range? | Synthetic voltage/power pairs; no POWER REF voltage-sensitivity experiment | Suitable controlled supply, independently observed voltage, DUT supply limits, and RF fixture |

WF-02 was selected first because it adds useful analysis and reporting with the least new control machinery; its synthetic implementation is now available, with POWER REF integration/exercise next. WF-03 then adds repeated-condition orchestration. WF-04/05 add reusable point tables and comparisons; WF-06 is a later extension because it needs another instrument/control path. These priorities are engineering recommendations within the owner's request, not adopted DUT acceptance limits.

## Measurement scope and references

The [437B manufacturer description](https://www.keysight.com/us/en/product/437B/high-performance-single-channel-average-power-meter.html) identifies a single-channel average-power meter. The current [8482A](https://www.keysight.com/us/en/product/8482A/power-sensor.html) covers 100 kHz–4.2 GHz. The [sensor manual](../../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf#page=15), printed page 15, describes the A-model range, sensor loading, and frequency-dependent calibration factors; the [compatibility reference](../SENSOR-COMPATIBILITY.md) records the 8482A measurement range as 1 µW–100 mW. That range is not a damage rating or a safe direct-transmitter connection policy. Use the individual sensor's manual/label, peak/DC limits, and prepared path to establish operating limits.

The [437B operating manual](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=19), printed pages 1-9–1-10, provides conditional settling/specification context. The [adopted measurement policy](../validation/MEASUREMENT-POLICY.md) records actual sampling limits. Neither a one-second requested interval nor a timestamped reading establishes one-second independent response or resolves an RF switching edge. Meter filtering, sensor response, range changes, and source settling affect every time-series test.

These tests measure power arriving at the sensor. A broadband power sensor does not isolate the fundamental from other RF energy in its response band. Frequency is supplied by source configuration or an independent instrument; the meter does not measure it. There is no automatic conversion of these tests into harmonic, frequency-accuracy, PEP, or modulation-quality measurements.

POWER REF has one nominal frequency/level (50 MHz/1 mW in the existing [WF-01 definition](POWER-REFERENCE-V1.md)). It can exercise acquisition, drift calculations, and slow cycle sequencing. It cannot generate a power-level sweep, frequency sweep, or transmitter supply experiment. Its stability run measures the combined reference/meter/sensor path, and its cycle run measures that path's repeatability. Neither is a transmitter result or independent reference calibration.

## Shared workflow contract

Every implementation below must extend the workflow/report layer while preserving the ordinary `hp437b log` behavior, defaults, CSV/sidecars, and existing healthy/failure shutdown semantics. Do not reinterpret sealed WF-01 captures as a new test. New workflows need their own versioned definitions, captures/importers, calculations, reports, and acceptance records; the existing WF-01-specific importer/renderer is not a generic transmitter runner today.

### Inputs and provenance

Before capture, resolve and retain:

- Workflow ID/version, mode, unique run ID, operator, DUT model/name/serial, test purpose, UTC time, and software identity. Unknown identity remains unknown; synthetic identities are fictional and conspicuously labeled.
- Ordered condition IDs and their requested frequency, power setting, signal/modulation mode, source state, dwell, acquisition window, and finite budgets. Record requested, acknowledged, and independently observed conditions separately. An acknowledgement is not independent measurement.
- Sensor/meter/adapter identity and settings, calibration/zero preparation, warm-up history, sensor factors, measurement point, fixture drawing/description, attenuation or coupling loss versus frequency, applicable ratings, and known issues. Preserve the current meter's supply discrepancy in provenance.
- External source control mode: `manual` with explicit operator acknowledgements, or a future named/validated driver. No arbitrary shell commands or unvalidated radio-control strings in a run definition. Reused POWER REF control remains restricted to its prepared direct-reference mode.
- Supplied criteria and decision rule, with units, source/revision, comparison point, coverage requirements, and any uncertainty/guard-band policy. Defaults below are proposed development profiles, not transmitter specifications. No limits means **Acceptance: NOT EVALUATED**.

Sensor calibration factors and fixture corrections are different quantities. Preserve raw sensor readings and corrections already applied by the meter. If positive fixture insertion/coupling loss is `L_dB`, then `P_DUT_W = P_sensor_W × 10^(L_dB/10)` at the explicitly defined upstream plane. Apply that correction once; retain both values, loss data, and uncertainty basis. Do not subtract a baseline or reapply a sensor factor silently. Without supported loss data, report sensor-input power only; do not issue an upstream-power verdict.

### Sequence, bounds, and failure behavior

Validate the complete definition, output reservation, path ratings, source-off/prepared state, settings, and control availability before enabling RF. Record a source-off baseline before RF and again afterward where available. Baseline means remain descriptive, may be signed, and are not a remote zero operation, leakage specification, or automatic subtraction.

Use absolute W with REL/offset/duty correction off for the initial versions. Preserve factors and record/verify settings. Serialized acquisition and status checks follow existing transaction semantics; a late/invalid reply is not a successful sample. Settling samples are retained and labeled separately from analysis plateaus. A fixed wait is a declared observation allowance, not proof of settling.

The draft finite profiles below request one-second sampling and a ten-second operation timeout. Actual sampling/coverage and averaging settings must be reported. Stage supervisors bound the declared acquisition-start windows, reserve time for the final pending transaction and cleanup, and enforce the whole-run ceiling. Timeout/disposal allowances consume that ceiling. Stop before a new stage if the remaining budget is inadequate; no automatic retries or run extension. Per-transaction and acquisition-stage budgets must be specified and validated when each runner is implemented.

| ID | Proposed finite development profile | Whole-run ceiling |
| --- | --- | --- |
| WF-02 | Three pre/post baseline samples; 20 s initial observation allowance; 1,800 s acquisition-start window, partitioned into six 300 s bins | 2,100 s |
| WF-03 | Three baseline samples; five cycles, each with 20 s on observation allowance, 30 s on acquisition window, 20 s off allowance, and three off samples | 900 s |
| WF-04 | Three baseline samples before/after; at most five ordered settings; each point has 20 s observation allowance and 30 s acquisition window | 900 s |
| WF-05 | Three baseline samples before/after; at most five ordered frequency points; each point has 20 s observation allowance and 30 s acquisition window | 900 s |
| WF-06 | Three baseline samples before/after; at most five ordered voltage points; each point has 20 s observation allowance and 30 s acquisition window | 900 s |

Manual acknowledgements have a proposed 60 s deadline per action, included in the whole-run ceiling. The ceilings take precedence if acknowledgement time leaves inadequate acquisition/cleanup budget. These profiles are design inputs; expose no new CLI defaults now. A transmitter profile must be revised before use if its rated duty cycle, cooling, switching, or settling needs differ. The POWER REF observation allowance comes from prior practice, not a universal instrument or transmitter response specification.

On cancellation, failed condition verification, invalid sample, transport error, instrument error, or storage failure, stop progression and preserve partial evidence. In known healthy protocol state, attempt the declared bounded source-off action and verify it, then perform healthy closure. With failed/uncertain communication, retain the existing no-blind-command/no-retry policy and mark source/local state unknown. Meter-local restoration does not turn off an external transmitter. An external driver needs its own independently justified shutdown path; manual mode requires operator source-off confirmation. Until implemented and accepted, no external transmitter is automatically keyed by this catalogue. Reporting failure never reopens a source or repeats capture.

### Report and verdict

Produce a one-page **RF Output Power Test** with a test-specific subtitle/row, DUT, operator, capture time, conditions, pre-RF baseline, primary result, compact plot/table, and acceptance outcome. Keep Equipment traceability, Report Harness, and Record in that footer order. Full conditions, formulas, source evidence, factors/losses, uncertainties, exclusions, failed points, and cleanup outcomes belong in machine-readable results and the technical appendix. Compare only compatible measurement planes and units.

Separate **execution** (completed/failed/interrupted), **coverage** (points/windows/cycles available), and **acceptance**. A failed or incomplete execution cannot receive an overall DUT pass; valid individual points can retain their own comparisons. Missing/invalid data stay missing, with reasons, not zeros, interpolation, or hidden exclusions. Mean power is computed in linear W; dBm is derived only from positive power. The result is not automatically a time-weighted energy measurement when receipt spacing varies.

## WF-02: Sustained output stability

**Purpose:** characterize slow output drift during a finite steady-condition transmission. This is stability of the recorded measurement path under stated conditions, not attribution of all change to the transmitter or a cold-start warm-up test.

**Sequence:** baseline → source on/condition verification → declared settling allowance → finite plateau time series → source off/verification → final baseline/cleanup. Preserve observations during settling outside the primary statistics. POWER REF uses the existing prepared direct path and a new explicit finite-run definition; a transmitter uses the future source boundary described below.

**Analysis:** mean/min/max/p2p W over valid plateau samples; first-bin and last-bin sample means; endpoint change W and percent relative to a positive first-bin mean; unweighted least-squares slope versus actual monotonic receipt time in W/min; per-bin counts, achieved spacing, and gaps. Do not bridge missing bins. Endpoint drift is unavailable if either endpoint bin is absent; slope needs at least two distinct valid timestamps. Percent is unavailable for nonpositive reference power. Slope and bin means describe sampled readings, not a sensor-independent transient response. No universal averaging-based sample count or absolute-accuracy claim is inferred.

**One-page result:** mean output, first→last bin change, slope, observed span, coverage, and power-versus-time plot. Supplied criteria may constrain endpoint drift or a band around a stated target, with explicit bin/data coverage and uncertainty policy. Missing required bins prevents an overall pass.

**Development:** synthetic constant, ramp, step, one missing endpoint bin, irregular sampling, and out-of-band drift cases. A later supervised POWER REF run exercises the real sequence; it does not establish transmitter thermal drift.

## WF-03: Transmission-cycle repeatability

**Purpose:** compare sustained output after separate source activations. This measures cycle-to-cycle steady output, not keying delay, overshoot, pulse shape, or PEP.

**Sequence:** baseline → repeat a finite numbered on/settle/capture/off/verify/off-baseline cycle → final cleanup. Record commanded and observed state transitions and each cycle's retained sample interval. The off dwell/acquisition is part of the condition, and the transmitter's permitted duty cycle must be checked before choosing cycle timing. Never count retries as new successful cycles.

**Analysis:** each cycle's valid plateau count/mean/range; equal-weight mean of completed cycle means; max-minus-min cycle mean W and percent of positive mean; optional standard deviation of at least two cycle means using the sample (`n−1`) definition. Show off baselines separately. An incomplete cycle remains incomplete and does not disappear from the denominator of requested cycles; unequal acquisition counts do not silently give longer cycles more weight.

**One-page result:** requested/completed cycles, cycle mean table or plot, cycle spread, and final source state. Criteria may bound cycle spread and individual cycle output, with a required number of completed cycles. Sensor off readings alone do not establish transmitter leakage performance.

**Development:** synthetic repeatable and shifted cycles, one missing/failed cycle, unequal counts, source-off failure, and cancellation. Slow POWER REF switching can later exercise the sequence without a radio; do not claim fast switching or transmitter-keying qualification.

## WF-04: Output power versus setting

**Purpose:** compare requested/declared transmitter power settings with measured steady output. A percentage setting does not imply the same percentage of rated watts; record an explicit target mapping only when a specification supplies one.

**Sequence:** source off/baseline → ordered points → source off/final baseline/cleanup. Each point records setting command/acknowledgement, declared fixed frequency/mode, source-on verification, settling observations, and plateau capture. Setting changes while keyed are forbidden unless the selected transmitter/control path explicitly permits them; otherwise unkey and acknowledge the next setting before enabling RF. Preserve order and any repeated reference point rather than sorting away hysteresis/history.

**Analysis:** sensor-input and, where supported, corrected DUT-plane mean/range per point; `error_W = measured_W − target_W`; percent error for positive targets; dB error for positive measured and target powers. Include missing points and evidence for requested versus acknowledged settings. No generic transmitter linearity claim follows from a few points or an assumed percentage-to-watts mapping.

**One-page result:** setting/target/measured/error table and compact target-versus-measured plot. Use supplied per-point tolerances and decision rule. Without target mapping, report the observed transfer table only.

**Development:** synthetic proportional, compressed-at-high-setting, nonmonotonic, missing target, invalid correction, and failed point cases. POWER REF tests one fixed point's acquisition/report wiring only; any multilevel sweep remains synthetic until a suitable controllable source is present. Changing meter units, CAL FAC, or offset is not a source-level sweep.

## WF-05: Output power versus frequency

**Purpose:** compare steady output at specified operating frequencies, holding the declared transmitter power setting/mode constant. This measures output variation across declared frequency points, not spectral flatness within a modulated channel or frequency accuracy.

**Sequence:** baseline → unkey/tune/acknowledge → verify frequency-dependent sensor factor and fixture correction → key/settle/capture per ordered point → off/final baseline/cleanup. Tuning or changing factors must not happen during a pending read. A future runner must define and test factor selection/readback rather than assuming current WF-01 automatically manages a table. If supported factors or loss data are unavailable, stop that point or explicitly report sensor-plane observations without a corrected DUT comparison. Never invent interpolation outside a documented factor policy/range.

**Analysis:** means/ranges and optional target error per frequency; maximum/minimum corrected positive mean and their ratio in dB, `10 log10(max_mean/min_mean)`. Show frequency and correction provenance per point. Unknown frequency is not a valid sweep point. Report observed spread over captured points only; incomplete coverage cannot satisfy an all-band criterion.

**One-page result:** frequency/output table, output-versus-frequency plot, worst observed point/spread, and coverage. Frequency labels say **declared** or identify the independent frequency measurement source. Criteria belong to the selected DUT/bands and stated measurement plane.

**Development:** synthetic band droop, unequal factor/loss data, repeated anchor, missing band, out-of-range frequency, and absent frequency evidence. POWER REF supplies only the nominal 50 MHz anchor; moving its frequency label or changing a calibration factor cannot create a sweep.

## WF-06: Supply-voltage sensitivity

**Purpose:** compare output across permitted transmitter supply voltages while frequency, setting, and signal mode stay fixed. This is a future equipment-assisted workflow, not an experiment on the 437B supply or POWER REF circuitry.

**Sequence:** prepared rated RF path and DUT supply limits → source-off baseline → bounded voltage points with source state controlled according to DUT requirements → observe actual voltage at the declared location → settle/capture → unkey/verify → declared supply restoration and cleanup. Supply control, voltage observation, current limit, and restoration need their own driver/procedure acceptance. Requested voltage without observed voltage supports only a labeled commanded-voltage comparison.

**Analysis:** RF mean/range per observed voltage, relative change against the declared nominal-voltage point, and an endpoint secant W/V when distinct endpoint voltages exist. Do not call the secant a universal regulator slope or measure DC-to-RF efficiency without synchronized, validated DC power measurements.

**One-page result:** voltage/output table and plot, nominal-point comparison, observed voltage coverage, and restoration outcome. Criteria and operating envelope come from the DUT/test specification.

**Development:** synthetic droop, missing voltage readback, missing nominal point, unsafe requested voltage rejected before activation, supply-control failure, and restoration failure. No physical work is blocked by the meter exchange, but this particular experiment needs a suitable DUT and supply.

## Synthetic worked inputs

The committed [fictional fixture](examples/transmitter-test-catalog-v1.json) provides short, transparent calculation examples for all five definitions. Its rows are deliberately sparse, not complete executions of the proposed profiles. All identities, conditions, unity sensor-factor assumptions, fixture losses, and values are synthetic; fixture loss is already specified separately from sensor factors. No real equipment calibration, uncertainty, limits, or compliance is asserted.

| Fixture | Expected descriptive result |
| --- | --- |
| WF-02 | Four sampled 60 s-bin representatives: 1.000→1.030 mW; linear mean 1.015 mW; endpoint change +3%; slope +0.010 mW/min |
| WF-03 | Three cycle means: 1.000, 0.990, and 1.010 mW; equal-cycle mean 1.000 mW; cycle spread 0.020 mW (2%); sample standard deviation 0.010 mW |
| WF-04 | With fictional 30 dB loss, sensor means 1.0/4.8/9.5 mW become DUT-plane 1.0/4.8/9.5 W versus targets 1/5/10 W; errors 0/−4/−5% |
| WF-05 | Fictional corrected band means 4.8/5.0/5.1/4.9/4.7 W; observed spread `10 log10(5.1/4.7)`, approximately 0.35472 dB |
| WF-06 | Fictional observed 11/12/13 V with 4.5/5.0/5.2 W; changes against 12 V: −10/0/+4%; endpoint secant 0.35 W/V |

These examples have no DUT limits, so their acceptance result is **NOT EVALUATED**. Implementation acceptance must add independent numeric oracles, threshold boundaries with supplied decision rules, absent limits, insufficient coverage, signed baselines, wrong units, source-state mismatch, cancellation/timeout/storage faults, and source-preservation/inventory checks. Test the proposed driver through fakes before any hardware run; synthetic passes and retained WF-01 re-analysis do not accept a new physical workflow.

## Implementation milestones and completion boundary

| Work item | Deliverable / acceptance boundary | Current status |
| --- | --- | --- |
| WF-CATALOG-01 | Prioritized definitions, report contracts, synthetic worked inputs, realistic POWER REF scope, and tracked implementation work | ✅ Definition complete |
| WF-02 | [Synthetic drift runner, analysis/report, and independent checks implemented](SUSTAINED-STABILITY-V1.md); separately recorded supervised POWER REF integration/evidence remains open | ⏳ Synthetic complete; physical follow-up open |
| WF-03 | Versioned cycle runner/report, partial-cycle/final-state checks, then separately recorded slow POWER REF evidence | ▧ Open |
| DUT-CTRL-01 | External/manual source contract, bounded key/unkey/setting acknowledgements, safe fixture/corrections, single-point transmitter capture/report, and source shutdown evidence | ▧ Open; prerequisite to physical transmitter workflows |
| WF-04 | Point-table power-setting workflow, targets/decision rules, reports, and fake-control acceptance; physical evidence only with a prepared source | ▧ Open |
| WF-05 | Point-table frequency workflow, factor/loss selection policy, reports, and fake-control acceptance; physical evidence only with a prepared source | ▧ Open |
| WF-06 | Voltage-control/observation/restoration contract, synthetic acceptance, and later DUT/supply integration | ▧ Later priority |

DUT-CTRL-01 should reuse the single-point acquisition/report concepts of WF-01, while providing a separate external-DUT identity and source boundary. It must never toggle POWER REF for a transmitter experiment or reuse a reference-only capture as transmitter evidence. Software design and fake-control acceptance can proceed now; real transmitter/fixture ratings and control details are required only for the corresponding physical test.

Harmonics/spurious emissions, occupied bandwidth/modulation quality, frequency accuracy, PEP/fast keying transients, and return loss/VSWR remain outside this meter-only catalogue. They require appropriate selective, time-resolved, frequency, or directional measurement hardware and separate workflows. Sequential amplifier gain/insertion-loss comparison is another possible later test, but one channel requires a justified stable-source/reconnection procedure or additional measurement paths; it is not a simultaneous two-channel measurement.

## Definition verification

All five committed fictional examples were checked with independent arithmetic for linear means, endpoint drift, actual-time slope, equal-cycle statistics, fixture-plane conversion, target errors, band spread, and voltage comparison. Markdown links/anchors/tables and the five original PDF checksums passed, as did `git diff --check`. A consistency review checked incomplete coverage, missing/negative values, correction application, external-source shutdown, sampling limitations, and the distinction between definitions, simulations, and physical evidence. No application code, logger behavior, dependency, capture, or hardware state changed. The existing software suite was not rerun for these documentation/fixture-only changes.
