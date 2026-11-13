# Supervised reconciliation: physical bridge preparation

November 13, 2026. Owner-authorized physical integration of the [bounded supervisor](BOUNDED-RECONCILIATION-FAKES.md), with fakes first. Status: implementation/fake checks complete; the [first healthy current-Mac case](RECONCILIATION-HEALTHY-20261113.md) subsequently passed protocol and closure checks, with separate owner confirmation of live readings, RMT off, and POWER REF off. The healthy case is complete. The preparation and procedure below retain their original scope. This is an optional recovery extension, not a new project completion gate.

## Implementation and evidence boundary

The bounded fake supervisor was delivered at `fd92464`; [all four CI jobs passed](https://github.com/lbussy/HP-437B-Automation/actions/runs/43509957790). The changes described here are subsequent physical-bridge work and are not covered by that earlier CI result. Delivery CI must be associated with its own commit.

The new [physical bridge](../../src/hp437b/reconciliation_physical.py) provides an explicitly gated `run_physical()` entry point, separate from `run_simulated()`. A standalone [supervised tool](../../tools/reconcile_meter.py) requires an explicit resource, setup file, output directory, run association, and fresh supervision confirmation. Its `--help` and missing-confirmation paths do not open hardware. There is no operator-interface integration, automatic fault hook, test resumption, or change to normal logging.

The bridge performs descriptor preflight for exactly the named `03eb:2065` USB serial, XyphroLabs/GpibUsb descriptor strings, and interface zero with USB488 class/subclass/protocol `fe/03/01`. Missing or duplicate matches do not select another adapter. It then uses pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1, checks the opened device again, and negotiates the existing project-local GTL profile. Descriptor access happens before VISA opens the resource/asserts remote enable. No firmware query, target-address change, EEPROM write, reset, or clear is added.

The bridge runs synchronous VISA inside the existing disposable supervisor child. It does not nest the ordinary `VisaTransport` process inside that child or change the production transport. Native VISA/USB calls are capped at two seconds. The physical supervisor reserves an additional three-second finish allowance before bounded disposal, so a pending native read can complete its existing abort handling. This allowance discards late results and is not proof that all backend faults finish or recover within three seconds. A still-hung worker is terminated and the case stops with operator recovery needed.

The parent owns Ctrl-C cancellation. The child ignores SIGINT and checks a shared stop event between operations, allowing a pending native call to return before raw transport close and preventing further commands after cancellation. Close is attempted even after work expiry; failed probes do not receive new ASCII cleanup. No late reply or worker receipt bypasses normal-exit/disposal checks.

The child holds the existing POWER REF runners' resource lease at `tmp/workflow-locks/<sha256-of-exact-resource>.lock`. A separate supervisor lease excludes other reconciliation parents. This cooperates with WF-01–WF-03 using the same configured resource string; it is not universal exclusion of external programs or differently spelled resource aliases. Other control applications must remain closed for the supervised case. Prior-worker-stopped is an explicit caller prerequisite, not a guessed PID or a fabricated physical observation.

Receipts retain host, package versions, declared meter/sensor label identities, preparation assertions, observed identification/status, shutdown/disposal facts, and fake-versus-physical evidence origin. A USB serial derived from instrument identification is not a unique adapter hardware serial. The 437B identification reply can omit its own serial, and the sensor label is not read over USB. `physical_identity_verified` therefore remains false; labels and front-panel observations remain separate supplied evidence.

## Offline verification

**Thirty new physical-bridge cases and the original 41 supervisor cases passed: 71 focused tests.** Actual bridge code is used with fake PyVISA managers, handles, USB descriptors, control transfers, and raw reads inside real spawned workers. Injected receipts are explicitly labeled `evidence_origin: injected_fake`, even though they exercise the physical entry point.

Coverage includes descriptor/interface/duplicate/permission failures, opened-device mismatch, dependency-pin changes, unsupported/rejected GTL, changed meter ID, partial writes, malformed/incomplete/oversized replies, source on, close failure, bounded absence retry, a hung native read, actual shared lock exclusion, missing preparation, and unavailable prior-worker proof. Cancellation cases verify both a simulated completed abort and a late valid reply: neither permits another command or a successful reconciliation. A directed child SIGINT case verifies that parent-controlled cancellation retains native finish/close. Help and missing-confirmation subprocess checks remain hardware-free.

```sh
.venv/bin/python tools/offline_qa.py --seconds 180 -- \
  .venv/bin/python -m pytest -q \
  tests/test_reconciliation_physical.py tests/test_reconciliation.py
```

The full guarded Python 3.14 reporting-environment regression passed **1,543 tests**, with three opt-in stress cases skipped, in 252.78 seconds. It ran outside the sandbox for existing loopback UI tests, with VISA/USB access still blocked except for explicitly injected fakes. Source-distribution and wheel builds passed; a guarded test imported the new bridge from the built wheel and reconciled through an injected backend, retaining `evidence_origin: injected_fake`. Ruff lint/format checks, repository Markdown/link/inventory/PDF-checksum checks, and `git diff --check` passed.

No real USB discovery/open, meter command, reference change, physical timeout, or cable action occurred during preparation. Fake success does not establish Mac/Pi hardware recovery, actual abort completion, or repair of an already-wedged adapter. The existing logger, production transport, instrument API, physical measurement runners, CLI defaults, and operator UI remain unchanged.

## First supervised current-meter case

The proposed first case is **one healthy source-off reconciliation**, not fault injection. It checks the new physical bridge and healthy closure before considering a separate post-timeout recovery case.

Fresh owner confirmation needed immediately before starting:

- Adapter USB is attached to this Mac, with the same meter `3125U33223` and sensor `MY41094127`; report any change rather than assuming these labels still apply.
- Sensor cable is on SENSOR and the sensor RF input remains directly on POWER REF, with no radio or other RF source connected.
- POWER REF is off, the display has live numeric readings, and RMT is off; leave settings unchanged.
- Meter/sensor are warmed up, other control applications are closed, and the owner can remain at the meter for about five minutes and operate PRESET/LOCAL if needed.

The existing address 13 and observed USB serial `HEWLETT-PACKARD_437B_1.8` are baseline facts, not values to scan/set automatically. The selected resource and actual descriptor match will be checked during the authorized run. No extra PCB-revision investigation, zero/CAL, correction changes, or equipment exchange is required.

Prepare an ignored setup JSON after that fresh confirmation, containing `expected_idn`, meter/sensor label serials, and `prepared` booleans named `power_ref_off`, `direct_reference_path`, `warmed_up`, `other_control_apps_closed`, and `operator_available`. The expected IDN baseline is `HEWLETT-PACKARD,437B,,1.8`; a mismatch stops the case. Keep this setup and the resulting receipt outside original sealed bundles.

The tool invocation requires `--confirm-supervised` and `--confirm-prior-worker-stopped`, with `--resource`, `--setup`, `--output`, and `--failed-run-id`. For this healthy preflight, use an explicit association such as `supervised-healthy-bridge-preflight`; do not label it as recovery from a new fault. No hardware invocation is included in the preparation checks above.

The first run uses one attempt, a 30-second work budget, three seconds of native finish allowance, bounded worker disposal, and a 60-second total policy ceiling. It performs descriptor/open checks, `*IDN?`, `SM`, source/error checks, then TR3 and negotiated GTL on a healthy probe, followed by close. It creates no measurement CSV, never switches POWER REF, and never starts a workflow. Source-on, mismatch, malformed reply, timeout, or failed cleanup stops the case without retry, reset, or blind source-off commands.

After Python closes, request a separate owner observation without pressing keys: live numeric readings updating, RMT off, and POWER REF off. If recovery keys are needed, record that fact separately; do not claim fully automatic restoration. If communication becomes uncertain, stop and use the known manual recovery only when needed. No automatic second attempt, forced timeout, USB port reset, reboot, or cable action is part of this first case.

A later post-timeout trial would need its own bounded procedure after healthy bridge acceptance. It is not included or implicitly launched by this preparation. Normal logging remains unchanged throughout.
