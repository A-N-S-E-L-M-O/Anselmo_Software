# Selmo — Bug Report
*Living document · updated session 18 · June 2026*

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

---

## Resolved

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
