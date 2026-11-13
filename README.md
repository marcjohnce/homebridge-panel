# Smart Home Panel

Touch-Anwendung für Raspberry Pi (Linux) zur Steuerung von Lichtern, Smart Plugs und Heizung
über **Homebridge** bzw. das **HomeKit Accessory Protocol (HAP)**. Oberfläche in Qt Quick (QML),
Logik in Python mit **PySide6**.

```
┌──────────────────────────── Raspberry Pi ────────────────────────────┐
│  Qt-Oberfläche (QML)  ◄── Signale / Eigenschaften ──┐                 │
│   Startseite · Detailansichten · Einstellungen      │                 │
│                                                     │                 │
│  Controller (app/qt)  ──── Hintergrund-Thread (asyncio) ────┐         │
│                             DeviceManager · Scheduler       │         │
│                             Backends: HAP · Homebridge-UI · Demo      │
└─────────────────────────────────────────────────────────────┼─────────┘
                                                              ▼
                                        Homebridge (HAP, Port 51826 …)
```

## Funktionen

- **Lichter**: Ein/Aus, Helligkeitsbalken, Farbrad, Weißton
- **Smart Plugs / Schalter**: Ein/Aus, Anzeige „in Betrieb“
- **Heizung**: Thermostate und HeaterCooler mit Bogenregler (ziehen oder −/+), Modus Aus/Heizen/Auto
- **Ventilatoren**: Ein/Aus, Stufe
- **Räume, Szenen, Zeitpläne** (z. B. werktags 06:30 „Komfort“, täglich 22:30 „Eco“)
- **Hell / Dunkel / Automatisch**, **Ruhebildschirm** mit großer Uhr
- **Einstellungsseite** für Darstellung, Ruhebildschirm und Homebridge-Verbindung (Adresse, Port, PIN)
  mit Ziffernblock, Verbindungstest und Übernehmen ohne Neustart

## Voraussetzungen

- Raspberry Pi 4/5 (Pi 3 möglich) mit Raspberry Pi OS **Bookworm** oder **Trixie**, 64 Bit
- Homebridge **im Insecure-Modus**: Homebridge-UI → Einstellungen → *Homebridge Insecure Mode*
  (entspricht `-I`), danach Homebridge neu starten. Port und PIN stehen in der Homebridge-`config.json`
  unter `bridge`.

PySide6 kommt per pip: auf Bookworm wird automatisch Version 6.8 installiert, auf Trixie die aktuelle.

## Installation

```bash
cd ~/smarthome-panel                  # ZIP entpacken oder Repository klonen
./deploy/install.sh --autostart       # startet nach dem Anmelden im Vollbild
```

| Aufruf | Wirkung |
|---|---|
| `./deploy/install.sh` | nur installieren, Eintrag im Startmenü |
| `./deploy/install.sh --autostart` | zusätzlich Vollbild-Start beim Desktop-Login (labwc, wayfire, X11) |
| `./deploy/install.sh --eglfs` | Vollbild **ohne Desktop** als Systemdienst (Pi OS Lite) |

Für `--autostart` den Desktop-Autologin aktivieren: `sudo raspi-config` → *System Options* →
*Boot / Auto Login* → *Desktop Autologin*.

Danach in der App unten links auf das Einstellungs-Symbol tippen, Adresse, Port und PIN der
Homebridge eintragen, **Verbindung testen** und **Übernehmen**.

### Starten von Hand

```bash
.venv/bin/python -m app                       # im Fenster (1024×600)
.venv/bin/python -m app --size 800x480        # andere Fenstergröße
.venv/bin/python -m app --fullscreen --hide-cursor
.venv/bin/python -m app --demo                # zusätzlich simulierte Geräte
```

## Einstellungen

In der App (Symbol unten links) – gespeichert in `~/.config/smarthome-panel/settings.json`:

| Abschnitt | Einstellung | Verhalten |
|---|---|---|
| Anzeige | Darstellung: Automatisch (dunkel 19–7 Uhr), Hell, Dunkel | sofort gespeichert |
| Anzeige | Ruhebildschirm nach: Nie, 1, 2, 5, 15 Minuten | sofort gespeichert |
| Homebridge | Mit Homebridge verbinden (Ein/Aus) | über **Übernehmen** |
| Homebridge | Adresse (IP oder Name), Port, PIN | über **Übernehmen**, vorher **Verbindung testen** |

Eingaben werden geprüft (Port 1–65535, PIN im Format 123-45-678, gültige IP/Hostname).
Nach **Übernehmen** baut die App die Verbindung ohne Neustart neu auf.

### Weitere Einstellungen hinzufügen

Die Einstellungsseite baut sich aus einem Schema in `app/settings.py` auf:

