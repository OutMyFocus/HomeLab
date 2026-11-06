"""The Machine page's API, with fake hardware (no Pi needed)."""

import itertools
import threading
import time

import numpy as np
import pytest

from app import Scanner, create_app
from mtgscanner import config
from mtgscanner.machine import Machine
from mtgscanner.tracking import Track
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

from mtgscanner import feed_watch  # noqa: E402


class FakeCamera:
    """Hands the tap an empty bed, then (once the motor has run `after` frames) a card in
    the landing zone, from a thread like the Scanner's loop. card_stays: True = the card
    stays put; False = it slides off once the stop pins drop; "over" = it goes over the
    teeth as soon as the motor stops; "shifts" = the pins push it up out of the landing
    band but it stays on the bed."""

    def __init__(self, tap, machine, card_after=3, card_stays=True):
        self.tap, self.machine = tap, machine
        self.card_after, self.card_stays = card_after, card_stays
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        motor_frames = 0
        landed = gone = False
        pins_since = None
        while self.running:
            frame = np.full((400, 300, 3), 120, np.uint8)
            calls = self.machine._motor.calls
            forward = self.machine.feeding and bool(calls) and calls[-1][0] == "forward"
            pins_ch = config.SERVOS["pins"][0]
            pins_down = self.machine.angles.get(pins_ch) == config.SERVOS["pins"][1]["down"]
            if forward and gone and not pins_down:
                gone, motor_frames, pins_since = False, 0, None   # the next card's feed
            if forward and not gone:
                motor_frames += 1
                if self.card_after is not None and motor_frames >= self.card_after:
                    landed = True
            if landed and self.card_stays == "over" and not self.machine.feeding:
                landed, gone = False, True     # it went over the teeth
            if landed and pins_down and self.card_stays in (False, "shifts"):
                pins_since = pins_since or time.monotonic()
            moved = pins_since is not None and time.monotonic() - pins_since > 0.4
            if landed and self.card_stays is False and moved:
                landed, gone = False, True     # the card slid off, 0.4 s after the pins dropped
            if landed and self.card_stays == "shifts" and moved:
                frame[150:200, 60:280] = 230   # pushed up out of the landing band, still on the bed
            elif landed:
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
    cams.append(FakeCamera(scanner.tap, machine, card_after=2, card_stays="over"))
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


# --- Sorting a card to a bin (Machine.drop, sort_one) ------------------------------

@pytest.fixture
def quick_sort(monkeypatch):
    """Short drop timings: pins down up to 0.7 s (the fake card leaves 0.4 s after they drop),
    doors and tilt 0.05 s."""
    monkeypatch.setattr(config, "SORT_PINS_SECONDS", 0.7)
    for name in ("SORT_DOORS_SECONDS", "SORT_TILT_SECONDS"):
        monkeypatch.setattr(config, name, 0.05)


def moves(machine):
    """(part, position) for every named move so far, from the fake servos' angles log."""
    return machine._moves


@pytest.fixture
def logged(machine, monkeypatch):
    machine._moves = []
    real = machine.move

    def move(part, position):
        machine._moves.append((part, position))
        real(part, position)
    monkeypatch.setattr(machine, "move", move)
    return machine


def test_drop_to_the_door_bin_opens_the_doors_and_puts_everything_back(client, logged, quick_sort):
    r = client.post("/api/machine/drop", json={"bin": 2})
    assert r.status_code == 200, r.get_json()
    m = [x for x in moves(logged) if x != ("chute", "centre")]
    assert m[:2] == [("pins", "down"), ("door_r", "open")]
    assert ("door_l", "open") in m and ("door_r", "closed") in m and ("door_l", "closed") in m
    assert m[-1] == ("pins", "up")
    assert moves(logged)[0] == ("chute", "centre") and moves(logged)[-2] == ("chute", "centre")


def test_drop_to_a_side_bin_drops_the_pins_before_tilting(client, logged, quick_sort):
    client.post("/api/machine/drop", json={"bin": 3})
    m = moves(logged)
    assert m[:2] == [("chute", "centre"), ("pins", "down")]
    assert ("chute", "right") in m and m.index(("chute", "right")) > m.index(("pins", "down"))
    assert not any(part.startswith("door") for part, _ in m)
    assert m[-2:] == [("chute", "centre"), ("pins", "up")]
    assert client.post("/api/machine/drop", json={"bin": 7}).status_code == 400


