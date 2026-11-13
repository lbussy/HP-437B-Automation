---
version: 1
slug: "src-hp437b-operator-web-index-html"
primary_target: "src/hp437b/operator_web/index.html"
related_targets: ["src/hp437b/operator_ui.py","src/hp437b/operator_jobs.py","src/hp437b/operator_web/app.css","src/hp437b/operator_web/app.js"]
---

# Local operator interface

Mode: Operate. The owner confirmed a single-user, loopback-only browser page, existing Python stack/report styling, and initially fakes only. The interface includes the reviewed current-meter POWER REF workflows and owner-authorized operator-guided radio sweeps. Primary target: src/hp437b/operator_web/index.html. Guided sweeps use simulated measurements or an explicitly configured bench meter; the operator sets the radio and confirms each point. Radio and supply control remain manual, and deployment remains local.

## Direction contract

THESIS: A short path from a saved DUT profile or operator-defined radio sweep to finite measurements and a readable report. No decorative instrument imitation or KPI dashboard.

OWN-WORLD: Inherit the reports' white surface, dark ink, restrained blue actions, workhorse system typography, and clear rules. Color communicates actions and live/error states.

STORY: Choose an operating mode. For a simulated transmitter suite, select the profile and tests, start explicitly, and follow workflow boundaries. For a POWER REF suite, choose the simulated reference source by default or the explicitly configured current meter, select WF-01–WF-03 checkboxes, and start once for shared progress, native results, PDF, and package. Bench source selection exposes fresh setup confirmations; cancellation explains the current capture-stage boundary and cleanup, and front-panel confirmation remains a separate post-run action. For a guided sweep, name the radio/DUT, choose frequency, drive-setting, or combined series, enter labels and capture timing, and start explicitly. All 17 requested bands fit the frequency list; the plan supports up to 32 frequency labels and 16 drive labels, with either combined sweep order. Confirm both radio labels afresh before each settling/capture, follow point completion and the frequency-by-drive results table, and stop when needed. Completed and partial point evidence survives a stop. Open the full HTML report, PDF summary, or portable package when ready. Failures and missing limits remain visible.

FIRST VIEWPORT: Compact project header and explicit mode statement; a two-column workspace with operating mode, setup, and Start on the left and live progress on the right. Suite mode uses the selected workflow rail and cancellation boundary. Guided mode uses the next-point confirmation panel, Stop series, point completion, and a horizontally scrollable results table. Report actions follow progress. Stack the same workspace on small screens; keep point confirmations readable and actions reachable.

FORM: Code-first extension of the user-confirmed report world and precisely specified task; no new-world concept round. Signature interaction: cancellation names the current test and the next boundary, while the last completed native results remain available. POWER REF mode separates setup attestations from recorded protocol observations and post-run front-panel confirmation. Guided mode separates declared radio frequency/drive labels from meter-indicated power at the sensor input; bench setup attestations appear only for the configured physical meter. Setup locks during an active sweep, both point confirmations reset for each prompt, and the capture action enables only after both are checked. Stop retains saved points and reminds the operator to turn radio RF off. A local Python/HTTP orchestration client exposes start, status, confirm-one-point, and stop through the same operator-owned workflow; it adds no automatic radio control.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

No shipping raster assets are required. Browser screenshots are verification evidence only.

Finish evidence: the guided extension received a ship disposition with no material fixes. Desktop, mobile setup, mobile point confirmation, stopped-series, and report-ready captures are verification evidence under `.impeccable/review/` (`guided-desktop.png`, `guided-mobile.png`, `guided-mobile-point.png`, `guided-stopped.png`, and `guided-reports.png`). This is interface/software evidence; new physical bench acceptance remains pending.

POWER REF suite finish evidence: ship disposition with no material fixes. Desktop and mobile verification captures are `.impeccable/review/ref-suite-desktop.jpg` and `.impeccable/review/ref-suite-mobile.jpg`. The inherited report world and CSS are unchanged. The detector’s section-padding warning was disproved by rendered whitespace and was not adopted as a new rule. This review provides interface/software evidence; it adds no physical bench acceptance.
