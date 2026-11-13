# Control and logging plan


Saved from the November 8, 2026 discussion at the user's request, and amended November 9 with the provisional open-source backend and validation plan. Phase 2 software was executed at the user's request on November 11; hardware qualification follows when the setup is ready.

## Current product direction

Updated November 12, 2026: the owner's [scope clarification](PROJECT-SCOPE.md) governs this plan. The product orchestrates measurement/test processes using the meter/sensor and provides agent-assisted analysis and reports about the equipment being tested. Control/logging and host-interaction validation are foundations. Equipment identity/calibration/known issues provide provenance; replacement arrival is not a project gate. WF-01, PROV-01, and REPORT-01 v1 are implemented, and [E2E-01/VAL-01 acceptance](validation/PIPELINE-ACCEPTANCE.md) is complete for that first profile. Future capabilities keep separate scopes in the [open-work register](OPEN-WORK.md).

Earlier bench-profile decisions and procedures below retain their limited scopes. They do not narrow the product to reference-bench logging or supersede the owner's clarified goal.

### User requirements and current state

- Collect power readings from the 437B using a Mac or Raspberry Pi.
- Current-setup adapter readiness HP-02 is complete for the tested supervised Mac/Pi profile; the Phase 2 Python interface and logger are implemented, with equipment exchange/onboarding tracked separately from software acceptance.
- Phase 2 implementation was explicitly authorized on November 11. Phase 3 execution was explicitly authorized on November 11; the [batch plan](validation/PHASE-3-PLAN.md) records successive supervised Mac batches, and the [Pi plan](validation/PI-QUALIFICATION.md) defines second-host gates.
- On November 11, 2026, the user reported that the seller/calibrator confirmed the current meter's [documented +5 V supply discrepancy](EQUIPMENT.md#individual-calibration-records) was unacceptable. The user plans to exchange the meter after a few development steps with it. Current-unit Mac measurement, control, logging, and named manual-recovery batches have passed; Pi reference/control/logging and a [named manual Pi-only recovery](validation/PI-ONLY-RECOVERY.md#p3-pi-r4-accepted-manual-pi-only-recovery) are recorded, and the exchange remains pending. Keep current-unit observations separate from replacement qualification.

### Adapter recommendation

