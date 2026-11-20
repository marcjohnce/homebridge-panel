"""Wi-Fi for guests: reading the current network (NetworkManager, wpa_supplicant) and the QR code."""
import base64
import subprocess

import pytest

from app.wifi import Wifi, WifiError, current_wifi, guest_wifi, qr_image


def nmcli(active: str, props: dict[str, str], secrets: bool = True):
    """A fake `nmcli`: the active connections and the properties of one; secrets only if allowed."""
    calls = []

    def run(cmd):
        calls.append(cmd)
        if cmd[0] != "nmcli":
            raise FileNotFoundError(cmd[0])
        if "--active" in cmd:
            return active
        prop = cmd[cmd.index("-g") + 1]
        if "-s" in cmd and not secrets:
            return ""
        return props.get(prop, "") + "\n"
    run.calls = calls
    return run


def test_uri_escapes_special_characters():
    assert Wifi("Home", "pass").uri() == "WIFI:T:WPA;S:Home;P:pass;;"
    assert Wifi('My;Net:"x"', r"a\b,c").uri() == r'WIFI:T:WPA;S:My\;Net\:\"x\";P:a\\b\,c;;'
    assert Wifi("Cafe", security="nopass", hidden=True).uri() == "WIFI:T:nopass;S:Cafe;H:true;;"


def test_networkmanager_wpa_with_secret():
    run = nmcli("Wired connection 1:802-3-ethernet\nHome\\:Net:802-11-wireless\nlo:loopback\n",
                {"802-11-wireless.ssid": "Home:Net", "802-11-wireless-security.key-mgmt": "wpa-psk",
                 "802-11-wireless-security.psk": "s3cret;pw", "802-11-wireless.hidden": "no"})
    assert current_wifi(run) == Wifi("Home:Net", "s3cret;pw", "WPA", False)
    # the escaped connection name is passed on unescaped, the secret only with -s
    psk_call = next(c for c in run.calls if "802-11-wireless-security.psk" in c)
    assert psk_call[-1] == "Home:Net" and "-s" in psk_call and "--escape" in psk_call


def test_networkmanager_open_wep_and_unreadable_secret(tmp_path):
    assert current_wifi(nmcli("Cafe:802-11-wireless\n", {"802-11-wireless.ssid": "Cafe"})) == Wifi("Cafe", security="nopass")
    wep = nmcli("Old:802-11-wireless\n", {"802-11-wireless.ssid": "Old", "802-11-wireless-security.key-mgmt": "none",
                                         "802-11-wireless-security.wep-key0": "abcde"})
    assert current_wifi(wep) == Wifi("Old", "abcde", "WEP")
    locked = nmcli("Home:802-11-wireless\n", {"802-11-wireless.ssid": "Home",
                                              "802-11-wireless-security.key-mgmt": "sae"}, secrets=False)
    assert current_wifi(locked) == Wifi("Home", "", "WPA")
    with pytest.raises(WifiError, match="password unknown"):
        guest_wifi("", "", locked)
    assert guest_wifi("", "typed-in", locked) == Wifi("Home", "typed-in", "WPA")     # password from the settings
    assert current_wifi(nmcli("eth:802-3-ethernet\n", {}), conf=tmp_path / "none") is None    # cable only


def test_network_from_the_settings_wins():
    never = nmcli("Home:802-11-wireless\n", {})
    assert guest_wifi(" Guests ", "welcome", never) == Wifi("Guests", "welcome", "WPA")
    assert guest_wifi("Guests", "", never) == Wifi("Guests", security="nopass")
    assert never.calls == []


def test_without_networkmanager_reads_wpa_supplicant(tmp_path):
    conf = tmp_path / "wpa_supplicant.conf"
    conf.write_text('country=DE\nnetwork={\n\tssid="Other"\n\tpsk="nope"\n}\n'
                    'network={\n\tssid="Home"\n\tpsk="secret pw"\n\tkey_mgmt=WPA-PSK\n}\n')

    def run(cmd):
        if cmd[0] == "nmcli":
            raise FileNotFoundError("nmcli")
        return "Home\n"
    assert current_wifi(run, conf) == Wifi("Home", "secret pw")
    assert current_wifi(run, tmp_path / "unreadable") == Wifi("Home")         # name only

    def no_wifi(cmd):
        raise subprocess.CalledProcessError(255, cmd)
    with pytest.raises(WifiError, match="no Wi-Fi"):
        guest_wifi("", "x", no_wifi, conf)


def test_qr_image_is_a_png():
    uri = qr_image(Wifi("Home", "secret").uri())
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"
