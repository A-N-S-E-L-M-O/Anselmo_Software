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

def _idx_paths(kind):
    """Per-mode index files: selmo-rag.docs.* / selmo-rag.code.*"""
    return (BASE / f"selmo-rag.{kind}.vecs.npy", BASE / f"selmo-rag.{kind}.meta.json")

# The bridge's own artifacts: never index them (a meta json holds every chunk
# duplicated, which self-poisons retrieval). Skipped by absolute path.
_SELF_PATHS = {os.path.abspath(str(p)) for p in (
    CFG_PATH, BASE / "selmo-rag-embed.log",
    BASE / "selmo-rag.vecs.npy", BASE / "selmo-rag.meta.json",   # legacy single index
    *_idx_paths("docs"), *_idx_paths("code"))}

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
    # Two retrieval modes, each with its own tiny embedder + its own index:
    #   docs -> nomic-embed-text (prose)   |   code -> jina-embeddings-v2-base-code
    # 'mode' is the active query mode; the client switches it from the folder bar.
    "mode":             "docs",
    "embed_url_code":   "http://127.0.0.1:8092",       # code embedder (jina) server
    "embed_model_code": "jina-embeddings-v2-base-code",
    "embed_model_path_code": "",                        # auto: first jina/code GGUF in models/
    "doc_prefix_code":  "",                             # jina-v2 needs no task prefix
    "query_prefix_code":"",
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

# Extensions where function/class-aware chunking helps (code, not prose/markup).
CODE_EXT = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".h", ".cpp",
            ".hpp", ".go", ".rs", ".rb", ".php", ".sh", ".bat", ".ps1", ".sql"}

# Start of a function/class/method definition across common languages.
_DEF_RE = re.compile(
    r'^[ \t]*(?:'
    r'(?:async[ \t]+)?def[ \t]+(\w+)'                          # python def
    r'|class[ \t]+(\w+)'                                       # class
    r'|(?:export[ \t]+)?(?:async[ \t]+)?function[ \t]+(\w+)'   # js function
    r'|(?:export[ \t]+)?(?:const|let|var)[ \t]+(\w+)[ \t]*=[ \t]*'
    r'(?:async[ \t]*)?(?:\([^)]*\)[ \t]*=>|function\b)'         # js arrow/fn const
    r')', re.M)

def _enclosing_symbol(text, upto):
    """Name of the last function/class defined at or before `upto` (best effort)."""
    last = None
    for m in _DEF_RE.finditer(text, 0, upto):
        last = m
    return next((g for g in last.groups() if g), "") if last else ""

def _line_offsets(text):
    offs, c = [], 0
    for ln in text.split("\n"):
        offs.append(c); c += len(ln) + 1
    return offs

def _code_chunks(text, size):
    """Split code at top-level definition boundaries so functions stay whole;
    oversized blocks fall back to the char chunker."""
    lines = text.split("\n")
    offs = _line_offsets(text)
    n = len(text)
    starts = [0]
    for i, ln in enumerate(lines):
        if i and _DEF_RE.match(ln) and (len(ln) - len(ln.lstrip())) <= 4:
            starts.append(i)
    starts = sorted(set(starts))
    ranges = []
    for j, s in enumerate(starts):
        a = offs[s]
        b = offs[starts[j + 1]] if j + 1 < len(starts) else n
        if b <= a:
            continue
        if b - a > size * 3:                       # huge block: sub-split by chars
            for aa, bb in build_chunks(text[a:b], size):
                ranges.append((a + aa, a + bb))
        else:
            ranges.append((a, b))
    return ranges or build_chunks(text, size)

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
_embed_children = []
atexit.register(lambda: [c.terminate() for c in _embed_children if c])

def _find_embed_model(include, exclude=()):
    """Auto-discover an embedding GGUF in models/ by name markers (no path needed)."""
    mdir = BASE / "models"
    if not mdir.is_dir():
        return ""
    for f in sorted(mdir.glob("*.gguf")):
        n = f.name.lower()
        if any(m in n for m in include) and not any(x in n for x in exclude):
            return str(f)
    return ""

