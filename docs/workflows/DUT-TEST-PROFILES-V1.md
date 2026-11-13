# PROFILE-01: Reusable DUT test profiles, v1

Status: delivered, with fake-only validation and single-workflow execution. Normal logging, physical workflow runners, dependencies, and existing commands/defaults are unchanged. The [fake suite runner](TEST-SUITES-V1.md) is now implemented; physical drivers remain open. Delivered to `devel` at `e05a120`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43349815908).

A profile saves transmitter identity, operator, ordered setting/frequency/voltage plans, fixture losses, sensor corrections, and optional acceptance criteria in one versioned JSON document. It reuses the existing [WF-04–WF-06 shared controls](CONTROLLED-SWEEPS-V1.md), capture files, PROV-01 records, deterministic calculations, and reports. Runs remain human-started. This version admits only `mode: "fake"`; it cannot open physical endpoints or turn POWER REF on.

## Create, validate, and run

The [fictional example](examples/dut-test-profile-v1.json) uses a 1.5 A WF-06 current-limit/restoration value compatible with the other fake workflows and contains all three workflows with no invented DUT limits, operator, manufacturer, model, serial, or asset ID. Its DUT name, fake conditions, and model powers are explicitly fictional. Edit a copy rather than the example:

```bash
python tools/offline_qa.py -- python -m hp437b.test_profiles example > tmp/my-profile.json

python tools/offline_qa.py -- python -m hp437b.test_profiles validate \
  --profile tmp/my-profile.json

python tools/offline_qa.py --seconds 120 -- python -m hp437b.test_profiles run \
  --profile tmp/my-profile.json --workflow WF-04 --operator 'Example operator' \
  --output output/reports/profile-setting \
  --report-output output/reports/profile-setting-report --no-plots
```

Select `WF-05` or `WF-06` to run the other saved plans, using fresh output directories. Only the selected workflow executes; this is not a suite command. Omit `--no-plots` with the optional `reports` extra to include plots. Omit `--report-output` for capture only. Re-report through the existing workflow command without the original profile file:

```bash
python tools/offline_qa.py -- python -m hp437b.power_setting report \
  --bundle output/reports/profile-setting \
  --output output/reports/profile-setting-report-again --no-plots
```

Commands return 0 for a valid profile/completed capture, 1 for a failed/interrupted capture, and 2 for configuration, storage, or publication errors. Profile validation performs no capture and creates no output. All included plans, even unselected workflows, must validate before a run allocates output. Existing outputs are never overwritten. Optional `--fault`, `--fault-point`, and `--stop-before` exercise the existing fake failure paths; they do not modify the saved profile or enable retries.

## Profile contract

The schema is `hp437b.dut-test-profile.v1`:

| Field | Meaning |
| --- | --- |
| `profile_id` | Stable 1–64 character identifier using letters, digits, dots, underscores, or hyphens; starts with a letter/digit |
| `revision` | Explicit positive integer revision, at most 1,000,000; increment when revising the profile |
| `mode` | Exactly `fake`; physical/resource/driver/shell fields are unsupported |
| `description` | Nonempty single-line description, at most 240 characters |
| `operator` | Supplied operator name or null; at most 120 characters |
| `dut` | Name plus manufacturer, model, serial, and asset ID; unknown identity fields are null |
| `workflows` | One to three entries keyed by `WF-04`, `WF-05`, or `WF-06`, each with a complete `plan` and nullable `criteria` |

DUT name must match every included plan. Identity fields are supplied facts, not simulated equipment readback or proof of a physical transmitter's identity. Each plan retains its existing schema and limits; each criteria object retains its workflow's decision rule. The profile adds no implicit interpolation, target, criterion, default correction, inheritance, include file, or driver selection. No file path in profile data is dereferenced as a control or calibration resource.

See [WF-04](POWER-SETTING-V1.md), [WF-05](FREQUENCY-SWEEP-V1.md), and [WF-06](SUPPLY-SENSITIVITY-V1.md) for plan/criteria fields. The existing plan structures explicitly include synthetic source/response/readback model values. Keep these separate from supplied targets, losses, sensor factors, and limits; they are not measurements. WF-05 corrections apply once, and WF-06 uses observed voltage in comparisons. No limits means NOT EVALUATED. A complete run may FAIL supplied fictional criteria without changing its measurements or execution status.

Operator precedence is explicit `--operator`, then profile operator, then `HP437B_OPERATOR`, then unknown. The resolved value and origin are frozen at capture. Re-reporting never rereads the environment for that captured operator. JSON input is limited to 256 KiB; duplicate keys, nonfinite values, unknown fields, unsupported versions/modes, invalid ordering/bounds, and incompatible criteria are rejected.

## Saved provenance and reuse

Each capture stores an additive `test-profile.json` snapshot using `hp437b.dut-test-profile-binding.v1`. It includes the complete validated profile, SHA-256 of its canonical JSON representation, selected workflow, and resolved operator value/basis/origin. The root starting/final records bind the snapshot bytes by path and hash; the final artifact inventory covers it. Source formatting is normalized; the profile hash describes canonical JSON, not the original file bytes or source pathname.

Import validates the snapshot and every plan again, checks the profile hash, and matches selected plan, criteria, and resolved operator to actual root/child evidence. A hidden, unbound snapshot is rejected. Profile-free controlled bundles and original synthetic fixtures remain readable. Hashes detect changes; they do not authenticate a profile author or device, and a fully rewritten/resealed evidence set is not cryptographically authenticated.

PROV-01 adds supplied DUT identity and an evidence-bound profile record. The main one-page **RF Output Power Test** continues showing DUT name, operator, time, signed pre-RF zero, conditions/results, final control state, and Report Harness. Complete profile/identity/criteria facts appear in provenance and the appendix. Editing or deleting the original profile cannot change a prior run; reporting uses only the capture's snapshot and native evidence. Keep private operator/DUT identifiers in local profile copies and ignored generated bundles, not committed examples.

## Completion boundary

PROFILE-01 implements reusable configuration and individual fake workflow runs. [SUITE-01](TEST-SUITES-V1.md) now implements human-started multi-workflow orchestration, a compact summary, and cross-workflow cancellation/failure checks using fakes. Physical transmitter/supply/observer drivers, rated fixtures, physical correction programming, and hardware acceptance remain separate. This work accesses no hardware or AI provider.
