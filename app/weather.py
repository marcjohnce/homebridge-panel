"""Weather from Open-Meteo (open-meteo.com): current weather and 7-day forecast for the places
set in the settings, place search by name. Free, no API key; data under CC BY 4.0, so the
weather view names the source.

Places are kept in settings.json (so they are part of backups and of the settings shared over
MQTT); the place marked as default is the one shown on the screen saver:

    "weather_places": [{"id": "w1a2b3", "name": "Berlin", "lat": 52.52, "lon": 13.41, "default": true}]
"""
from __future__ import annotations

import math
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SEARCH_URL = "https://geocoding-api.open-meteo.com/v1/search"
TIMEOUT = 15.0
DAYS = 7
MAX_PLACE_NAME = 24

# WMO weather code -> kind (icon) and the text shown; texts are translated in i18n_catalog
KINDS: dict[int, tuple[str, str]] = {
    0: ("clear", "Clear"),
    1: ("clear", "Mainly clear"),
    2: ("partly", "Partly cloudy"),
    3: ("cloud", "Overcast"),
    45: ("fog", "Fog"), 48: ("fog", "Fog"),
    51: ("drizzle", "Light drizzle"), 53: ("drizzle", "Drizzle"), 55: ("drizzle", "Heavy drizzle"),
    56: ("sleet", "Freezing drizzle"), 57: ("sleet", "Freezing drizzle"),
    61: ("rain", "Light rain"), 63: ("rain", "Rain"), 65: ("rain", "Heavy rain"),
    66: ("sleet", "Freezing rain"), 67: ("sleet", "Freezing rain"),
    71: ("snow", "Light snow"), 73: ("snow", "Snow"), 75: ("snow", "Heavy snow"), 77: ("snow", "Snow grains"),
    80: ("showers", "Light showers"), 81: ("showers", "Showers"), 82: ("showers", "Heavy showers"),
    85: ("snow", "Snow showers"), 86: ("snow", "Snow showers"),
    95: ("thunder", "Thunderstorm"), 96: ("thunder", "Thunderstorm with hail"), 99: ("thunder", "Thunderstorm with hail"),
}


def describe(code: Any) -> tuple[str, str]:
    """(kind, English text) for a WMO code; the kind names the icon (Icons.js), except "clear"
    (sun or moon) and "partly" (sun behind a cloud). Unknown codes count as overcast."""
    try:
        return KINDS[int(code)]
    except (TypeError, ValueError, KeyError):
        return ("cloud", "Overcast")


class WeatherError(Exception):
    pass


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None


def parse_forecast(data: dict[str, Any]) -> dict[str, Any]:
    """The answer of /v1/forecast as {current: {temp, feels, humidity, wind, code, day},
    days: [{date: "YYYY-MM-DD", code, max, min, rain_chance, rain}]}."""
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    if "temperature_2m" not in cur or not daily.get("time"):
        raise WeatherError("unexpected answer")
    current = {"temp": _num(cur.get("temperature_2m")), "feels": _num(cur.get("apparent_temperature")),
               "humidity": _num(cur.get("relative_humidity_2m")), "wind": _num(cur.get("wind_speed_10m")),
               "code": int(cur.get("weather_code") or 0), "day": bool(cur.get("is_day", 1))}

    def col(key: str, i: int) -> Any:
        values = daily.get(key) or []
        return values[i] if i < len(values) else None

    days = [{"date": d, "code": int(col("weather_code", i) or 0), "max": _num(col("temperature_2m_max", i)),
             "min": _num(col("temperature_2m_min", i)), "rain_chance": _num(col("precipitation_probability_max", i)),
             "rain": _num(col("precipitation_sum", i))} for i, d in enumerate(daily["time"][:DAYS])]
    return {"current": current, "days": days}


async def fetch(lat: float, lon: float, client: httpx.AsyncClient | None = None) -> dict[str, Any]:
    params = {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "timezone": "auto", "forecast_days": DAYS,
              "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,wind_speed_10m",
              "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum"}
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)
    try:
        r = await client.get(FORECAST_URL, params=params)
        if r.status_code != 200:
            raise WeatherError(f"HTTP {r.status_code}")
        return parse_forecast(r.json())
    except httpx.HTTPError as e:
        raise WeatherError(str(e) or type(e).__name__) from e
    except ValueError as e:
        raise WeatherError("unexpected answer") from e
    finally:
        if own:
            await client.aclose()


