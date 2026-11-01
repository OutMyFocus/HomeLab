"""Commander Vault, built into the sorter.

Commander Vault used to be a separate page on claude.ai with its own collection, decks
and prices. Everything it did now lives here, on the Pi:

  * the weekly Canadian price check (ca_prices.py) and the Commander card database
    (carddb.py), run in the background once a week, or now from Settings;
  * importing: a ManaBox CSV, or everything saved in Commander Vault (its "export for the
    sorter" file: collection sources, decks, wishlist, trade binder, games and prices);
  * sources: every import is its own source in collection.csv (the Source column), so a
    bad import can be removed in one go.
"""

import csv
import io
import json
import re
import threading
import time
from datetime import datetime
from urllib.parse import quote
from pathlib import Path

from flask import jsonify, request, send_from_directory

from . import ca_prices, carddb, config, decks, play, wishlist
from .collection import append_rows, ensure_columns
from .library import read_rows, write_rows
from .live import API, card_from_scryfall
from .sorting import card_price
from .vault_prices import VaultPrices

WEEK = 7 * 24 * 3600
SCANNED = "Scanned with the sorter"


def status_file() -> Path:
    return config.DATA_DIR / "vault_status.json"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


# --- Cards to add: turning Vault and ManaBox rows into collection.csv rows ------------------

def resolve(live, cards: list[dict]) -> dict:
    """Scryfall's card for each {n, set, cn}, 75 per request. Returns {(name, set, cn): card json};
    cards it can't find (or everything, offline) are left out."""
    found: dict = {}
    if not live:
        return found
    exact = [c for c in cards if c.get("set") and c.get("cn")]
    by_name = [c for c in cards if not (c.get("set") and c.get("cn"))]

    def key(c):
        return (c["n"], (c.get("set") or "").upper(), str(c.get("cn") or ""))

    for start in range(0, len(exact), 75):
        chunk = exact[start:start + 75]
        page = live._get(f"{API}/cards/collection", {"identifiers": [
            {"set": c["set"].lower(), "collector_number": str(c["cn"])} for c in chunk]})
        if not page:
            return found
        got = {(js["set"].upper(), js["collector_number"]): js for js in page.get("data", [])}
        for c in chunk:
            js = got.get((c["set"].upper(), str(c["cn"])))
            if js:
                found[key(c)] = js
            else:
                by_name.append(c)
    for start in range(0, len(by_name), 75):
        chunk = by_name[start:start + 75]
        page = live._get(f"{API}/cards/collection", {"identifiers": [{"name": c["n"]} for c in chunk]})
        if not page:
            return found
        got = {}
        for js in page.get("data", []):
            got[js["name"].lower()] = js
            got.setdefault(js["name"].split(" // ")[0].lower(), js)
        for c in chunk:
            if js := got.get(c["n"].lower()) or got.get(c["n"].split(" // ")[0].lower()):
                found[key(c)] = js
    return found


def to_rows(scanner, cards: list[dict], source: str, added: str) -> list[dict]:
    """collection.csv rows for imported cards ({n, q, set, cn, f, pr}), filled in from
    Scryfall when it's reachable (so they get pictures, rarity and colors)."""
    live = getattr(scanner, "live", None)
    found = resolve(live, cards)
    when = (added or datetime.now().isoformat(timespec="seconds"))[:19].replace("Z", "")
    if "T" not in when:
        when += "T12:00:00"
    rows = []
    for c in cards:
        js = found.get((c["n"], (c.get("set") or "").upper(), str(c.get("cn") or "")))
        foil = bool(c.get("f"))
        row = {"Name": c["n"], "Quantity": max(1, int(c.get("q") or 1)), "Set code": (c.get("set") or "").upper(),
               "Set name": "", "Collector number": str(c.get("cn") or ""), "Foil": "foil" if foil else "normal",
               "Rarity": "", "Scryfall ID": "", "Price CAD": "", "Price source": "", "Bin": "",
               "Scanned at": when, "Source": source}
        if js:
            card = card_from_scryfall(js)
            scanner.matcher.remember(card)
            if live:
                live._remember(js)
            row.update({"Name": card.name, "Set code": card.set_code.upper(), "Set name": card.set_name,
                        "Collector number": card.collector_number, "Rarity": card.rarity, "Scryfall ID": card.id})
            price, how = card_price(card, foil, scanner.vault, live)
        else:
            price, how = None, ""
        if c.get("pr") is not None:
            price, how = float(c["pr"]), "Price when it was imported"
        if price is not None:
            row["Price CAD"], row["Price source"] = f"{price:.2f}", how
        rows.append(row)
    return rows


