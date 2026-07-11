"""
selmo_rag.py -- local RAG (retrieval) bridge for Selmo
Port 8088 -- started automatically by the tray, alongside the other bridges.

This is the "RAG mode" backend: it indexes a folder of the user's own files
into a local vector store and, on each query, returns the most relevant chunks
in the SAME shape as the web bridge ({title, url, snippet}), so the client's
existing retrieve-then-answer send loop treats it identically.

API (mirrors selmo_web.py):
  GET  /status
       -> {ok, corpus_dir, n_chunks, embed_model, embedder_up, backend}
  GET  /search?q=<query>&n=<k>
       -> JSON array of { title, url, snippet }   (title=filename,
          url=<path>#chunk-N, snippet=chunk text)
  POST /reindex
       -> {ok, n_files, n_chunks}   (re-reads corpus_dir from config)

Design notes:
  - Extraction: txt/md/odt/docx are dependency-free (docx via zipfile, the same
    trick extract_odt uses for odt); pdf is optional (pypdf if installed).
  - Chunking reuses chunk_pipeline.build_chunks (provable, no re-implementation).
  - Embeddings: HTTP POST to a llama.cpp `--embeddings` server (OpenAI-style
    /v1/embeddings). The endpoint URL is config-driven; the bridge can also
    auto-start its own private llama-server child (embed_autostart).
  - Vector store: faiss if available, else a numpy brute-force cosine fallback,
    so faiss-cpu is an optimisation and not a hard dependency.

Config: selmo-rag-config.json (see keys in DEFAULT_CFG).
Index files (gitignored): selmo-rag.vecs.npy + selmo-rag.meta.json
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request, urllib.parse
import json, sys, os, re, zipfile, subprocess, time, atexit, threading
from pathlib import Path
from xml.etree import ElementTree as ET

PORT     = 8088
BASE     = Path(__file__).resolve().parent
CFG_PATH = BASE / "selmo-rag-config.json"
VEC_PATH = BASE / "selmo-rag.vecs.npy"
META_PATH= BASE / "selmo-rag.meta.json"

DEFAULT_CFG = {
    "corpus_dir":       "",                       # folder to index (empty = none yet)
    "embed_url":        "http://127.0.0.1:8091",  # llama.cpp --embeddings server
    "embed_model":      "nomic-embed-text-v1.5",  # label sent as `model`
    "chunk_size":       1200,                     # characters per chunk
    "top_k":            5,                         # default results per query
    "embed_autostart":  True,                     # spawn our own embeddings child
    "llama_bin":        "",                        # auto: bin/llama-server.exe if empty
    "embed_model_path": "",                        # auto: first embedding GGUF in models/ if empty
    # nomic-embed-v1.5 needs task prefixes; blank them for embedders that don't
    # (e.g. all-MiniLM). bge-* want a query instruction only.
    "doc_prefix":       "search_document: ",
    "query_prefix":     "search_query: ",
    # No hardcoded folder exclusions: the user unchecks subfolders in the picker
    # (relative names, one per top-level dir). Populated from the GUI, not code.
    "exclude_dirs":     [],
    # File extensions to index; user-selectable in the picker. Empty = all known.
    "formats":          [],
}

# Text-ish extensions read as plain UTF-8 (docs + code + config).
TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".json", ".html", ".htm", ".css",
    ".ini", ".cfg", ".conf", ".yaml", ".yml", ".xml", ".toml",
    ".sh", ".bat", ".ps1", ".c", ".h", ".cpp", ".hpp", ".java", ".rs",
    ".go", ".rb", ".php", ".sql", ".tex",
}
# Extensions that need a dedicated extractor.
SPECIAL_EXT = {".odt", ".docx", ".pdf"}
KNOWN_EXTS  = TEXT_EXT | SPECIAL_EXT
TIMEOUT     = 60  # embeddings can be slow on first batch

def allowed_exts(cfg):
    """Extensions to index: the user's `formats` if set, else every known one."""
    picked = cfg.get("formats") or []
    norm = {(e if e.startswith(".") else "." + e).lower() for e in picked}
    return norm or set(KNOWN_EXTS)

# ── Reuse the proven extractor/chunker (no re-implementation) ──────────────────
try:
    from chunk_pipeline import build_chunks, extract_odt
    HAS_CHUNK = True
