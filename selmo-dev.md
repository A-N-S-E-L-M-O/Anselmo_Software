# Selmo — Development documentation
*Updated session 16 · 2026-06-13 · v0.716*

---

## v0.716 — tok/sec bar + HTTPS proxy for mobile mic (session 16 cont.)

**tok/sec bar — dynamic scale with colour coding:**
The fondoscala is no longer fixed. `_tokScale` starts at 20 tok/s (realistic for Magistral 24B Q3).
If tokSec exceeds 95% of the current scale, the scale auto-expands to the next multiple of 10 above `tokSec × 1.2`.
Colour: **cyan** ≥ 20 tok/s · **yellow** 10–20 · **red** < 10. The bar never pegs; no "casino" effect.

**HTTPS proxy for mobile microphone (`selmo_https_proxy.py`, port 8443):**
Mobile browsers block `getUserMedia()` on non-secure HTTP origins — so Whisper was always broken on the phone.
`selmo_https_proxy.py` is a lightweight Python HTTPS reverse proxy:
- Generates a self-signed TLS cert (`selmo.crt` / `selmo.key`) on first run, with the machine's LAN IP in the SAN.
- Listens on `:8443` and routes `/proxy/808X/path` → the matching local service; everything else → llama-server (8080).
- `chat.html` detects `location.protocol === 'https:'` and switches all service URLs to `/proxy/808X` paths (avoids mixed-content blocks).
- The proxy is started automatically by `selmo_server.py` alongside the other services.

**Usage from phone:** `https://192.168.x.x:8443/chat.html` — Firefox shows a cert warning once, user clicks "Accept the risk" — done. Desktop continues to use `http://127.0.0.1:8080` unchanged.

**Lesson:** delete `selmo.crt` / `selmo.key` if the machine's LAN IP changes (the cert embeds the IP in the SAN). The proxy regenerates them on the next startup.

## v0.714 — Phone UI fixes + chunking lessons (session 16)

**Phone header (≤400px):** THINK button was hidden (`display:none`); replaced with compact padding so it stays visible. NEW CHAT label collapsed to "CHAT" via CSS `::before` pseudo-element (no HTML change).

**Mobile keyboard:** added `interactive-widget=resizes-content` to the viewport meta (Android Chrome) and a `visualViewport` resize listener that sets `body.style.height` dynamically — keeps the input area above the software keyboard on both Android and iOS.

**llama-server OOM on Magistral:** `CTX=0` (model training context, 32K+) caused a 20 GB KV-cache allocation on a 12 GB GPU. Fixed by setting `CTX=8192` in `Selmo.bat`. `--fit on` was tried but discarded — it fell back to CPU and reduced throughput to ~3 chunks vs the normal ~39.

**Chunking / verbatim-copy behaviour:** the model (Magistral-Small) starts copying source text verbatim after summarising the first few paragraphs of a chunk. Root cause is instruction-following drift over long generations — the instruction loses weight as more source tokens are processed. Reversing prompt/content order made things worse. **Workaround (confirmed working): cap the output via the user prompt** — e.g. "make a 2–3 sentence abstract". Concise output targets keep the model on task. `SP_TASK` simplified: removed the formatting-consistency clause (manageable from user prompt) and softened the fidelity rule to "do not omit or add content *unless the prompt requires it*" so summarisation tasks are not treated as copy tasks.

---

## v0.708 — UI rebuilt + multi-device (session 15)

Redesigned `chat.html`'s look from scratch (CSS only + markup tweaks; no logic touched): refined retro-terminal aesthetic, vintage palette unchanged, rounded panels and bubbles, CRT vignettes. Real responsive layout: 3-column desktop; ≤1024px the history and dashboard become drawers triggered from the header buttons; ≤640px full-width input with 44–46px touch targets, `100dvh` (input no longer hidden by the browser bar), `overflow-x:hidden` (no horizontal scroll from the off-canvas drawer), header that doesn't overflow (<400px hides THINK and shortens the logo). Typography recalibrated and dashboard compacted so it doesn't overflow vertically (36px odometer per cell — a JS constraint).

Remote/phone access fix: `selmo_web.py` (8081) and `selmo_gpu_monitor.py` (8082) now listen on `0.0.0.0` (previously `127.0.0.1`, unreachable from LAN); the client-side `TTS_URL` uses `location.hostname` instead of a hardcoded `127.0.0.1`. Whisper and TTS were already on `0.0.0.0`.

