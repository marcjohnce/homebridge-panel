# User interface

All screenshots are taken from the running app with demo devices and annotated
automatically: numbered callouts point to the elements, and each image has its legend below.
The tables add details. To update them after UI changes, run:

```bash
python tools/doc_screenshots.py      # writes docs/images/*.png
```

## Screen sizes

The layout adapts to the display. Wide screens show a **sidebar** on the left with the clock,
indoor temperature and scenes. Square and portrait screens (width less than 1.4 × height)
switch to a **top bar** with the same elements in one row and the scenes as a horizontal strip,
so the tiles get the full width. The callout numbers below are the same for both layouts.

The panel is optimized for **1280 × 800** and **720 × 720**:

- Fonts, spacing and touch targets grow with the screen: 1.0× up to 1024 × 600 and on square
  or portrait screens, 1.2× at 1280 × 720, 1.25× at 1280 × 800 (at most 1.3×).
- The thermostat dial, brightness bar and color wheel use the space that is available instead
  of a fixed size (dial: 540 px at 1280 × 800, 424 px at 720 × 720).
- If the tile rows almost fit on the screen, tiles become slightly flatter (at most 15%) so only
  whole rows are visible – three rows at 720 × 720.

| Resolution | Typical display | Tile columns | Notes |
|---|---|---|---|
| 800 × 480 | Raspberry Pi Touch Display (7″, 1st generation) | 3 | compact sidebar and clock |
| 1024 × 600 | common 7″ HDMI/DSI displays | 4 | |
| 1280 × 720 | Raspberry Pi Touch Display 2 (7″), rotated to landscape | 4 | 1.2× scale |
| **1280 × 800** | common 10.1″ displays | 4 | **optimized**, 1.25× scale, used for the detail screenshots |
| **720 × 720** | square displays, e.g. Pimoroni HyperPixel 4.0 Square (4″) | 3 | **optimized**, top bar layout |
| 720 × 1280 | Raspberry Pi Touch Display 2 in its native portrait orientation | 3 | top bar layout |

Start the app at a given size in a window with `.venv/bin/python -m app --size 800x480`.

## Home screen