# Name markers used to auto-find each embedder in models/.
_DOC_MARKS  = ("nomic", "minilm", "bge", "gte", "e5", "embed")
_CODE_MARKS = ("code", "jina")

def _embedder(kind, cfg):
    """(url, model, prefixes) for a retrieval kind: 'docs' (nomic) or 'code' (jina)."""
    if kind == "code":
        return {"url":   cfg.get("embed_url_code") or "http://127.0.0.1:8092",
                "model": cfg.get("embed_model_code") or "code",
                "doc_prefix":   cfg.get("doc_prefix_code", ""),
                "query_prefix": cfg.get("query_prefix_code", "")}
    return {"url":   cfg.get("embed_url") or "http://127.0.0.1:8091",
            "model": cfg.get("embed_model") or "local",
            "doc_prefix":   cfg.get("doc_prefix", ""),
            "query_prefix": cfg.get("query_prefix", "")}

def _spawn_embedder(binp, modp, port, tag):
    """Spawn one llama-server --embeddings child on a private loopback port.
    -b/-ub 8192: the whole input must fit ONE physical batch (default 512 rejects
    >512-token chunks with a 500). --n-gpu-layers 0 keeps this tiny model on CPU
    so it never fights the main LLM for VRAM. Console hidden, stderr -> log."""
    try:
        _elog = open(BASE / f"selmo-rag-embed-{tag}.log", "w", encoding="utf-8", errors="replace")
        p = subprocess.Popen(
            [binp, "-m", modp, "--embeddings", "--host", "127.0.0.1",
             "--port", str(port), "--pooling", "mean",
             "-c", "8192", "-b", "8192", "-ub", "8192", "--n-gpu-layers", "0"],
            stdout=_elog, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        _embed_children.append(p)
        print(f"  [rag] spawned {tag} embedder on 127.0.0.1:{port} "
              f"({os.path.basename(modp)}, pid {p.pid})")
    except Exception as e:
        print(f"  [rag] could not spawn {tag} embedder: {e}")

def _maybe_autostart_embedder(cfg):
    """Spawn BOTH tiny embedders on CPU if not already up: docs (nomic) + code
    (jina). Paths auto-resolve to bin/llama-server.exe + the first matching GGUF
    in models/; a missing model is skipped gracefully (that mode just stays empty)."""
    if not cfg.get("embed_autostart"):
        return
    binp = cfg.get("llama_bin") or str(BASE / "bin" / "llama-server.exe")
    if not os.path.exists(binp):
        print(f"  [rag] embed_autostart: llama-server not found at {binp}; skipping")
        return
    plan = [
        ("docs", _embedder("docs", cfg)["url"],
         cfg.get("embed_model_path") or _find_embed_model(_DOC_MARKS, exclude=_CODE_MARKS)),
        ("code", _embedder("code", cfg)["url"],
         cfg.get("embed_model_path_code") or _find_embed_model(_CODE_MARKS)),
    ]
    for tag, url, modp in plan:
        if embedder_up(url):
            print(f"  [rag] {tag} embedder already reachable; reusing it")
            continue
        if not (modp and os.path.exists(modp)):
            hint = "nomic-embed*" if tag == "docs" else "jina*/*code*"
            print(f"  [rag] {tag} embedder: no matching GGUF in models/ ({hint}); skipping")
            continue
        port = urllib.parse.urlparse(url).port or (8091 if tag == "docs" else 8092)
        _spawn_embedder(binp, modp, port, tag)

def embed_batch(texts, emb, prefix=""):
    """POST texts to an embedder <url>/v1/embeddings; return list[list[float]].
    `emb` is the {url, model, ...} dict from _embedder(kind). `prefix` is the
    model's task instruction (nomic's 'search_document: '); empty for jina.
    Raises on failure so callers can surface a clear error."""
    url = emb["url"].rstrip("/") + "/v1/embeddings"
    inp = [prefix + t for t in texts] if prefix else list(texts)
    body = json.dumps({"model": emb.get("model", "local"),
                       "input": inp}).encode("utf-8")
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))
    rows = sorted(data.get("data", []), key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in rows]