except Exception as e:                              # pragma: no cover
    HAS_CHUNK = False
    print(f"  [rag] WARNING: chunk_pipeline import failed ({e}); using local fallback")
    def extract_odt(path):                          # minimal local fallback
        with zipfile.ZipFile(path) as z:
            xml = z.read("content.xml").decode("utf-8")
        NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
        lines = []
        def walk(node):
            if node.tag in (f"{{{NS}}}p", f"{{{NS}}}h"):
                lines.append("".join(node.itertext()).strip()); return
            for c in node: walk(c)
        walk(ET.fromstring(xml))
        return "\n".join(lines)
    def build_chunks(text, size):
        n, ranges, i = len(text), [], 0
        while i < n:
            e = min(i + size, n)
            nl = text.rfind("\n", i, e)
            if nl > i: e = nl + 1
            ranges.append((i, e)); i = e
        return ranges

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:                                   # pragma: no cover
    HAS_NUMPY = False

try:
    import faiss
    HAS_FAISS = True
except Exception:
    HAS_FAISS = False

# ── Config ────────────────────────────────────────────────────────────────────
def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  [rag] config parse error ({e}); using defaults")
    return cfg

# ── Text extraction ───────────────────────────────────────────────────────────
def _extract_docx(path):
    """DOCX = a zip with word/document.xml; strip tags, keep paragraph breaks.
    Dependency-free, the same spirit as chunk_pipeline.extract_odt for odt."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = re.sub(r"</w:p>", "\n", xml)          # paragraph end -> newline
    xml = re.sub(r"<[^>]+>", "", xml)           # drop all tags
    xml = (xml.replace("&amp;", "&").replace("&lt;", "<")
              .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
    return re.sub(r"\n{3,}", "\n\n", xml).strip()

def _extract_pdf(path):
    """PDF is optional: use pypdf if present, else return '' (file skipped)."""
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()
    except Exception as e:
        print(f"  [rag] pdf extract failed for {path}: {e}")
        return ""

def extract_any(path):
    ext = Path(path).suffix.lower()
    try:
        if ext == ".odt":
            return extract_odt(str(path))
        if ext == ".docx":
            return _extract_docx(path)
        if ext == ".pdf":
            return _extract_pdf(path)
        if ext in TEXT_EXT:                    # docs + code + config: plain read
            return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [rag] extract failed for {path}: {e}")
    return ""

# ── Embeddings (llama.cpp --embeddings, OpenAI-style) ─────────────────────────
_embed_child = None

def _find_embed_model():
    """Auto-discover an embedding GGUF in models/ so no absolute path is needed.
    Matches by the usual embedder name markers."""
    mdir = BASE / "models"
    if not mdir.is_dir():
        return ""
    marks = ("embed", "nomic", "minilm", "bge", "gte", "e5")
    for f in sorted(mdir.glob("*.gguf")):
        if any(m in f.name.lower() for m in marks):
            return str(f)
    return ""

def _maybe_autostart_embedder(cfg):
    """Optionally spawn a private llama-server --embeddings child on a loopback
    port. Paths are auto-resolved: the binary defaults to bin/llama-server.exe
    (same one the tray uses) and the model to the first embedding GGUF found in
    models/. So the only thing you have to provide is the model file itself; if
    it is missing we skip gracefully and the bridge waits for an external
    embed_url instead."""
    global _embed_child
    if not cfg.get("embed_autostart"):
        return
    if embedder_up(cfg):
        print("  [rag] embeddings server already reachable; reusing it")
        return
    binp = cfg.get("llama_bin") or str(BASE / "bin" / "llama-server.exe")
    modp = cfg.get("embed_model_path") or _find_embed_model()
    if not (binp and os.path.exists(binp)):
        print(f"  [rag] embed_autostart: llama-server not found at {binp}; skipping")
        return
    if not (modp and os.path.exists(modp)):
        print("  [rag] embed_autostart: no embedding GGUF in models/ "
              "(filename should contain embed/nomic/minilm/bge/gte/e5); skipping. "
              "Drop one in models/ and restart.")
        return
    print(f"  [rag] embedder model: {os.path.basename(modp)}")
    port = urllib.parse.urlparse(cfg["embed_url"]).port or 8091
    try:
        # -b/--ubatch 8192: embeddings must fit the whole input in ONE physical
        # batch (default 512 rejects chunks > ~512 tokens). --n-gpu-layers 0
        # keeps this tiny model on CPU so it never fights the main LLM for VRAM.
        # Log the child's output to a file instead of hiding it, so a failed
        # launch (bad flag, OOM, missing dll) is diagnosable. *.log is gitignored.
        _elog = open(BASE / "selmo-rag-embed.log", "w", encoding="utf-8", errors="replace")
        _embed_child = subprocess.Popen(
            [binp, "-m", modp, "--embeddings", "--host", "127.0.0.1",
             "--port", str(port), "--pooling", "mean",
             "-c", "8192", "-b", "8192", "-ub", "8192", "--n-gpu-layers", "0"],
            stdout=_elog, stderr=subprocess.STDOUT,
            # Hide the console window on Windows (output already goes to the log),
            # matching how the tray launches its other child processes.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        atexit.register(lambda: _embed_child and _embed_child.terminate())
        print(f"  [rag] spawned embeddings child on 127.0.0.1:{port} (pid {_embed_child.pid})")
    except Exception as e:
        print(f"  [rag] could not spawn embeddings child: {e}")

def embed_batch(texts, cfg, prefix=""):
    """POST texts to <embed_url>/v1/embeddings; return list[list[float]].
    `prefix` is the model's task instruction (e.g. nomic's 'search_document: ')
    prepended to each text. Raises on failure so callers can surface a clear error."""
    url = cfg["embed_url"].rstrip("/") + "/v1/embeddings"
    inp = [prefix + t for t in texts] if prefix else list(texts)
    body = json.dumps({"model": cfg.get("embed_model", "local"),
                       "input": inp}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    rows = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in rows]

def _embed_all(texts, cfg, prefix, on_progress=None):
    """Embed many texts. Batches for speed, but if a batch is rejected (e.g.
    llama-server returns 500 because the combined tokens exceed its batch/context
    limit) it falls back to one request per item. A single item that still fails
    propagates, so a genuine per-chunk problem surfaces instead of being hidden.
    on_progress(done) is called after each batch so callers can show progress."""
    out, B, i = [], 8, 0
    while i < len(texts):
        batch = texts[i:i + B]
        try:
            out.extend(embed_batch(batch, cfg, prefix))
        except Exception:
            for t in batch:
                out.extend(embed_batch([t], cfg, prefix))
        i += B
        if on_progress:
            on_progress(len(out))
    return out

def embedder_up(cfg):
    # Short timeouts keep /status snappy so the client chip stays responsive.
    try:
        url = cfg["embed_url"].rstrip("/") + "/health"
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return r.status < 500
    except Exception:
        # /health may be absent; a models probe is a good enough liveness check
        try:
            url = cfg["embed_url"].rstrip("/") + "/v1/models"
            with urllib.request.urlopen(url, timeout=1.5) as r:
                return r.status < 500
        except Exception:
            return False

# ── Vector store (numpy matrix + meta sidecar; faiss used for search if present)
class Store:
    def __init__(self):
        self.vecs = None     # np.ndarray (n, dim), L2-normalised
        self.meta = []       # list of {source, title, chunk_id, text}
        self.index = None    # faiss index if available
        self.load()

    def load(self):
        if HAS_NUMPY and VEC_PATH.exists() and META_PATH.exists():
            try:
                self.vecs = np.load(VEC_PATH)
                self.meta = json.loads(META_PATH.read_text(encoding="utf-8"))
                self._build_index()
                print(f"  [rag] loaded index: {len(self.meta)} chunks")
            except Exception as e:
                print(f"  [rag] index load failed ({e}); starting empty")
                self.vecs, self.meta, self.index = None, [], None

    def _build_index(self):
        if HAS_FAISS and self.vecs is not None and len(self.vecs):
            idx = faiss.IndexFlatIP(self.vecs.shape[1])
            idx.add(self.vecs.astype("float32"))
            self.index = idx

    def save(self):
        if HAS_NUMPY and self.vecs is not None:
            np.save(VEC_PATH, self.vecs)
        META_PATH.write_text(json.dumps(self.meta, ensure_ascii=False),
                             encoding="utf-8")

    def replace(self, vecs, meta):
        self.vecs = _normalise(vecs) if len(vecs) else None
        self.meta = meta
        self._build_index()
        self.save()

    def search(self, qvec, k):
        if self.vecs is None or not len(self.meta):
            return []
        q = _normalise([qvec])[0]
        if self.index is not None:                       # faiss path
            import numpy as _np
            D, I = self.index.search(_np.asarray([q], dtype="float32"), k)
            order = [(int(i), float(d)) for i, d in zip(I[0], D[0]) if i >= 0]
        else:                                            # numpy brute force
            sims = self.vecs @ q
            top = sims.argsort()[::-1][:k]
            order = [(int(i), float(sims[i])) for i in top]
        return order

def _normalise(vecs):
    import numpy as _np
    a = _np.asarray(vecs, dtype="float32")
    norms = _np.linalg.norm(a, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return a / norms

STORE = None  # built in main()

# Live indexing progress, polled by the client via GET /progress so a long
# reindex shows a bar instead of a single blocking request (which timed out
# through the front door and returned a non-JSON error page).
_PROGRESS = {"indexing": False, "phase": "idle", "files": 0,
             "chunks": 0, "chunks_total": 0, "done": False,
             "n_files": 0, "n_chunks": 0, "error": ""}

# ── Indexing ──────────────────────────────────────────────────────────────────
def reindex(cfg):
    corpus = cfg.get("corpus_dir", "").strip()
    if not corpus or not os.path.isdir(corpus):
        raise ValueError("corpus_dir is not set or does not exist")
    files, chunk_texts, meta = [], [], []
    size = int(cfg.get("chunk_size", 1200))
    exclude = set(cfg.get("exclude_dirs", []))   # user-unchecked top-level subfolders
    allowed = allowed_exts(cfg)                   # user-selected formats (or all known)
    for root, dirs, names in os.walk(corpus):
        # Prune the subfolders the user unchecked + hidden dirs (.git, .venv, …).
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith(".")]
        for name in sorted(names):
            if Path(name).suffix.lower() not in allowed:
                continue
            fpath = os.path.join(root, name)
            text = extract_any(fpath)
            if not text.strip():
                continue
            files.append(fpath)
            _PROGRESS["files"] = len(files)
            for ci, (a, b) in enumerate(build_chunks(text, size)):
                snippet = text[a:b].strip()
                if not snippet:
                    continue
                chunk_texts.append(snippet)
                meta.append({
                    "source":   fpath,
                    "title":    name,
                    "chunk_id": ci,
                    "text":     snippet,
                })
    if not chunk_texts:
        STORE.replace([], [])
        return {"ok": True, "n_files": len(files), "n_chunks": 0}
    # Embed in small batches with single-item fallback (see _embed_all); report
    # progress so the client can draw a bar.
    _PROGRESS.update({"phase": "embedding", "chunks_total": len(chunk_texts), "chunks": 0})
    vecs = _embed_all(chunk_texts, cfg, cfg.get("doc_prefix", ""),
                      lambda done: _PROGRESS.__setitem__("chunks", done))
    _PROGRESS["phase"] = "saving"
    STORE.replace(vecs, meta)
    return {"ok": True, "n_files": len(files), "n_chunks": len(meta)}

def start_reindex(cfg):
    """Kick off reindex in a background thread and return immediately, so the
    HTTP request doesn't block for minutes (which timed out through the proxy).
    The client polls GET /progress."""
    if _PROGRESS.get("indexing"):
        return {"ok": True, "started": False, "already": True}
    _PROGRESS.update({"indexing": True, "phase": "scanning", "files": 0,
                      "chunks": 0, "chunks_total": 0, "done": False,
                      "n_files": 0, "n_chunks": 0, "error": ""})
    def _worker():
        try:
            r = reindex(cfg)
            _PROGRESS.update({"n_files": r.get("n_files", 0),
                              "n_chunks": r.get("n_chunks", 0), "phase": "done"})
        except Exception as e:
            _PROGRESS.update({"error": str(e), "phase": "error"})
        finally:
            _PROGRESS.update({"indexing": False, "done": True})
    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "started": True}

def search(query, k, cfg):
    if STORE.vecs is None or not len(STORE.meta):
        return []
    qvec = embed_batch([query], cfg, cfg.get("query_prefix", ""))[0]
    hits = STORE.search(qvec, k)
    out = []
    for i, _score in hits:
        m = STORE.meta[i]
        out.append({
            "title":   m["title"],
            "url":     f'{m["source"]}#chunk-{m["chunk_id"]}',
            "snippet": m["text"][:600],
        })
    return out

def browse(dirpath, cfg):
    """List a folder's top-level subfolders + the indexable formats present in
    its whole tree, so the client can render subfolder + format checkboxes."""
    dirpath = (dirpath or "").strip()
    if not dirpath or not os.path.isdir(dirpath):
        return {"ok": False, "error": "not a folder", "dir": dirpath,
                "subdirs": [], "formats": []}
    try:
        subdirs = sorted([e.name for e in os.scandir(dirpath)
                          if e.is_dir() and not e.name.startswith(".")],
                         key=str.lower)
    except Exception as e:
        return {"ok": False, "error": str(e), "dir": dirpath,
                "subdirs": [], "formats": []}
    exts = {}
    for root, dirs, names in os.walk(dirpath):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for n in names:
            e = Path(n).suffix.lower()
            if e in KNOWN_EXTS:
                exts[e] = exts.get(e, 0) + 1
    formats = [{"ext": e, "count": exts[e]} for e in sorted(exts)]
    return {"ok": True, "dir": dirpath, "subdirs": subdirs, "formats": formats}

# ── HTTP handler (mirrors selmo_web.py) ───────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)
        cfg    = load_cfg()

        if parsed.path == "/status":
            self._json({
                "ok":          True,
                "corpus_dir":  cfg.get("corpus_dir", ""),
                "n_chunks":    len(STORE.meta),
                "embed_model": cfg.get("embed_model", ""),
                "embedder_up": embedder_up(cfg),
                "backend":     "faiss" if HAS_FAISS else "numpy",
                "exclude_dirs": cfg.get("exclude_dirs", []),
                "formats":     cfg.get("formats", []),
            })

        elif parsed.path == "/search":
            q = qs.get("q", [""])[0].strip()
            k = int(qs.get("n", [str(cfg.get("top_k", 5))])[0])
            if not q:
                self._json({"error": "empty query"}); return
            try:
                self._json(search(q, k, cfg))
            except Exception as e:
                self._json({"error": f"search failed: {e}"})

        elif parsed.path == "/browse":
            d = qs.get("dir", [cfg.get("corpus_dir", "")])[0]
            self._json(browse(d, cfg))

        elif parsed.path == "/progress":
            self._json(dict(_PROGRESS))

        else:
            self.send_response(404); self._cors(); self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        cfg    = load_cfg()
        if parsed.path == "/config":
            # Persist a few config keys from the browser so corpus selection +
            # reindex can be driven entirely from the GUI (no editing the JSON).
            try:
                length  = int(self.headers.get("Content-Length", 0) or 0)
                payload = json.loads(self.rfile.read(length) or b"{}")
                for k in ("corpus_dir", "chunk_size", "embed_url",
                          "embed_model", "top_k", "embed_autostart",
                          "llama_bin", "embed_model_path",
                          "exclude_dirs", "formats"):
                    if k in payload:
                        cfg[k] = payload[k]
                CFG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
                self._json({"ok": True, "corpus_dir": cfg.get("corpus_dir", "")})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif parsed.path == "/reindex":
            try:
                self._json(start_reindex(cfg))
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        else:
            self.send_response(404); self._cors(); self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Type", "application/json; charset=utf-8")

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200); self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global STORE
    cfg = load_cfg()
    print()
    print("  selmo_rag.py — local RAG (retrieval) bridge")
    print(f"  http://localhost:{PORT}/status")
    print(f"  http://localhost:{PORT}/search?q=query")
    print(f"  vector backend: {'faiss' if HAS_FAISS else 'numpy'}"
          f"{'' if HAS_NUMPY else '  (numpy MISSING — install numpy)'}")
    print(f"  embeddings: {cfg.get('embed_url')}  model={cfg.get('embed_model')}")
    print()
    if not HAS_NUMPY:
        print("  [rag] FATAL: numpy is required. pip install numpy --break-system-packages")
        sys.exit(1)
    _maybe_autostart_embedder(cfg)
    STORE = Store()
    # Bind loopback only: reached exclusively through the front door
    # (/proxy/8088), which connects over 127.0.0.1. (security review parity with
    # selmo_web.py — never expose an unauthenticated bridge to the LAN.)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  [rag] stopped.")

if __name__ == "__main__":
    main()
