# Combined POWER REF suite cancellation/recovery — November 13, 2026

Status: the selected current-Mac cancellation capture, protocol cleanup, and report audit passed. The owner confirmed the post-cancellation front panel; the fresh WF-01-only recovery capture and audit passed. The owner also confirmed the recovery final front panel. Normal logging, CLI, transport, physical runner source, and dependencies are unchanged.

## Supervised case

The owner confirmed the same Mac, meter SN 3125U33223, sensor SN MY41094127, direct POWER REF path, warmed-up setup, other control applications closed, POWER REF initially off, and availability for front-panel recovery. The assistant selected all three workflows in the local interface and started once. Cancellation was requested through the page during WF-01 stage S40, its five-minute plateau. The intended short reference-on capture had already finished before the request; this actual case therefore tests cancellation during the sustained plateau. No stage timing or normal behavior was changed, and no cable disconnect, forced timeout, reboot, or automatic retry was used.

The cancellation marker was recorded at 18:00:04.867647 UTC. The runner completed S40, observed cancellation before the next normal stage, and used its existing healthy cleanup. OC0 was sent at 18:04:47.643199 UTC; the parent capture closed at 18:04:56.740063 UTC. This is cooperative stage-boundary cancellation, not immediate RF off.

## Recorded outcome

- Suite execution: **interrupted**, with the original three-workflow denominator and **0/3 complete**.
- WF-01: interrupted after completed S40; **305 valid rows**, including 299 plateau readings, three signed pre-RF baseline readings, and three short reference-on readings.
- Pre-RF zero: **−0.020 µW**; plateau mean: **0.989518394649 mW**. No baseline subtraction or acceptance verdict.
- Native healthy cleanup: **reference off verified** and **USB488 GTL accepted**. The interrupted route skips the normal S60/post-baseline and independent final free-run stage, so `safe_to_advance` remains false. Protocol return to local did not substitute for the later, separately recorded owner display observation.
- WF-02 and WF-03: **not started**, with no operational child directories.
- Exact trace: one OC1 and one OC0; no automatic measurement retry or resume.
- Page: **Suite cancelled**, WF-01 **Interrupted**, later workflows **Not run**, and final attestation required before another Start.

The offline audit validated sealed native/parent evidence, every CSV sequence/status/unit/raw-frame value, source commands, stopped progression, report binding, and physical-mode portable ZIP. All sixty source files stayed byte-for-byte unchanged. The actual one-page PDF was rendered and visually checked. No equipment session was opened by this audit.

## Provenance and retained artifacts

Suite `209b45be-2027-4110-b4e6-14558ce80695`; job `c62140e999b748c0a9249ea84758e007`; native WF-01 `a1ac8e87-179c-47b3-a893-655acdf15da7`. Capture ran 2026-11-13T17:58:37.452092+00:00 → 2026-11-13T18:04:56.740063+00:00 using clean commit `647a74be9e6ee2f7e4d1ea11279b571bd4def351`. Raw local evidence is ignored under `output/reports/reference-suite-bench/c62140e999b748c0a9249ea84758e007/`; audit/screenshot scratch is ignored under `tmp/ref-suite-cancel/`.

| Artifact | SHA-256 |
| --- | --- |
| capture | `2042175c4cd2d378c4378de8f945c21a452bf011fdd829ddf8e264c1bf3f960b` |
| report | `ce893c1c84612fcb514ce1738d927d1221d471bd0ea2e7aaf1794e14dfe977b9` |
| pdf | `3455ba8a1ca7505387d9171cdab4cd8d6ffac386b53bd0139492f32859e853dc` |
| zip | `57f9a5ddcd34ac1fed5dcf3546a9947c42380013eae06d85b22e50f0d849b0ee` |

## Post-cancellation confirmation and fresh run

The owner confirmed live updating readings, RMT off, POWER REF off, and continued availability. The separate UI attestation was recorded at `2026-11-13T18:42:43.520975+00:00` and matches the interrupted capture inventory. Only after recording it, the assistant deselected WF-02/WF-03, renewed setup attestations for the unchanged configuration, and clicked Start for a fresh WF-01-only suite. No manual LOCAL, cable recovery, power cycle, reset, automatic retry, or change to logger/runner behavior was used.

Recovery job `4a0033eea2e64fafb36ca6bf36665c43`; suite `0d937ec3-4d28-4d7e-92b1-644d4419f9b5`; native WF-01 `a59c7960-3791-4b21-9161-1ab2daea26bb`. Capture ran `2026-11-13T18:42:53.669443+00:00` → `2026-11-13T18:49:50.810060+00:00` (417.141 seconds). Acquisition identified commit `647a74be9e6ee2f7e4d1ea11279b571bd4def351` with a modified working tree due to the cancellation bench documentation/checklist changes; runtime source remained unchanged.

| Recovery result | Observed value |
| --- | --- |
| Execution | Completed, 1/1 selected workflow |
| Samples | 308 valid total, including 299 plateau; no failed samples |
| Signed pre-RF zero | −0.00333333333 µW |
| Plateau mean | 0.989 mW |
| Post-RF baseline | −0.010 µW |
| Native stages | S00–S70 all completed |
| Cleanup | Reference off, accepted USB488 GTL, independent free-run/numeric-display check passed |
| Progression gate | `safe_to_advance=true` |
| Source commands | One OC1 and one OC0; no cancellation marker in the new job |

The fresh-run audit revalidated all raw-frame/CSV sequences and values, native/parent joins, report identity, and physical-mode ZIP. All sixty-two source files stayed unchanged. The actual one-page PDF was rendered and visually checked. The interrupted suite retained its original identity and outcome; the fresh run did not resume or relabel it. No measurement acceptance limits were supplied; acceptance remains NOT EVALUATED.

After closure, the owner confirmed live updating readings, RMT off, and POWER REF off without pressing keys. The assistant recorded the separate recovery UI attestation at `2026-11-13T18:51:24.884441+00:00`; its capture hash matches the sealed recovery parent.

| Recovery artifact | SHA-256 |
| --- | --- |
| capture | `aa3dd2a342bce83f60691f017a825c5d84d6278aa0d7eef88fab38793f2a55a6` |
| report | `0ac877bc5fbdd56d3f1f7ded7d89330f0d0beb48129621bbdba9e0b4ba3ef6fe` |
| pdf | `7f412efc0a6d51db7349eebf800c8b3f25ef523787d815c68dcf763009c9e482` |
| zip | `b753797099f4b850c7b625839659c5383dfe564fd33a61989d4816d4b64bb794` |
| Cancellation owner confirmation | `ea29d0d6cb3be9a7556afa5d0239ff42f95065277dade52915d796a7d9cc8e2b` |
| Recovery owner confirmation | `1a0fe42d75d3e077098c9f8b5c4aa4102269e2ddd87a76b2a69887d742ea0217` |

This evidence covers cancellation requested during WF-01 S40 in an all-three selected suite, healthy source-off/local cleanup, stopped later workflows, retained interrupted reporting, and a fresh WF-01-only operator-started run. Both final front-panel observations passed. WF-02/WF-03-specific physical cancellation, forced faults, Pi-suite operation, and unattended recovery remain separate scopes. No further run was started.
