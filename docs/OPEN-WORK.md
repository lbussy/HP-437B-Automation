# Open work

Updated: November 23, 2026. ✅ Complete, ⏳ In progress, and ▧ Not started/deferred.

| Item | Current status | Remaining action |
| --- | --- | --- |
| HP-01: Equipment | ⏳ Scoped Mac bench use recorded | Firmware 2.0, resource, owner-supplied meter/sensor identities, ZERO, and one corrected RF capture are recorded in the [bench review](validation/30M-POWER-20261123.md). Front-panel address and broader selected host/interaction checks remain unverified |
| Human-started POWER REF software | ✅ Implemented | No outstanding mandatory feature work; current-meter hardware use remains separately scoped |
| Automatic 8482A correction | ✅ Implemented | Exact-frequency logging and configured guided points; certificate-derived factors and native receipts. One physical 30 m point exercised |
| Transmitter power measurement | ⏳ One physical point recorded | [30 m GP2 test](validation/30M-POWER-20261123.md): 24.500 mW indicated at sensor input; harmonics/uncertainty limits recorded. Broader guided physical sweeps remain untested |
| WF-04–WF-06 physical experiments | ▧ When selected | Actual setting/frequency/voltage experiment; a supply is needed only for the voltage case |
| Automatic frequency × drive sweep and optional PDF | ⏳ Offline matrix and report implemented | [Guided workflow](workflows/OPERATOR-GUIDED-SWEEPS.md#automatic-simulation) and [implementation plan](workflows/AUTOMATIC-FREQUENCY-DRIVE-PLAN.md). Live Pico/Pi bridges, equipment timing and shutdown verification, and the conducted 52-point Pico campaign remain open |
| Broader/unattended recovery | ▧ Optional/unqualified | No automatic workflow resumption or already-wedged repair claim |
| Broader command/bus support | ▧ Optional | Resolve relevant [ambiguities](inventory/AMBIGUITIES.md) before enabling guarded operations |
| AI/provider automation | ▧ Deferred | Human-started deterministic mode remains selected |

Software-only tests and workflow definitions remain available. Extra test combinations, unsolicited DUT limits, and blanket requalification are not completion requirements. Record new hardware results against the actual current setup; do not infer a pass from software or laboratory evidence alone.
