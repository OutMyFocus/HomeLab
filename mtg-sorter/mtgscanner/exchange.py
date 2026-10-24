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


def load_rate() -> tuple[float, str]:
    """Set config.USD_TO_CAD to the latest rate. Returns (rate, date of the rate)."""
    saved = None
    try:
        saved = json.loads(CACHE.read_text())
        if time.time() - saved["fetched"] < 24 * 3600:
            return _use(saved)
    except (OSError, ValueError, KeyError):
        pass
    try:
        obs = requests.get(URL, timeout=5, headers={"User-Agent": config.USER_AGENT}).json()["observations"][-1]
        saved = {"rate": float(obs["FXUSDCAD"]["v"]), "date": obs["d"], "fetched": time.time()}
        config.DATA_DIR.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(saved))
    except (requests.RequestException, ValueError, KeyError, IndexError, OSError):
        if saved is None:
            return config.USD_TO_CAD, ""
    return _use(saved)


def _use(saved: dict) -> tuple[float, str]:
    config.USD_TO_CAD = saved["rate"]
    return saved["rate"], saved["date"]