Vision: client-side image normalization (createImageBitmap→canvas→JPEG, cap 1280px) for large photos and iPhone HEIC; `max_tokens` reduced to 1200 when there is an image (reserving ctx for the image tokens); the client now shows the server's error body instead of a bare "HTTP 400". **Two bugs still open** — see BUG-IMG-02 and BUG-IMG-03 in the bug report.

---

## Technical stack

### Reference hardware

| Component | Spec |
|---|---|
| CPU | Intel i9-11900KF @ 3.5GHz |
| RAM | 32GB |
| GPU | NVIDIA RTX 4070 Ti 12GB VRAM |
| OS | Windows 11 |

Real GPU draw during inference: 70-90W · Utilization: ~40-99% · Temperature: 50-60°C

### Software

| Component | Choice | Notes |
|---|---|---|
| Runtime | llama.cpp (CUDA) · MIT | |
| GPU monitor | pynvml via Python · port 8082 | Real watts from the GPU |
| Web bridge | selmo_web.py · port 8081 | Local SearXNG (Podman) + DDG fallback + trafilatura |
| Container engine | Podman Desktop · Apache 2.0 | SearXNG on port 8888 |
| Launcher | Selmo.bat / Mizan.bat | Model selector + adaptive -ngl logic |
| TTS | selmo_tts.py · port 8084 | Kokoro-ONNX, Italian voices, language auto-detect |


---

## Dependencies — full setup

### Python
Requires Python 3.10+ (tested on 3.14). A single interpreter, no venv.

```
pip install flask faster-whisper pynvml trafilatura requests --break-system-packages
pip install kokoro-onnx soundfile langdetect --break-system-packages --prefer-binary
```

| Package | Used by | Notes |
|---|---|---|
| flask | all bridges | lightweight web server |
| faster-whisper | selmo_whisper.py | STT, small model ~500MB (auto-download) |
| pynvml | selmo_gpu_monitor.py | real GPU watts |
| trafilatura | selmo_web.py | text extraction from web pages |
| requests | selmo_web.py | HTTP client |
| kokoro-onnx | selmo_tts.py | neural TTS, Apache 2.0 |
| soundfile | selmo_tts.py | WAV encoding |
| langdetect | selmo_tts.py | language auto-detect for TTS |

### Model files to download manually

| File | Where | Size |
|---|---|---|
|  |  | ~290MB |
|  |  | ~10MB |
| LLM model |  | variable |
| mmproj |  | ~170-880MB (optional, for vision) |
| Whisper | auto in | ~500MB (downloaded on first launch) |

Kokoro link: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

### External binaries

| Tool | Where | Notes |
|---|---|---|
|  |  | llama.cpp CUDA build |
| Podman Desktop | installed globally | for local SearXNG |
| SearXNG | Podman container on port 8888 | manual start or Podman autostart |

### Ports

| Port | Service |
|---|---|
| 8080 | llama-server (LLM) |
| 8081 | selmo_web.py (web search) |
| 8082 | selmo_gpu_monitor.py (GPU watts) |
| 8083 | selmo_whisper.py (STT) |
| 8084 | selmo_tts.py (TTS Kokoro) |
| 8443 | selmo_https_proxy.py (HTTPS reverse proxy for mobile mic) |
| 8888 | SearXNG (Podman container) |

---

## Server parameters — adaptive launcher logic

Based on the size of the .gguf file. Updated in session 8 with a 9000MB threshold to separate 13B from 22-24B (the KV cache overflows at 16384 ctx with 11GB free VRAM — verified on Mistral Small 3.2 24B IQ3_M).

| File range | Typical models | -ngl | --ctx-size |
|---|---|---|---|
| < 6000 MB | ~9B | 99 | 4096 |
| 6000–9000 MB | ~13B | 99 | 16384 |
| 9000–13000 MB | 22-24B | 45 | 8192 |
| > 13000 MB | >30B | 30 | 8192 |

