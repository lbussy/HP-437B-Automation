# Current-meter setup and interaction checks

Current equipment: meter **SN 3125U22346**, sensor **SN MY41094127**, USBGpib V2/recorded adapter firmware V2.4. Laboratory records list meter software 2.0 and HPIB address 13. Records are [reviewed](CALIBRATION-REVIEW.md); physical project setup/interaction checks remain pending.

## Shared setup gates

Prepare the [measurement-policy](MEASUREMENT-POLICY.md) path, source initially off, automatic range/filter, absolute W, REL/offset/duty off, closed competing applications, and available operator recovery. Warm up at least thirty minutes before preparation/accuracy-dependent observations ([operating manual, PDF 16](../../references/manuals/hp-437b/HP-437B-Operating-Manual-00437-90047.pdf#page=16)). Use the source-backed [ZERO](ZERO-AUTOMATION.md) and [CAL](CAL-AUTOMATION.md) procedures only when selected and applicable; no adjustment is automatic.

## Per-host cases and finite budgets

Select cases relevant to actual use, with fresh authorization and setup. No blanket fault campaign is required. Each host has at most twenty-five minutes of active selected-case time, excluding warm-up/operator response; software preflight has a ten-minute ceiling. Stop at the first failed gate, preserving failed/partial artifacts. No automatic retry.

| Case | Required observation | Maximum allowance |
| --- | --- | --- |
| Identity/access | Actual resource, labels, firmware, host/runtime/pins, exclusive ownership, and ordinary-user access | 120 seconds device-access work |
| Source-off baseline | Fresh ID/status, complete serialized acquisition, normal close, independent free-run/numeric display check | 120 seconds; each operation at most 30 seconds |
| Prepared control/display | Matching units/corrections, deliberate reference control, display agreement within a predeclared increment, restored source off | 180 seconds plus 30 seconds cleanup; display hold at most 60 seconds |
| Short log | Three valid rows, interval 1, timeout 10, W, actual serials; CSV/sidecar/raw joins and cleanup | 90 seconds |
| Sustained log | Duration 300, interval 1, timeout 10, W; actual timing/counts, complete evidence, explicit source off | 420 seconds |
| File protection | Existing CSV/sidecar unchanged when output-path reuse is refused before opening | 30 seconds; no device I/O |
| Selected interruption | Source off; between-read cancellation, partial data, bounded close, and fresh verification | 90 seconds plus 120 seconds verification |
| Selected forced timeout | Source off; one declared 0.5-second deadline case, actual abort/disposal evidence, failed data retained | 90 seconds; at most one attempt per host |
| Fresh reconciliation | Only after independently verified completed abort; fresh ID/status/acquisition/free-run and operator final-state observation | 120 seconds plus operator observation |

Discover the actual USB resource; never copy a descriptor from another session. Use original HP commands, not assumed SCPI. New runs require new filenames and actual meter/sensor identity. The generic logger preserves source state, so the supervising procedure must explicitly verify reference off while transactions are known healthy. An uncertain session receives no blind OC0/retry/reopen or ordinary ASCII cleanup.

Healthy closure is TR3 followed by conditional USB488 GTL. Separately confirm live numeric readings, RMT off, and POWER REF off after Python closes. Accepted USB status or process exit alone is insufficient. Failed-read shutdown may allow up to one additional second for backend abort/disposal; a late reply remains failed and discarded.

## Pi access and file retrieval

Move USB hosts only after closing the session and verifying reference off. Recheck actual node/resource, binding, and ordinary-user read/write access on Pi. The supplied plugdev 0660 [udev rule](../../config/udev/70-hp437b-usbgpib.rules) is the scoped access option; do not silently change security, services, firmware, or dependencies. Record actual host versions and verify retrieved CSV/sidecar/trace hashes. Keep credentials and raw local measurements out of Git.

## Final acceptance and report

A selected profile passes only when its declared cases, evidence joins, source/settings restoration, and separate operator observations pass on the actual intended host/setup. Retain failures and limitations; do not infer Mac support from Pi or vice versa. Laboratory calibration, display agreement, software correctness, and RF accuracy remain distinct claims. Update [open work](../OPEN-WORK.md), [validation](../VALIDATION.md), and the [coverage matrix](../inventory/COVERAGE.md) only with current evidence.
