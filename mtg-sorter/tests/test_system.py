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
    assert s["feeder_defaults"] == {"seconds": 0.8, "speed": 0.7}
    s = client.post("/api/machine/reset", json={}).get_json()
    assert not s["customized"] and s["parts"]["pins"]["positions"]["down"] == config.SERVOS["pins"][1]["down"]
    assert client.post("/api/machine/save", json={"part": "pins", "position": "sideways", "angle": 5}).status_code == 400


def test_moving_parts_test(client, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    r = client.post("/api/machine/test", json={}).get_json()
    assert [t["part"] for t in r["test"]] == [*config.SERVOS, "feeder"]
    assert all(t["ok"] for t in r["test"])