The assistant recommended the **XyphroLabs USBGpib V2**, a USB-C to GPIB controller, for this single-instrument setup. [Binho's product listing](https://binho.io/test-measurement/products/usbgpib-v2/) showed **US$59 and in stock** when checked during the November 8 discussion. Price and availability are historical observations and should be checked before purchase. The [developer's project](https://github.com/xyphro/UsbGpib) identifies Binho as a distribution partner.

The [adapter manual](https://github.com/xyphro/UsbGpib/blob/master/Tutorials/UsbGpibV2_manual.md), sections “Advantages of UsbGpib V2 adapter,” “Using the adapter,” and “Technical specifications,” documents controller operation, GPIB reads, writes, and triggering, USBTMC communication, macOS and Linux support, and PyVISA/PyVISA-py integration. See the [developer's setup tutorials](https://github.com/xyphro/UsbGpib/tree/master/Tutorials) for platform-specific setup. These are manufacturer/developer claims, not local validation of this adapter with the user's 437B, Mac, or Pi.

The adapter supports **control as well as data collection**. The 437B operating manual, §3-14, Table 3-2, printed page 3-25, states that measurement results are available over HP-IB and that operations other than the LINE switch and HP-IB address setting are bus programmable. Use the meter's own command reference for implementation; a USBTMC adapter does not change the meter's command language to modern SCPI.

The adapter can plug directly into the meter's rear HP-IB connector. Plan for a USB data cable matching the host connector and the adapter's USB-C socket; use a GPIB extension cable only if physical clearance requires it. Confirm the purchased model is **USBGpib V2**, since other adapters and later versions may require different setup.

An alternative discussed was the [Prologix GPIB-USB controller](https://prologix.biz/product/gpib-usb-controller/), listed at **US$299.95** during the same discussion. It supports macOS and Linux through a virtual serial interface and would require a different software transport from the USBGpib V2. The USBGpib V2 remains the saved recommendation. A XyphroLabs GpibUsb adapter is now present; exact PCB revision is unmarked/unverified and accepted as a metadata limitation at the owner's direction.

### Proposed Mac/Pi workflow

The assistant proposed leaving a Pi beside the meter for longer runs:

437B → USBGpib V2 → USB data cable → Raspberry Pi → timestamped CSV files

The Mac would start collection and retrieve files over the local network, for example through SSH and file transfer. Direct USB connection to the Mac is also an intended option. A small Python logger would configure the meter, trigger or request readings using its documented commands, and record results. Mac and Pi are the selected hosts. The [adopted initial policy](validation/MEASUREMENT-POLICY.md) uses W, automatic range/filter, a one-second requested interval, finite five-minute runs, and the existing CSV/sidecar fields. Actual achieved timing is reported; production CLI defaults remain unchanged.

### Provisional open-source software choice

The user asked for an open-source alternative to R&S VISA and approved adding a provisional-backend validation plan on November 9. The proposed stack is:

Python logger → PyVISA → PyVISA-py → PyUSB/libusb → USBGpib V2 → 437B

[PyVISA-py](https://github.com/pyvisa/pyvisa-py) is an MIT-licensed Python backend for PyVISA; it is separate from PyVISA itself. Its [USB installation documentation](https://github.com/pyvisa/pyvisa-py/blob/main/docs/source/installation.rst) describes PyUSB and a USB backend such as libusb. The adapter's normal USBTMC firmware uses this USB path, rather than the native GPIB-driver path. Select the backend explicitly with `pyvisa.ResourceManager("@py")` during validation.

**The stack has named current-unit Mac/Pi evidence for the implemented logging profile.** Additional operations need evidence when required by an application workflow; a replacement is not a blanket software gate. In the adapter manual's FAQ, under “Do I really need to use a VISA library?”, the author describes PyVISA-py's USBTMC implementation as incomplete and mentions version queries and advanced features. That is the adapter author's assessment, not an independently reproduced failure with the latest released backend or this 437B. It does not establish that ordinary control and logging will fail or that the adapter is unsuitable. The [backend changelog](https://github.com/pyvisa/pyvisa-py/blob/main/CHANGES) also contains ongoing USBTMC work; unreleased improvements must not be treated as capabilities of an installed release.

Keep the USBGpib V2 recommendation. Accept PyVISA-py for this application only after the required operations pass hardware testing: configuration, power readback against the front panel, required trigger and status operations, termination, timeout recovery, and sustained logging. Record exact released package and adapter firmware versions, tested operations, and results. An unrelated unsupported feature need not disqualify a stack that passes these requirements.

If a required operation fails, investigate configuration or a reproducible backend defect before deciding whether to fix it or change backends. R&S VISA remains a possible proprietary fallback, not the selected open-source solution. Its royalty-free object-code license and platform compatibility would need consideration before adopting it. Do not promise full orchestration through PyVISA-py until the operations actually required have been validated.

### Decision register

| Decision | Current position | Still needed |
| --- | --- | --- |
| Instrument and goal | Automated measurement/test orchestration and agent-assisted reports using the meter/sensor; reference-bench logging is the initial tested foundation | Define/implement the workflow, provenance, analysis/reporting, and end-to-end application contracts in [current scope](PROJECT-SCOPE.md) |
| Adapter | Arrived: XyphroLabs USBGpib V2 (owner-reported marking), USB `03eb:2065`, detected on this Mac November 11 | Adapter firmware `V2.4` was read through the [documented internal query](validation/ADAPTER-IDENTIFICATION.md); Anker USB-C cable and front-panel meter GPIB address 13 are owner-reported; exact PCB revision is an accepted unknown. Recheck the replacement meter's identity and address during acceptance. Instrument USB identification content is not adapter firmware |
| Language and API | Python/PyVISA interface/logger and named Mac/Pi interaction cases implemented | Build workflow and reporting layers; test newly required operations without changing established logging behavior silently |
| Open-source backend | Pinned PyVISA-py 0.8.1 with named current-unit Mac/Pi cases and explicit bus guards | Targeted validation for additional workflow requirements; unrelated bus gaps retain deferrals |
| Host | MacBook Pro ARM64/macOS and Pi 5/aarch64 Debian with separate per-case environments; current-unit shutdown fix verified on both | Preserve per-host evidence; check relevant changes when equipment/workflows change; broader recovery remains separately scoped |
| Logging behavior | [DEC-02 complete](validation/MEASUREMENT-POLICY.md): W, automatic range/filter, interval 1 second requested, duration 300 seconds, actual timing reported, existing CSV/sidecar | Keep this as an adopted test profile; workflow-specific policies remain to be defined; CLI defaults unchanged |
| Measurement setup | Prepared internal-reference path and actual sensor/factor policy recorded; [replacement procedure ready](validation/REPLACEMENT-ACCEPTANCE.md) | Capture identities, applicable records/factors, setup, and known issues in run provenance; perform equipment-specific checks when used |

### Qualification sequence after adapter arrival

1. Record the actual adapter model/firmware, Mac architecture and macOS version, or Pi model and OS. Confirm USB cabling and the meter's configured GPIB address.
2. Follow the adapter's platform tutorial, install and record the candidate software versions, and establish basic communication with the provisional PyVISA-py USB backend. Confirm the 437B's command syntax, output format, termination, and trigger/read behavior from its operating manual before writing the logger.
3. Verify a software reading against the front-panel display and exercise a reversible remote setting. Confirm units, status/error handling, and return to local operation. Do not assume calibration or zeroing should run automatically; derive any such procedure from the manuals and the actual bench setup.
4. Choose the host, logging interval, duration, and CSV fields. Account for meter averaging, range changes, and settling; the current Mac/unit achieved approximately one-second receipt spacing in the recorded five-minute reference case; additional hosts and other range/filter/signal conditions require their own evidence.
5. Implement and validate the Python logger on the selected host, including timestamps, explicit units, timeouts, invalid readings, and clean shutdown. Test required triggering/status operations, recovery after a timeout, and a sustained logging run before accepting the backend. For Pi logging, verify Mac access and file retrieval. Validate each additional host before claiming support. Record actual bench results and any adapter-specific limitations here.


## Three-phase execution

1. ✅ Complete — Phase 1: Inventory; use the [command and GPIB reference](inventory/README.md) and [coverage matrix](inventory/COVERAGE.md).
2. ✅ Complete — Phase 2: Implement; the [software milestone](SOFTWARE.md) provides the interface/logger and records deferred coverage in the [review](PHASE-2-REVIEW.md). The [execution prompt](prompts/phase-2-implementation.md) is retained. Resolve transport requirements using the [released-backend evidence](inventory/GPIB.md#transport-evidence-profiles) and [source questions](inventory/AMBIGUITIES.md).
3. ✅ Complete (WF-01 v1 profile) — Phase 3: Qualify; the [pipeline acceptance](validation/PIPELINE-ACCEPTANCE.md) joins the scoped hardware interactions started November 11 with synthetic and retained workflow/provenance/analysis/report evidence. New capabilities require their own acceptance scope. Equipment exchange is not a software gate.

The [Phase 1 review](inventory/REVIEW.md) recommends the first batch and documents command sequencing constraints. Preserve separate documentation, implementation, software-test, Mac, and Pi statuses. PyVISA-py remains provisional for complete bus control.

## Related records

See [open work](OPEN-WORK.md), [equipment references](EQUIPMENT.md), and the [hardware validation plan](VALIDATION.md).

## Phase 2 software choices

Python 3.11+ is the baseline; local checks used Python 3.14.10 on macOS ARM64. Runtime pins are PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1, with @py selected explicitly. The finite logger defaults are ten samples, one-second interval, dBm, and ten-second operation timeout; user options override these software defaults. DEC-01 and DEC-02 record the selected hosts and explicit initial run policy; the software defaults remain unchanged. See [usage](SOFTWARE.md) for exact behavior and qualification limits.

## Automatic local-return implementation

The owner requested removing the manual PRESET/LOCAL step after runs. The [project-local USB488 extension](validation/AUTOMATIC-LOCAL.md) retains dependency pins and reuses the existing USB handle to request Go To Local on healthy Instrument close. Other bus features and uncertain-state recovery remain guarded. Initial Mac physical verification is tracked separately from software tests, Pi, and replacement acceptance.

## Pre-arrival work and corrected completion boundary

The [pre-arrival review](validation/PRE-ARRIVAL-REVIEW.md) and [replacement procedure](validation/REPLACEMENT-ACCEPTANCE.md) preserve completed preparation. The November 12 owner clarification supersedes earlier claims that no useful work remained or that HP-01/replacement arrival must gate PHASE-03/VAL-01. Equipment exchange remains tracked with its actual identity and records. Software workflow, provenance, analysis/reporting, and end-to-end testing proceed independently.

## Hardware-free software qualification

The [offline campaign](validation/OFFLINE-QUALIFICATION-RESULTS.md) strengthened parameter, parser, logger, storage-fault, process/deadline, and clean-install evidence. Integrated and pushed to `devel` at `6bda91d`, with [Python 3.11/3.14 CI passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43214328205). Runtime source and pins are unchanged. This validates software foundations, not DUT accuracy or the unimplemented orchestration/reporting product.

## First application workflow

[WF-01 POWER REF measurement and repeatability](workflows/POWER-REFERENCE-V1.md) defines a finite off/on/off sequence, short and sustained captures, stop/cleanup behavior, provenance, and deterministic/agent-assisted report boundaries. A [shortened synthetic worked report](workflows/examples/POWER-REFERENCE-V1-SYNTHETIC.md) makes the inputs/calculations/output concrete without hardware. Definition is prepared, and the [synthetic prototype exercise](workflows/WF-01-EXERCISE.md) produced seven real synthetic output bundles/reports. The [first fixed physical POWER REF workflow](workflows/WF-01-PHYSICAL.md#current-meter-physical-result) then completed on the current Mac/meter with generated report and owner final-state confirmation. Wider workflow scope and the complete reporting product remain implementation work. Normal logger behavior stays unchanged.

## Reusable provenance

[PROV-01 v1](RUN-PROVENANCE.md) provides run, DUT, and equipment models with explicit fact bases, evidence paths/hashes/JSON pointers, history, detached legacy WF-01 imports, and new-workflow sidecars. The nine reviewed bundles were imported with all 165 source files unchanged; no new physical run or normal logger change is involved.

## Saved-run reporting and analysis

[REPORT-01 v1](REPORTING.md) adds independent saved-CSV calculations, coverage/failure treatment, PNG/SVG plots, richer HTML/Markdown/JSON reports, and a validated file-based handoff for attributed agent drafts. Nine retained physical/synthetic bundles were exercised without device I/O or source changes. External provider automation, additional workflows, and broader E2E/VAL acceptance remain follow-ups; normal logging is unchanged.

## First end-to-end application acceptance

[E2E-01 / VAL-01](validation/PIPELINE-ACCEPTANCE.md) accepts the complete WF-01/PROV-01/REPORT-01 v1 profile using seven fresh synthetic and nine retained inputs. Tests preserve original evidence and failed/interrupted outcomes, check analysis bindings and plots/reports, and leave normal logging unchanged. Phase 3 is complete within this declared profile; additional workflows, DUT-specific criteria, external providers, and unattended operation require their own scoped work.

## Human-started deterministic reporting decision

The owner selected human-started tests with deterministic reports only for now; AI/provider automation is deferred. [RUN-01](workflows/DETERMINISTIC-RUN.md) adds opt-in post-capture provenance and richer reports, plus saved-bundle publication, without model calls, normal logging changes, or new physical I/O. The physical CLI hook is verified with explicit fakes; this change does not broaden host or unattended-operation claims.

## Human-readable RF result sheet

The owner requires a concise report about the equipment being tested: DUT identity, time/conditions, measured RF output, and acceptance outcome, with the measurement fixture retained as traceability. The [result-sheet contract](REPORTING.md#reader-facing-rf-report-contract) replaces a diagnostic dump as the primary report; full evidence remains in an appendix. POWER REF demonstration data remains explicitly identified as reference-source data.

## Additional DUT test workflows

**WF-CATALOG-01 — Definition complete, November 12, 2026.** The [transmitter test catalogue](workflows/TRANSMITTER-TEST-CATALOG.md) prioritizes WF-02 sustained output stability, WF-03 transmission-cycle repeatability, WF-04 output versus setting, WF-05 output versus frequency, and WF-06 supply-voltage sensitivity. It defines inputs, finite draft profiles, calculations, one-page reports, criteria/coverage treatment, source cleanup, synthetic examples, and POWER REF's useful scope. [WF-02 now has a synthetic implementation](workflows/SUSTAINED-STABILITY-V1.md); its [POWER REF integration](workflows/WF-02-PHYSICAL.md) is implemented/offline-tested and the selected Mac run passed capture/audit and owner final-state confirmation. WF-03 now has current-Mac POWER REF evidence, and WF-04/05/06 synthetic implementations are complete. Physical transmitter/supply integration remains DUT-CTRL-01.

**WF-02 synthetic implementation is complete**, including finite captures, independent drift/coverage calculations, provenance, and deterministic reports. [Physical POWER REF integration](workflows/WF-02-PHYSICAL.md) is implemented/offline-tested; the selected current-Mac run passed capture/audit and owner final-state confirmation. [WF-03 slow-cycle repeatability](workflows/TRANSMISSION-CYCLES-V1.md) now has a synthetic capture/provenance/report implementation; its [physical POWER REF integration](workflows/WF-03-PHYSICAL.md) is offline-tested and selected Mac execution passed five cycles/150 plateau rows, independent audit, and owner final-state confirmation. External transmitter control/manual acknowledgements, safe fixture/correction records, and single-point transmitter reporting are tracked as **DUT-CTRL-01**. [WF-04 output versus setting](workflows/POWER-SETTING-V1.md) now has bounded synthetic point captures, fixture/target comparisons, provenance, and deterministic reports; [WF-05 output versus frequency](workflows/FREQUENCY-SWEEP-V1.md) now has synthetic exact-point captures, frequency-dependent correction placement, spread/target/coverage analysis, provenance, and deterministic reports; [WF-06 supply-voltage sensitivity](workflows/SUPPLY-SENSITIVITY-V1.md) now has synthetic observed-voltage captures, nominal/endpoint analysis, restoration checks, provenance, and deterministic reports; physical work still needs a controlled supply/voltage-observer/source path. Equipment exchange is not a software gate, and normal logging remains unchanged.

## Report harness release identity

The report footer places Report Harness before Record. Clean exact semantic-version releases show their tag version; development builds show the commit, while full commit identity remains in metadata. Wheels/source archives carry build identity for installed use without a checkout. This does not change package-version policy, create/publish release tags, or alter normal logging. See the [tag-aware report policy](REPORTING.md#tagged-releases-and-development-builds).

## External transmitter control foundation

[DUT-CTRL-01 fake-control v1](workflows/EXTERNAL-TRANSMITTER-V1.md) now supplies reusable transmitter/supply/voltage-observer contracts and guarded single-condition orchestration. The fake-only workflow uses the existing Instrument/logger, captures source-off zero/settling/plateau/final baseline, verifies owned-source shutdown/restoration, and publishes provenance and deterministic reports. Saved receipt replay validates controls without device calls or reacquisition. Physical drivers, manual acknowledgement flows, independent shutdown qualification, and hardware acceptance remain open. Existing WF-01–WF-06 implementations, normal logging, dependencies, and CLI defaults are unchanged.

## Shared controls for WF-04–WF-06

The [shared-control fake sweeps](workflows/CONTROLLED-SWEEPS-V1.md) now integrate DUT-CTRL-01 into ordered setting, frequency, and supply-voltage runs. Each point uses guarded transmitter/supply/observer operations and production logger capture through explicit fakes, carries shared fake hardware state, verifies shutdown/restoration, and stops on failure. Native point evidence feeds existing analyses, provenance, and reports. Legacy fixture commands and saved bundles remain supported. Delivered to `devel` at `d2f5584`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43337194421). Physical drivers and normal logging remain unchanged.

## Reusable DUT test profiles

[PROFILE-01](workflows/DUT-TEST-PROFILES-V1.md) implements explicit fake-only profiles for supplied DUT identity, operator, existing WF-04–WF-06 plans, and acceptance criteria. Human-started single-workflow runs reuse shared controls and preserve a hashed full profile snapshot in capture/provenance. Existing commands, physical runners, and normal logging remain unchanged. Delivered to `devel` at `e05a120`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43349815908). SUITE-01 now composes selected workflows and summarizes results with explicit stop/cancel behavior, as recorded below; physical drivers and AI automation remain separate.

## Human-started test suites

[SUITE-01](workflows/TEST-SUITES-V1.md) now runs an ordered profile-selected subset of WF-04–WF-06 through one shared fake hardware state, verifies cross-workflow restoration/timing/profile joins, stops after execution/criterion failure or cooperative cancellation, and produces individual reports plus a compact summary. Sealed captures support report-only retries; storage faults retain partial evidence without asserting completion. Delivered to `devel` at `e05a120`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43349815908). Normal logging, physical runners, and dependencies remain unchanged. Physical drivers remain separate future work; the local fake-only interface is recorded below.

## PDF export and portable report delivery

[REPORT-EXPORT-01](workflows/PDF-EXPORT-V1.md) adds explicit optional `--pdf` and `--package` delivery to WF-04–WF-06, profiles, and suites. PDFs are built from verified results with embedded fonts and existing harness provenance. A sibling ZIP contains sealed reports and unmodified evidence, with strict hash/path/identity checks and report-only retry paths. The default HTML/Markdown/JSON flow, ordinary logger, physical runners, and runtime dependency pins are unchanged; the renderer is an optional extra. Delivered to `devel` at `40714e7`; [Python 3.11/3.14 software and reporting CI passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43358371391). PROFILE-01/SUITE-01 are delivered separately at `e05a120` with passing CI; their final delivery-record head is `b30dd87`.

## Local operator interface

[OPERATOR-UI-01](workflows/OPERATOR-UI-V1.md) implements the owner-confirmed single-user, loopback-only browser interface with the existing Python stack and report styling. It selects/imports fake DUT profiles and WF-04–WF-06 subsets, starts a native suite worker, shows boundary progress, requests cooperative cancellation, and opens PDFs/portable ZIPs. Saved evidence remains authoritative; the page adds operational state and recent history, without automatic retries or resume. Local guarded/browser/installed-wheel checks passed; delivery and CI verification are in progress. Physical drivers, remote access, and AI automation remain separate. Normal logging is unchanged.
