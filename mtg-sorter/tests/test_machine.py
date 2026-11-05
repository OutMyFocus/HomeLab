"""The Machine page's API, with fake hardware (no Pi needed)."""

import time

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


@pytest.fixture(autouse=True)
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)   # saved angles go here, not in data/
    return tmp_path


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


class FakePCA:
    def __init__(self, mode1):
        self.mode1_reg = mode1


def test_board_that_lost_power_is_set_up_again(machine, monkeypatch):
    # A PCA9685 that was unplugged and plugged back in wakes up asleep (MODE1 bit 4).
    asleep = FakeKit()
    asleep._pca = FakePCA(0x11)
    machine._kit = asleep
    fresh = FakeKit()
    fresh._pca = FakePCA(0x20)
    monkeypatch.setattr(machine, "_servos", lambda: machine._kit or fresh)
    machine.set_angle(1, 70)
    assert fresh.servo[1].angle == 70
    assert asleep.servo[1].angle is None


def test_lost_board_is_looked_for_again(machine):
    class Broken:
        @property
        def angle(self): return None
        @angle.setter
        def angle(self, v): raise OSError(121, "Remote I/O error")
    machine._kit.servo[2] = Broken()
    with pytest.raises(OSError):
        machine.set_angle(2, 90)
    assert machine._kit is None


def test_servo_lets_go_after_a_move(machine, monkeypatch):
    monkeypatch.setattr(config, "SERVO_HOLD_SECONDS", 0.05)
    machine.set_angle(1, 70)
    assert machine._kit.servo[1].angle == 70
    time.sleep(0.2)
    assert machine._kit.servo[1].angle is None
    assert machine.angles[1] is None


def test_stop_pins_keep_holding(machine, monkeypatch):
    # The gate drops under its own weight when let go, so the pins never go limp by themselves.
    monkeypatch.setattr(config, "SERVO_HOLD_SECONDS", 0.05)
    machine.move("pins", "up")
    pins = config.SERVOS["pins"][0]
    time.sleep(0.2)
    assert machine._kit.servo[pins].angle == machine.servos()["pins"][1]["up"]
    machine.relax_all()                 # Relax still lets them go
    assert machine._kit.servo[pins].angle is None


def test_a_new_move_keeps_holding(machine, monkeypatch):
    monkeypatch.setattr(config, "SERVO_HOLD_SECONDS", 0.15)
    machine.set_angle(1, 70)
    time.sleep(0.1)
    machine.set_angle(1, 80)      # restarts the hold
    time.sleep(0.1)
    assert machine._kit.servo[1].angle == 80


def test_held_parts_still_let_go_after_the_hold_limit(machine, monkeypatch):
    # A gate or door jammed at a stop mustn't cook its servo.
    monkeypatch.setattr(config, "SERVO_HOLD_SECONDS", 0.01)
    monkeypatch.setattr(config, "SERVO_HOLD_LIMIT", 0.1)
    pins = config.SERVOS["pins"][0]
    machine.move("pins", "up")
    time.sleep(0.05)
    assert machine._kit.servo[pins].angle is not None
    time.sleep(0.2)
    assert machine._kit.servo[pins].angle is None


def test_home_sweeps_from_the_last_angle(machine, monkeypatch):
    chute = config.SERVOS["chute"][0]
    machine.set_angle(chute, 100)
    fresh = Machine()                       # as after a restart: it remembers 100
    fresh._kit = machine._kit
    sent = []
    real = fresh.set_angle
    monkeypatch.setattr(fresh, "set_angle", lambda ch, a: (sent.append((ch, a)), real(ch, a)))
    fresh.home(pause=0, speed=10_000)
    path = [a for ch, a in sent if ch == chute]
    target = fresh.servos()["chute"][1]["centre"]
    assert path[-1] == target and len(path) > 10
    assert all(abs(b - a) <= 2.01 for a, b in zip([100] + path, path))   # no jumps


# --- Feed one card, watching the camera (feed_watch.py) ---------------------------

import threading  # noqa: E402

import numpy as np  # noqa: E402

from mtgscanner import feed_watch  # noqa: E402


