# TIS-1W conducted Si5351 sweep

Add the **Turn Island Systems TIS-1W** between **Pico C’s Si5351 CLK0** (`wpicoc.local`) and the **Agilent 8482H SN 3318A09219** in a conducted 50 Ω fixture. The HP 437B SN 3125U22346 reads the sensor. The amplifier’s advertised output is approximately 1 W of square-wave power into 50 Ω and varies with frequency. Its input is nominally 1.5 Vpp into 50 Ω with a 5 Vpp limit. [TIS-1W manufacturer guide, pp. 2–3](https://turnislandsystems.com/wp-content/uploads/2025/09/TIS-1W.pdf#page=2)

## Sweep coverage

Use the same carriers and drive order as the [previous Si5351 matrix](SI5351-PHYSICAL-SWEEP-PLAN.md#2-frozen-frequency-and-drive-matrix), excluding **2200 m, 630 m, and 2 m**. The selected **11 bands** fall within the TIS-1W’s specified **1–60 MHz** range. Run them at **2, 4, 6, and 8 mA** Si5351 clock drive, for **44 points** and **88 retained readings** at two per point. [TIS-1W manufacturer specifications](https://turnislandsystems.com/product/tis-1w-digital-1w-power-amplifier/)

Use the 8482H’s carrier-specific CAL FAC at each point. The planned values use linear interpolation in Hz and round half up to the meter’s 0.1% entry increment. [8482H serial-specific calibration chart](../validation/8482H-CALIBRATION-20261122.md#calibration-factors-as-printed)

| Band | Carrier (Hz) | CAL FAC (%) |
| --- | ---: | ---: |
| 160 m | 1838100 | 98.4 |
| 80 m | 3570100 | 99.1 |
| 60 m | 5366200 | 99.2 |
| 40 m | 7040100 | 99.3 |
| 30 m | 10140200 | 99.5 |
| 20 m | 14097100 | 99.4 |
| 17 m | 18106100 | 99.4 |
| 15 m | 21096100 | 99.3 |
| 12 m | 24926100 | 99.3 |
| 10 m | 28126100 | 99.2 |
| 6 m | 50294500 | 99.0 |

## Runner setup

Launch the operator service with `--sweep-setup` and `--pico-si5351-setup` as for the [Pico Si5351 workflow](OPERATOR-GUIDED-SWEEPS.md#pico-si5351). In the sweep setup, use `"fixture_profile": "tis-1w"`, `"sensor_serial": "3318A09219"`, and describe the actual RF path in `fixture`. The service presents **Automatic Pico Si5351 with TIS-1W and 8482H** and reviews all 44 points through the existing `pico-si5351` target. Use `python -m hp437b.guided_client tis-1w-plan` to generate the CLI plan. A CLI Start uses the fresh Review digest and every confirmation in `hp437b.pico_sweep.TIS_1W_PREPARED`.

The runner sends the chart-derived CAL FAC and checks meter status while RF is off, before each tone. It stops on readings above 3 W, requires an RF-off indication within ±50 µW, and marks points with a retained reading at or below 100 µW as limited. The settling comparison allows the larger of 10 µW or 1% of the larger reading’s magnitude. These are software measurement checks. The fixture must keep actual input inside the sensor ratings throughout the test. [Keysight 8482H specifications, Table 14](https://www.keysight.com/fi/en/assets/7018-09107/data-sheets-archived/5965-6382.pdf#page=19)

Hardware-blocked tests exercise all 44 points and 88 readings through the operator API and runner. They check each CAL FAC write, drive restoration, sealed results, and shutdown after a simulated overrange reading. The [physical validation record](../VALIDATION.md#tis-1w-conducted-si5351-sweep) covers all 44 points with the 8482H.

## Bench preparation

- Confirm the actual CLK0-to-amplifier input level and the complete 50 Ω output path, including any filters or attenuation and the measurement plane. Establish an independent way to remove the amplifier’s USB-C power at the bench.
- Choose whether to measure unfiltered average power at the sensor or power after a specified output filter. The TIS-1W’s square wave has harmonics, and the unfiltered thermocouple reading includes their contributions. [TIS-1W manufacturer guide, pp. 3, 5–7](https://turnislandsystems.com/wp-content/uploads/2025/09/TIS-1W.pdf#page=3)
- Confirm the 8482H is connected and verify ZERO and CAL for that setup. The [8482H bench check](../validation/8482H-BENCH-20261124.md) records the preparation and internal-reference indication for the documented setup.
