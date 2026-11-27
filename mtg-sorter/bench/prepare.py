"""Get everything the scanner test bench needs, into bench/cache (not in git).

    python bench/prepare.py            # all cards (about 108,000), 1000 tuning + 2000 test cards
    python bench/prepare.py --dev 200 --test 400

Steps: Scryfall's card list, a fixed random pick of tuning ("dev") and test cards
(extra borderless / showcase / old frame / double-faced cards mixed in), the small
picture of every card to build the card database from, and the large picture of
each picked card to make fake photos from.
"""

import argparse
import gzip
import json
import os
import random
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
CACHE = HERE / "cache"
HEADERS = {"User-Agent": "HomeLabMTGSorter/0.1", "Accept": "application/json"}


def card_list():
    out = CACHE / "cards.json"
    if out.exists():
        return json.loads(out.read_text())
    raw = CACHE / "default-cards.download"
    if not raw.exists():
        info = requests.get("https://api.scryfall.com/bulk-data/default-cards", headers=HEADERS, timeout=30).json()
        with requests.get(info["download_uri"], headers=HEADERS, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(raw, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    data = raw.read_bytes()
    text = (gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data).decode("utf-8")
    rows = json.loads(text) if text.lstrip().startswith("[") else [json.loads(l) for l in text.splitlines() if l.strip()]
    cards = []
    for c in rows:
        if c.get("digital") or c.get("layout") == "art_series":
            continue
        faces = c.get("card_faces") or [{}]
        pics = c.get("image_uris") or faces[0].get("image_uris")
        if not pics:
            continue
        back = faces[1].get("image_uris") if len(faces) > 1 and not c.get("image_uris") else None
        cards.append(dict(
            id=c["id"], name=c["name"], set=c["set"], cn=c.get("collector_number"), layout=c.get("layout"),
            frame=c.get("frame"), border=c.get("border_color"), full_art=c.get("full_art"),
            fe=c.get("frame_effects"), small=pics.get("small"), large=pics.get("large"),
            back_small=(back or {}).get("small"), back_large=(back or {}).get("large"),
            usd=(c.get("prices") or {}).get("usd")))
    out.write_text(json.dumps(cards))
    return cards


def special(c):
    fe = c.get("fe") or []
    return (c["border"] == "borderless" or "showcase" in fe or "extendedart" in fe or c.get("full_art")
            or c["frame"] in ("1993", "1997")
            or c["layout"] in ("token", "transform", "modal_dfc", "split", "flip", "adventure", "saga"))


def split(cards, dev_n, test_n):
    out = CACHE / "split.json"
    if out.exists():
        return json.loads(out.read_text())
    rng = random.Random(20261126)
    shuffled = list(cards)
    rng.shuffle(shuffled)
    plain_dev, plain_test = int(dev_n * 0.8), int(test_n * 0.8)
    dev = shuffled[:plain_dev]
    test = shuffled[plain_dev:plain_dev + plain_test]
    used = {c["id"] for c in dev + test}
    extra = [c for c in shuffled if special(c) and c["id"] not in used]
    dev += extra[:dev_n - plain_dev]
    test += extra[dev_n - plain_dev:dev_n - plain_dev + test_n - plain_test]
    backs = [c for c in shuffled if c.get("back_large") and c["id"] not in used][:200]
    result = {"dev": [c["id"] for c in dev], "test": [c["id"] for c in test], "backs": [c["id"] for c in backs]}
    out.write_text(json.dumps(result))
    return result


def download(jobs):
    """jobs: list of (url, path). Skips files already there."""
    session = requests.Session()
    session.headers["User-Agent"] = HEADERS["User-Agent"]
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=32))
    done, lock = [0], threading.Lock()

    def get(job):
        url, path = job
        if path.exists() and path.stat().st_size > 1000:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(5):
            try:
                r = session.get(url, timeout=30)
                if r.status_code == 200:
                    tmp = path.with_suffix(".part")
                    tmp.write_bytes(r.content)
                    os.replace(tmp, path)
                    break
            except requests.RequestException:
                pass
            time.sleep(1 + attempt)
        with lock:
            done[0] += 1
            if done[0] % 5000 == 0:
                print(f"  {done[0]} pictures", flush=True)

    with ThreadPoolExecutor(24) as ex:
        list(ex.map(get, jobs))


def _fingerprint(path):
    from PIL import Image
    from mtgscanner import vision
    try:
        return path, vision.fingerprint_pil(Image.open(path))
    except Exception:
        return path, None


def build_db(cards):
    """cards.db made the same way build_db.py makes it, from the cached small pictures."""
    from mtgscanner.database import connect
    out = CACHE / "cards.db"
    if out.exists():
        return
    by_path = {}
    for c in cards:
        by_path[CACHE / "small" / f"{c['id']}.jpg"] = ("front", c)
        if c.get("back_small"):
            by_path[CACHE / "small_back" / f"{c['id']}.jpg"] = ("back", c)
    conn = connect(out)
    with Pool() as pool:
        for path, fp in pool.imap_unordered(_fingerprint, list(by_path), chunksize=200):
            if fp is None:
                continue
            side, c = by_path[path]
            if side == "front":
                conn.execute("INSERT OR REPLACE INTO cards (id, name, set_code, set_name, collector_number, "
                             "rarity, colors, price_usd, price_usd_foil, fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (c["id"], c["name"], c["set"], c["set"], c["cn"], "", "",
                              float(c["usd"]) if c["usd"] else None, None, fp))
            else:
                conn.execute("INSERT OR REPLACE INTO faces (card_id, fingerprint) VALUES (?, ?)", (c["id"], fp))
    conn.commit()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dev", type=int, default=1000)
    p.add_argument("--test", type=int, default=2000)
    a = p.parse_args()
    CACHE.mkdir(exist_ok=True)
    print("card list")
    cards = card_list()
    picked = split(cards, a.dev, a.test)
    by_id = {c["id"]: c for c in cards}
    print(f"{len(cards)} cards; small pictures for the database")
    jobs = [(c["small"], CACHE / "small" / f"{c['id']}.jpg") for c in cards]
    jobs += [(c["back_small"], CACHE / "small_back" / f"{c['id']}.jpg") for c in cards if c.get("back_small")]
    download(jobs)
    print("large pictures of the picked cards")
    ids = picked["dev"] + picked["test"]
    jobs = [(by_id[i]["large"], CACHE / "large" / f"{i}.jpg") for i in ids]
    jobs += [(by_id[i]["back_large"], CACHE / "large_back" / f"{i}.jpg") for i in picked["backs"]]
    download(jobs)
    print("card database")
    build_db(cards)
    print("ready:", CACHE)


if __name__ == "__main__":
    main()
