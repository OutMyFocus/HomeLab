"""Today's US-to-Canadian dollar rate, from the Bank of Canada.

Only cards Commander Vault hasn't priced use this: their Scryfall USD price is
converted to CAD. The rate is saved in data/usd_cad.json and fetched again once a
day. With no internet it keeps the last saved rate, or config.USD_TO_CAD.
"""

import json
import time

import requests

from . import config

URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1"
CACHE = config.DATA_DIR / "usd_cad.json"


def _valid(saved) -> bool:
    """A saved rate that can be used: {"rate": a number above 0, "fetched": a time}."""
    return (isinstance(saved, dict) and isinstance(saved.get("rate"), (int, float)) and saved["rate"] > 0
            and isinstance(saved.get("fetched"), (int, float)))


def load_rate() -> tuple[float, str]:
    """Set config.USD_TO_CAD to the latest rate. Returns (rate, date of the rate).
    Called at start and then every hour (vault.Weekly.loop); it only asks the Bank of
    Canada when the saved rate is a day old."""
    try:
        saved = json.loads(CACHE.read_text())
    except (OSError, ValueError):
        saved = None
    if not _valid(saved):
        saved = None   # missing or damaged: fetch it again
    if saved and time.time() - saved["fetched"] < 24 * 3600:
        return _use(saved)
    try:
        obs = requests.get(URL, timeout=5, headers={"User-Agent": config.USER_AGENT}).json()["observations"][-1]
        fresh = {"rate": float(obs["FXUSDCAD"]["v"]), "date": str(obs["d"]), "fetched": time.time()}
        if not fresh["rate"] > 0:
            raise ValueError("no rate")
        saved = fresh
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        tmp.write_text(json.dumps(saved))
        tmp.replace(CACHE)
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError, OSError):
        if saved is None:
            return config.USD_TO_CAD, ""
    return _use(saved)


def _use(saved: dict) -> tuple[float, str]:
    config.USD_TO_CAD = float(saved["rate"])
    return config.USD_TO_CAD, str(saved.get("date") or "")
