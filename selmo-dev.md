# Selmo — Development documentation
*Updated session 21 · 2026-06-18 · v0.829*

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
| 8082 | System-power monitor (system watts + Wh counter; GPU via NVML, CPU power estimated from load, LHM optional) | `selmo_gpu_monitor.py` |
| 8083 | Whisper STT | `selmo_whisper.py` |
| 8084 | Kokoro TTS | `selmo_tts.py` |
| 8085 | LibreHardwareMonitor remote web server (**optional** real CPU/GPU power) | external |
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
| pynvml / psutil | `selmo_gpu_monitor.py` | GPU watts/load/VRAM (NVIDIA) + system RAM |
| trafilatura / requests | `selmo_web.py` | web text extraction + HTTP |
| kokoro-onnx / soundfile / langdetect | `selmo_tts.py` | neural TTS + WAV + language detect |

**Manual downloads:** the LLM `.gguf` (any compatible model dropped in `models\`), an optional `*mmproj*.gguf` next to it for vision, the Whisper model (auto on first launch), and a Kokoro voice (`kokoro-onnx` releases). **External binaries:** llama.cpp CUDA build in `bin\`, Podman Desktop for the optional local SearXNG, and **LibreHardwareMonitor** (system-power source) installed by `setup-lhm.ps1` into `bin\LibreHardwareMonitor\`.

**Whole-system power (v0.816).** `selmo_gpu_monitor.py` reports a system-power estimate, not just GPU watts. It reads CPU package power and GPU power from LibreHardwareMonitor's remote web server (`http://127.0.0.1:8085/data.json`, vendor-agnostic — works for NVIDIA and AMD; the GPU figure no longer depends on NVML) and computes `wall ≈ (cpu + gpu + OTHER_DC) / PSU_EFF` (defaults `OTHER_DC=45 W` for board/RAM/drives/fans, `PSU_EFF=0.88` for an 80 PLUS Gold unit at partial load; both tunable against a wall meter). `setup-lhm.ps1` makes this reproducible with no manual GUI step: it downloads a pinned LHM release (v0.9.4) into `bin\LibreHardwareMonitor\`, writes `LibreHardwareMonitor.config` (web server on `:8085`, start minimized to tray), and registers a scheduled task that runs LHM elevated at logon (RAPL needs admin, so this skips the per-boot UAC prompt). `selmo_server.py` also launches LHM as a fallback when the task isn't used. The main dashboard gauge now shows **system watts** (CPU+GPU+losses, 0–500 W scale); the GPU%/temp/VRAM mini-gauges stay NVIDIA-only via NVML.

**Driver-free power & backend energy (v0.820).** LHM turned out to be a non-starter for a 5-minute install on an arbitrary machine: its WinRing0 driver needs admin and is quarantined by Microsoft Defender's vulnerable-driver blocklist, so CPU package power and core temperatures don't read on a locked-down box (the GPU still works — that's NVAPI/NVML, no driver). So **LHM is now optional**. When it isn't feeding real watts, `selmo_gpu_monitor.py` keeps GPU watts from NVML and **estimates CPU watts from utilisation** — linear idle→TDP, with laptop/desktop defaults chosen by battery presence (`psutil.sensors_battery()`): laptop `4→28 W`, desktop `20→125 W`, plus the `OTHER_DC`/`PSU_EFF` loss model; all four are tunable against a wall meter. `cpu_est:true` marks an estimate and the client prefixes it with `~`. CPU **temperature** is best-effort (LHM only, package→hottest-core) and hidden when unavailable. Net effect: the whole power panel needs only `pip install psutil pynvml`.

Energy is integrated in the monitor itself (`integrate_energy`, a 1 s tick of `sys_watts`) as the single source of truth: `wh_session` (resets each launch) and `wh_total` (persisted in `selmo-wh.json`, gitignored), both resettable via `GET /reset_session` and `/reset_total`. Every `chat.html` instance only displays these, so multiple tabs or devices can never double-count — the box draws one set of watts no matter how many UIs are open (the old client-side `localStorage` counter summed across instances). The dashboard regroups the hardware readouts under the gauge (watt split → VRAM/RAM → GPU/CPU load); the session-watt-hours odometer reads to 0.1 Wh.

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

A profile bundles a **system prompt + sampling parameters + colour palette**, switched at runtime from the watermark/logo (click it to open the profile modal) — no server restart. As of **v0.815 there are three profiles** — Selmo (blue), Mizan (red), Custom (neutral) — each a `body` state with its own palette. The chosen profile persists in `localStorage` and is restored on reload.

### Selmo — blue, the assistant

Temperature 0.75, top-p 0.9. Warm, ironic, concise. Prompt trimmed to four lines (s14) so the model gets straight to the point:

```
You are Selmo, a local AI on the user's own hardware.
Direct, concise, and ironic. No preamble, no hype, no servility. When unsure, say so in a line. Never invent facts.
Reply in the user's language.
You don't browse; web results may appear in the conversation — use them when present. Never output [SEARCH:] tags.
```

*(v0.815 dropped the old `/web` wording from the prompt — the WEB toggle is the interface. The functional `/web` remnants in `chat.html`, the push-to-talk prefix and the `sendMsg` strip, are still there — see backlog.)*

### Mizan — red, the antagonist

Temperature 0.01, top-p 1.0. Deterministic, cold, no opinions, no first person. The narrative antagonist from *Dialoghi con la lavatrice* (see manifesto). Purpose: extraction, translation, code-checking — accuracy as the only criterion.

```
You are Mizan, an analysis system. Identify yourself as Mizan when asked.
Reply precisely and concisely. No opinions. No hesitation. No first person.
Extract data, translate, check code. Accuracy is the only criterion.

When web results are present in the conversation, use them. Never emit search tags.
```

*(v0.815: Mizan now names itself — previously it was an anonymous "analysis system" and refused to say who it was.)*

### Custom — neutral, the open profile

User-defined. A neutral grey **system palette** (no blue, no red) with the sampling parameters and system prompt exposed for direct editing, instead of inheriting a preset. Defaults: temp 0.7, top-p 0.95, top-k 40, with a generic helper system prompt. The values and prompt persist in `localStorage` (`scustomtemp`/`scustomtopp`/`scustomtopk`/`scustomsp`) and feed each request live.

### The three profiles (shipped v0.815)

| Profile | Palette | Personality | Parameters |
|---|---|---|---|
| **Selmo** | Blue (default) | warm, ironic assistant | preset: temp 0.75, top-p 0.9, top-k 40 |
| **Mizan** | Red (full palette) | cold analysis system, self-identifies | preset: temp 0.01, top-p 1.0, top-k 0 |
| **Custom** | Neutral grey (no blue/red) | user-defined | free: temp / top-p / top-k / system prompt, all editable |

**Implementation (chat.html, v0.815).** `currentProfile` is one of `selmo`/`mizan`/`custom`, persisted in `localStorage` and restored on load. `activeSP()` returns the active system prompt (`SP_SELMO` / `SP_MIZAN` / the editable `CUSTOM_SP`) and feeds `chatHistory[0]` via `syncThinkPrompt()`. `setProfile(name)` swaps `document.body` between no-class / `.mizan` / `.custom`, calls `syncSampling()` to set `currentTemp`/`currentTopP`/`currentTopK`, rewrites the watermark text, and refreshes the modal. Every chat request now sends `temperature`/`top_p`/`top_k` from those globals (the three `currentTemp` send-sites gained `top_p:currentTopP,top_k:currentTopK`). The modal — opened by clicking the logo — carries three badges (`.pm-selmo`/`.pm-mizan`/`.pm-custom`) and a parameters panel that is editable only under Custom and read-only otherwise.

**Palettes.** Each profile is a `body` state. `body.mizan` red-shifts the full token set via an **R↔B channel swap** that preserves luminance (`#001166` → `#661100`), with scoped overrides for every hardcoded blue surface (body gradient, header, nav/aside, gauges, session items, avatars, both bubbles, input area, think panel); accents go red/orange (`--cyan` → `#ff4d63`, `--yellow` → `#ff9a33`) rather than channel-swapped, so it reads as red. `body.custom` desaturates the same set to neutral greys. Both are scoped so Selmo's (unclassed) rules stay exactly as they were.

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

**Git is the only safety net.** No `.bat` backups (deprecated). Only Fabio commits and bumps the version, from his own Windows shell — never the agent. On every positive feedback, prepare the change and hand Fabio a ready-to-paste commit that also bumps the version +0.001 (the `hbadge` in `chat.html` and this file's header). v1.0 is reserved for the real release. Costly s13 lesson: a working version that lived only in the working tree, never committed, was lost. **s17 reprise:** the docs described the Selmo/Mizan profile system as already built, but a preflight (`git log -S setProfile`, grep for `body.mizan`/`SP_MIZAN`) showed it had never reached the committed `chat.html` — only ancient v0.31 traces existed. The bash mount was clean (matched HEAD), so this was real lost/never-committed work, not a cache lie. Lesson: when docs and code disagree, trust `git` and the Read tool, and confirm the starting state before "completing" something — it may not exist yet.

**The language always follows the user.** Never hardcode a language in injected prompts — "reply in the same language as the user's message".

**Speed ≠ file size — layer count is what matters.** Read `block_count` from the GGUF; `-ngl` must cover it or layers spill to CPU (s14). Never sacrifice `-ngl` to widen ctx.

**KV cache & VRAM.** 22–24B at ctx 16384 overflows 11 GB free on the 4070 Ti; safe ctx 8192 for files > 9.5 GB. The "45 % rule" is about chunk-input vs the *running* context, not the launch ctx, and only holds for models that actually keep their nominal context (EuroLLM does not — kept at 8192).

**Reasoning belongs to the server.** No client-side `<think>` parsing (tokens split across deltas). `--reasoning-format` extracts it into `reasoning_content`; the panel hooks only that. `SP_TASK` silences reasoning ("output only the result"), which is wrong for analytical questions — those go to normal chat, not the chunk pipeline.

**Web search needs a query-rewrite step (s17, v0.817).** The engine query used to be the raw user message (`webQuery=txt.trim()`), so short follow-ups ("17 anni" → the *movie*), typos and chatty phrasing returned junk and the model wasted its turn apologising for useless results. Fix: a local RAG-style rewrite (`rewriteQuery`, cf. Rewrite-Retrieve-Read / HyDE) distils the recent turns + new message into a keyword query *before* searching; the sources footer then shows the query actually sent (`🔎 "…" ← original`) so it's auditable. Two traps cost a few rounds: (1) an in-prompt `/no_think` is **ignored** by reasoning models (Qwen, Gemma) — disable thinking via `chat_template_kwargs.enable_thinking:false` with a plain-call retry if the server rejects the field; (2) make extraction template-proof — demand a single `QUERY:` line and pull it from `content` + `reasoning_content` after stripping any `<think>`/`[THINK]` block, with a generous token budget as a net. On any failure (`!res.ok`, no `QUERY:` line, exception) the function returns the raw message, so behaviour never regresses.

**Vision.** One image per page, never a concatenated canvas (extreme aspect ratio, multi-MB base64). Gemma 4 has a per-image token budget (1120 for OCR) and a non-causal encoder that needs `--batch-size/--ubatch-size ≥ image tokens` (2048) or it crashes.

**Server timeout.** `--timeout 600` (phone uploads) or `0` to disable; `should_stop` in the log is client disconnect, not a fault. **IQ3_M vs Q3_K_M:** same footprint, IQ3_M slightly better (importance quantization preserves critical weights).

**cmd `set /p`.** Each `set /p` must be on its own line — chaining with `&` does not run the second prompt.

---

## Nice-to-have / future work

**tokens/Wh efficiency log** *(arxiv publication candidate)*
Per-session append to a simple CSV or JSON: model name, quantization, average t/s, average system watts (GPU+CPU, already available from `selmo_gpu_monitor.py`), computed tokens/Wh. Data sources are all live: `/metrics` on llama-server for token counts, port 8082 for power. No UI needed — background logging only. Motivation: provides empirical MoE-vs-dense energy efficiency data on consumer hardware, directly in the spirit of the project's GDPR-by-design / local-first ethos. Magistral (dense 24B) vs Qwen3 (MoE 3B active / 30B total) on the same RTX 4070 Ti is a clean controlled experiment worth publishing.

**RAG / persistent memory** *(community contribution candidate)*
Index a local folder of documents (PDF, DOCX, TXT) into a persistent vector store; inject relevant chunks into context before each reply. Enables cross-session memory and corpus-level queries. Implementation: a local embedding model (`nomic-embed-text` or `all-MiniLM`) + `faiss` or `chromadb` for vector search — no external services. Out of scope for the core project (Selmo targets single-document, single-session workflows) but a natural extension for the open codebase. Not a priority until the base project stabilises.

**`no_think` as ini flag** *(general, not model-specific)*
Add `no_think=true` as an optional key in `selmo-models.ini`. `selmo_server.py` writes it to `selmo-config.json`; `chat.html` reads it and prepends `/no_think` to every user message. Works for any future model that supports the token, without hardcoding model names.

**Split `chat.html` into per-subsystem files** *(maintainability / tooling-reliability — candidate v0.900 major sublevel)*
A single ~2,765-line, ~139 KB `chat.html` is the worst case for the mount/Edit-tool bugs (BUG-META-01/02): the Edit tool truncates it, so every change goes through Python-in-bash and re-reads/re-writes the whole file across the flaky bridge. Runtime cost of the single file is nil (Firefox handles it easily) — this is purely an editing-reliability win, not a performance one. Plan: extract the inline `<script>` into ~6–7 plain `.js` files loaded with classic `<script src>` tags (NOT ES modules, NO bundler), served statically by llama-server from the project root (works over the 8443 proxy too). Classic scripts keep every function global, so the inline `onclick="fn()"` handlers keep working with zero behavioural change; ES modules would force rewiring every event handler. Suggested split mirrors the subsystems: `selmo-core.js` (globals, config, `addMsg`, sessions), `selmo-chat.js` (`sendMsg`, streaming, THINK, `maxTok`), `selmo-profiles.js`, `selmo-docs.js` (files, chunking, export), `selmo-web.js` (toggle, `rewriteQuery`), `selmo-voice.js` (Whisper/Kokoro/VAD), `selmo-vision.js` + `selmo-imagegen.js`. Leave the `<style>` block inline (not the pain point; optional later cleanup). Cache-bust with versioned URLs (`selmo-chat.js?v=0.x`). Safe method (the extraction is itself the riskiest edit on this file): assemble the files in a scratch dir, `node --check` each, diff the concatenation against the original script to prove the JS is byte-identical apart from file boundaries, write across in one pass, verify with the Read tool. Land it as its own committed checkpoint BEFORE stacking new features.

---

## Changelog (condensed, reverse chronological)

- **v0.826** — per-reply output download (first document-export step): each assistant reply gets `↓ .md` / `↓ .tsv` buttons under the bubble. `.md` saves the reply verbatim; `.tsv` extracts the first Markdown table as tab-separated with a UTF-8 BOM — tab dodges the Italian comma-decimal / semicolon-list CSV collision (a comma-CSV misparses on double-click in IT-locale Excel/Calc), the BOM keeps accented chars intact. Pure client-side (no new dependency, no bridge, nothing leaves localhost); `addDownloadBar()` called at the two live finalize sites. Manual-button trigger, not the LLM-decided tag protocol (deferred to avoid the `[SEARCH:]`/`QUERY:` parsing fragility); reloaded-from-history turns don't show the bar yet (deferred).
- **v0.824** — BUG-EXIT-01 fixed: `_do_exit` now calls `os._exit(0)` instead of `icon.stop()` — pystray's stop does not reliably unblock `icon.run()` on Windows, leaving the tray process hung after Exit. `selmo-models.ini` tuned: `[EuroLLM-22]` section added with `--cache-type-k/v q4_0` and `-ngl 54` to prevent KV-cache overflow on 12 GB VRAM; `[EuroLLM-9B]` ctx corrected to 4096 (native training context); `[Magistral]` ctx reduced 16384→8192 (same overflow fix, recovered ~15 t/s); `[Mistral]` kept as reference. GUI picker (`selmo_tray.py`) now shows the ini `note` inline next to each model name and uses a wider window. `chunk_pipeline.py`: fixed-size chunks (boundary detection removed); truncation detection via `finish_reason == length` now prefixes output with `[TRUNCATED]`; `available_tokens` capped at `max_tokens` to prevent 1:1 tasks (translation) from receiving chunks larger than the output budget.
- **v0.823** — no black window at startup: the tray now runs under `pythonw.exe` (via new `Selmo.vbs`, window style 0) so no console is ever allocated — hiding it was unreliable because on Windows 11 `GetConsoleWindow()` returns an internal helper window under Windows Terminal, not the visible tab. The console model picker is replaced by a Tkinter dialog (`_gui_picker`, still edits srv args + chunking size); `print()` diagnostics go to `selmo-tray.log`. `llama-server` launched with `CREATE_NO_WINDOW` so it doesn't pop its own console when the parent has none. Child cleanup no longer depends on the console ctrl handler: all children join a Windows Job Object with `KILL_ON_JOB_CLOSE`, so they die when the tray exits for any reason.
- **v0.820** — power without a kernel driver: CPU watts **estimated from load** (laptop/desktop profile via battery detection), GPU from NVML, LHM now **optional** (its WinRing0 driver is Defender-blocked and admin-only, so CPU power/temp don't read on a locked-down box); estimated figures flagged with `~`. Energy counter moved into the monitor as the single source of truth — `wh_session`/`wh_total` persisted in `selmo-wh.json` with `/reset_session` `/reset_total` endpoints — so multiple open UIs can't double-count (was client-side `localStorage`). Device line gained CPU load (temperature best-effort, LHM-only); session odometer reads to 0.1 Wh; hardware readouts regrouped under the gauge (watt split → VRAM/RAM → GPU/CPU load).
- **v0.818** — profile params mini-help: native `title` tooltips on Temp / Top-p / Top-k / System prompt in the profile modal, explaining each parameter and its use-case ranges on hover.
- **v0.817** — web search query-rewrite: a local RAG-style step (`rewriteQuery`) turns the chat turn into a keyword query before hitting the engine — fixes terse follow-ups (e.g. "17 anni" returning the movie) by inheriting the running topic from recent turns. Thinking disabled via `chat_template_kwargs.enable_thinking:false` (+ plain-call retry) since in-prompt `/no_think` is ignored by Qwen/Gemma; strict `QUERY:` line parsed from `content`/`reasoning_content`; the sources footer shows the query actually sent (`🔎 "…" ← original`). Graceful fallback to the raw message on any failure.
- **v0.816** — whole-system power: the main gauge now shows CPU+GPU+losses (system watts), not GPU-only. `selmo_gpu_monitor.py` reads CPU package + GPU power from LibreHardwareMonitor (`:8085/data.json`, vendor-agnostic — NVIDIA and AMD) and applies a PSU/baseline losses model. New `setup-lhm.ps1` makes it installer-reproducible (pinned download + config + elevated scheduled task, no manual GUI step); `selmo_server.py` launches LHM as a fallback.
- **v0.815** — three-profile system shipped (Selmo blue / Mizan red / Custom neutral): full Mizan red palette via R↔B channel swap + scoped surface overrides; Custom neutral palette with editable temp/top-p/top-k/system-prompt bound per-request; profile modal with three badges opened from the logo; profile persisted in `localStorage`. Mizan self-identifies; `/web` wording dropped from the system prompts; neutral welcome bubble. *(The profile system documented since s14 had never actually reached the committed `chat.html` — built from scratch this session; see Lessons.)*
- **v0.814** — docs streamline (consolidated Mizan notes, three-profile roadmap, `/web` → WEB toggle wording, mount-cache notes). Docs only — `chat.html` badge stayed v0.812.
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
- **v0.716** �