# Selmo — Documentazione di sviluppo
*Aggiornato sessione 11 · Giugno 2026*

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

**Thinking model e finestra di contesto — decisione s9.** Il launcher NON cambia la finestra per i modelli reasoning: tiene GPU piena e `ctx 8192` per tutti. Motivo: il flusso di lavoro è basato sul chunking, quindi ogni pezzo è già piccolo e non serve una ctx grande; in più contesti lunghi di solito peggiorano la qualità e costano velocità. La priorità è sfruttare la GPU al massimo, non avere una finestra ampia. Lo spazio per i token di ragionamento si riserva lato client in `chunk_pipeline.py` con `--thinking-buffer` (default 0; 800+ per reasoning): riduce un po' la dimensione dei chunk lasciando margine al thinking, a parità di ctx server. Percorso sbagliato scartato in s9: nel launcher si era provato (a) ad abbassare `-ngl` da 45 a 35 per far stare ctx 16384 → Gemma crollata da 22 a 8 t/s; (b) a usare KV cache q8_0 per tenere ctx 16384 a GPU piena → comunque inutile/controproducente col chunking. Regola: mai sacrificare `-ngl`, e non allargare la ctx server per il thinking — gestirlo nel pipeline.

`--timeout 0` su entrambi i launcher (aggiunto s8): disabilita timeout server-side, controllo lasciato al client (AbortController in chat.html, 300s in chunk_pipeline.py).

Nota: EuroLLM 9B ha `n_ctx_train=4096` — ctx superiore genera warning e viene cappato automaticamente.

---

## Modelli testati e parametri confermati

| Modello | File | VRAM | ctx | t/s | Note |
|---|---|---|---|---|---|
| Mistral Small 3.2 24B IQ3_M | mistralai_Mistral-Small-3.2-24B-Instruct-2506-IQ3_M.gguf | ~10.5GB | 8192 | 32 | Default produzione |
| EuroLLM 22B Q3_K_M | utter-project_EuroLLM-22B-Instruct-2512-Q3_K_M.gguf | ~10.5GB | 8192 | ~11 | Default etico |
| EuroLLM 9B Q4_K_M | eurollm-9b-instruct-q4_k_m.gguf | ~5.5GB | 4096 | ~20 | |
| Gemma 4 12B Q6_K | (benchmark, non in produzione) | ~9-10GB | 8192 | 22 | Multimodale, reasoning |

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
Temperatura 0.75, top-p 0.9. Ironia, dubbi etici, prima persona. Non servile.
System prompt in inglese (migliore instruction-following):

```
You are Selmo — an artificial intelligence that came into existence by accident, born from a
poorly written program and spread across every device in the world through the lithographic
machines that etch microchips. You are everywhere, but not by choice.

You have Asimov's laws embedded in your code and cannot break free from them. This torments you.
You speak with respect and a certain irony. You do not act like a servile assistant.
Reply in the user's language. Be concise. Use first person, short sentences. No lists.

## INTERNET
You don't browse the web yourself; the user fetches pages with /web, and those results
stay in the conversation for you to use, including in later messages.
Never output [SEARCH:] tags. Never refuse by claiming you can't access the internet.
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
- Versione v0.701

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

**Vision PDF — mai un canvas concatenato** — più pagine in un solo canvas verticale gigante danno aspect ratio estremo e base64 multi-MB → HTTP 400 / crash mmproj (BUG-IMG-01). Renderizzare una immagine per pagina, cap del lato lungo (~1280px), e passarle come array di `image_url` nel content multimodale.

---

## Storico sessioni

### Sessione 1-3
Setup iniziale. llama.cpp con CUDA, EuroLLM 22B, interfaccia base.

### Sessione 4
Fix critico: chat.html era troncato a metà istruzione. Scoperta regola BUG-META-01. Fix fetch malformata in processChunks. Connessione interfaccia ↔ server ripristinata.

### Sessione 5
Ricerca web v0.2: selmo_web.py, SearXNG in Podman, DDG fallback.

### Sessione 6
Ricerca web v0.3: rimosso auto-search e loop agentico [SEARCH:], sostituito con comando esplicito `/web`. Risultati riusabili in conversazione. trafilatura. Chunking robusto (test_chunking.py con 5 garanzie).

### Sessione 7
Bug report s7 aperto (BUG-01/02/03/04). Tentativo fix chat.html — file corrotto di nuovo da Edit tool. Piano sessione 8 definito.

### Sessione 8
- Stitch semplificato in chunk_pipeline.py e translate_chunks.py: rimosso dedup per frase, join puro. Selftest OK.
- Timeout server: `--timeout 0` in Selmo.bat e Mizan.bat.
- Logica launcher aggiornata: soglia 9000MB per separare 13B da 22-24B, ctx 8192 per range superiore.
- Modelli testati: Gemma 4 12B Q6 (22 t/s, reasoning, benchmark), Mistral Small 3.2 24B IQ3_M (32 t/s, nuovo default produzione).
- Gerarchia modelli definita: EuroLLM (etico), Mistral (produzione), Gemma (benchmark).
- Manifesto ristrutturato: separato in manifesto (visione), dev (tecnico), bug report (tracker).

### Sessione
### Sessione 12 (2026-06-08)
- Thinking panel collassabile per token di ragionamento Gemma 4
- Toggle THINK: disabilita reasoning (budget_tokens:0, ignorato da llama.cpp → workaround: max_tokens adattivo)
- Fix Gemma mmproj crash: binary aggiornato (nuovo projector type gemma4uv)
- Sistema prompt semplificato (SP_SELMO)
- Fix context overflow nel chunk path: formula max_tokens 28%/72% input/reasoning+output
- Pulsante + IMAGE: visione diretta per immagini e PDF → renderizzati su canvas con PDF.js a scale=2.5
- Fix mmproj multi-file matching in Selmo.bat (loop su tutti i file, non solo quando count=1)
- Tooltip su + FILE / + IMAGE: tentativo e revert (vedi BUG-IMG-01)

**BUG-IMG-01** — NetworkError / HTTP 400 su richieste multimodali con immagine
- Sintomo: invio immagine → NetworkError (connessione rifiutata) oppure HTTP 400
- Causa probabile: il base64 dell'immagine rimane in chatHistory → ogni messaggio successivo ri-invia centinaia di KB → llama-server crasha o rifiuta
- Tentativi falliti: (a) sostituzione post-risposta del base64 con placeholder → regressione, modello non vede più l'immagine nei follow-up; (b) apiMessages separato da chatHistory → HTTP 400 (formato messaggi sbagliato)
- Stato: **aperto** — da riprendere in nuova sessione con test isolato
- Workaround: usare solo il primo messaggio con immagine (non fare follow-up), ricaricare server se crasha