1. In `FIELDS` einen Eintrag ergänzen, z. B.
   `Field("poll_interval", "homebridge", "Abfrageintervall", "choice", 5, options=((2, "2 s"), (5, "5 s"), (10, "10 s")))`.
   Arten: `choice`, `toggle`, `number`, `host`, `pin`. Neuer Abschnitt: Eintrag in `SECTIONS`
   (`instant=True` speichert sofort, `False` über „Übernehmen“).
2. Wirkung einbauen: Betrifft sie die Verbindung, in `apply_to_config()` auswerten; betrifft sie die
   Oberfläche, im `Controller` (`app/qt/controller.py`) als Eigenschaft bereitstellen und in
   `settings_saved()` das passende Signal auslösen.

Prüfung und Speicherung übernimmt `validate()` bzw. `SettingsStore` automatisch.

## Räume, Szenen, Zeitpläne (`config.yaml`)

| Abschnitt | Zweck |
|---|---|
| `server` | Abfrageintervall, Zeitzone |
| `panel` | Titel, Standardraum, `show_cooling` |
| `hap` | zusätzliche Bridges (Child-Bridges); die Haupt-Bridge kommt aus den Einstellungen |
| `homebridge_ui` | alternativ Zugriff über die Homebridge-Weboberfläche (Benutzer/Passwort) |
| `demo` | simulierte Geräte |
| `devices` | pro Gerät (ID oder Name): `room`, `name`, `icon`, `order`, `hidden` |
| `scenes` | Szenen mit Aktionen `{device: …, set: {…}}` |
| `schedules` | Szene zu Uhrzeit an Wochentagen (`mo di mi do fr sa so`) |

**Attribute in Szenen**: `on`, `brightness` (0–100), `hue` (0–360), `saturation` (0–100),
`color_temp` (Mired 140–500), `speed` (0–100), `target_temp` (°C), `mode` (`off|heat|cool|auto`).

**Symbole** (`icon:`): `light`, `ceiling`, `strip`, `plug`, `switch`, `thermostat`, `radiator`,
`floor`, `fan`, `coffee`, `tv`; für Szenen `moon`, `sun`, `film`, `leaf`, `home`, `power`.

## Bedienung

- **Startseite**: Uhr, Innentemperatur (Mittelwert der Thermostate), Szenen; rechts die Kacheln.
  Antippen schaltet, „›“ oder langes Drücken öffnet die Detailansicht. Eingeschaltet = gold.
  Auf Kacheln wird der Raumname aus dem Gerätenamen weggelassen („Heizung Wohnzimmer“ → „Heizung“).
- **Ruhebildschirm**: die erste Berührung weckt nur auf und löst nichts darunter aus.
- Eine angeschlossene Tastatur funktioniert überall (Tab, Pfeiltasten, Enter, Esc).

## Projektstruktur

```
app/
  __main__.py          Start: python -m app
  settings.py          Einstellungs-Schema, Prüfung, Speicher, Anwendung auf die Konfiguration
  config.py            config.yaml (Pydantic)
  manager.py           Geräteverwaltung: Abfrage, Befehle, Szenen
  scheduler.py         Zeitpläne
  hap_types.py         HAP-Typen ⇄ Gerätezustand/Befehle
  backends/            HAP, Homebridge-UI, Demo
  qt/
    main.py            Qt-Anwendung, Schriften, QML-Engine
    controller.py      Brücke zu QML: Gerätemodell, Einstellungen, Hintergrund-Thread
    format.py          Kacheltexte
  qml/                 Oberfläche (Main.qml, Theme, Kacheln, Detailansichten, Einstellungen …)
  assets/fonts/        Jost (SIL Open Font License)
deploy/                install.sh, start.sh, systemd-Dienst für den Betrieb ohne Desktop
tools/screenshots.py   Screenshots ohne Bildschirm erzeugen (auch QML-Ladeprüfung)
tests/                 pytest: Backends, Manager, Einstellungen, Qt-Controller, QML
```

## Entwicklung

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q                     # inkl. Qt-Tests ohne Bildschirm
python tools/screenshots.py /tmp/shots  # Screenshots aller Ansichten, hell und dunkel
```

## Hinweise

- **Sicherheit**: Im Insecure-Modus kann jeder im Heimnetz mit der PIN auf Homebridge zugreifen.
- **Native HomeKit-Geräte ohne Homebridge** (z. B. Eve) brauchen ein verschlüsseltes HAP-Pairing; das ist
  nicht enthalten. Solche Geräte über ein Homebridge-Plugin einbinden.
- Fremde Änderungen (z. B. per Home-App) erscheinen nach spätestens 5 s, eigene Befehle sofort.
- Auf dem Pi zeichnet Qt Linien und Bögen mit dem GPU-Kurvenrenderer; auf sehr alten Modellen ohne
  OpenGL ES 3 kann `QT_QUICK_BACKEND=software` gesetzt werden.
