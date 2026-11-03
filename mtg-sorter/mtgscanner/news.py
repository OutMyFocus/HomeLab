"""The News page: Magic news, new sets, the latest previewed cards and ban announcements.

Where it comes from:
  * magic.wizards.com/en/news. Wizards has no RSS feed any more, so this reads the
    news page itself and, once per article, the article page for its date and picture.
  * RSS/Atom feeds from community sites (MTGGoldfish, EDHREC, ...). Each one can be
    turned on or off on the page; the choice is saved in data/news_settings.json.
  * Scryfall's /sets (sets coming out soon and just out) and a card search for the
    newest previewed cards of sets that aren't out yet.

Everything is kept in memory and in data/news_cache.json, so the page opens at once and
still shows the last news when the internet is down. A source older than REFRESH is
fetched again in the background; the Refresh button fetches everything now.
"""

import html
import json
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urljoin

import requests
from flask import jsonify, request, send_from_directory

from . import config

REFRESH = 30 * 60          # seconds before a source is fetched again
RETRY = 2 * 60             # after a failed fetch, wait this long before trying again
NOW_LIMIT = 60             # the Refresh button won't re-fetch a source newer than this
KEEP = 40                  # articles kept per source
WIZARDS_DETAILS = 24       # Wizards article pages read per refresh (for their dates)
SCRYFALL = "https://api.scryfall.com"
WIZARDS = "https://magic.wizards.com"

SOURCES = [
    {"key": "wizards", "name": "Wizards of the Coast", "site": WIZARDS + "/en/news", "on": True,
     "desc": "The official Magic site: announcements, previews, ban lists"},
    {"key": "goldfish", "name": "MTGGoldfish", "site": "https://www.mtggoldfish.com", "on": True,
     "url": "https://www.mtggoldfish.com/feed", "desc": "Prices, decks and set reviews"},
    {"key": "edhrec", "name": "EDHREC", "site": "https://edhrec.com/articles", "on": True,
     "url": "https://edhrec.com/articles/feed", "desc": "Commander news and new card reviews"},
    {"key": "hipsters", "name": "Hipsters of the Coast", "site": "https://www.hipstersofthecoast.com", "on": True,
     "url": "https://www.hipstersofthecoast.com/feed/", "desc": "Weekly news round-ups"},
    {"key": "mtgazone", "name": "MTG Arena Zone", "site": "https://mtgazone.com", "on": False,
     "url": "https://mtgazone.com/feed/", "desc": "MTG Arena news and limited reviews"},
    {"key": "reddit", "name": "r/magicTCG", "site": "https://www.reddit.com/r/magicTCG", "on": False,
     "url": "https://www.reddit.com/r/magicTCG/.rss", "desc": "The Magic subreddit (busy, lots of memes)"},
]
BY_KEY = {s["key"]: s for s in SOURCES}

# Sets worth showing as "coming out" (no token sheets, promos, art series or digital sets).
SET_TYPES = {"expansion", "core", "masters", "draft_innovation", "commander", "funny", "starter",
             "duel_deck", "from_the_vault", "spellbook", "premium_deck", "arsenal", "planechase",
             "archenemy", "eternal"}
JUST_OUT = 45  # days a released set stays under "Just out"

WIZARDS_SECTIONS = {
    "announcements": "Announcements", "card-preview": "Card preview", "feature": "Feature",
    "making-magic": "Making Magic", "mtg-arena": "MTG Arena", "magic-story": "Story",
    "magic-the-gathering-arena": "MTG Arena", "digital": "Digital", "events": "Events",
}

TAGS = {
    "bans": re.compile(r"\b(un)?bann?(ed|ing|s)?\b|\bb\s*&\s*r\b|banned and restricted|restricted list|banned-and-restricted", re.I),
    "previews": re.compile(r"preview|spoiler|revealed?\b|first look|card-preview|debut", re.I),
    "arena": re.compile(r"\barena\b|mtg-arena", re.I),
}


# ---------- small helpers ----------

def clean_text(raw: str, limit: int = 260) -> str:
    """HTML (or escaped HTML) to one plain line, cut at a word near limit."""
    text = html.unescape(raw or "")
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?)])", r"\1", text)   # "<i>Standard</i>." left a space
    # WordPress feeds end with "The post X appeared first on Y."
    text = re.sub(r"\s*The post .{0,200} appeared first on .{0,80}\.?$", "", text)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",;:.-") + "…"
    return text


