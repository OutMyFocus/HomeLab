"""The log of collected scans (data/captures/log.csv): labels and new scans at the same time."""

import threading

from mtgscanner.captures import COLUMNS, CaptureLog


def record(n):
    return {k: "" for k in COLUMNS} | {"time": f"2026-11-18 10:00:{n % 60:02d}", "result": "recognized",
                                       "card_id": f"id{n}", "crop": f"2026-11-18/{n:06d}_card.jpg"}


def test_labels_and_new_scans_at_the_same_time_lose_nothing(tmp_path):
    log = CaptureLog(tmp_path)
    for n in range(200):
        log.finish(record(n))

    def phone():                   # a phone's scanner adds scans under its own lock
        for n in range(200, 300):
            log.finish(record(n))

    def train_tab():               # the Train tab labels old ones under the machine's lock
        for n in range(0, 100, 2):
            log.update(record(n)["crop"], verdict="saved")

    threads = [threading.Thread(target=phone), threading.Thread(target=train_tab)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = log.rows()
    assert len(rows) == 300 and len({r["crop"] for r in rows}) == 300
    assert sum(r["verdict"] == "saved" for r in rows) == 50
    assert log.counts["total"] == 300 and log.counts["saved"] == 50
    assert CaptureLog(tmp_path).counts == log.counts
    assert not list(tmp_path.glob("*.tmp"))


def test_new_scans_wait_while_the_log_is_rewritten(tmp_path):
    log = CaptureLog(tmp_path)
    log.finish(record(0))
    done = threading.Event()
    with log._lock:                # what update() holds while it rewrites the file
        t = threading.Thread(target=lambda: (log.finish(record(1)), done.set()))
        t.start()
        assert not done.wait(0.3)
    t.join(5)
    assert done.is_set() and len(log.rows()) == 2


def test_two_first_scans_write_one_header(tmp_path):
    log = CaptureLog(tmp_path)
    start = threading.Barrier(2)

    def scan(n):
        start.wait()
        log.finish(record(n))

    threads = [threading.Thread(target=scan, args=(n,)) for n in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert (tmp_path / "log.csv").read_text().count("time,camera") == 1 and len(log.rows()) == 2
