# Broader command and backend support review

Reviewed November 13, 2026, against `devel` at `1258f0bcd4f1712690c77be99502cfd6e0207328`.

## Scope and conclusion

The owner requested a review of useful command/backend gaps that can be developed with fakes and checked on the current meter, without additional hardware or changes to normal logging. This review is complete. The priorities below are recommendations, not newly required deliverables or authorization to run them. No hardware session was opened, command enabled, dependency changed, or runtime code modified for this review.

The current human-started POWER REF deliverable remains usable with no mandatory feature work outstanding. Most useful near-term command work is **physical verification of existing implementations**. True serial polling is the clearest useful **backend implementation gap**. Complete command coverage, a replacement meter, and unattended operation are not prerequisites for the present deliverable.

## What is already implemented

The [inventory](COMMANDS.md), [coverage matrix](COVERAGE.md), [ambiguity register](AMBIGUITIES.md), [software guide](../SOFTWARE.md), and [offline parameter audit](../validation/OFFLINE-PARAMETER-COVERAGE.md) remain the detailed references.

An I/O-free registry tally reproduced 118 command/syntax variants across 50 families: 78 encodable and 40 guarded. The 78 include eleven contextual helpers and two zero/calibration procedures that require true serial polling; they are not 78 independently executable, physically verified operations. The bus inventory has three byte-transfer paths, one conditional project-local Go To Local path, fifteen deferred normal-API operations, and one instrument C0 exclusion. `BUS_GUARDS` retains seventeen entries because it also dispatches conditional G008 and exclusion G020.

| Existing coverage | Remaining distinction |
| --- | --- |
| Typed encoders, parameter boundaries, malformed replies, transaction serialization, uncertainty, and failed-transfer disposal | Scripted tests establish software behavior; they do not establish the meter's response to every command/value |
| Identification, normal acquisition/status, W/dBm selection, POWER REF switching, free-run/local cleanup, and named timeout/reconciliation cases | Existing Mac/Pi bench records cover their named sequences, not every parameter or command combination |
| `ERR?`, `*ESR?`, `*ESE?`, `*SRE?`, `*STB?`, `OD`, `SM`, and `LP2` | Public query/parsing paths already exist; most additional query framing/lifecycle cases lack bench evidence |
| Range, filter, resolution, trigger, correction, relative, and limit command encoders | Many are implemented but lack explicit reversible physical cases; no reason to rewrite them before testing |
| `zero()` and `calibrate()` | Scripted polling procedures exist; the production USB transport does not provide their required `serial_poll` capability |

The forty guarded variants are thirty table clear/edit/label operations, two identification aliases, four legacy learn/mask/restore forms, reset/self-test/special-menu operations, and the `DF` display alias. Guard rejection tests are not implementation support.

## Recommended order

These are small selectable batches. Existing fake tests should be reused; add cases only for new orchestration, newly observed framing, or a concrete uncovered failure. Do not recreate the existing parameter campaign or require a complete cross-product.

| Priority | Useful gap and existing IDs | Fake work first | Later check with current meter | Scope boundary |
| --- | --- | --- | --- | --- |
| 1 | Explicit diagnostics using existing status/display/register queries: C027–C030, C067, C095, C108, C110 | Exercise an opt-in diagnostic sequence through existing APIs: retain raw replies and query order, identify which reads can clear evidence, stop on malformed/late replies, and preserve uncertain-session guards. Existing per-query parsers are already tested | With POWER REF off and no pending trigger/calibration, capture actual register/mask framing and compare status/display with the front panel. Start with mask reads and non-clearing `*STB?`; keep error/event reads separately identified | No automatic diagnostics added to the logger, no unsolicited register clear, no intentional error injection in the initial batch |
| 2 | Read-only configuration snapshot, C064 `LP2` | Existing parser and transport tests preserve `@2` plus 58 binary bytes, including embedded newlines. Any new export/helper needs complete-frame, truncation, no text decoding/termination loss, and post-read ordering cases | Capture the complete binary frame with POWER REF off, retain it as opaque setup evidence, then verify an ordinary acquisition and live/local cleanup | No field decoding without a byte layout, no claim that equal/different hashes prove equivalent/different settings, no binary restore or automatic rollback |
| 3 | Reversible acquisition settings: C042–C044 filter, C074/C087/C091 range, C076 resolution, C111–C114 trigger | Reuse exact-domain tests. Add only chosen sequence/state-readback/restoration cases, including failure stopping further commands. Keep acquisition replies ahead of ASCII status queries | Test a few documented settings one at a time, with POWER REF where a numeric observation helps. Record before/after settings and achieved sampling; restore the recorded setup and free-run/local state | No default/profile changes, no full parameter sweep, no inference about sensor accuracy, settling, or bandwidth |
| 4 | True serial polling, G015, enabling existing C001/C116 procedures later | A separately selected negotiated backend extension needs USB488 capability, request/tag/status/length/interrupt-response checks, deadlines, worker disposal, unsupported-device rejection, and clear separation from ASCII `*STB?` | First prove one bounded source-off poll on the actual adapter/host and preserve fresh ordinary communication. Only after that, separately select prepared zero/CAL procedure checks using the connected sensor and POWER REF | No dependency upgrade, zero/CAL execution, SRQ-event claim, or logger hook implied by this review |