| # | Element | What it does |
|---|---|---|
| 1 | Clock and date | Current time and date (in the top bar: clock with date and temperature next to it) |
| 2 | Indoor and outdoor temperature | *indoors*: average of all reachable thermostats and indoor sensors. *outdoors*: sensors marked `outdoor: true` (shown only if there is one) |
| 3 | Scenes | Tap to run a scene from `config.yaml`, e.g. *All off* or *Comfort* |
| 4 | Connection status | Green: all bridges connected. Red: a bridge is not reachable (details under Settings → Info) |
| 5 | Settings | Opens the [settings page](#settings) |
| 6 | Rooms | Filter the tiles by room; *All* shows every device with its room above the name |
| 7 | Device that is on | Gold tiles are switched on. Tap a tile to switch it on or off (blinds: open or close) |
| 8 | Open controls | Opens brightness, color or speed controls. A long press on the tile does the same |
| 9 | Heating tile | Small arc with the target temperature; the text turns orange while heating. Tap to open the thermostat |
| 10 | Sensor tile | Current readings, e.g. temperature, humidity and air pressure of a weather station. Tap to open the [sensor view](#sensors) |

Tiles leave out the room from the device name when the room is shown anyway
("Living Room Heating" → "Heating"). The detail view shows the full name.

### 1280 × 800 – 10.1″ displays

![Home screen at 1280 × 800](images/home-1280x800.png)

### 720 × 720 – square displays (top bar)

![Home screen at 720 × 720](images/home-720x720.png)

### 1024 × 600

![Home screen at 1024 × 600](images/home-1024x600.png)

### 800 × 480 – Raspberry Pi Touch Display

![Home screen at 800 × 480](images/home-800x480.png)

### 1280 × 720 – Raspberry Pi Touch Display 2 (landscape)

![Home screen at 1280 × 720](images/home-1280x720.png)

### 720 × 1280 – portrait (top bar)

<img src="images/home-720x1280.png" alt="Home screen at 720 × 1280 in portrait" width="360">

## Thermostat

![Thermostat at 1280 × 800](images/heating.png)

<img src="images/heating-720x720.png" alt="Thermostat at 720 × 720" width="480">

| # | Element | What it does |
|---|---|---|
| 1 | Back | Returns to the home screen; shows the device's room |
| 2 | Status | *Heating now* while the heating is running, *Not reachable* if the device is offline |
| 3 | Dial | Drag the knob along the arc to set the target temperature; the current temperature is shown below the target |
| 4 | Cooler / Warmer | Changes the target in the thermostat's step size (usually 0.5 °C) |
| 5 | Mode | *Off*, *Heat* or *Auto*. Changing the temperature while off switches to *Heat* |

Changes are sent shortly after you stop dragging or tapping, so a quick series of taps
results in one command.

## Lights and fans

**Color light** – 1280 × 800 and 720 × 720

![Light with color wheel at 1280 × 800](images/light.png)

<img src="images/light-720x720.png" alt="Light with color wheel at 720 × 720" width="480">

**White light with adjustable white tone** – 1280 × 800 and 720 × 720

![Light with white tone at 1280 × 800](images/light-white-tone.png)

<img src="images/light-white-tone-720x720.png" alt="Light with white tone at 720 × 720" width="480">

| # | Element | What it does |
|---|---|---|
| 1 | Brightness | Drag up or down (1–100%). For fans this bar sets the speed |
| 2 | Color wheel | Angle sets the hue, distance from the center sets the saturation; the ring shows the current color |
| 3 | Power | Switches the device on or off; gold when on |
| 4 | White tone | From cool (left) to warm (right), shown in kelvin |

Only the controls the device supports are shown.

## Blinds

Window blinds (HomeKit *Window Covering*). Tap the tile to open fully or close, tap "›"
or press and hold for the detail view.

![Blinds at 1280 × 800](images/blinds.png)

<img src="images/blinds-720x720.png" alt="Blinds at 720 × 720" width="480">

| # | Element | What it does |
|---|---|---|
| 1 | Blind | Drag up or down (or tap) to set the position; the gold rail is the lower edge of the blind |
| 2 | Position | 0% = closed, 100% = fully open. While moving it shows the target and *Opening …* / *Closing …* |
| 3 | Open, stop, close | Opens fully, stops where the blind is (using the blind's own stop function if it has one), closes fully |
| 4 | Slat angle | Tilts the slats from −90° to 90°; only shown for blinds that support it |

While a blind moves, the panel polls it every second so the position follows smoothly,
then returns to the normal interval. If a blind reports an obstruction, the tile and the
detail view show *Obstructed*.

In scenes: `position` (0–100), `tilt` (−90…90), `stop: true`; `on: true` opens fully and
`on: false` closes.

## Sensors

Temperature, humidity, air pressure and light sensors from Homebridge appear as tiles with
their readings. All sensors of one device are combined into one tile, so a weather station
with three sensors shows up once. Tap the tile for large readings.

![Weather station at 1280 × 800](images/sensor.png)

<img src="images/sensor-720x720.png" alt="Weather station at 720 × 720" width="480">

| # | Element | What it does |
|---|---|---|
| 1 | Outdoors | Shown for sensors marked `outdoor: true` in `config.yaml` |
| 2 | Temperature | In °C |
| 3 | Humidity | Relative humidity in % |
| 4 | Air pressure | In hPa |
| 5 | Light level | In lux (light sensors) |

![Light sensor at 1280 × 800](images/sensor-light.png)

| Reading | HomeKit service | Notes |
|---|---|---|
| Temperature | Temperature Sensor | |
| Humidity | Humidity Sensor | |
| Light level | Light Sensor | |
| Air pressure | Eve Air Pressure Sensor or Eve Weather (custom Eve types) | HomeKit has no standard air pressure type; plugins such as Eve-compatible weather plugins expose it this way. Apple's Home app does not show it, the panel does |

Readings update with every poll (5 seconds by default). Sensors are read-only; tapping a
sensor tile never switches anything.

Mark outdoor sensors in `config.yaml`, so their temperature is shown as *outdoors* in the
sidebar, top bar and screen saver and is left out of the indoor average:

```yaml
devices:
  "Weather Station": { room: Garden, outdoor: true }
```

## Settings

![Settings page](images/settings.png)

| # | Element | What it does |
|---|---|---|
| 1 | Display | *Appearance* (Automatic, Light, Dark), *Language* and *Screen saver after*. Saved immediately |
| 2 | Rooms and devices | Opens the room management (see below); shows the number of rooms |
| 3 | Homebridge | *Connect to Homebridge*, *Address*, *Port* and *PIN*. Changes are collected until you apply them |
| 4 | Test connection | Tries the entered address, port and PIN without saving and reports how many devices were found |
| 5 | Apply | Saves the Homebridge settings and reconnects without restarting the app. Enabled only when something changed |

*Automatic* switches to dark from 7 pm to 7 am. Scroll down for the **Info** section with
connection details, number of devices, file locations and version.

### Language

The panel speaks English, German, French, Italian and Spanish. *System* follows the language of
the operating system (English if it is none of these). The language switches immediately,
including dates, decimal separators and messages, and also applies to the on-screen keyboard
layout (QWERTZ for German, AZERTY for French).

![Settings in German](images/settings-de.png)

![Home screen in German](images/home-de.png)

### Rooms and devices

*Settings → Rooms and devices* manages the rooms shown as tabs on the home screen. Every
change is saved at once and the home screen follows immediately.

![Rooms](images/rooms.png)

| # | Element | What it does |
|---|---|---|
| 1 | Rooms / Devices | Switches between the list of rooms and the list of devices |
| 2 | Room | Name and number of devices. The default room (*General*) collects devices that have no room yet |
| 3 | Buttons | Move the room up or down (this is the order of the room tabs), rename it, delete it |
| 4 | Add room | Creates a room. Empty rooms are kept here but do not appear on the home screen until a device is in them |

Deleting a room moves its devices to the default room. The default room itself can only be
deleted when it is empty.

Names are entered with an on-screen keyboard; a connected keyboard works as well.

![Keyboard for names](images/keyboard.png)

| # | Element | What it does |
|---|---|---|
| 1 | Name | The current name is selected when the keyboard opens; the first key replaces it |
| 2 | Keys | Letter layout of the panel language. *?123* switches to digits, punctuation and accented letters; hold delete to clear |
| 3 | Done | Saves the name, or shows why it cannot be used (empty, longer than 24 characters, name already taken) |

The *Devices* tab lists all devices grouped by room. Tap a device to move it:

![Choose a room](images/room-picker.png)

| # | Element | What it does |
|---|---|---|
| 1 | Rooms | The current room is highlighted; tap another one to move the device there |
| 2 | New room … | Creates a room with the keyboard and moves the device into it |

Rooms set here take precedence over `room:` in `config.yaml`. Moving a device back to its room from
`config.yaml` removes the override again.

### Keypad

Tapping *Address*, *Port* or *PIN* opens a keypad.

![Keypad for the PIN](images/keypad.png)

| # | Element | What it does |
|---|---|---|
| 1 | Entry | The current value is highlighted when the keypad opens; the first key press replaces it. The PIN is formatted as 123-45-678 while typing |
| 2 | Hint | Explains the expected format; shows an error in red if the entry is invalid |
| 3 | Keys | Digits and delete (hold to clear). The address keypad also has a "." key |
| 4 | Done | Checks the entry and takes it over; *Cancel* or Esc discards it |

A connected keyboard works as well, including letters for host names.

### System: restart

At the bottom of the settings page, above *Info*.

![System section](images/settings-system.png)

| # | Element | What it does |
|---|---|---|
| 1 | System | Actions that act on the app or the device |
| 2 | Restart app | Closes and starts the panel again with the same options and reconnects to Homebridge – useful after editing `config.yaml` |
| 3 | Restart Raspberry Pi | Reboots the device; the panel is back after about a minute |

Both ask before they run. While restarting, the panel shows *Restarting …*.

![Confirmation before restarting](images/confirm-restart.png)

| # | Element | What it does |
|---|---|---|
| 1 | Cancel | Closes the dialog without restarting (Esc or tapping outside does the same) |
| 2 | Restart | Restarts now (Enter does the same) |

Rebooting needs permission. `deploy/install.sh` installs a rule that allows the panel user to
reboot, also without a desktop session. If it is missing, the panel shows
*Restart not allowed* – run the install script again.

## Screen saver

After the time set under *Screen saver after*, the panel shows a large clock with the
indoor temperature. The first touch only wakes the panel and does not trigger anything
underneath.

![Screen saver](images/screensaver.png)

## Dark theme

![Home screen, dark](images/home-dark.png)

![Thermostat, dark](images/heating-dark.png)
