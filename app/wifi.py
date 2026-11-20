"""Wi-Fi for guests: the network the panel is connected to (or one set in the settings) as a QR
code that phone cameras understand ("WIFI:T:WPA;S:<name>;P:<password>;;").

The current network and its password come from NetworkManager (`nmcli`, Raspberry Pi OS
Bookworm and later). Reading the password needs the permission to read connection secrets,
which the user of a desktop session has; otherwise it can be entered in the settings. Older
systems without NetworkManager: name from `iwgetid`, password from wpa_supplicant.conf when
that file is readable.
"""
from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

Run = Callable[[list[str]], str]        # runs a command, returns its output; raises OSError / CalledProcessError

WPA_SUPPLICANT = Path("/etc/wpa_supplicant/wpa_supplicant.conf")


class WifiError(Exception):
    pass


@dataclass
class Wifi:
    ssid: str
    password: str = ""
    security: str = "WPA"           # WPA (also WPA2/WPA3), WEP or nopass
    hidden: bool = False

    def uri(self) -> str:
        """Text of the QR code; \\ ; , : " are escaped as the format asks."""
        def esc(s: str) -> str:
            return re.sub(r'([\\;,:"])', r"\\\1", s)
        parts = [f"T:{self.security}", f"S:{esc(self.ssid)}"]
        if self.security != "nopass":
            parts.append(f"P:{esc(self.password)}")
        if self.hidden:
            parts.append("H:true")
        return "WIFI:" + ";".join(parts) + ";;"


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True).stdout


def _split_terse(line: str) -> list[str]:
    """Splits a line of `nmcli -t` at the colons that are not escaped."""
    out, cur, esc = [], "", False
    for ch in line:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            out.append(cur)
            cur = ""
        else:
            cur += ch
    return out + [cur]


def _nmcli(run: Run) -> Wifi | None:
    """The active Wi-Fi connection of NetworkManager; None without NetworkManager or Wi-Fi."""
    try:
        active = run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"])
    except (OSError, subprocess.SubprocessError):     # no NetworkManager, or it is not running
        return None
    name = next((f[0] for f in map(_split_terse, active.splitlines()) if len(f) >= 2 and f[1] == "802-11-wireless"), None)
    if name is None:
        return None

    def get(prop: str, secret: bool = False) -> str:
        cmd = ["nmcli", "--escape", "no"] + (["-s"] if secret else []) + ["-g", prop, "connection", "show", "id", name]
        try:
            return run(cmd).strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    ssid = get("802-11-wireless.ssid") or name
    mgmt = get("802-11-wireless-security.key-mgmt")
    hidden = get("802-11-wireless.hidden") == "yes"
    if not mgmt or mgmt == "owe":                      # open network (also "enhanced open")
        return Wifi(ssid, security="nopass", hidden=hidden)
    if mgmt == "none":                                 # static WEP
        return Wifi(ssid, get("802-11-wireless-security.wep-key0", secret=True), "WEP", hidden)
    return Wifi(ssid, get("802-11-wireless-security.psk", secret=True), "WPA", hidden)


def _legacy(run: Run, conf: Path) -> Wifi | None:
    """Without NetworkManager: name from iwgetid, password from wpa_supplicant.conf."""
    try:
        ssid = run(["iwgetid", "-r"]).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if not ssid:
        return None
    try:
        text = conf.read_text()
    except OSError:
        return Wifi(ssid)
    for block in re.findall(r"network\s*=\s*\{(.*?)\}", text, re.S):
        if re.search(r'^\s*ssid\s*=\s*"' + re.escape(ssid) + r'"\s*$', block, re.M):
            if re.search(r"^\s*key_mgmt\s*=\s*NONE\s*$", block, re.M):
                return Wifi(ssid, security="nopass")
            psk = re.search(r'^\s*psk\s*=\s*"(.*)"\s*$', block, re.M)
            return Wifi(ssid, psk.group(1) if psk else "")
    return Wifi(ssid)


def current_wifi(run: Run = _run, conf: Path = WPA_SUPPLICANT) -> Wifi | None:
    """The Wi-Fi the panel is connected to (password "" if it cannot be read); None without Wi-Fi."""
    found = _nmcli(run)
    return found if found is not None else _legacy(run, conf)


def guest_wifi(ssid: str, password: str, run: Run = _run, conf: Path = WPA_SUPPLICANT) -> Wifi:
    """The network for the QR code: the one from the settings, else the current one. A password
    from the settings also fills in the one of the current network if that cannot be read."""
    ssid = ssid.strip()
    if ssid:
        return Wifi(ssid, password, "WPA" if password else "nopass")
    wifi = current_wifi(run, conf)
    if wifi is None:
        raise WifiError("no Wi-Fi")
    if wifi.security != "nopass" and not wifi.password:
        if not password:
            raise WifiError("password unknown")
        wifi.password = password
    return wifi


def qr_image(text: str) -> str:
    """The QR code as a PNG data URI, one pixel per module with the quiet zone (scale it up
    without smoothing)."""
    import segno
    return segno.make(text, error="m").png_data_uri(scale=1, border=4, dark="#000000", light="#ffffff")
