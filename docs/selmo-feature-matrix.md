# Selmo — Feature matrix vs local-LLM GUIs
*July 2026. Legend: OK = built-in · ext = only via external tool/config · no = not available.*

| Capability | Selmo | LM Studio | Jan | GPT4All | Open WebUI |
|---|---|---|---|---|---|
| Local LLM chat (llama.cpp) | OK | OK | OK | OK | OK |
| Fully open-source | OK | no (proprietary) | OK | OK | OK |
| Runs CPU-only (no GPU) | OK | OK | OK | OK | OK |
| Zero-install portable, click-to-run for non-devs | OK | installer | installer | installer | no (Docker/server) |
| Voice input / speech-to-text (Whisper) | OK | ext | ext | no | OK (local Whisper) |
| Hands-free voice conversation (VAD) | OK | no | no | no | OK (voice call) |
| Text-to-speech / read aloud | OK (Kokoro) | ext | no | no | OK |
| Image input / vision / OCR | OK | OK | OK | ext | OK |
| **Image generation (output)** | **OK (sd.cpp)** | ext | no | no | ext (ComfyUI/A1111) |
| Web search | OK (local SearXNG + fallback) | no | ext | no | OK |
| Document RAG / folder search ("chat with files") | OK | no | ext | OK (LocalDocs) | OK |
| Local filesystem agent (read/write files, multi-step) | OK | no | no | no | ext (tools) |
| **Whole-document, provable-coverage pipeline** | **OK** | no | no | no | no |
| **Energy / watt / tokens-per-Wh monitor** | **OK** | no | no | no | no |
| Phone access to your PC's model over LAN (secure) | OK | no | no | no | OK (web app) |
| GDPR/EU-by-design, explicit no-telemetry | OK (positioning) | no | partial | partial | partial |

## Reading of the table

Selmo's real story is **integration and out-of-the-box**, not any single feature.
LM Studio, Jan and GPT4All mostly reach voice, TTS and image generation only
through external tools you wire up yourself, if at all. The one genuinely
feature-rich rival is **Open WebUI** — it has STT, TTS, web search and vision
built-in — but it is server/Docker-shaped and its image generation and TTS still
lean on external engines (ComfyUI, AUTOMATIC1111, separate TTS backends) that you
configure. None of them do click-to-run for a non-technical user.

Selmo-only across the whole set: **image generation shipped in the box**, the
**exhaustive whole-document pipeline** that covers every passage of a long file
(the retrieval-style RAG everyone offers doesn't do that — Selmo now ships that
folder search *too*, with the pipeline on top of it), the **energy monitor**, and
the **folder-scoped filesystem agent** that reads and, when allowed, writes files
across several steps. Those, plus the family-grade portability, are the defensible
ground — the multimodal features are what make the package feel complete next to
them.