**⚠ Known limit (s14): fixed NGL vs number of layers.** The 9000–13000 band uses `NGL=45`, implicitly tuned on the **40 layers** of Mistral-Small-24B (45≥40 → everything on the GPU, 33 t/s). But **EuroLLM-22B has 54 layers**: with NGL=45, **9 layers stay on the CPU** → 6 t/s. The file size (MB) is **not** enough to predict speed: what counts is the GGUF's `block_count`. A "small" 22B on disk can have more layers than a 24B. To make EuroLLM-22B fly you'd need a higher NGL with reduced ctx (it still stays at the 12GB limit). Not fixed in s14 (decided to bet on Magistral as the replacement).

**Thinking models and context window — s9 decision.** The launcher does NOT change the window for reasoning models: it keeps the GPU full and `ctx 8192` for all. Reason: the workflow is chunking-based, so every piece is already small and a large ctx isn't needed; on top of that, long contexts usually hurt quality and cost speed. The priority is to use the GPU to the max, not to have a wide window. Room for the reasoning tokens is reserved on the client side in `chunk_pipeline.py` with `--thinking-buffer` (default 0; 800+ for reasoning): it slightly reduces the chunk size, leaving margin for thinking, at the same server ctx. Wrong path discarded in s9: in the launcher we tried (a) lowering `-ngl` from 45 to 35 to fit ctx 16384 → Gemma collapsed from 22 to 8 t/s; (b) using a q8_0 KV cache to keep ctx 16384 at full GPU → useless/counterproductive with chunking anyway. Rule: never sacrifice `-ngl`, and don't widen the server ctx for thinking — handle it in the pipeline.

`--timeout 0` on both launchers (added s8): disables the server-side timeout, control left to the client (AbortController in chat.html, 300s in chunk_pipeline.py).

Note: EuroLLM 9B has `n_ctx_train=4096` — a higher ctx generates a warning and is capped automatically.

---

## Tested models and confirmed parameters

| Model | File | VRAM | ctx | t/s | Notes |
|---|---|---|---|---|---|
| Mistral Small 3.2 24B IQ3_M | mistralai_Mistral-Small-3.2-24B-Instruct-2506-IQ3_M.gguf | ~10.5GB | 8192 | 32-33 | Production default · **40 layers** → all on GPU with NGL=45 |
| EuroLLM 22B Q3_K_M | utter-project_EuroLLM-22B-Instruct-2512-Q3_K_M.gguf | ~10.5GB | 8192 | **6** | **54 layers** → with NGL=45, 9 layers stay on CPU = slow. Quality not impressive. See the NGL lesson. |
| EuroLLM 9B Q4_K_M | EuroLLM-9B-Instruct-2512.i1-Q4_K_M.gguf | ~5.5GB | 4096 | **70** | Pure ChatML (no reasoning). All on GPU. Reasons well "in context" in normal chat. |
| Gemma 4 12B Q6_K | gemma-4-12b-it-Q6_K.gguf | ~9-10GB | 8192 | 22 | Multimodal, reasoning. Apache 2.0. |

**Ethical replacement candidate (s14 research)**: **Magistral Small 2509** (Mistral, French, Apache 2.0) — reasoning **+ vision** (vision encoder from the 2509). Same architecture as Mistral-Small-24B (**40 layers** → fast on 12GB). GGUF: `unsloth/Magistral-Small-2509-GGUF`. For 12GB: `Q3_K_S` (10.4GB) or fallback `UD-IQ3_XXS` (9.41GB), + `mmproj-F16.gguf` (rename to `mmproj-Magistral-Small-2509-F16.gguf` for the auto-match). Reasoning with `[THINK]` tokens. Pure-text 100% open-data alternative: **OLMo 3 7B Think** (Ai2). Qwen3-VL-8B-Thinking is strong but Chinese.

---

## File structure

```
AppData\Local\Selmo\
├── bin\                          # llama.cpp binaries (CUDA)
├── models\                       # any .gguf here appears in the menu automatically
├── Test files\
│   └── Dialoghi con la lavatrice.odt
├── chat.html                     # main interface
├── mizan.html                    # stub → chat.html in Mizan mode
├── Selmo.bat                     # universal launcher
├── Mizan.bat                     # Mizan launcher (temp 0.01)
├── selmo_gpu_monitor.py          # real watt monitor (port 8082)
├── selmo_web.py                  # web search bridge (port 8081)
├── chunk_pipeline.py             # generic pipeline: file → chunking → LLM → output
├── translate_chunks.py           # ODT translation pipeline
├── test_chunking.py              # text anomaly analysis with robust chunking
├── setup-git.ps1                 # local git repo initialization
├── selmo-manifesto.md            # vision and roadmap
├── selmo-dev.md                  # this file
├── selmo_whisper.py              # Whisper bridge (port 8083)
└── selmo-bug-report.md           # living bug tracker
```

