"""The News page: feeds, the Wizards news page, Scryfall sets and previews, caching."""

from datetime import date, datetime, timezone

import pytest
import requests

from app import Scanner, create_app
from mtgscanner import config
from mtgscanner.news import (News, clean_text, parse_feed, parse_previews, parse_sets, parse_wizards_article,
                             parse_wizards_list, safe_url, tags_for)
from test_scanner import db  # noqa: F401  (db is a fixture)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>EDHREC</title>
  <item>
    <title>Older &amp; wiser</title><link>https://edhrec.com/articles/older/</link>
    <dc:creator><![CDATA[Someone]]></dc:creator><pubDate>Mon, 02 Nov 2026 10:00:00 +0000</pubDate>
    <category><![CDATA[Articles]]></category>
    <description><![CDATA[<p>Short <b>summary</b>.</p><p>The post Older appeared first on EDHREC.</p>]]></description>
    <content:encoded><![CDATA[<img src="https://edhrec.com/pic.jpg"><p>Body</p>]]></content:encoded>
  </item>
  <item>
    <title>Banned and Restricted Announcement</title><link>https://edhrec.com/articles/bans/</link>
    <pubDate>Tue, 03 Nov 2026 10:00:00 +0000</pubDate><description>Big changes</description>
  </item>
  <item><title>No link</title></item>
  <item><title>Sneaky</title><link>javascript:alert(1)</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>MTGGoldfish</title>
  <entry>
    <published>2026-11-03T18:30:20Z</published>
    <link rel="alternate" type="text/html" href="https://www.mtggoldfish.com/articles/boosters"/>
    <title>I Opened Star Trek Collector Boosters</title>
    <summary>Can we open an autographed card?</summary>
    <author><name>SaffronOlive</name></author>
  </entry>
</feed>"""

WIZ_LIST = """
<div data-article-hub-card-v="1.8.1"><div class="cat">Announcements</div>
  <h3 class="x">Banned and Restricted Announcement &ndash; November 10, 2026</h3>
  <div><p>Changes to <i>Standard</i>.</p></div>
  <a href="/en/news/announcements/banned-and-restricted-november-10-2026">read</a></div>
<div data-article-hub-card-v="1.8.1"><h3>Star Trek Mechanics</h3>
  <a href="/en/news/feature/star-trek-mechanics">read</a></div>
<article data-article-card-v="1.9.1"><a href="/en/news/feature">Feature</a>
  <a href="/en/news/feature/star-trek-mechanics"><h3>Star Trek Mechanics</h3></a></article>