def safe_url(url: str | None, base: str = "") -> str:
    """Only http(s) links and pictures go to the page."""
    url = html.unescape((url or "").strip())
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    elif base and not re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
        url = urljoin(base, url)
    return url if re.match(r"^https?://", url, re.I) else ""


def to_time(value: str | None) -> float | None:
    """RSS (RFC 822), Atom (ISO 8601) or Wizards ("2026-11-03T09:00-08:00") dates to a timestamp."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except ValueError:
        return None


def tags_for(*text: str) -> list[str]:
    joined = " ".join(t for t in text if t)
    return [tag for tag, rx in TAGS.items() if rx.search(joined)]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el, name: str):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _children(el, name: str):
    return [c for c in el if _local(c.tag) == name]


def _text(el, name: str) -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None else ""


def _first_img(raw: str) -> str:
    m = re.search(r"<img\b[^>]*?\bsrc=[\"']([^\"']+)", html.unescape(raw or ""), re.I)
    return m.group(1) if m else ""


# ---------- feeds ----------

def parse_feed(xml_text: str, source: str) -> list[dict]:
    """RSS 2.0 or Atom to article dicts, newest first."""
    # No DOCTYPE/entities from the internet: the feeds we read never need them.
    xml_text = re.sub(r"<!DOCTYPE[^>\[]*(\[.*?\])?\s*>", "", xml_text, flags=re.S | re.I)
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    out = []
    if _local(root.tag) == "feed":       # Atom
        entries = _children(root, "entry")
    else:                                 # RSS: <rss><channel><item>
        channel = _child(root, "channel")
        entries = _children(channel if channel is not None else root, "item")
    for e in entries:
        title = clean_text(_text(e, "title"), 200)
        link = ""
        for l in _children(e, "link"):
            if l.get("href") and l.get("rel", "alternate") == "alternate":
                link = l.get("href")
                break
            if (l.text or "").strip():
                link = l.text.strip()
                break
        link = safe_url(link or _text(e, "url"))
        if not title or not link:
            continue
        body = _text(e, "description") or _text(e, "summary") or _text(e, "encoded") or _text(e, "content")
        rich = _text(e, "encoded") or _text(e, "content") or body
        image = ""
        for c in e.iter():
            name = _local(c.tag)
            if name in ("thumbnail", "content") and c.get("url") and (c.get("medium", "image") == "image"):
                image = c.get("url")
                break
            if name == "enclosure" and (c.get("type") or "").startswith("image") and c.get("url"):
                image = c.get("url")
                break
        image = safe_url(image or _first_img(rich), link)
        author = _text(e, "creator")
        a = _child(e, "author")
        if not author and a is not None:
            author = _text(a, "name") or (a.text or "").strip()
        cats = [clean_text(c.text or c.get("term") or c.get("label") or "", 40) for c in _children(e, "category")]
        published = to_time(_text(e, "pubDate") or _text(e, "published") or _text(e, "updated") or _text(e, "date"))
        summary = clean_text(body)
        if source == "reddit":
            summary = ""  # reddit's "submitted by ... [link] [comments]"
            author = author.removeprefix("/u/")
        out.append({"source": source, "title": title, "url": link, "summary": summary, "image": image,
                    "author": clean_text(author, 60), "section": cats[0] if cats and source != "reddit" else "",
                    "published": published, "tags": tags_for(title, " ".join(cats))})
    out.sort(key=lambda a: -(a["published"] or 0))
    return out[:KEEP]


# ---------- magic.wizards.com ----------

ARTICLE_HREF = re.compile(r'href="(/en/news/([a-z0-9-]+)/([a-z0-9-]+))"')


def parse_wizards_list(page: str) -> list[dict]:
    """The article cards on magic.wizards.com/en/news (and /archive), in page order."""
    out, seen = [], set()
    chunks = re.split(r"data-article-(?:hub-)?card-v=", page)[1:]
    for chunk in chunks:
        chunk = chunk[:6000]
        m = ARTICLE_HREF.search(chunk)
        h3 = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S)
        if not m or not h3:
            continue
        path, section, _slug = m.groups()
        if path in seen:
            continue
        seen.add(path)
        p = re.search(r"<p>(.*?)</p>", chunk, re.S)
        title = clean_text(h3.group(1), 200)
        summary = clean_text(p.group(1)) if p else ""
        out.append({"source": "wizards", "title": title, "url": WIZARDS + path, "summary": summary, "image": "",
                    "author": "", "section": WIZARDS_SECTIONS.get(section, section.replace("-", " ").capitalize()),
                    "published": None, "tags": tags_for(title, section, path)})
    return out


def parse_wizards_article(page: str) -> dict:
    """The date and picture of one Wizards article page."""
    found = {}
    m = re.search(r'publishedDateTime:"([^"]+)"', page)
    if m:
        found["published"] = to_time(m.group(1))
    if not found.get("published"):
        t = re.search(r"<time[^>]*>\s*([A-Z][a-z]{2,8}\.? \d{1,2}, \d{4})", page)
        if t:
            for fmt in ("%b %d, %Y", "%B %d, %Y"):
                try:
                    found["published"] = datetime.strptime(t.group(1).replace(".", ""), fmt).replace(
                        hour=12, tzinfo=timezone.utc).timestamp()
                    break
                except ValueError:
                    pass
    og = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', page)
    if og:
        found["image"] = safe_url(og.group(1))
    return found


# ---------- Scryfall ----------

def parse_sets(js: dict, today: date) -> dict:
    """Scryfall /sets to {"upcoming": [...soonest first], "recent": [...newest first]}."""
    upcoming, recent = [], []
    for s in js.get("data", []):
        if s.get("digital") or s.get("set_type") not in SET_TYPES or not s.get("released_at"):
            continue
        try:
            when = date.fromisoformat(s["released_at"])
        except ValueError:
            continue
        item = {"code": s.get("code", "").upper(), "name": s.get("name", ""), "type": s.get("set_type", ""),
                "released": s["released_at"], "days": (when - today).days, "cards": s.get("card_count") or 0,
                "icon": safe_url(s.get("icon_svg_uri")), "url": safe_url(s.get("scryfall_uri")),
                "parent": (s.get("parent_set_code") or "").upper()}
        if when > today:
            upcoming.append(item)
        elif (today - when).days <= JUST_OUT:
            recent.append(item)
    upcoming.sort(key=lambda s: (s["released"], s["parent"] != "", s["name"]))
    recent.sort(key=lambda s: (s["released"], s["parent"] == ""), reverse=True)
    return {"upcoming": upcoming[:16], "recent": recent[:10]}


PREVIEW_QUERY = "date>today not:reprint -is:digital -st:token -st:memorabilia"


def preview_search_url() -> str:
    return f"https://scryfall.com/search?q={quote(PREVIEW_QUERY)}&order=spoiled&dir=desc&as=grid"


def parse_previews(js: dict, limit: int = 36) -> list[dict]:
    """Scryfall card search (newest previews first) to small card dicts."""
    out = []
    for c in js.get("data", [])[:limit]:
        imgs = c.get("image_uris") or ((c.get("card_faces") or [{}])[0].get("image_uris") or {})
        preview = c.get("preview") or {}
        out.append({"id": c.get("id", ""), "name": c.get("name", ""), "set": (c.get("set") or "").upper(),
                    "set_name": c.get("set_name", ""), "rarity": c.get("rarity", ""),
                    "image": safe_url(imgs.get("normal") or imgs.get("small")),
                    "url": safe_url((c.get("scryfall_uri") or "").split("?")[0]),
                    "released": c.get("released_at", ""), "previewed": preview.get("previewed_at", ""),
                    "by": clean_text(preview.get("source", ""), 60), "by_url": safe_url(preview.get("source_uri"))})
    return out


# ---------- fetching and caching ----------

def _get(url: str, accept: str = "*/*", timeout: float = 10) -> requests.Response:
    resp = requests.get(url, headers={"User-Agent": config.USER_AGENT, "Accept": accept}, timeout=timeout)
    resp.raise_for_status()
    return resp


def fetch_text(url: str) -> str:
    resp = _get(url, "application/rss+xml, application/atom+xml, application/xml, text/html;q=0.9, */*;q=0.5")
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def fetch_json(url: str) -> dict:
    return _get(url, "application/json").json()


class News:
    def __init__(self, online: bool = True, fetch_text=fetch_text, fetch_json=fetch_json, clock=time.time):
        self.online = online
        self.fetch_text = fetch_text
        self.fetch_json = fetch_json
        self.clock = clock
        self.lock = threading.Lock()
        self.busy = set()          # sources being fetched right now
        self.cache = None          # {key: {"items": ..., "at": ts, "error": str|None, "tried": ts}}

    # --- files in the data folder ---
    @staticmethod
    def _cache_path():
        return config.DATA_DIR / "news_cache.json"

    @staticmethod
    def _settings_path():
        return config.DATA_DIR / "news_settings.json"

    def _load(self):
        if self.cache is None:
            try:
                self.cache = json.loads(self._cache_path().read_text())
                if not isinstance(self.cache, dict):
                    self.cache = {}
            except (OSError, ValueError):
                self.cache = {}
            for entry in self.cache.values():
                entry["tried"] = 0   # a restart may retry at once
        return self.cache

    def _save(self):
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path().with_suffix(".tmp")
            tmp.write_text(json.dumps(self.cache))
            tmp.replace(self._cache_path())
        except OSError:
            pass

    def enabled(self) -> dict[str, bool]:
        try:
            saved = json.loads(self._settings_path().read_text())
        except (OSError, ValueError):
            saved = {}
        return {s["key"]: bool(saved.get(s["key"], s["on"])) for s in SOURCES}

    def set_enabled(self, changes: dict) -> dict[str, bool]:
        now = self.enabled()
        for key, on in changes.items():
            if key in BY_KEY:
                now[key] = bool(on)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._settings_path().write_text(json.dumps(now, indent=1))
        return now

    # --- one source ---
    def _fetch(self, key: str):
        if key == "sets":
            return parse_sets(self.fetch_json(SCRYFALL + "/sets"), date.today())
        if key == "previews":
            url = f"{SCRYFALL}/cards/search?q={quote(PREVIEW_QUERY)}&order=spoiled&dir=desc"
            try:
                return parse_previews(self.fetch_json(url))
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    return []   # Scryfall answers 404 when no card matches (nothing previewed)
                raise
        if key == "wizards":
            return self._fetch_wizards()
        return parse_feed(self.fetch_text(BY_KEY[key]["url"]), key)

    def _fetch_wizards(self):
        items = []
        for page in ("/en/news", "/en/news/archive"):
            try:
                items += parse_wizards_list(self.fetch_text(WIZARDS + page))
            except Exception:
                if page == "/en/news":
                    raise
        unique, seen = [], set()
        for a in items:
            if a["url"] not in seen:
                seen.add(a["url"])
                unique.append(a)
        # Dates and pictures are on each article's own page; keep what we already know.
        with self.lock:
            known = {a["url"]: a for a in (self._load().get("wizards") or {}).get("items") or []}
        first_time = not known
        todo = [a for a in unique[:KEEP] if not (known.get(a["url"]) or {}).get("checked")][:WIZARDS_DETAILS]

        def details(a):
            try:
                return a["url"], parse_wizards_article(self.fetch_text(a["url"]))
            except Exception:
                return a["url"], None   # try again next time

        with ThreadPoolExecutor(4) as pool:
            found = dict(pool.map(details, todo))
        now = self.clock()
        for a in unique:
            old = known.get(a["url"]) or {}
            extra = found.get(a["url"])
            a["published"] = (extra or {}).get("published") or old.get("published")
            a["image"] = (extra or {}).get("image") or old.get("image") or ""
            a["checked"] = bool(old.get("checked") or extra is not None)
            # Every real article has a date on its page; ones without (rules, terms) aren't news.
            a["hide"] = a["checked"] and not a["published"]
            # Until its page is read: the time it showed up here (not on the very first fetch,
            # when everything would look brand new).
            a["seen"] = old.get("seen") or (None if first_time else now)
        unique.sort(key=lambda a: -(a["published"] or a["seen"] or 0))
        return unique[:KEEP]

    def _refresh(self, key: str):
        try:
            items, error = self._fetch(key), None
        except Exception as e:  # network down, site changed, bad XML ...
            items, error = None, _short_error(e)
        with self.lock:
            cache = self._load()
            entry = cache.setdefault(key, {"items": None, "at": 0, "error": None})
            entry["tried"] = self.clock()
            entry["error"] = error
            if items is not None:
                entry["items"], entry["at"] = items, self.clock()
            self.busy.discard(key)
            self._save()

    def _stale(self, entry, limit=REFRESH) -> bool:
        if not entry:
            return True
        now = self.clock()
        if entry.get("error") and now - (entry.get("tried") or 0) < RETRY:
            return False
        return now - (entry.get("at") or 0) > limit

    # --- the page ---
    def keys(self) -> list[str]:
        on = self.enabled()
        return [k for k in on if on[k]] + ["sets", "previews"]

    def refresh(self, wait: bool = False, now: bool = False):
        """Fetch what's old. wait=True fetches the missing ones before returning;
        now=True (the Refresh button) fetches everything older than a minute and waits."""
        if not self.online:
            return
        with self.lock:
            cache = self._load()
            todo = [k for k in self.keys() if k not in self.busy and self._stale(cache.get(k), NOW_LIMIT if now else REFRESH)]
            self.busy.update(todo)
            missing = [k for k in todo if not (cache.get(k) or {}).get("items") and (cache.get(k) or {}).get("items") != []]
        if not todo:
            return
        sync = todo if now else (missing if wait else [])
        later = [k for k in todo if k not in sync]
        if later:
            threading.Thread(target=lambda: [self._refresh(k) for k in later], daemon=True, name="news").start()
        if sync:
            with ThreadPoolExecutor(min(6, len(sync))) as pool:
                list(pool.map(self._refresh, sync))

    def snapshot(self) -> dict:
        on = self.enabled()
        with self.lock:
            cache = self._load()
            articles = []
            for key in on:
                if on[key]:
                    articles += [a for a in (cache.get(key) or {}).get("items") or [] if not a.get("hide")]
            for a in articles:
                a.setdefault("seen", None)
            articles.sort(key=lambda a: -(a.get("published") or a.get("seen") or 0))
            sources = [{"key": s["key"], "name": s["name"], "site": s["site"], "desc": s["desc"], "on": on[s["key"]],
                        "updated": (cache.get(s["key"]) or {}).get("at") or None,
                        "error": (cache.get(s["key"]) or {}).get("error"),
                        "count": len((cache.get(s["key"]) or {}).get("items") or [])} for s in SOURCES]
            sets = (cache.get("sets") or {}).get("items") or {"upcoming": [], "recent": []}
            previews = (cache.get("previews") or {}).get("items") or []
            stamps = [(cache.get(k) or {}).get("at") or 0 for k in self.keys()]
            return {
                "articles": articles, "sources": sources, "sets": sets, "previews": previews,
                "previews_url": preview_search_url(),
                # The banner is for Wizards' own ban list announcements, not talk about bans.
                "bans": [a for a in articles if "bans" in a["tags"] and a["source"] == "wizards"
                         and (a.get("published") or a.get("seen") or 0) > self.clock() - 21 * 86400][:3],
                "updated": max(stamps) if stamps and max(stamps) else None,
                "refreshing": bool(self.busy), "online": self.online,
                "errors": {k: (cache.get(k) or {}).get("error") for k in ("sets", "previews") if (cache.get(k) or {}).get("error")},
            }


def _short_error(e: Exception) -> str:
    if isinstance(e, requests.HTTPError) and e.response is not None:
        return f"The site answered {e.response.status_code}"
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return "Couldn't reach the site"
    if isinstance(e, ET.ParseError):
        return "The feed couldn't be read"
    return "Couldn't read the news there"


def add_news_routes(app, scanner, web_dir, news: News | None = None):
    # --offline (no Scryfall prices) also means no news fetching; the saved news still shows.
    # The News lives in app.extensions["news"] so tests can swap in a fake internet.
    app.extensions["news"] = news or News(online=getattr(scanner, "live", None) is not None)

    @app.get("/news")
    def news_page():
        return send_from_directory(web_dir, "news.html")

    @app.get("/api/news")
    def news_feed():
        n = app.extensions["news"]
        n.refresh(wait=True, now=request.args.get("refresh") == "1")
        return jsonify(n.snapshot())

    @app.post("/api/news/sources")
    def news_sources():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "Send {source: true/false}"}), 400
        n = app.extensions["news"]
        n.set_enabled(body)
        n.refresh(wait=True)
        return jsonify(n.snapshot())
