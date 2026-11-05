"""Every page names its scripts and styles with a version (/static/app.js?v=3f9c2a1b), so
a phone or a Cloudflare tunnel never mixes a new page with an old cached script.

Cloudflare keeps .js and .css for hours whatever the app says, so after an update a page
could load with yesterday's script, and its new buttons did nothing. The version is a
hash of the file itself, so it changes exactly when the file does.
"""

import hashlib
import re
from pathlib import Path

ASSET = re.compile(rb"""(["'(])(/static/[\w./-]+\.(?:js|css|svg))(["')])""")
_hashes: dict[str, tuple[int, str]] = {}


def version(web_dir: Path, name: str) -> str:
    path = web_dir / name
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        return ""
    seen = _hashes.get(name)
    if seen and seen[0] == mtime:
        return seen[1]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:10]
    _hashes[name] = (mtime, digest)
    return digest


def stamp(html: bytes, web_dir: Path) -> bytes:
    def add(m):
        v = version(web_dir, m.group(2).decode()[len("/static/"):])
        return m.group(1) + m.group(2) + (b"?v=" + v.encode() if v else b"") + m.group(3)
    return ASSET.sub(add, html)


def install(app, web_dir: Path):
    web_dir = Path(web_dir)

    @app.after_request
    def stamp_pages(resp):
        if resp.status_code != 200 or resp.mimetype != "text/html" or resp.is_streamed and not resp.direct_passthrough:
            return resp
        try:
            resp.direct_passthrough = False
            body = resp.get_data()
        except (RuntimeError, OSError):
            return resp
        resp.set_data(stamp(body, web_dir))
        # The page itself is checked every time (the versions inside it change without it).
        resp.headers.pop("ETag", None)
        resp.headers.pop("Last-Modified", None)
        resp.headers["Cache-Control"] = "no-cache"
        return resp
