# Selmo

**A fully local AI assistant that runs on your own hardware.** Chat, vision and
OCR, document analysis, optional web search, voice, and image generation, all
served from a single machine. Nothing leaves your device except an explicit web
search.

> Part of the Selmo project, inspired by the book *Dialoghi con la lavatrice*.

Selmo is **privacy-first by design**: your prompts, files, and conversations
stay on your computer. It runs any open-source LLM with a permissive license on
top of `llama.cpp`, behind a single HTML client.

## Features

- **Local chat** over `llama.cpp` with any compatible GGUF model.
- **Three profiles** (Selmo / Mizan / Custom), each with its own system prompt,
  sampling parameters, and colour palette, switchable at runtime.
- **Reasoning / THINK panel** for reasoning models (server-side extraction, no
  fragile client-side tag parsing).
- **Vision and OCR** for multimodal models: images and PDFs, one image per page.
- **Document analysis** with automatic chunking for `.docx`, `.odt`, `.pdf`,
  `.xlsx`/`.xls`/`.ods`, `.pptx`/`.odp`, `.txt`, `.csv`.
- **Optional web search**, off by default and explicit: local SearXNG with a
  DuckDuckGo fallback and a local query-rewrite step.
- **Voice loop**: Whisper STT + Kokoro TTS + hands-free VAD.
- **Local image generation** via `stable-diffusion.cpp` (Z-Image-Turbo and other
  models), text-to-image and image-to-image, with an automatic VRAM swap so the
  image model and the LLM can share a 12 GB GPU.
- **Power and energy monitoring** (system watts, session and total Wh).
- **Phone access over HTTPS** with microphone support.

## Architecture

One `llama.cpp` server, a few single-purpose Python bridges, and one HTML client
(`chat.html`). A front door on port 8080 serves the client and reverse-proxies
every backend by port.

| Port | Service |
|---|---|
| 8080 / 8443 | Front door (HTTP / HTTPS), serves the client and proxies the backends |
| 8081 | Web search bridge (SearXNG + DuckDuckGo fallback) |
| 8082 | System power / energy monitor |
| 8083 | Whisper STT |
| 8084 | Kokoro TTS |
| 8086 | Image generation (stable-diffusion.cpp) |
| 8087 | Tray control API (LLM load/unload coordination) |
| 8089 | llama-server (LLM), loopback only, behind the front door |

See `selmo-dev.md` for the full engineering reference and `selmo-manifesto.md`
for the project's philosophy.

## Requirements

- Windows 11 with a CUDA-capable NVIDIA GPU (reference: RTX 4070 Ti 12 GB).
- Python 3.10+ (single interpreter, no venv required).
- A `llama.cpp` CUDA build in `bin/`.
- One or more GGUF models in `models/` (an optional `*mmproj*.gguf` next to a
  model enables vision).

```
pip install flask faster-whisper pynvml trafilatura requests --break-system-packages
pip install kokoro-onnx soundfile langdetect psutil --break-system-packages --prefer-binary
```

Large binaries and weights (`models/`, `bin/`, `tts/`, image weights, `*.gguf`,
`*.onnx`, `*.safetensors`) are **not** included in this repository and must be
downloaded separately. See `selmo-dev.md` > "Setup & dependencies".

## Quick start

1. Put a GGUF model in `models/` and a `llama.cpp` CUDA build in `bin/`.
2. Launch with `Selmo.bat` (or the tray app). Pick the model when prompted.
3. Open the client:

   - **Desktop:** `http://127.0.0.1:8080/chat.html`
   - **Phone (mic over TLS):** `https://192.168.x.x:8443/chat.html` (accept the
     self-signed certificate once)

## License

Selmo is licensed under the **Apache License 2.0 with the Commons Clause**. This
makes it **source-available**: you may use, study, modify, and redistribute it,
but you may **not Sell** the Software (no resale, no paid hosting/consulting
whose value derives substantially from Selmo). See [`LICENSE`](LICENSE).

**Attribution is required.** Any redistribution or derivative work must credit
the Selmo project and the book *Dialoghi con la lavatrice*. See [`NOTICE`](NOTICE).

Third-party open-source components remain under their own licenses; the list is
in `selmo-dev.md` > "Credits & licenses". Model weights are not distributed here
and keep their respective licenses.
