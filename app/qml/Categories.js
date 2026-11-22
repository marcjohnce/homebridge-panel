.pragma library

// Menu areas of the home screen (see app/qt/format.py CATEGORIES; "scenes": scenes of the panel)
var keys = ["favorites", "light", "scenes", "climate", "weather", "energy", "security"];
var icons = { favorites: "star", light: "light", scenes: "spark", climate: "thermostat", weather: "weather",
              energy: "bolt", security: "shield" };

// "energy" only while a device measures its power, "weather" only with a place in the settings
function shown(hasEnergy, hasWeather) {
    return keys.filter(k => (k !== "energy" || hasEnergy) && (k !== "weather" || hasWeather));
}
