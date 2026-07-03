# Selmo - adding a model

Selmo ships **engine-only and model-agnostic**. The installer sets up llama.cpp
and the app; no model is bundled. On the **first launch** it offers to download
one default (Mistral-7B-Instruct v0.3, ~4.4 GB - Apache 2.0, European, no
reasoning: a solid all-rounder that fits an 8 GB PC, a bit slower on CPU-only):
say yes to get chatting immediately, or say no and add your own model as below.
The file is pulled from Hugging Face (`bartowski/Mistral-7B-Instruct-v0.3-GGUF`).
You are never locked to the default.

## How to add a model

1. Download a GGUF model file.
2. Drop it into the `models\` folder inside the Selmo install
   (`...\Programs\Selmo\models\`). For vision, put an `*mmproj*.gguf` next to
   the model, in the same folder.
3. In Selmo's browser UI open the settings panel and pick the model. The tray
   control API loads it; no restart needed.

`selmo-models.ini` already carries tuned launch flags for the models below
(matched by a substring of the file name), so a recognised model gets sensible
defaults automatically. On a CPU-only machine, remove `-ngl ...` from that
model's `srv` line (or lower it) so it does not try to offload to a weak GPU.

## Recommended models

The project's stance: Apache 2.0 as the preferred license, European first.

| Model | Why | License / origin | Approx Q4 size | Good for |
|---|---|---|---|---|
| EuroLLM-9B-Instruct | The principled default: EU data, disclosed/auditable training | Apache 2.0, EU | ~5.5 GB | 16 GB+ machines |
| Mistral-7B-Instruct v0.3 | Light, distributable, solid all-rounder | Apache 2.0, FR | ~4.4 GB | 8 GB machines |
| LFM2.5-8B-A1B | Fastest on weak hardware (MoE, ~1B active), reasons | LFM Open License (not Apache), US | ~5.2 GB | low-end / fast demo |
| Pixtral-12B | Vision / OCR | Apache 2.0, FR | ~7.5 GB + mmproj | image input |
| EuroLLM-22B | Larger EU translator (testing) | Apache 2.0, EU | ~10.5 GB | strong machines |

Notes on fit: on an 8 GB machine keep the model under ~5 GB and leave room for
the OS and browser; if it swaps, drop one quant step (Q4 -> Q3_K_M). LFM2.5 is
the fast pick for low-end hardware but is American and not Apache 2.0, so it sits
outside the project's "100% European, Apache" line - flag it as such if you ship
it as a default.

Download GGUFs from Hugging Face (e.g. the `bartowski`, `LiquidAI`, or
`mradermacher` repositories).
