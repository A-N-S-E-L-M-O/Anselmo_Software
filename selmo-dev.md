# Selmo — Development documentation
*Updated session 16 · 2026-06-14 · v0.815*

> **Read first:** the **Lessons learned** section near the end of this file, and **`selmo-bug-report.md`**.
> **Project language:** English only — see `selmo-manifesto.md`. Conversation with Fabio can be any language; every file artifact is English.

This is the engineering reference for Selmo: how it is built, the parameters that matter, the lessons that cost something to learn, and the changelog. The vision lives in the manifesto; the open defects live in the bug report. This file is organised by topic, with a condensed reverse-chronological changelog at the end.

---

## Architecture at a glance

Selmo is one `llama.cpp` server, a small set of single-purpose Python bridges, and a single HTML client (`chat.html`). Everything runs locally; nothing leaves the machine except an explicit `/web` search.

| Port | Service | File |
|---|---|---|
| 8080 | llama-server (LLM, also serves `chat.html`) | `bin/` + `selmo_server.py` |
| 8081 | Web search bridge (SearXNG + DDG fallback + trafilatura) | `selmo_web.py` |
| 8082 | GPU/RAM monitor (real watts via pynvml, RAM via psutil) | `selmo_gpu_monitor.py` |
| 8083 | Whisper STT | `selmo_whisper.py` |
| 8084 | Kokoro TTS | `selmo_tts.py` |
| 8443 | HTTPS reverse proxy (mobile mic) | `selmo_https_proxy.py` |
| 8888 | SearXNG (Podman container) | external |

`selmo_server.py` launches llama-server and starts the bridges alongside it. The client talks to each service on its own port (or through the 8443 proxy when loaded over HTTPS).

### Reference hardware

Intel i9-11900KF · 32 GB RAM · NVIDIA RTX 4070 Ti 12 GB · Windows 11.
Real GPU draw during inference 70–90 W, utilisation 40–99 %, temperature 50–60 °C.

### Software

| Component | Choice | License |
|---|---|---|
| Runtime | llama.cpp (CUDA) | MIT |
| Container engine | Podman Desktop (SearXNG) | Apache 2.0 |
| GPU monitor | pynvml | BSD-3 |
| TTS | Kokoro-ONNX | Apache 2.0 |

---

## Setup & dependencies

Python 3.10+ (tested on 3.14), a single interpreter, no venv.

```
pip install flask faster-whisper pynvml trafilatura requests --break-system-packages
pip install kokoro-onnx soundfile langdetect psutil --break-system-packages --prefer-binary
```

| Package | Used by | Notes |
|---|---|---|
| flask | all bridges | lightweight web server |
| faster-whisper | `selmo_whisper.py` | STT, `small` model ~500 MB (auto-download) |
| pynvml / psutil | `selmo_gpu_monitor.py` | GPU watts + RAM |
| trafilatura / requests | `selmo_web.py` | web text extraction + HTTP |
| kokoro-onnx / soundfile / langdetect | `selmo_tts.py` | neural TTS + WAV + language detect |

