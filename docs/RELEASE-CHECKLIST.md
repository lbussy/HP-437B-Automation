# Current release checklist

Updated: November 19, 2026.

| Area | Current readiness |
| --- | --- |
| Interface/logger and command registry | Implemented; guarded operations remain explicit |
| WF-01–WF-03 reference workflows and suites | Implemented; current-meter physical interaction checks pending |
| Guided transmitter capture | Implemented; actual transmitter/path use pending |
| WF-04–WF-06 / shared DUT controls | Synthetic/fake implementations available; physical experiments selected separately |
| Provenance, reports, profiles, saved-run history, supplied-limit assessments, PDF/ZIP | Implemented; software results do not certify RF accuracy |
| ZERO/CAL interface and bounded diagnostic runners | Implemented; opt-in, supervised, and separate from ordinary logging |
| Current equipment | Meter SN 3125U22346 and sensor SN MY41094127 records indexed; confirm actual setup when used |
| Unattended recovery / general bus support | Not qualified; existing guards remain |
| AI/provider automation | Deferred |

For a software change, run relevant checks using the [software guide](SOFTWARE.md), check Markdown links and `git diff --check`, and verify reference hashes. Before claiming hardware support, retain scoped current-meter/host evidence and separate operator final-state confirmation. Before an accuracy claim, retain applicable sensor/fixture corrections and uncertainty evidence.

No outstanding mandatory POWER REF feature is identified. Current work is in [OPEN-WORK.md](OPEN-WORK.md). Publishing, pushing, and releases require user authorization; never enable immutable releases.
