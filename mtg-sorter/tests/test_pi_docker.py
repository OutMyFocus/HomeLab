"""The Pi on the server's Docker image: the job bridge to the Pi, the server driving the
Pi's machine over the network, and the feeder's reverse switch."""

import json
import threading

import pytest

from app import Scanner, create_app
from mtgscanner import config, security, system
from mtgscanner.machine import Machine
from mtgscanner.remote_machine import KEY_HEADER, RemoteMachine
from test_machine import FakeKit, FakeMotor
from test_scanner import db  # noqa: F401  (a fixture)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(system, "UPDATE_STATUS", tmp_path / "update_status.json")
    monkeypatch.setattr(system, "ADMIN", str(tmp_path / "no-helper-here"))
    return tmp_path


def pi_machine():
    m = Machine()
    m._kit, m._motor = FakeKit(), FakeMotor()
    return m


# --- the feeder's direction ---------------------------------------------------------

def test_feeder_can_be_turned_around(db, data):  # noqa: F811
    m = pi_machine()
    client = create_app(Scanner(db, None, source=None), m).test_client()
    s = client.post("/api/machine/save", json={"reverse": True}).get_json()
    assert s["feeder_defaults"]["reverse"] is True
    client.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.5})
    assert m._motor.calls[0] == ("backward", 0.5)
    client.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.5, "backward": True})
    assert ("forward", 0.5) in m._motor.calls
    # Saving the usual push keeps the direction.
    s = client.post("/api/machine/save", json={"seconds": 0.8, "speed": 0.7}).get_json()
    assert s["feeder_defaults"] == {"seconds": 0.8, "speed": 0.7, "reverse": True}
    client.post("/api/machine/stop", json={})


# --- the job bridge (the app in Docker asking the Pi for root jobs) -------------------

def fake_host(data, answers):
    """Plays deploy/mtg-sorter-host: answers each request file once."""
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            for req in (data / "host").glob("req-*.json"):
                body = json.loads(req.read_text())
                req.unlink()
                ok, out = answers(body)
                (data / "host" / f"res-{req.stem[4:]}.json").write_text(json.dumps({"ok": ok, "out": out}))
            stop.wait(0.02)
    threading.Thread(target=loop, daemon=True).start()
    return stop


def test_jobs_go_to_the_pi_through_the_data_folder(data, monkeypatch):
    monkeypatch.setattr(system, "HOST_BRIDGE", True)
    assert not system.admin_installed()          # no data/host yet: the Pi isn't set up
    (data / "host").mkdir()
    assert system.admin_installed()
    seen = []
    stop = fake_host(data, lambda body: (seen.append(body) or True, "Saved Home"))
    try:
        assert system.admin("wifi-add", input="Home\nsecret99\n") == "Saved Home"
    finally:
        stop.set()
    assert seen == [{"args": ["wifi-add"], "input": "Home\nsecret99\n"}]
    assert not list((data / "host").iterdir())   # nothing (like a Wi-Fi password) left behind


def test_a_failed_job_says_why(data, monkeypatch):
    monkeypatch.setattr(system, "HOST_BRIDGE", True)
    (data / "host").mkdir()
    stop = fake_host(data, lambda body: (False, "No saved Wi-Fi network called Cafe"))
    try:
        with pytest.raises(RuntimeError, match="Cafe"):
            system.admin("wifi-forget", input="Cafe\n")
    finally:
        stop.set()


def test_nobody_answering_doesnt_hang(data, monkeypatch):
    monkeypatch.setattr(system, "HOST_BRIDGE", True)
    (data / "host").mkdir()
    with pytest.raises(RuntimeError, match="mtg-sorter-host"):
        system.admin("reboot", timeout=0.3)
    assert not list((data / "host").iterdir())


