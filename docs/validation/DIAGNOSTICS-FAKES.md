# Explicit diagnostics: fake-first batch

Implemented November 13, 2026, after the owner requested the first batch from the [command/backend review](../inventory/COMMAND-BACKEND-REVIEW.md). That review and its checklist updates were pushed to `devel` at `c98e187`; all four [software/reporting CI jobs](https://github.com/lbussy/HP-437B-Automation/actions/runs/43533490440) passed on Python 3.11 and 3.14. The diagnostics changes described here are subsequent local work, not covered by that remote CI result.

## Delivered scope

[diagnostics.run_simulated](../../src/hp437b/diagnostics.py) runs a finite, explicitly simulated diagnostic sequence through the existing `Instrument.query` parser/transaction APIs. It has no resource argument, transport factory, hardware discovery, physical mode, CLI/UI integration, or normal logger hook. It adds no command encoders, backend capabilities, dependencies, or newly required deliverables.

The default sequence is `*ESE?`, `*SRE?`, `*STB?`, then `OD`. Setting `include_latched_reads=True` explicitly appends `ERR?`, `*ESR?`, and finally `SM`.

| Query group | Evidence and limits |
| --- | --- |
| `*ESE?` / `*SRE?` | Read masks; no enable-mask setter is sent |
| `*STB?` | ASCII status query, documented not to clear the status byte; not a true serial poll |
| `OD` | Display text, preserved as text; not treated as a fresh numeric power measurement |
| Optional `ERR?` / `*ESR?` | Separately selected because error selection and event-read clearing semantics still need physical evidence |
| Optional `SM` | Last because reading status can clear resolved error latches; status updates after measurement, and this batch triggers no new measurement |

These effects follow the [review's manual references](../inventory/COMMAND-BACKEND-REVIEW.md#command-semantics-that-affect-the-proposed-tests) and [A06](../inventory/AMBIGUITIES.md#a06). Fixed fixtures do not model an actual meter's error queue, event clearing, or status timing. Optional reads do not resolve A06.

## Receipt and failure behavior

Each invocation reserves a new output directory and writes `diagnostics.json`. Existing directories are rejected before constructing the fake transport. The receipt records simulation identity, query order and effects, per-query timing/status, raw reply bytes as hex, parsed values, untouched not-attempted rows, errors, cleanup, and the fake transport trace. Empty `raw_hex` means no reply bytes were captured, including failed writes/reads; it is not a fabricated valid reply.

Collection outcomes are `completed`, `query_failed`, `cleanup_failed`, or `interrupted`. `completed` means the selected replies were parsed and cleanup completed, **not** that the instrument passed a health check. Every receipt says `Not evaluated; diagnostic replies only`, and makes no physical front-panel or source-off claim. In particular, a stale or omitted `SM` cannot prove POWER REF is off.

A malformed, failed, or late query stops the sequence. The original bytes remain available even when parsing/deadline checks reject them. No query retry or post-fault probe occurs. Existing `Instrument` uncertainty handling prevents further I/O and suppresses free-run/local cleanup after a query failure; transport close still occurs. An interrupted batch saves partial evidence and re-raises the interruption. Healthy fake cleanup exercises the existing `TR3` then Go To Local sequence. A cleanup failure retains successful query results, records the failure, and still closes once.

The fixed batch has four or seven queries, each with a validated finite operation timeout (default 0.25 seconds; configurable 0.01–5 seconds), plus existing bounded cleanup. The late-reply fixture deliberately returns after its deadline to verify rejection. This fake path does not establish containment of an uncooperative physical backend; a physical bridge needs its own worker/ownership and disposal checks before it can be exposed.

## Reproduce offline

Use the repository's offline launcher, which blocks hardware entry points. For example, save this small script under ignored `tmp/diagnostics/example.py`:

```python
from hp437b.diagnostics import run_simulated

result = run_simulated(
    "tmp/diagnostics/example-run",  # Must not already exist.
    include_latched_reads=True,
)
print(result["status"])
```

Run it with:

```bash
.venv/bin/python tools/offline_qa.py --seconds 180 -- .venv/bin/python tmp/diagnostics/example.py
```

Available fixed scenarios are `healthy`, `instrument_errors`, `source_on` (requires the optional status read), `malformed_reply`, `read_error`, `late_reply`, and `cleanup_error`. The three read-failure scenarios optionally select a `fault_at` query included in the chosen plan; the default fault is at `*SRE?`. This is fixture selection, not a production recovery policy.

## Software evidence

[Thirty-two focused tests](../../tests/test_diagnostics.py) passed through `tools/offline_qa.py`. They exercise default/optional order, raw and parsed receipts, error indications without a health verdict, malformed replies at all seven positions, late replies, transport/write failures, no post-fault queries, cleanup failure, cancellation by interruption, invalid arguments, output preservation, and unchanged closed/uncertain-session guards.

The final focused diagnostics/instrument/transport check passed **83 tests**, including interruption during query collection and during cleanup. The full suite in the existing Python 3.14 reporting environment passed **1,575 tests**, with three opt-in stress cases skipped. An initial run in the minimal sandbox environment had six loopback-bind permission failures and skipped optional reporting cases; the corrected run used the existing reporting dependencies and allowed local HTTP binds while retaining the hardware-blocking offline guard. Lint, formatting, documentation links/IDs/manual checksums, `git diff --check`, and the wheel/source-package build passed. The wheel contains the diagnostics module.

Eight fresh ignored local bundles were also exercised: default and optional healthy collections, error indications, source-on status observation, malformed reply, read failure, late reply, and failed local return. Each produced the expected collection outcome and closed its fake transport. No measurements or raw local artifacts are committed.

## Remaining selected opportunity

The fake batch is complete. The subsequent [physical diagnostics runner](DIAGNOSTICS-PHYSICAL-RUNNER.md) is implemented and tested with injected backends; the subsequent [basic current-meter wspr5 pass](PI-DIAGNOSTICS-BASIC-20261113.md) is complete with separate owner final confirmation. Optional latch-read captures remain untested. The public `run_simulated` entry point remains fake-only. The basic pass covers mask reads, `*STB?`, and numeric display text on the recorded Pi setup. Additional reads with latch effects remain separately selectable, with POWER REF off and no pending trigger/calibration. It must preserve raw framing, establish session ownership and cleanup, and record host-specific results. There is no authorization here to clear registers, inject physical errors, change settings/source state, run zero/CAL, or add automatic diagnostics to normal logging.

`LP2`, reversible settings, and true serial polling remain the review's other optional opportunities. Their status and physical matrix cells are unchanged by this simulated work.
