# User interface

All screenshots are taken from the running app with demo devices and annotated
automatically. To update them after UI changes, run:

```bash
python tools/doc_screenshots.py      # writes docs/images/*.png
```

## Screen sizes

The layout adapts to the display. Landscape is recommended.

| Resolution | Typical display | Tile columns | Notes |
|---|---|---|---|
| 800 × 480 | Raspberry Pi Touch Display (7″, 1st generation) | 3 | compact sidebar and clock |
| 1024 × 600 | common 7″ HDMI/DSI displays | 4 | reference size for this guide |
| 1280 × 720 | Raspberry Pi Touch Display 2 (7″), rotated to landscape | 5 | |
| 1280 × 800 | common 10.1″ displays | 5 | |
| 720 × 1280 | Raspberry Pi Touch Display 2 in its native portrait orientation | 2 | usable, but leaves space unused and cuts off long room tabs; rotate the display to landscape |

Start the app at a given size in a window with `.venv/bin/python -m app --size 800x480`.

## Home screen

| # | Element | What it does |
|---|---|---|
| 1 | Clock and date | Current time and date |
| 2 | Indoor temperature | Average of all reachable thermostats |
| 3 | Scenes | Tap to run a scene from `config.yaml`, e.g. *All off* or *Comfort* |
| 4 | Connection status | Green: all bridges connected. Red: a bridge is not reachable (details under Settings → Info) |
| 5 | Settings | Opens the [settings page](#settings) |
| 6 | Rooms | Filter the tiles by room; *All* shows every device with its room above the name |
| 7 | Device that is on | Gold tiles are switched on. Tap a tile to switch it on or off |
| 8 | Open controls | Opens brightness, color or speed controls. A long press on the tile does the same |
| 9 | Heating tile | Small arc with the target temperature; the text turns orange while heating. Tap to open the thermostat |

Tiles leave out the room from the device name when the room is shown anyway
("Living Room Heating" → "Heating"). The detail view shows the full name.

### 1024 × 600

![Home screen at 1024 × 600](images/home-1024x600.png)

### 800 × 480 – Raspberry Pi Touch Display

![Home screen at 800 × 480](images/home-800x480.png)

### 1280 × 720 – Raspberry Pi Touch Display 2 (landscape)

![Home screen at 1280 × 720](images/home-1280x720.png)

### 1280 × 800 – 10.1″ displays

![Home screen at 1280 × 800](images/home-1280x800.png)

### 720 × 1280 – portrait

<img src="images/home-720x1280.png" alt="Home screen at 720 × 1280 in portrait" width="360">

## Thermostat

![Thermostat detail view](images/heating.png)

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

**Color light**

![Light with color wheel](images/light.png)

**White light with adjustable white tone**

![Light with white tone](images/light-white-tone.png)

| # | Element | What it does |
|---|---|---|
| 1 | Brightness | Drag up or down (1–100%). For fans this bar sets the speed |
| 2 | Color wheel | Angle sets the hue, distance from the center sets the saturation; the ring shows the current color |
| 3 | Power | Switches the device on or off; gold when on |
| 4 | White tone | From cool (left) to warm (right), shown in kelvin |

Only the controls the device supports are shown.

## Settings

![Settings page](images/settings.png)

| # | Element | What it does |
|---|---|---|
| 1 | Display | *Appearance* (Automatic, Light, Dark) and *Screen saver after*. Saved immediately |
| 2 | Homebridge | *Connect to Homebridge*, *Address*, *Port* and *PIN*. Changes are collected until you apply them |
| 3 | Test connection | Tries the entered address, port and PIN without saving and reports how many devices were found |
| 4 | Apply | Saves the Homebridge settings and reconnects without restarting the app. Enabled only when something changed |

*Automatic* switches to dark from 7 pm to 7 am. Scroll down for the **Info** section with
connection details, number of devices, file locations and version.

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

## Screen saver

After the time set under *Screen saver after*, the panel shows a large clock with the
indoor temperature. The first touch only wakes the panel and does not trigger anything
underneath.

![Screen saver](images/screensaver.png)

## Dark theme

![Home screen, dark](images/home-dark.png)

![Thermostat, dark](images/heating-dark.png)
