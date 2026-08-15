# MWV1 ZMK firmware

MWV1 is a wireless split keyboard made from two copies of the same reversible PCB. Both halves use a nice!nano v2. The left half is the ZMK central and connects to the host over Bluetooth or USB; the right half is a BLE peripheral.

The configuration follows the current ZMK `main` branch and builds against the current Zephyr board target `nice_nano//zmk`. ZMK Studio is enabled on the left/central firmware.

## Hardware analysis

The source project was read from `V1.kicad_sch`, `V1.kicad_pcb`, and `V1.kicad_pro`. No hardware files were modified.

The schematic contains exactly 38 `Keyswitch` symbols (`S1` through `S38`) and one `RP2040_Pro_Micro` symbol (`U1`). The PCB contains the same 38 switch footprints, one reversible Pro Micro footprint, five row nets (`R0`–`R4`), and eight column nets (`C0`–`C7`). The project file adds no alternative net mapping.

### Matrix per PCB half

| KiCad row | C0 | C1 | C2 | C3 | C4 | C5 | C6 | C7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R0 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | — |
| R1 | S8 | S9 | S10 | S11 | S12 | S13 | S14 | — |
| R2 | S15 | S16 | S17 | S18 | S19 | S20 | S21 | S36 |
| R3 | S22 | S23 | S24 | S25 | S26 | S27 | S28 | S37 |
| R4 | S29 | S30 | S31 | S32 | S33 | S34 | S35 | S38 |

That is 38 keys per half and 76 keys for the complete keyboard. The logical key order is 14, 14, 16, 16, and 16 keys from top to bottom.

### Controller pin mapping

The KiCad symbol names RP2040 GPIOs, while ZMK addresses the physical Pro Micro interconnect. The effective mapping below was verified by continuity measurements from every matrix net to the nice!nano pins on the assembled reversible PCB:

| KiCad net | KiCad U1 pad / RP2040 label | ZMK Pro Micro pin | nice!nano v2 GPIO |
|---|---|---:|---|
| R0 | 23 / GP26 | 18 | P1.15 |
| R1 | 22 / GP22 | 15 | P1.13 |
| R2 | 21 / GP20 | 14 | P1.11 |
| R3 | 20 / GP23 | 16 | P0.10 |
| R4 | 19 / GP21 | 10 | P0.09 |
| C0 | 6 / GP2 | 2 | P0.17 |
| C1 | 7 / GP3 | 3 | P0.20 |
| C2 | 8 / GP4 | 4 | P0.22 |
| C3 | 9 / GP5 | 5 | P0.24 |
| C4 | 10 / GP6 | 6 | P1.00 |
| C5 | 11 / GP7 | 7 | P0.11 |
| C6 | 12 / GP8 | 8 | P1.04 |
| C7 | 13 / GP9 | 9 | P1.06 |

The left overlay scans the columns from the outside toward the inside as `2, 3, 4, 5, 6, 7, 8, 9`. The mirrored right PCB is read in physical left-to-right order, so its overlay reverses the sequence to `9, 8, 7, 6, 5, 4, 3, 2`. The right transform adds a column offset of eight. In the first two rows, the transform skips the absent inner `C7` position on each half.

### Important: no matrix diodes

Neither the schematic nor the PCB contains diode components or diode intermediate nets. An electrical diode direction therefore cannot be derived because no diodes exist. ZMK still requires a scan direction; `diode-direction = "col2row"` is used to drive columns high and read rows with pull-downs. It must not be interpreted as a statement that COL2ROW diodes are fitted.

A diode-less 5×8 matrix can ghost for some three-or-more-key combinations. Firmware cannot remove that electrical limitation. If reliable arbitrary n-key rollover is required, the PCB must be revised to add one diode per switch.

## Split and Bluetooth behavior

