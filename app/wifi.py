"""Wi-Fi for guests: the guest network set in the settings as a QR code that phone cameras
understand ("WIFI:T:WPA;S:<name>;P:<password>;;")."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Wifi:
    ssid: str
    password: str = ""

    @property
    def security(self) -> str:
        return "WPA" if self.password else "nopass"     # WPA also stands for WPA2/WPA3

    def uri(self) -> str:
        """Text of the QR code; \\ ; , : " are escaped as the format asks."""
        def esc(s: str) -> str:
            return re.sub(r'([\\;,:"])', r"\\\1", s)
        parts = [f"T:{self.security}", f"S:{esc(self.ssid)}"]
        if self.password:
            parts.append(f"P:{esc(self.password)}")
        return "WIFI:" + ";".join(parts) + ";;"


def qr_image(text: str) -> str:
    """The QR code as a PNG data URI, one pixel per module with the quiet zone (scale it up
    without smoothing)."""
    import segno
    return segno.make(text, error="m").png_data_uri(scale=1, border=4, dark="#000000", light="#ffffff")
