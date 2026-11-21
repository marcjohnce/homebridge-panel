"""Sharing the settings between panels through the MQTT broker (Settings → System → Backups).

Saving and loading are done by hand: a panel saves its shared settings as one retained message,
another panel loads them when asked to. Nothing is synchronised in the background, so nothing
is overwritten unnoticed.

    topic smarthome-panel/shared, retained:
    {"smarthome_panel_shared": 1, "saved": "2026-11-21T12:00:00+01:00", "panel": "Kitchen",
     "version": "0.0.4", "settings": {… the shared part of settings.json …}}

Shared: rooms and their order, display names, kinds, menu areas, hidden devices, "No alerts",
light and switch groups, virtual devices and the Homebridge address. Each panel keeps its own
favorites, display settings, MQTT connection and – as anyone with access to the broker could
read them – the PINs and passwords.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from typing import Any

from .config import MqttConfig

TOPIC = "smarthome-panel/shared"
FORMAT = 1
SHARED_VALUES = ("show_general", "wifi_ssid", "hap_enabled", "hap_host", "hap_port")
SHARED_LISTS = ("virtual", "groups", "switch_groups")
LOCAL_ROOM_KEYS = ("favorites",)


class ShareError(Exception):
    pass


def _wait(timeout: float, *events: threading.Event) -> None:
    """Waits until one of the events is set or the time is up."""
    step = 0.02
    while timeout > 0 and not any(e.is_set() for e in events):
        threading.Event().wait(step)
        timeout -= step


def shared_part(settings: dict[str, Any]) -> dict[str, Any]:
    """The part of settings.json that is shared."""
    out: dict[str, Any] = {k: settings[k] for k in SHARED_VALUES if k in settings}
    rooms = settings.get("rooms") if isinstance(settings.get("rooms"), dict) else {}
    out["rooms"] = {k: v for k, v in rooms.items() if k not in LOCAL_ROOM_KEYS}
    for k in SHARED_LISTS:
        out[k] = settings.get(k) if isinstance(settings.get(k), list) else []
    return out


def merge(local: dict[str, Any], shared: dict[str, Any]) -> dict[str, Any]:
    """The local settings with the shared part of another panel; the local favorites stay."""
    out = dict(local)
    for k in SHARED_VALUES:
        if k in shared:
            out[k] = shared[k]
    for k in SHARED_LISTS:
        if isinstance(shared.get(k), list):
            out[k] = shared[k]
    rooms = shared.get("rooms") if isinstance(shared.get("rooms"), dict) else {}
    own = local.get("rooms") if isinstance(local.get("rooms"), dict) else {}
    out["rooms"] = {**{k: v for k, v in rooms.items() if k not in LOCAL_ROOM_KEYS},
                    **{k: own[k] for k in LOCAL_ROOM_KEYS if k in own}}
    return out


def payload(settings: dict[str, Any], panel: str, version: str) -> dict[str, Any]:
    return {"smarthome_panel_shared": FORMAT, "saved": datetime.now().astimezone().isoformat(),
            "panel": panel, "version": version, "settings": shared_part(settings)}


def _client(cfg: MqttConfig):
    from .backends.mqtt import make_client
    return make_client(cfg)


def _connect(cfg: MqttConfig, client, on_ready) -> threading.Event:   # noqa: ANN001
    """Connects; on_ready runs once connected. Returns the event set when it failed."""
    failed = threading.Event()
    client.failure = None

    def on_connect(c, userdata, flags, reason, properties=None):  # noqa: ANN001
        if reason.is_failure:
            client.failure = str(reason)
            failed.set()
        else:
            on_ready()

    client.on_connect = on_connect
    try:
        client.connect_async(cfg.host, cfg.port, keepalive=10)
        client.loop_start()
    except Exception as e:      # noqa: BLE001 – bad host names and the like
        raise ShareError(str(e)) from e
    return failed


def save(cfg: MqttConfig, data: dict[str, Any]) -> None:
    """Publishes the shared settings as a retained message."""
    client = _client(cfg)
    done = threading.Event()
    result: dict[str, Any] = {}

    def ready():
        info = client.publish(TOPIC, json.dumps(data, ensure_ascii=False), qos=1, retain=True)
        result["info"] = info
        done.set()

    failed = _connect(cfg, client, ready)
    try:
        _wait(cfg.timeout, done, failed)
        if failed.is_set():
            raise ShareError(client.failure or "refused")
        if not done.is_set():
            raise ShareError("no answer")
        info = result["info"]
        info.wait_for_publish(cfg.timeout)
        if not info.is_published():
            raise ShareError("not published")
    finally:
        client.disconnect()
        client.loop_stop()


def load(cfg: MqttConfig, wait: float = 1.5) -> dict[str, Any] | None:
    """The shared settings on the broker, None if nobody saved any yet."""
    client = _client(cfg)
    subscribed = threading.Event()
    got = threading.Event()
    result: dict[str, Any] = {}

    def on_message(c, userdata, msg):  # noqa: ANN001
        result["payload"] = msg.payload
        got.set()

    client.on_message = on_message
    client.on_subscribe = lambda *a, **k: subscribed.set()
    failed = _connect(cfg, client, lambda: client.subscribe(TOPIC, qos=1))
    try:
        _wait(cfg.timeout, subscribed, failed)
        if failed.is_set():
            raise ShareError(client.failure or "refused")
        if not subscribed.is_set():
            raise ShareError("no answer")
        if not got.wait(wait):          # the broker sends a retained message right after subscribing
            return None
    finally:
        client.disconnect()
        client.loop_stop()
    raw = result["payload"]
    if not raw:                         # an empty retained message deletes it
        return None
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise ShareError(f"not readable: {e}") from e
    if not (isinstance(data, dict) and data.get("smarthome_panel_shared") == FORMAT
            and isinstance(data.get("settings"), dict)):
        raise ShareError("not shared settings of the panel")
    return data
