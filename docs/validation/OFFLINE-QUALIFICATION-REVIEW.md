# Offline qualification: three adversarial assessments

Exactly three self-assessments of the delivered work, not independent reviewers. Hardware remains excluded. The [plan](OFFLINE-QUALIFICATION-PLAN.md), [coverage ledger](OFFLINE-PARAMETER-COVERAGE.md), and [results](OFFLINE-QUALIFICATION-RESULTS.md) define the evidence boundary.

## Assessment 1: isolation, limits, and delivery

Found and corrected: the first guard did not explicitly interdict existing-device bulk/control methods; these are now blocked alongside construction, discovery, backend loading, VISA, optional serial construction, and native-library loading. Eleven sentinel denial paths run in parent, exec, and spawn contexts. Startup failure exits rather than continuing after a sitecustomize exception. Python/C runtime support initializes before native-load interdiction; no USB device library is loaded. Arbitrary native code, inherited handles, isolation flags, and deliberately escaped process groups are outside this inspected-path guard, and none are exercised.

The first manifest omitted maintained QA tools from source distributions; `MANIFEST.in` now includes them. The final-reserve restriction originally existed only in prose; the supervisor now mechanically refuses campaign launches in the last thirty minutes, with explicit final-verification override. It rejects non-finite global deadlines. Regression tests cover actual command expiry, expired global time, the reserve, and final verification. Limits bound commands/campaigns; Python protection is not presented as an OS security boundary.

One sandboxed run passed all 346 tests but failed the launcher's process-group cleanup with `PermissionError`; the launcher did not hide this. Scoped local software execution with owned-group cleanup available passed afterward. No driver, service, security policy, network identity, or device privilege was changed. Local-only delivery is explicit; no push, PR, or bench installation.

## Assessment 2: independent oracles, coverage, and packaging

The ledger's broad no-argument wording initially relied on one common encoder path. Added individual extra-value rejection cases for all 46 no-argument literals, every confirmation gate, and DU lengths/invalid characters/types. Corrected a test comment's filter reference to printed 3-63. Numeric boundaries and finite domains are taken from the cited inventory/manual entries, not encoder constants. Generated valid measurements use an independently constructed documented grammar and Decimal values; only non-ASCII, missing terminator, and oversize mutations are asserted invalid. This avoids the false claim that any mutation must fail.

Storage tests assert the actual durable-state limit: final replacement failure leaves the prior running sidecar and raises, while resources close. A flush failure can leave a physical CSV row whose completed-flush counter has not advanced; no successful metadata or power-loss guarantee is claimed. No production change is justified by those expected failure semantics.

Artifact inspection found that setuptools' automatic license selection omitted `THIRD_PARTY_NOTICES.md` from both archives. Added explicit project license-file metadata for LICENSE and the existing notices; this changes packaging only, not dependencies or device behavior.

The strict native-load guard also rejected pip's macOS trust-store framework import during the first offline installation attempt. Kept the guard intact and used pip's command-local legacy certificate implementation for `--no-index` installation; no network or host trust configuration changed.

Wheel and source-distribution checks verify isolated installations outside source, parent/spawn origins, inherited guards, package content, exact pins, license/notices, and software tests. Full test/campaign results are recorded separately from artifact contents/hashes. Original publisher artifacts and physical coverage records remain unchanged. Additional interpreter/Pi checks are optional and not claimed as new passes.

## Assessment 3: final scope, provenance, and remaining uncertainty

Final review found an unbounded final `wait()` in supervisor disposal and a runtime-support import outside startup's fail-closed exception handler. Bounded the last wait, moved that initialization into the handler, cleared inherited active flags before initialization, and added a failed-import child regression proving application code never starts. Existing supervisor timeout regression still enforces bounded completion.

Final review checks the complete diff, maintained tools, default versus opt-in cases, source/artifact installations, Markdown links/anchors, inventory totals, reference checksums, and main-checkout/package-origin preservation. All runtime source files, pins, CLI/defaults, CSV/sidecar schema, transaction scheduling, and one-second failed-read shutdown remain byte-identical to the starting commit. Changes are tests, QA tooling/CI invocation, packaging of that tooling, and documentation only.

Residual limitations: Python accident guards do not contain malicious/native bypasses; the 512 MiB worker ceiling is not enforced on this Mac, so bounded inputs/rows/processes are used instead. SM fields are varied independently, not as all state combinations. Identification retains existing fixtures, and opaque snapshot bytes are not decoded. Decimal spaces, invalid-type cross-products, all message strings, service/status lifecycles, hardware timing, guarded capabilities, already-wedged recovery, unattended operation, and replacement acceptance are not fully qualified. Those limits remain explicit, not silently promoted to passes. Remote CI is not run for this local-only branch. No runtime fix or normal-logging change resulted.