Recommendation: start with the bounded diagnostics batch. It is directly useful when explaining a failed test or unusual meter state, and it can expose real framing differences before adding a convenience interface. `LP2` is a small independent readback check; acquisition-setting verification adds confidence in already supported controls. Serial polling has the greatest new backend value but a larger implementation/evidence cost.

## Command semantics that affect the proposed tests

The publisher operating manual is the authority, rather than modern SCPI conventions:

- [Printed 3-32/PDF 62](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=62) specifies an uninterrupted `LP2` result: `@2`, 58 binary bytes, and EOI on the last byte. The manual names contained settings but does not provide their byte layout here. A readback helper cannot safely turn this into a typed restore API.
- [Printed 3-33/PDF 63](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=63) states that `SM` updates only after a measurement. A setter followed immediately by `SM` is not sufficient proof of a changed setting. Complete and consume the acquisition before selecting the status response; interpret range/filter codes using their documented mapping rather than comparing raw codes with requested counts.
- [Printed 3-37–38/PDF 67–68](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=67) distinguishes the mask, status byte, serial-poll lifecycle, and ASCII `*STB?`. The manual explicitly says `*STB?` does not clear the status byte. Serial polling can clear it after SPD/unaddressing; the two routes are not interchangeable.
- [Appendix A-1/PDF 151](../../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf#page=151) describes error latching and how reading `SM` can clear resolved error evidence. Calling a query “read-only” does not make it observationally neutral. Remaining event/error lifecycle questions stay in [A06](AMBIGUITIES.md#a06); do not import IEEE/SCPI assumptions.
- The existing numeric query parser requires three ASCII digits plus CR/LF, with a maximum of 127 for `*STB?` and 255 for the other byte-valued queries. These are tested parser contracts. Capture actual raw replies for the additional physical queries before claiming their full framing is accepted. Do not silently loosen the parser or send extra queries to recover from a partial frame.
- Filter encoding accepts exact powers of two from 1 through 512. Numeric grids, range/resolution domains, and correction limits already have [offline coverage](../validation/OFFLINE-PARAMETER-COVERAGE.md). Manual rounding ambiguities are not a reason to introduce rounding or new defaults.

For a later reversible batch, the original values must be known and restorable through supported commands before changing them. An opaque `LP2` capture is not a working rollback mechanism. Stop the batch if restoration cannot be established. Keep original observations and failed results; neither automatic retries nor post-fault probes belong in the same uncertain session.

## Backend findings and decision

The installed, qualified profile remains pinned. As of this review, GitHub reports [PyVISA-py 0.8.1](https://github.com/pyvisa/pyvisa-py/releases/tag/0.8.1) as the latest published release. Its USB session lacks native serial polling, explicit REN control, and bus trigger methods. The project-local conditional Go To Local extension is already separately tested; this is not general VISA bus support.

The [development changelog at inspected commit be0aeb4](https://github.com/pyvisa/pyvisa-py/blob/be0aeb4156e658426ce306a5c2bff399766be187/CHANGES) places USBTMC status-byte, trigger, and REN additions under **0.9.0 unreleased**. The corresponding [USB session implementation](https://github.com/pyvisa/pyvisa-py/blob/be0aeb4156e658426ce306a5c2bff399766be187/pyvisa_py/usb.py#L228) and [protocol implementation](https://github.com/pyvisa/pyvisa-py/blob/be0aeb4156e658426ce306a5c2bff399766be187/pyvisa_py/protocols/usbtmc.py#L593) are useful design references, not a released or physically accepted backend for this project. No upgrade to a development branch is recommended merely to broaden the command count.

The adapter's published firmware at [88a1383](https://github.com/xyphro/UsbGpib/commit/88a13830eea3e2d8bf9f6e33123cc1523f42c70a) provides a concrete serial-poll route:

- [USB READ_STATUS_BYTE handler](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/TestAndMeasurement.c#L669) asserts REN, invokes `gpib_readStatusByte`, merges any cached SRQ byte, and prepares control and interrupt responses.
- [GPIB polling implementation](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/gpib.c#L149) sends listener addressing, SPE, talker addressing, reads the status byte, then sends SPD and UNT. This is actual bus polling rather than an ASCII query.
- Important limitation: that function returns a byte even after an internal timeout/recovery, and the USB handler writes a success status without separately propagating that GPIB timeout. A zero byte must not be treated as proof of a successful instrument poll or completion. A candidate needs a bounded completion loop and explicit evidence limits; cached SRQ merging also needs to be understood. Published source alone does not prove the exact installed firmware binary or end-to-end behavior.

A narrow, opt-in serial-poll extension using the pinned transport is worth investigating if selected, following the existing conditional-capability model. It must remain separate from normal logging. Prove the backend mechanism before removing any procedure guard, and record host-specific physical evidence before claiming support on Mac or Pi.

## Lower-value or unresolved work

| Candidate | Disposition and reason |
| --- | --- |
| True GET/bus trigger, G013 | Firmware and upstream development sources provide leads, but existing ASCII acquisition triggers already serve the workflows. Defer unless a concrete synchronization need appears |
| Device clear, IFC, raw bus commands, lockout, SRQ events, or parallel poll | Not needed to enlarge the current POWER REF workflow. Preserve guards and existing named recovery evidence; healthy clear or an interrupt endpoint does not establish fault repair or event delivery |
| Automatic zero/CAL | Useful future setup automation after true serial polling works. Current procedures are fake-tested; a later prepared sensor/reference test checks software interaction, not meter certification |
| Duty/offset/relative/limit/frequency-correction modes | Existing code, but changed interpretation/corrections and incomplete readback/restoration make them a later explicit experiment. No radio is needed for selected mode checks; POWER REF cannot validate frequency response or multiple transmitter levels |
| Table clear/edit/label, persistent save/recall, binary restore | Keep ambiguous guards and avoid persistent setup changes. Table editing needs exact framing and a designated backed-up table; restore needs a known layout/format and a separate use case |
| `ID`/`IDN?`/`DF` aliases, display suppression/messages | Little new measurement value compared with working identification and front-panel observations; do not prioritize just to raise coverage totals |
| Reset, self-test, special-menu emulation | Keep guards. Ambiguous effects and disrupted setup do not serve an identified workflow gap |
| Another backend/adapter | No demonstrated need for existing operation. Evaluate only for a selected capability the pinned path cannot provide |

None of these deferred choices becomes a release requirement. Existing hardware limitations and provenance remain attached to results. POWER REF supports interaction and repeatability development; it cannot stand in for a transmitter's frequency, output-level, or supply-voltage experiment.

## Review verification

The review compared the registry, driver/parser/transport paths, existing tests, command/bus inventories, ambiguity records, and named bench summaries. The original summary tables (PDF 71–72), learn/status pages (62–63, 67–68), and error-lifecycle page (151) were visually checked from derived previews without changing publisher files. Released/development backend and adapter sources were inspected through their official repositories at the revisions linked above.

The focused existing offline suite passed **360 tests** through `tools/offline_qa.py`: command encoding, parameter boundaries/guards, protocol/offline protocol parsing, instrument procedures, transport, and USB488 local-return tests. A direct pytest invocation was rejected by the repository's offline guard before tests ran; the guarded invocation then passed. These are regression results for existing code, not software acceptance of a new serial-poll or diagnostic implementation. No new measurement or physical acceptance result is claimed.

## Selected follow-up

After this review was committed and pushed at `c98e187`, its four [CI jobs](https://github.com/lbussy/HP-437B-Automation/actions/runs/43533490440) passed. The owner then selected the diagnostics batch using fakes first. The [subsequent implementation and software evidence](../validation/DIAGNOSTICS-FAKES.md) are separate from this review: fixed query plans, explicit latch-read selection, raw ordered receipts, and stop-on-failure through existing APIs. No physical command support is promoted. Other priorities remain optional and unimplemented by this batch.

The owner subsequently selected the [physical diagnostics runner](../validation/DIAGNOSTICS-PHYSICAL-RUNNER.md), with injected backend tests first. That separate runner is implemented; the [single supervised basic wspr5 case](../validation/PI-DIAGNOSTICS-BASIC-20261113.md) subsequently passed four query captures, cleanup/closure, and separate owner final-state confirmation. The subsequent [single passive wspr5 latch-read pass](../validation/PI-DIAGNOSTICS-LATCHES-20261113.md) also completed with separate owner final confirmation; A06 clearing/queue semantics remain unqualified. No normal logging or bus-capability guard changes are included.
