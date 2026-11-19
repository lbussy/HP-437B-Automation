# Event read-clear and error-selection experiment: fake-first preparation

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Fixed experiment and sources

Both literal byte sequences are private fixed fixtures. The normal encoder still rejects `QX` and negative frequencies. The tool has no arbitrary raw-command argument, and no command registry/ambiguity guard is relaxed. No valid frequency, calibration factor, sensor table, saved state, reference output, or enable mask is written. Original diagnostic history may be consumed, and new entry/error event indications are deliberately generated; that is part of the selected experiment.

## Bounded sequence

The maximum is **69 uniquely identified steps: 62 queries and seven deliberate invalid-entry writes**, plus existing identity preflight and healthy cleanup. Repeated queries are intentional observations, never retries after failed communication.

| Phase | Fixed work | Purpose |
| --- | --- | --- |
| Baseline | Read ESE/SRE/STB; ESR three times; ERR three times; SM twice | Preserve prior evidence; require zero enable masks, quiet error replies/status, source off, and normal live mode before any stimulus |
| Event read-clear | QX once; ESR three times; ERR three times; SM twice | Observe a newly induced command-error bit before reading SM; distinguish disappearance, persistence, or inconclusive observations |
| Isolated A | QX once; ERR three times; ESR three times; SM twice | Establish whether ERR exposes code 91 with this query ordering |
| Isolated B | FR-3GZ once; ERR three times; ESR three times; SM twice | Establish whether ERR exposes code 82 before making a paired-error inference |
| A then B | QX, then FR-3GZ; ERR three times; ESR three times; SM twice | Preserve the two-error order and bounded reply sequence |
| B then A | FR-3GZ, then QX; same reads | Distinguish order-dependent hypotheses without assuming FIFO |
| Final | ESE/SRE/STB, three ERR reads, three ESR reads, two SM reads | Record remaining diagnostic state and verify observed enable masks/active status/configuration flags |

The baseline allows an observed Power On bit but stops before fixtures if preexisting error event bits, nonzero masks, nonzero error replies, or active status errors are present. No masks are reset to force the precondition. Each phase's last SM must show reference off, normal mode, not standby, and no active measurement/entry error; observed scale/relative/group-trigger/limit/offset/duty flags must match the baseline. Range/filter snapshots are retained without treating normal automatic changes as setter changes. SM updates may lag measurements; an unchanged error indication after the fixed status pair is a bounded observation stop, not a declaration of an instrument defect or proof that an error can never clear.

If the command-error event is unobservable, or isolated ERR replies do not expose the expected entry codes, the runner stops before further stimuli/pair inference. `observation_stop` is an incomplete experiment with retained data; it is not a successful qualification claim. Healthy communication can still perform TR3/GTL/raw close. If a transaction is malformed, partial, failed, late, or cancelled, no more queries, fixtures, or ASCII cleanup are sent; the existing native-finish/disposal path applies.

## Interpretation and limits

The result records bounded signatures: command bit disappears on subsequent reads, persists across three reads, or is inconclusive; paired ERR sequences may be FIFO-like, LIFO-like, latest-sticky, single-slot-like, or inconclusive. These labels do not create a production queue API or prove general queue capacity, other error classes/event bits, arbitrary timing, or all clearing semantics. Three zeros alone do not prove read-clear behavior. Known repeated-command IDs are distinct so no earlier reply is overwritten by a later read of the same query.

`accepted_full_case` is true only for a fully completed, timely, normally closed case; stopped/failed/cancelled cases keep it false. The original receipt still has no inferred physical identity or front-panel confirmation. New operator observations remain separate evidence. A06 and the Mac/Pi matrix are not promoted by fake results.
