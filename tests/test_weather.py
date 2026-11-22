import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app import weather

FORECAST = {
    "current": {"time": "2026-11-22T10:00", "temperature_2m": 7.6, "relative_humidity_2m": 81,
                "apparent_temperature": 4.9, "is_day": 1, "weather_code": 61, "wind_speed_10m": 17.3},
    "daily": {"time": [f"2026-11-{22 + i}" for i in range(7)],
              "weather_code": [61, 3, 2, 0, 71, 95, 45],
              "temperature_2m_max": [9.1, 8, 7, 6, 2, 11, 5], "temperature_2m_min": [4, 3, 2, 1, -3, 6, 0],
              "precipitation_probability_max": [80, 10, 5, 0, 60, 90, 20],
              "precipitation_sum": [4.2, 0, 0, 0, 2.1, 9.9, 0]},
}
SEARCH = {"results": [
    {"name": "Hamburg", "latitude": 53.55073, "longitude": 9.99302, "country": "Germany", "admin1": "Hamburg"},
    {"name": "Hamburg", "latitude": 42.71589, "longitude": -78.82948, "country": "United States", "admin1": "New York"},
]}


@pytest.fixture
def server(monkeypatch):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            seen.append((url.path, parse_qs(url.query)))
            body = json.dumps(FORECAST if url.path == "/v1/forecast" else SEARCH).encode()
            self.send_response(200 if "fail" not in self.path else 500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    monkeypatch.setattr(weather, "FORECAST_URL", base + "/v1/forecast")
    monkeypatch.setattr(weather, "SEARCH_URL", base + "/v1/search")
    yield base, seen
    srv.shutdown()


def test_fetch_and_search(server, monkeypatch):
    base, seen = server
    data = asyncio.run(weather.fetch(52.52, 13.41))
    assert data["current"] == {"temp": 7.6, "feels": 4.9, "humidity": 81.0, "wind": 17.3, "code": 61, "day": True}
    assert len(data["days"]) == 7 and data["days"][4] == \
        {"date": "2026-11-26", "code": 71, "max": 2.0, "min": -3.0, "rain_chance": 60.0, "rain": 2.1}
    q = seen[0][1]
    assert q["latitude"] == ["52.5200"] and q["timezone"] == ["auto"] and q["forecast_days"] == ["7"]
    assert "weather_code" in q["daily"][0] and "temperature_2m" in q["current"][0]

    found = asyncio.run(weather.search("Hamburg", "de"))
    assert found == [{"name": "Hamburg", "region": "Germany", "lat": 53.5507, "lon": 9.993},
                     {"name": "Hamburg", "region": "New York, United States", "lat": 42.7159, "lon": -78.8295}]
    assert seen[1][1]["language"] == ["de"]

    monkeypatch.setattr(weather, "FORECAST_URL", base + "/fail")
    with pytest.raises(weather.WeatherError):
        asyncio.run(weather.fetch(1, 2))


def test_codes_coordinates_and_places():
    assert weather.describe(0) == ("clear", "Clear") and weather.describe(95)[0] == "thunder"
    assert weather.describe(999) == ("cloud", "Overcast")
    assert weather.parse_coordinates("52.52, 13.41") == (52.52, 13.41)
    assert weather.parse_coordinates("52,52; 13,41") == (52.52, 13.41)
    assert weather.parse_coordinates("52,52, 13,41") == (52.52, 13.41)
    assert weather.parse_coordinates("-33.87 151.21") == (-33.87, 151.21)
    assert weather.parse_coordinates("Berlin") is None and weather.parse_coordinates("95, 10") is None
    places = weather.clean([{"id": "a", "name": "A", "lat": 1, "lon": 2}, {"id": "b", "name": "B", "lat": 3, "lon": 4},
                            "junk", {"id": "c", "name": "C", "lat": "x", "lon": 1}])
    assert [p["id"] for p in places] == ["a", "b"] and places[0]["default"] and not places[1]["default"]
    with pytest.raises(weather.WeatherError):
        weather.parse_forecast({"current": {}})
    demo = weather.demo(52.5, 13.4)
    assert len(demo["days"]) == 7 and demo == weather.demo(52.5, 13.4)


def test_every_weather_kind_has_an_icon():
    """A kind without an icon would show the light bulb that LineIcon falls back to."""
    from pathlib import Path
    icons = (Path(__file__).parent.parent / "app" / "qml" / "Icons.js").read_text(encoding="utf-8")
    for kind, _ in weather.KINDS.values():
        name = {"clear": "sun", "partly": "weather"}.get(kind, kind)
        assert f"\n    {name}:" in icons, kind
    assert "\n    moon:" in icons
