"""The Bins page (/bins): choose what goes into each of the sorter's bins.

The rules themselves live in sort_rules.py. This adds the page, and a preview that
counts how your current collection would be split by rules you haven't saved yet.
"""

from flask import jsonify, request, send_from_directory

from . import accounts, config, decks, sort_rules, wishlist
from .library import holdings, read_rows


def preview(rules: dict, items: list[dict], taken: dict | None = None) -> dict:
    """How many cards (and how much value) each bin would get, with a few examples. Wanted
    cards are counted up to the listed number of copies, as a sort run pulls them; `taken`
    is filled with {name key: copies pulled} for wanted_summary."""
    from .database import Card
    out = {str(b): {"cards": 0, "value": 0.0, "examples": []} for b in sort_rules.BINS}
    want = sort_rules.wanted_counts(rules)
    limit = (rules.get("wanted") or {}).get("limit", True)
    taken = {} if taken is None else taken

    def add(b, qty, it):
        slot = out[str(b)]
        slot["cards"] += qty
        each = (it["value"] or 0) / it["qty"] if it["qty"] else 0
        slot["value"] = round(slot["value"] + each * qty, 2)
        slot["examples"].append((it["price"] or 0, it["name"]))

    for it in items:
        card = Card(it["id"], it["name"], it["set"], it["set_name"], it["number"], it["rarity"],
                    ",".join(it["colors"]) if it["known"] else None, None, None)
        qty = it["qty"]
        key = sort_rules.wanted_for(card, rules, taken)
        if key:
            pulled = min(qty, want[key] - taken.get(key, 0)) if limit else qty
            taken[key] = taken.get(key, 0) + pulled
            add(rules["wanted"]["bin"], pulled, it)
            qty -= pulled
        if qty > 0:
            b, _ = sort_rules.pick(card, it["foil"], it["price"], rules, taken)
            add(b, qty, it)
    for slot in out.values():
        names = [n for _, n in sorted(slot["examples"], reverse=True)]
        slot["examples"] = list(dict.fromkeys(names))[:4]   # the most valuable, each name once
    return out


def wanted_summary(rules: dict, taken: dict) -> dict:
    """How much of the wanted list your collection already has (or a run has pulled)."""
    want = sort_rules.wanted_counts(rules)
    names = {sort_rules.name_key(c["name"]): c["name"] for c in (rules.get("wanted") or {}).get("cards", [])}
    missing = [{"name": names.get(k, k), "qty": q - taken.get(k, 0)} for k, q in want.items() if taken.get(k, 0) < q]
    return {"cards": sum(want.values()), "found": sum(min(taken.get(k, 0), q) for k, q in want.items()),
            "different": len(want), "missing": missing[:300]}


def add_bins_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def items():
        with scanner.lock:
            rows = read_rows(accounts.collection_csv())
        return holdings(rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))

    def answer(rules=None):
        rules = rules or sort_rules.load()
        taken: dict[str, int] = {}
        split = preview(rules, items(), taken)
        return jsonify({
            "rules": rules,
            "custom": sort_rules.is_custom(),
            "preview": split,
            "wanted": wanted_summary(rules, taken),
            "presets": [{"id": k, "label": v[0], "hint": v[1]} for k, v in sort_rules.PRESETS.items()],
            "colors": sort_rules.COLORS,
            "rarities": sort_rules.RARITIES,
            "bins": sort_rules.BINS,
            "decks": [{"id": d["id"], "name": d.get("name") or "Untitled deck"} for d in decks.load_decks()],
            "wishlist": len(wishlist.load_items()),
        })

    @app.get("/bins")
    def bins_page():
        return send_from_directory(web_dir, "bins.html")

    @app.get("/api/bins")
    def bins_get():
        return answer()

    @app.post("/api/bins/preview")
    def bins_preview():
        """Rules from the page, checked but not saved, or {preset: name}."""
        js = body()
        try:
            rules = (sort_rules.preset(js["preset"], js.get("wanted")) if js.get("preset")
                     else sort_rules.clean(js))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return answer(rules)

    @app.post("/api/bins")
    def bins_save():
        try:
            rules = sort_rules.save(body())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return answer(rules)

    @app.post("/api/bins/wanted/list")
    def bins_wanted_list():
        """A list for the wanted panel, from {deck: id} or {wishlist: true}: {text, source}."""
        js = body()
        if js.get("deck"):
            deck = next((d for d in decks.load_decks() if d["id"] == str(js["deck"])), None)
            if deck is None:
                return jsonify({"error": "That deck isn't saved"}), 404
            return jsonify({"text": deck.get("text") or "", "source": deck.get("name") or "Deck"})
        if js.get("wishlist"):
            items = wishlist.load_items()
            return jsonify({"text": "\n".join(f"{max(1, int(i.get('qty') or 1))} {i['name']}" for i in items),
                            "source": "Wishlist"})
        return jsonify({"error": "Pick a deck or the wishlist"}), 400

    @app.post("/api/bins/wanted")
    def bins_wanted_save():
        """Change only the wanted list and keep the rest of the saved rules (the deck page's
        Pull from bulk button): {on, bin, text | cards | deck, ...}."""
        js = body()
        current = sort_rules.load()
        wanted = {**current.get("wanted", {}), **js}
        if js.get("deck"):
            deck = next((d for d in decks.load_decks() if d["id"] == str(js["deck"])), None)
            if deck is None:
                return jsonify({"error": "That deck isn't saved"}), 404
            wanted.update(text=deck.get("text") or "", source=deck.get("name") or "Deck")
        if "text" in js or js.get("deck"):
            wanted.pop("cards", None)
        try:
            rules = sort_rules.save({**current, "wanted": wanted})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        return answer(rules)

    @app.post("/api/bins/reset")
    def bins_reset():
        sort_rules.reset()
        return answer()
