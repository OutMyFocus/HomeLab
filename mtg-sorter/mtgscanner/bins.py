"""The Bins page (/bins): choose what goes into each of the sorter's bins.

The rules themselves live in sort_rules.py. This adds the page, and a preview that
counts how your current collection would be split by rules you haven't saved yet.
"""

from flask import jsonify, request, send_from_directory

from . import config, sort_rules
from .library import holdings, read_rows


def preview(rules: dict, items: list[dict]) -> dict:
    """How many cards (and how much value) each bin would get, with a few examples."""
    from .database import Card
    out = {str(b): {"cards": 0, "value": 0.0, "examples": []} for b in sort_rules.BINS}
    for it in items:
        card = Card(it["id"], it["name"], it["set"], it["set_name"], it["number"], it["rarity"],
                    ",".join(it["colors"]) if it["known"] else None, None, None)
        b, _ = sort_rules.pick(card, it["foil"], it["price"], rules)
        slot = out[str(b)]
        slot["cards"] += it["qty"]
        slot["value"] = round(slot["value"] + (it["value"] or 0), 2)
        slot["examples"].append((it["price"] or 0, it["name"]))
    for slot in out.values():
        names = [n for _, n in sorted(slot["examples"], reverse=True)]
        slot["examples"] = list(dict.fromkeys(names))[:4]   # the most valuable, each name once
    return out


def add_bins_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def items():
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        return holdings(rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))

    def answer(rules=None):
        rules = rules or sort_rules.load()
        return jsonify({
            "rules": rules,
            "custom": sort_rules.is_custom(),
            "preview": preview(rules, items()),
            "presets": [{"id": k, "label": v[0], "hint": v[1]} for k, v in sort_rules.PRESETS.items()],
            "colors": sort_rules.COLORS,
            "rarities": sort_rules.RARITIES,
            "bins": sort_rules.BINS,
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
            rules = sort_rules.preset(js["preset"]) if js.get("preset") else sort_rules.clean(js)
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

    @app.post("/api/bins/reset")
    def bins_reset():
        sort_rules.reset()
        return answer()
