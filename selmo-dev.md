# Selmo — Development documentation
*Updated session 16 · 2026-06-13 · v0.803*

---

## v0.803 — THINK toggle locked for reasoning-first models (session 16 cont.)

For reasoning-first models (`REASON_FIRST`, e.g. Olmo 3 Think) the THINK button is forced visibly active (`THINK ●`) but greyed and non-clickable: the model always reasons, so the toggle has nothing to switch. `applyReasonLock()` sets the locked look (no cyan `.on` glow, `opacity .5`, `cursor:not-allowed`, `disabled`) and keeps `IS_THINK_ON=false`, so `THINK_INSTR` — which targets Magistral's `[THINK]` format — is never injected; Olmo reasons natively in `<think>`. `toggleThink()` early-returns when `REASON_FIRST`, and `setThinkEnabled` re-applies the lock after a chunking run re-enables the button. Normal models are unchanged: `REASON_FIRST` false → fully toggleable as before.

---

## v0.802 — reasoning panel for Olmo Think / `<think>` tags (session 16 cont.)

`streamTokens` now separates the reasoning for **two tag families**: Magistral's `[THINK]…[/THINK]` (unchanged) and Olmo's `<think>…</think>`. It also handles **reasoning-first** models: Olmo 3 Think's chat template opens `<think>` in the generation prompt, so the stream begins *inside* the reasoning block and only ever emits the closing `</think>` (confirmed in `selmo-llama.log`: `example_format` ends with `<think>`). A `REASON_FIRST` flag, detected at startup from the chat template exposed by `/props` (true when the template has an unclosed `<think>` opening: `lastIndexOf('<think>') > lastIndexOf('</think>')`), makes the parser start in reasoning state. A `console.log('Selmo reasoning-first:', …)` reports the detected value.

The flush state machine was generalised: `OPENS=['[THINK]','<think>']`, `CLOSES=['[/THINK]','</think>']`, picking whichever marker appears first, with a 7-char hold-back (longest tag is 8 chars) to survive a tag split across SSE chunks.

**Safeguards — Magistral and Gemma untouched.** Magistral's template uses `[THINK]` so `REASON_FIRST` stays false and the initial state is identical to before. Gemma streams its reasoning out-of-band in `reasoning_content`; receiving that delta now also forces `inTk=false`, disarming the implicit-open so Gemma's final answer can never land in the panel. Verified with `node --check`.

---

## v0.801 — launcher runtime prompt for ngl/ctx (session 16 cont.)

`Selmo.bat` no longer hardcodes `-ngl`/`--ctx`. After the model is chosen it prompts for both, with the defaults pre-filled (`99` / `8192`) — press ENTER to keep or type a new value. This makes it easy to test different models and GPUs without editing the file. See the rewritten "Server parameters" section for details and the rationale (file size does not predict speed; `block_count` does). `Selmo.bat` was also fully translated to English per the project language rule.

---

## v0.800 — VAD: hands-free conversation (session 16 cont.)

Hands-free mode with pause detection via **Silero VAD** (`@ricky0123/vad-web` v5, ONNX in-browser). New 🗣 button (`#vad-btn`) next to the mic.

Flow: tap once → the VAD listens → `onSpeechEnd` returns a `Float32Array` at 16 kHz → client-side conversion to WAV (`f32ToWav`) → POST to Whisper `/transcribe` (no server change: it already accepts `.wav`) → text into the input → auto-send. In hands-free mode the reply TTS is forced (`pttForceTts`).

**Anti-echo:** during transcription + generation + TTS the VAD is paused (`vadInstance.pause()`), so it doesn't listen to itself. It resumes when the reply is done. The resume is hooked to the end of TTS: `speakText` now fires a completion callback (`src.onended` for Kokoro, `utt.onend` for Web Speech) → `vadAfterSpeak()` → `vadResume()`. Fallback in `endTurn` via `_ttsPending`/`vadAwaitingReply` for the case where generation errors out and `speakText` is never called.

**Push-to-talk bypasses the VAD** (explicit requirement): `pttStart` pauses the VAD and uses the `MediaRecorder` path; after the reply the VAD resumes.

Button states: cyan = listening, blinking green = user speaking, blinking yellow = busy.