---

## Personality — system prompts

### Selmo
Temperature 0.75, top-p 0.9. System prompt **trimmed to 4 lines** (session 14): a touch of
personality (ironic, no preamble, no hype, no servility), plus language and the `/web` mechanic. No long
sections: the model must get straight to the point. The previous version (s13) was already short but
had a verbose INTERNET section.

```
You are Selmo, a local AI on the user's own hardware.
Direct, concise, and ironic. No preamble, no hype, no servility. When unsure, say so in a line. Never invent facts.
Reply in the user's language.
You don't browse; the user fetches pages with /web and the results appear in the conversation — use them when present. Never output [SEARCH:] tags.
```

### Mizan
Temperature 0.01, top-p 1.0. The antagonist. Deterministic, cold, without opinions.

```
You are an analysis system. Reply precisely and concisely.
No opinions. No hesitation. No first person.
Extract data, translate, check code. Accuracy is the only criterion.

For up-to-date data the user uses /web; the results stay in the conversation. Never emit search tags.
```

The Selmo/Mizan toggle changes the system prompt + temperature + color palette (blue/red) at runtime without restarting the server. `mizan.html` sets `localStorage.selmo_automode='mizan'` and redirects to `chat.html`.

---

## Access

**Desktop** — `http://127.0.0.1:8080/chat.html`
**Local network** — `http://192.168.x.x:8080/chat.html` (Windows firewall asks for confirmation on first launch)
**HTTPS (mobile mic)** — `https://192.168.x.x:8443/chat.html` via selmo_https_proxy.py; accept the self-signed cert warning once in the browser.
**Remote** — VPN on the home router → the phone re-enters the local network, zero extra config

---

## chat.html features — implemented ✓

- SVG speedometer with animated needle (real or estimated GPU watts)
- Mechanical drum odometer (session Wh)
- Real wattmeter via GPU monitor (port 8082, 1s polling)
- Configurable electricity cost (€/kWh persisted in localStorage)
- Session and total Wh persisted with a reset button
- Total tokens persisted with a reset button
- STOP button with AbortController
- + new chat button
- EXPORT button → downloads the chat as .md with timestamp, model, Wh
- Share Tech Mono font
- Blue (Selmo) and red (Mizan) palette with a runtime toggle
- Selmo/Mizan toggle — switches system prompt + temperature + colors
- File loading: .txt, .csv, .docx (JSZip + namespace-aware DOMParser), .odt (JSZip + DOMParser)
- Auto-chunking of long documents (CHUNK_SIZE=11000 char) with a final summary
- `/web <query>` command: explicit search, nothing runs on its own
- `/web` results injected as top-priority context, reusable in later messages, `[1][2]` citations, source ledger
- `/datetime` endpoint: real date/time without an external search
- Clickable source ledger with an engine indicator (green = SearXNG local, yellow = fallback)
- Full text extraction with trafilatura (news)
- Server connection indicator with automatic retry every 3s
- Web bridge indicator with the active engine
- Image loading (jpg/png/gif/webp): base64 → OpenAI-compatible multimodal message (requires mmproj)
- Microphone button (🎤): MediaRecorder → POST /transcribe → text injected into the input
- Whisper bridge status indicator (port 8083)
- Push-to-talk: hold Space or the middle mouse button → record → release → transcribe → send automatically
- System-voice TTS (Web Speech API, it-IT): 🔊 button, always available without a server. PTT forces TTS even if manually disabled
- .xlsx/.xls/.ods loading (SheetJS): convert to CSV text with the sheet name
- .pdf loading (PDF.js): page-by-page text extraction
- .pptx loading (JSZip + XML): slide-by-slide text extraction
- .odp loading (JSZip + content.xml + NS API): page-by-page text extraction
- Kokoro TTS (kokoro-onnx, Apache 2.0): offline neural voice, port 8084, language auto-detect (langdetect)
- Ctrl+Space: PTT web search (transcribes and sends as /web <text>, response read aloud)
- Launcher: automatic mmproj matching by name (no more manual choice)
- Collapsible reasoning panel (chat, web, file/chunk) — the reasoning stays out of the document stitch
- Simplified system prompt (lean SP_SELMO)
- /web fix: user message bubble shown + response in the user's language
- Local SearXNG indicator: `/status` probes 8888; green dot "local web", yellow if local is down (public fallback = data leaving), off if the bridge is off
- + IMG/OCR button: Gemma 4 vision on images and PDFs (one image per page, clickable thumbnails); mmproj flag in the launcher
- Version v0.702

