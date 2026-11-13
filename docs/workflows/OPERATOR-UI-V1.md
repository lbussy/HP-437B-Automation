# OPERATOR-UI-01: Local operator interface, v1

Status: implemented and locally exercised; delivery and CI verification in progress. This single-user browser interface uses the existing [profiles](DUT-TEST-PROFILES-V1.md), [suite runner](TEST-SUITES-V1.md), and [PDF/portable delivery](PDF-EXPORT-V1.md). The owner confirmed a loopback-only Python service, the existing reports' clean style, and **fakes only** for this first interface. Normal logging, physical runners, the main CLI, and base dependency pins remain unchanged.

## Launch

Use Python 3.11 or newer on a Unix host, with the existing optional reporting dependencies:

```bash
python -m pip install -e '.[reports,pdf]'
python -m hp437b.operator_ui --port 8765 \
  --runs-dir output/reports/operator-runs
```

Open the printed `http://127.0.0.1:8765` URL on that computer. `--port 0` chooses an available port. Add `--no-plots` to omit individual plots and avoid requiring the `reports` extra; the `pdf` extra is still required. Dependency checks precede any run. There is no frontend build step, external asset fetch, physical endpoint, or AI provider.

A fictional example profile is available immediately. Choose a profile, optionally enter an operator name, select one or more tests, and press **Start suite**. Tests run in displayed WF-04, WF-05, WF-06 order. All included profile plans and adjacent restoration conditions are validated before allocating a job. The default example's acceptance is NOT EVALUATED because it supplies no DUT limits; completion is not a PASS claim.

Use **Import profile JSON** for an existing fake-only profile. Imports preserve duplicate-key rejection and the profile's 256 KiB limit. Alternatively, supply `--profiles-dir path/to/profiles` for a directory of `.json` profiles; invalid files appear under the profile-issues disclosure. Each catalog directory considers its first 100 sorted JSON files. Imported profiles are retained under the run root. Plans, corrections, fake mode, and criteria use the existing profile contract; the UI does not edit them.

## Progress and cancellation

One suite may be active per run directory. A filesystem lock is inherited by the worker, preventing a second service from acquiring the same root while it finishes. Use one operator service per computer; independent roots are independent sessions, not a machine-wide lock.

The page shows each test starting, its recorded completion/acceptance, report generation, and final results. Progress updates at workflow boundaries; it is operational state, not a new measurement stream or evidence record. Refreshing the page reconnects to the current job and recent history without starting another run.

**Request cancellation** writes a cooperative request. If a test is active, it finishes its finite capture and existing RF-off/restoration checks before the next workflow is skipped. The page names the active test and next boundary when available. Cancellation is neither immediate shutdown nor process termination. Fast fake runs may finish before the request reaches a boundary; the UI reports that outcome. Once report generation starts, cancellation is unavailable. Partial/cancelled suites retain their native results and can still produce reports.

Stop the service with Ctrl-C. It requests boundary cancellation when capture is active and waits up to 30 seconds. A still-finishing worker is not killed and retains the root lock. There is no automatic retry, reset, or resume. After an interrupted prior session, a newly acquired root marks stale operational state as failed and retains saved files rather than restarting tests.

## Reports and retained files

**Open PDF report** opens the one-page suite answer in a new tab; child report links lead to the individual PDFs. **Download package** saves the existing hashed portable ZIP, including reports, provenance, and original evidence. Recent runs link to their PDFs. The service exposes inventoried report artifacts and verified packages, not arbitrary local files.

Each UUID-named job directory contains:

- `request.json`: frozen profile/selection/operator request.
- `state.json`, `worker.log`, and optional `cancel.requested`: operational diagnostics, outside the evidence inventory.
- `capture/`: the authoritative native suite and child evidence.
- `report/` and `report.zip`: sealed publication and portable delivery.

The API returns up to 20 recent jobs; the page displays the latest five. History survives service restart. There is no automatic deletion. Keep local runs under ignored `output/reports/`; do not commit raw measurements or local UI state.

Capture failure, criterion failure, cancellation, and publication error remain distinct. A report error retains capture evidence. For a sealed capture, use the existing report-only command with a fresh output path:

```bash
python -m hp437b.test_suite report \
  --bundle output/reports/operator-runs/JOB_ID/capture \
  --output output/reports/recovered-suite-report --package
```

Use `--no-plots` if appropriate. This command does not recapture or change the original operational job status. Unsealed partial captures require inspection; the interface does not assert completion or offer blind restart.

## Local access and validation scope

The service binds only IPv4 `127.0.0.1`, requires the exact printed Host, uses a local session cookie and API token, and rejects cross-origin writes. Static code is packaged with Python; user-supplied text is rendered as text. These controls serve a local single-user tool, not a remote authentication or multiuser authorization system. Do not expose the port through a proxy or tunnel. Run/profile storage is operator-owned; hashes detect changed evidence, not authorship.

[Validation](../VALIDATION.md#local-operator-interface--november-12-2026) records guarded regression, native fake workers, cancellation, access controls, artifact verification, installed-wheel behavior, and desktop/mobile browser checks. This establishes local software behavior, not physical DUT control, timing qualification, or broader host/backend support. Physical controls, remote access, profile editing, and AI automation remain separate future work.