**Library from the jsdelivr CDN** (onnxruntime-web 1.22.0 + vad-web 0.0.29), like jszip/pdf.js: needs network on the **first** VAD start, then cached. For fully offline use: serve the `.onnx`/`.wasm`/worklet files from Selmo and point `baseAssetPath`/`onnxWASMBasePath` locally. `redemptionMs` left at the default 1400 ms (the pause length that triggers end-of-utterance).

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

## Credits & licenses

Third-party components and their licenses (for publication / attribution). All are open source; the permissive ones (MIT / Apache 2.0 / BSD / ISC / OFL) impose no copyleft on Selmo's own code.

| Component | Role | License |
|---|---|---|
| llama.cpp | LLM runtime (server + CUDA) | MIT |
| faster-whisper | STT engine | MIT |
| CTranslate2 | faster-whisper backend | MIT |
| Whisper model (OpenAI) | STT weights | MIT |
| Kokoro / kokoro-onnx | neural TTS | Apache 2.0 |
| onnxruntime / onnxruntime-web | ONNX inference (VAD + Kokoro) | MIT |
| @ricky0123/vad-web | browser VAD library | ISC |
| Silero VAD (`silero_vad.onnx`) | VAD model weights | MIT |
| Flask | Python web bridges | BSD-3-Clause |
| requests | HTTP client | Apache 2.0 |
| trafilatura | web text extraction | Apache 2.0 (≥ v1.8.0; GPLv3+ before) |
| langdetect | TTS language auto-detect | Apache 2.0 |
| pynvml | GPU watt monitor | BSD-3-Clause |
| soundfile | WAV encoding | BSD-3-Clause |
| Podman | container engine (for SearXNG) | Apache 2.0 |
| SearXNG | local metasearch | AGPL-3.0 — see note |
| JSZip | client-side zip (docx/odt/pptx) | MIT or GPLv3 (dual) |
| SheetJS (xlsx) | spreadsheet parsing | Apache 2.0 |
| PDF.js | PDF text/render | Apache 2.0 |
| marked | Markdown rendering | MIT |
| Share Tech Mono | UI font | SIL Open Font License (OFL) |

**AGPL note (SearXNG):** SearXNG runs as a **separate process** in its own Podman container, reached over HTTP. Selmo neither bundles nor links its code, so the AGPL copyleft does not extend to Selmo's source. It stays an optional, swappable local service (the web bridge falls back to DuckDuckGo if it is down). For a publication that ships SearXNG, keep it as a separate container and point users to its upstream repo.

**Not-EU but open (transparency note):** Silero (VAD), onnxruntime (Microsoft), Whisper (OpenAI), JSZip/SheetJS/PDF.js are open source but not European — neutral with respect to the manifesto's "European AI" stance, like the other US-origin client libraries already in use.

---

## Server parameters — runtime prompt (ngl + ctx)

Current behavior (v0.801): `Selmo.bat` no longer derives `-ngl` / `--ctx` from the file size. After the model is chosen it **prompts** for both, with the defaults pre-filled — press ENTER to keep them or type a new value:

```
  GPU layers (-ngl) [99]:
  Context window (--ctx) [8192]:
```

Defaults: `NGL=99` (offload every layer to the GPU) and `CTX=8192`. The chosen values are passed straight to `selmo_server.py --ngl --ctx`. The 8192 default comes from the v0.714 OOM lesson: `CTX=0` (the model's training context, 32K+) made Magistral allocate a ~20 GB KV cache on a 12 GB GPU. 8192 is the safe ceiling for 22-24B models on the RTX 4070 Ti; smaller models can take more, which is exactly why the value is now asked at launch instead of hardcoded.

**Why a prompt instead of file-size bands (superseded heuristic).** Up to s16 the launcher picked `-ngl` / `--ctx` from the `.gguf` size (bands like <6000 MB → ngl 99 / ctx 4096, 9000-13000 MB → ngl 45 / ctx 8192, etc.). That heuristic was wrong: file size (MB) does not predict speed — the GGUF's `block_count` (layer count) does. EuroLLM-22B has **54 layers**, so a fixed `NGL=45` left 9 layers on the CPU → 6 t/s; Mistral-Small-24B has **40 layers**, so the same NGL=45 ran fully on the GPU → 33 t/s, despite near-identical size on disk. Rather than keep guessing, NGL/CTX are now chosen at launch for the specific model + GPU. Possible future step: auto-detect free VRAM via `nvidia-smi` and read `block_count` from the GGUF to suggest the values.

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
- Load lib from CDN + `silero_vad.onnx` (~2MB) serve