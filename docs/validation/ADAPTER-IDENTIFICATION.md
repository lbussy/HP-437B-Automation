# Adapter firmware and hardware identification

This document describes the implemented software path and its current operating limits. Hardware behavior on meter SN 3125U22346 remains unverified; use fresh setup and explicit supervision for selected physical work. Normal logging does not start these diagnostic operations automatically.

## Current inventory

USBGpib V2; USB vendor/product `03eb:2065`; recorded adapter firmware **V2.4**; Anker USB-C cable. Exact PCB revision is unknown and retained as a metadata limitation. Instrument software and GPIB address are separate meter facts. Confirm the actual descriptor/resource and meter address before use; no current-meter compatibility pass is implied by adapter identification.

## Documented procedure

The publisher [README, Firmware version](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#firmware-version) documents USB class/interface pulse-indicator request `a1/40`, followed by the adapter-internal query `!ver?`. The [firmware parser](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/SW/TestAndMeasurement/miniparser.c), `cmd_ver_query`, returns the firmware version through an internal response buffer, without writing EEPROM. The reviewed parser has no hardware-revision query. The [hardware notes](https://github.com/xyphro/UsbGpib/blob/88a13830eea3e2d8bf9f6e33123cc1523f42c70a/README.md#mounting-the-pcb--flashing-the-firmware) state the same firmware supports REV1 and REV2 hardware, so the firmware version cannot identify the PCB revision.

Use one exclusive PyUSB handle selected by exact vendor/product and expected serial descriptor, with the USB488 interface and bulk endpoints checked before sending the query. Require pulse response `01` before the internal command. Send one complete USBTMC DEV_DEP_MSG_OUT containing only `!ver?`, then one REQUEST_DEV_DEP_MSG_IN and consume its complete reply. Check message ID, tag/inverse, length, reserved bytes, and EOM before ASCII decoding. Individual USB calls have ten-second timeouts and the helper has a twenty-five-second outer ceiling. Stop without retry on failure. No other internal commands, EEPROM setters, GPIB program commands, or changes to production code are included. Pulse indication can briefly blink the adapter LED.
