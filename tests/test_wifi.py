"""Wi-Fi for guests: text and image of the QR code."""
import base64

from app.wifi import Wifi, qr_image


def test_uri_escapes_special_characters():
    assert Wifi("Home", "pass").uri() == "WIFI:T:WPA;S:Home;P:pass;;"
    assert Wifi('My;Net:"x"', r"a\b,c").uri() == r'WIFI:T:WPA;S:My\;Net\:\"x\";P:a\\b\,c;;'
    assert Wifi("Cafe").uri() == "WIFI:T:nopass;S:Cafe;;"          # open network


def test_qr_image_is_a_png():
    uri = qr_image(Wifi("Home", "secret").uri())
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1])[:8] == b"\x89PNG\r\n\x1a\n"
