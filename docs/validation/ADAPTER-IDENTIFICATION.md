# Adapter firmware and hardware identification

Status: ✅ Adapter-reported firmware captured; ▧ Physical hardware revision unverified. November 11, 2026. The owner requested reading both over USB, with the adapter already connected to the Mac after the completed timeout verification. Meter power, GPIB, sensor/RF path, and POWER REF-off setup were retained. No new measurement, fault injection, firmware update, reset, or persistent configuration change was included.

## Documented procedure

The publisher [README, Firmware version](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#firmware-version) documents USB class/interface pulse-indicator request `a1/40`, followed by the adapter-internal query `!ver?`. The [firmware parser](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/miniparser.c), `cmd_ver_query`, returns the firmware version through an internal response buffer, without writing EEPROM. The reviewed parser has no hardware-revision query. The [hardware notes](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#mounting-the-pcb--flashing-the-firmware) state the same firmware supports REV1 and REV2 hardware, so the firmware version cannot identify the PCB revision.

Use one exclusive PyUSB handle selected by exact vendor/product and expected serial descriptor, with the USB488 interface and bulk endpoints checked before sending the query. Require pulse response `01` before the internal command. Send one complete USBTMC DEV_DEP_MSG_OUT containing only `!ver?`, then one REQUEST_DEV_DEP_MSG_IN and consume its complete reply. Check message ID, tag/inverse, length, reserved bytes, and EOM before ASCII decoding. Individual USB calls have ten-second timeouts and the helper has a twenty-five-second outer ceiling. Stop without retry on failure. No other internal commands, EEPROM setters, GPIB program commands, or changes to production code are included. Pulse indication can briefly blink the adapter LED.

## Physical capture

The direct query completed successfully at 18:53:54 CST (November 12, 00:53:54 UTC). The adapter replied with exactly four bytes, `56322e34`, decoded as **`V2.4`**. The control request returned `01`; the complete USBTMC response was `0202fd00040000000100000056322e34` (tag 2, length 4, EOM). Interface ownership was released and the handle disposed. Core capture time was 0.001687 seconds; no timeout, retry, reset, or instrument program command occurred.

| Field | Observed value | Interpretation |
| --- | --- | --- |
| Adapter firmware reply | `V2.4` | Adapter-reported firmware version; not a firmware-image hash or proof of a specific source commit |
| USB vendor/product | `03eb:2065` | Identified XyphroLabs adapter profile |
| Manufacturer/product strings | `XyphroLabs` / `GpibUsb` | USB descriptor strings |
| USB serial descriptor | `HEWLETT-PACKARD_437B_1.8` | Connected instrument identification; 1.8 is the meter firmware |
| `bcdDevice` | `0x0001` | USB device release value 0.01; not the reported V2.4 firmware or an established hardware revision |
| `bcdUSB` | `0x0110` | USB specification descriptor value, not a hardware revision |
| Interface | 0, class `fe`, subclass 3, protocol 1 | USB488 interface profile |
| Physical hardware revision | Unverified | No revision-specific field in the documented queries/descriptors; obtain a label/PCB marking or manufacturer confirmation |

The publisher [descriptor source](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/Descriptors.c) defines the release number as `VERSION_BCD(0,0,1)`, independently of the firmware query. Do not promote the USB release value, firmware version, model family, or inferred connector style into a verified PCB revision.

Ignored raw evidence: `output/logs/adapter-identification-20261111/usb-identification.json`, SHA-256 `ed2bdf9fe12c35f4d47362cc22060d744103601e9edff0042f5826d24c978e88`. Source review and exact query/reply framing support this firmware-version claim; they do not expand the named recovery or bus-capability acceptance. Hardware revision remains open under HP-02. No production code or logging behavior changed.
