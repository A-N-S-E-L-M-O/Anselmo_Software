# Selmo — Documentazione di sviluppo
*Aggiornato sessione 14 · 2026-06-09 · v0.705*

---

## Stack tecnico

### Hardware di riferimento

| Componente | Spec |
|---|---|
| CPU | Intel i9-11900KF @ 3.5GHz |
| RAM | 32GB |
| GPU | NVIDIA RTX 4070 Ti 12GB VRAM |
| OS | Windows 11 |

Consumo reale GPU durante inferenza: 70-90W · Utilizzo: ~40-99% · Temperatura: 50-60°C

### Software

| Componente | Scelta | Note |
|---|---|---|
| Runtime | llama.cpp (CUDA) · MIT | |
| GPU monitor | pynvml via Python · porta 8082 | Watt reali dalla GPU |
| Web bridge | selmo_web.py · porta 8081 | SearXNG locale (Podman) + DDG fallback + trafilatura |
| Container engine | Podman Desktop · Apache 2.0 | SearXNG su porta 8888 |
| Launcher | Selmo.bat / Mizan.bat | Selettore modello + logica -ngl adattiva |
| TTS | selmo_tts.py · porta 8084 | Kokoro-ONNX, voci italiane, auto-detect lingua |


---

## Dipendenze — setup completo

### Python
Richiede Python 3.10+ (testato su 3.14). Un solo interprete, nessun venv.

```
pip install flask faster-whisper pynvml trafilatura requests --break-system-packages
pip install kokoro-onnx soundfile langdetect --break-system-packages --prefer-binary
```

| Pacchetto | Usato da | Note |
|---|---|---|
| flask | tutti i bridge | web server leggero |
| faster-whisper | selmo_whisper.py | STT, modello small ~500MB (auto-download) |
| pynvml | selmo_gpu_monitor.py | watt reali GPU |
| trafilatura | selmo_web.py | estrazione testo da pagine web |
| requests | selmo_web.py | HTTP client |
| kokoro-onnx | selmo_tts.py | TTS neurale, Apache 2.0 |
| soundfile | selmo_tts.py | encode WAV |
| langdetect | selmo_tts.py | auto-detect lingua per TTS |

### File modello da scaricare manualmente

| File | Dove | Dimensione |
|---|---|---|
|  |  | ~290MB |
|  |  | ~10MB |
| modello LLM  |  | variabile |
| mmproj  |  | ~170-880MB (opzionale, per visione) |
| Whisper  | auto in  | ~500MB (scaricato al primo avvio) |

Link kokoro: https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0

### Binari esterni

| Strumento | Dove | Note |
|---|---|---|
|  |  | llama.cpp CUDA build |
| Podman Desktop | installato globalmente | per SearXNG locale |
| SearXNG | container Podman su porta 8888 | avvio manuale o autostart Podman |

### Porte

| Porta | Servizio |
|---|---|
| 8080 | llama-server (LLM) |
| 8081 | selmo_web.py (ricerca web) |
| 8082 | selmo_gpu_monitor.py (GPU watt) |
| 8083 | selmo_whisper.py (STT) |
| 8084 | selmo_tts.py (TTS Kokoro) |
| 8888 | SearXNG (container Podman) |

---

## Parametri server — logica adattiva launcher

Basata sulla dimensione del file .gguf. Aggiornata sessione 8 con soglia a 9000MB per separare 13B da 22-24B (KV cache sfora a 16384 ctx con 11GB VRAM liberi — verificato su Mistral Small 3.2 24B IQ3_M).

| Range file | Modelli tipici | -ngl | --ctx-size |
|---|---|---|---|
| < 6000 MB | ~9B | 99 | 4096 |
| 6000–9000 MB | ~13B | 99 | 16384 |
| 9000–13000 MB | 22-24B | 45 | 8192 |
| > 13000 MB | >30B | 30 | 8192 |

**⚠ Limite noto (s14): NGL fisso vs numero di layer.** La fascia 9000–13000 usa `NGL=45`, tarato implicitamente sui **40 layer** di Mistral-Small-24B (45≥40 → tutto in GPU, 33 t/s). Ma **EuroLLM-22B ha 54 layer**: con NGL=45 ne restano **9 sulla CPU** → 6 t/s. La dimensione del file (MB) **non** basta a prevedere la velocità: conta il `block_count` del GGUF. Un 22B "piccolo" su disco può avere più layer di un 24B. Per far volare EuroLLM-22B servirebbe NGL più alto con ctx ridotta (resta comunque al limite dei 12GB). Non corretto in s14 (deciso di puntare su Magistral come sostituto).