def test_sort_one_feeds_then_drops_and_sees_the_bed_clear(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    out = client.post("/api/machine/sort_one", json={"bin": 1}).get_json()
    assert out["result"] == "landed" and out["bin"] == 1, out
    assert out["dropped"] is True and out["drop_tries"] == 1
    assert "bin 1" in out["message"]


def test_sort_one_moves_on_as_soon_as_the_card_has_left_the_teeth(watched, monkeypatch):
    """Pins down at most 2 s, but the fake card slides off the moment they drop, so the
    drop goes on after the least time (0.5 s + a moment), not the full 2 s."""
    monkeypatch.setattr(config, "SORT_PINS_SECONDS", 2.0)
    monkeypatch.setattr(config, "SORT_DOORS_SECONDS", 0.05)
    monkeypatch.setattr(config, "SORT_TILT_SECONDS", 0.05)
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    out = client.post("/api/machine/sort_one", json={"bin": 2}).get_json()
    assert out["result"] == "landed" and out["dropped"] is True, out
    assert 400 <= out["pins_ms"] < 1500, out["pins_ms"]


def test_sort_one_tries_the_drop_again_when_the_card_stays(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=True))
    out = client.post("/api/machine/sort_one", json={"bin": 2}).get_json()
    assert out["result"] == "landed" and out["dropped"] is False and out["drop_tries"] == 2, out
    assert "still on the bed" in out["message"]


def test_sort_one_sees_a_card_the_pins_pushed_out_of_the_landing_band(watched, quick_sort):
    """The card leaves the landing band when the pins drop, but not the bed (2026-11-06,
    B04): it is still there, so it must not count as dropped."""
    client, scanner, machine, cams = watched
    cam = FakeCamera(scanner.tap, machine, card_after=3, card_stays="shifts")
    cams.append(cam)
    out = client.post("/api/machine/sort_one", json={"bin": 1}).get_json()
    assert out["result"] == "landed" and out["dropped"] is False, out


def test_sort_one_does_not_drop_when_nothing_came(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=None))
    out = client.post("/api/machine/sort_one", json={"bin": 3, "max_seconds": 0.3}).get_json()
    assert out["result"] == "none" and out["dropped"] is None and out["drop_tries"] == 0
    assert client.post("/api/machine/sort_one", json={"bin": 9}).status_code == 400


# --- The tuning run (tuning.py) --------------------------------------------------------

def wait_tune(client, seconds=40):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        d = client.get("/api/machine/tune").get_json()
        if not d["running"]:
            return d
        time.sleep(0.05)
    raise AssertionError("the tuning run didn't finish")


def test_tuning_run_goes_round_the_bins_and_scores_clean_feeds(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    r = client.post("/api/machine/tune", json={"cycles": 2, "speed": 0.8})
    assert r.status_code == 200, r.get_json()
    assert client.post("/api/machine/tune", json={}).status_code == 409    # one at a time
    d = wait_tune(client)
    assert d["done"] == "finished" and d["score"] == {"clean": 6, "total": 6}, d
    assert [f["bin"] for f in d["feeds"]] == [1, 2, 3, 1, 2, 3]
    assert d["settings"]["speed"] == 0.8 and d["changes"] == []
    saved = client.post("/api/machine/tune/save", json={}).get_json()
    assert saved["speed"] == 0.8 and saved["pins_seconds"] == 0.7
    assert machine.feeder_defaults()["speed"] == 0.8
    assert machine.sort_defaults()["pins_seconds"] == 0.7    # the quick test timing, saved


def test_tuning_run_slows_the_feeder_after_a_card_goes_over(watched, quick_sort, monkeypatch):
    monkeypatch.setattr(config, "SORT_PINS_SECONDS", 1.0)   # long enough to notice the card was never there
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=2, card_stays="over"))
    client.post("/api/machine/tune", json={"cycles": 1, "bins": [2], "speed": 0.8})
    d = wait_tune(client)
    assert d["feeds"][0]["result"] == "over" and d["feeds"][0]["clean"] is False
    assert d["settings"]["speed"] == 0.75 and d["changes"][0]["speed"] == 0.75


