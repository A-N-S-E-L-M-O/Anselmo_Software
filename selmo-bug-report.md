# Selmo — Bug Report
*Living document · updated session 15 · June 2026*

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

---

## BUG-IMG-02 · Vision from phone → HTTP 400 ⚠️ OPEN (session 15)

**Symptom** — Uploading an image from the phone (Android) makes the multimodal request to `llama-server` (8080) return **HTTP 400**. The model in use (Magistral-Small-2509) has the mmproj loaded (auto-match on `Magistral-` in `Selmo.bat`), so vision is active and worked from the desktop.

**Already done (v0.708, not a fix)**
- Client-side image normalization: `createImageBitmap`→canvas→JPEG, long-side cap 1280px, `accept="image/*"` (handles large photos and iPhone HEIC via Safari's decode).
- `max_tokens` capped at 1200 when there is an image (to avoid overflowing ctx 8192 with the image tokens).
- The client now shows the **body of the error** from the server instead of a bare "HTTP 400".

**Next step** — Read the real server message (now visible in the bubble) and distinguish: ctx overflow, image decode error, or "multimodal not supported" for Magistral. If it's Magistral that can't handle vision, fall back to Gemma 4 for image tasks.

---

## BUG-IMG-03 · Vision + web search together doesn't work ⚠️ OPEN (session 15)

**Symptom** — With an image loaded **and** WEB active (or the `/web` command), the image is not analyzed.

**Cause (identified)** — In `sendMsg`, when `IS_WEB_ON`/`isWebSearch` is true, the flow enters the web branch (≈line 1643) which builds a **text-only** prompt (source context) and handles/closes its own fetch **before** reaching the multimodal block `if(fileImage)` (≈line 1706): the attached image is therefore ignored. Also `recentClean` does `.replace(...)` on `m.content` which, for a previous image message, is an **array** → possible exception.

**Proposed fix** — In the web branch include `imgContent` in the content array too (context text + `image_url`), or establish an explicit priority with a warning ("web ignores the image"). Handle the `content` array case inside `recentClean` (skip it or serialize it).

---

## Resolved

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
