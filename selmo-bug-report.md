# Selmo — Bug Report
*Living document · updated session 26 · June 2026*

---

## BUG-META-01 · Never use the Edit tool on chat.html ⚠️ PERMANENT RULE

**Symptom** — Using the `Edit` tool on `chat.html` truncates the file halfway (verified s4, s5, s7).

**Rule — NEVER DEVIATE**
- Edit `chat.html` only with Python via bash (`open` → `replace` → `write`), never with the Edit tool.
- After every change: extract the inline script and `node --check`; verify with the **Read** tool; the file must end with `</script></body></html>`.
- Restart `llama-server` after the change + Ctrl+F5.

---

## BUG-META-02 · NUL / line-ending corruption on the mount ⚠️ (session 13)

Files written/edited via tools on this mount can end up full of NUL bytes (`\x00`) and/or with wrong line endings. It happened in s13 to `Selmo.bat` (593 NUL + LF → the `^` continuation broke cmd → fragments executed as commands → crash on startup) and to `selmo-bug-report.md` (3684 NUL → grep saw it as "binary"). The **Write** tool seems to be the culprit; the **Edit** tool and Python writes stay clean.

**Rule**: after every change to a `.bat`/`.md`, check `python3 -c "print(open('f','rb').read().count(b'\x00'))"` → it must return 0. The `.bat` files must be **CRLF**. Cleanup: remove the NULs and rewrite (the `.bat` files in CRLF), preferably via Python.

**Read-side variant (session 16).** The same mount also serves **stale, truncated** *read* views: bash `cat`/`wc` showed `chat.html` as 2025 lines while the real file was 2361 lines ending cleanly in `</script></body></html>`, and `git` (reading through the same mount) reported phantom "337 deletions". The disk file was intact: the **Read tool** and **`git show HEAD:<file>`** (object store) both returned true content. Implications: don't trust bash views of `chat.html`; verify with the Read tool; and **never edit `chat.html` via Python-in-bash while the bash view is truncated** — a write-back would chop the real file to the truncated length. A session restart clears the stale cache.

---

## BUG-IMG-02 · Vision from phone → HTTP 400 ⚠️ OPEN — needs phone retest (session 15)

**Symptom** — Uploading an image from the phone (Android) makes the multimodal request to `llama-server` (8080) return **HTTP 400**. The model in use (Magistral-Small-2509) has the mmproj loaded (auto-match on `Magistral-` in `Selmo.bat`), so vision is active and worked from the desktop.

