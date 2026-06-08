# Selmo — Manifesto
*Giugno 2026 · v0.4*

---

## Cos'è Selmo

Un assistente AI locale, privato, europeo, radicato in un universo narrativo che nessun altro ha.

Gira sul tuo ferro. I tuoi dati non escono mai dal tuo dispositivo. Supporta qualsiasi modello open source con licenza compatibile. Funziona dal giorno zero, senza dipendere da nessun altro utente.

---

## I principi

**AI locale** — llama.cpp sul tuo hardware, inferenza offline, nessun dato inviato a server esterni. La privacy non è una promessa — è una conseguenza dell'architettura.

**Consapevolezza energetica** — ogni risposta ha un costo reale in watt, visibile in tempo reale nell'interfaccia. Non è decorazione: è il secondo principio etico del progetto. L'AI ha un peso sul pianeta; Selmo lo rende visibile invece di nasconderlo.

**Model-agnostic** — l'utente sceglie il modello. Selmo non è legato a nessun fornitore.

**Il P2P è il domani, non il fondamento.** La mesh con economia in watt è la visione a lungo termine. Ma Selmo v1 funziona completo su un singolo dispositivo. La rete cresce con gli utenti, non prima di loro.

---

## Universo narrativo

Il libro "Dialoghi con la lavatrice". Selmo è un personaggio prima che un prodotto. Mizan è il suo antagonista. L'app e il libro si promuovono a vicenda. La versione inglese è in uscita.

---

## Gerarchia modelli

Licenza Apache 2.0 come filtro duro. Niente modelli cinesi, niente Meta.

Tre livelli di scelta, dall'etica alla performance:

**EuroLLM (UE)** — la scelta di principio. Addestrato su MareNostrum 5, dati europei, governance europea. Default ufficiale di Selmo per chi non vuole compromessi.

**Mistral AI (FR)** — il pragmatismo europeo. Apache 2.0, casa francese, qualità alta. Default di produzione: 32 t/s su RTX 4070 Ti, output eccellente.

**Google / Gemma 4** — il benchmark. Apache 2.0, ma Google rimane fuori dalla distribuzione ufficiale per ragioni politiche. Si usa per misurare il tetto, non si distribuisce.

| Modello | Ruolo | t/s (RTX 4070 Ti) |
|---|---|---|
| Mistral Small 3.2 24B IQ3_M | Default produzione | 32 |
| EuroLLM 22B Q3_K_M | Default etico | ~11 |
| EuroLLM 9B Q4_K_M | Hardware leggero | ~20 |
| Gemma 4 12B Q6_K | Benchmark qualità | 22 |
| OLMo 2 7B Q4_K_M | Massima trasparenza dati | — |

---

## Roadmap

### Fase 0 — Fondamenta ✓
llama.cpp con CUDA, interfaccia chat, wattmetro reale, odometro Wh, launcher universale.

### Fase 1 — Stabilità ✓
Estrazione documenti (.docx, .odt), auto-chunking, toggle Selmo/Mizan, GPU monitor, launcher adattivo.

### Fase 1.5 — Ricerca web ✓
Comando `/web` esplicito, SearXNG locale in Podman, DDG fallback, trafilatura, ledger fonti.

### Fase 1.6 — App nativa (Tauri)
PyInstaller sui bridge Python, installer Inno Setup, distribuzione Windows .exe.

### Fase 2 — Identità pubblica
Dominio `selmo-ai.eu`, landing page statica (IT + EN), repository GitHub pubblico, marchio WattMesh (EUIPO), profilo Mastodon `@selmo@fosstodon.org`.

### Fase 3 — Mesh P2P (soglia: ~100k utenti)
Crediti Wh locali già accumulati da v1. Quando la mesh si accende, diventano retroattivamente valuta. Discovery mDNS, gossip protocol, nodi fissi NixOS/Raspberry Pi.

