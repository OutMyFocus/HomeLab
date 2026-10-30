"""The Machine page's API, with fake hardware (no Pi needed)."""

import pytest

from app import Scanner, create_app
from mtgscanner import config
from mtgscanner.machine import Machine
from test_scanner import db  # noqa: F401  (a fixture)


class FakeServo:
    angle = None


class FakeKit:
    def __init__(self):
        self.servo = [FakeServo() for _ in range(16)]


class FakeMotor:
    def __init__(self):
        self.calls = []

    def forward(self, speed): self.calls.append(("forward", speed))
    def backward(self, speed): self.calls.append(("backward", speed))
    def stop(self): self.calls.append(("stop",))


@pytest.fixture
def machine():
    m = Machine()
    m._kit, m._motor = FakeKit(), FakeMotor()
    return m


@pytest.fixture
def client(db, machine):  # noqa: F811
    return create_app(Scanner(db, None, source=None), machine).test_client()


def test_named_positions_move_the_right_channel(client, machine):
    channel, positions = config.SERVOS["pins"]
    state = client.post("/api/machine/move", json={"part": "pins", "position": "down"}).get_json()
    assert machine._kit.servo[channel].angle == positions["down"]
    assert state["parts"]["pins"]["angle"] == positions["down"]


def test_slider_angles_are_kept_in_range(client, machine):
    client.post("/api/machine/move", json={"channel": 2, "angle": 250})
    assert machine._kit.servo[2].angle == 180
    assert client.post("/api/machine/move", json={"channel": 16, "angle": 90}).status_code == 400
    assert client.post("/api/machine/move", json={"part": "nope", "position": "up"}).status_code == 400


def test_relax_lets_go_of_every_servo(client, machine):
    client.post("/api/machine/move", json={"channel": 0, "angle": 90})
    client.post("/api/machine/relax", json={})
    assert machine._kit.servo[0].angle is None


def test_feeder_runs_then_stops(client, machine):
    state = client.post("/api/machine/feed", json={"seconds": 0.05, "speed": 0.5}).get_json()
    assert state["feeder"]["running"]
    assert machine._motor.calls[0] == ("forward", 0.5)
    client.post("/api/machine/stop", json={})
    assert machine._motor.calls[-1] == ("stop",)
    assert not client.get("/api/machine").get_json()["feeder"]["running"]


def test_missing_hardware_says_what_is_wrong(db):  # noqa: F811
    m = Machine()
    m._servos = lambda: None   # as on a PC: nothing to talk to
    m.servo_error = "Servo board not found"
    client = create_app(Scanner(db, None, source=None), m).test_client()
    res = client.post("/api/machine/move", json={"part": "pins", "position": "up"})
    assert res.status_code == 503 and "not found" in res.get_json()["error"]
    assert client.get("/machine").status_code == 200
