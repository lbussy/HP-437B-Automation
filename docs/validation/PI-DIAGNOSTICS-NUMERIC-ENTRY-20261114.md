# wspr5 invalid numeric-entry ERR/SM observations

November 14, 2026. The separately authorized [fixed numeric-entry experiment](DIAGNOSTICS-NUMERIC-ENTRY-FAKES.md) completed on the current meter, including owner final-state and before/after setting confirmation. This record establishes specific entry/event observations, not general ERR queue semantics, measurement-error handling, or meter performance. Normal logging is unchanged.

## Authorization, setup, and provenance

The owner reported **FREQ 0.0500GZ and CAL FAC 100.0%**, viewed and exited without changes. They confirmed unchanged wspr5 connections, POWER REF/RMT off, live readings, other apps closed, and five-minute availability. The prepared runner checked no prior control worker, retained the existing shared resource lock, matched the staged runtime manifest, and used the supplied originals as metadata only. No valid frequency or calibration-factor entry was sent.

The isolated installation was `/home/pi/hp437b-qualification/diagnostics-numeric-entry-20261114T131236Z`. Preparation passed **319 installed-package guarded tests in 86.46 seconds**, with lint/formatting and installed/delivered runtime hash checks passing. Build provenance is base commit `2e06392e43389730f2ba8f8588c2e9947d685b1e` plus modified-source runtime hashes, rather than a fabricated later commit identity. Delivery SHA-256: `af75587925df4a9d80c64741ba6bcec8e870f9b4b2a8c0b73b00b49c437729a0`.

The exact expected resource was `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`. The meter identified as HP 437B firmware 1.8 with an empty serial field; supplied labels remain meter `3125U33223` and sensor `MY41094127`. The host was Python 3.13.5/Linux 6.18.60+rpt-rpi-2712/aarch64/glibc 2.41, using pinned PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. The original normal logger and udev rule were preserved.

## Observed sequence

The pass ran at **13:21:35.637228–13:21:41.288714 UTC**, completing in **5.651591 seconds**. All **64 distinct steps** completed and were accepted before deadline: 57 queries, five fixed `FR-3GZ` stimuli, and two no-command waits. CLI exit was 0, the worker exited normally with code 0, and disposal was not forced.

| Case | ERR replies | ESR replies | SM entry errors | SM measurement errors |
| --- | --- | --- | --- | --- |
| SM first | 0, 0, 0 | 16, 0 | 82, 0 | 0, 0 |
| ERR first | 0, 0, 0 | 16, 0 | 82, 0 | 0, 0 |
| ESR first | 0, 0, 0 | 16, 0 | 82, 0 | 0, 0 |
| Two-second wait, SM first | 0, 0, 0 | 16, 0 | 82, 0 | 0, 0 |
| Two-second wait, ERR first | 0, 0, 0 | 16, 0 | 82, 0 | 0, 0 |

The waits were **2.000057** and **2.000062 seconds**. Baseline and final ESE/SRE/STB, three ESR reads, and three ERR reads were all zero. SM frames showed reference off, normal mode, no standby, no measurement errors, preserved configuration flags, range/filter 11/17, and W units. Each first post-stimulus SM contained entry error 82, and its second read contained zero. No QX, paired-error case, valid frequency/CAL FAC setter, source operation, clear/preset, zero/CAL, USB reset, reboot, retry, or cable operation occurred.

TR3/free-run and USB488 Go To Local were accepted, transport closed, and installed diagnostic runtime, original normal-logger runtime, and permanent udev-rule hashes remained unchanged. Quiet SM fields alone were not used to claim preservation of FREQ or CAL FAC.

## Meaning and limits

The invalid numeric entry produced the manual's execution event and a numeric **entry error observable through SM**, even while ERR returned zero. Reading ERR three times before SM did not consume the observed entry latch; reading ESR before SM also left 82 observable. Repeated SM reads gave 82→0 and ESR gave 16→0 under all five selected orders/windows. This adds scoped entry-latch and execution-event read-clear evidence to A06.

Consequently, an ERR zero cannot be interpreted as absence of an entry error on this setup, and ERR cannot be treated as a general queue of these command/numeric-entry errors. This independently demonstrates useful numeric-error visibility rather than merely another unobserved QX numeric-code hypothesis. There is no demonstrated ERR queue fault requiring a normal-logging change.

Among the specific fakes, the ERR-excludes-entry/SM-visible model matches the observations. This does not prove internal firmware selection logic, that ERR reports every measurement/device error, general queue existence/order/capacity, other entry codes, or arbitrary timing. There were no paired errors. The original receipt conservatively retains `cause: unresolved` and `queue_observation: not_tested`; this interpretation does not rewrite it. Other event/latch behavior and general error-selection semantics remain unresolved, and no additional test becomes a release requirement.

## Owner final confirmation and settings

After Python closed, the owner answered **“Yes”** to the combined final check: live readings updating, RMT off, POWER REF off, then viewing/exiting FREQ and CAL FAC and confirming they remained **0.0500GZ and 100.0%**. No additional error indication was separately reported. No manual re-entry or recovery was requested or reported. The owner observation is retained separately, while the original receipt retains `numeric_settings_verified: false`, `front_panel_confirmation: not_provided`, and `physical_identity_verified: false`. The setting comparison is owner evidence, not USB readback.

## Retained evidence

Remote capture: `/home/pi/hp437b-qualification/diagnostics-numeric-entry-20261114T131236Z/runs/numeric-entry-20261114T132135Z`. Retrieved raw records remain ignored under `output/logs/pi-diagnostics-numeric-entry/numeric-entry-20261114T132135Z/`; delivery, isolated preflight, package/source checks, and local verification stay ignored under `tmp/numeric-err-selection/`.

| Evidence | SHA-256 |
| --- | --- |
| Original `capture/diagnostics.json` | `0e4b08397e75e240a0f588d2269e8b523c56ebbfe06ef05c6d1b0b6b80107cbe` |
| Wrapper `result.json` | `b56d45abbc482dca028928f1754db3042678ce01d54757b8b6abc23059e15dae` |
| Separate owner final confirmation | `a969627d89e889913cf9a34fb0d211b83eb69a5b67aad439ebebcc42ddaa5b98` |
| Unchanged permanent udev rule | `9a103e41be902ef27cc1068b768c68bb6781a5d3f35f70d9657a86c5e64af6be` |

Local verification independently checked the original receipt hash, all 64 distinct timely completed steps, each ordered case's ERR/ESR/SM values, original-setting metadata, native worker exit, accepted local return/transport closure, and logger/rule/runtime preservation. The separate owner record was added without modifying the original capture. Raw local measurements and tool state are not committed.