def test_tuning_run_stops_when_a_card_is_left_on_the_bed(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=True))
    client.post("/api/machine/tune", json={"cycles": 3, "speed": 0.8})
    d = wait_tune(client)
    assert len(d["feeds"]) == 1 and d["feeds"][0]["dropped"] is False
    assert "still on the bed" in d["done"]
    assert d["settings"]["pins_seconds"] == 0.7    # a card left on the bed isn't "slow": no pins change


def test_tuning_run_stops_when_the_hopper_is_empty(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=None))
    client.post("/api/machine/tune", json={"cycles": 2, "bins": [1], "speed": 0.9})
    d = wait_tune(client)
    assert [f["result"] for f in d["feeds"]] == ["none", "none"]
    assert "hopper" in d["done"] and d["settings"]["speed"] == 1.0   # 0.95 then 1.0
    assert client.post("/api/machine/tune", json={"bins": [9]}).status_code == 400


# --- The sort run (sort_run.py): the machine on its own ------------------------------

class FakeRecognizer:
    """Stands in for the scanner's loop during a sort run: whenever the feed watch lets
    the pictures through (tap.watching == 0, the "choose" step), it puts one recognized
    card on the scanner's table; while the feed watch is watching, the table is empty."""

    def __init__(self, scanner, card, status="locked"):
        self.scanner, self.card, self.status = scanner, card, status
        self.running = True
        self.ids = itertools.count(100)
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while self.running:
            with self.scanner.lock:
                if self.scanner.tap.watching == 0 and not self.scanner.tracks and self.card is not None:
                    t = Track(next(self.ids), 1, np.array([[40, 240], [260, 240], [260, 290], [40, 290]], float))
                    t.card, t.status, t.checked_time = self.card, self.status, time.monotonic()
                    t.streak_key = self.card.id
                    self.scanner.tracks.append(t)
                elif self.scanner.tap.watching > 0:
                    self.scanner.tracks.clear()
            time.sleep(0.02)


def wait_sort(client, seconds=40):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        d = client.get("/api/machine/sort").get_json()
        if not d["running"]:
            return d
        time.sleep(0.05)
    raise AssertionError("the sort run didn't finish")


def test_sort_run_recognizes_saves_and_bins_each_card(watched, quick_sort, db):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    cams.append(FakeRecognizer(scanner, db.get_card("id1")))     # Card 1, $4.50 -> bin 2
    r = client.post("/api/machine/sort", json={"max_cards": 2, "speed": 0.8})
    assert r.status_code == 200, r.get_json()
    assert client.post("/api/machine/sort", json={}).status_code == 409    # one at a time
    d = wait_sort(client)
    assert d["done"] == "did the 2 cards asked for", d
    assert [c["status"] for c in d["cards"]] == ["saved", "saved"]
    assert [c["bin"] for c in d["cards"]] == [2, 2] and d["cards"][0]["name"] == "Card 1"
    assert d["counts"]["saved"] == 2 and d["tally"] == [{"bin": 2, "label": "$1 - $10", "cards": 2}]
    assert all(c["dropped"] for c in d["cards"])
    assert len(scanner.session) == 2 and scanner.session[0]["bin"] == 2     # in the collection