<article data-article-card-v="1.9.1"><a href="/en/news/mtg-arena/terms"><h3>Arena Direct Terms</h3></a></article>
"""

WIZ_ARTICLE = """<meta data-hid="og:image" property="og:image" content="https://images.ctfassets.net/a/b/c/pic.webp">
<time>Nov 10, 2026</time><script>window.__NUXT__={publishedDateTime:"2026-11-10T09:00-08:00"}</script>"""

SETS = {"data": [
    {"code": "trk", "name": "Star Trek", "set_type": "expansion", "released_at": "2026-11-13", "card_count": 581,
     "icon_svg_uri": "https://svgs.scryfall.io/sets/trk.svg", "scryfall_uri": "https://scryfall.com/sets/trk"},
    {"code": "ttrk", "name": "Star Trek Tokens", "set_type": "token", "released_at": "2026-11-13", "card_count": 27},
    {"code": "nau", "name": "Nauctis", "set_type": "expansion", "released_at": "2027-02-05", "card_count": 0},
    {"code": "fra", "name": "Last Month", "set_type": "expansion", "released_at": "2026-10-02", "card_count": 300},
    {"code": "old", "name": "Long Ago", "set_type": "expansion", "released_at": "2025-01-01", "card_count": 300},
    {"code": "yx", "name": "Alchemy", "set_type": "alchemy", "released_at": "2026-12-01", "digital": True},
]}

CARDS = {"data": [
    {"id": "a1", "name": "Picard", "set": "trk", "set_name": "Star Trek", "rarity": "mythic",
     "image_uris": {"normal": "https://cards.scryfall.io/normal/a1.jpg"}, "scryfall_uri": "https://scryfall.com/card/trk/1/picard?utm_source=api",
     "released_at": "2026-11-13", "preview": {"source": "Wizards", "source_uri": "https://magic.wizards.com", "previewed_at": "2026-10-20"}},
    {"id": "b2", "name": "Two Faces // Other", "set": "trk", "set_name": "Star Trek", "rarity": "rare",
     "card_faces": [{"image_uris": {"normal": "https://cards.scryfall.io/normal/b2.jpg"}}], "scryfall_uri": "https://scryfall.com/card/trk/2/x"},
]}


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "COLLECTION_CSV", tmp_path / "collection.csv")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")


class Web:
    """Stands in for the internet: url -> text or JSON, counts the calls."""

    def __init__(self):
        self.calls = []
        self.down = False

    def text(self, url):
        self.calls.append(url)
        if self.down:
            raise requests.ConnectionError("down")
        if url.endswith("/en/news") or url.endswith("/en/news/archive"):
            return WIZ_LIST
        if "/en/news/" in url:
            return WIZ_ARTICLE if "banned" in url or "mechanics" in url else "<html>no date here</html>"
        if "goldfish" in url:
            return ATOM
        return RSS

    def json(self, url):
        self.calls.append(url)
        if self.down:
            raise requests.ConnectionError("down")
        return SETS if url.endswith("/sets") else CARDS


@pytest.fixture
def web():
    return Web()


@pytest.fixture
def news(web):
    return News(online=True, fetch_text=web.text, fetch_json=web.json)


@pytest.fixture
def client(db, news):  # noqa: F811
    app = create_app(Scanner(db, None, source=None))
    app.extensions["news"] = news
    return app.test_client()


def test_rss_feed(news):
    items = parse_feed(RSS, "edhrec")
    assert [a["title"] for a in items] == ["Banned and Restricted Announcement", "Older & wiser"]   # newest first, junk dropped
    old = items[1]
    assert old["summary"] == "Short summary."
    assert old["image"] == "https://edhrec.com/pic.jpg"
    assert old["author"] == "Someone" and old["section"] == "Articles"
    assert items[0]["tags"] == ["bans"]


def test_atom_feed():
    (a,) = parse_feed(ATOM, "goldfish")
    assert a["url"] == "https://www.mtggoldfish.com/articles/boosters"
    assert a["author"] == "SaffronOlive" and a["published"] > 0


def test_wizards_news_page_and_article():
    items = parse_wizards_list(WIZ_LIST)
    assert [a["title"] for a in items] == ["Banned and Restricted Announcement – November 10, 2026", "Star Trek Mechanics", "Arena Direct Terms"]
    assert items[0]["url"] == "https://magic.wizards.com/en/news/announcements/banned-and-restricted-november-10-2026"
    assert items[0]["section"] == "Announcements" and "bans" in items[0]["tags"]
    assert items[0]["summary"] == "Changes to Standard."
    found = parse_wizards_article(WIZ_ARTICLE)
    assert found["image"].startswith("https://images.ctfassets.net/")
    assert found["published"] == datetime(2026, 11, 10, 17, tzinfo=timezone.utc).timestamp()


def test_sets_coming_out_and_just_out():
    s = parse_sets(SETS, date(2026, 11, 3))
    assert [x["code"] for x in s["upcoming"]] == ["TRK", "NAU"]        # no tokens, no digital sets
    assert s["upcoming"][0]["days"] == 10 and s["upcoming"][0]["cards"] == 581
    assert [x["code"] for x in s["recent"]] == ["FRA"]                  # not last year's


def test_previews():
    cards = parse_previews(CARDS)
    assert cards[0]["url"] == "https://scryfall.com/card/trk/1/picard" and cards[0]["by"] == "Wizards"
    assert cards[1]["image"] == "https://cards.scryfall.io/normal/b2.jpg"   # double-faced: the front


def test_helpers():
    assert safe_url("javascript:alert(1)") == "" and safe_url("//x.com/a.png") == "https://x.com/a.png"
    assert safe_url("/en/news", "https://magic.wizards.com/") == "https://magic.wizards.com/en/news"
    assert clean_text("<p>" + "word " * 100 + "</p>", 30).endswith("…")
    assert tags_for("Unbanned: Black Lotus") == ["bans"]
    assert tags_for("Bant Spirits deck") == []
    assert "previews" in tags_for("Exclusive card preview")


def test_the_page_and_its_api(client, web):
    assert client.get("/news").status_code == 200
    d = client.get("/api/news").get_json()
    assert {a["source"] for a in d["articles"]} == {"wizards", "goldfish", "edhrec", "hipsters"}
    wiz = [a for a in d["articles"] if a["source"] == "wizards"]
    assert [a["title"] for a in wiz] == ["Banned and Restricted Announcement – November 10, 2026", "Star Trek Mechanics"]  # no dateless terms page
    assert d["bans"][0]["source"] == "wizards"    # the banner is for Wizards' own announcements
    assert d["sets"]["upcoming"] and len(d["previews"]) == 2
    assert d["articles"] == sorted(d["articles"], key=lambda a: -(a["published"] or 0))
    # Everything is cached: a second visit fetches nothing.
    n = len(web.calls)
    client.get("/api/news")
    assert len(web.calls) == n


def test_turning_sources_on_and_off(client, web):
    client.get("/api/news")
    d = client.post("/api/news/sources", json={"goldfish": False, "reddit": True, "nope": True}).get_json()
    on = {s["key"]: s["on"] for s in d["sources"]}
    assert on["goldfish"] is False and on["reddit"] is True and "nope" not in on
    assert "goldfish" not in {a["source"] for a in d["articles"]}
    assert (config.DATA_DIR / "news_settings.json").exists()


def test_internet_down_keeps_the_saved_news(db, web):  # noqa: F811
    first = News(online=True, fetch_text=web.text, fetch_json=web.json)
    first.refresh(wait=True)
    count = len(first.snapshot()["articles"])
    # A restart with no internet: the news saved in data/news_cache.json still shows.
    web.down = True
    again = News(online=True, fetch_text=web.text, fetch_json=web.json, clock=lambda: 4e9)
    again.refresh(now=True)
    d = again.snapshot()
    assert len(d["articles"]) == count
    assert all(s["error"] == "Couldn't reach the site" for s in d["sources"] if s["on"])


def test_offline_never_fetches(web):
    n = News(online=False, fetch_text=web.text, fetch_json=web.json)
    n.refresh(now=True)
    assert web.calls == [] and n.snapshot()["articles"] == []


def test_page_follows_the_shared_layout(client):
    import re
    html = client.get("/news").get_data(as_text=True)
    assert 'src="/static/shell.js?v=' in html and 'src="/static/look.js?v=' in html
    assert html.count('class="brand"') == 1
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