def manabox_cards(text: str) -> list[dict]:
    """The cards in a ManaBox CSV export (or any CSV with a Name column)."""
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    rows = [r for r in reader if any(x.strip() for x in r)]
    if len(rows) < 2:
        raise ValueError("The file has no card rows")
    head = [h.strip().lower() for h in rows[0]]

    def col(*names):
        return next((head.index(n) for n in names if n in head), -1)

    i_name, i_qty, i_set = col("name", "card name"), col("quantity", "count", "qty"), col("set code", "edition", "set")
    i_cn, i_foil = col("collector number", "card number", "number"), col("foil", "finish")
    i_price, i_cur, i_proxy = col("purchase price", "price cad"), col("purchase price currency"), col("proxy")
    if i_name < 0:
        raise ValueError("This doesn't look like a ManaBox export: it has no Name column")
    cards = []
    for r in rows[1:]:
        cell = lambda i: r[i].strip() if 0 <= i < len(r) else ""   # noqa: E731
        name = cell(i_name)
        if not name or cell(i_proxy).lower() == "true":
            continue
        try:
            q = max(1, int(float(cell(i_qty) or 1)))
        except ValueError:
            q = 1
        price = None
        if cell(i_price) and (i_cur < 0 or cell(i_cur) in ("", "CAD")):
            try:
                price = float(cell(i_price))
            except ValueError:
                pass
        card = {"n": name, "q": q, "set": cell(i_set), "cn": cell(i_cn),
                "f": 1 if cell(i_foil).lower() not in ("", "normal", "nonfoil", "no", "false", "0") else 0}
        if price is not None:
            card["pr"] = price
        cards.append(card)
    if not cards:
        raise ValueError("The file has no card rows")
    return cards


# --- Sources ---------------------------------------------------------------------------------

