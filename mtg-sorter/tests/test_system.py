"""The Maintenance page's API, on a PC (no Pi, no helper): it answers and says what's missing."""

import io
import json
import sqlite3
import zipfile

import pytest

from app import Scanner, create_app
from mtgscanner import config, system
from mtgscanner.machine import Machine
from test_machine import FakeKit, FakeMotor
from test_scanner import db  # noqa: F401  (a fixture)


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(system, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(system, "UPDATE_STATUS", tmp_path / "update_status.json")
    monkeypatch.setattr(system, "ADMIN", str(tmp_path / "no-helper-here"))
    return tmp_path


@pytest.fixture
def client(db, data):  # noqa: F811
    m = Machine()
    m._kit, m._motor = FakeKit(), FakeMotor()
    return create_app(Scanner(db, None, source=None), m).test_client()


def test_page_and_checkup(client):
    assert client.get("/maintenance").status_code == 200
    s = client.get("/api/system").get_json()
    ids = {c["id"] for c in s["checks"]}
    assert {"power", "camera", "servos", "feeder", "cards", "disk", "updates"} <= ids
    camera = next(c for c in s["checks"] if c["id"] == "camera")
    assert camera["state"] == "bad" and camera["fix"]       # no camera: says so, and what to do
    assert next(c for c in s["checks"] if c["id"] == "servos")["state"] == "ok"
    h = client.get("/api/health").get_json()
    assert h["alive"] and h["overall"] == "bad"
    assert any(p["label"] == "Camera" for p in h["problems"])


def test_buttons_explain_when_the_helper_is_missing(client):
    for path in ("restart", "reboot", "poweroff", "update"):
        res = client.post(f"/api/system/{path}", json={})
        assert res.status_code == 503 and "setup.sh" in res.get_json()["error"]


def test_helper_jobs_go_through_sudo(client, data, monkeypatch):
    (data / "no-helper-here").touch()
    ran = []
    monkeypatch.setattr(system, "run", lambda cmd, **kw: (ran.append((cmd, kw.get("input"))), (True, "ok"))[1])
    assert client.post("/api/system/autoupdate", json={"on": False}).status_code == 200
    assert ran[-1][0][-3:] == [system.ADMIN, "autoupdate", "off"] and ran[-1][0][:2] == ["sudo", "-n"]
    assert client.post("/api/system/wifi", json={"ssid": "Cabin", "password": "hunter22"}).status_code == 200
    assert ran[-1][0][-1] == "wifi-add" and ran[-1][1] == "Cabin\nhunter22\n"   # the password goes on stdin
    assert client.post("/api/system/wifi", json={"ssid": "Cabin", "password": "short"}).status_code == 400


def test_logs_say_where_they_are(client, monkeypatch):
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    res = client.get("/api/system/logs?which=app")
    assert res.status_code == 503
    assert client.get("/api/system/logs?which=nope").status_code == 400


def test_stuck_updates_offer_the_fix(monkeypatch):
    monkeypatch.setattr(system, "ON_PI", True)
    monkeypatch.setattr(system, "version", lambda: {"available": True, "local_edits": ["mtg-sorter/mtgscanner/config.py"],
                                                    "commit": "abc1234", "behind": 2})
    monkeypatch.setattr(system, "auto_updates_on", lambda: True)
    c = system.updates_check()
    assert c["state"] == "bad" and c["action"] == "update_force" and "config.py" in c["summary"]


def test_power_warning_from_throttle_flags(monkeypatch):
    monkeypatch.setattr(system, "supply_volts", lambda: 4.71)
    monkeypatch.setattr(system, "throttled", lambda: 0x50005)
    c = system.power_check()
    assert c["state"] == "bad" and "4.71 V" in c["summary"] and "5 A" in c["fix"]
    monkeypatch.setattr(system, "throttled", lambda: 0x50000)
    assert system.power_check()["state"] == "warn"
    monkeypatch.setattr(system, "throttled", lambda: 0)
    assert system.power_check()["state"] == "ok"


def test_backup_and_restore_round_trip(client, data):
    (data / "collection.csv").write_text("Name,Quantity\nOld Card,1\n")
    (data / "app_settings.json").write_text('{"mode": "slots"}')
    conn = sqlite3.connect(data / "cards.db"); conn.execute("CREATE TABLE t (x)"); conn.commit(); conn.close()
    res = client.get("/api/system/backup")
    assert res.status_code == 200 and res.mimetype == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(res.data)).namelist()
    assert {"collection.csv", "app_settings.json", "cards.db"} <= set(names)

    (data / "collection.csv").write_text("Name,Quantity\nNew Card,1\n")
    r = client.post("/api/system/restore", data={"backup": (io.BytesIO(res.data), "b.zip")},
                    content_type="multipart/form-data").get_json()
    assert "collection.csv" in r["restored"]
    assert "Old Card" in (data / "collection.csv").read_text()
    kept = zipfile.ZipFile(data / "backups" / r["saved_first"])      # what was there is kept first
    assert "New Card" in kept.read("collection.csv").decode()