---

## Lessons learned

**Never use the Edit tool on chat.html** — the file is large (~1350 lines) with multiline template literals. The tool truncates silently. Always use Python via bash (see BUG-META-01 in the bug report).

**node --check after every change to chat.html** — extract the inline script and verify before closing the session.

**Restart the server after a change to chat.html** — `llama-server --path .` can serve the cached version. Mitigation: anti-cache meta in the head + Ctrl+F5.

**The language always follows the user** — never hardcode a language in the injected prompts. Use "reply in the same language as the user's message".

**KV cache and VRAM** — 22-24B models with ctx 16384 overflow the 11GB free VRAM on the RTX 4070 Ti. Safe threshold: ctx 8192 for files > 9.5GB.

**IQ3_M vs Q3_K_M** — IQ3_M is importance quantization: same footprint, slightly higher quality because it preserves the critical weights.

**Server timeout** — `--timeout 0` disables the server-side timeout. The `should_stop` in the log indicates cancellation due to client disconnect, not a critical error.

**Git is the only safety net — commit on every positive feedback** — no more `.bat` backups (`bk.bat`/`restore.bat`/`bk*`, deprecated). When Fabio confirms something works: immediate commit with a clear message + version bump (the `hbadge` badge in chat.html and the header of this file). Costly s13 lesson: the first working vision iteration lived only in the working tree, never committed, and when later micro-changes broke it there was no snapshot to go back to. Never again leave good states uncommitted.

**Vision PDF — never a concatenated canvas** — multiple pages in a single giant vertical canvas give an extreme aspect ratio and a multi-MB base64. Render one image per page, cap the long side (~1280px), and pass them as an array of `image_url` in the multimodal content.

**Vision Gemma 4 — token budget + ubatch** — Gemma 4 has a token/image budget (70/140/280/560/1120; 1120 for OCR). The encoder uses non-causal attention → the image tokens must fit in a single ubatch: you need `--batch-size`/`--ubatch-size` ≥ image tokens (2048 for the 1120 budget), otherwise `GGML_ASSERT` and a crash. Flag only in the mmproj branch of Selmo.bat.

**.bat: CRLF and zero NUL** — the `.bat` files must be CRLF (the `^` continuation on LF breaks cmd). Watch out for the mount's NUL corruption (BUG-META-02): after every change to `.bat`/`.md`, check that the NUL bytes are 0.

**Speed ≠ file size: layer count is what matters (s14)** — a "smaller" model in MB can be slower if it has more layers than the fixed `-ngl` value. EuroLLM-22B (54 layers) at NGL=45 leaves 9 layers on the CPU → 6 t/s; Mistral-Small-24B (40 layers) at NGL=45 goes fully to the GPU → 33 t/s, despite being almost identical on disk. Read the `block_count` from the GGUF before drawing conclusions about VRAM or flags.

**Reasoning: leave it to the server, don't parse it in the client (s14)** — the old client-side scanner for `<think>` tags was broken: the tokens come out split across the stream deltas (`<`, `think`, `>`), so `indexOf('<think>')` failed and the panel didn't trigger. Solution: no manual parsing; `llama-server` extracts the reasoning into `reasoning_content` and the panel hooks **only** that. Also removed the THINK button and `budget_tokens` (a non-standard param, ignored). Pure ChatML models (EuroLLM) emit no reasoning: no panel, and that's correct. To make the panel appear with reasoning models you may need `--reasoning-format` in the launcher.

**SP_TASK silences the reasoning (s14)** — the chunk prompt says "output only the result, no commentary": right for translation/extraction, wrong for analytical questions ("why don't the totals match"). On those the model jumps to a confused conclusion. That's why analytical questions go to **normal chat** (SP_SELMO), not the chunk pipeline. From v0.705 the choice is guided: file > 50% of ctx → it asks "Chunk it / Normal chat"; light file → normal chat automatically with the document as context.

---