def test_sort_run_puts_a_card_it_cannot_read_in_the_fallback_bin(watched, quick_sort, monkeypatch, db):
    monkeypatch.setattr(config, "SORT_RECOGNIZE_SECONDS", 0.4)
    monkeypatch.setattr(config, "SORT_FOIL_AFTER", 0.1)
    monkeypatch.setattr(config, "SORT_FALLBACK_BIN", 3)
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    # a card recognized before the feed (the last one dropped, or the next one hanging
    # out of the slot at the top of the picture) doesn't count as this card
    stale = Track(1, 1, np.array([[40, 240], [260, 240], [260, 290], [40, 290]], float))
    stale.card, stale.status, stale.checked_time = db.get_card("id1"), "locked", time.monotonic() - 1
    top = Track(2, 2, np.array([[40, 10], [260, 10], [260, 60], [40, 60]], float))
    top.card, top.status, top.checked_time = db.get_card("id2"), "locked", time.monotonic() + 100
    unread = Track(3, 3, np.array([[40, 240], [260, 240], [260, 290], [40, 290]], float))
    unread.status, unread.checked_time = "unknown", time.monotonic() + 100      # no match yet: keep waiting
    scanner.tracks.extend([stale, top, unread])

    class Sticky:   # the scanner keeps re-planting the stale tracks, as it would carry on a track
        def __init__(self):
            self.running = True
            threading.Thread(target=self.loop, daemon=True).start()

        def loop(self):
            while self.running:
                with scanner.lock:
                    if not scanner.tracks:
                        for t in (stale, top, unread):
                            t.checked_time = time.monotonic() + 100
                        scanner.tracks.extend([stale, top, unread])
                time.sleep(0.02)
    cams.append(Sticky())
    scanner.frame_size = (300, 400)
    class Bars:   # the light bars: dimmed for the second look, then put back
        settings = {"brightness": 30}
        changes = []

        def update(self, raw):
            self.settings = self.settings | raw
            self.changes.append(raw["brightness"])
    scanner.lights = Bars()
    client.post("/api/machine/sort", json={"max_cards": 1, "speed": 0.8})
    d = wait_sort(client)
    assert d["cards"][0]["status"] == "unknown" and d["cards"][0]["bin"] == 3, d
    assert d["cards"][0]["dimmed"] is True and scanner.lights.changes == [8, 30]
    assert scanner.session == []                                          # not saved


def test_sort_run_does_not_save_an_unsure_guess(watched, quick_sort, db):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    cams.append(FakeRecognizer(scanner, db.get_card("id2"), status="unsure"))
    client.post("/api/machine/sort", json={"max_cards": 1, "speed": 0.8})
    d = wait_sort(client)
    c = d["cards"][0]
    assert c["status"] == "unsure" and c["name"] == "Card 2" and c["bin"] == config.SORT_FALLBACK_BIN, d
    assert scanner.session == []


def test_sort_run_warns_when_a_bin_is_filling_up(watched, quick_sort, db, monkeypatch):
    monkeypatch.setattr(config, "SORT_BIN_WARN", 2)
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    cams.append(FakeRecognizer(scanner, db.get_card("id1")))
    client.post("/api/machine/sort", json={"max_cards": 2, "speed": 0.8})
    d = wait_sort(client)
    assert d["full"] == [2] and "Bin 2" in d["warning"], d
    door = config.SERVOS["door_l"]
    assert machine.angles.get(door[0]) == door[1]["closed"]     # the doors are told "closed" again each card


def test_sort_run_stops_when_the_hopper_is_empty(watched, quick_sort):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=None))
    client.post("/api/machine/sort", json={"speed": 0.8, "max_cards": 0})
    d = wait_sort(client)
    assert "hopper is empty" in d["done"] and d["counts"]["none"] == 2, d
    assert client.post("/api/machine/sort/stop", json={}).get_json()["running"] is False


def test_sort_run_stops_when_two_cards_come_out_together(watched, quick_sort, db):
    client, scanner, machine, cams = watched
    cams.append(FakeCamera(scanner.tap, machine, card_after=3, card_stays=False))
    pair = FakeRecognizer(scanner, db.get_card("id1"))
    cams.append(pair)

    class Second:   # a second card next to the first, as a stacked pair looks to the scanner
        def __init__(self):
            self.running = True
            threading.Thread(target=self.loop, daemon=True).start()

        def loop(self):
            while self.running:
                with scanner.lock:
                    if len(scanner.tracks) == 1 and scanner.tap.watching == 0:
                        t = Track(999, 2, np.array([[40, 185], [260, 185], [260, 235], [40, 235]], float))
                        t.card, t.status, t.checked_time, t.streak_key = db.get_card("id2"), "locked", time.monotonic(), "id2"
                        scanner.tracks.append(t)
                time.sleep(0.01)
    cams.append(Second())
    client.post("/api/machine/sort", json={"max_cards": 3, "speed": 0.8})
    d = wait_sort(client)
    assert "two cards came out together" in d["done"], d
    assert d["cards"][-1]["status"] == "double" and d["cards"][-1]["bin"] is None
    pins = config.SERVOS["pins"]
    assert machine.angles.get(pins[0]) == pins[1]["up"]      # nothing was dropped
    assert scanner.session == []
