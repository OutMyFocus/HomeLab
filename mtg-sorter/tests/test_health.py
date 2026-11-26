"""The Machine health page and its JSON, with fake hardware (no Pi needed)."""

import json

import pytest

from app import Scanner, create_app
from mtgscanner import config, health, system
from mtgscanner.bin_sensors import BinSensors
from mtgscanner.machine import Machine
from mtgscanner.remote_machine import RemoteMachine
from test_machine import FakeKit, FakeMotor
from test_pi_docker import Wire
from test_scanner import db  # noqa: F401  (a fixture)


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "MACHINE_MODEL", "mk2")
    monkeypatch.setattr(system, "temperature", lambda: 47.5)
    monkeypatch.setattr(system, "throttled", lambda: 0x50000)   # under-voltage and slowed since it started
    monkeypatch.setattr(system, "supply_volts", lambda: 5.02)
    health.reset()
    return tmp_path


@pytest.fixture
def machine():
    m = Machine()
    m._kit, m._motor = FakeKit(), FakeMotor()
    return m


@pytest.fixture
def client(db, machine):  # noqa: F811
    return create_app(Scanner(db, None, source=None), machine).test_client()


def test_the_page_and_its_json_cover_every_part(client):
    assert client.get("/machine/health").status_code == 200
    r = client.get("/api/machine/health").get_json()
    for key in ("pi", "camera", "servos", "feeder", "bins", "lights", "scans", "events", "problems", "overall"):
        assert key in r
    assert r["pi"]["temperature_c"] == 47.5 and r["pi"]["supply_volts"] == 5.02
    assert "under-voltage since it started" in r["pi"]["throttled"]
    assert [s["part"] for s in r["servos"]] == ["stop", "push1", "door_f", "door_b", "push2"]
    assert r["feeder"]["pins"] == [17, 27]


def test_a_move_and_a_feeder_pulse_are_recorded(client, machine):
    client.post("/api/machine/move", json={"part": "stop", "position": "up"})
    client.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.6})
    r = client.get("/api/machine/health").get_json()
    stop = next(s for s in r["servos"] if s["part"] == "stop")
    assert stop["angle"] == config.SERVOS_MK2["stop"][1]["up"] and stop["last_move_at"]
    assert r["feeder"]["pulses"][0] | {"at": 0} == {"at": 0, "seconds": 0.05, "speed": 0.6, "direction": "forward"}
    assert r["counts"]["pulses"] == 1


def test_saved_angles_outside_the_safe_range_warn(client):
    client.post("/api/machine/save", json={"part": "push2", "position": "right", "angle": 176})
    r = client.get("/api/machine/health").get_json()
    push2 = next(s for s in r["servos"] if s["part"] == "push2")
    assert push2["warnings"] == ['"right" is saved at 176°, outside 10-170°']
    assert any("Level 2 pusher" in p["text"] and p["state"] == "warn" for p in r["problems"])


def test_jams_and_a_failed_run_show_as_problems(client):
    for result in ("landed", "stuck"):
        health.feed_result({"result": result, "landed_ms": None, "motor_ms": 500})
    health.drop_result({"bin": 3, "dropped": False, "drop_tries": 2})
    health.run_ended("a card is held in the slot: open the gate a little")
    r = client.get("/api/machine/health").get_json()
    assert r["overall"] == "bad"
    assert r["counts"]["jams"] == 2 and r["feeder"]["tally"] == {"landed": 1, "stuck": 1}
    texts = [e["text"] for e in r["events"]]
    assert "Feed: a card stuck in the slot" in texts
    assert any(t.startswith("Bin 3: the card was still on the bed") for t in texts)
    assert texts[0].startswith("Sort run ended")
    assert any(p["area"] == "feeder" and p["state"] == "bad" for p in r["problems"])


