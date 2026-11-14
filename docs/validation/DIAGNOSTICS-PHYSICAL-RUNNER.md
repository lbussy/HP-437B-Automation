# Supervised diagnostics: physical runner preparation

November 13, 2026. The owner selected a physical diagnostics runner, with fakes first, after the [fake-first batch](DIAGNOSTICS-FAKES.md) was delivered to `devel` at `5200697` with [all four CI jobs passing](https://github.com/lbussy/HP-437B-Automation/actions/runs/43535323965). Physical runner implementation and offline verification are recorded here; no meter or USB session was opened during preparation. The subsequent [single basic wspr5 case](PI-DIAGNOSTICS-BASIC-20261113.md) is complete with protocol/closure evidence and separate owner final confirmation; optional latch reads remain untested. The preparation and first-test procedure below retain their original scope.

## Delivered scope

[diagnostics_physical.run_physical](../../src/hp437b/diagnostics_physical.py) is a separate, explicitly selected entry point. The standalone [diagnose_meter.py](../../tools/diagnose_meter.py) requires an exact USB resource, setup JSON, new output directory, and fresh supervision/prior-worker-stop confirmations. `--help` and missing-confirmation paths do not discover or open USB devices. No normal logger, measurement runner, operator-interface flow, command registry, dependency pin, or reconciliation behavior is changed.

The runner reuses the existing pinned USB bridge's descriptor/opened-device checks, local-return negotiation, and synchronous VISA operations inside one disposable spawned child. It does not run reconciliation as a preflight. In particular, **there is no automatic `SM` preflight**, because reading status can clear resolved error evidence. POWER REF off and absence of a pending trigger/calibration are fresh operator assertions, retained in the receipt. The runner neither switches the reference nor infers continuous source state from an old status reply.

The selected `03eb:2065` adapter must match the exact supplied USB serial, XyphroLabs/GpibUsb descriptors, USB488 interface zero, and opened-device identity. The expected meter identification is checked with `*IDN?`. No fallback adapter, GPIB scan/address change, firmware operation, clear/reset, or backend upgrade is attempted. The existing qualified PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1 pins and conditional Go To Local profile remain required for this runner.

The default diagnostic sequence is `*ESE?`, `*SRE?`, `*STB?`, then `OD`. The explicit `--include-latched-reads` option appends `ERR?`, `*ESR?`, and finally `SM`. The shared collector preserves the original fake-only API and its existing behavior. [Manual references and read effects](DIAGNOSTICS-FAKES.md#delivered-scope) remain applicable: `*STB?` is an ASCII query rather than a serial poll, `OD` is display text rather than a fresh power sample, and error/event/status lifecycle questions remain open. This runner does not establish those physical semantics through fakes.

## Ownership, deadlines, and evidence

- Exactly one attempt; no retries, post-fault probes, source switching, setting changes, zero/CAL, or test resumption.
- The child holds the existing exact-resource POWER REF/reconciliation lease at `tmp/workflow-locks/<sha256-resource>.lock` through raw transport close. A diagnostics supervisor lease is held through worker disposal. Busy ownership stops before discovery. Use the same lock root across installations (`--workflow-lock-root` overrides the tool's source-root default). This cooperates with the existing exact resource string and shared lock directory; it does not exclude unrelated control programs or alternate resource aliases. Other control applications must be closed.
- Default work budget is 20 seconds, with a 25-second total policy ceiling. Existing VISA/control-transfer timeout values are capped at two seconds per native call. Three seconds are reserved to let pending native work/abort/close finish before the existing bounded process-disposal mechanism is used. These budgets do not guarantee repair of a stalled adapter or restoration after forced termination.
- The parent owns Ctrl-C cancellation; the child ignores direct SIGINT and checks the stop event/deadline between operations. An in-flight operation may finish. Cancellation or deadline expiry cannot become successful completion because a late reply or receipt arrives during shutdown grace.
- Healthy collection sends explicit `TR3`, then negotiated Go To Local, then raw close. After a query failure or observed cancellation/expiry, the worker performs raw close only, with no new ASCII cleanup. Failure during cleanup is separately recorded. A hung child is disposed, and transport closure remains unknown unless it was actually reported; worker disposal is not front-panel recovery proof.
- A new `diagnostics.json` is persisted before launching the worker and updated with query progress. It retains query order/effects, raw hex, parsed values, VISA framing status, timing, preflight identity/environment, declared equipment labels/setup, cleanup, and worker exit/disposal facts. Up to 4,097 raw bytes are retained for an oversized transfer; no continuation read or text-decoding workaround is used. Partial/malformed replies remain evidence even when rejected.
- Rows received after cancellation/deadline are retained with `accepted_before_deadline: false`; uncompleted work stays incomplete. Success requires all selected rows accepted before the deadline, successful local return/close, and normal worker exit. Completion is collection success, **not** a meter-health or calibration verdict.

Injected integration factories must explicitly declare simulation and are labeled `evidence_origin: injected_fake`; the physical default is labeled `physical_bridge`. Label serials are supplied provenance, not hardware-verified USB identities. `physical_identity_verified` remains false, and `front_panel_confirmation` remains `not_provided`. Keep the later owner's actual observation separate from the original receipt.

## Offline software evidence

Forty new [physical-runner tests](../../tests/test_diagnostics_physical.py) use real spawned workers and the actual descriptor/VISA/USB488 bridge with injected USB devices, managers, handles, and transfers. They cover:

- Basic query order without an implicit SM read, explicit latch-read ordering, raw/parsed data, fixed backend pins, two-second native timeout values, and ordinary TR3/GTL/close.
- Absent/duplicate/changed adapter, changed descriptors/interface/opened identity, access denial, changed pins, unsupported local return, and changed meter identification, all without diagnostics or fallback/retry.
- Malformed, partial, oversized, incomplete-EOM, and failed query transfers; preserved raw bytes; no subsequent query or ASCII cleanup.
- Rejected GTL and failed close; preservation of successful query results without a successful batch claim.
- Cooperative cancellation with simulated native abort or late success, late deadline replies, a hung read with bounded disposal, and direct child SIGINT ownership.
- Existing resource/diagnostics leases, lease retention through raw close, prior-worker/setup/argument guards, pre-start cancellation, new-output reservation, and hardware-free help/missing-confirmation subprocesses.

The focused diagnostics, original reconciliation, and transport suite passed **154 tests** under `tools/offline_qa.py`. This includes the 32 original fake-only diagnostics tests, which still pass after extracting their collector for reuse. No fake result promotes a Mac/Pi command matrix cell or establishes physical abort/recovery behavior.

The full local Python 3.14 reporting-environment regression passed **1,615 tests**, with three opt-in stress cases skipped, in 248.60 seconds. Loopback tests ran outside the filesystem/network sandbox while the offline guard continued to block instrument entry points. Lint, formatting, Markdown links/IDs/manual checksums, and `git diff --check` passed. Source and wheel builds passed; packaged diagnostics modules match their final source bytes, and the source distribution includes the standalone tool. The lock-root/help checks were also rerun after exposing the shared-directory option (five passed).

## Isolated wspr5 software preparation

The new source/wheel delivery was safely reviewed for regular relative archive members and transferred through the existing outside-sandbox SSH configuration. Delivery SHA-256 is `c197fb21aed6cd0bdaeb0004c0485c502d65a5c086d96cf4258b5c2bc837c314`. Its manifest identifies base commit `5200697` plus the modified working tree and runtime hashes; it does not claim that the new runner is already committed at that base.

A new non-editable installation is ready at `/home/pi/hp437b-qualification/diagnostics-20261114T005719Z/.venv`. Source and tools are under the same workspace's `source/hp437b_automation-0.1.0`. The Pi reports Python 3.13.5 on Linux 6.18.60+rpt-rpi-2712/aarch64. **214 selected tests passed in 48.24 seconds** through the hardware-blocking launcher, covering diagnostics, physical diagnostics, original reconciliation, transport, instrument, and logger behavior. Lint, formatting, and normal logger help checks also passed. All installed runtime module hashes match the delivered manifest; the retrieved report and full fake-test log were independently checked locally.

The original logger at `/home/pi/hp437b-qualification/20261111/.venv` has unchanged runtime bytes, origin, and pinned dependencies. Its shared modules also match the new installation. The existing udev rule is unchanged at SHA-256 `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be`. No system packages, access grants, service, or other radio program was changed. Dependencies were installed only in the new virtual environment. The preparation did not load the native USB backend, discover/open the adapter, or issue meter commands; injected fakes remain software evidence rather than Pi hardware acceptance.

Local delivery/preflight artifacts remain ignored under `tmp/diagnostics-physical/`; remote preparation logs remain in the new isolated workspace. For the later test, use the existing reconciliation installation's shared lock root, `/home/pi/hp437b-qualification/reconciliation-20261113T233143Z/source/hp437b_automation-0.1.0/tmp/workflow-locks`, through `--workflow-lock-root`, rather than silently creating a second independent lock domain in the new source tree. Fresh prior-worker and other-app checks are still needed immediately before an authorized meter invocation.

## First supervised wspr5 test

The adapter can remain on wspr5 with the existing meter/sensor and unchanged connections. No radio, new hardware, warm-up wait, or zero/CAL is needed for these diagnostic reads. This checks software interaction and reply framing, not instrument calibration or a fresh RF power measurement. Keep the current meter's known provenance/limitations attached to any retained result.

Before the bench run, prepare an isolated source/wheel installation on wspr5 and run its selected offline tests without modifying the normal logger environment or udev rule. Use existing SSH configuration outside the sandbox; do not request a password or alter host access as part of this runner. Check the configured exact resource, expected identification, ordinary-user permissions, and absence of an active prior control worker. USB preflight/open belongs to the freshly confirmed physical invocation, not unattended preparation.

Then request fresh owner confirmation:

- Adapter USB is on wspr5; the same meter `3125U33223`, sensor `MY41094127`, and GPIB/sensor/RF connections are unchanged. Report any change rather than assuming the labels still apply.
- POWER REF is off, the meter shows live numeric readings, and RMT is off. No trigger/zero/calibration is pending; other control applications are closed.
- The owner is at the meter for about five minutes and can use PRESET/LOCAL if needed.

Populate ignored setup JSON with `expected_idn` (`HEWLETT-PACKARD,437B,,1.8` for the recorded current meter), `meter_serial`, `sensor_serial`, and a `prepared` dictionary whose true booleans are `power_ref_off`, `live_readings`, `rmt_off`, `no_pending_operation`, `other_control_apps_closed`, and `operator_available`. Retain the observed USB serial `HEWLETT-PACKARD_437B_1.8` and existing address 13 as baseline facts; do not scan or set the address automatically. Use the exact resource and shared workflow-lock directory already configured for the Pi so its lease agrees with other runners, including when the new source is in an isolated directory.

The first case is one default/basic pass. Run the standalone tool from the prepared source tree with `--resource`, `--setup`, `--output`, `--workflow-lock-root`, `--confirm-supervised`, and `--confirm-prior-worker-stopped`. **Omit `--include-latched-reads`** for that first case. Capture raw mask/status/display framing, close, and stop on the first failure. No forced timeout or cable action is part of this test.

After Python closes, request an owner observation without pressing keys: live readings updating, RMT off, and POWER REF off. Record a needed recovery key separately rather than claiming automatic restoration. Only a separately selected later pass should include error/event/status reads; successful basic framing does not prove their clearing semantics. Normal logging remains unchanged throughout.
