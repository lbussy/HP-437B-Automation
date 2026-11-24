# Open work

Updated: November 24, 2026. ✅ Complete, ⏳ In progress, and ▧ Not started/deferred.

| Item | Current status | Remaining action |
| --- | --- | --- |
| HP-01: Equipment | ⏳ Scoped Mac bench use recorded | Firmware 2.0, resource, owner-supplied meter/sensor identities, ZERO, and one corrected RF capture are recorded in the [bench review](validation/30M-POWER-20261123.md). Front-panel address and broader selected host/interaction checks remain unverified |
| 8482H calibration documents | ✅ Available | [Certificate and chart review](validation/8482H-CALIBRATION-20261122.md), serial-specific factors, and provenance |
| Reference library | ✅ Available | [Manuals and calibration index](../references/README.md), document hashes, manifests, and verified receipt compatibility |
| Guided report presentation | ✅ Updated | Shared template removes the redundant physical-measurement subtitle, uses consistent status capitalization and N/A for absent acceptance criteria, and follows [per-run metadata conventions](workflows/OPERATOR-GUIDED-SWEEPS.md#report-presentation) |
| Human-started POWER REF software | ✅ Implemented | No outstanding mandatory feature work; current-meter hardware use remains separately scoped |
| Automatic 8482A correction | ✅ Implemented | Exact-frequency logging and configured guided points use certificate-derived factors and native receipts. Exercised across all 52 Pico points |
| Transmitter power measurement | ⏳ Conducted Pico direct-GPIO matrix recorded | [52-point bench record](validation/PICO-52-20261123.md) gives sensor-input power and fixture limitations. Additional output profiles remain unverified |
| WF-04–WF-06 physical experiments | ▧ When selected | Actual setting/frequency/voltage experiment; a supply is needed only for the voltage case |
| Automatic frequency × drive sweep and optional PDF | ⏳ Direct GPIO completed 52/52 physical points | [Guided workflow](workflows/OPERATOR-GUIDED-SWEEPS.md#live-control-prerequisites) and [full bench record](validation/PICO-52-20261123.md). Pi and Si5351 live controls remain open |
| Broader/unattended recovery | ▧ Optional/unqualified | No automatic workflow resumption or already-wedged repair claim |
| Broader command/bus support | ▧ Optional | Resolve relevant [ambiguities](inventory/AMBIGUITIES.md) before enabling guarded operations |
| AI/provider automation | ▧ Deferred | Human-started deterministic mode remains selected |

Software-only tests and workflow definitions remain available. Extra test combinations, unsolicited DUT limits, and blanket requalification are not completion requirements. Record new hardware results against the actual current setup; do not infer a pass from software or laboratory evidence alone.
