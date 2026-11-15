// Test accessories for the smart home panel: every service type the panel supports
let hap, homebridge;
module.exports = (api) => { hap = api.hap; homebridge = api; api.registerPlatform("PanelTest", PanelTest); };

class Acc {
  constructor(name) {
    const { Service, Characteristic, uuid } = hap;
    this.name = name;
    this.info = new Service.AccessoryInformation()
      .setCharacteristic(Characteristic.Manufacturer, "Panel Test").setCharacteristic(Characteristic.Model, "T1")
      .setCharacteristic(Characteristic.SerialNumber, uuid.generate(name).slice(0, 8));
    this.services = [this.info];
  }
  add(ServiceType, name, values, sub) {
    const s = new ServiceType(name, sub);
    for (const [C, v] of values) {
      const ch = s.getCharacteristic(C);
      ch.value = v;
      ch.onGet(() => ch.value);
      ch.onSet((nv) => { ch.value = nv; if (this.onSet) this.onSet(s, C, nv); });
    }
    this.services.push(s);
    return s;
  }
  getServices() { return this.services; }
}

class PanelTest {
  constructor(log) { this.log = log; }
  accessories(cb) {
    const { Service: S, Characteristic: C } = hap;
    const list = [];
    const mk = (name) => { const a = new Acc(name); list.push(a); return a; };

    mk("Color Light").add(S.Lightbulb, "Color Light", [[C.On, true], [C.Brightness, 70], [C.Hue, 30], [C.Saturation, 80]]);
    mk("White Light").add(S.Lightbulb, "White Light", [[C.On, false], [C.Brightness, 40], [C.ColorTemperature, 300]]);
    mk("Plug").add(S.Outlet, "Plug", [[C.On, true], [C.OutletInUse, true]]);
    mk("Switch").add(S.Switch, "Switch", [[C.On, false]]);
    mk("Fan").add(S.Fanv2, "Fan", [[C.Active, 0], [C.RotationSpeed, 50]]);
    const th = mk("Thermostat");
    th.add(S.Thermostat, "Thermostat", [[C.CurrentHeatingCoolingState, 1], [C.TargetHeatingCoolingState, 1],
      [C.CurrentTemperature, 19.5], [C.TargetTemperature, 21], [C.TemperatureDisplayUnits, 0]]);
    th.add(S.Battery, "Battery", [[C.BatteryLevel, 7], [C.StatusLowBattery, 0]]);
    mk("Blinds").add(S.WindowCovering, "Blinds", [[C.CurrentPosition, 60], [C.TargetPosition, 60], [C.PositionState, 2]]);
    const win = mk("Window");
    win.add(S.ContactSensor, "Window", [[C.ContactSensorState, 1]]);
    win.add(S.Battery, "Battery", [[C.BatteryLevel, 55], [C.StatusLowBattery, 0]]);
    mk("Leak").add(S.LeakSensor, "Leak", [[C.LeakDetected, 0], [C.StatusLowBattery, 1]]);
    mk("Motion").add(S.MotionSensor, "Motion", [[C.MotionDetected, true]]);
    mk("Presence").add(S.OccupancySensor, "Presence", [[C.OccupancyDetected, 1]]);
    mk("Smoke").add(S.SmokeSensor, "Smoke", [[C.SmokeDetected, 0]]);
    mk("CO").add(S.CarbonMonoxideSensor, "CO", [[C.CarbonMonoxideDetected, 0]]);
    const ws = mk("Weather");
    ws.add(S.TemperatureSensor, "Temperature", [[C.CurrentTemperature, 6.5]]);
    ws.add(S.HumiditySensor, "Humidity", [[C.CurrentRelativeHumidity, 82]]);
    const air = mk("Air");
    air.add(S.AirQualitySensor, "Air", [[C.AirQuality, 2], [C.PM2_5Density, 12]]);
    air.add(S.CarbonDioxideSensor, "CO2", [[C.CarbonDioxideDetected, 0], [C.CarbonDioxideLevel, 640]]);
    mk("Light Level").add(S.LightSensor, "Light Level", [[C.CurrentAmbientLightLevel, 321]]);

    const alarm = mk("Alarm");
    alarm.add(S.SecuritySystem, "Alarm", [[C.SecuritySystemCurrentState, 3], [C.SecuritySystemTargetState, 3]]);
    alarm.onSet = (s, Ch, v) => { if (Ch === C.SecuritySystemTargetState) s.getCharacteristic(C.SecuritySystemCurrentState).value = v; };
    const valve = mk("Sprinkler");
    valve.add(S.Valve, "Sprinkler", [[C.Active, 0], [C.InUse, 0], [C.ValveType, 1], [C.SetDuration, 600], [C.RemainingDuration, 0]]);
    valve.onSet = (s, Ch, v) => {
      if (Ch === C.Active) { s.getCharacteristic(C.InUse).value = v; s.getCharacteristic(C.RemainingDuration).value = v ? s.getCharacteristic(C.SetDuration).value : 0; }
    };
    const garage = mk("Garage");
    garage.add(S.GarageDoorOpener, "Garage", [[C.CurrentDoorState, 1], [C.TargetDoorState, 1], [C.ObstructionDetected, false]]);
    garage.onSet = (s, Ch, v) => { if (Ch === C.TargetDoorState) s.getCharacteristic(C.CurrentDoorState).value = v; };
    const win2 = mk("Skylight");
    win2.add(S.Window, "Skylight", [[C.CurrentPosition, 0], [C.TargetPosition, 0], [C.PositionState, 2]]);
    win2.onSet = (s, Ch, v) => { if (Ch === C.TargetPosition) s.getCharacteristic(C.CurrentPosition).value = v; };
    const door2 = mk("Motor Door");
    door2.add(S.Door, "Motor Door", [[C.CurrentPosition, 0], [C.TargetPosition, 0], [C.PositionState, 2]]);
    door2.onSet = win2.onSet;
    mk("Speaker").add(S.Speaker, "Speaker", [[C.Mute, false], [C.Volume, 40]]);
    const smart = mk("Smart Speaker");
    smart.add(S.SmartSpeaker, "Smart Speaker", [[C.CurrentMediaState, 1], [C.TargetMediaState, 1], [C.Volume, 30]]);
    smart.onSet = (s, Ch, v) => { if (Ch === C.TargetMediaState) s.getCharacteristic(C.CurrentMediaState).value = v; };
    const pur = mk("Purifier");
    pur.add(S.AirPurifier, "Purifier", [[C.Active, 0], [C.CurrentAirPurifierState, 0], [C.TargetAirPurifierState, 1],
      [C.RotationSpeed, 40]]);
    pur.onSet = (s, Ch, v) => { if (Ch === C.Active) s.getCharacteristic(C.CurrentAirPurifierState).value = v ? 2 : 0; };
    mk("Humidifier").add(S.HumidifierDehumidifier, "Humidifier", [[C.Active, 1],
      [C.CurrentHumidifierDehumidifierState, 2], [C.TargetHumidifierDehumidifierState, 1], [C.CurrentRelativeHumidity, 38],
      [C.RelativeHumidityHumidifierThreshold, 45], [C.RelativeHumidityDehumidifierThreshold, 60], [C.WaterLevel, 70]]);
    const lock = mk("Lock");
    lock.add(S.LockMechanism, "Lock", [[C.LockCurrentState, 1], [C.LockTargetState, 1]]);
    lock.onSet = (s, Ch, v) => { if (Ch === C.LockTargetState) s.getCharacteristic(C.LockCurrentState).value = v; };
    const tv = mk("Television");
    const tvs = tv.add(S.Television, "Television", [[C.Active, 0], [C.ActiveIdentifier, 1],
      [C.ConfiguredName, "Television"], [C.SleepDiscoveryMode, 1]]);
    tvs.getCharacteristic(C.RemoteKey).onSet(() => {});
    ["HDMI 1", "HDMI 2", "Netflix"].forEach((name, i) => {
      const src = tv.add(S.InputSource, name, [[C.Identifier, i + 1], [C.ConfiguredName, name],
        [C.IsConfigured, 1], [C.InputSourceType, 3], [C.CurrentVisibilityState, 0]], "input" + (i + 1));
      tvs.addLinkedService(src);
    });
    const spk = tv.add(S.TelevisionSpeaker, "Speaker", [[C.Mute, false], [C.VolumeControlType, 1]]);
    spk.getCharacteristic(C.VolumeSelector).onSet(() => {});
    tvs.addLinkedService(spk);
    this.addHistory(list, mk);
    cb(list);
  }

