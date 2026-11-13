# PROFILE-01 extension: Reusable POWER REF profiles

Status: implemented, with hardware-blocked software and browser checks. This extends the existing [fake transmitter profiles](DUT-TEST-PROFILES-V1.md); those still save DUT identity and WF-04–WF-06 plans. Normal logging, CLI defaults, physical runner source, and dependency pins are unchanged.

In **POWER REF suite** mode, a saved reference profile reuses selected WF-01–WF-03 workflows, an optional operator, and optional attributed acceptance criteria. Select the profile, explicitly choose a simulated or configured physical source, and start once. The existing suite produces its original measurement PDF/package, followed automatically by a separate assessed PDF/package. No manual criteria-file handoff is needed. Execution status and assessment outcome remain distinct.

The reference subject is always **Internal POWER REF**. A profile cannot relabel it as an external transmitter, configure a meter/backend, change timing/zero/CAL/correction settings, or enable physical access. Supplied limits are not equipment specifications or evidence of accuracy. The existing service launch configuration and fresh setup confirmations remain required for every physical run; final front-panel confirmation remains separate. This extension has not performed a new physical bench run.

## Operator flow

1. Select **POWER REF suite**, choose the tests, and expand **Save or revise a reference profile**.
2. Supply a profile ID, positive revision, description, and optional operator. Leave unwanted criteria blank. Record who supplied any limits or coverage requirements.
3. Save the revision. Select it for subsequent runs. Changing tests or editing the profile clears the saved selection until it is saved again. Operator overrides are recorded for that run.
4. Choose the source and start. After capture and native reports finish, the profile assessment reports **Pass**, **Fail**, or **Not evaluated**, with the [ACCEPT-01 coverage gates and inclusive/no-guard-band rule](ACCEPTANCE-V1.md).
5. Open the original measurement PDF/package or separate assessed PDF/package. Saved history retains both links. If assessment publication fails, the original capture/report remains available; reuse the saved profile in the saved-run assessment section to retry reporting without another capture.

Under **Assess saved POWER REF limits**, the optional saved-profile selector offers only profiles with exactly the same ordered workflow selection as the capture. The assessment records that the profile was selected **post capture**. Original measurement operator, equipment provenance, reports, and front-panel confirmations stay unchanged. Unset limits cannot yield Pass. Missing/partial/insufficient evidence remains Not evaluated under ACCEPT-01; profiles never turn incomplete evidence into a completed test.

## Contract and storage

Schema: `hp437b.reference-test-profile.v1`.

| Field | Contract |
| --- | --- |
| `profile_id` | 1–64 letters/digits/dots/underscores/hyphens, starting with a letter/digit |
| `revision` | Integer 1–1,000,000; a changed revision cannot overwrite an existing ID/revision |
| `description` | Nonempty single line, at most 240 characters |
| `subject` | Exactly `Internal POWER REF` |
| `operator` | Supplied name or null, following existing operator validation |
| `workflows` | One to three distinct WF-01–WF-03 entries in that order |
| `criteria` | Complete ACCEPT-01 criteria document; no criteria for unselected workflows |

Profiles are canonical JSON, capped at 16 KiB each and 100 saved revisions per run directory. The service stores them under `reference-profiles/<canonical-sha256>.json`. Saving identical content is idempotent; changed content with the same ID/revision is refused. Increment the revision to save a change. Corrupt/symlinked profiles are reported and excluded; saving is blocked until unreadable stored profiles are resolved. These are local operational records, not committed examples or authenticated author signatures.

Each profile-started request freezes an `hp437b.reference-test-profile-binding.v1` snapshot containing the full validated profile, its canonical SHA-256, and `selected: before_capture`. The assessed report metadata/provenance and portable package retain that binding, compare it against assessment criteria and selected workflows, and re-evaluate the decision against native sealed evidence. Post-capture application uses `selected: post_capture`. Assessment computation is always post capture; selection timing records the service's operation, not cryptographically authenticated proof of when a person authored criteria. Later revisions or missing profile files cannot change a completed assessment.

An explicit nonempty run operator overrides the profile operator; otherwise the saved operator is used. Criteria author/source and assessor are separate from the measurement operator. A saved profile with no limits still produces an explicit Not evaluated assessment after a profile-started run. Ordinary unsaved suite starts retain their prior behavior and do not create this automatic assessment.

## Local API

All actions retain the existing loopback Host, session-token, cookie, same-origin, JSON, and request-size gates. No arbitrary pathname, shell, USB endpoint, or executable is accepted in profile data.

| Route | Body |
| --- | --- |
| `POST /api/reference-profiles` | `profile` document |
| `POST /api/reference-profile-run` | `profile_key`, `meter_mode`, `operator`, `prepared` |
| `POST /api/reference-profile-assessment` | `source_job_id`, `profile_key`, `assessor` |

`GET /api/state` lists valid saved reference profiles and loading issues separately from existing fake DUT profiles. Run snapshots expose the selected profile, assessment outcome/error, and readiness. Automatic assessment artifacts are available through the existing authenticated route under `assessment/report.pdf`, `assessment/results.json`, and `assessment/package.zip`. The original `report.pdf` and `package.zip` continue to refer to original measurements.

## Verification boundary

Tests exercise immutable revisions, schema/limit/source validation, explicit source/preparation gates, snapshot tampering, single/combined fake captures, automatic one-page assessment/package verification, no-criteria outcomes, operator precedence, boundary cancellation, HTTP refusal, and assessment-publication failure followed by report-only retry. Existing saved physical-format captures exercise each native reader without reopening equipment. Current results and browser evidence are recorded in [VALIDATION](../VALIDATION.md).

Final local verification: **1,433 full-regression tests passed**, with three opt-in stress cases skipped; all 27 focused profile tests passed. Source/wheel builds, isolated wheel report generation, browser/PDF review, four assessment package audits, source preservation, lint/format, JavaScript syntax, documentation checks, and `git diff --check` passed. Physical profile-started bench acceptance remains separate from this software verification.