def sources(rows: list[dict]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in rows:
        name = (r.get("Source") or "").strip() or SCANNED
        s = out.setdefault(name, {"name": name, "cards": 0, "added": r.get("Scanned at", ""), "scanned": name == SCANNED})
        try:
            s["cards"] += max(1, int(float(r.get("Quantity") or 1)))
        except ValueError:
            s["cards"] += 1
        s["added"] = min(s["added"] or r.get("Scanned at", ""), r.get("Scanned at", "") or s["added"])
    return sorted(out.values(), key=lambda s: (s["scanned"], s["added"]))


def unique_source(rows: list[dict], name: str) -> str:
    taken = {(r.get("Source") or "").strip() for r in rows}
    name = (str(name or "").strip() or "ManaBox import")[:80]
    if name not in taken and name != SCANNED:
        return name
    n = 2
    while f"{name} ({n})" in taken:
        n += 1
    return f"{name} ({n})"


# --- Importing everything from Commander Vault ------------------------------------------------

def deck_text(d: dict) -> str:
    """A Vault deck ({commander, list: [[name, qty]]}) as a decklist the Decks page reads."""
    lines = []
    if d.get("commander"):
        lines += ["Commander", f"1 {d['commander']}", "", "Deck"]
    lines += [f"{int(q)} {n}" for n, q in d.get("list", []) if n]
    return "\n".join(lines)


def import_vault(scanner, data: dict) -> dict:
    """Bring in an export from Commander Vault. Anything already imported is skipped, so
    importing the same file twice does nothing the second time."""
    if not isinstance(data, dict) or not (data.get("commander_vault") or data.get("collection") or data.get("decks")):
        raise ValueError("This isn't a Commander Vault export")
    did = {"sources": 0, "cards": 0, "decks": 0, "wishlist": 0, "trade": 0, "games": 0, "prices": 0, "guides": 0}

    prices = data.get("prices") or {}
    if prices.get("prices"):
        have = ca_prices.load()
        if have.get("date") != prices.get("date") and (not have.get("prices") or not have.get("checked")
                                                       or _age(have["checked"]) > WEEK):
            ca_prices.save({**prices, "checked": prices.get("checked") or "", "imported": True})
            scanner.vault = VaultPrices.load(config.VAULT_PRICES)
            did["prices"] = len(prices["prices"])

    with scanner.lock:
        rows = read_rows(config.COLLECTION_CSV)
    taken = {(r.get("Source") or "").strip() for r in rows}
    new_rows = []
    for batch in data.get("collection") or []:
        name = str(batch.get("name") or "Commander Vault").strip()[:80]
        cards = [c for c in batch.get("cards") or [] if isinstance(c, dict) and c.get("n")]
        if not cards or name in taken:
            continue
        taken.add(name)
        new_rows += to_rows(scanner, cards, name, str(batch.get("added") or ""))
        did["sources"] += 1
        did["cards"] += sum(max(1, int(c.get("q") or 1)) for c in cards)
    if new_rows:
        with scanner.lock:
            append_rows(config.COLLECTION_CSV, new_rows)

    saved = {d["id"] for d in decks.load_decks()}
    guides = data.get("guides") or {}
    guide_dir = config.DATA_DIR / "guides"
    for name, html in guides.items():
        if re.fullmatch(r"[a-z0-9_-]{1,40}\.html", name) and isinstance(html, str):
            guide_dir.mkdir(parents=True, exist_ok=True)
            (guide_dir / name).write_text(html.replace('href="index.html"', 'href="/decks"'), encoding="utf-8")
            did["guides"] += 1
    for d in data.get("decks") or []:
        deck_id = "cv-" + re.sub(r"[^a-z0-9-]", "", str(d.get("id", "")).lower())[:20]
        if deck_id == "cv-" or deck_id in saved:
            continue
        guide = str(d.get("guide") or "")
        decks.save_deck(d.get("name"), deck_text(d), deck_id, create=True,
                        extra={"proxied": bool(d.get("proxied")), "accent": str(d.get("accent") or ""),
                               "guide": f"/guides/{guide}" if guide in guides else ""})
        did["decks"] += 1

    trades = data.get("trades") or {}
    for w in trades.get("wants") or []:
        try:
            wishlist.add(w.get("n"), w.get("max"))
            did["wishlist"] += 1
        except ValueError:
            pass
    did["trade"] = play.add_to_binder([{"name": c.get("n"), "set": c.get("set", ""), "number": c.get("cn", ""),
                                        "foil": bool(c.get("f")), "qty": c.get("q", 1)}
                                       for c in trades.get("cards") or [] if c.get("n")])
    did["games"] = play.import_games(data.get("games") or [])
    return did


# --- The weekly jobs ---------------------------------------------------------------------------

class Weekly:
    """Runs the price check and the card database update in the background: once a week
    on its own, or now when asked. One job at a time."""

    def __init__(self, scanner, offline: bool = False):
        self.scanner, self.offline = scanner, offline
        self.lock = threading.Lock()
        self.job = None          # "prices" or "carddb" while one runs
        self.message = ""
        self.progress = None     # [done, total]
        self.error = ""

    def status(self) -> dict:
        st = _read(status_file(), {})
        prices = ca_prices.load()
        return {
            "job": self.job, "message": self.message, "progress": self.progress, "error": self.error,
            "offline": self.offline,
            "prices": {"date": prices.get("date", ""), "checked": prices.get("checked") or st.get("prices_checked", ""),
                       "cards": len(prices.get("prices") or {}), "printings": len(prices.get("printings") or {}),
                       "imported": bool(prices.get("imported"))},
            "carddb": carddb.info(),
            "last": st,
        }

    def start(self, job: str) -> bool:
        with self.lock:
            if self.job:
                return False
            self.job, self.message, self.progress, self.error = job, "Starting", None, ""
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return True

    def _run(self, job: str):
        try:
            if job == "carddb":
                n = carddb.download(lambda m: setattr(self, "message", m))
                self._note("carddb_built", f"{n:,} cards")
            else:
                self._prices()
        except Exception as e:   # the network, a store, Scryfall: try again next time
            self.error = f"{'Price check' if job == 'prices' else 'Card database update'} didn't finish: {e}"
            self._note(f"{job}_error", str(e))
        finally:
            self.job, self.progress = None, None

    def _prices(self):
        with self.scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        deck_names = [x["name"] for d in decks.load_decks() for x in decks.parse(d.get("text", ""))]
        names, keys = ca_prices.wanted(rows, deck_names, [i["name"] for i in wishlist.load_items()],
                                       [c["name"] for c in play.load_binder()])

        def progress(done, total, what):
            self.progress = [done, total]
            self.message = f"Checking Canadian prices: {done} of {total}"
        data = ca_prices.check(names, keys, progress=progress)
        self.scanner.vault = VaultPrices.load(config.VAULT_PRICES)
        self._note("prices_checked", f"{len(data['prices'])} cards")

    def _note(self, key, value):
        st = _read(status_file(), {})
        st[key] = value
        st[key + "_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _write(status_file(), st)

    def due(self) -> str | None:
        """The job that's due, if any: the card database first, then prices."""
        st = _read(status_file(), {})
        if not carddb.db_file().exists() or time.time() - carddb.db_file().stat().st_mtime > WEEK:
            if not _recent(st.get("carddb_error_at")):
                return "carddb"
        prices = ca_prices.load()
        checked = prices.get("checked") or ""
        if not prices.get("prices") or not checked or _age(checked) > WEEK:
            if not _recent(st.get("prices_error_at")):
                return "prices"
        return None

    def loop(self, first_wait: float = 120):
        """Check every hour whether a job is due (started by app.py, not in tests)."""
        time.sleep(first_wait)
        while not self.offline:
            try:
                if (job := self.due()) and not self.job:
                    self.start(job)
            except Exception:
                pass
            time.sleep(3600)


def _age(iso: str) -> float:
    try:
        return time.time() - datetime.fromisoformat(iso).timestamp()
    except (TypeError, ValueError):
        return float("inf")


def _recent(iso, hours: float = 12) -> bool:
    return bool(iso) and _age(iso) < hours * 3600


# --- Web routes -------------------------------------------------------------------------------

def add_vault_routes(app, scanner, web_dir, weekly: Weekly | None = None):
    weekly = weekly or Weekly(scanner, offline=getattr(scanner, "live", None) is None)
    app.config["weekly"] = weekly

    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    @app.get("/cards")
    def cards_page():
        return send_from_directory(web_dir, "cards.html")

    @app.get("/api/carddb")
    def card_database():
        return carddb.send(request.headers)

    @app.get("/api/cards/number")
    def cards_by_number():
        """Printings with this collector number (and set), from Scryfall: Card lookup's "FRA 419"."""
        set_code = re.sub(r"[^a-z0-9]", "", str(request.args.get("set", "")).lower())[:6]
        number = re.sub(r"[^0-9a-z★]", "", str(request.args.get("cn", "")).lower())[:8]
        live = getattr(scanner, "live", None)
        if not (set_code or number):
            return jsonify({"cards": []})
        if live is None:
            return jsonify({"error": "Number search needs the internet (the app is offline)"}), 400
        q = " ".join(x for x in (f"set:{set_code}" if set_code else "", f"cn:{number}" if number else "",
                                 "game:paper", "lang:en") if x)
        page = live._get(f"{API}/cards/search?q={quote(q)}&unique=prints&order=set")
        cards = [{"name": js["name"], "set": js["set"].upper(), "number": js["collector_number"],
                  "set_name": js.get("set_name", "")} for js in (page or {}).get("data", [])]
        return jsonify({"cards": cards})

    @app.get("/guides/<name>")
    def guide(name):
        return send_from_directory(config.DATA_DIR / "guides", name)

    @app.get("/api/vault")
    def vault_status():
        return jsonify(weekly.status())

    @app.post("/api/vault/run")
    def vault_run():
        job = body().get("job")
        if job not in ("prices", "carddb"):
            return jsonify({"error": "Which job? prices or carddb"}), 400
        if weekly.offline:
            return jsonify({"error": "The app was started with --offline, so it can't reach the stores"}), 400
        if not weekly.start(job):
            return jsonify({"error": "Already working on it"}), 409
        return jsonify(weekly.status())

    @app.get("/api/vault/prices")
    def vault_prices():
        """The Canadian store prices, for Card lookup and the deck builder."""
        data = ca_prices.load()
        return jsonify({k: data.get(k) for k in ("date", "checked", "stores", "prices", "printings", "prev")})

    @app.post("/api/vault/import")
    def vault_import():
        try:
            did = import_vault(scanner, body())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"imported": did, "status": weekly.status()})

    @app.get("/api/sources")
    def sources_list():
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        return jsonify({"sources": sources(rows)})

    @app.post("/api/sources/manabox")
    def sources_manabox():
        """{csv: the file's text, name: what to call this source}."""
        js = body()
        try:
            cards = manabox_cards(str(js.get("csv") or ""))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if js.get("preview"):
            return jsonify({"cards": sum(c["q"] for c in cards), "rows": len(cards),
                            "repeats": [f"{c['q']}x {c['n']}" for c in cards
                                        if c["q"] >= 5 and c["n"].lower() not in ca_prices.BASICS][:12]})
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        name = unique_source(rows, js.get("name"))
        new = to_rows(scanner, cards, name, "")
        with scanner.lock:
            append_rows(config.COLLECTION_CSV, new)
            rows = read_rows(config.COLLECTION_CSV)
        return jsonify({"source": name, "cards": sum(c["q"] for c in cards), "sources": sources(rows)})

    @app.post("/api/sources/remove")
    def sources_remove():
        name = str(body().get("name") or "").strip()
        if not name or name == SCANNED:
            return jsonify({"error": "Pick an imported source. Scanned cards are removed on the History page"}), 400
        with scanner.lock:
            ensure_columns(config.COLLECTION_CSV)
            rows = read_rows(config.COLLECTION_CSV)
            keep = [r for r in rows if (r.get("Source") or "").strip() != name]
            if len(keep) == len(rows):
                return jsonify({"error": "There's no source called that"}), 404
            write_rows(config.COLLECTION_CSV, keep)
        return jsonify({"removed": len(rows) - len(keep), "sources": sources(keep)})