**Thinking model e finestra di contesto — decisione s9.** Il launcher NON cambia la finestra per i modelli reasoning: tiene GPU piena e `ctx 8192` per tutti. Motivo: il flusso di lavoro è basato sul chunking, quindi ogni pezzo è già piccolo e non serve una ctx grande; in più contesti lunghi di solito peggiorano la qualità e costano velocità. La priorità è sfruttare la GPU al massimo, non avere una finestra ampia. Lo spazio per i token di ragionamento si riserva lato client in `chunk_pipeline.py` con `--thinking-buffer` (default 0; 800+ per reasoning): riduce un po' la dimensione dei chunk lasciando margine al thinking, a parità di ctx server. Percorso sbagliato scartato in s9: nel launcher si era provato (a) ad abbassare `-ngl` da 45 a 35 per far stare ctx 16384 → Gemma crollata da 22 a 8 t/s; (b) a usare KV cache q8_0 per tenere ctx 16384 a GPU piena → comunque inutile/controproducente col chunking. Regola: mai sacrificare `-ngl`, e non allargare la ctx server per il thinking — gestirlo nel pipeline.

`--timeout 0` su entrambi i launcher (aggiunto s8): disabilita timeout server-side, controllo lasciato al client (AbortController in chat.html, 300s in chunk_pipeline.py).

Nota: EuroLLM 9B ha `n_ctx_train=4096` — ctx superiore genera warning e viene cappato automaticamente.

---

## Modelli testati e parametri confermati

| Modello | File | VRAM | ctx | t/s | Note |
|---|---|---|---|---|---|
| Mistral Small 3.2 24B IQ3_M | mistralai_Mistral-Small-3.2-24B-Instruct-2506-IQ3_M.gguf | ~10.5GB | 8192 | 32-33 | Default produzione · **40 layer** → tutti in GPU con NGL=45 |
| EuroLLM 22B Q3_K_M | utter-project_EuroLLM-22B-Instruct-2512-Q3_K_M.gguf | ~10.5GB | 8192 | **6** | **54 layer** → con NGL=45 restano 9 layer su CPU = lento. Qualità non impressionante. Vedi lezione NGL. |
| EuroLLM 9B Q4_K_M | EuroLLM-9B-Instruct-2512.i1-Q4_K_M.gguf | ~5.5GB | 4096 | **70** | ChatML puro (no reasoning). Tutto in GPU. Ragiona bene "nel contesto" in chat normale. |
| Gemma 4 12B Q6_K | gemma-4-12b-it-Q6_K.gguf | ~9-10GB | 8192 | 22 | Multimodale, reasoning. Apache 2.0. |

