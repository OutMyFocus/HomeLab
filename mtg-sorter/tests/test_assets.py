"""Pages link their scripts with a version, so a cache (Cloudflare, a phone) can't pair a
new page with an old script."""

import re

from app import WEB, Scanner, create_app
from mtgscanner import config
from test_scanner import db  # noqa: F401  (db is a fixture)


def test_pages_link_versioned_scripts(db, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    client = create_app(Scanner(db, None, source=None)).test_client()
    for page in ("/settings", "/", "/collection", "/static/login.html"):
        r = client.get(page)
        html = r.get_data(as_text=True)
        links = re.findall(r'/static/[\w./-]+\.(?:js|css)[^"\']*', html)
        assert links and all(re.search(r"\?v=[0-9a-f]{10}$", link) for link in links), (page, links)
        assert "ETag" not in r.headers and r.headers["Cache-Control"] == "no-cache"
    # The version follows the file.
    v = re.search(r"/static/accounts\.js\?v=(\w+)", client.get("/settings").get_data(as_text=True)).group(1)
    import hashlib
    assert v == hashlib.sha256((WEB / "accounts.js").read_bytes()).hexdigest()[:10]
    # The scripts themselves still load with the version on.
    assert client.get(f"/static/accounts.js?v={v}").status_code == 200
