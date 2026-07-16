# Selmo - adding a model

Selmo ships **engine-only and model-agnostic**: the installer sets up llama.cpp
and the app, and no model is bundled. On the **first launch** it offers to
download one default - **Mistral-7B-Instruct v0.3 Q3_K_M** (~3.5 GB, Apache 2.0,
European, no reasoning: a solid all-rounder, light enough for an entry-level
8 GB PC). Say yes to start chatting immediately, or say no and add your own. The
default is pulled from Hugging Face (`bartowski/Mistral-7B-Instruct-v0.3-GGUF`);
you are never locked to it.

## How to add a model

1. Download a GGUF model file.
2. Drop it into the `models\` folder inside the Selmo install
   (`...\Selmo\models\`). For vision, put an `*mmproj*.gguf` next to the model,
   in the same folder.
3. In Selmo's browser UI open the settings panel (click the `model:` label in
   the header) and pick the model. The tray loads it; no restart needed.

`selmo-models.ini` already carries tuned launch flags for the models below,
matched by a substring of the file name (**first match wins** - specific names
sit above generic ones). A recognised model therefore gets sensible defaults
automatically: context size, GPU offload (`-ngl`), reasoning format, MoE expert
offload and chunk size. On a CPU-only machine the tray auto-rewrites `-ngl` to 0
when it finds no NVIDIA GPU, so a GPU-tuned section still loads; you can also
lower `-ngl` by hand in that model's `srv` line.

## Recommended models

The project's stance: **Apache 2.0 as the preferred license, European first.**
Models outside that line are still supported - they are flagged so you can
choose with open eyes.

| Model | Role | License / origin | Approx size | Fit |
|---|---|---|---|---|
| **Mistral-7B-Instruct v0.3** | First-run default; light all-rounder | Apache 2.0 - FR | ~3.5 GB (Q3_K_M) / ~4.4 GB (Q4_K_M) | Any PC, incl. 8 GB CPU-only |
| **EuroLLM-9B-Instruct** | Ethical default: EU data, disclosed training | Apache 2.0 - EU | ~5.5 GB (Q4_K_M) | 16 GB+; no reasoning, ctx capped at 4096, very fast (~70 t/s) |
| **Mistral Small 3.2 24B** | Production default; best general chat / translation | Apache 2.0 - FR | ~10.5 GB (IQ3_M) | 12 GB GPU (40 layers all on GPU, ~32-33 t/s) |
| **Magistral Small 2509 24B** | Reasoning **+ vision**, multilingual | Apache 2.0 - FR | ~9.4-10.4 GB + mmproj | 12 GB GPU; `[THINK]` reasoning |
| **Qwen3 30B/35B-A3B** | Premium quality: reasoning (+ vision), MoE | Apache 2.0 - CN, data undisclosed | ~18-20 GB (Q4), experts stream from RAM | 12 GB GPU **+ 32 GB RAM** via `--n-cpu-moe`; >30 t/s |
| **Qwen3.5-2B** | Ultra-light test / chat | Apache 2.0 - CN | ~1.3 GB (Q4_K_M) | Any PC; reasoning optional (THINK toggle) |
| **LFM2.5-8B-A1B** | Fastest on weak hardware, reasons (MoE, ~1B active) | LFM Open License - US | ~5.2 GB | Low-end / fast demo - **not Apache, not EU** |
| **LFM2-VL-1.6B** | Low-power image input / OCR | LFM Open License - US | ~2 GB (model + mmproj) | Any PC; the light vision option |
| **Gemma 4 12B** | Quality benchmark (measured, not distributed) | Gemma Terms - US | ~9-10 GB (Q6_K) | Reference only - the Gemma license is not freely redistributable |

Notes on fit: on an 8 GB machine keep the model under ~5 GB and leave room for
the OS and browser; if it swaps, drop one quant step (Q4 -> Q3_K_M). LFM2.5 is
the fast pick for low-end hardware but is American and not Apache 2.0, so it sits
outside the project's "European, Apache" line - flag it if you ship it as a
default. Gemma is used only to benchmark quality, not distributed with Selmo.

## Running Qwen3 30B/35B-A3B on 12 GB (the premium option)

Qwen3-30B-A3B and 35B-A3B are **Mixture-of-Experts** models: ~30-35B total
parameters but only ~3B active per token, so they punch far above their
inference cost. On a 12 GB GPU the trick is `-ngl 99` to place the whole model on
the GPU, then `--n-cpu-moe N` to claw the experts of N layers back into system
RAM until it fits 12 GB. The `[Qwen3]` launch preset in `selmo-models.ini` (the
tuned flags ship with Selmo; the **model itself is not bundled** - you download
it, like every model) uses `--n-cpu-moe 26` at
ctx 32768; **start at ~26 and lower N while VRAM holds** - fewer offloaded layers
means more experts on the GPU and higher speed. On the reference box (RTX 4070 Ti
12 GB + 32 GB RAM) this runs at **>30 tokens/second**, which is what makes a
30-35B model practical on consumer hardware at all.

Reasoning is available through the THINK toggle (`think=kwarg`: off by default,
turn it on when you want it). Vision is present in the model upstream, but
llama.cpp's support for Qwen3 vision is recent - test OCR / image tasks before
relying on them, and fall back to Magistral or LFM2-VL for image input if they
misbehave. Practical requirement: a 12 GB GPU **and ~32 GB system RAM** for the
offloaded experts; on less RAM, use a smaller model.

## Embedding models for RAG / agent search (optional)

RAG mode - semantic search over a folder of your own files, and the agent's
`rag_search` tool - needs a small **embedding** model in `models\`, separate from
the chat model. Selmo runs two retrieval modes, each with its own tiny embedder
(CPU-only, auto-detected by a marker in the file name):

| Mode | Embedder | For | Approx size |
|---|---|---|---|
| **docs** | `nomic-embed-text-v1.5` | prose: txt, md, docx, pdf, notes | ~146 MB (Q8) |
| **code** | `jina-embeddings-v2-base-code` | source code | ~172 MB (Q8) |

You switch mode from the folder bar in the UI. **Neither is needed just to chat**,
and the agent's file tools (list, read, write, text search) work with no embedder
at all. For documents, `nomic-embed-text` is the one that matters; **`jina` is
optional** - add it only if you want code-aware semantic search over a codebase.
If an embedder is missing, that mode simply stays empty and the other keeps
working. Pull both as GGUF from Hugging Face (search for `nomic-embed-text-v1.5`
and `jina-embeddings-v2-base-code`) and drop them in `models\`; the bridge finds
them by name, no config needed.

## Where to download

Pull GGUFs from Hugging Face - e.g. `bartowski` (Mistral), `utter-project`
(EuroLLM), `unsloth` (Magistral, Qwen3), `LiquidAI` (LFM2), or `mradermacher`
(broad coverage). Match the quant to your hardware using the sizes above.
