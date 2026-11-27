import concurrent.futures
import json
import socket
import urllib.error
import urllib.request

from app.web import Pairing

from test_qt import collect_in_main_thread, make_controller, pump_until, qapp  # noqa: F401 (fixtures)


def test_pairing_codes_and_tokens(tmp_path):
    p = Pairing(tmp_path / "web_tokens.json")
    assert p.pair("123456") == ""                       # no code shown yet
    code = p.new_code(now=1000)
    assert p.pair(code, now=1000 + 301) == ""           # too old
    code = p.new_code(now=2000)
    for _ in range(5):
        assert p.pair("000000" if code != "000000" else "111111", now=2001) == ""
    assert p.pair(code, now=2001) == ""                 # void after five wrong tries
    code = p.new_code(now=3000)
    token = p.pair(code, now=3001)
    assert token and p.valid(token) and not p.valid("x")
    assert p.pair(code, now=3002) == ""                 # a code works once
    assert token not in (tmp_path / "web_tokens.json").read_text()      # only the hash is kept
    assert Pairing(tmp_path / "web_tokens.json").valid(token)
    p.forget()
    assert not Pairing(tmp_path / "web_tokens.json").valid(token)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_web_setup(qapp, tmp_path):
    """Off by default; on: the page, pairing with the code from the panel, then settings, rooms,
    devices, virtual devices, scenes and backups over the API. No secrets go out."""
    port = free_port()
    ctl = make_controller(tmp_path, alarm_pin="1234", web_port=port)
    ctl.start()
    assert pump_until(lambda: len(ctl.devices.all()) == 29)
    assert ctl.web.server is None
    assert "error" in ctl.web.newCode()
    ctl.settings.save({"web_enabled": True})
    assert ctl.web.server is not None and ctl.web.server.port == port
    base = f"http://127.0.0.1:{port}"
    pool = concurrent.futures.ThreadPoolExecutor(1)
    cookie = {"v": ""}

    def request(path, body=None, headers=None):
        def run():
            h = {"Cookie": cookie["v"], **({"Content-Type": "application/json", "X-Panel": "1"} if body is not None else {}),
                 **(headers or {})}
            req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status, r.headers, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.headers, e.read()
        fut = pool.submit(run)
        assert pump_until(fut.done, timeout=15)
        status, headers, data = fut.result()
        try:
            data = json.loads(data)
        except ValueError:
            pass
        return status, headers, data

    status, _, page = request("/")
    assert status == 200 and b"Smart Home Panel" in page
    status, _, data = request("/api/state")
    assert status == 401 and data["error"] == "pair" and data["t"]["connect"]
    assert request("/api/settings", {"changes": {"theme": "dark"}})[0] == 401
    paired = []
    ctl.web.paired.connect(lambda: paired.append(1))
    code = ctl.web.newCode()["code"].replace(" ", "")
    assert request("/api/pair", {"code": "999999" if code != "999999" else "111111"})[0] == 401
    status, headers, _ = request("/api/pair", {"code": code})
    assert status == 200 and paired == [1]
    cookie["v"] = headers["Set-Cookie"].split(";")[0]
    assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]

    status, _, state = request("/api/state")
    assert status == 200 and state["rooms"] and state["devices"]
    fields = {f["key"]: f for s in state["sections"] for f in s["fields"]}
    assert fields["alarm_pin"]["value"] == "" and fields["alarm_pin"]["isSet"]       # never sent out
    assert not any(k.startswith("web_") for k in fields) and "reboot" not in fields
    # a post without the panel's header (as another web site could send) is refused
    assert request("/api/settings", {"changes": {"theme": "dark"}}, {"X-Panel": "0"})[0] == 403

    status, _, data = request("/api/settings", {"changes": {"theme": "dark", "alarm_pin": "", "web_enabled": False}})
    assert status == 200 and ctl.store.get("theme") == "dark" and ctl.store.get("alarm_pin") == "1234"
    assert ctl.store.get("web_enabled") is True
    status, _, data = request("/api/settings", {"changes": {"hap_port": 0}})
    assert status == 400 and "hap_port" in data["errors"]

    assert request("/api/room", {"op": "add", "name": "Office"})[0] == 200 and "Office" in [r["name"] for r in ctl.roomEditor.rooms]
    status, _, data = request("/api/device", {"id": "demo:coffee", "values": {"room": "Office", "name": "Espresso", "favorite": True}})
    assert status == 200 and ctl.devices.get("demo:coffee")["room"] == "Office"
    assert ctl.devices.get("demo:coffee")["name"] == "Espresso" and ctl.devices.get("demo:coffee")["favorite"]

    status, _, data = request("/api/virtual", {"op": "save", "values": {"name": "Pressure", "topic": "boiler/p", "unit": "bar"}})
    assert status == 200 and [v["name"] for v in data["virtual"]] == ["Pressure"]

    status, _, data = request("/api/scene", {"op": "draft", "id": "", "room": "Office"})
    assert [d["id"] for d in data["draft"]["devices"]] == ["demo:coffee"]
    status, _, data = request("/api/scene", {"op": "save", "id": "", "name": "Morning", "room": "Office",
                                             "devices": {"demo:coffee": {"on": True}}})
    assert status == 200 and [s["name"] for s in data["scenes"]] == ["Morning"]

    status, _, data = request("/api/backup", {"op": "create"})
    assert status == 200 and len(data["backups"]) == 1

    assert ctl.web.pairing.hashes
    ctl.run_action("web_signout")                     # from the panel: every browser signed out
    assert not ctl.web.pairing.hashes and request("/api/state")[0] == 401
    ctl.settings.save({"web_enabled": False})
    assert ctl.web.server is None
    pool.shutdown()
    ctl.shutdown()