def test_restore_refuses_odd_zips(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../etc/evil", "x")
        z.writestr("captures/../../evil", "x")
    buf.seek(0)
    res = client.post("/api/system/restore", data={"backup": (buf, "b.zip")}, content_type="multipart/form-data")
    assert res.status_code == 400
    res = client.post("/api/system/restore", data={"backup": (io.BytesIO(b"not a zip"), "b.zip")},
                      content_type="multipart/form-data")
    assert res.status_code == 400


def test_machine_angles_are_saved_outside_config(client, data):
    s = client.post("/api/machine/save", json={"part": "pins", "position": "down", "angle": 58}).get_json()
    assert s["parts"]["pins"]["positions"]["down"] == 58
    assert s["parts"]["pins"]["factory"]["down"] == config.SERVOS["pins"][1]["down"]   # config.py untouched
    assert s["customized"]
    assert json.loads((data / "machine_settings.json").read_text())["servos"]["pins"]["down"] == 58
    client.post("/api/machine/move", json={"part": "pins", "position": "down"})
    assert client.get("/api/machine").get_json()["parts"]["pins"]["angle"] == 58

    s = client.post("/api/machine/save", json={"seconds": 0.8, "speed": 0.7}).get_json()
    assert s["feeder_defaults"] == {"seconds": 0.8, "speed": 0.7, "reverse": False,
                                    "backoff": config.FEED_BACKOFF_SECONDS, "push": config.FEED_PUSH_SECONDS}
    s = client.post("/api/machine/reset", json={}).get_json()
    assert not s["customized"] and s["parts"]["pins"]["positions"]["down"] == config.SERVOS["pins"][1]["down"]
    assert client.post("/api/machine/save", json={"part": "pins", "position": "sideways", "angle": 5}).status_code == 400


def test_moving_parts_test(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    r = client.post("/api/machine/test", json={}).get_json()
    assert [t["part"] for t in r["test"]] == [*config.SERVOS, "feeder"]
    assert all(t["ok"] for t in r["test"])


def test_in_docker_the_server_has_no_camera_or_self_updates(client, monkeypatch):
    from mtgscanner import system
    monkeypatch.setattr(system, "IN_DOCKER", True)
    s = client.get("/api/system").get_json()
    camera = next(c for c in s["checks"] if c["id"] == "camera")
    assert camera["state"] == "off" and "This device's camera" in camera["fix"]
    updates = next(c for c in s["checks"] if c["id"] == "updates")
    assert updates["state"] == "off" and "Docker" in updates["summary"]
    assert client.get("/api/health").get_json()["overall"] != "bad" or \
        all(p["label"] != "Camera" for p in client.get("/api/health").get_json()["problems"])
    # Restart works without the Pi's helper: the app starts itself over in place, so the
    # container keeps running even with no Docker restart policy (Unraid sets none).
    timers, execs = [], []
    monkeypatch.setattr(system.threading, "Timer", lambda delay, fn: type("T", (), {"start": lambda self: (timers.append(delay), fn())})())
    monkeypatch.setattr(system.os, "execv", lambda exe, argv: execs.append((exe, argv)))
    assert client.post("/api/system/restart").get_json()["ok"]
    assert timers == [1.0] and execs == [(system.sys.executable, [system.sys.executable, *system.sys.argv])]


def test_data_folder_can_be_moved_with_an_environment_variable(tmp_path, monkeypatch):
    import importlib
    from mtgscanner import config
    monkeypatch.setenv("MTG_DATA_DIR", str(tmp_path / "elsewhere"))
    try:
        importlib.reload(config)
        assert config.DATA_DIR == (tmp_path / "elsewhere").resolve()
        assert config.DB_PATH == config.DATA_DIR / "cards.db"
    finally:
        monkeypatch.delenv("MTG_DATA_DIR")
        importlib.reload(config)
    assert config.DATA_DIR.name == "data"


def test_in_docker_the_pi_only_buttons_say_so_and_the_app_log_is_kept_in_memory(client, monkeypatch):
    import logging
    from mtgscanner import system
    monkeypatch.setattr(system, "IN_DOCKER", True)
    monkeypatch.setattr(system, "HOST_BRIDGE", False)
    # Reboot, shut down, update and automatic updates are the Pi's: the server says where to go instead.
    for path in ("/api/system/reboot", "/api/system/poweroff", "/api/system/update"):
        r = client.post(path, json={})
        assert r.status_code == 503 and "Docker" in r.get_json()["error"] and "Unraid" in r.get_json()["error"]
        assert "maintenance helper" not in r.get_json()["error"]
    r = client.post("/api/system/autoupdate", json={"on": True})
    assert r.status_code == 400 and "Docker" in r.get_json()["error"]
    # The app log comes from memory (Docker keeps the container's output, not journalctl).
    system.keep_logs_in_memory()
    logging.getLogger("werkzeug").info("GET /scan 200")
    logging.getLogger("mtgscanner.test").warning("something to look at")
    text = client.get("/api/system/logs?which=app&lines=50").get_json()["text"]
    assert "GET /scan 200" in text and "something to look at" in text
    r = client.get("/api/system/logs?which=system")
    assert r.status_code == 503 and "Unraid" in r.get_json()["error"]
    s = client.get("/api/system").get_json()
    assert s["docker"] is True and s["pi_docker"] is False


# --- Wi-Fi: never cut the Pi off -------------------------------------------------------------

def fake_nmcli(monkeypatch, ran, connections="preconfigured:802-11-wireless:yes\nCa\\:bin:802-11-wireless:no\n"
               "Wired connection 1:802-3-ethernet:yes\n"):
    """nmcli as Raspberry Pi Imager leaves it: the profile in use is "preconfigured", its network HomeNet."""
    (system.config.DATA_DIR / "no-helper-here").touch()

    def run(cmd, **kw):
        ran.append(cmd)
        if cmd[:1] == ["nmcli"] and "device" in cmd:
            return True, "yes:HomeNet:78\nno:Neighbours:30\n"
        if cmd[:1] == ["nmcli"]:
            return True, connections
        return True, "ok"
    monkeypatch.setattr(system, "run", run)
    monkeypatch.setattr(system.shutil, "which", lambda name: "/usr/bin/" + name)


def test_wifi_knows_which_saved_profile_is_in_use(data, monkeypatch):
    fake_nmcli(monkeypatch, [])
    w = system.wifi()
    assert w["ssid"] == "HomeNet" and w["signal"] == 78
    assert w["saved"] == ["preconfigured", "Ca:bin"] and w["in_use"] == ["preconfigured"]


def test_the_network_in_use_cant_be_forgotten_or_replaced(client, monkeypatch):
    ran = []
    fake_nmcli(monkeypatch, ran)
    helper = lambda: [c for c in ran if c[:1] == ["sudo"]]  # noqa: E731
    r = client.post("/api/system/wifi/forget", json={"name": "preconfigured"})
    assert r.status_code == 400 and "using right now" in r.get_json()["error"] and not helper()
    for ssid in ("HomeNet", "preconfigured"):
        r = client.post("/api/system/wifi", json={"ssid": ssid, "password": "newpass123"})
        assert r.status_code == 400 and "cable" in r.get_json()["error"] and not helper()
    assert client.post("/api/system/wifi/forget", json={"name": "Ca:bin"}).status_code == 200
    assert helper()[-1][-1] == "wifi-forget"
    assert client.post("/api/system/wifi", json={"ssid": "Cabin", "password": "hunter22"}).status_code == 200


# --- Backups and restores --------------------------------------------------------------------

def a_backup(client, **kw) -> bytes:
    res = client.get("/api/system/backup", **kw)
    assert res.status_code == 200 and res.mimetype == "application/zip"
    return res.data


def restore(client, raw: bytes, **form):
    return client.post("/api/system/restore", data={"backup": (io.BytesIO(raw), "b.zip"), **form},
                       content_type="multipart/form-data")


def test_backups_hold_the_lights_news_and_machine_key(client, data):
    extra = {"lights.json": '{"leds": 30}', "news_settings.json": '{"sources": []}', "machine_key": "k" * 40}
    for name, text in extra.items():
        (data / name).write_text(text)
    raw = a_backup(client)
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert set(extra) <= set(z.namelist())
    assert json.loads(z.comment)["made_on"] == "server"
    for name in extra:
        (data / name).unlink()
    r = restore(client, raw)
    assert r.status_code == 200 and r.get_json()["restarting"] is False   # no helper here
    for name, text in extra.items():
        assert (data / name).read_text() == text
    assert (data / "machine_key").stat().st_mode & 0o777 == 0o600


def test_backup_with_scans_streams_and_round_trips(client, data):
    (data / "collection.csv").write_text("Name,Quantity\nOld Card,1\n")
    (data / "captures" / "a").mkdir(parents=True)
    pics = {f"captures/a/{i}.jpg": bytes([i]) * (300_000 + i) for i in range(4)}
    for name, raw in pics.items():
        (data / name).write_bytes(raw)
    res = client.get("/api/system/backup?scans=1", buffered=False)
    assert res.is_streamed
    raw = b"".join(res.response)
    z = zipfile.ZipFile(io.BytesIO(raw))
    assert z.testzip() is None and set(pics) <= set(z.namelist())
    for name in pics:
        (data / name).unlink()
    assert restore(client, raw).status_code == 200
    assert all((data / name).read_bytes() == b for name, b in pics.items())


def damage(raw: bytes, member: str, how: str) -> bytes:
    """A backup with one file spoiled: its check sum (crc) or its compressed bytes (deflate)."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    info = z.getinfo(member)
    raw = bytearray(raw)
    if how == "crc":   # the check sum in the central directory, which is what zipfile trusts
        at = raw.find(b"PK\x01\x02", z.start_dir)
        while raw[at + 46:at + 46 + len(member)] != member.encode():
            at = raw.find(b"PK\x01\x02", at + 4)
        raw[at + 16:at + 20] = (info.CRC ^ 0xFFFFFFFF).to_bytes(4, "little")
    else:
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        for i in range(start, start + min(info.compress_size, 64)):
            raw[i] ^= 0x5A
    return bytes(raw)


@pytest.mark.parametrize("how", ["crc", "deflate"])
def test_a_damaged_backup_changes_nothing(client, data, how):
    (data / "collection.csv").write_text("Name,Quantity\nOld Card,1\n")
    (data / "users.json.ok").write_text("")   # a file the backup doesn't touch
    (data / "decks.json").write_text(json.dumps({"decks": ["x" * 4000]}))
    raw = a_backup(client)
    (data / "collection.csv").write_text("Name,Quantity\nNew Card,1\n")
    (data / "decks.json").write_text('{"decks": []}')
    names = zipfile.ZipFile(io.BytesIO(raw)).namelist()
    assert names.index("collection.csv") < names.index("decks.json")   # the good file comes first
    r = restore(client, damage(raw, "decks.json", how))
    assert r.status_code == 400 and "Nothing was changed" in r.get_json()["error"]
    assert "New Card" in (data / "collection.csv").read_text()          # not half restored
    assert (data / "decks.json").read_text() == '{"decks": []}'
    assert not list(data.rglob("*.restoring"))


def test_a_restore_can_keep_this_machines_own_settings(client, data, monkeypatch):
    (data / "collection.csv").write_text("Name,Quantity\nTower Card,1\n")
    (data / "app_settings.json").write_text('{"rotate": 0}')
    (data / "machine_settings.json").write_text('{"servos": {}}')
    raw = a_backup(client)                                   # made on the server
    monkeypatch.setattr(system, "ON_PI", True)               # ...restored on the Pi
    (data / "collection.csv").write_text("Name,Quantity\nPi Card,1\n")
    (data / "app_settings.json").write_text('{"rotate": 90}')
    (data / "machine_settings.json").write_text('{"servos": {"pins": {"down": 58}}}')
    r = restore(client, raw, keep_settings="1").get_json()
    assert r["kept"] == ["app_settings.json", "machine_settings.json"] and r["made_on"] == "server"
    assert "stayed as they were" in r["message"]
    assert "Tower Card" in (data / "collection.csv").read_text()
    assert json.loads((data / "app_settings.json").read_text()) == {"rotate": 90}
    assert "58" in (data / "machine_settings.json").read_text()
    r = restore(client, raw).get_json()                      # a full restore still puts everything back
    assert r["kept"] == [] and json.loads((data / "app_settings.json").read_text()) == {"rotate": 0}
    assert json.loads(zipfile.ZipFile(io.BytesIO(a_backup(client))).comment)["made_on"] == "pi"


def test_after_a_restore_in_docker_the_page_waits_for_the_restart(client, data, monkeypatch):
    (data / "collection.csv").write_text("Name,Quantity\nOld Card,1\n")
    raw = a_backup(client)
    restarts = []
    monkeypatch.setattr(system, "IN_DOCKER", True)
    monkeypatch.setattr(system, "HOST_BRIDGE", False)
    monkeypatch.setattr(system, "restart_in_place", lambda: restarts.append(1))
    monkeypatch.setattr(system.threading, "Timer", lambda delay, fn: type("T", (), {"start": lambda self: fn()})())
    r = restore(client, raw).get_json()
    assert r["restarting"] is True and restarts == [1]


# --- Health: up for everyone, problems only for those who run Maintenance -------------------

def test_health_shows_problems_only_to_admins(client, data, monkeypatch):
    away = {"REMOTE_ADDR": "203.0.113.9"}
    stranger = client.application.test_client()
    assert "problems" in stranger.get("/api/health", environ_base=away).get_json()    # nothing locked
    # A PIN: a phone that hasn't typed it learns only that the app is up.
    assert client.post("/api/lock/set", json={"pin": "2468"}).status_code == 200
    h = stranger.get("/api/health", environ_base=away)
    assert h.status_code == 200 and h.get_json()["alive"] and "problems" not in h.get_json()
    assert "problems" in client.get("/api/health").get_json()                         # the Pi itself
    assert client.post("/api/lock/remove", json={}).status_code == 200
    # Accounts: only an admin sees what's wrong.
    monkeypatch.setattr(config, "COLLECTION_CSV", data / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", data / "captures")
    nic = client.application.test_client()
    nic.environ_base.update(away)
    assert nic.post("/api/accounts/setup", json={"username": "nic", "password": "secret-1", "name": "Nic"}).status_code == 200
    assert nic.post("/api/accounts/add", json={"username": "sam", "password": "sammy-1", "name": "Sam"}).status_code == 200
    sam = client.application.test_client()
    sam.environ_base.update(away)
    assert sam.post("/api/login", json={"username": "sam", "password": "sammy-1"}).status_code == 200
    assert "problems" not in stranger.get("/api/health", environ_base=away).get_json()
    assert "problems" not in sam.get("/api/health").get_json()
    assert any(p["label"] == "Camera" for p in nic.get("/api/health").get_json()["problems"])


def test_memory_reads_in_gb_once_it_is_over_a_gb(monkeypatch):
    monkeypatch.setattr(system, "memory", lambda: {"free_mb": 15090, "total_mb": 16087})
    assert system.memory_check()["summary"] == "14.7 GB free of 15.7 GB"
    monkeypatch.setattr(system, "memory", lambda: {"free_mb": 150, "total_mb": 900})
    c = system.memory_check()
    assert c["state"] == "warn" and c["summary"].startswith("150 MB free of 900 MB")
