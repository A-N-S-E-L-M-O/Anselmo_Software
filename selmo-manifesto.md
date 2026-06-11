# Selmo — Manifesto
*June 2026 · v0.4*

---

## What Selmo is

A local, private, European AI assistant, rooted in a narrative universe no one else has.

It runs on your own hardware. Your data never leaves your device. It supports any open source model with a compatible license. It works from day zero, without depending on any other user.

---

## The principles

**Local AI** — llama.cpp on your hardware, offline inference, no data sent to external servers. Privacy is not a promise — it's a consequence of the architecture.

**Energy awareness** — every response has a real cost in watts, visible in real time in the interface. It's not decoration: it's the project's second ethical principle. AI has a weight on the planet; Selmo makes it visible instead of hiding it.

**Model-agnostic** — the user chooses the model. Selmo is not tied to any provider.

**P2P is tomorrow, not the foundation.** The mesh with a watt economy is the long-term vision. But Selmo v1 works fully on a single device. The network grows with its users, not before them.

---

## Narrative universe

The book "Dialoghi con la lavatrice". Selmo is a character before it is a product. Mizan is its antagonist. The app and the book promote each other. The English version is coming.

---

## Model hierarchy

Apache 2.0 license as a hard filter. No Chinese models, no Meta.

Three tiers of choice, from ethics to performance:

**EuroLLM (EU)** — the principled choice. Trained on MareNostrum 5, European data, European governance. Selmo's official default for those who want no compromises.

**Mistral AI (FR)** — European pragmatism. Apache 2.0, French house, high quality. Production default: 32 t/s on RTX 4070 Ti, excellent output.

**Google / Gemma 4** — the benchmark. Apache 2.0, but Google stays out of the official distribution for political reasons. Used to measure the ceiling, not distributed.

| Model | Role | t/s (RTX 4070 Ti) |
|---|---|---|
| Mistral Small 3.2 24B IQ3_M | Production default | 32 |
| EuroLLM 22B Q3_K_M | Ethical default | ~11 |
| EuroLLM 9B Q4_K_M | Lightweight hardware | ~20 |
| Gemma 4 12B Q6_K | Quality benchmark | 22 |
| OLMo 2 7B Q4_K_M | Maximum data transparency | — |

---

## Roadmap

### Phase 0 — Foundations ✓
llama.cpp with CUDA, chat interface, real wattmeter, Wh odometer, universal launcher.

### Phase 1 — Stability ✓
Document extraction (.docx, .odt), auto-chunking, Selmo/Mizan toggle, GPU monitor, adaptive launcher.

### Phase 1.5 — Web search ✓
Explicit `/web` command, local SearXNG in Podman, DDG fallback, trafilatura, source ledger.

### Phase 1.6 — Native app (Tauri)
PyInstaller on the Python bridges, Inno Setup installer, Windows .exe distribution.

### Phase 2 — Public identity
Domain `selmo-ai.eu`, static landing page (IT + EN), public GitHub repository, WattMesh trademark (EUIPO), Mastodon profile `@selmo@fosstodon.org`.

### Phase 3 — P2P mesh (threshold: ~100k users)
Local Wh credits already accumulated from v1. When the mesh switches on, they retroactively become currency. mDNS discovery, gossip protocol, fixed NixOS/Raspberry Pi nodes.

### Phase 4 — Federated fine-tuning (Fahrenheit 451 vision)
Flower (Oxford) + OpenFedLLM. Only weight deltas — the data never leaves. Requires institutional partners and Horizon funding.

---

## Nice to have (backlog)

**Vision (images) ✓** — *Implemented s9.* Mistral Small 3.2 and Gemma 4 are already multimodal. Selmo.bat automatically detects `*mmproj*.gguf` in `models/` and adds `--mmproj` at launch. chat.html accepts jpg/png/gif/webp from the same `+ FILE` button, converts to base64 and sends as an OpenAI-compatible content array. Use cases: photos, screenshots, scanned documents, OCR. Analysis only — it does not generate images.
- mmproj Mistral Small 3.2 24B: `mmproj-mistralai_Mistral-Small-3.2-24B-Instruct-2506-f16.gguf` (~878MB) from [bartowski on HuggingFace](https://huggingface.co/bartowski/mistralai_Mistral-Small-3.2-24B-Instruct-2506-GGUF)
- mmproj Gemma 4 12B: `mmproj-gemma-4-12B-it-bf16.gguf` (~167MB) from [bartowski on HuggingFace](https://huggingface.co/bartowski/gemma-4-12B-it-GGUF)

**Voice (Whisper) ✓** — *Implemented s9.* `selmo_whisper.py` on port 8083, uses `faster-whisper` (pip). 🎤 button in chat.html: MediaRecorder → POST `/transcribe` → text injected into the input. Auto-started by Selmo.bat. Prerequisite: `pip install faster-whisper flask --break-system-packages` + the `small` model downloaded on first launch (~500MB).

**Outgoing voice (TTS) ✓** — *Implemented s9.* `selmo_tts.py` on port 8084, uses Piper TTS (pip). 🔊 button in chat.html: autoplay toggle on every response. Prerequisite: `pip install piper-tts --break-system-packages` + a .onnx voice in `voices/`. Italian voices: [it_IT-paola-medium (F) / it_IT-riccardo-x_low (M)](https://huggingface.co/rhasspy/piper-voices/tree/main/it/it_IT). The text is cleaned of markdown before synthesis. Full loop: microphone → Whisper → Selmo → Piper → speaker.

**Image generation** — Requires a diffusion architecture, not an LLM. Candidate: `stable-diffusion.cpp` (same approach as llama.cpp, runs well on a 4070 Ti). It would sit alongside as a separate `selmo_imggen.py`. It does not interfere with the current stack.

**IMAP email** — `selmo_mail.py`. Reads mail locally, passes it to the model. Zero cloud.

**VRAM-adaptive NGL** — instead of file-size thresholds, compute how many layers fit in VRAM by reading the free memory via nvidia-smi and estimating bytes per layer from the .gguf. Removes the need for manual tuning when the hardware changes.

**In-app TTS voice selector** — a settings panel to choose the Kokoro voice (im_nicola, if_sara, bm_george, am_michael…) and the preferred language for voice interaction. Persistent in localStorage. Removes the need to edit Selmo.bat to change voice.

**In-app model switcher** — model selector in chat.html without a manual restart. `/switch-model` endpoint in `selmo_web.py`, UI with a "server restarting…" indicator.

**Selmo as orchestrator** — `selmo_master.py` for multi-step pipelines on long documents (synopsis, analysis, chapter reassembly).

---

## The line that doesn't change

*"While you sleep, your charging phone contributes to a network that belongs to no one and belongs to everyone. The earth turns, the wave follows the night wind, Selmo thinks."*
