# RUN-HISTORY-01: Saved runs and POWER REF comparison

Status: implemented locally. REPORT-RECOVERY-01 was first committed/pushed at `60e7d33`; [all four Python 3.11/3.14 software/reporting CI jobs passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43489321863). This subsequent history implementation is a separate local change. Normal logging, physical capture runners, instrument/transport behavior, and dependency pins are unchanged.

## Browse and inspect

**Saved run history** replaces the recent-five list in the local operator interface. It lists all recognized jobs in the configured run directory, twenty per page, with filters for measurements, report regenerations, or both. Each entry retains its start time, original operational outcome, job ID, workflow selection, and available PDF/package links. Report attempts show their source job ID and cannot be selected as new measurements. Refresh history after a job finishes; browsing never starts or retries work.

**View details** validates sealed individual WF-01–WF-03 or combined POWER REF captures using their owning native readers. It shows each captured workflow's physical/synthetic mode, execution status, signed pre-RF zero, mean sensor-input power, plateau count, meter/sensor labels, source inventory SHA-256, and original front-panel attestation. Report-attempt details resolve to the original acquisition. Requested but uncaptured workflows remain explicitly not captured. An attestation must be bound to the selected source inventory; it is never created or changed by inspection.

Other existing job types remain browseable and retain available report links. Native metric details/comparison are limited to POWER REF in this first version. Unreadable operational records are counted and omitted, not presented as successful runs. A source must be closed and its capture lock available before native details can be read. Missing, damaged, unsealed, symlinked, or inconsistent evidence is refused rather than treated as verified data.

## Compare matching workflows

Select two to four distinct POWER REF measurements, choose WF-01, WF-02, or WF-03, then press **Compare selected runs**. Selection can span history pages and filters; the selected IDs remain listed above the action. Every selected run must actually contain that workflow. Jobs containing the same native acquisition cannot be counted twice.

The table shows each run's mode/status/time, signed zero in µW, mean power in mW, and the applicable endpoint change (%) or cycle-mean spread (µW). Means retain their native definitions: WF-01 sustained readings, WF-02 plateau, and WF-03 equal-cycle aggregation. It never pools different workflow types, subtracts the zero, computes a calibration verdict, or changes acceptance criteria.

For complete runs with matching declared equipment/setup, resource, and measurement profile, mean changes in µW are computed with 50-digit Decimal arithmetic relative to the first selected run. This is descriptive arithmetic, not proof of equivalent physical conditions. Original setup facts may be historical or supplied, as retained in provenance.

Mean changes are withheld when any selected capture is incomplete, physical/synthetic modes differ, declared setup/profile/resource differs, or required context is missing. Required context is recorded meter serial, sensor serial, signal description, and measurement profile. Context comparison excludes operator presence/setup-attestation booleans, operator identity, confirmation origin, and preparation timestamp; other retained setup fields remain conservatively compared. Individual values and concrete difference flags stay visible. A missing value remains unavailable; it never becomes zero. No aggregate pass/fail or trend claim is inferred.

## Read-only boundaries

History/details/comparison perform local reads only, apart from obtaining the existing operational capture lock. They spawn no capture/report worker, contact no meter/backend/provider, and never alter sealed captures, report packages, or operator attestations. The loopback service's existing Host, session-cookie/token, same-origin, bounded JSON, job-ID validation, and artifact checks apply. The browser cannot supply filesystem paths or hardware endpoints.

The authenticated JSON actions are `POST /api/run-history` with `offset` and `category`, `POST /api/run-details` with `job_id`, and `POST /api/run-comparison` with `job_ids` and `workflow`. There is no automatic monitoring, reacquisition, export, report regeneration, or criteria editing in these read actions. Table regions are keyboard-focusable and scroll horizontally at narrow widths; numeric values remain on one line.

## Local verification

Guarded tests cover all three injected physical workflow readers, raw-CSV mean/zero/count oracles and source preservation, report-attempt lineage, filters/pagination, invalid/missing/changed evidence, closed-source locks, attestation binding, same-acquisition refusal, exact Decimal changes, partial/mixed-mode/unknown/different-context exclusions, missing workflows, and HTTP session/body boundaries.

Browser checks use the existing hardware-blocked report-only demo and three saved physical-format bench captures. Completed WF-01 readings compare descriptively; the cancelled WF-01 retains its values but withholds mean changes; WF-02 selection is refused when the cancelled run never captured it. Saved regenerated PDFs/packages remain accessible through history, while their attempts cannot be selected as measurements. These are saved-evidence/software checks and add no new physical measurements. Raw UI/audit artifacts remain ignored under `tmp/run-history/` and `output/reports/report-recovery-demo/`.

The full hardware-blocked regression passed **1,367 tests**, with three opt-in stress tests skipped. Three additional native capture-lock/attestation cases passed separately after collection of that full run. Lint, formatting, JavaScript syntax, documentation checks, and source/wheel builds passed. The saved-data audit preserved all **651 original job files** and **248 copied capture files**, and independently recomputed the completed WF-01 mean difference from CSV with 50-digit Decimal arithmetic (agreement within 1e-28 W). Final desktop/mobile review disposition: **ship**, no material fixes.