- `mwv1_left` is the central and runs the keymap, USB HID, Bluetooth host connection, and ZMK Studio.
- `mwv1_right` is a BLE peripheral and sends key positions to the central.
- ZMK's five standard Bluetooth profiles are available on the Function layer.
- Hold either `FN` key to reach the Function layer. Its left top row contains `BT CLR`, profiles 0–4, and `Studio Unlock`.
- The Function layer also contains explicit `OUT USB` and `OUT BLE` keys.

## Building

Push the repository to GitHub. `.github/workflows/build.yml` invokes the current ZMK workflow, and `build.yaml` produces:

- `mwv1_left` — central firmware with ZMK Studio over USB
- `mwv1_right` — BLE peripheral firmware
- `settings_reset` — settings-reset firmware for the nice!nano v2

The left-side equivalent local command is:

```sh
west build -d build/mwv1_left -b nice_nano//zmk \
  -S studio-rpc-usb-uart -- \
  -DSHIELD=mwv1_left \
  -DZMK_CONFIG=/absolute/path/to/zmk-config-mwv1/config \
  -DCONFIG_ZMK_STUDIO=y
```

Build the right side without the snippet and Studio argument, using `-DSHIELD=mwv1_right`.

## Flashing for the first time

1. Switch both keyboard halves off.
2. Connect the right nice!nano by USB and double-press reset to mount the `NICENANO` drive.
3. Copy the right-side UF2 file to the drive and disconnect USB.
4. Connect the left nice!nano, enter the bootloader the same way, and copy the left-side UF2 file.
5. Power both halves and reset both at nearly the same time. They should bond automatically within a few seconds.
6. Pair `MWV1` in the host Bluetooth settings, or use the left half directly over USB.

The peripheral does not act as a USB keyboard. USB host output and ZMK Studio belong to the left/central half.

## ZMK Studio

Connect the left half over USB, select USB output on the Function layer, and invoke `Studio Unlock` on that layer. Then open [ZMK Studio](https://zmk.studio/) in Chrome or Edge. The physical layout contains all 76 positions in the same order as the matrix transform and keymap.

After Studio has stored a runtime keymap, later edits to `mwv1.keymap` are not applied until **Restore Stock Settings** is selected in Studio.

## Pairing problems and settings reset

For a host-only pairing problem, remove `MWV1` from the host, select the intended Bluetooth profile, press `BT CLR`, and pair again.

If the two halves no longer connect:

1. Flash the `settings_reset` UF2 to **both** nice!nanos. It clears all host and split bonds.
2. Reflash `mwv1_right` to the right controller.
3. Reflash `mwv1_left` to the left controller.
4. Power and reset both halves at nearly the same time.
5. Remove the old host entry and pair `MWV1` again.

Settings reset is intentionally a separate temporary firmware. Always reflash the correct left/right firmware afterward.

## BLE controller smoke test

The `mwv1_ble_test` artifact starts Bluetooth and USB without configuring matrix GPIOs, split communication, or ZMK Studio. It advertises as `MWV1 BLE TEST` and is intended only for diagnosis.

1. Flash `settings_reset` to the controller under test.
2. Flash `mwv1_ble_test` immediately afterward.
3. Keep the controller powered by USB or a charged battery.
4. Search for `MWV1 BLE TEST` from both a phone and the host computer.

If the test name is not visible to either device, the failure is independent of the keyboard matrix and split configuration. Reflash `mwv1_left` after completing the test.

The normal and diagnostic firmware use ZMK's conservative BLE connection mode and disable strict GATT subscription enforcement to improve compatibility with Windows hosts. Passkey entry remains disabled.

## Matrix USB logging

The `mwv1_left_debug` artifact replaces Studio with ZMK USB logging on the central half. It keeps the real matrix, split, keymap, USB HID, and Bluetooth configuration. Use it temporarily when no key presses are detected, then capture the serial output while pressing keys. Reflash the normal `mwv1_left` artifact after diagnosis to restore ZMK Studio.

The `mwv1_right_debug` artifact keeps the right half in peripheral mode while exposing its matrix and split logs over USB. It is used to distinguish a local right-side matrix problem from a missing split BLE connection. Reflash the normal `mwv1_right` artifact after diagnosis.
