# Test against a real Homebridge

A small Homebridge plugin (`plugin/homebridge-panel-test`) with one accessory per device type the
panel supports: lights (color, white tone), plug, switch, fan, thermostat with battery, blinds,
window with battery, leak, motion, occupancy, smoke and CO sensors, weather and air quality
sensors, light sensor, alarm system, valve, garage door, a television with input sources and
speaker, motorized window and door, speaker, smart speaker, air purifier, humidifier and door lock,
plus – when `fakegato-history` is installed – a weather sensor and a thermostat with an Eve history. `check.py` runs the panel's device
manager against it and checks that every device is recognized and every command arrives.

```sh
mkdir -p /tmp/hb && cd /tmp/hb
npm install homebridge@2 fakegato-history    # or homebridge@1 to compare
mkdir storage && cp ~/homebridge-panel/tools/homebridge-test/config.json storage/
NODE_PATH=$PWD/node_modules npx homebridge -I -U storage -P ~/homebridge-panel/tools/homebridge-test/plugin --strict-plugin-resolution &
python ~/homebridge-panel/tools/homebridge-test/check.py hap
```

For the Homebridge UI backend also install `homebridge-config-ui-x`, add
`{"platform": "config", "name": "Config", "port": 8581}` to `platforms` in `storage/config.json`,
start its standalone server
(`UIX_CONFIG_PATH=storage/config.json UIX_STORAGE_PATH=storage UIX_INSECURE_MODE=1
node node_modules/homebridge-config-ui-x/dist/bin/standalone.js`), create a user in the browser
on port 8581 and run `check.py ui <user> <password>`.

Last run (November 2026, 26 device types, Eve history): all checks passed with Homebridge 2.5.0 (HAP-NodeJS 2.3.0) over HAP
and over Homebridge UI 5.30.1, and with Homebridge 1.11.4 over HAP.
