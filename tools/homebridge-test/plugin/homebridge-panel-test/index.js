// Test accessories for the smart home panel: every service type the panel supports
let hap;
module.exports = (api) => { hap = api.hap; api.registerPlatform("PanelTest", PanelTest); };

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
    cb(list);
  }
}
