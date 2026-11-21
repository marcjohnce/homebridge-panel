.pragma library

// Menu areas of the home screen (see app/qt/format.py CATEGORIES; "scenes": scenes of the panel)
var keys = ["favorites", "light", "scenes", "climate", "energy", "security"];
var icons = { favorites: "star", light: "light", scenes: "spark", climate: "thermostat", energy: "bolt", security: "shield" };

// "energy" only while a device measures its power
function shown(hasEnergy) {
    return keys.filter(k => k !== "energy" || hasEnergy);
}
