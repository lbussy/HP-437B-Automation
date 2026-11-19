# Current measurement policy

The selected initial profile is supervised internal-reference/readback logging, using the actual current meter/sensor and USBGpib V2 setup. See [equipment](../EQUIPMENT.md).

| Setting | Profile |
| --- | --- |
| Path | Sensor cable to SENSOR; sensor RF input directly to POWER REF; no external source or attenuation |
| Reference | Nominal 50 MHz/1 mW; initially off; activate only in the selected prepared case |
| Units | Explicit W, absolute measurement, REL/offset/duty off |
| Acquisition | Automatic range/filter; record actual resolution, factors, and settings |
| Timing | Requested interval 1 second; report achieved spacing, gaps, and overruns |
| Short/sustained logging | Three rows / finite 300-second acquisition-start window |
| Timeout | Ten-second normal operation timeout; diagnostic cases declare their own bounds |
| Corrections | Verify the actual sensor's 99% reference factor for CAL; record active measurement CAL FAC separately |
| Files | New CSV/sidecar/output paths, actual identities, raw replies, and preserved partial failures |

These are explicit profile options, not changes to logger defaults. A display/readback comparison does not establish absolute RF accuracy. Internal-reference drift cannot isolate source, sensor, and meter effects.

ZERO and CAL are separate explicit actions; they are not automatic workflow preflight. Follow the [ZERO](ZERO-AUTOMATION.md), [CAL](CAL-AUTOMATION.md), and [interface](../workflows/METER-PREPARATION.md) contracts with fresh supervision. Sensor input must be source-free for ZERO; CAL requires its direct reference path, prior applicable zero, warm-up, and actual sensor factor.

External transmitters require documented ratings, load/attenuation path, frequency-dependent losses/corrections, source shutdown, and applicable uncertainty. No new threshold or overload test is implied. Unattended operation, persistent table edits, binary restoration, and general bus recovery remain outside this profile.
