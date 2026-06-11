"""
selmo_web.py -- web search bridge for Selmo
Port 8081 -- started automatically by Selmo.bat / Mizan.bat

API:
  GET /search?q=<query>&n=<num>&full=<0|1>
  Response: JSON array of { title, url, snippet [, text] }

  GET /fetch?url=<url>
  Response: { url, text }

Logic:
  1. DuckDuckGo HTML scrape (primary, no API key)
  2. Fallback to SearXNG public EU instances
  3. Text extraction with trafilatura (if installed) or regex html

Install dependency: pip install trafilatura --break-system-packages
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse, urllib.error
import json, sys, re, time, datetime

PORT    = 8081
TIMEOUT = 8

# Pool SearXNG — prima locale, poi istanze europee pubbliche
SEARX_POOL = [
    "http://localhost:8888",
    "https://searx.be",
    "https://search.disroot.org",
    "https://searx.fmac.xyz",
    "https://searx.tiekoetter.com",
    "https://searx.sev.monster",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# ── Trafilatura (opzionale) ───────────────────────────────────────────────────
try:
    import trafilatura
    HAS_TRAF = True
except ImportError:
    HAS_TRAF = False

def _strip_html(html_bytes):
    """Fallback minimo se trafilatura non è installato."""
    text = html_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s{3,}", "\n\n", text)
    return text.strip()[:3000]

def fetch_text(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(200_000)
        if HAS_TRAF:
            text = trafilatura.extract(
                raw, include_comments=False, include_tables=True,
                favor_recall=True
            ) or ""
        else:
            text = _strip_html(raw)
        return text[:4000]
    except Exception as e:
        return ""

# ── DuckDuckGo (primary) ─────────────────────────────────────────────────────
def ddg_search(query, n=5):
    """DuckDuckGo HTML scrape — no API key required."""
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "wt-wt", "kp": "-2"})
        url = f"https://html.duckduckgo.com/html/?{params}"
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://duckduckgo.com/",
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            html = r.read().decode("utf-8", errors="replace")
        out = []
        blocks = re.findall(
            r'class="result__title".*?href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</span>',
            html, re.S
        )
        for href, title, snippet in blocks[:n]:
            real_url = href
            m = re.search(r'uddg=([^&]+)', href)
            if m:
                real_url = urllib.parse.unquote(m.group(1))
            title   = re.sub(r"<[^>]+>", "", title).strip()
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            snippet = re.split(r'\n{2,}|\s{5,}', snippet)[0].strip()[:300]
            if title and real_url:
                out.append({"title": title, "url": real_url, "snippet": snippet})
        if out:
            print(f"  [web] DDG — {len(out)} results for '{query}'")
            return out
        print(f"  [web] DDG — no results parsed for '{query}'")
    except Exception as e:
        print(f"  [web] DDG failed: {e}")
    return []

# ── SearXNG (fallback) ────────────────────────────────────────────────────────
def searx_search(query, n=5, pool=None):
    if pool is None:
        pool = SEARX_POOL
    params = urllib.parse.urlencode({
        "q":          query,
        "format":     "json",
        "categories": "general",
        "language":   "auto",
        "pageno":     1,
    })
    for base in pool:
        url = f"{base}/search?{params}"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA, "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.loads(r.read().decode("utf-8", errors="replace"))
            results = data.get("results", [])[:n]
            out = []
            for x in results:
                out.append({
                    "title":   x.get("title", "").strip(),
                    "url":     x.get("url", ""),
                    "snippet": x.get("content", "").strip(),
                })
            if out:
                print(f"  [web] SearXNG {base} — {len(out)} results for '{query}'")
                return out
        except Exception as e:
            print(f"  [web] {base} failed: {e}")
            continue
    print(f"  [web] ERROR: no SearXNG instance reachable for '{query}'")
    return []

NEWS_SOURCES = [
    "https://www.bbc.com/news",
    "https://apnews.com",
    "https://reuters.com",
]

NEWS_RE = re.compile(
    r'\b(news|notizie|headlines|breaking|latest|today|oggi|attualit[àa])\b', re.I
)

def web_search(query, n=5):
    """Search priority:
    1. SearXNG on localhost:8888 (Podman — fully local, no external calls)
    2. SearXNG public EU instances (fallback if local not running)
    3. DuckDuckGo HTML scrape (last resort)
    For news-like queries, enriches top result with full text via trafilatura."""
    engine = "none"
    # Try local SearXNG first (fast — if not running it fails immediately)
    results = searx_search(query, n, pool=["http://localhost:8888"])
    if results:
        engine = "SearXNG local"
    if not results:
        # Try public SearXNG instances
        results = searx_search(query, n, pool=SEARX_POOL[1:])
        if results:
            engine = "SearXNG public"
    if not results:
        # Last resort: DDG
        results = ddg_search(query, n)
        if results:
            engine = "DDG"

    # For news queries, fetch full text of first result
    if results and NEWS_RE.search(query):
        top_url = results[0]["url"]
        is_homepage = not re.search(r'/\w{4,}', urllib.parse.urlparse(top_url).path)
        fetch_url = top_url if not is_homepage else NEWS_SOURCES[0]
        text = fetch_text(fetch_url)
        if text:
            results[0]["text"] = text[:3000]
            engine += " + trafilatura"
            print(f"  [web] full text fetched from {fetch_url} ({len(text)} chars)")

    # Tag each result with the engine used
    for r in results:
        r["_engine"] = engine

    return results

def searx_local_up(timeout=1.0):
    """Reachability probe della SearXNG locale (Podman, 8888).
    True = istanza locale raggiungibile -> la ricerca resta sul tuo computer."""
    try:
        req = urllib.request.Request("http://localhost:8888/",
                                     headers={"User-Agent": "Selmo"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default HTTP log

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/search":
            q    = qs.get("q",    [""])[0].strip()
            n    = int(qs.get("n", ["5"])[0])
            full = qs.get("full", ["0"])[0] == "1"
            if not q:
                self._json({"error": "empty query"})
                return
            results = web_search(q, n)
            if full:
                for r in results:
                    r["text"] = fetch_text(r["url"])
            self._json(results)

        elif parsed.path == "/fetch":
            url = qs.get("url", [""])[0].strip()
            if not url:
                self._json({"error": "empty url"})
                return
            text = fetch_text(url)
            self._json({"url": url, "text": text})

        elif parsed.path == "/datetime":
            now = datetime.datetime.now()
            self._json({
                "datetime": now.strftime("%A, %B %d, %Y — %H:%M:%S"),
                "date":     now.strftime("%A, %B %d, %Y"),
                "time":     now.strftime("%H:%M:%S"),
                "iso":      now.isoformat(),
            })

        elif parsed.path == "/status":
            self._json({
                "ok":          True,
                "trafilatura": HAS_TRAF,
                "searx_local": searx_local_up(),
                "searx_pool":  SEARX_POOL,
            })

        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False, indent=None).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    print("  selmo_web.py — web search bridge")
    print(f"  http://localhost:{PORT}/search?q=query")
    print(f"  http://localhost:{PORT}/fetch?url=...")
    print(f"  trafilatura: {'OK' if HAS_TRAF else 'not installed (pip install trafilatura)'}")
    print()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  [web] stopped.")