**Manual downloads:** the LLM `.gguf` (any compatible model dropped in `models\`), an optional `*mmproj*.gguf` next to it for vision, the Whisper model (auto on first launch), and a Kokoro voice (`kokoro-onnx` releases). **External binaries:** llama.cpp CUDA build in `bin\`, Podman Desktop for the optional local SearXNG.

---

## Launcher & server parameters

### INI-driven launcher (v0.807 → v0.811)

`Selmo.bat` carries no model logic. It reads `selmo-models.ini`, where each `[section]` is a case-insensitive substring matched against the model file name (**first match wins** — put specific names higher, e.g. `[LFM2.5]` above `[LFM2]`), with `[default]` as fallback.

Since **v0.811** each section holds one **`srv=`** line: the exact llama-server command, forwarded verbatim. At launch you pick the model, see its `srv` string, and press ENTER to keep it or paste a full replacement (a "show + retype" UX — `set /p` cannot pre-fill an editable line). `selmo_server.py` takes a single `--srv "<flags>"`, `shlex`-splits it, and prepends only the **four structural flags** the app cannot run without: `--model` (the menu pick), `--host 0.0.0.0`, `--port 8080`, `--path <base>`. Those four are stripped from `srv` if typed by mistake, so static serving and the LAN bind can never break. An `*mmproj*.gguf` in the model's own folder is auto-detected and appended **last** with `--batch-size/--ubatch-size 2048` (so our batch wins Gemma's non-causal ubatch assert — see Vision).

`chunk_ratio` / `chunk_maxtok` stay Selmo-only keys (written to `selmo-config.json` for the client, never sent to the server). **Caveat:** sampling flags (`--temp`/`--top-p`/`--top-k`) in `srv` set only the server default — `chat.html` sends its own per-request values and overrides them. Keep `--reasoning-format deepseek` (THINK panel), `--timeout 600` (phone uploads, BUG-IMG-02) and `--metrics` in the string; features depend on them.

Models live in folders LM-Studio-style: `Selmo.bat` scans `models\` recursively, each model remembers its folder, and the mmproj is matched within that same folder.

### NGL / CTX

`-ngl` and `--ctx` are no longer derived from file size. Defaults: `NGL=99` (all layers on GPU), `CTX=8192`.

**Why 8192:** `CTX=0` (a model's 32K+ training context) made Magistral allocate a ~20 GB KV cache on a 12 GB GPU (v0.714 OOM). 8192 is the safe ceiling for 22–24B models on the 4070 Ti.

**Why a prompt instead of size bands:** file size in MB does not predict speed — the GGUF's `block_count` (layer count) does. EuroLLM-22B has 54 layers, so a fixed `NGL=45` left 9 on the CPU → 6 t/s; Mistral-Small-24B has 40 layers, so the same NGL ran fully on GPU → 33 t/s, at near-identical disk size. Possible future step: read free VRAM from `nvidia-smi` + `block_count` from the GGUF and suggest values automatically.

**Thinking models and ctx (s9 decision):** never widen the server ctx for reasoning and never sacrifice `-ngl`. The workflow is chunk-based, so each piece is already small; room for reasoning tokens is reserved client-side in `chunk_pipeline.py` via `--thinking-buffer` (0 default, 800+ for reasoners). Discarded paths: lowering `-ngl` to fit ctx 16384 (Gemma collapsed 22 → 8 t/s) and a q8_0 KV cache (counterproductive with chunking).

### MoE offload (`--n-cpu-moe`)

To run a premium big MoE (e.g. Qwen3 30B/35B-A3B, ~3B active) on 12 GB: keep the dense backbone on the GPU, push experts to RAM. Lower N pushes more experts onto the GPU (faster) while VRAM holds. Wired through `selmo_server.py` and exposed in the `srv` string.

---

## Profiles & personalities

A profile bundles a **system prompt + sampling temperature + colour palette**, switched at runtime from the watermark/logo (opens the profile modal) — no server restart. Today there are two profiles; the next step is three (below).

### Selmo — blue, the assistant

Temperature 0.75, top-p 0.9. Warm, ironic, concise. Prompt trimmed to four lines (s14) so the model gets straight to the point:

```
You are Selmo, a local AI on the user's own hardware.
Direct, concise, and ironic. No preamble, no hype, no servility. When unsure, say so in a line. Never invent facts.
Reply in the user's language.
You don't browse; the user fetches pages with /web and the results appear in the conversation — use them when present. Never output [SEARCH:] tags.
```

*(The `/web` line in the prompt is a leftover — web mode is the WEB toggle now; update the wording on the next chat.html pass.)*

### Mizan — red, the antagonist

Temperature 0.01, top-p 1.0. Deterministic, cold, no opinions, no first person. The narrative antagonist from *Dialoghi con la lavatrice* (see manifesto). Purpose: extraction, translation, code-checking — accuracy as the only criterion.

```
You are an analysis system. Reply precisely and concisely.
No opinions. No hesitation. No first person.
Extract data, translate, check code. Accuracy is the only criterion.

For up-to-date data the user uses /web; the results stay in the conversation. Never emit search tags.
```

**Implementation (chat.html).** `activeSP()` returns `SP_MIZAN` when `currentProfile==='mizan'`, else `SP_SELMO`. `setProfile(name)` sets `currentTemp` (0.01 vs 0.75), toggles `document.body.classList('mizan')`, and swaps the watermark text (Mizan/Selmo). The profile modal exposes `.pm-selmo` (cyan `#44DDEE`) and `.pm-mizan` (red `#FF4455`) buttons.

**Known gap — the Mizan palette is incomplete.** `body.mizan` currently overrides only the accent tokens (`--cyan`, `--yellow`, and their glows) to red/orange. The blue *background* tokens (`--bg`, `--panel`, `--dark`, `--chat-bg`, `--ink`, `--steel`, `--border`) and several hardcoded blue surfaces (the body radial gradient `#0b237f`/`#00072e`, header `#00093a`, nav/aside `#000938`, dashboard `#001046`, the chat bubbles) stay blue. Result: red buttons on a blue app, not a red palette. Fixing this means red-shifting the full token set plus the handful of hardcoded blue surfaces, scoped inside `body.mizan` so Selmo's rules are untouched. A clean R↔B channel swap preserves luminance/contrast while rotating the hue family (e.g. `#001166` → `#661100`).

### Next step — three profiles, three badges, three palettes

The new design promotes the toggle into a three-way selector. Three profile badges in the modal, each with its own palette:

| Profile | Palette | Personality | Parameters |
|---|---|---|---|
| **Selmo** | Blue (current default) | warm, ironic assistant | preset: temp 0.75, top-p 0.9 |
| **Mizan** | Red (complete the palette per above) | cold analysis system | preset: temp 0.01, top-p 1.0 |
| **Custom** | Neutral / standard system palette (no blue or red theming) | user-defined | **free parameters** — temperature, top-p, top-k and the system prompt are user-editable in the UI |

Custom is the open profile: it drops the branded palette for a neutral system look and exposes the sampling parameters and system prompt for the user to set directly, instead of inheriting a preset. This is the home for the "selectable personality and parameters" feature. Work items: (1) complete the Mizan red palette; (2) add the neutral Custom palette as a third `body` state; (3) add the third badge + a small parameters panel bound to the per-request sampling values `chat.html` already sends.

---

## Reasoning / THINK panel

The panel is fed only by what the server extracts — no client-side tag parsing (the old `indexOf('<think>')` scanner failed because tokens arrive split across SSE deltas).

- **`--reasoning-format deepseek`** in the `srv` string makes llama-server populate `reasoning_content`; the panel hooks that delta. Gemma streams reasoning out-of-band there too; receiving it forces `inTk=false` so Gemma's final answer can never land in the panel.
- **THINK button is template-driven** (read from `/props`, no hardcoded model list): the lowercased chat template contains `think` → button shown and ON by default; absent → hidden. If a model starts emitting reasoning mid-stream, the button re-activates itself (the model is in charge).
- **Two internal flags.** `REASON_FIRST`: the template opens `<think>` in the generation prompt (Olmo) → the parser starts inside the reasoning block. `INSTRUCTED = think-capable && !REASON_FIRST && !'<|think|>'`: only Magistral-style models get the manual `[THINK]` system instruction; native reasoners (Olmo `<think>`, Gemma `<|think|>`) never do, to avoid literal `[THINK]` leaking into the answer. `syncThinkPrompt()` is the single place that sets the thinking clause.
- **History keeps the panel.** Turns are saved as `[THINK]reasoning[/THINK]answer`; `renderStored()` re-splits on load so reasoning returns to the collapsible panel and only the answer stays in the bubble. `loadSession` also appends a centered model/ctx/reasoning trace at the top.

Classification verified against the GGUF templates: EuroLLM-9B (no `think` → hidden), Magistral-Small-2509 (`[THINK]` → instructed), Olmo-3-7B-Think (`<think>` → native), Gemma-4-12B-it (`<|think|>` → native).

---

## Documents, chunking, web, vision, voice

### Documents & chunking

The client extracts text from `.txt`, `.csv`, `.docx`/`.odt` (JSZip + namespace-aware DOMParser), `.xlsx`/`.xls`/`.ods` (SheetJS → CSV), `.pdf` (PDF.js, page by page), `.pptx`/`.odp` (JSZip + XML, slide by slide). Long documents are auto-chunked with a final summary.

**Two routing modes (from v0.705):** a file above ~50 % of ctx asks "Chunk it / Normal chat"; a light file goes to normal chat automatically with the document as context. This matters because `SP_TASK` ("output only the result, no commentary") is right for translation/extraction but wrong for analytical questions ("why don't the totals match") — there it makes the model jump to a confused conclusion. Analytical questions therefore go to normal chat (`SP_SELMO`), not the chunk pipeline.

**Verbatim-copy lesson (v0.714):** Magistral starts copying source text verbatim after summarising the first paragraphs of a long chunk — instruction-following drift as more source tokens accumulate. Reversing prompt/content order made it worse. Confirmed workaround: cap the output from the user prompt ("a 2–3 sentence abstract"); concise targets keep the model on task. `SP_TASK` was softened to "do not omit or add content *unless the prompt requires it*" so summarisation isn't treated as a copy task.

### Web search

Web access is **off by default** and explicit — nothing leaves localhost unless the user turns it on. The mechanism is the **WEB toggle button** in the header (`toggleWeb()`, `IS_WEB_ON`): when on (`WEB ●`) the message is sent as a web search; when off, it stays local chat. `selmo_web.py` uses local SearXNG in Podman with a DuckDuckGo fallback and trafilatura extraction. Results are injected as top-priority context, reusable in later messages, with `[1][2]` citations and a clickable source ledger (green dot = local SearXNG, yellow = public fallback = data leaving the machine). A separate path answers "what day/time is it" locally without a search.

**Leftover to clean up:** the old typed `/web <query>` command predates the toggle and still lingers in `chat.html` — the system-prompt text mentions `/web`, push-to-talk prepends `/web `, and `sendMsg` still strips a leading `/web`. The toggle is the real interface now; remove these remnants on the next `chat.html` pass.

### Vision (Gemma 4 / Magistral)

Selmo.bat auto-detects `*mmproj*.gguf` and adds `--mmproj`. The client sends one image **per page** at ~1280 px long-side as an OpenAI-compatible content array `[{image_url}, {text}]`; clickable thumbnails open full resolution. Analysis/OCR only — no image generation.

Gemma 4 has a **token budget per image** (70/140/280/560/**1120** for OCR) that fixes the interpreted resolution, so oversized or concatenated images are pointless — the model resizes anyway. The launcher uses the OCR budget in the mmproj branch: `--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048`. The batch/ubatch raise is essential: Gemma's vision encoder uses **non-causal** attention, so all image tokens must fit one ubatch — with the default 512, `GGML_ASSERT(n_ubatch >= n_tokens)` fires and the server dies (this was the real cause of BUG-IMG-01, not the message format). Output cap fixed in v0.809: `maxTok()` now reserves ~1300 tok/image + 800 headroom and gives the rest to the answer (up to 8000), instead of a flat 1200 that truncated vision answers.

### Voice

Full loop: microphone → Whisper → Selmo → Kokoro TTS → speaker. `selmo_whisper.py` (8083, faster-whisper) transcribes; `selmo_tts.py` (8084, Kokoro-ONNX, language auto-detect) speaks; Web Speech API is the always-available fallback that needs no server. Push-to-talk: hold Space or middle mouse → record → release → send; Ctrl+Space does PTT web search. **VAD hands-free (v0.800):** Silero VAD (`@ricky0123/vad-web`, ONNX in-browser) — tap once, speak, `onSpeechEnd` → WAV → Whisper → auto-send, reply forced to TTS. Anti-echo pauses the VAD during transcription/generation/TTS and resumes on the TTS completion callback. Library from CDN (cached after first use); for fully offline, serve the `.onnx`/`.wasm`/worklet locally.

### Mobile / HTTPS

Mobile browsers block `getUserMedia()` on plain HTTP, so the mic was broken on the phone. `selmo_https_proxy.py` (8443) is a self-signed HTTPS reverse proxy: it generates `selmo.crt`/`selmo.key` on first run (LAN IP in the SAN), routes `/proxy/808X/...` to the matching service and everything else to llama-server. The client switches to `/proxy/808X` paths when `location.protocol === 'https:'`. Phone access: `https://192.168.x.x:8443/chat.html`, accept the cert warning once. **Lesson:** delete `selmo.crt`/`selmo.key` if the LAN IP changes (the cert embeds it); the proxy regenerates them.

---

## Tested models

| Model | File | VRAM | ctx | t/s | Notes |
|---|---|---|---|---|---|
| Mistral Small 3.2 24B IQ3_M | `mistralai_Mistral-Small-3.2-24B-Instruct-2506-IQ3_M.gguf` | ~10.5 GB | 8192 | 32–33 | Production default · 40 layers → all on GPU |
| EuroLLM 22B Q3_K_M | `utter-project_EuroLLM-22B-Instruct-2512-Q3_K_M.gguf` | ~10.5 GB | 8192 | 6 | 54 layers → 9 stay on CPU at NGL=45 = slow; quality unremarkable |
| EuroLLM 9B Q4_K_M | `EuroLLM-9B-Instruct-2512.i1-Q4_K_M.gguf` | ~5.5 GB | 4096 | 70 | Pure ChatML, no reasoning; `n_ctx_train=4096` (capped automatically) |
| Gemma 4 12B Q6_K | `gemma-4-12b-it-Q6_K.gguf` | ~9–10 GB | 8192 | 22 | Multimodal, reasoning, Apache 2.0 |

**Ethical replacement candidate (s14):** **Magistral Small 2509** (Mistral, FR, Apache 2.0) — reasoning **+ vision**, same 40-layer architecture as Mistral-Small-24B (fast on 12 GB). GGUF `unsloth/Magistral-Small-2509-GGUF`: `Q3_K_S` (10.4 GB) or `UD-IQ3_XXS` (9.41 GB) + `mmproj-F16.gguf`. Reasoning via `[THINK]`. Fully-open-data text alternative: **OLMo 3 7B Think** (Ai2). **Qwen3 30B/35B-A3B** is the premium MoE option (experts in RAM via `--n-cpu-moe`); natively multimodal in the same unsloth repo, but llama.cpp vision for it is fresh — test before trusting.

Selection filter (from the manifesto): permissive license as a hard gate; EuroLLM = ethical default, Mistral = production default, Gemma = quality benchmark (measured, not distributed).

---

## Access

- **Desktop:** `http://127.0.0.1:8080/chat.html`
- **LAN:** `http://192.168.x.x:8080/chat.html` (Windows firewall confirms on first launch)
- **HTTPS (mobile mic):** `https://192.168.x.x:8443/chat.html`
- **Remote:** VPN into the home router → the phone re-enters the LAN, no extra config

---

## Credits & licenses

All third-party components are open source; the permissive ones (MIT / Apache 2.0 / BSD / ISC / OFL) impose no copyleft on Selmo's code.

llama.cpp (MIT) · faster-whisper + CTranslate2 + Whisper weights (MIT) · Kokoro/kokoro-onnx (Apache 2.0) · onnxruntime(-web) (MIT) · @ricky0123/vad-web (ISC) · Silero VAD (MIT) · Flask (BSD-3) · requests (Apache 2.0) · trafilatura (Apache 2.0 ≥ v1.8) · langdetect (Apache 2.0) · pynvml (BSD-3) · soundfile (BSD-3) · Podman (Apache 2.0) · JSZip (MIT/GPLv3 dual) · SheetJS (Apache 2.0) · PDF.js (Apache 2.0) · marked (MIT) · Share Tech Mono (OFL).

**SearXNG (AGPL-3.0)** runs as a separate process in its own Podman container, reached over HTTP — Selmo neither bundles nor links it, so the copyleft does not reach Selmo's source. It stays optional and swappable (the web bridge falls back to DuckDuckGo). **Transparency note:** Silero, onnxruntime (Microsoft), Whisper (OpenAI), JSZip/SheetJS/PDF.js are open but not European — neutral with respect to the manifesto's "European AI" stance, like the other US-origin client libraries.

---

## Lessons learned

**Editing `chat.html` — Python via bash only.** The Edit tool truncates this large file silently (BUG-META-01). After every change: extract the inline script and run `node --check`, verify with the **Read** tool (not bash `cat`/`wc`), confirm the file still ends with `</script></body></html>`. Then restart `llama-server` (it can serve the cached page) — anti-cache meta in the head + Ctrl+F5.

**The sandbox mount lies (BUG-META-02).** Tool/bash views of files on the mount can be NUL-corrupted or truncated (a stale cache served a 2025-line view of a 2361-line `chat.html` this session). The real files were intact — the **Read tool** and `git show HEAD:<file>` (object store) read true content; bash `cat`/`wc` did not. Never commit from the sandbox: a commit from a corrupted view poisons the repo. After any `.bat`/`.md` change check `python3 -c "print(open('f','rb').read().count(b'\x00'))"` returns 0; `.bat` files must be CRLF (an `^` continuation on LF breaks cmd). The Write tool is the NUL culprit; the Edit tool and Python writes stay clean.

**Git is the only safety net.** No `.bat` backups (deprecated). Only Fabio commits and bumps the version, from his own Windows shell — never the agent. On every positive feedback, prepare the change and hand Fabio a ready-to-paste commit that also bumps the version +0.001 (the `hbadge` in `chat.html` and this file's header). v1.0 is reserved for the real release. Costly s13 lesson: a working version that lived only in the working tree, never committed, was lost.

**The language always follows the user.** Never hardcode a language in injected prompts — "reply in the same language as the user's message".

**Speed ≠ file size — layer count is what matters.** Read `block_count` from the GGUF; `-ngl` must cover it or layers spill to CPU (s14). Never sacrifice `-ngl` to widen ctx.

**KV cache & VRAM.** 22–24B at ctx 16384 overflows 11 GB free on the 4070 Ti; safe ctx 8192 for files > 9.5 GB. The "45 % rule" is about chunk-input vs the *running* context, not the launch ctx, and only holds for models that actually keep their nominal context (EuroLLM does not — kept at 8192).

**Reasoning belongs to the server.** No client-side `<think>` parsing (tokens split across deltas). `--reasoning-format` extracts it into `reasoning_content`; the panel hooks only that. `SP_TASK` silences reasoning ("output only the result"), which is wrong for analytical questions — those go to normal chat, not the chunk pipeline.

**Vision.** One image per page, never a concatenated canvas (extreme aspect ratio, multi-MB base64). Gemma 4 has a per-image token budget (1120 for OCR) and a non-causal encoder that needs `--batch-size/--ubatch-size ≥ image tokens` (2048) or it crashes.

**Server timeout.** `--timeout 600` (phone uploads) or `0` to disable; `should_stop` in the log is client disconnect, not a fault. **IQ3_M vs Q3_K_M:** same footprint, IQ3_M slightly better (importance quantization preserves critical weights).

**cmd `set /p`.** Each `set /p` must be on its own line — chaining with `&` does not run the second prompt.

---

## Changelog (condensed, reverse chronological)

- **v0.813** — `selmo-models.ini` chunk-ratio tuning.
- **v0.812** — consolidation checkpoint on the stable v0.811 base (recovery after a mount-cache regression made the working tree look reverted to v0.714; real disk was intact).
- **v0.811** — full parameter control: the ini carries the raw `srv=` server command; four structural flags prepended; `[Mistral]` section added.
- **v0.809** — models by folder (LM-Studio style, recursive scan, per-folder mmproj); vision output cap removed (was a flat 1200 that truncated answers).
- **v0.808** — VRAM/RAM gauges side by side; MoE offload `--n-cpu-moe` end-to-end; server status compacted to icon chips.
- **v0.807** — INI-driven launcher: per-model defaults out of the bat, first-match-wins sections.
- **v0.806** — THINK button re-activates when the model starts reasoning mid-stream.
- **v0.805** — reasoning panel preserved in loaded history (`renderStored` re-split) + model trace at top.
- **v0.804** — THINK auto-detected from the chat template; `INSTRUCTED`/`REASON_FIRST` flags; copy fix ("only web searches leave this machine").
- **v0.803** — THINK toggle locked (active + greyed) for reasoning-first models (Olmo).
- **v0.802** — reasoning panel for `<think>` tags and reasoning-first models; generalised flush state machine.
- **v0.801** — launcher runtime prompt for ngl/ctx; `Selmo.bat` translated to English.
- **v0.800** — VAD hands-free conversation (Silero `@ricky0123/vad-web`).
- **v0.716** — dynamic tok/sec bar (colour-coded); HTTPS proxy (8443) for the mobile mic.
- **v0.714** — phone header/keyboard fixes; Magistral OOM fix (CTX=8192); chunking verbatim-copy workaround.
- **v0.708** — UI rebuilt (retro-terminal, responsive 3-column → drawers); LAN binds on `0.0.0.0`; vision normalization.
- **v0.702** — vision IMG/OCR button + mmproj launcher flags (BUG-IMG-01 resolved).

---

## Backlog / next dev steps

**Three-profile system** *(next — see Profiles & personalities).* Selmo (blue) · Mizan (red, complete the palette) · Custom (neutral system palette + free, user-editable sampling parameters and system prompt). Adds the third badge and a small parameters panel bound to the per-request values the client already sends.

**Multi-document loading.** `fileDoc` is a single variable — a second upload silently replaces the first. Goal: load N documents and pick a strategy. *Serial/batch* — chunks from all docs processed in sequence, aggregated into one reply (each doc isolated so the model never sees two at once; maps to map-reduce summarisation). *Parallel/comparative* — same prompt applied independently per doc, results side by side (2–4 docs before the UI gets unwieldy). The literature's key point: cross-document attention is only safe at the synthesis step, not during chunk extraction — Selmo's isolated-per-chunk architecture already follows this.

**Other backlog.** Remove the `/web` leftovers from `chat.html` (prompt text, PTT prefix, `sendMsg` strip) now that the WEB toggle is the interface · VAD fully offline (serve onnx/wasm/worklet locally) · VRAM-adaptive NGL (read free VRAM + GGUF block_count to auto-suggest) · in-app model switcher (`/switch-model`, no manual restart) · in-app TTS voice selector (persisted in localStorage) · image generation as a separate `selmo_imggen.py` (stable-diffusion.cpp) · IMAP email bridge (`selmo_mail.py`) · Selmo as orchestrator (`selmo_master.py`, multi-step pipelines on long documents).

---

*The line that doesn't change: "While you sleep, your charging phone contributes to a network that belongs to no one and belongs to everyone. The earth turns, the wave follows the night wind, Selmo thinks."*