def _embed_all(texts, emb, prefix, on_progress=None):
    """Embed many texts with embedder `emb`. Batches for speed, but if a batch is
    rejected (e.g. llama-server 500 when the combined tokens exceed its limit) it
    falls back to one request per item. A single item that still fails propagates.
    on_progress(done) is called after each batch so callers can show progress."""
    out, B, i = [], 8, 0
    while i < len(texts):
        batch = texts[i:i + B]
        try:
            out.extend(embed_batch(batch, emb, prefix))
        except Exception:
            for t in batch:
                out.extend(embed_batch([t], emb, prefix))
        i += B
        if on_progress:
            on_progress(len(out))
    return out

def embedder_up(url):
    # Short timeouts keep /status snappy so the client chip stays responsive.
    for path in ("/health", "/v1/models"):
        try:
            with urllib.request.urlopen(url.rstrip("/") + path, timeout=1.5) as r:
                return r.status < 500
        except Exception:
            continue
    return False

# ── Vector store (numpy matrix + meta sidecar; faiss used for search if present)
class Store:
    def __init__(self, vec_path, meta_path, name=""):
        self.vec_path  = vec_path
        self.meta_path = meta_path
        self.name = name
        self.vecs = None     # np.ndarray (n, dim), L2-normalised
        self.meta = []       # list of {source, title, chunk_id, text}
        self.index = None    # faiss index if available
        self.load()

    def load(self):
        if HAS_NUMPY and self.vec_path.exists() and self.meta_path.exists():
            try:
                self.vecs = np.load(self.vec_path)
                self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
                self._build_index()
                print(f"  [rag] loaded {self.name} index: {len(self.meta)} chunks")
            except Exception as e:
                print(f"  [rag] {self.name} index load failed ({e}); starting empty")
                self.vecs, self.meta, self.index = None, [], None

    def _build_index(self):
        if HAS_FAISS and self.vecs is not None and len(self.vecs):
            idx = faiss.IndexFlatIP(self.vecs.shape[1])
            idx.add(self.vecs.astype("float32"))
            self.index = idx

    def save(self):
        if HAS_NUMPY and self.vecs is not None:
            np.save(self.vec_path, self.vecs)
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False),
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

STORE_DOC  = None  # docs index (nomic) — built in main()
STORE_CODE = None  # code index (jina)  — built in main()

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
    files = []
    doc_texts, doc_meta, code_texts, code_meta = [], [], [], []
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
            if os.path.abspath(fpath) in _SELF_PATHS:   # skip our own index/config/log
                continue
            text = extract_any(fpath)
            if not text.strip():
                continue
            files.append(fpath)
            _PROGRESS["files"] = len(files)
            ext = Path(name).suffix.lower()
            is_code = ext in CODE_EXT
            rel = os.path.relpath(fpath, corpus)
            ranges = _code_chunks(text, size) if is_code else build_chunks(text, size)
            for ci, (a, b) in enumerate(ranges):
                snippet = text[a:b].strip()
                if not snippet:
                    continue
                # Contextual header: file path (+ enclosing function/class for code).
                # Embedded AND shown to the model, so a query naming a file/symbol
                # matches the right chunk and the model always knows its source.
                sym = _enclosing_symbol(text, b) if is_code else ""
                header = "File: " + rel + (" · " + sym if sym else "")
                stored = header + "\n" + snippet
                rec = {"source": fpath, "title": name, "chunk_id": ci, "text": stored}
                # Route each file to its mode's index: code -> jina, everything
                # else (prose/markup/config) -> nomic.
                if is_code:
                    code_texts.append(stored); code_meta.append(rec)
                else:
                    doc_texts.append(stored);  doc_meta.append(rec)
    _PROGRESS.update({"phase": "embedding",
                      "chunks_total": len(doc_texts) + len(code_texts), "chunks": 0})
    # docs bucket -> nomic (primary: if its embedder is down, that's an error).
    doc_emb = _embedder("docs", cfg)
    if doc_texts:
        if not embedder_up(doc_emb["url"]):
            raise RuntimeError("docs embedder (nomic) not reachable at " + doc_emb["url"])
        dvecs = _embed_all(doc_texts, doc_emb, doc_emb["doc_prefix"],
                           lambda d: _PROGRESS.__setitem__("chunks", d))
        STORE_DOC.replace(dvecs, doc_meta)
    else:
        STORE_DOC.replace([], [])
    # code bucket -> jina (optional: skipped, not fatal, if jina isn't installed).
    code_emb, note = _embedder("code", cfg), ""
    if code_texts:
        if embedder_up(code_emb["url"]):
            base = len(doc_texts)
            cvecs = _embed_all(code_texts, code_emb, code_emb["doc_prefix"],
                               lambda d: _PROGRESS.__setitem__("chunks", base + d))
            STORE_CODE.replace(cvecs, code_meta)
        else:
            note = ("code embedder (jina) not reachable - code index left unchanged; "
                    "drop a jina/code GGUF in models/ and restart the tray")
    _PROGRESS["phase"] = "saving"
    return {"ok": True, "n_files": len(files),
            "docs": len(doc_meta), "code": (len(code_meta) if not note else 0),
            "n_chunks": len(doc_meta) + (len(code_meta) if not note else 0),
            "note": note}

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