def test_bin_sensors_are_not_connected_until_fitted(data):
    opened = []

    class Pin:
        def __init__(self, pin):
            opened.append(pin)
            self.is_active = pin == 20     # bin 2's sensor sees cards (its pin is low)
    sensors = BinSensors(make_input=Pin)
    s = sensors.read()
    assert not opened and all(b["full"] is None and b["seated"] is None for b in s["bins"])
    sensors.set_fitted("full", True)
    s = sensors.read()
    assert {b["bin"]: b["full"] for b in s["bins"]} == {1: False, 2: True, 3: False, 4: False}
    assert all(b["seated"] is None for b in s["bins"])        # the hall sensors still aren't fitted
    assert json.loads((data / "bin_sensors.json").read_text()) == {"full": True, "seated": False}
    _, problems = health.sensors_part(sensors)
    assert [p["text"] for p in problems] == ["Bin 2 is full."]


def test_the_sensor_switch_is_saved_from_the_page(client):
    r = client.post("/api/machine/health/sensors", json={"kind": "full", "fitted": True}).get_json()
    assert r["bins"]["fitted"] == {"full": True, "seated": False}
    assert client.post("/api/machine/health/sensors", json={"kind": "nope", "fitted": True}).status_code == 400


def test_the_report_downloads_as_a_file(client):
    r = client.get("/api/machine/health?download=1")
    assert r.headers["Content-Disposition"].startswith('attachment; filename="sortr-health-')


def test_the_server_shows_the_pis_health(db, machine):  # noqa: F811
    pi_client = create_app(Scanner(db, None, source=None), machine).test_client()
    pi_client.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.5})
    remote = RemoteMachine("http://10.0.0.247:5000", key="")
    remote.http = Wire(pi_client)
    server = create_app(Scanner(db, None, source=None), remote).test_client()
    r = server.get("/api/machine/health").get_json()
    assert r["reachable"] and r["server"]["pi_url"] == "http://10.0.0.247:5000"
    assert r["counts"]["pulses"] == 1 and len(r["servos"]) == 5
    r = server.post("/api/machine/health/sensors", json={"kind": "seated", "fitted": True}).get_json()
    assert r["bins"]["fitted"]["seated"] is True


def test_an_unreachable_pi_still_answers(db):  # noqa: F811
    remote = RemoteMachine("http://10.0.0.247:5000")

    class Down:
        def get(self, *a, **k):
            import requests
            raise requests.ConnectionError("no route")
        post = get
    remote.http = Down()
    server = create_app(Scanner(db, None, source=None), remote).test_client()
    res = server.get("/api/machine/health")
    r = res.get_json()
    assert res.status_code == 200 and r["reachable"] is False and r["overall"] == "bad"
    assert "Can't reach the sorter's Pi" in r["problems"][0]["text"]


def test_a_full_bin_counts_only_when_every_reading_agrees(data):
    reads = {"n": 0}

    class Pin:
        def __init__(self, pin):
            self.pin = pin

        @property
        def is_active(self):
            if self.pin == 16:                 # bin 1's sensor sees a card for one reading only
                reads["n"] += 1
                return reads["n"] == 1
            return self.pin == 21              # bin 3 is full every time
    sensors = BinSensors(make_input=Pin)
    assert sensors.blocked(gap=0) == {"full": [], "out": []}      # nothing fitted: nothing blocks
    sensors.set_fitted("full", True)
    assert sensors.blocked(reads=3, gap=0) == {"full": [3], "out": []}


def test_the_sort_run_stops_before_feeding_when_a_bin_is_full(data, machine):
    from mtgscanner.sort_run import SortRun

    class Sensors:
        def __init__(self):
            self.answer = {"full": [], "out": []}

        def blocked(self):
            return self.answer

    class Watcher:
        fed = 0

        def sort_one(self, *a, **k):
            Watcher.fed += 1
            return {"result": "none"}
    sensors = Sensors()
    run = SortRun(Watcher(), None, machine, sensors)
    assert run._blocked_bins() is None
    sensors.answer = {"full": [2], "out": [4]}
    assert run._blocked_bins() == "bin 2 is full and bin 4 is out: empty or seat it, then press Start again"
    run.state["running"] = True
    run._run(1.0, 0)
    assert Watcher.fed == 0 and run.state["done"].startswith("bin 2 is full")
    assert SortRun(Watcher(), None, machine)._blocked_bins() is None     # no sensors: never blocked
