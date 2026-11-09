# Hardware validation plan

Status: planned; no results recorded. This is an acceptance checklist, not an executable bench procedure. Derive actual commands and zero/calibration steps from the [manuals](EQUIPMENT.md) and the real signal path.

## Record the environment

Record meter and sensor identification, sensor calibration information, adapter model/firmware, host model/architecture/OS, Python and released dependency versions, USB cable, GPIB address, termination settings, and measurement configuration. Distinguish installed releases from unreleased backend changes.

## Required checks

1. Discover and open the adapter through PyVISA-py using the USBTMC path. Record the resource identifier; use documented 437B commands rather than assuming SCPI examples apply.
2. Read power and compare with the front panel using matching units and correction settings. This comparison checks readback, not absolute calibration accuracy.
3. Change a reversible configuration setting, verify the effect, restore it, and confirm return to local control.
4. Exercise the trigger and status operations actually required by the chosen measurement sequence. Record which operations were tested and which remain unsupported or untested.
5. Verify response termination, expected invalid/overrange behavior, bounded timeouts, recovery after a timeout, and clean shutdown.
6. Run sustained CSV logging for an agreed duration and interval. Check timestamps, explicit units, missing/invalid samples, interruption handling, and output completeness. Record measured behavior without claiming a rate from configuration alone.
7. For Pi operation, verify Mac access and file retrieval. Repeat relevant checks on every additional host before claiming support there.

## Backend decision

PyVISA-py remains provisional until required checks pass. An unrelated missing feature need not disqualify it. If a required operation fails, isolate configuration issues from reproducible defects, then decide whether to fix the backend or adopt another transport/backend. R&S VISA is a proprietary fallback requiring a separate adoption decision.

## Results to retain

For each validation run, record date, operator, environment, exact procedure/commands, expected and observed behavior, pass/fail for each required check, and remaining limits. Raw local measurements belong in ignored `data/` or `output/logs/`; deliberately selected, reviewed evidence may be added under `docs/validation/` when available. No passing result is implied by this document.