def search(query, k, cfg, mode="docs"):
    store = STORE_CODE if mode == "code" else STORE_DOC
    if store is None or store.vecs is None or not len(store.meta):
        return []
    emb = _embedder("code" if mode == "code" else "docs", cfg)
    qvec = embed_batch([query], emb, emb["query_prefix"])[0]
    hits = store.search(qvec, k)
    out = []
    for i, _score in hits:
        m = store.meta[i]
        out.append({
            "title":   m["title"],
            "url":     f'{m["source"]}#chunk-{m["chunk_id"]}',
            "snippet": m["text"],   # whole chunk (already bounded by chunk_size)
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
            mode = cfg.get("mode", "docs")
            doc_url, code_url = _embedder("docs", cfg)["url"], _embedder("code", cfg)["url"]
            docs_up, code_up = embedder_up(doc_url), embedder_up(code_url)
            self._json({
                "ok":          True,
                "corpus_dir":  cfg.get("corpus_dir", ""),
                "mode":        mode,
                "n_chunks":    len(STORE_CODE.meta) if mode == "code" else len(STORE_DOC.meta),
                "docs_chunks": len(STORE_DOC.meta),
                "code_chunks": len(STORE_CODE.meta),
                "embed_model": cfg.get("embed_model", ""),
                "embedder_up": code_up if mode == "code" else docs_up,  # active mode
                "docs_up":     docs_up,
                "code_up":     code_up,
                "backend":     "faiss" if HAS_FAISS else "numpy",
                "exclude_dirs": cfg.get("exclude_dirs", []),
                "formats":     cfg.get("formats", []),
            })

        elif parsed.path == "/search":
            q = qs.get("q", [""])[0].strip()
            k = int(qs.get("n", [str(cfg.get("top_k", 5))])[0])
            mode = qs.get("mode", [cfg.get("mode", "docs")])[0]
            if not q:
                self._json({"error": "empty query"}); return
            try:
                self._json(search(q, k, cfg, mode))
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
                          "exclude_dirs", "formats",
                          "mode", "embed_url_code", "embed_model_code",
                          "embed_model_path_code"):
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
    global STORE_DOC, STORE_CODE
    cfg = load_cfg()
    print()
    print("  selmo_rag.py — local RAG (retrieval) bridge")
    print(f"  http://localhost:{PORT}/status")
    print(f"  http://localhost:{PORT}/search?q=query&mode=docs|code")
    print(f"  vector backend: {'faiss' if HAS_FAISS else 'numpy'}"
          f"{'' if HAS_NUMPY else '  (numpy MISSING — install numpy)'}")
    print(f"  docs embedder: {cfg.get('embed_url')}  |  code embedder: {cfg.get('embed_url_code')}")
    print()
    if not HAS_NUMPY:
        print("  [rag] FATAL: numpy is required. pip install numpy --break-system-packages")
        sys.exit(1)
    _maybe_autostart_embedder(cfg)
    STORE_DOC  = Store(*_idx_paths("docs"), name="docs")
    STORE_CODE = Store(*_idx_paths("code"), name="code")
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
