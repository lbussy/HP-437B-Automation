# Controlled entry-error serial-poll experiment

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Manual findings and selected condition

The generic serial-poll description says SPD/unaddressing can clear the sent status byte, while later conditions can be buffered. Appendix A separately describes entry-error latching until the cause is removed and SM is read, including with no SRQ. These descriptions do not establish one unique post-poll entry-bit pattern on this firmware. The experiment must record that pattern, not assume immediate clearing or silently clear it with CS/*CLS.

Select **one fixed invalid numeric entry**, `FR-3GZ`, with event-enable and service-request masks both zero. This avoids changing either mask and avoids selecting the earlier QX-only event as a numeric entry-error substitute. There is no valid FREQ/CAL setter, reference switch, zero/calibration, table/persistent operation, deliberate timeout, or arbitrary raw-command API. Preserve fresh owner FREQ/CAL FAC observations because neither SM nor accepted writes independently verify those numeric settings.

## Fixed profile and order

[The fixed collector](../../src/hp437b/diagnostics_poll_entry.py) has **21 unique rows**:

| Phase | Operation and boundary |
| --- | --- |
| Baseline | SM must be source-off/free-run/no-error; ESE? and SRE? must be zero. Two ESR reads permit only initial 0/Power On 128 then 0; STB? must be zero. Unexpected preexisting evidence stops before the fixture and is retained, not discarded by retry |
| Stimulus | Exactly one private `FR-3GZ` write. A partial/failed write may still have taken effect; do not resend |
| Before poll | Two `*STB?` reads must both report isolated bit 4. A missing/changed/unexpected bit stops before polling, rather than claiming the condition was generated |
| Native poll | One existing tag-2 USB488 control/interrupt probe. A validated zero is recorded as inconclusive; it is not a nonzero success. No second poll or interrupt drain |
| After poll | Two ASCII `*STB?` values, before SM or ESR reads, record whether bit 4 disappears, persists, or changes between observations. Unexpected unrelated bits make the case inconclusive |
| Read cleanup | Two SM reads allow first entry 82 or 0, then require quiet state; two ESR reads expect execution 16 then 0; STB? must be zero, ESE?/SRE? still zero. No CS/*CLS or mask/numeric restoration writes |
| Followup | One consumed TR1/read and final source-off/error-free SM with original interpretation flags; standby after TR1 is allowed |
| Healthy closure | Existing TR3, accepted GTL, raw close, then separate owner final-state/numeric-setting comparison |

If the before-poll gate fails after the fixture, remaining main rows are skipped and only the fixed read-cleanup/followup path is attempted, provided communication is healthy. Baseline failure never injects the fixture. A valid zero poll or unexpected post-poll observation is retained and marks the case inconclusive while bounded read cleanup can still verify a quiet final state. An unquiet cleanup status, changed interpretation flags, persistent events/status, or complete measurement error stops its remaining followup. Native/framing/partial/cancelled/deadline failures stop **all** later commands, including read cleanup and TR3/GTL; only raw close/disposal remains permitted. No automatic recovery/reconnect/retry is introduced.