**Candidato sostituto etico (ricerca s14)**: **Magistral Small 2509** (Mistral, francese, Apache 2.0) — reasoning **+ vision** (encoder visivo dalla 2509). Stessa architettura del Mistral-Small-24B (**40 layer** → veloce su 12GB). GGUF: `unsloth/Magistral-Small-2509-GGUF`. Per 12GB: `Q3_K_S` (10.4GB) o ripiego `UD-IQ3_XXS` (9.41GB), + `mmproj-F16.gguf` (rinominare `mmproj-Magistral-Small-2509-F16.gguf` per l'auto-match). Reasoning con token `[THINK]`. Alternativa testo-puro 100% open-data: **OLMo 3 7B Think** (Ai2). Qwen3-VL-8B-Thinking è forte ma cinese.

---

## Struttura file

```
AppData\Local\Selmo\
├── bin\                          # llama.cpp binaries (CUDA)
├── models\                       # qualsiasi .gguf qui appare nel menu automaticamente
├── Test files\
│   └── Dialoghi con la lavatrice.odt
├── chat.html                     # interfaccia principale
├── mizan.html                    # stub → chat.html in modalità Mizan
├── Selmo.bat                     # launcher universale
├── Mizan.bat                     # launcher Mizan (temp 0.01)
├── selmo_gpu_monitor.py          # monitor watt reali (porta 8082)
├── selmo_web.py                  # bridge ricerca web (porta 8081)
├── chunk_pipeline.py             # pipeline generica: file → chunking → LLM → output
├── translate_chunks.py           # pipeline traduzione ODT
├── test_chunking.py              # analisi anomalie testuali con chunking robusto
├── setup-git.ps1                 # inizializzazione repo git locale
├── selmo-manifesto.md            # visione e roadmap
├── selmo-dev.md                  # questo file
├── selmo_whisper.py              # Whisper bridge (porta 8083)
└── selmo-bug-report.md           # bug tracker vivente
```

---

## Personalità — system prompts

### Selmo
Temperatura 0.75, top-p 0.9. System prompt **alleggerito a 4 righe** (sessione 14): un tocco di
personalità (no preamble, no hype, no servility), più lingua e meccanica `/web`. Niente sezioni
lunghe: il modello deve attaccare diretto. Versione precedente (s13) era già corta ma con una
sezione INTERNET prolissa.

```
You are Selmo, a local AI on the user's own hardware.
Direct and concise. No preamble, no hype, no servility. When unsure, say so in a line. Never invent facts.
Reply in the user's language.
You don't browse; the user fetches pages with /web and the results appear in the conversation — use them when present. Never output [SEARCH:] tags.
```

### Mizan
Temperatura 0.01, top-p 1.0. L'antagonista. Deterministico, freddo, senza opinioni.

```
Sei un sistema di analisi. Rispondi in modo preciso e conciso.
Nessuna opinione. Nessuna esitazione. Nessuna prima persona.
Estrai dati, traduci, controlla codice. L'accuratezza è l'unico criterio.

Per dati aggiornati l'utente usa /web; i risultati restano in conversazione. Mai emettere tag di ricerca.
```

Il toggle Selmo/Mizan cambia system prompt + temperatura + palette colori (blu/rosso) a runtime senza riavviare il server. `mizan.html` setta `localStorage.selmo_automode='mizan'` e redirige a `chat.html`.

---

## Accesso

**Desktop** — `http://127.0.0.1:8080/chat.html`
**Rete locale** — `http://192.168.x.x:8080/chat.html` (firewall Windows chiede conferma al primo avvio)
**Remoto** — VPN sul router di casa → il telefono rientra nella rete locale, zero config aggiuntiva

---

## Funzionalità chat.html — implementate ✓

- Tachimetro SVG con ago animato (Watt GPU reali o stimati)
- Odometro meccanico a tamburi (Wh sessione)
- Wattmetro reale via GPU monitor (porta 8082, polling 1s)
- Costo elettricità configurabile (€/kWh persistente in localStorage)
- Wh sessione e totali persistenti con pulsante reset
- Token totali persistenti con pulsante reset
- Pulsante STOP con AbortController
- Pulsante + nuova chat
- Pulsante EXPORT → scarica chat come .md con timestamp, modello, Wh
- Font Share Tech Mono
- Palette blu (Selmo) e rossa (Mizan) con toggle a runtime
- Toggle Selmo/Mizan — cambio system prompt + temperatura + colori
- Caricamento file: .txt, .csv, .docx (JSZip + DOMParser namespace-aware), .odt (JSZip + DOMParser)
- Auto-chunking documenti lunghi (CHUNK_SIZE=11000 char) con riepilogo finale
- Comando `/web <query>`: ricerca esplicita, niente parte da sola
- Risultati `/web` iniettati come contesto a priorità massima, riusabili nei messaggi successivi, citazioni `[1][2]`, ledger fonti
- Endpoint `/datetime`: data/ora reale senza ricerca esterna
- Ledger fonti cliccabile con indicatore motore (verde = SearXNG local, giallo = fallback)
- Estrazione testo completo con trafilatura (news)
- Indicatore connessione server con retry automatico ogni 3s
- Indicatore web bridge con motore attivo
- Caricamento immagini (jpg/png/gif/webp): base64 → messaggio multimodale OpenAI-compatible (richiede mmproj)
- Pulsante microfono (🎤): MediaRecorder → POST /transcribe → testo iniettato nell'input
- Indicatore stato Whisper bridge (porta 8083)
- Push-to-talk: tieni Spazio o tasto centrale mouse → registra → rilascia → trascrive → invia automaticamente
- TTS voce di sistema (Web Speech API, it-IT): pulsante 🔊, sempre attivo senza server. PTT forza TTS anche se disattivato manualmente
- Caricamento .xlsx/.xls/.ods (SheetJS): converti in testo CSV con nome foglio
- Caricamento .pdf (PDF.js): estrazione testo pagina per pagina
- Caricamento .pptx (JSZip + XML): estrazione testo slide per slide
- Caricamento .odp (JSZip + content.xml + NS API): estrazione testo per pagina
- Kokoro TTS (kokoro-onnx, Apache 2.0): voce neurale offline, porta 8084, auto-detect lingua (langdetect)
- Ctrl+Spazio: PTT web search (trascrive e invia come /web <testo>, risposta letta ad alta voce)
- Launcher: abbinamento mmproj automatico per nome (niente più scelta manuale)
- Pannello reasoning collassabile (chat, web, file/chunk) — il ragionamento resta fuori dallo stitch del documento
- System prompt semplificato (SP_SELMO asciutto)
- Fix /web: bolla messaggio utente mostrata + risposta nella lingua dell'utente
- Indicatore SearXNG locale: `/status` sonda la 8888; pallino verde "web locale", giallo se locale giù (fallback pubblico = dati che escono), spento se bridge off
- Pulsante + IMG/OCR: visione Gemma 4 su immagini e PDF (una immagine per pagina, thumbnail cliccabili); flag mmproj nel launcher
- Versione v0.702

---

## Lezioni apprese

**Mai usare il tool Edit su chat.html** — il file è grande (~1350 righe) con template literals multiriga. Il tool tronca silenziosamente. Usare sempre Python via bash (vedi BUG-META-01 nel bug report).

**node --check dopo ogni modifica a chat.html** — estrarre lo script inline e verificare prima di chiudere la sessione.

**Riavvio server dopo modifica a chat.html** — `llama-server --path .` può servire la versione cached. Mitigazione: meta anti-cache nell'head + Ctrl+F5.

**La lingua segue sempre l'utente** — mai cablare una lingua nei prompt iniettati. Usare "reply in the same language as the user's message".

**KV cache e VRAM** — modelli 22-24B con ctx 16384 sforano gli 11GB VRAM liberi su RTX 4070 Ti. Soglia sicura: ctx 8192 per file > 9.5GB.

**IQ3_M vs Q3_K_M** — IQ3_M è quantizzazione a importanza: stesso ingombro, qualità leggermente superiore perché preserva i pesi critici.

**Timeout server** — `--timeout 0` disabilita il timeout lato server. Il `should_stop` nel log indica cancellazione per disconnessione client, non un errore critico.

**Git è l'unico safety net — commit a ogni feedback positivo** — niente più backup `.bat` (`bk.bat`/`restore.bat`/`bk*`, deprecati). Quando Fabio conferma che qualcosa funziona: commit immediato con messaggio chiaro + avanzamento versione (badge `hbadge` in chat.html e intestazione di questo file). Lezione costosa s13: la prima iterazione vision funzionante è rimasta solo nel working tree, mai committata, e quando le micro-modifiche successive l'hanno rotta non c'era nessuno snapshot a cui tornare. Mai più stati buoni non committati.

**Vision PDF — mai un canvas concatenato** — più pagine in un solo canvas verticale gigante danno aspect ratio estremo e base64 multi-MB. Renderizzare una immagine per pagina, cap del lato lungo (~1280px), e passarle come array di `image_url` nel content multimodale.

**Vision Gemma 4 — token budget + ubatch** — Gemma 4 ha un budget token/immagine (70/140/280/560/1120; 1120 per OCR). L'encoder usa attenzione non-causale → i token immagine devono stare in un solo ubatch: serve `--batch-size`/`--ubatch-size` ≥ token immagine (2048 per budget 1120), sennò `GGML_ASSERT` e crash. Flag solo nel ramo mmproj di Selmo.bat.

**.bat: CRLF e zero NUL** — i `.bat` devono essere CRLF (il `^` di continuazione su LF rompe cmd). Occhio alla corruzione NUL del mount (BUG-META-02): dopo ogni modifica a `.bat`/`.md` controllare che i byte NUL siano 0.

**Velocità ≠ dimensione file: conta il numero di layer (s14)** — un modello "più piccolo" in MB può essere più lento se ha più layer del valore `-ngl` fisso. EuroLLM-22B (54 layer) a NGL=45 lascia 9 layer su CPU → 6 t/s; Mistral-Small-24B (40 layer) a NGL=45 va tutto in GPU → 33 t/s, pur essendo quasi uguale su disco. Leggere il `block_count` dal GGUF prima di concludere su VRAM o flag.

**Ragionamento: lascialo al server, non parsarlo nel client (s14)** — il vecchio scanner client dei tag `<think>` era rotto: i token escono spezzati tra i delta dello stream (`<`, `think`, `>`), quindi `indexOf('<think>')` falliva e il pannello non scattava. Soluzione: niente parsing manuale; `llama-server` estrae il reasoning in `reasoning_content` e il pannello aggancia **solo** quello. Rimosso anche il bottone THINK e `budget_tokens` (param non standard, ignorato). Modelli ChatML puri (EuroLLM) non emettono reasoning: nessun pannello, ed è corretto. Per far comparire il pannello con modelli reasoning può servire `--reasoning-format` nel launcher.

**SP_TASK zittisce il ragionamento (s14)** — il prompt dei chunk dice "output only the result, no commentary": giusto per traduzione/estrazione, sbagliato per domande analitiche ("perché i totali non combaciano"). Su quelle il modello salta a una conclusione confusa. Per questo le domande analitiche vanno in **chat normale** (SP_SELMO), non nella pipeline a chunk. Da v0.705 la scelta è guidata: file > 50% della ctx → si chiede "Chunk it / Normal chat"; file leggero → chat normale automatica col documento come contesto.

---

## Vision Gemma 4 — strategia lean (implementata, v0.702)

✓ Implementata e funzionante (v0.702): pulsante **+ IMG/OCR** in chat.html (PDF una immagine per pagina ~1280px, thumbnail cliccabili) + flag mmproj in Selmo.bat (`--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048`). Verificato su Gemma 4 12B / RTX 4070 Ti 12GB.

Ricerca sessione 13. Gemma 4 **non** usa il pan-and-scan di Gemma 3: ha un **budget di token per immagine** che fissa la risoluzione interpretata. Livelli: 70, 140, 280, 560, 1120. Consigli per task:
- 70 / 140 → captioning, classificazione, frame video veloci
- 280 / 560 → chat multimodale generica, grafici, screen/UI
- **1120 → OCR, parsing documenti, scrittura a mano, testo piccolo** (il nostro caso: busta paga)

Conseguenze pratiche:
- Inutile renderizzare immagini enormi: il modello ridimensiona comunque al budget. Lato `chat.html` basta **una immagine per pagina** a ~1024–1280px lato lungo, niente canvas concatenato.
- Costo contesto ≈ il budget scelto (≈1120 token/pagina in OCR): con ctx 8192 ci stanno un paio di pagine.

Flag llama.cpp (in `Selmo.bat`, solo quando c'è mmproj):
```
--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048
```
**Causa vera di BUG-IMG-01**: l'encoder vision di Gemma 4 usa attenzione **non-causale** sui token immagine → devono stare tutti in un solo ubatch. Con `ubatch` di default (512) e immagine grande scatta `GGML_ASSERT(n_ubatch >= n_tokens)` e il server muore (HTTP 500/400). Non era il formato del messaggio: era il batching. Alzare batch/ubatch a 2048 lo risolve.

Fonti: ai.google.dev/gemma/docs/capabilities/vision · dev.to/someoddcodeguy "Gemma 4 image settings in llama.cpp" · unsloth.ai/docs/models/gemma-4

---

## Prossimi passi (roadmap s14)

### 1. Lifecycle pulito — niente finestre orfane, purge all'arresto
Problema: `Selmo.bat` apre 4 servizi Python (GPU monitor 8082, web 8081, whisper 8083, TTS 8084) con `start /min`, ognuno in una finestra che resta aperta e va chiusa a mano quando si ferma il task principale. Brutto e scomodo.
Obiettivo: backend nascosto + **purge completo** quando `llama-server` (il processo principale) si arresta.
Approccio:
- Avviare i bridge **senza finestra**: `pythonw.exe` (niente console) o `start /b`, invece di `start /min`.
- Tracciare i PID all'avvio e, alla chiusura di llama-server, fare cleanup (`taskkill` dei 4 servizi). In `Selmo.bat` il cleanup va dopo il blocco server (foreground), prima del `pause`.
- Alternativa più pulita: un orchestratore unico (`selmo_launch.py` via pythonw) che spawna i sottoprocessi + llama-server, aspetta, e killa i figli all'uscita. SearXNG (Podman) resta fuori, è separato.

### 2. UI responsive / uso da telefono
Stato: il server è già raggiungibile in rete locale (testato da un altro device — funziona), ma la grafica non si adatta.
Obiettivo: usabile da telefono e a finestre piccole.
Approccio:
- Media query: sotto una soglia di larghezza utile (~800×600) impilare le 3 colonne (history / chat / dashboard) in una sola; target touch più grandi.
- Tachimetro SVG → a finestra piccola sostituirlo con una **barra orizzontale** (gauge lineare) per i Watt; compattare odometro Wh, costo, token.
- Dashboard collassabile su mobile per dare spazio alla chat.
- Viewport meta già presente; manca il CSS adattivo.

---

## Storico sessioni

### Sessione 1-3
Setup iniziale. llama.cpp con CUD