"""Score the scanner on fake photos made from real card pictures.

    python bench/bench.py phone 200            # 200 tuning cards, every phone scene
    python bench/bench.py machine 200 --split test
    python bench/bench.py table,bed 200 --split backs   # back faces of double-faced cards
    python bench/bench.py none_phone,none_bed 300       # photos with no card at all

Run bench/prepare.py first. Prints, per scene, how often the card is read right and
sure, read right at all, the exact printing, read WRONG (sure or likely, the bad
kind), and how long one picture takes. --out saves every result as JSON.
--repo scores another copy of the code (for example an older checkout) on the same pictures.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("kinds", help="comma list of scenes, or phone / machine / all")
p.add_argument("n", type=int, help="how many cards")
p.add_argument("--split", default="dev", choices=["dev", "test", "backs"])
p.add_argument("--repo", default=str(HERE.parent))
p.add_argument("--db", default=str(HERE / "cache" / "cards.db"))
p.add_argument("--out", default="")
p.add_argument("--workers", type=int, default=os.cpu_count() or 4)
p.add_argument("--seed", type=int, default=1)
A = p.parse_args()
CACHE = HERE / "cache"
sys.path.insert(0, A.repo)
sys.path.insert(0, str(HERE))
os.environ.setdefault("MTG_DATA_DIR", str(CACHE / "data"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import simulate as sim  # noqa: E402

G = {}


def init():
    from mtgscanner import database, printings
    m = database.Matcher(database.connect(Path(A.db)))
    m.pictures = printings.StockPictures(CACHE / "stock")
    printings.KEEP_ON_DISK = 10 ** 9
    G["m"] = m
    G["cards"] = {c["id"]: c for c in json.loads((CACHE / "cards.json").read_text())}
    G["machine"] = {}


def machine_scanner(kind):
    """A Scanner set up as on the sorter: whole cards only, bed box, bare bed known."""
    if kind not in G["machine"]:
        import app
        sc = app.Scanner(G["m"], None, None)
        H, W = 1080, 1440
        long = H * 0.83
        short = long * 63 / 88
        sc.min_card = round(long * short / (H * W) * 0.8, 4)
        pad = 0.02
        sc.bed_box = [(W / 2 - short / 2) / W - pad, (H / 2 - long / 2) / H - pad,
                      (W / 2 + short / 2) / W + pad, (H / 2 + long / 2) / H + pad]
        sc.frame_size = (W, H)
        sc.remember_empty_bed(sim.empty_bed(np.random.default_rng(3), kind), save=False)
        sc._bed_still = lambda frame, bed: True
        G["machine"][kind] = sc
    return G["machine"][kind]


def name_key(n):
    return n.split(" // ")[0].strip().lower()


def read_phone(frame):
    from mtgscanner import recognize
    out = []
    for outlines in recognize.find_cards(frame):
        for _, mt in recognize.identify_card(G["m"], frame, outlines, wait=30.0):
            out.append(mt)
    return out


def read_machine(frame, kind):
    import inspect
    from mtgscanner import recognize
    sc = machine_scanner(kind)
    kw = {"printing": True} if "printing" in inspect.signature(recognize.identify_outlines).parameters else {}
    return [sc._screen(o, recognize.identify_outlines(G["m"], frame, o, refine=False, wait=30.0, **kw))
            for o in sc._whole_cards(frame)]


def run_one(job):
    card_id, kind = job
    truth = G["cards"][card_id]
    seed = int(hashlib.md5(f"{card_id}:{kind}:{A.seed}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    if kind == "none_phone":
        frame = sim.background(rng, 1920, 1080, str(rng.choice(sim.PHONE_TABLES))).astype(np.uint8)
    elif kind == "none_bed":
        bed = sim.empty_bed(rng, "bed").astype(np.float32) * rng.uniform(0.5, 1.1)
        frame = np.clip(bed + rng.normal(0, 4, bed.shape), 0, 255).astype(np.uint8)
    else:
        folder = "large_back" if A.split == "backs" else "large"
        frame, _, _ = sim.scenario(rng, cv2.imread(str(CACHE / folder / f"{card_id}.jpg")), kind)
    t0 = time.perf_counter()
    is_phone = kind in sim.PHONE or kind == "none_phone"
    matches = read_phone(frame) if is_phone else read_machine(frame, kind.replace("none_", ""))
    res = dict(id=card_id, kind=kind, ms=(time.perf_counter() - t0) * 1000, conf=None, printing=False)
    read = [mt for mt in matches if mt is not None and mt.card is not None]
    right = [mt for mt in read if name_key(mt.card.name) == name_key(truth["name"])]
    wrong = [mt for mt in read if name_key(mt.card.name) != name_key(truth["name"])]
    if kind.startswith("none"):
        res["outcome"] = "wrong" if any(mt.confidence in ("sure", "likely") for mt in read) else "unread"
    elif any(w.confidence in ("sure", "likely") for w in wrong):
        res.update(outcome="wrong", got=min(wrong, key=lambda x: x.distance).card.name)
    elif right:
        best = min(right, key=lambda x: x.distance)
        res.update(outcome="right", conf=best.confidence, printing=best.card.id == card_id)
    else:
        res["outcome"] = "unread"
    return res


def main():
    ids = json.loads((CACHE / "split.json").read_text())[A.split][:A.n]
    kinds = {"phone": sim.PHONE, "machine": sim.MACHINE, "all": sim.PHONE + sim.MACHINE}.get(A.kinds) \
        or A.kinds.split(",")
    jobs = [(c, k) for c in ids for k in kinds]
    t = time.time()
    with Pool(A.workers, initializer=init) as pool:
        results = list(pool.imap_unordered(run_one, jobs, chunksize=4))
    if A.out:
        Path(A.out).write_text(json.dumps(results))
    by = defaultdict(list)
    for r in results:
        by[r["kind"]].append(r)
    print(f"{len(results)} pictures in {time.time() - t:.0f}s")
    print(f"{'scene':11} {'n':>5} {'sure+right':>10} {'right':>7} {'printing':>8} {'WRONG':>6} {'ms':>6}")
    for k in kinds:
        rs = by[k]
        n = len(rs)
        c = Counter(r["outcome"] for r in rs)
        sure = sum(r["outcome"] == "right" and r["conf"] == "sure" for r in rs)
        printing = sum(r["outcome"] == "right" and r["printing"] for r in rs)
        ms = np.median([r["ms"] for r in rs])
        print(f"{k:11} {n:5} {100 * sure / n:9.1f}% {100 * c['right'] / n:6.1f}% {100 * printing / n:7.1f}% "
              f"{c['wrong']:6} {ms:6.0f}")


if __name__ == "__main__":
    main()
