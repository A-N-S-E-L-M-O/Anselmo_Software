===== FILE: README.md =====

# A.N.S.E.L.M.O

**A fully local AI assistant that runs on your own hardware.** Chat, vision and OCR, document analysis, optional web search, voice, and image generation, all served from a single machine. Nothing leaves your device except what you ask for: an explicit web search, and the standard fetch of the page's open-source libraries on first load.

> *A.N.S.E.L.M.O: Algorithm for Neural Synthesis with Emotional-Linguistic Memory Optimization. Selmo, to friends.* From the book *Dialoghi con la lavatrice* (English edition: *The Washing Machine Dialogues*), which inspired this project.

**Status:** `v0.924` · **Session:** `33`  
A.N.S.E.L.M.O is **privacy-first by design**: your prompts, files, and conversations stay on your computer. It runs any open-source LLM with a permissive license on top of `llama.cpp`, behind a single HTML client.

## Features

- **Local chat** over `llama.cpp` with any compatible GGUF model.
- **Three profiles** (Selmo / Mizan / Custom), each with its own system prompt, sampling parameters, and colour palette, switchable at runtime.
- **Reasoning / THINK panel** for reasoning models (server-side extraction via `deepseek` format, no fragile client-side tag parsing).
- **Vision and OCR** for multimodal models: images and PDFs, one image per page. Requires `*mmproj*.gguf`.
- **Document analysis** with automatic chunking for `.docx`, `.odt`, `.pdf`, `.xlsx`/`.xls`/`.ods`, `.pptx`/`.odp`, `.txt`, `.csv`.
- **Optional web search**, off by default and explicit: local SearXNG (Podman) with DuckDuckGo fallback and a local query-rewrite step.
- **Voice loop**: Whisper STT + Kokoro TTS + hands-free VAD or Push-to-Talk.
- **Local image generation** via `stable-diffusion.cpp` (Z-Image-Turbo), text-to-image and image-to-image, with automatic VRAM swap so the image model and the LLM can share a 12 GB GPU.
- **Power and energy monitoring**: Real-time watts tracking (NVML/LibreHardwareMonitor) with session/total Wh persistence.
- **Phone access over HTTPS** with microphone support on port 8443.

## Architecture

One `llama.cpp` server, a set of single-purpose Python bridges, and one HTML client (`chat.html`). A front door serves the client and reverse-proxies every backend by port.

| Port | Service | Notes |
| :--- | :--- | :--- |
| **8080** / **8443** | Front Door (HTTP/HTTPS) | Serves `chat.html`. HTTPS required for mobile mic access. |
| **8081** | Web Search Bridge | SearXNG + DDG fallback. |
| **8082** | Power Monitor | NVML + CPU estimation. |
| **8083** | Whisper STT | Speech-to-text bridge. |
| **8084** | Kokoro TTS | Text-to-speech bridge. |
| **8086** | Image Generation | Shells out to `stable-diffusion.cpp`. |
| **8087** | Tray Control API | LLM load/unload/switch coordination. |
| **8089** | llama-server (LLM) | Loopback only (`127.0.0.1`). |

See `docs/selmo-dev.md` for the full engineering reference, port map details, and module split rules.

## Requirements

A.N.S.E.L.M.O runs on **any PC capable of running a local LLM**.
- **Minimum:** 8 GB RAM (CPU inference only; slower but functional).
- **Recommended:** NVIDIA GPU with CUDA support for accelerated inference and vision/image generation features.

### Test Bench Reference

Performance is validated against the following setup, which supports **Qwen3 30B-A3B** (MoE) at **>30 tokens/second**:

*   **CPU:** Intel i9-11900KF
*   **RAM:** 32 GB
*   **GPU:** NVIDIA RTX 4070 Ti 12 GB
*   **OS:** Windows 11

For optimal performance with large MoE models (e.g., Qwen3 35B-A3B), the launcher supports `--n-cpu-moe` to offload experts to RAM, ensuring smooth inference even when VRAM is constrained.

### Dependencies

```bash
pip install flask faster-whisper pynvml trafilatura requests --break-system-packages
pip install kokoro-onnx soundfile langdetect psutil --break-system-packages --prefer-binary
```

Large binaries and weights (`models/`, `bin/`, `tts/`, image weights, `*.gguf`, `*.onnx`, `*.safetensors`) are **not** included in this repository and must be downloaded separately. See `docs/selmo-dev.md` > "Setup & dependencies".

## Quick start

1. Put a GGUF model in `models/` and a `llama.cpp` CUDA build in `bin/`.
   - For vision, ensure an `*mmproj*.gguf` is present next to the model.
2. Launch with `Selmo.bat` (or the tray app). Pick the model when prompted.
3. Open the client:
   - **Desktop:** `http://127.0.0.1:8080/chat.html`
   - **Phone (mic over TLS):** `https://<your-lan-ip>:8443/chat.html` (accept the self-signed certificate once).

## License & Attribution

A.N.S.E.L.M.O is licensed under the **Apache License 2.0 with the Commons Clause**. This makes it **source-available**: you may use, study, modify, and redistribute it, but you may **not Sell** the Software (no resale, no paid hosting/consulting whose value derives substantially from Selmo). See [`LICENSE`](LICENSE).

**Attribution is required.** Any redistribution or derivative work must credit the A.N.S.E.L.M.O (Selmo) project and the book *Dialoghi con la lavatrice*. See [`NOTICE`](NOTICE).

Third-party open-source components remain under their own licenses; the list is in `docs/selmo-dev.md` > "Credits & licenses". Model weights are not distributed here and keep their respective licenses.