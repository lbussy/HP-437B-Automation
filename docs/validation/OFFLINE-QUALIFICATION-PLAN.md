# Offline software qualification plan

Executed November 11, 2026, from baseline `9d84059cb7778cbd87f505159df52521003dca8a`, on an isolated local task branch. The [execution prompt](../prompts/offline-qualification.md) defines authorization. No physical interfaces, discovery, bench installations, or remote delivery are authorized.

Four-hour global ceiling, with the final thirty minutes reserved for verification/delivery; guarded preparation capped at twenty minutes. Each command runs through `tools/offline_qa.py` with a 180-second supervised process-group ceiling. Larger optional campaigns use declared limits below. Fixed seed 4378482. Maximum two workers, artifact ceiling 1 GiB, minimum free space 2 GiB. Per-worker memory limits are not portable on this Mac; use bounded input/row counts instead, and do not claim an enforced 512 MiB ceiling. No campaign launches in the final reserve.

| Case | Priority | Oracle and scope | Hard bound |
| --- | --- | --- | --- |
| OQ-01 | Mandatory | Startup canaries, parent/exec/spawn, sentinel denial before application imports | 180 seconds |
| OQ-02 | Mandatory | Unchanged baseline: existing independent byte fixtures, lint, format, build | 180 seconds per command |
| OQ-03 | Mandatory | Every C/G ID linked to inventory sources, finite masks/enums, literal bounds, pre-I/O guards | 180 seconds per batch |
| OQ-04 | Mandatory | Literal valid/invalid parser examples; fixed-seed bounded mutations classified by grammar | 10,000 inputs, 65,537 bytes/input, 180 seconds |
| OQ-05 | Mandatory | Production collect with explicit synthetic transport; CSV/metadata, scheduling, injected storage faults | 5,000 rows, 180 seconds |
| OQ-06 | Mandatory | Real IPC/fake backend deadline paths, late replies, disposal, no replay | 30 trials, 180 seconds |
| OQ-07 | Mandatory | Wheel/sdist content and clean installation outside source; origin and inherited canaries | 180 seconds per command |
| OQ-08 | Optional | Extra installed interpreters, Pi software-only workspace, expanded guarded research | Only after core; skip if access/isolation unavailable |
| OQ-09 | Mandatory | Exactly three adversarial reviews, final checks, reference checksums, local commit | Final reserve |

Stop on guard failure; inspect and fix isolation before broader tests. Expected malformed replies/faults are negative-test passes only when the asserted contract holds. Unspecified protocol grammar is not a rejection oracle. Genuine failures receive minimized regressions and at most two diagnostic timing reproductions. No retries to manufacture a green run. Preserve raw diagnostics in ignored task scratch; commit sanitized fixtures only. All physical and replacement acceptance gates remain unchanged.
