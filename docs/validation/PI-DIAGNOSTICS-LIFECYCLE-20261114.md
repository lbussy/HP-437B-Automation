# wspr5 lifecycle experiment: read-clear observed, error selection inconclusive

November 14, 2026. Status: **partial physical evidence with the planned observation stop**, not acceptance of the complete 69-step experiment. The [fake-first profile and Pi preparation](DIAGNOSTICS-LIFECYCLE-FAKES.md) retain their separate software evidence. No normal logging change was made.

## Authorization and setup

The owner reported FREQ `0.0500GZ` (50 MHz), viewed and exited without changing it, then confirmed live readings, RMT and POWER REF off, unchanged wspr5 equipment/connections, closed other control apps, idle operation, and five-minute availability. The supervised invocation recorded the original frequency for precise recovery if needed. No frequency fixture or restoration was ultimately performed.

One invocation used the isolated `/home/pi/hp437b-qualification/diagnostics-lifecycle-20261114T114137Z` installation, the expected USB resource `USB0::0x03EB::0x2065::HEWLETT-PACKARD_437B_1.8::0::INSTR`, and the existing shared workflow-lock directory. Installed runtime hashes/pins matched the prepared delivery, and no active prior control worker was found before opening. The meter identified as HP 437B firmware 1.8, with an empty serial field; declared labels remain meter `3125U33223` and sensor `MY41094127`.

Host/backend were Python 3.13.5, Linux 6.18.60+rpt-rpi-2712/aarch64, PyVISA 1.16.2, PyVISA-py 0.8.1, and PyUSB 1.3.1. Capture-time build provenance is base `dc75cda` plus the modified-source delivery/runtime hashes. No later commit identity is fabricated for this installed preparation.

## Actual observed sequence

The experiment ran at **11:50:49.434861–11:50:50.277992 UTC**, returning `observation_stop` in **0.843229 seconds**. It completed 29 identified steps (27 queries and two QX fixtures); 40 later planned steps remained unattempted. Every completed step was accepted before its deadline.

| Phase | Observed values | Interpretation within this case |
| --- | --- | --- |
| Baseline | ESE/SRE/STB 0; ESR 128 → 0 → 0; ERR 0 → 0 → 0; both SM frames errors 0/reference off/normal live W | The initial Power On bit was present on the first read and absent on the next two; baseline permitted the command-error test |
| Command-error event | QX once; ESR 32 → 0 → 0; ERR 0 → 0 → 0; both SM frames errors 0/reference off/normal live W | A new command-error bit appeared after the fixed invalid command and was absent on subsequent ESR reads |
| Isolated error A | QX once; ERR 0 → 0 → 0; ESR 32 → 0 → 0; both SM frames errors 0/reference off/normal live W | Command-error event was observable even when ERR was read first, but ERR never returned the expected entry code 91 |
| Remaining phases | Not attempted | No FR-3GZ, no paired A/B order cases, and no final phase |

The runner stopped after `single_a` with reason `isolated_entry_error_not_observable_no_pair_inference_permitted`. `accepted_full_case` remains false. Its CLI returned 1 to distinguish an incomplete experiment from complete acceptance; the worker itself exited normally with code 0.

The publisher [Figure 3-7, printed 3-39/PDF 69](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=69) assigns Power On to 128 and command error to 32. Repeated observations support read-clear behavior for those observed bits on this current-host/current-firmware sequence. The command bit was independently induced twice, with the same 32 → 0 → 0 result under both ESR-first and ERR-first query ordering. This does not establish every event bit, simultaneous-event race handling, other firmware/hosts, or the time of the original power-on event.

The zero ERR replies do **not** establish absence of a queue, its order/depth, measurement-error selection, or why entry code 91 was not exposed. SM also reported entry error 0 when sampled after those query groups. Whether intervening valid queries affect the entry latch, ERR selects another class, or another firmware-specific rule applies remains unresolved. No second session or modified experiment was launched to chase a preferred result.

## Closure and separate owner confirmation

After the observation stop, healthy communication performed TR3/free-run, accepted USB488 Go To Local through `xyphro-usb488-gtl-v1`, and raw close. The worker stopped normally with exit code 0, no forced termination, and `transport_closed: true`. No mask setter, clear/reset, preset, valid setting write, calibration/zero, RF switch, retry, reboot, or cable action occurred. Only the two fixed QX error stimuli were sent.

The owner answered **Yes** to the no-key confirmation of live readings updating, RMT off, and POWER REF off; no additional error-message description was supplied. This is separate owner evidence, not an inferred front-panel observation or rewritten original receipt. No manual frequency restoration was needed because no FR command was issued.

## Preservation and retained evidence

The original Pi logger's source bytes, dependency pins, and origin matched its before/after snapshot. The existing udev rule and isolated installed runtime were unchanged. Normal logging remains unchanged.

The remote case is `/home/pi/hp437b-qualification/diagnostics-lifecycle-20261114T114137Z/runs/lifecycle-20261114T115049Z`. The complete retrieved evidence remains ignored under `output/logs/pi-diagnostics-lifecycle/lifecycle-20261114T115049Z/`. The original receipt hash matches the remote capture report; step counts/IDs, exact values, deadline acceptance, early stop, absence of frequency fixtures, cleanup, worker exit, and preservation facts were independently checked locally.

| Artifact | SHA-256 |
| --- | --- |
| Original receipt | `3e3f8a264a2c2b3da543cce2efb704c73bb3f62605c67ac381fb61a30bbdb07c` |
| Capture/preservation summary | `50d4086f0a4033b33d5bf1262d6265674b660b5fbda01e801d2427470de3f715` |
| Separate supplied owner final observation | `fedf58f79ca4d2b3b753f546353beebe8119691fc11a5ce8994d09cf5d7782ed` |

The original receipt retains `front_panel_confirmation: not_provided` and `physical_identity_verified: false`. Declared labels, exact captured replies, and later supplied owner observations remain separate facts.

## Remaining scope

The two observed event-bit read-clear cases have current-Pi evidence. ERR selection/queue semantics and the unexecuted frequency/pair phases remain inconclusive/unqualified; [A06](../inventory/AMBIGUITIES.md#a06) stays open. This bounded stop is an expected safety/interpretation branch already covered by the invisible-entry-error fake, not a reason to change normal operation, weaken the guard, or assume FIFO semantics. Any further probe is separately selected work, not a new completion gate for the current POWER REF deliverable.
