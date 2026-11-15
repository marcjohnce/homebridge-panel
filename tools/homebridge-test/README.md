# Test against a real Homebridge

A small Homebridge plugin (`plugin/homebridge-panel-test`) with one accessory per device type the
panel supports: lights (color, white tone), plug, switch, fan, thermostat with battery, blinds,
window with battery, leak, motion, occupancy, smoke and CO sensors, weather and air quality
sensors, light sensor, alarm system, valve and garage door. `check.py` runs the panel's device
manager against it and checks that every device is recognized and every command arrives.

```sh
mkdir -p /tmp/hb && cd /tmp/hb
npm install homebridge@2                     # or homebridge@1 to compare
mkdir storage && cp ~/homebridge-panel/tools/homebridge-test/config.json storage/
npx homebridge -I -U storage -P ~/homebridge-panel/tools/homebridge-test/plugin --strict-plugin-resolution &
python ~/homebridge-panel/tools/homebridge-test/check.py hap
```

For the Homebridge UI backend also install `homebridge-config-ui-x`, start its standalone server
(`UIX_CONFIG_PATH=storage/config.json UIX_STORAGE_PATH=storage UIX_INSECURE_MODE=1
node node_modules/homebridge-config-ui-x/dist/bin/standalone.js`), create a user in the browser
on port 8581 and run `check.py ui <user> <password>`.

Last run (November 2026): all checks passed with Homebridge 2.5.0 (HAP-NodeJS 2.3.0) over HAP
and over Homebridge UI 5.30.1, and with Homebridge 1.11.4 over HAP.