## Vision Gemma 4 — lean strategy (implemented, v0.702)

✓ Implemented and working (v0.702): **+ IMG/OCR** button in chat.html (PDF one image per page ~1280px, clickable thumbnails) + mmproj flag in Selmo.bat (`--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048`). Verified on Gemma 4 12B / RTX 4070 Ti 12GB.

Session 13 research. Gemma 4 does **not** use Gemma 3's pan-and-scan: it has a **token budget per image** that fixes the interpreted resolution. Levels: 70, 140, 280, 560, 1120. Recommendations per task:
- 70 / 140 → captioning, classification, fast video frames
- 280 / 560 → generic multimodal chat, charts, screen/UI
- **1120 → OCR, document parsing, handwriting, small text** (our case: payslip)

Practical consequences:
- No point rendering huge images: the model resizes to the budget anyway. On the `chat.html` side **one image per page** at ~1024–1280px on the long side is enough, no concatenated canvas.
- Context cost ≈ the chosen budget (≈1120 tokens/page in OCR): with ctx 8192 a couple of pages fit.

llama.cpp flags (in `Selmo.bat`, only when there is an mmproj):
```
--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048
```
**The real cause of BUG-IMG-01**: Gemma 4's vision encoder uses **non-causal** attention on the image tokens → they must all fit in a single ubatch. With the default `ubatch` (512) and a large image, `GGML_ASSERT(n_ubatch >= n_tokens)` fires and the server dies (HTTP 500/400). It wasn't the message format: it was the batching. Raising batch/ubatch to 2048 fixes it.

Sources: ai.google.dev/gemma/docs/capabilities/vision · dev.to/someoddcodeguy "Gemma 4 image settings in llama.cpp" · unsloth.ai/docs/models/gemma-4

---

## Nice to have

### VAD — conversational voice (local, no cloud)
**Goal:** natural voice conversation — tap mic once, speak, VAD detects end of speech, sends to Whisper, model replies via TTS Kokoro, returns to listening.

**Approach:** [`@ricky0123/vad`](https://www.npmjs.com/package/@ricky0123/vad) — Silero VAD compiled to ONNX, runs entirely in the browser via WebAssembly (onnxruntime-web).
- Load lib from CDN + `silero_vad.onnx` (~2MB) served by Selmo.
- Callbacks: `onSpeechStart` / `onSpeechEnd(blob)` → blob sent directly to Whisper port 8083.
- Silero VAD: 88% TPR at 5% FPR vs 50% for browser-native WebRTC VAD.
- After transcription → auto-send → Kokoro TTS reads reply → back to listening.
- Requires the HTTPS proxy to be active (getUserMedia needs secure context on mobile).
- Latency budget: Whisper ~500ms on short clips (4070 Ti) — acceptable for conversation.

---

## Next steps (s14 roadmap)

### 1. Clean lifecycle — no orphan windows, purge on shutdown
Problem: `Selmo.bat` opens 4 Python services (GPU monitor 8082, web 8081, whisper 8083, TTS 8084) with `start /min`, each in a window that stays open and must be closed by hand when the main task stops. Ugly and inconvenient.
Goal: hidden backend + **full purge** when `llama-server` (the main process) stops.
Approach:
- Start the bridges **without a window**: `pythonw.exe` (no console) or `start /b`, instead of `start /min`.
- Track the PIDs at startup and, when llama-server closes, do cleanup (`taskkill` the 4 services). In `Selmo.bat` the cleanup goes after the server block (foreground), before the `pause`.
- Cleaner alternative: a single orchestrator (`selmo_launch.py` via pythonw) that spawns the subprocesses + llama-server, waits, and kills the children on exit. SearXNG (Podman) stays outside, it's separate.

### 2. Responsive UI / phone use
Status: the server is already reachable on the local network (tested from another device — it works), but the UI doesn't adapt.
Goal: usable from a phone and at small window sizes.
Approach:
- Media queries: below a useful width threshold (~800×600) stack the 3 columns (history / chat / dashboard) into one; larger touch targets.
- SVG speedometer → at small windows replace it with a **horizontal bar** (linear gauge) for the watts; compact the Wh odometer, cost, tokens.
- Collapsible dashboard on mobile to give room to the chat.
- Viewport meta already present; the adaptive CSS is missing.

---

## Session history

### Session 1-3
Initial setup. ll