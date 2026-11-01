"""The Commander card database: every Commander-legal card, for Card lookup and the deck
builder (the part of Commander Vault that knew every card).

The scanner's own cards.db only holds the cards it can recognize. This is a separate,
small list of every card that's legal (or banned) in Commander: name, mana cost, type,
rules text, color identity, power/toughness, rarity, Game Changer and banned marks, and
EDHREC rank. It's built on the Pi from Scryfall's "Oracle Cards" file (about 25 MB to
download) and kept as data/carddb.json, plus a gzipped copy the pages download once and
keep in the browser.

    python -m mtgscanner.carddb            # build it now
"""

import gzip
import json
import time
from pathlib import Path

import requests

from . import config

BULK_API = "https://api.scryfall.com/bulk-data/oracle-cards"
SKIP_LAYOUTS = {"token", "double_faced_token", "emblem", "art_series", "scheme", "planar", "vanguard"}


def db_file() -> Path:
    return config.DATA_DIR / "carddb.json"


def gz_file() -> Path:
    return config.DATA_DIR / "carddb.json.gz"


def info() -> dict:
    """How many cards the database has and when it was built ({} if there's none yet)."""
    path = db_file()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            head = f.read(200)
        meta = json.loads(head[:head.index(',"cards"')] + "}")
    except (OSError, ValueError):
        meta = {}
    return {"cards": meta.get("n"), "built": meta.get("built") or time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)), "bytes": gz_file().stat().st_size
        if gz_file().exists() else path.stat().st_size}


def card_row(c: dict) -> dict | None:
    """One Scryfall card as a compact row, or None if it isn't a Commander card."""
    legal = (c.get("legalities") or {}).get("commander")
    if legal not in ("legal", "banned") or c.get("layout") in SKIP_LAYOUTS:
        return None
    faces = c.get("card_faces") or []
    if "oracle_text" in c:
        text = c["oracle_text"]
    elif faces:
        text = "\n//\n".join(f"{f.get('name', '')} {f.get('mana_cost', '')}\n{f.get('type_line', '')}\n"
                             f"{f.get('oracle_text', '')}" for f in faces)
    else:
        text = ""
    cost = c["mana_cost"] if "mana_cost" in c else (faces[0].get("mana_cost", "") if faces else "")
    pt = None
    if "power" in c:
        pt = f"{c['power']}/{c['toughness']}"
    elif faces and "power" in faces[0]:
        pt = f"{faces[0]['power']}/{faces[0]['toughness']}"
    row = {"n": c["name"], "m": cost or "", "v": c.get("cmc", 0), "t": c.get("type_line", ""), "o": text,
           "ci": "".join(c.get("color_identity", [])), "r": (c.get("rarity") or "")[:1]}
    if pt:
        row["pt"] = pt
    if c.get("game_changer"):
        row["gc"] = 1
    if legal == "banned":
        row["b"] = 1
    if c.get("loyalty"):
        row["l"] = c["loyalty"]
    if c.get("edhrec_rank"):
        row["e"] = c["edhrec_rank"]
    return row


def _cards_in(path: Path):
    """Each card in a Scryfall bulk file: JSON Lines (.jsonl.gz) or one big JSON list."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line or line in ("[", "]"):
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def build(src: Path, dst: Path | None = None) -> int:
    """Turn a Scryfall Oracle Cards file into carddb.json (and its .gz). Returns the card count."""
    dst = dst or db_file()
    rows = [r for r in (card_row(c) for c in _cards_in(src)) if r]
    if len(rows) < 1000:
        raise RuntimeError(f"Only {len(rows)} Commander cards found in the download, so it's kept as it was")
    rows.sort(key=lambda r: r["n"])
    built = time.strftime("%Y-%m-%dT%H:%M:%S")
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"v": 1, "n": len(rows), "built": built, "cards": rows}, separators=(",", ":"),
                      ensure_ascii=False)
    tmp = dst.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    gz_tmp = dst.with_suffix(".gz.tmp")
    with gzip.open(gz_tmp, "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(text)
    tmp.replace(dst)
    gz_tmp.replace(dst.with_name(dst.name + ".gz"))
    return len(rows)


def download(progress=None) -> int:
    """Download today's Oracle Cards file from Scryfall and rebuild the database."""
    headers = {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    meta = requests.get(BULK_API, headers=headers, timeout=20)
    meta.raise_for_status()
    meta = meta.json()
    url = meta.get("jsonl_download_uri") or meta["download_uri"]
    src = config.DATA_DIR / (".oracle-cards.jsonl.gz" if url.endswith(".gz") else ".oracle-cards.json")
    src.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, headers=headers, timeout=60, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length") or meta.get("compressed_size") or 0)
            got = 0
            with src.open("wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    got += len(chunk)
                    if progress and total:
                        progress(f"Downloading the card list, {min(99, round(got / total * 100))}%")
        if progress:
            progress("Building the card database")
        return build(src)
    finally:
        src.unlink(missing_ok=True)


def names() -> set[str]:
    """Every card name in the database, lowercase (empty if there's no database yet)."""
    try:
        data = json.loads(db_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {c["n"].lower() for c in data.get("cards", [])}


def send(request_headers):
    """The Flask response for /api/carddb: the gzipped file when the browser takes gzip."""
    from flask import Response, jsonify, send_file
    if not db_file().exists():
        return jsonify({"error": "The card database isn't built yet. Settings, Commander Vault, Update now."}), 404
    gz = gz_file()
    if gz.exists() and "gzip" in (request_headers.get("Accept-Encoding") or ""):
        resp = send_file(gz, mimetype="application/json", conditional=True, max_age=0)
        resp.headers["Content-Encoding"] = "gzip"
        resp.headers["Vary"] = "Accept-Encoding"
        return resp
    return send_file(db_file(), mimetype="application/json", conditional=True, max_age=0)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(build(Path(sys.argv[1])), "cards")
    else:
        print(download(print), "cards")