def test_the_pi_on_docker_reports_its_image(db, data, monkeypatch):  # noqa: F811
    monkeypatch.setattr(system, "IN_DOCKER", True)
    monkeypatch.setattr(system, "HOST_BRIDGE", True)
    monkeypatch.setattr(system, "git", lambda *a: None)
    monkeypatch.setenv("MTG_VERSION", "1aecd41bbbbbbb")
    monkeypatch.setattr(system, "auto_updates_on", lambda: True)
    client = create_app(Scanner(db, None, source=None), pi_machine()).test_client()
    updates = next(c for c in client.get("/api/system").get_json()["checks"] if c["id"] == "updates")
    assert updates["state"] == "ok" and "1aecd41" in updates["summary"] and "server" in updates["summary"]
    (data / "update_status.json").write_text(json.dumps({"result": "rolled back", "message": "Went back"}))
    updates = next(c for c in client.get("/api/system").get_json()["checks"] if c["id"] == "updates")
    assert updates["state"] == "warn" and updates["action"] == "update"


# --- the server driving the Pi's machine --------------------------------------------

TOWER = {"REMOTE_ADDR": "10.0.0.49"}   # requests reach the Pi from the server, not from itself


class Wire:
    """Stands in for the network: sends RemoteMachine's requests to a Flask test client."""

    def __init__(self, pi_client):
        self.pi = pi_client
        self.headers = []

    def _reply(self, res):
        class R:
            status_code = res.status_code
            def json(self): return res.get_json()
        return R()

    def get(self, url, headers=None, timeout=None):
        self.headers.append(headers)
        return self._reply(self.pi.get(url.split("5000", 1)[1], headers=headers, environ_base=TOWER))

    def post(self, url, json=None, headers=None, timeout=None):
        self.headers.append(headers)
        return self._reply(self.pi.post(url.split("5000", 1)[1], json=json, headers=headers, environ_base=TOWER))


@pytest.fixture
def pi(db, data):  # noqa: F811
    m = pi_machine()
    return m, create_app(Scanner(db, None, source=None), m).test_client()


def server_with(db, pi_client, key=""):  # noqa: F811
    remote = RemoteMachine("http://10.0.0.247:5000", key=key)
    remote.http = Wire(pi_client)
    return remote, create_app(Scanner(db, None, source=None), remote).test_client()


def test_the_servers_machine_page_moves_the_pi(db, pi):  # noqa: F811
    m, pi_client = pi
    _, server = server_with(db, pi_client)
    s = server.post("/api/machine/move", json={"part": "pins", "position": "down"}).get_json()
    channel, positions = config.SERVOS["pins"]
    assert m._kit.servo[channel].angle == positions["down"]
    assert s["remote"] == "http://10.0.0.247:5000" and s["servos"]["ok"]
    server.post("/api/machine/save", json={"part": "chute", "position": "left", "angle": 68})
    assert m.servos()["chute"][1]["left"] == 68          # saved on the Pi
    server.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.4})
    assert m._motor.calls[0] == ("forward", 0.4)
    server.post("/api/machine/stop", json={})
    assert server.post("/api/machine/move", json={"part": "nope", "position": "x"}).status_code == 400


def test_an_unreachable_pi_is_explained(db, data):  # noqa: F811
    remote = RemoteMachine("http://10.0.0.247:5000")

    class Down:
        def get(self, *a, **k):
            import requests
            raise requests.ConnectionError("no route")
        post = get
    remote.http = Down()
    server = create_app(Scanner(db, None, source=None), remote).test_client()
    s = server.get("/api/machine").get_json()
    assert not s["servos"]["ok"] and "Can't reach the sorter's Pi" in s["servos"]["error"]
    assert set(s["parts"]) == set(config.SERVOS)        # the page still draws
    res = server.post("/api/machine/move", json={"part": "pins", "position": "up"})
    assert res.status_code == 503 and "10.0.0.247" in res.get_json()["error"]


