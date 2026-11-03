"""Scan history (the History page, /history): your scanning sessions, day by day.

There's no separate log: sessions are worked out from the "Scanned at" time of each row
in data/collection.csv. Cards saved within half an hour of each other count as one
session.
"""

from datetime import datetime, timedelta

from flask import Response, jsonify, request, send_from_directory

from . import config
from .library import export, holdings, qty, read_rows, write_rows

GAP = timedelta(minutes=30)


def _when(row) -> datetime | None:
    try:
        return datetime.fromisoformat(str(row.get("Scanned at", "")).strip())
    except ValueError:
        return None


def _price(row) -> float:
    try:
        return float(row.get("Price CAD") or 0)
    except ValueError:
        return 0.0


def sessions(rows: list[dict]) -> list[dict]:
    """Newest first: {start, end, cards, value, top, bins, rows: [...]}."""
    timed = sorted(((t, r) for r in rows if (t := _when(r))), key=lambda x: x[0])
    groups: list[list] = []
    for t, r in timed:
        if groups and t - groups[-1][-1][0] <= GAP:
            groups[-1].append((t, r))
        else:
            groups.append([(t, r)])
    out = []
    for g in reversed(groups):
        bins: dict[str, int] = {}
        for _, r in g:
            bins[r.get("Bin") or "?"] = bins.get(r.get("Bin") or "?", 0) + qty(r)
        top_t, top = max(g, key=lambda x: _price(x[1]))
        out.append({
            "start": g[0][0].isoformat(timespec="seconds"),
            "end": g[-1][0].isoformat(timespec="seconds"),
            "minutes": round((g[-1][0] - g[0][0]).total_seconds() / 60),
            "cards": sum(qty(r) for _, r in g),
            "value": round(sum(_price(r) * qty(r) for _, r in g), 2),
            "foils": sum(qty(r) for _, r in g if (r.get("Foil") or "").lower() == "foil"),
            "top": {"name": top.get("Name", ""), "set": top.get("Set code", ""), "price": _price(top) or None,
                    "id": top.get("Scryfall ID", "")},
            "bins": bins,
            "rows": [{"name": r.get("Name", ""), "set": r.get("Set code", ""), "number": r.get("Collector number", ""),
                      "foil": (r.get("Foil") or "").lower() == "foil", "qty": qty(r),
                      "price": _price(r) or None, "bin": r.get("Bin", ""), "time": t.strftime("%H:%M:%S"),
                      "id": r.get("Scryfall ID", "")} for t, r in g],
        })
    return out


def per_day(rows: list[dict], days: int = 30, today=None) -> list[dict]:
    """Cards and value scanned on each of the last `days` days (oldest first)."""
    today = today or datetime.now().date()
    counts = {(today - timedelta(days=i)).isoformat(): {"cards": 0, "value": 0.0} for i in range(days)}
    for r in rows:
        t = _when(r)
        if t and (d := t.date().isoformat()) in counts:
            counts[d]["cards"] += qty(r)
            counts[d]["value"] = round(counts[d]["value"] + _price(r) * qty(r), 2)
    return [{"day": d} | v for d, v in sorted(counts.items())]


def _in(row, start, end) -> bool:
    t = _when(row)
    return t is not None and start <= t <= end


def _span(js):
    try:
        return datetime.fromisoformat(str(js["start"])), datetime.fromisoformat(str(js["end"]))
    except (KeyError, ValueError):
        raise ValueError("Send the session's start and end")


def add_history_routes(app, scanner, web_dir):
    def body() -> dict:
        js = request.get_json(force=True, silent=True)
        return js if isinstance(js, dict) else {}

    def answer():
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
        found = sessions(rows)
        return jsonify({"sessions": found[:300], "total_sessions": len(found), "days": per_day(rows)})

    @app.get("/history")
    def history_page():
        return send_from_directory(web_dir, "history.html")

    @app.get("/api/history")
    def history():
        return answer()

    @app.post("/api/history/delete")
    def history_delete():
        """Take a whole session's cards back out of the collection (a test run, say)."""
        try:
            start, end = _span(body())
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        with scanner.lock:
            rows = read_rows(config.COLLECTION_CSV)
            keep = [r for r in rows if not _in(r, start, end)]
            if len(keep) == len(rows):
                return jsonify({"error": "No cards from that session are left"}), 404
            write_rows(config.COLLECTION_CSV, keep)
        return answer()

    @app.post("/api/history/export")
    def history_export():
        js = body()
        try:
            start, end = _span(js)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        with scanner.lock:
            rows = [r for r in read_rows(config.COLLECTION_CSV) if _in(r, start, end)]
        items = holdings(rows, scanner.matcher, scanner.vault, getattr(scanner, "live", None))
        try:
            text, name, mime = export(items, str(js.get("format", "manabox")))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        name = name.replace("collection-", f"session-{start:%Y-%m-%d-%H%M}-")
        return Response(text, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{name}"'})