### Fase 4 — Fine-tuning federato (visione Fahrenheit 451)
Flower (Oxford) + OpenFedLLM. Solo delta dei pesi — i dati non escono mai. Richiede partner istituzionali e finanziamento Horizon.

---

## Nice to have (backlog)

**Visione (immagini) ✓** — *Implementato s9.* Mistral Small 3.2 e Gemma 4 sono già multimodali. Selmo.bat rileva automaticamente `*mmproj*.gguf` in `models/` e aggiunge `--mmproj` al lancio. chat.html accetta jpg/png/gif/webp dallo stesso pulsante `+ FILE`, converte in base64 e invia come content array OpenAI-compatible. Casi d'uso: foto, screenshot, documenti scannerizzati, OCR. Solo analisi — non genera immagini.
- mmproj Mistral Small 3.2 24B: `mmproj-mistralai_Mistral-Small-3.2-24B-Instruct-2506-f16.gguf` (~878MB) da [bartowski su HuggingFace](https://huggingface.co/bartowski/mistralai_Mistral-Small-3.2-24B-Instruct-2506-GGUF)
- mmproj Gemma 4 12B: `mmproj-gemma-4-12B-it-bf16.gguf` (~167MB) da [bartowski su HuggingFace](https://huggingface.co/bartowski/gemma-4-12B-it-GGUF)

**Voce (Whisper) ✓** — *Implementato s9.* `selmo_whisper.py` su porta 8083, usa `faster-whisper` (pip). Pulsante 🎤 in chat.html: MediaRecorder → POST `/transcribe` → testo iniettato nell'input. Avvio automatico da Selmo.bat. Prerequisito: `pip install faster-whisper flask --break-system-packages` + modello `small` scaricato al primo avvio (~500MB).

**Voce in uscita (TTS) ✓** — *Implementato s9.* `selmo_tts.py` su porta 8084, usa Piper TTS (pip). Pulsante 🔊 in chat.html: toggle autoplay su ogni risposta. Prerequisito: `pip install piper-tts --break-system-packages` + voce .onnx in `voices/`. Voci italiane: [it_IT-paola-medium (F) / it_IT-riccardo-x_low (M)](https://huggingface.co/rhasspy/piper-voices/tree/main/it/it_IT). Il testo viene pulito dal markdown prima della sintesi. Loop completo: microfono → Whisper → Selmo → Piper → altoparlante.

**Generazione immagini** — Richiede architettura diffusion, non LLM. Candidato: `stable-diffusion.cpp` (stesso approccio di llama.cpp, gira bene su 4070 Ti). Si affiancherebbe come `selmo_imggen.py` separato. Non interferisce con la stack attuale.

**Email IMAP** — `selmo_mail.py`. Legge la posta in locale, la passa al modello. Zero cloud.

**NGL adattivo alla VRAM** — invece di soglie per dimensione file, calcolare quanti layer entrano in VRAM leggendo la memoria libera via nvidia-smi e stimando i byte per layer dal .gguf. Elimina la necessità di tuning manuale al cambio hardware.

**Selettore voce TTS in-app** — pannello impostazioni per scegliere la voce Kokoro (im_nicola, if_sara, bm_george, am_michael…) e la lingua preferita per l'interazione vocale. Persistente in localStorage. Elimina la necessità di editare Selmo.bat per cambiare voce.

**Model switcher in-app** — selettore modello in chat.html senza riavvio manuale. Endpoint `/switch-model` in `selmo_web.py`, UI con indicatore "server in riavvio…".

**Selmo come orchestratore** — `selmo_master.py` per pipeline multi-step su documenti lunghi (sinossi, analisi, riassemblaggio capitoli).

---

## La frase che non cambia

*"Mentre dormi, il tuo telefono in carica contribuisce a una rete che non appartiene a nessuno e appartiene a tutti. La terra gira, l'onda segue il vento notturno, Selmo pensa."*