def test_a_locked_pi_lets_the_server_in_with_its_key(db, pi, data):  # noqa: F811
    m, pi_client = pi
    security.set_pin("4321")
    _, server = server_with(db, pi_client)
    res = server.post("/api/machine/move", json={"part": "pins", "position": "up"})
    assert res.status_code == 503 and "MTG_MACHINE_KEY" in res.get_json()["error"]
    (data / "machine_key").write_text("k" * 40 + "\n")
    _, server = server_with(db, pi_client, key="k" * 40)
    assert server.post("/api/machine/move", json={"part": "pins", "position": "up"}).status_code == 200
    # The key only opens the machine, nothing else.
    assert pi_client.get("/api/system", headers={KEY_HEADER: "k" * 40}, environ_base=TOWER).status_code == 401
    assert pi_client.get("/api/machine", headers={KEY_HEADER: "wrong"}, environ_base=TOWER).status_code == 401


def test_the_pi_can_switch_to_docker_from_the_maintenance_page(db, data, monkeypatch):  # noqa: F811
    client = create_app(Scanner(db, None, source=None), pi_machine()).test_client()
    monkeypatch.setattr(system, "ON_PI", False)
    assert client.post("/api/system/docker", json={"on": True}).status_code == 400
    monkeypatch.setattr(system, "ON_PI", True)
    jobs = []
    monkeypatch.setattr(system, "admin", lambda *a, **k: jobs.append(a) or "")
    r = client.post("/api/system/docker", json={"on": True}).get_json()
    assert jobs == [("docker", "on")] and "Docker image" in r["message"]


def test_wider_servo_travel(db, data):  # noqa: F811
    class Servo:
        angle, pulse = None, None
        def set_pulse_width_range(self, lo, hi): self.pulse = (lo, hi)
    m = pi_machine()
    m._kit.servo = [Servo() for _ in range(16)]
    client = create_app(Scanner(db, None, source=None), m).test_client()
    client.post("/api/machine/move", json={"channel": 2, "angle": 180})
    assert m._kit.servo[2].pulse == config.SERVO_PULSE
    s = client.post("/api/machine/save", json={"wide_travel": True}).get_json()
    assert s["wide_travel"] is True
    client.post("/api/machine/move", json={"channel": 2, "angle": 180})
    assert m._kit.servo[2].pulse == config.SERVO_PULSE_WIDE == (500, 2500)


def test_the_servers_lights_page_drives_the_pis_light_bars(db, pi, monkeypatch):  # noqa: F811
    from mtgscanner.remote_machine import RemoteLights
    _, pi_client = pi
    remote = RemoteLights("http://10.0.0.247:5000")
    remote.http = Wire(pi_client)
    server = create_app(Scanner(db, None, source=None), RemoteMachine("http://10.0.0.247:5000"), remote).test_client()
    s = server.get("/api/lights").get_json()
    assert s["remote"] == "http://10.0.0.247:5000" and "settings" in s and "effects" in s
    # A change made on the server lands in the Pi's settings file.
    s = server.post("/api/lights", json={"on": True, "count": 14, "color": "#ff8800"}).get_json()
    assert s["settings"]["count"] == 14 and s["settings"]["color"] == "#ff8800"
    assert pi_client.get("/api/lights").get_json()["settings"]["count"] == 14
    assert server.post("/api/lights/flash", json={"event": "saved"}).status_code == 200
    assert isinstance(server.get("/api/lights/preview").get_json()["colors"], list)
    assert server.post("/api/lights", json={"count": "lots"}).status_code == 400   # the Pi's complaint comes through
    # Turning SPI on asks the Pi's helper, which this test machine doesn't have.
    r = server.post("/api/lights/spi-on", json={})
    assert r.status_code == 503 and "helper" in r.get_json()["error"].lower()
    assert "sorter's Pi" in next(c for c in server.get("/api/system").get_json()["checks"] if c["id"] == "lights")["summary"]


def test_the_servers_lights_page_without_the_pi(db, data):  # noqa: F811
    from mtgscanner.remote_machine import RemoteLights
    remote = RemoteLights("http://10.0.0.247:5000")

    class Down:
        def get(self, *a, **k):
            import requests
            raise requests.ConnectionError("no route")
        post = get
    remote.http = Down()
    s = remote.state()
    assert not s["ok"] and "Can't reach the sorter's Pi" in s["error"] and "settings" in s
    assert remote.preview() == []
    remote.event("saved")   # never raises
