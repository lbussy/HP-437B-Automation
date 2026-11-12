# Hardware validation plan

Updated November 12, 2026. This document covers software/adapter interaction checks and measurement provenance, not certification of the meter. The [project scope](PROJECT-SCOPE.md) and [current checklist](RELEASE-CHECKLIST.md) govern application acceptance. The [batch plan](validation/PHASE-3-PLAN.md) and run/review records preserve historical scoped evidence. Replacement arrival is not an overall software gate.

Workflow, provenance, analysis, and report acceptance (WF-01/PROV-01/REPORT-01/E2E-01) can proceed using synthetic and retained bench data within their limits. Additional physical checks are needed for particular new hardware interactions or measurement claims, not for every software task. Derive actual commands and zero/calibration procedures from the [manuals](EQUIPMENT.md) and actual setup.

## Record the environment

Record meter and sensor identification, sensor calibration information, adapter model/firmware, host model/architecture/OS, Python and released dependency versions, USB cable, GPIB address, termination settings, and measurement configuration. Distinguish installed releases from unreleased backend changes.

The [individual calibration records](EQUIPMENT.md#individual-calibration-records) cover meter SN 3125U33223 and sensor SN MY41094127. The user reported on November 11, 2026, that the seller/calibrator confirmed the meter's documented +5 V supply discrepancy was unacceptable, and plans to exchange it after a few development steps. Do not count that supply entry as passing. Associate any interim development results with the current meter and its known discrepancy. Record the replacement meter's identity and applicable calibration records, and check the setup/compatibility assumptions relevant to its use. This equipment follow-up does not block software development. Use correction factors for the sensor actually in use. Certificate results do not establish backend compatibility or replace local bench validation.

## Required checks

1. Discover and open the adapter through PyVISA-py using the USBTMC path. Record the resource identifier; use documented 437B commands rather than assuming SCPI examples apply.
2. Read power and compare with the front panel using matching units and correction settings. This comparison checks readback, not absolute calibration accuracy.
3. Change a reversible configuration setting, verify the effect, restore it, and confirm return to local control.
4. Exercise the trigger and status operations actually required by the chosen measurement sequence. Record which operations were tested and which remain unsupported or untested.
5. Verify response termination, the declared bounded failure/recovery cases, and clean shutdown. Distinguish software invalid/overrange parsing tests from any physically required case; the adopted internal-reference profile excludes unsafe overload testing and does not claim instrument-generated invalid/overrange evidence.
6. Run sustained CSV logging for an agreed duration and interval. Check timestamps, explicit units, missing/invalid samples, interruption handling, and output completeness. Record measured behavior without claiming a rate from configuration alone.
7. For Pi operation, verify Mac access and file retrieval. Repeat relevant checks on every additional host before claiming support there.

## Backend decision

PyVISA-py remains provisional until required checks pass. An unrelated missing feature need not disqualify it. If a required operation fails, isolate configuration issues from reproducible defects, then decide whether to fix the backend or adopt another transport/backend. R&S VISA is a proprietary fallback requiring a separate adoption decision.

## Results to retain

For each validation run, record date, operator, environment, exact procedure/commands, expected and observed behavior, pass/fail for each required check, and remaining limits. Raw local measurements belong in ignored `data/` or `output/logs/`; deliberately selected, reviewed evidence may be added under `docs/validation/` when available. No passing result is implied by this document.

## Capability-by-capability qualification

Use the [coverage matrix](inventory/COVERAGE.md) to select capability IDs and their linked prerequisites, expected results, and source questions. Record implementation, software-test, Mac, and Pi status independently. Resolve ambiguous reset/self-test, table-edit, binary-restore, and status lifecycle behavior before accepting those APIs.

The [bus evidence](inventory/GPIB.md#transport-evidence-profiles) identifies limitations in released PyVISA-py 0.8.1. Demonstrate the selected released solution for serial polling, device clear, local restoration, and any required bus trigger or SRQ events. Follow the documented trigger/calibration ordering: await completion or use a verified serial-poll route, because an incoming ASCII program command can abort unfinished work.

## Phase 2 handoff

Use the [installed software and CLI](SOFTWARE.md) and [Phase 2 review](PHASE-2-REVIEW.md) to prepare the first hardware batch. Scripted transports, IPC timeout tests, and synthetic demo output establish software behavior. Physical results belong in the Mac/Pi columns after identifying the actual meter, sensor, adapter, firmware, OS, and dependency versions.

## Automatic local-return follow-up

The owner requested automatic local return after normal sessions. The [versioned extension and cases](validation/AUTOMATIC-LOCAL.md) keep the pinned open-source stack and add a narrowly negotiated USB488 GTL path. Required physical acceptance distinguishes accepted USB control status from RMT off and working front-panel controls. Failed/uncertain transactions retain manual recovery requirements. No Pi or replacement support follows from a Mac current-unit result.

## Named interruption and recovery evidence

The [failure/recovery record](validation/FAILURE-RECOVERY.md) accepts between-read process-directed SIGINT and one induced in-flight acquisition timeout with subsequent manual adapter USB reconnect and fresh protocol verification on the current Mac/unit. Partial-data integrity, uncertainty blocking, no unsafe post-fault traffic, and final source-off/live-local state are recorded separately. Other fault patterns, unattended recovery, device clear, second-host behavior, and replacement acceptance are not inferred.

## Pi preflight

[Pi qualification](validation/PI-QUALIFICATION.md) records the isolated Raspberry Pi 5/aarch64 environment and passing 237-test installed-package suite, lint/format/build, CLI checks, exact runtime pins, and native libusb loading. Ordinary-user USB identification, owner local confirmation, baseline/control, short/five-minute reference logging, and CSV/sidecar hash retrieval passed under the owner-authorized permanent USB permission rule. The owner confirmed final live/local/reference-off operation after sustained logging; display agreement (0.989 mW), between-read SIGINT, and induced timeout handling passed; Pi-only reconnect failed enumeration. An expanded manual LOCAL/Mac-host-assisted return to Pi passed fresh ID/acquisition/free-run checks, with owner confirmation of final live/local/reference-off state; root cause and Pi-only recovery remain unresolved. These version/current-unit cases do not establish replacement or unattended support.

The subsequent [Pi-only recovery investigation](validation/PI-ONLY-RECOVERY.md) stopped its USB port-reset candidate after host reachability was lost following the post-timeout reset and the owner restarted the Pi. A returned reset status is not a recovery pass. Host logs and protocol reconciliation remain pending; no automatic recovery API is enabled.

Reconciled host logs show orderly restart and accepted SSH sessions before adapter unplug; no reset-caused crash is established. The separate USBTMC-clear candidate passed healthy/protocol checks but timed out after the approved fault, with host liveness retained. Manual full USB+GPIB isolation/reconnect is the next named Pi-only route awaiting owner completion; no new fault or Mac action is included.

The [P3-PI-R4 manual full-adapter isolation case](validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) subsequently passed with correct re-enumeration, new-node permissions, fresh ID/status/source-off acquisition, independent free-run, and owner live/local/reference-off confirmation. Boot identity was unchanged; no Mac move or new fault was used. Accept this named supervised Pi-only route only. The long response interval prevents a required-step or recovery-latency claim; software-only candidates, root cause, repeatability, replacement, and unattended recovery stay open.

## Integrated failed-read shutdown

The owner authorized the failure-only transport fix after the original forced-timeout/USB-only failure was reproduced. The [integrated Pi case](validation/PI-ONLY-RECOVERY.md#integrated-failed-read-shutdown-result) passed exact installed-package provenance, 261 local/installed software tests, ordinary CLI logging, one original forced deadline with actual backend abort trace, fresh ID/status/acquisition/free-run verification, and owner final live/local/reference-off confirmation. An expired dispatched read now allows up to one second for existing backend shutdown, while retaining the failed sample, uncertainty, no automatic retry, and bounded worker disposal. Normal logging code/defaults/CSV are unchanged. Already-wedged repair, other fault patterns, replacement, and unattended acceptance remain separate.

The [Mac repetition](validation/MAC-FAILED-READ-SHUTDOWN.md) subsequently passed with the same committed runtime, the declared Mac source-import origin/pins/libusb, ordinary logging, one original forced timeout, exact backend abort trace, fresh protocol/free-run verification, and owner final live/local/reference-off confirmation. Both current-unit host records now support the named failed-read shutdown route. Application acceptance now follows the workflow/provenance/reporting scope; replacement identity/setup is a separate equipment follow-up.

## Pre-arrival readiness

The [adopted initial policy](validation/MEASUREMENT-POLICY.md), [replacement acceptance procedure](validation/REPLACEMENT-ACCEPTANCE.md), and [pre-arrival evidence review](validation/PRE-ARRIVAL-REVIEW.md) complete the available preparation. Scope is supervised internal-reference/readback logging with explicit wider-operation exclusions. These records do not complete the automation/reporting product. The earlier replacement-gate policy is superseded: equipment onboarding and applicable measurement limitations are separate from workflow-to-report software acceptance.

## First application-profile acceptance

[E2E-01 / VAL-01](validation/PIPELINE-ACCEPTANCE.md) records explicit assertions and a 16-case workflow/provenance/analysis/report acceptance campaign. It completes the first WF-01 v1 software profile without new hardware I/O; equipment provenance, measurement limits, and named host evidence retain their original scopes.

## WF-04 synthetic output versus setting — November 12, 2026

[WF-04 v1](workflows/POWER-SETTING-V1.md) now implements a finite synthetic external-transmitter point sweep, sensor/DUT-plane comparisons, supplied target/loss mapping, configurable operator, reusable PROV-01 records, and deterministic HTML/Markdown/JSON reports with optional PNG/SVG. No meter, USB, native backend, RF source, or provider was accessed. Production logger, instrument/transport, existing physical workflow runners, runtime dependencies, and CLI defaults are unchanged.

Validation evidence is local and ignored under `tmp/wf04/` and `output/reports/wf04-synthetic-20261112-v2/`:

- Full regression: **814 tests passed**, including stress-enabled cases, behind `tools/offline_qa.py`; targeted WF-04 tests cover 53 cases. Subsequent presentation/strict-outcome checks also receive the targeted suite.
- Fourteen synthetic scenarios were captured and reported: nominal, compressed, nonmonotonic, missing target, missing loss, sensor plane, zero output, timeout, malformed response, complete instrument error, cancellation, source-off failure, acknowledgement mismatch, and missing point. Fresh no-plot reimports reproduced results and preserved all source bytes.
- Independent catalogue oracle: 1/4.8/9.5 mW sensor means, fictional 30 dB loss, 1/4.8/9.5 W DUT-plane means versus 1/5/10 W targets, errors 0/−4/−5%. Inclusive fictional 5% limits pass; a stricter point-specific bound fails. No limits means NOT EVALUATED. Missing corrections/targets, zero power outside the nominal measurement range, and incomplete execution cannot yield overall PASS.
- Tests verify no simulator-truth substitution, no fixture double correction, source order/unkeyed setting changes, unknown final source state after uncertain faults, no retry after failed off, retained partial/skipped coverage, evidence hashes and semantic joins, symlink/output protections, publication failure preservation, and CLI exits.
- Source distribution and wheel build passed under the offline guard. A fresh installed wheel, invoked outside the checkout without Matplotlib, generated a capture/report with full producer commit/source metadata. Optional plot tests verify actual PNG/SVG signatures.
- Every scenario's one-page sheet and the five-point repeated-anchor example were rendered for Letter and A4 (30 one-page outputs), with success and failed-source-state sheets visually inspected. The main sheet includes signed pre-RF zero, transmitter/operator/time, declared frequency/mode/plane, point results, acceptance, and final synthetic source state. Full evidence remains in the appendix.
- Ruff, formatting, Markdown links/anchors/tables, five publisher PDF hashes, and `git diff --check` passed. New reporting tests are included in the existing Python 3.11/3.14 hosted reporting matrix, and Delivered to `devel` at `db45dbc`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43313033157).

The generator creates virtual sample evidence directly; it does not exercise production `Instrument`/`collect` or reproduce actual native timeout behavior. This evidence establishes synthetic orchestration/analysis/report behavior only. Physical multi-level transmitter work remains **DUT-CTRL-01**; POWER REF can supply a fixed point, not a level sweep. Equipment replacement remains a separate provenance/onboarding follow-up.

## WF-05 synthetic output versus frequency — November 12, 2026

[WF-05 v1](workflows/FREQUENCY-SWEEP-V1.md) now implements finite ordered frequency sweeps at a fixed declared setting/mode, exact-point sensor/fixture correction provenance, deterministic target/spread/coverage analysis, PROV-01 records, and one-page HTML/Markdown reports with optional PNG/SVG. No equipment, native backend, RF source, or AI provider was accessed. Normal logger, instrument/transport, existing workflow runners, dependencies, and CLI defaults remain unchanged.

Local ignored evidence: `tmp/wf05/` and `output/reports/wf05-synthetic-20261112/`.

- **883 tests passed** in the stress-enabled full regression suite behind `tools/offline_qa.py`; **69 WF-05 cases** cover scenarios, arithmetic/corrections, incomplete/unknown coverage, criteria, storage failure, evidence joins, corruption, CLI/path protection, provenance, and plots. Final review fixes also receive the targeted/full suite.
- Nineteen fresh synthetic captures were exercised: nominal, band droop, unequal corrections, meter-corrected factors, repeated anchor, missing target/loss/factor, sensor plane, zero output, timeout, malformed response, complete instrument error, cancellation, source-off failure, frequency mismatch/unverified frequency, factor mismatch, and missing band. Re-reporting produced the same computed results without modifying source bytes.
- Independent catalogue oracle: 1.8/3.5/7/14/28 MHz; corrected means 4.8/5.0/5.1/4.9/4.7 W; errors −4/0/+2/−2/−6%; observed spread `10 log10(5.1/4.7) = 0.354723181622… dB`; worst target error P05. Explicit fictional 6%/0.4 dB criteria pass, while 0.3 dB spread or a tighter P05 tolerance fails. Default acceptance is NOT EVALUATED.
- Separate unequal-factor/loss and meter-corrected scenarios both recover 5 W at every point. Tests verify that already applied sensor factors are not reapplied, unknown factors/losses are not replaced with simulator truth, sensor-plane results can survive missing fixture data, and their DUT-plane spread retains separate partial coverage. Spread-only criteria do not require target mapping; error criteria do.
- Frequency/factor readback mismatch stops before that point is keyed. Uncertain communication produces no later actor commands and unknown final external source-off state. Failed off is not retried. Partial/skipped points remain in requested coverage; nonpositive/incomplete/ineligible cases cannot pass complete-sweep criteria. Zero-output descriptive error remains visible in the worst-error summary.
- Source distribution and wheel build passed under the guard. A fresh installed wheel, invoked outside the checkout without Matplotlib, generated corrected synthetic capture/report output. Producer metadata retains the full commit and source hashes. Optional plots are verified as real PNG/SVG files.
- All 19 one-page sheets were rendered for Letter and A4 (38 outputs), with band-droop, correction-placement, and failure sheets checked visually. Sheets show pre-RF zero, transmitter/operator/time, fixed setting/mode, declared frequency points, CF application location, fixture losses, results, coverage/spread/worst point, acceptance, and final synthetic source state. Full source/criteria/uncertainty limitations remain in the appendix.
- Ruff, formatting, Markdown links/anchors/tables, five publisher PDF hashes, and `git diff --check` passed. WF-05 tests are added to the existing Python 3.11/3.14 hosted reporting matrix; Delivered to `devel` at `64ea656`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43319936286).

This virtual generator does not exercise production `Instrument`/`collect`, CAL FAC programming, frequency readback, USB, native timeouts, or external transmitter shutdown. This is software/model evidence, not physical source or sensor qualification. POWER REF remains a fixed nominal 50 MHz anchor, not a sweep source. Physical integration stays **DUT-CTRL-01**; WF-06 synthetic development can proceed separately from equipment exchange.

## WF-06 synthetic supply-voltage sensitivity — November 12, 2026

[WF-06 v1](workflows/SUPPLY-SENSITIVITY-V1.md) now implements finite observed-voltage RF captures, declared supply envelope/current-limit setup, explicit nominal reference, observed endpoint secant, distinct restoration verification, PROV-01 records, and deterministic one-page reports/plots. No real supply, voltage observer, RF source, meter, native backend, or AI provider was accessed. Normal logger, instrument/transport, existing workflows, dependencies, and CLI defaults remain unchanged.

Local ignored evidence: `tmp/wf06/` and `output/reports/wf06-synthetic-20261112/`.

- Stress-enabled full regression: **964 tests passed** behind `tools/offline_qa.py`. **81 WF-06 cases** cover all scenarios, independent arithmetic, unsafe requests rejected before allocation, nominal/observed-voltage handling, current-limit setup, source/restore state, criteria, provenance, corruption, storage failure, CLI/path protection, and optional plots. The final report refinement also passed the targeted suite.
- Twenty-two fresh synthetic scenarios were captured and reported: nominal, droop, observed offset, repeated anchor, missing nominal/readback, unsafe readback, same voltage, missing loss, sensor plane, zero nominal, timeout, malformed response, complete instrument error, cancellation, missing point, source-off failure, supply-control failure, current-limit mismatch, restoration write failure, restoration mismatch, and unverified restoration. Reimports reproduced computed results without changing source bytes.
- Independent catalogue oracle: observed 11/12/13 V; DUT-plane means 4.5/5/5.2 W; nominal P02 at 12 V and 5 W; changes −10/0/+4%; endpoint secant 0.35 W/V. Fictional inclusive 10%/0.35 W/V limits pass; tighter limits and point-specific overrides fail. Default acceptance is NOT EVALUATED. With observed 10.98/12.02/13.01 V, secant uses the observed 2.03 V span, not requested endpoints.
- Missing/nonpositive nominal points never become an implicit reference or a zero denominator. Equal voltages yield unavailable secant. Repeated anchors retain order/history, and ties use the first captured endpoint ID. Missing fixture loss is not replaced with model truth; sensor-plane results avoid fixture multiplication. No DC current/input power or efficiency is inferred from a current-limit setting.
- Missing/unsafe voltage readback stops before RF at that point. Current-limit mismatch activates no point. Uncertain read/source state and supply-control failure block restoration commands; complete instrument-error/cancellation cases can perform the distinct declared restore action after known RF off. Restore failure/mismatch/missing readback fails execution even with 3/3 RF points complete; no failed off/restore is retried, and no incomplete/unsafe run can pass complete-run criteria.
- Source distribution and wheel build passed under the guard. A fresh installed wheel, invoked outside the checkout without Matplotlib, generated capture, provenance, and corrected reports. Producer metadata retains the full commit/source hashes. Optional plot checks verify PNG/SVG files, including a no-data display for failed current-limit setup.
- Every scenario's report was rendered for Letter and A4 (**44 one-page outputs**). Droop, repeated-anchor, restoration-failure, and empty-capture sheets were visually checked. Primary sheets show requested versus observed voltage, RF power/change, signed pre-RF zero, declared nominal point, observed endpoint IDs/secant, final RF/supply state, and a concise cause for incomplete/failed runs. Full technical evidence remains in the appendix.
- Ruff, formatting, Markdown links/anchors/tables, five publisher PDF hashes, and `git diff --check` passed. WF-06 tests are included in the existing Python 3.11/3.14 hosted reporting matrix; **WF-06 hosted CI is pending later commit/push**.

This is synthetic state-machine/analysis/report evidence. It does not qualify a supply driver, voltage observer, current compliance, RF keying, native timeout, or physical restoration procedure. Physical source/supply integration remains **DUT-CTRL-01**, with rated limits, actual observation/calibration, RF shutdown, and restoration evidence. Neither POWER REF nor changes to meter corrections/units create a supply-voltage sweep; equipment exchange is a separate follow-up.