  // Eve history like plugins built on fakegato-history keep it: three days of 10-minute values
  // (weather) and a small ring buffer that has already wrapped around (thermostat).
  // Optional: needs `npm install fakegato-history` where Homebridge can find it (e.g. NODE_PATH).
  addHistory(list, mk) {
    let FakeGato;
    try {
      FakeGato = require("fakegato-history")(homebridge);
    } catch (e) {
      this.log.info("fakegato-history not installed – no history accessories");
      return;
    }
    const { Service: S, Characteristic: C } = hap;
    const now = Math.round(Date.now() / 1000);
    const hw = mk("History Weather");
    hw.add(S.TemperatureSensor, "History Weather", [[C.CurrentTemperature, 7.5]]);
    hw.add(S.HumiditySensor, "History Humidity", [[C.CurrentRelativeHumidity, 80]]);
    Object.assign(hw, { displayName: "History Weather", log: this.log });
    const wh = new FakeGato("weather", hw, { disableTimer: true, size: 4032 });
    hw.services.push(wh);
    for (let i = 432; i >= 1; i--) {
      wh.addEntry({ time: now - i * 600, temp: Math.round(500 + 300 * Math.sin(i / 24)) / 100, humidity: 80, pressure: 1013 });
    }
    const ht = mk("History Thermostat");
    ht.add(S.Thermostat, "History Thermostat", [[C.CurrentHeatingCoolingState, 1], [C.TargetHeatingCoolingState, 1],
      [C.CurrentTemperature, 20.5], [C.TargetTemperature, 21], [C.TemperatureDisplayUnits, 0]]);
    Object.assign(ht, { displayName: "History Thermostat", log: this.log });
    const th = new FakeGato("thermo", ht, { disableTimer: true, size: 100 });
    ht.services.push(th);
    for (let i = 150; i >= 1; i--) {
      th.addEntry({ time: now - i * 600, currentTemp: 20 + (i % 10) / 10, setTemp: 21, valvePosition: 40 });
    }
  }
}
