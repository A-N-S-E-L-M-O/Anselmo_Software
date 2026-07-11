# Selmo — RAG mode strategy
*Analysis + plan only. Nothing applied. July 2026.*

## 1. Where we stand (verified)

Selmo has no retrieval layer and, by design, has never wanted one: the
feature matrix lists "Document RAG (chat with files)" as **no (by design)**, and
the differentiator is the exhaustive, provable-coverage pipeline
(`chunk_pipeline.py`), which is a different job from retrieval. RAG lives in
`selmo-dev.md` only as a parked *community-contribution candidate*
("index a local folder into a vector store; inject relevant chunks before each
reply … out of scope for the core").

What already exists and makes this cheap:

- **A bridge pattern.** Each capability is a single-purpose Python process on
  its own port, reverse-proxied by the front door (`selmo_https_proxy.py`):
  web 8081, monitor 8082, whisper 8083, tts 8084, image 8086, control 8087,
  llama 8089. `ALLOWED_PORTS = {8081..8087, 8089}`.
- **A toggle pattern.** The web feature is an explicit, user-flipped mode:
  `IS_WEB_ON` + `toggleWeb()` + a header button with a `web-dot`/`web-txt`
  status pill fed by `checkWebBridge()` → `GET /status`.
- **A retrieval-shaped send loop.** In `selmo-send.js`, the `if(isWebSearch)`
  branch already does the whole retrieve-then-answer dance: `rewriteQuery()`
  distils the turn into a query, `webSearch()` returns
  `[{title, url, snippet}]`, the results are formatted as `[1] [2] …` and
  injected via `ctxMsg` ("… Cite sources as [1], [2]"), and the sources footer
  renders from `proactiveSources`.
- **An extractor + chunker.** `chunk_pipeline.py` exposes `extract(path)`
  (PDF/DOCX/ODT/TXT) and `build_chunks(text, size)` — the same functions the
  parked `selmo_parallel.py` design already plans to import.

So RAG mode is not new machinery. It is a **second retrieval source wired into
the existing web plumbing**, behind its own toggle and its own port.

## 2. Design — mirror the web bridge exactly

One new port (**8088**), one new toggle (**`RAG ●`**), same status-pill and
same sources-footer behaviour. When RAG is on, the user's message is rewritten
into a query (reusing `rewriteQuery`), matched against an index of their own
files, and the top-k chunks are injected as context before the model answers —
identical to how web results are injected today. The "sources" in the footer
become filenames + chunk anchors instead of URLs.

Web and RAG stay **mutually exclusive** in v1 (like web vs image), to keep the
test surface small. Combining them (retrieve from corpus *and* web in one turn)
is a later enhancement; the injection format already supports concatenating
both.

## 3. Server — `selmo_rag.py` (port 8088)

A bridge in the shape of `selmo_web.py`, three endpoints:

- `GET /status` → `{ok, corpus_dir, n_chunks, embed_model, embedder_up}` —
  feeds the status pill, exactly like the web bridge's `/status`.
- `POST /reindex` → walk `corpus_dir`, `extract()` + `build_chunks()` each file,
  embed every chunk, (re)build the faiss index. Returns `{n_files, n_chunks}`.
- `GET /search?q=<query>&n=5` → embed the query, faiss top-k, return an array
  of **`{title, url, snippet}`** so the send loop treats it identically to web
  results. `title` = filename, `url` = source path + `#chunk-N`,
  `snippet` = the chunk text.

Internals:

- **Extraction/chunking:** import `extract` and `build_chunks` from
  `chunk_pipeline.py` (do not reimplement; same choice as `selmo_parallel.py`).
- **Vector store:** a persisted **faiss** index (`selmo-rag.index`) plus a
  sidecar JSON (`selmo-rag.meta.json`) holding `{chunk_text, source_path,
  offset}` per vector. Both **gitignored**, like `selmo-wh.json`.
- **Embedder — the one real dependency decision.** Recommended: `selmo_rag.py`
  spawns its **own `llama-server --embeddings`** child on a private loopback
  port (e.g. `127.0.0.1:8091`, *not* in `ALLOWED_PORTS`, not LAN-exposed),
  loading a small embedding GGUF (`nomic-embed-text-v1.5`). This keeps
  everything in the llama.cpp family, reuses the bundled engine, and pulls **no
  torch / sentence-transformers**. From the outside there is still exactly one
  new port (8088); the embedder is an internal child, like the process the
  image bridge already manages. The only new pip dependency is `faiss-cpu`.
  Cost: ~300 MB RAM/VRAM for the embedding model while indexing/searching.

## 4. Client — a twin of the web toggle

- **`chat.html`** — a `RAG` button next to `WEB` in the header, with
  `rag-dot`/`rag-txt`. (Edit via Python-in-bash only, never the Edit tool;
  bump the shared `?v=` on the scripts that change.)
- **`selmo-bridges.js`** — `checkRagBridge()` (copy of `checkWebBridge`, paints
  the pill from `/status`) and `ragSearch(query, n)` (copy of `webSearch`).
- **`selmo-sessions.js`** — `toggleRag()` (copy of `toggleWeb`, flips
  `IS_RAG_ON`, toggles the button `.on` class + caption).
- **`selmo-boot.js`** — globals `IS_RAG_ON` / `ragOk`, const `RAG =
  '/proxy/8088'`, and a `checkRagBridge()` call in the startup poll next to
  `checkWebBridge()`.
- **`selmo-send.js`** — an `if(IS_RAG_ON)` branch mirroring `if(isWebSearch)`:
  `rewriteQuery(txt, chatHistory, docCtx)` → `ragSearch()` → format `[1] [2] …`
  → the same `ctxMsg` injection → stream. `proactiveSources` populates the
  existing footer unchanged.

Because the search result shape and the injection path are shared, the only
genuinely new client logic is the toggle wiring and the one send-loop branch.

## 5. Touch-list, file by file

1. `selmo_rag.py` — new bridge on 8088 (`/status`, `/reindex`, `/search`);
   imports `extract`/`build_chunks`; manages the internal llama.cpp embedder +
   faiss index.
2. `selmo_https_proxy.py` — add `8088` to `ALLOWED_PORTS`; add the
   `/proxy/8088 -> selmo_rag` line to the port-map comment.
3. `selmo_tray.py` — one `_start_service("RAG Bridge [port 8088]",
   [str(BASE / "selmo_rag.py")])` next to the web-bridge line (~1205).
4. `selmo-bridges.js` — `checkRagBridge`, `ragSearch`.
5. `selmo-sessions.js` — `toggleRag`.
6. `selmo-boot.js` — `IS_RAG_ON`/`ragOk` globals, `RAG` const, startup check.
7. `selmo-send.js` — the `if(IS_RAG_ON)` branch.
8. `chat.html` — the `RAG` header button; `?v=` bump on changed scripts.
9. `selmo-rag-config.json` (new) — `corpus_dir` + embed-model name; the faiss
   index + meta sidecar go in `.gitignore`.
10. `selmo-models.ini` — an entry for the embedding GGUF so it is selectable
    like the other models.

## 6. Two decisions to settle before code

- **Corpus selection.** Minimal path: a `corpus_dir` in
  `selmo-rag-config.json` plus a `/reindex` endpoint. Later: a folder picker in
  the settings panel (`selmo-settings.js`), which already talks to the control
  API on 8087 — a matching `POST /rag/reindex` there would let indexing be
  triggered from the browser.
- **Embedder.** Recommended above: an internal llama.cpp `--embeddings` child
  (no torch, +`faiss-cpu`). The lighter-footprint alternative
  (sentence-transformers on CPU) is rejected because it drags in torch, against
  the minimal-dependency ethos.

## 7. Positioning

The toggle keeps retrieval RAG and the exhaustive provable-coverage pipeline
cleanly separate: the exhaustive pipeline stays the default document flow and
the project's identity, while RAG is an opt-in mode for querying a large corpus.
No blur, because the user chooses which one is active.

## 8. Recommendation & phasing

1. **Bridge first, headless.** Ship `selmo_rag.py` (8088) with a
   config-file `corpus_dir` and `/reindex`/`/search`, using the internal
   llama.cpp embedder + faiss. Prove it from `curl` before any UI. This is a
   committed checkpoint on its own, touching no client code.
2. **Toggle + send branch.** Add the `RAG` button, the bridge check, and the
   `if(IS_RAG_ON)` branch — the second checkpoint.
3. **Browser-side indexing (optional).** A settings-panel folder picker and a
   control-API reindex trigger.

Reuse over invention throughout: `rewriteQuery`, the `{title,url,snippet}`
result shape, the sources footer, and `chunk_pipeline.extract/build_chunks` all
carry over unchanged, so the net-new surface is one bridge, one toggle, and one
send-loop branch.