class FakeCamera:
    """Hands the tap an empty bed, then (once the motor has run `after` frames) a card in
    the landing zone, from a thread like the Scanner's loop."""

    def __init__(self, tap, machine, card_after=3, card_stays=True):
        self.tap, self.machine = tap, machine
        self.card_after, self.card_stays = card_after, card_stays
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        motor_frames = 0
        landed = False
        while self.running:
            frame = np.full((400, 300, 3), 120, np.uint8)
            if self.machine.feeding:
                motor_frames += 1
                if self.card_after is not None and motor_frames >= self.card_after:
                    landed = True
            if landed and (self.card_stays or self.machine.feeding):
                frame[240:290, 40:260] = 230   # a white card across the zone (y 0.6-0.72)
            self.tap.put(frame)
            time.sleep(0.02)


@pytest.fixture
def watched(db, machine, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "FEED_SETTLE_SECONDS", 0.2)
    monkeypatch.setattr(config, "FEED_BACKOFF_SECONDS", 0.05)
    monkeypatch.setattr(config, "FEED_ZONE", (0.2, 0.62, 0.8, 0.70))
    scanner = Scanner(db, None, source=None)
    app = create_app(scanner, machine)
    cams = []
    yield app.test_client(), scanner, machine, cams
    for c in cams:
        c.running = False


def test_feed_one_stops_the_motor_when_a_card_lands(watched):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3))
    out = client.post("/api/machine/feed_one", json={"max_seconds": 2}).get_json()
    assert out["result"] == "landed", out
    assert out["landed_ms"] is not None and out["motor_ms"] < 1500
    assert machine._motor.calls[0][0] == "forward"
    # then a short turn backwards, so the next card goes back into the hopper
    kinds = [c[0] for c in machine._motor.calls]
    assert kinds[:3] == ["forward", "stop", "backward"] and kinds[-1] == "stop"
    assert out["backoff_ms"] == 50
    assert not machine.feeding


def test_feed_one_gives_up_when_no_card_comes(watched):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=None))
    out = client.post("/api/machine/feed_one", json={"max_seconds": 0.4}).get_json()
    assert out["result"] == "none"
    assert out["landed_ms"] is None
    assert machine._motor.calls[-1] == ("stop",)
    assert "backward" not in [c[0] for c in machine._motor.calls]   # nothing landed: no back-off


def test_feed_one_sees_a_card_that_went_over_the_teeth(watched):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=2, card_stays=False))
    out = client.post("/api/machine/feed_one", json={"max_seconds": 2}).get_json()
    assert out["result"] == "over"


def test_feed_one_needs_a_camera(watched):
    client, *_ = watched
    r = client.post("/api/machine/feed_one", json={"max_seconds": 0.3})
    assert r.status_code == 503
    assert "camera" in r.get_json()["error"]


def test_landing_zone_is_saved_and_checked(watched):
    client, *_ = watched
    assert client.post("/api/machine/feed_zone", json={"zone": [0.1, 0.5, 0.9, 0.6]}).status_code == 200
    assert client.get("/api/machine/feed_zone").get_json()["zone"] == [0.1, 0.5, 0.9, 0.6]
    assert client.post("/api/machine/feed_zone", json={"zone": [0.5, 0.5, 0.4, 0.6]}).status_code == 400


def test_a_shadow_over_the_zone_is_not_a_card():
    ref = np.full((100, 100), 120, np.uint8)
    zone = [0.2, 0.6, 0.8, 0.7]
    darker = ref - 40   # the whole picture darker by the same amount: a hand's shadow
    assert feed_watch.changed_share(ref, darker, zone) < 0.05
    card = ref.copy()
    card[55:75, 15:85] = 230   # a card over the zone, the rest of the bed as it was
    assert feed_watch.changed_share(ref, card, zone) > 0.9


def test_scanner_skips_recognizing_while_a_feed_watches(db, monkeypatch):  # noqa: F811
    scanner = Scanner(db, None, source=None)
    tap = feed_watch.FrameTap()
    scanner.tap = tap

    class OneFrame:
        def read(self):
            return np.full((200, 100, 3), 120, np.uint8)

    scanner.source = OneFrame()
    looked = []
    monkeypatch.setattr(scanner, "process", lambda frame: looked.append(frame))
    scanner.turn()
    assert len(looked) == 1 and tap.seq == 0      # nobody watching: the normal loop
    tap.watching = 1
    scanner.turn()
    assert len(looked) == 1 and tap.seq == 1      # watching: straight to the feed, no recognizing
    assert scanner.jpeg is not None