**Already done (v0.708, not a fix)**
- Client-side image normalization: `createImageBitmap`→canvas→JPEG, long-side cap 1280px, `accept="image/*"` (handles large photos and iPhone HEIC via Safari's decode).
- `max_tokens` capped at 1200 when there is an image (to avoid overflowing ctx 8192 with the image tokens).
- The client now shows the **body of the error** from the server instead of a bare "HTTP 400".

**Next step** — Read the real server message (now visible in the bubble) and distinguish: ctx overflow, image decode error, or "multimodal not supported" for Magistral. If it's Magistral that can't handle vision, fall back to Gemma 4 for image tasks.

**Status (s18)** — Diagnostics are all in place (error body shown in the bubble, client resize to 1280px JPEG, `max_tokens` cap when an image is attached). Nothing more to change in code until an actual phone retest captures the real 400 message.

---

## BUG-MIC-01 · Whisper over HTTPS is painful (self-signed cert) ⚠️ OPEN (session 18)

**Symptom** — Microphone capture (Whisper STT) needs a **secure context**; browsers only grant `getUserMedia` over HTTPS (or `localhost`). On the phone over LAN that means the 8443 reverse proxy (`selmo_https_proxy.py`) with the self-signed `selmo.crt`/`selmo.key`, so the browser shows "not secure" warnings and the user must click through the cert exception — and some browsers still block the mic outright.

**Why** — A self-signed cert isn't trusted, and `getUserMedia` refuses to run in an untrusted/insecure origin. Browser security policy, not a Selmo bug per se.

**Fix options — Selmo runs on Firefox (next session)**
- **Firefox `about:config` (fastest)** — set `media.getusermedia.insecure.enabled = true` and `media.devices.insecure.enabled = true`; this grants the mic over plain HTTP with no cert at all. Works on desktop and on Firefox for Android (type `about:config` in the URL bar). Per-profile/device.
- **Permanent cert exception** — keep the 8443 HTTPS proxy and add a *permanent* exception for the self-signed `selmo.crt` in Firefox ("Advanced → Accept the Risk and Continue"). Firefox persists it, so the warning is one-time per device and the origin becomes a trusted secure context.
- **mkcert (cleanest)** — generate a locally-trusted cert for the LAN IP. Caveat: Firefox uses its **own NSS trust store**, not the OS one, so either import the mkcert root CA into Firefox (Settings → Privacy & Security → Certificates → Authorities → Import) **or** set `security.enterprise_roots.enabled = true` so Firefox honours the OS store. Replaces `selmo.crt`/`selmo.key`.

*(Chrome's `unsafely-treat-insecure-origin-as-secure` flag does **not** apply — Selmo runs on Firefox.)*

**Status (s23, v0.831) — mitigated by the front door.** `selmo_https_proxy.py` is now the single entry point and serves the same `chat.html` over HTTPS on 8443, so the phone gets a secure context there and the mic + VAD work after a one-time cert acceptance. The cert now auto-regenerates when the LAN IP changes (recorded in `selmo-cert-ip.txt`), so the manual delete step is gone. `chat.html` shows a banner with a tap-link to the 8443 page when it is opened over insecure HTTP on a non-localhost host (e.g. the phone on 8080), where the mic can never run. The one remaining friction is the self-signed-cert warning itself; the three trust options above (Firefox permanent exception / `about:config` / mkcert) still apply. Kept OPEN until a phone retest confirms mic + VAD over 8443.

---

## BUG-EXIT-01 · Python processes hang on exit ⚠️ FIXED (session 18)

**Symptom** — After clicking Exit in the tray, the `selmo_tray.py` process stays alive. All child processes (GPU monitor, web bridge, Whisper, TTS, HTTPS proxy) are correctly killed by `_cleanup()`, but the main tray process itself hangs because `icon.stop()` does not reliably unblock `icon.run()` on Windows (known pystray-on-Windows issue).

**Root cause** — `_do_exit` called `_cleanup()` then `icon.stop()`. If pystray's internal message loop didn't drain cleanly, `icon.run()` never returned, leaving the tray process alive indefinitely.

**Fix** — Replace `icon.stop()` with `os._exit(0)` in `_do_exit`. Since `_cleanup()` has already terminated/killed all children, `os._exit(0)` kills the tray process immediately, bypassing pystray's unreliable teardown.

```python
def _do_exit(icon, item):
    _cleanup()
    os._exit(0)
```

---

## BUG-WEB-IMG-01 · Image + WEB search: query not derived from image content 🧪 SUPPOSEDLY RESOLVED — TESTING SOLUTION (session 20)

**Symptom** — When an image is loaded and WEB is on, the web-search query is still based on the user's literal words (e.g. "why grayed out") rather than the specific content visible in the image (e.g. "MSI Z490-A PRO BIOS Wake Up Event Setup grayed out"). Web results are therefore irrelevant.

**Desired flow**
1. Analyse the image → model describes product names, model numbers, menu names, visible text
2. `rewriteQuery` receives that description as `docContext` and derives specific keywords from it (NOT from the user's words)
3. Web search with the image-informed query
4. Final answer: model gets image + description + web results

**What was tried (s19)**
- Pre-analysis call outputting a `SEARCH:` tag → model keeps paraphrasing the user's question regardless of prompt
- Passing image data URLs directly to `rewriteQuery` (multimodal rewrite) → same problem
- Two-step: pure description call → feed description to `rewriteQuery` with a context-priority instruction → **not yet confirmed working**

**Current code state (after s19 patches)**
- `rewriteQuery(rawMsg, history, docContext)` — when `docContext` present, sys prompt says "use specific terms from context, do NOT paraphrase user's words"
- Web search branch: if `fileImage` → description call (max 600 tok) → `_imgAnalysis` → `rewriteQuery(rawQuery, chatHistory, _imgAnalysis.slice(0,1500))`
- `ctxMsg` includes `_imgAnalysis` + full image (multimodal) + web results

**Solution under test (s20, v0.825)** — Replaced the two-step (describe → `rewriteQuery`) with a **single multimodal call** that keeps the user's question next to the pixels. The model must answer in a fixed shape — `SEEN: <identifiers read off the image>` then `QUERY: <search query>` — with one worked example (a Canon-camera case, deliberately *not* the MSI Z490 test image, so a real test can't be a false positive from example leakage). Forcing `SEEN` first makes it extract the concrete product/menu/error terms before composing the query, instead of paraphrasing the user's vague words. Thinking disabled the supported way (`chat_template_kwargs.enable_thinking:false` + plain retry); `QUERY:`/`SEEN:` parsed from `content`+`reasoning_content`; fall back to the text `rewriteQuery` if no `QUERY:` line. `_imgAnalysis` (= `SEEN`) still flows into the final answer's context. A visible yellow `⚡ img→query: "…"` line is appended to the user bubble (flags `RAW` when the image step didn't rewrite) so a test is conclusive without the console.

**Next step — confirm with a hard reload (Ctrl+Shift+R).** The s19/first-s20 test searched the raw "why is option grayed out" — the pre-fix behaviour — because Firefox served a cached `chat.html`. Retest on the BIOS image with WEB on and read the yellow `img→query` line. If it still shows `RAW` after a hard reload, the single-call vision rewrite is likely failing on **Qwen3-MoE specifically** (llama.cpp vision for it is fresh) — isolate by testing the same image on Gemma 4 / Magistral. Also fixed this pass: `exportChat` dumped image turns as `[object Object]` (printed the raw content array) — now uses `_orig`/joined text parts.

---

## BUG-NOANS-01 · Reasoning completes, then no answer — from the 2nd turn 🧪 FIX UNDER TEST (session 24)

**Symptom** — On the phone (and reproducible in general), the model finishes its reasoning (the panel fills, e.g. "reasoning complete (96 tok)") and then emits **no answer**: the bubble stays empty, "0 tok". It happens **from the second interaction onward**, with several different models, and **even with small contexts** — so it is not a context-overflow problem.

**Root cause** — Each finished turn is stored in `chatHistory` as `[THINK]reasoning[/THINK]answer` (needed for the collapsible panel and for saved sessions). But the chat send-sites passed `chatHistory` **verbatim** to llama-server (`messages:chatHistory`), so every follow-up request fed the model its **own prior reasoning** back inside the prompt. A reasoning model that sees a completed `[THINK]...[/THINK]` block in the history tends to open a fresh reasoning block and then stop — generating zero answer tokens. Turn 1 has no prior assistant reasoning, so it works; turn 2+ carries it and breaks. Model- and ctx-independent, exactly as reported. (The web path's `recentClean` already stripped `[THINK]` from the conversation summary — confirming reasoning was never meant to be re-fed as text; the main message array just wasn't doing the same.)

**Fix (v0.836, code)** — New `apiMessages()` helper (`chat.html`, just above `maxTok()`) returns `chatHistory` with each assistant turn's `[THINK]...[/THINK]` block stripped, leaving only the clean answer. The two streaming send-sites (normal chat and web) now send `messages:apiMessages()` instead of `messages:chatHistory`. `chatHistory` itself is untouched, so the THINK panel and session save/restore (`renderStored`) keep working; only the model stops seeing stale reasoning. The chunk pipeline builds its own `chunkHistory` and is unaffected.

**Next step — confirm on the phone.** Hard-reload (Ctrl+F5 / clear cache), restart `llama-server`, then have a multi-turn conversation with a reasoning model (the one in the screenshot, plus one more). The answer must appear on the 2nd, 3rd, … turns. If an answer is still ever empty after this, the remaining suspect is a single transition delta carrying both `reasoning_content` and `content` (the `if/else if` in `streamTokens` drops `content` on that delta) — but that would lose at most a fragment, not the whole answer.

## BUG-CHUNK-01 · Chunk task silently capped at ~512 output tokens 🧪 UNDER OBSERVATION (session 26)

**Symptom** — A chunked task (translation, analysis, extraction — *any* chunk job) returns every chunk truncated mid-sentence at exactly ~511 output tokens, losing most of each chunk. Seen translating a book with LFM2-8B-A1B (Swallow) at ctx 16384: 24/24 chunks reported "done" but each one cut after a few paragraphs.

**Root cause** — `processDoc` computes `maxTok = max(512, (N_CTX - system - prompt - 256) - chunking_size)`. The `max(512, …)` floor fires whenever `N_CTX` is too small relative to `chunking_size`. In practice `N_CTX` was the **fallback default 4096**, not the model's real ctx: the real value is read from `/props` once at page load (inside `checkServer`), and that fetch had **no retry**. If it failed or arrived late — e.g. the LLM was swapped out for image generation when the page loaded, so `/props` returned 502, then `ensureLLM` reloaded the model but never re-read `/props` — `N_CTX` stayed 4096. With `chunking_size` 4000 that gives `maxTok = 512`, while the input chunk (sized from `chunking_size`, *not* from N_CTX) still filled the window. So input ~fills 4096, output is floored to 512, the rest of each chunk is dropped. The header showing **"local"** instead of the model name is the same degraded state (model id missing from `/v1/models`). Not translation-specific — every chunk pipeline is affected.

**Mitigation (code, UNDER OBSERVATION)** — `chat.html`: new `MODEL_READY` flag, true only when `loadProps()` reads a real ctx (`n_ctx ≥ 1024`); `loadProps()` retries `/props` up to 10× (1.5 s apart) and is also called from `ensureLLM()` after a post-image reload, so `N_CTX` refreshes instead of staying stale. Pre-flight guard added to **both** chunk pipelines: `processDoc` aborts if `!MODEL_READY || maxTok<=512`, `processChunks` aborts if `!MODEL_READY`, showing a neutral message that asks the user to Ctrl+F5 and retry once the model name appears — instead of burning time and energy on 24 capped chunks.

**Next step — observe.** (1) Normal chunk tasks still run. (2) Force the degraded state (open the page while the LLM is swapped out / before it loads) and verify the task aborts with the message rather than truncating. (3) After an image generation, run a chunk task and confirm `N_CTX` is the real value. Residual design smell: the input chunk size derives from `chunking_size` alone, not from the live window, so a genuinely small-ctx model with an oversized `chunking_size` could still starve output (the `maxTok<=512` guard catches the extreme case; mid-range starvation is still possible). Consider clamping `inT` to `(N_CTX - overhead)/2` for output-heavy tasks.

## Resolved

### BUG-IMG-04 · Image model loaded -> 8080 stops responding — ✓ RESOLVED (v0.831)

**Symptom** — With the v0.830 VRAM swap, starting image generation unloaded llama-server to free the GPU. But llama-server also served `chat.html` on 8080, so unloading it took the whole web UI down: 8080 stopped answering until the next chat turn reloaded the model. A page refresh during image mode left nothing to load.

**Fix** — Decoupled the static UI host from the swappable LLM. `selmo_https_proxy.py` became an always-up front door on 8080 that serves `chat.html` from disk and reverse-proxies the backends; llama-server moved to private `127.0.0.1:8089` behind it (`/proxy/8089`). Unloading the LLM no longer touches the page host: while swapped, `/proxy/8089` returns 502 and `ensureLLM()` reloads on the next chat, but the page stays served. The client (`chat.html`) talks only to the front door via relative `/proxy/808x` paths, so the GUI uses one port regardless of which backend is loaded.

### BUG-IMG-03 · Vision + web search together — ✓ RESOLVED in code (verify with a quick test)

The fix the report had filed as "proposed" is actually implemented in `sendMsg`. When an image is loaded with WEB on, the web branch builds a multimodal array (the image pages + the web-context text) instead of a text-only prompt, so the image is no longer dropped (≈line 2042). `recentClean` also reads `m._orig` first and, when the content is an array, filters/joins the text parts — so the old `.replace()`-on-an-array exception is gone (≈line 2031). Confirmation run: load an image, turn WEB on, ask about it.

### BUG-IMG-01 · Vision + IMG/OCR (images/PDF) — ✓ RESOLVED (v0.702)

Three distinct causes, finally isolated:
1. **mmproj runtime crash** — Gemma 4's vision encoder uses non-causal attention: all image tokens must fit in a single ubatch. With the default ubatch (512) and a large image, `GGML_ASSERT(n_ubatch >= n_tokens)` would fire. Fix: `--batch-size 2048 --ubatch-size 2048`.
2. **Oversized/concatenated image** — pointless: Gemma 4 resizes to the token budget. Fix: one image **per page** at ~1280px + OCR budget `--image-min-tokens 1120 --image-max-tokens 1120`.
3. **Launcher startup crash (s13)** — it was NOT the flags: it was a corrupted `Selmo.bat` (NUL + LF). See BUG-META-02.

**v0.702 implementation**
- `chat.html`: dedicated **+ IMG/OCR** button; `loadFileAsImage` (images as-is, PDF one image per page ~1280px); sent as a multimodal array; **clickable thumbnails** (open at full resolution).
- `Selmo.bat` (mmproj branch): `--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048`.
- Verified working on Gemma 4 12B, RTX 4070 Ti 12GB.

### Archived
- **BUG-04** · `/web` TDZ on `chatHistory` — resolved (s13).
- **BUG-05** · `input()` double click in `chunk_pipeline.py` — resolved s9.
- **BUG-01 / BUG-02 / BUG-03** · old UI issues s7–s9 — to be re-checked only if they reappear.

---

*Bash mount note (s9): the Linux mount can stay frozen; verify with the Read tool. See BUG-META-02 for the NUL corruption.*