async def search(name: str, language: str = "en", client: httpx.AsyncClient | None = None) -> list[dict[str, Any]]:
    """Places matching a name: [{name, region, lat, lon}], best first (at most 8)."""
    own = client is None
    client = client or httpx.AsyncClient(timeout=TIMEOUT)
    try:
        r = await client.get(SEARCH_URL, params={"name": name, "count": 8, "language": language, "format": "json"})
        if r.status_code != 200:
            raise WeatherError(f"HTTP {r.status_code}")
        out = []
        for p in r.json().get("results") or []:
            if _num(p.get("latitude")) is None or _num(p.get("longitude")) is None:
                continue
            region = ", ".join(x for x in (p.get("admin1"), p.get("country")) if x and x != p.get("name"))
            out.append({"name": str(p.get("name", "")), "region": region,
                        "lat": round(float(p["latitude"]), 4), "lon": round(float(p["longitude"]), 4)})
        return out
    except httpx.HTTPError as e:
        raise WeatherError(str(e) or type(e).__name__) from e
    except ValueError as e:
        raise WeatherError("unexpected answer") from e
    finally:
        if own:
            await client.aclose()


_COORDS = re.compile(r"^\s*(-?\d{1,2}(?:[.,]\d+)?)\s*[;,/ ]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$")


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """"52.52, 13.41" or "52,52; 13,41" -> (lat, lon); None if it is not a valid pair."""
    m = _COORDS.match(text)
    if not m:
        # "52,52, 13,41": decimal commas and a comma between
        parts = [p.strip() for p in re.split(r",\s+|;", text)]
        if len(parts) != 2:
            return None
        m = _COORDS.match(" ".join(parts))
        if not m:
            return None
    lat, lon = (float(g.replace(",", ".")) for g in m.groups())
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 4), round(lon, 4)


def new_id(taken: set[str]) -> str:
    while True:
        wid = "w" + secrets.token_hex(3)
        if wid not in taken:
            return wid


def clean(places: Any) -> list[dict[str, Any]]:
    """Valid places of settings.json; exactly one is the default (the first, if none is)."""
    out = []
    for p in places if isinstance(places, list) else []:
        if not (isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("name"), str)
                and _num(p.get("lat")) is not None and _num(p.get("lon")) is not None):
            continue
        out.append({"id": p["id"], "name": p["name"], "lat": float(p["lat"]), "lon": float(p["lon"]),
                    "default": p.get("default") is True})
    defaults = [p for p in out if p["default"]]
    for p in defaults[1:]:
        p["default"] = False
    if out and not defaults:
        out[0]["default"] = True
    return out


def demo(lat: float, lon: float, today: date | None = None) -> dict[str, Any]:
    """Made-up weather for the demo and the screenshots: the same for the same place and day."""
    today = today or datetime.now().date()
    seed = int(abs(lat * 1000 + lon * 7)) + today.toordinal()
    codes = [2, 61, 3, 0, 80, 1, 71, 95, 2, 45]
    base = 8 - abs(lat - 45) / 6
    days = []
    for i in range(DAYS):
        code = codes[(seed + i * 3) % len(codes)]
        hi = round(base + ((seed + i * 5) % 9) - 3, 1)
        days.append({"date": (today + timedelta(days=i)).isoformat(), "code": code, "max": hi,
                     "min": round(hi - 4 - (seed + i) % 4, 1),
                     "rain_chance": float((seed * 7 + i * 13) % 90 if code >= 51 else (seed + i) % 20),
                     "rain": round(((seed + i) % 7) * 0.8, 1) if code >= 51 else 0.0})
    return {"current": {"temp": round(days[0]["max"] - 1.5, 1), "feels": round(days[0]["max"] - 4, 1),
                        "humidity": 78.0, "wind": 14.0, "code": days[0]["code"], "day": 7 <= datetime.now().hour < 19},
            "days": days}
