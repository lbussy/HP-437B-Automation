# HP 437B sensor compatibility by application family

Updated: 2026-11-12.

This table records manufacturer-documented compatibility for 19 standard legacy 8480-series sensor models, grouped by practical application. Application labels describe useful coverage, not exclusive uses. Compatibility is a documentation finding, not local bench qualification of these sensors.

Power ranges below are specified measurement ranges, not overload or damage limits. Use the individual sensor's calibration factors and the applicable manual for operating limits and procedures.

| Family | Application group | Frequency coverage | Confirmed compatible sensors and measurement ranges |
| --- | --- | --- | --- |
| **8482** | **Amateur radio / broadband LF, HF, VHF, and UHF** — 2200 m through 70 cm | **100 kHz–4.2 GHz** | **8482A:** 1 µW–100 mW; **8482H:** 100 µW–3 W; **8482B:** 1 mW–25 W |
| **8481** | **General RF and microwave testing** — communications, radar, components, and laboratory sources | **10 MHz–18 GHz** | **8481D:** 100 pW–10 µW; **8481A:** 1 µW–100 mW; **8481H:** 100 µW–3 W; **8481B:** 1 mW–25 W |
| **8483** | **75 Ω RF systems** — cable television, broadband distribution, and other 75 Ω equipment | **100 kHz–2 GHz** | **8483A:** 1 µW–100 mW |
| **8484** | **Low-level RF and microwave measurements** — older high-sensitivity family | **10 MHz–18 GHz** | **8484A:** 100 pW–10 µW |
| **8485** | **Extended microwave testing through K band** — microwave links, radar, and components | **50 MHz–26.5 GHz**; option **033** extends to **33 GHz** | **8485D:** 100 pW–10 µW; **8485A:** 1 µW–100 mW; both support option **033** |
| **8487** | **Broadband coaxial microwave testing through 50 GHz** — communications, radar, and component characterization | **50 MHz–50 GHz** | **8487D:** 100 pW–10 µW; **8487A:** 1 µW–100 mW |
| **R8486** | **Ka-band waveguide systems** — radar, satellite, and microwave links | **26.5–40 GHz** | **R8486D:** 100 pW–10 µW; **R8486A:** 1 µW–100 mW |
| **Q8486** | **Q-band waveguide systems** — millimeter-wave communications, radar, and research | **33–50 GHz** | **Q8486D:** 100 pW–10 µW; **Q8486A:** 1 µW–100 mW |
| **V8486** | **V-band waveguide systems** — including 60 GHz communications | **50–75 GHz** | **V8486A, standard version:** 1 µW–100 mW |
| **W8486** | **W-band waveguide systems** — millimeter-wave radar, imaging, and research | **75–110 GHz** | **W8486A:** 1 µW–100 mW |

## Scope and exclusions

- Coaxial sensors above are 50 Ω except the 75 Ω 8483A. The 8486 families use waveguide measurement inputs.
- The B models require their supplied, matched attenuator to obtain specified accuracy.
- V8486A-H02 is explicitly incompatible with the 437B; only the standard V8486A is included.
- E8486A variants are excluded because the reviewed manufacturer records do not establish consistent, option-specific 437B compatibility.
- The newer N8480 series, including CFT versions, is incompatible with the 437B.

This is a reference for the listed standard legacy models and the stated 033 extensions, not an exhaustive compatibility claim for every special-order variant or other manufacturer's sensor. The project's present sensor is the 8482A; see [equipment and individual calibration records](EQUIPMENT.md).

## Sources

- [HP 437B Operating Manual, 00437-90047](../output/pdf/hp-437b-8482a/HP-437B-Operating-Manual-00437-90047.pdf), Table 1-3 (printed page 1-10), and Table 3-1 (printed page 3-3): named sensors, meter characteristics, and legacy power/frequency ranges.
- [8480 Series Operating and Service Manual, 08481-90173](../output/pdf/hp-437b-8482a/HP-8482A-8480-Series-Operating-Service-Manual-08481-90173.pdf), printed page 15: coaxial sensor compatibility with the 437B and A/H/B/D measurement ranges; printed page 17: matched B-model attenuator; printed page 18: 8485A/D option 033.
- [Keysight sensor data sheet, 5990-4019](https://www.keysight.com/content/dam/keysight/en/doc/ungate/data-sheets/5990-4019.pdf), Table 26: high-sensitivity and waveguide sensor frequency/power specifications.
- [Keysight V8486A product specifications](https://www.keysight.com/au/en/product/V8486A/waveguide-power-sensor-50-75-ghz.html): standard model range and 43x compatibility, with explicit H02 exclusion.
- [Keysight thermocouple sensor compatibility notice](https://www.keysight.com/us/en/products/rf-power-meters/power-sensors/thermocouple-power-sensors.html): N8480-series exclusion for 43x meters, including CFT options.
