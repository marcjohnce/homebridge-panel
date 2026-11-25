"""Data models for panel devices."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DeviceType(str, Enum):
    LIGHT = "light"
    PLUG = "plug"
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    FAN = "fan"
    SENSOR = "sensor"
    BLIND = "blind"
    SECURITY = "security"     # contact (window, door, glass break), leak, motion, smoke and CO sensors
    VALUE = "value"           # virtual device: a value received over MQTT
    GARAGE = "garage"         # garage door opener
    LOCK = "lock"             # door lock
    TV = "tv"                 # television: power, input sources, volume, remote keys
    SPEAKER = "speaker"       # speaker / smart speaker: volume, mute, play/pause
    PURIFIER = "purifier"     # air purifier: on/off, auto/manual, speed
    HUMIDIFIER = "humidifier" # humidifier / dehumidifier: mode, target humidity
    VALVE = "valve"           # water valve: generic, irrigation, shower head, faucet
    ALARM = "alarm"           # alarm system (HomeKit SecuritySystem): armed / disarmed / triggered


# Icon names used by the UI (see app/qml/Icons.js):
# light, strip, ceiling, plug, switch, thermostat, radiator, floor, fan, coffee, tv,
# weather, drop, sun
DEFAULT_ICONS = {
    DeviceType.LIGHT: "light",
    DeviceType.PLUG: "plug",
    DeviceType.SWITCH: "switch",
    DeviceType.THERMOSTAT: "thermostat",
    DeviceType.FAN: "fan",
    DeviceType.SENSOR: "thermostat",
    DeviceType.BLIND: "blinds",
    DeviceType.SECURITY: "contact",
    DeviceType.VALUE: "gauge",
    DeviceType.ALARM: "alarm",
    DeviceType.VALVE: "valve",
    DeviceType.GARAGE: "garage",
    DeviceType.LOCK: "lock",
    DeviceType.TV: "tv",
    DeviceType.SPEAKER: "speaker",
    DeviceType.PURIFIER: "purifier",
    DeviceType.HUMIDIFIER: "humidifier",
}

# Kinds of security sensors. A contact sensor can be a window, a door, a plain contact
# (e.g. a cupboard or a gate) or a glass break detector; HomeKit has no glass break type, so
# plugins expose those as contact or motion sensors.
SECURITY_KINDS = ("window", "door", "contact", "glassbreak", "leak", "motion", "presence", "smoke", "co")
SECURITY_ICONS = {"window": "window", "door": "door", "contact": "contact", "glassbreak": "glass",
                  "leak": "leak", "motion": "motion", "presence": "presence",
                  "smoke": "smoke", "co": "co"}
ALARM_KINDS = {"glassbreak", "leak", "smoke", "co"}
# Presence (occupancy) sensors report "present" for as long as someone is in the room: no security
# alerts unless switched on on the panel
QUIET_KINDS = {"presence"}

# What a switch or plug powers; chosen on the panel or with appliance: in config.yaml.
# The kind sets the icon; "fan" puts the device under "Climate", washer and dishwasher
# show "Running" while their plug reports power use.
APPLIANCE_KINDS = ("switch", "plug", "coffee", "washer", "dishwasher", "fan", "printer3d", "computer")
APPLIANCE_ICONS = {k: k for k in APPLIANCE_KINDS}
# Lamp kinds of lights; only the icon changes (lamp: in config.yaml)
LAMP_KINDS = ("bulb", "ceiling", "pendant", "chandelier", "spot", "downlight", "wall", "table", "desk", "floorlamp", "globe",
              "tube", "strip")
LAMP_ICONS = {"bulb": "light", "ceiling": "ceiling", "spot": "spot", "downlight": "downlight", "wall": "wall", "table": "table",
              "desk": "desk", "floorlamp": "floorlamp", "globe": "globe", "tube": "tube", "pendant": "pendant", "strip": "strip",
              "chandelier": "chandelier"}
# Lamp kind guessed from the name of a new light (in the languages of the panel); the first
# kind with a matching word wins, so the more specific ones come first ("Deckenspot" is a spot,
# "Schreibtischlampe" a desk lamp, not a table lamp). Words are matched in the lower case name.
LAMP_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("strip", ("strip", "streifen", "led-band", "ledband", "lichtband", "ruban", "striscia", "tira led", "fita led")),
    ("tube", ("röhre", "roehre", "leuchtstoff", "tube", "neon", "tubo")),
    ("chandelier", ("kronleuchter", "lüster", "luester", "chandelier", "lustre", "lampadario", "araña", "candelabro")),
    ("pendant", ("pendel", "hängelampe", "hängeleuchte", "haengelampe", "pendant", "suspension", "sospensione",
                 "colgante", "pendente")),
    # recessed before spot: "Einbaustrahler" is a downlight, "Strahler" a spot
    ("downlight", ("downlight", "einbau", "encastré", "encastre", "incasso", "empotrad", "embutid", "encastrad")),
    ("spot", ("spot", "strahler", "faretto", "foco")),
    ("desk", ("schreibtisch", "desk", "bureau", "scrivania", "escritorio", "secretária", "secretaria")),
    ("floorlamp", ("stehlampe", "stehleuchte", "floor lamp", "floorlamp", "lampadaire", "piantana", "de pie", "de pé")),
    ("table", ("tischlampe", "tischleuchte", "nachttisch", "table", "chevet", "tavolo", "comodino", "mesa")),
    ("wall", ("wand", "wall", "mural", "applique", "parete", "pared", "parede", "aplique")),
    ("globe", ("kugel", "globe", "globo", "sphère", "boule", "esfera")),
    ("ceiling", ("decke", "ceiling", "plafond", "plafonnier", "soffitto", "plafoniera", "techo", "plafón", "teto")),
)


# Kind of a new switch or plug guessed from its name, as for lights; the more specific first
APPLIANCE_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("printer3d", ("3d-drucker", "3d drucker", "3d printer", "3d-printer", "imprimante 3d", "stampante 3d",
                   "impresora 3d", "impressora 3d", "prusa", "bambu", "creality", "ender")),
    ("computer", ("computer", "rechner", "pc", "server", "laptop", "notebook", "ordinateur", "computador",
                  "ordenador", "nas")),
)


def guess_appliance(name: str) -> str | None:
    """What a new switch or plug powers, from its name ("3D-Drucker" → "printer3d"); None if
    nothing fits. Short words count only as a whole word ("PC", "Ender"), not inside others
    ("Kalender")."""
    low = name.casefold()
    words = set(low.replace("-", " ").split())
    for kind, keys in APPLIANCE_WORDS:
        if any((k in words) if len(k) <= 5 else (k in low) for k in keys):
            return kind
    return None


def guess_lamp(name: str) -> str | None:
    """Lamp kind from the name of a light ("Wandleuchte Flur" → "wall"), None if nothing fits."""
    low = name.casefold()
    for kind, words in LAMP_WORDS:
        if any(w in low for w in words):
            return kind
    return None


# Kinds of valves (HomeKit ValveType); generic valves (e.g. water shut-off) go under "Security"
VALVE_KINDS = ("generic", "irrigation", "shower", "faucet")
VALVE_ICONS = {"generic": "valve", "irrigation": "sprinkler", "shower": "shower", "faucet": "faucet"}
KIND_ICONS = {**SECURITY_ICONS, **APPLIANCE_ICONS, **LAMP_ICONS, **VALVE_ICONS}
KIND_KEYS = ("security", "appliance", "lamp", "valve")     # meta keys that hold a device's kind
AREAS = ("light", "climate", "security")      # menu areas a device can be moved to     # triggered = alarm; the others are only "open" / "motion"


@dataclass
class Device:
    id: str
    name: str
    type: DeviceType
    backend: str
    room: str
    icon: str
    state: dict[str, Any] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    reachable: bool = True
    order: int = 100

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d
