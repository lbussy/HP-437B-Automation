# Adapter firmware and hardware identification

Status: ✅ Current-setup adapter identification/readiness complete: model, firmware, cable, and meter GPIB address recorded; exact PCB revision retained as an accepted metadata limitation. November 11, 2026. The owner requested reading both over USB, with the adapter already connected to the Mac after the completed timeout verification. Meter power, GPIB, sensor/RF path, and POWER REF-off setup were retained. No new measurement, fault injection, firmware update, reset, or persistent configuration change was included.

## Documented procedure

The publisher [README, Firmware version](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#firmware-version) documents USB class/interface pulse-indicator request `a1/40`, followed by the adapter-internal query `!ver?`. The [firmware parser](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/miniparser.c), `cmd_ver_query`, returns the firmware version through an internal response buffer, without writing EEPROM. The reviewed parser has no hardware-revision query. The [hardware notes](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#mounting-the-pcb--flashing-the-firmware) state the same firmware supports REV1 and REV2 hardware, so the firmware version cannot identify the PCB revision.

Use one exclusive PyUSB handle selected by exact vendor/product and expected serial descriptor, with the USB488 interface and bulk endpoints checked before sending the query. Require pulse response `01` before the internal command. Send one complete USBTMC DEV_DEP_MSG_OUT containing only `!ver?`, then one REQUEST_DEV_DEP_MSG_IN and consume its complete reply. Check message ID, tag/inverse, length, reserved bytes, and EOM before ASCII decoding. Individual USB calls have ten-second timeouts and the helper has a twenty-five-second outer ceiling. Stop without retry on failure. No other internal commands, EEPROM setters, GPIB program commands, or changes to production code are included. Pulse indication can briefly blink the adapter LED.

## Physical capture

The direct query completed successfully at 18:53:54 CST (November 12, 00:53:54 UTC). The adapter replied with exactly four bytes, `56322e34`, decoded as **`V2.4`**. The control request returned `01`; the complete USBTMC response was `0202fd00040000000100000056322e34` (tag 2, length 4, EOM). Interface ownership was released and the handle disposed. Core capture time was 0.001687 seconds; no timeout, retry, reset, or instrument program command occurred.

| Field | Observed value | Interpretation |
| --- | --- | --- |
| Owner-reported marking | `V2` | Owner reported this marking after exterior-identification guidance; recorded as model designation, without assuming an exact PCB revision |
| Adapter firmware reply | `V2.4` | Adapter-reported firmware version; not a firmware-image hash or proof of a specific source commit |
| USB vendor/product | `03eb:2065` | Identified XyphroLabs adapter profile |
| Manufacturer/product strings | `XyphroLabs` / `GpibUsb` | USB descriptor strings |
| USB serial descriptor | `HEWLETT-PACKARD_437B_1.8` | Connected instrument identification; 1.8 is the meter firmware |
| `bcdDevice` | `0x0001` | USB device release value 0.01; not the reported V2.4 firmware or an established hardware revision |
| `bcdUSB` | `0x0110` | USB specification descriptor value, not a hardware revision |
| Interface | 0, class `fe`, subclass 3, protocol 1 | USB488 interface profile |
| Cable | Anker USB-C | Owner-reported cable brand/type |
| Meter GPIB primary address | 13 | Owner read the current meter's SPECIAL → HP-IB ADRS display; not inferred from the factory default or read over USB |
| Physical hardware revision | Unmarked/unverified | Owner reports no revision marking and elected to stop pursuing it; accepted metadata limitation, not a Phase 3 blocker |

The publisher [descriptor source](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/Descriptors.c) defines the release number as `VERSION_BCD(0,0,1)`, independently of the firmware query. Do not promote the USB release value, firmware version, model family, or inferred connector style into a verified PCB revision.

Ignored raw evidence: `output/logs/adapter-identification-20261111/usb-identification.json`, SHA-256 `ed2bdf9fe12c35f4d47362cc22060d744103601e9edff0042f5826d24c978e88`. Source review and exact query/reply framing support this firmware-version claim; they do not expand the named recovery or bus-capability acceptance. The owner subsequently closed further PCB-revision investigation as an accepted metadata limitation under HP-02. No production code or logging behavior changed.

The owner subsequently reported the marking `V2`. Record the adapter model designation as USBGpib V2, owner-reported. The exact PCB revision remains unverified; the reported `V2` model marking and confirmed `V2.4` firmware are recorded separately.

## Owner scope correction and address lookup

The owner reports no hardware-revision marking, elected to stop pursuing PCB revision, and identified the cable as Anker USB-C. Retain exact PCB revision as unknown; it is not a Phase 3 acceptance blocker. Model USBGpib V2, reported firmware V2.4, USB identity, and qualified host behavior remain recorded separately.

The reviewed V2.4 parser supports `!addr <primary> [secondary]` as a target setter, with no documented `!addr?` readback. The meter [command inventory boundary](../inventory/COMMANDS.md#physical-and-service-boundaries), derived from operating manual printed 3-98–99/PDF 128–129, identifies its HP-IB address as a local setting. No guessed address query, target change, or scan was sent. A front-panel readout was requested through SPECIAL → `4 HP-IB ADRS` → ENTER, followed by ENTER without editing to retain the existing address. The owner subsequently reported the displayed address as **13**. Record it as front-panel evidence for the current meter, not a USB readback or an assumption from the factory default. Python remained closed during the menu operation. Recheck the replacement meter's address when it arrives.

HP-02 is complete for the current adapter and tested supervised Mac/Pi profile: model USBGpib V2, firmware V2.4, Anker USB-C cable, front-panel meter address 13, and the previously recorded control/logging/shutdown evidence. The unmarked PCB revision is an accepted unknown. Replacement-meter compatibility remains PHASE-03/HP-01; this closure does not accept unrelated bus capabilities, already-wedged repair, or unattended operation.
