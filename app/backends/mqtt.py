"""MQTT client: virtual devices show the last value received on a topic (read-only).

paho-mqtt runs its own network thread; received values are kept here and the device
manager is told to refresh this backend at once, so new values appear without waiting
for the next poll.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any

from ..config import MqttConfig, VirtualDevice
from ..hap_types import Char, ServiceSnapshot
from ..i18n import tr
from .base import Backend, BackendError

log = logging.getLogger(__name__)


def extract(payload: str, json_key: str) -> Any:
    """Value of a payload: a number if it is one, the text otherwise; json_key picks a
    field of a JSON payload ("a.b" for nested objects). None if the key is missing."""
    value: Any = payload.strip()
    if json_key:
        try:
            value = json.loads(payload)
        except ValueError:
            return None
        for part in json_key.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return value
    return json.dumps(value)


def make_client(cfg: MqttConfig):
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"smarthome-panel-{secrets.token_hex(3)}",
                         transport="websockets" if cfg.protocol == "websocket" else "tcp")
    if cfg.protocol == "tls":
        client.tls_set()
    if cfg.username:
        client.username_pw_set(cfg.username, cfg.password or None)
    return client


class MqttBackend(Backend):
    def __init__(self, cfg: MqttConfig, devices: list[VirtualDevice]):
        super().__init__(cfg.name)
        self.cfg = cfg
        self.devices = {d.id: d for d in devices}
        self.payloads: dict[str, str] = {}          # topic -> last payload
        self.received: dict[str, float] = {}        # topic -> time received
        self.changed: Callable[[], None] | None = None   # set by the device manager
        self._client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connected = threading.Event()
        self._error = ""

    # ---------- paho callbacks (network thread) ----------
    def _on_connect(self, client, userdata, flags, reason, properties=None) -> None:  # noqa: ANN001
        if reason.is_failure:
            self._error = str(reason)
            return
        self._error = ""
        for topic in {d.topic for d in self.devices.values()}:
            client.subscribe(topic)
        self._connected.set()
        self._notify()

    def _on_disconnect(self, client, userdata, flags, reason, properties=None) -> None:  # noqa: ANN001
        self._connected.clear()
        self._error = str(reason)
        self._notify()

    def _on_message(self, client, userdata, msg) -> None:  # noqa: ANN001
        self.receive(msg.topic, msg.payload.decode("utf-8", errors="replace"))

    def receive(self, topic: str, payload: str) -> None:
        self.payloads[topic] = payload
        self.received[topic] = time.time()
        self._notify()

    def _notify(self) -> None:
        if self.changed and self._loop:
            self._loop.call_soon_threadsafe(self.changed)

    # ---------- backend ----------
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        try:
            client = make_client(self.cfg)
        except Exception as e:  # pragma: no cover - TLS setup on unusual systems
            self._error = str(e)
            return
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_message = self._on_message
        client.reconnect_delay_set(1, 30)
        try:
            client.connect_async(self.cfg.host, self.cfg.port, keepalive=30)
            client.loop_start()
        except Exception as e:
            self._error = str(e)
            return
        self._client = client
        # give the first connection a moment, so the first fetch already has the devices
        await asyncio.to_thread(self._connected.wait, min(self.cfg.timeout, 3.0))

    async def stop(self) -> None:
        self.changed = None                 # no refresh for our own disconnect
        if self._client:
            self._client.disconnect()
            self._client.loop_stop()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def value(self, device: VirtualDevice) -> Any:
        payload = self.payloads.get(device.topic)
        return None if payload is None else extract(payload, device.json_key)

    async def fetch(self) -> list[ServiceSnapshot]:
        if not self.connected:
            raise BackendError(tr("MQTT broker {host}:{port} not reachable: {error}").format(
                host=self.cfg.host, port=self.cfg.port, error=self._error or tr("no connection")))
        snaps = []
        for d in self.devices.values():
            chars = {
                "Value": Char(name="Value", value=self.value(d), writable=False, ref=(d.id, "Value")),
                "Unit": Char(name="Unit", value=d.unit, writable=False, ref=(d.id, "Unit")),
                "Decimals": Char(name="Decimals", value=d.decimals, writable=False, ref=(d.id, "Decimals")),
                "Icon": Char(name="Icon", value=d.icon, writable=False, ref=(d.id, "Icon")),
            }
            snaps.append(ServiceSnapshot(key=d.id, service_type="Value", name=d.name, chars=chars, accessory=d.topic))
        return snaps

    async def write(self, writes: list[tuple[Char, Any]]) -> None:
        raise BackendError(tr("Virtual devices only show values"))


async def test_connection(cfg: MqttConfig) -> tuple[bool, str]:
    """Connects once with the given settings; (ok, message) for the settings page."""
    done = threading.Event()
    result: dict[str, Any] = {}

    def on_connect(client, userdata, flags, reason, properties=None):  # noqa: ANN001
        result["reason"] = reason
        done.set()

    try:
        client = make_client(cfg)
        client.on_connect = on_connect
        client.connect_async(cfg.host, cfg.port, keepalive=10)
        client.loop_start()
    except Exception as e:
        return False, tr("Connection failed: {error}").format(error=e)
    try:
        ok = await asyncio.to_thread(done.wait, cfg.timeout)
    finally:
        client.disconnect()
        client.loop_stop()
    if not ok:
        return False, tr("MQTT broker {host}:{port} not reachable: {error}").format(
            host=cfg.host, port=cfg.port, error=tr("no answer"))
    reason = result["reason"]
    if reason.is_failure:
        return False, tr("MQTT broker refused the connection: {error}").format(error=reason)
    return True, tr("Connected to the MQTT broker {host}:{port}").format(host=cfg.host, port=cfg.port)
