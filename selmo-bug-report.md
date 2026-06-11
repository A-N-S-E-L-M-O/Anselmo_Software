# Selmo — Bug Report
*Documento vivente · aggiornato sessione 15 · Giugno 2026*

---

## BUG-META-01 · Mai il tool Edit su chat.html ⚠️ REGOLA PERMANENTE

**Sintomo** — Usando il tool `Edit` su `chat.html` il file viene troncato a metà (verificato s4, s5, s7).

**Regola — MAI DEROGARE**
- Modificare `chat.html` solo con Python via bash (`open` → `replace` → `write`), mai col tool Edit.
- Dopo ogni modifica: estrarre lo script inline e `node --check`; verificare con il tool **Read**; il file deve finire con `</script></body></html>`.
- Riavviare `llama-server` dopo la modifica + Ctrl+F5.

---

## BUG-META-02 · Corruzione NUL / line-ending sul mount ⚠️ (sessione 13)

File scritti/modificati via tool su questo mount possono ritrovarsi pieni di byte NUL (`\x00`) e/o con line-ending sbagliati. Capitato in s13 a `Selmo.bat` (593 NUL + LF → il `^` di continuazione rompeva cmd → frammenti eseguiti come comandi → crash all'avvio) e a `selmo-bug-report.md` (3684 NUL → grep lo vedeva "binary"). Il tool **Write** sembra il colpevole; il tool **Edit** e la scrittura Python restano puliti.

**Regola**: dopo ogni modifica a `.bat`/`.md`, controllare `python3 -c "print(open('f','rb').read().count(b'\x00'))"` → deve dare 0. I `.bat` devono essere **CRLF**. Pulizia: rimuovere i NUL e riscrivere (i `.bat` in CRLF), preferibilmente via Python.

---

## BUG-IMG-02 · Visione da telefono → HTTP 400 ⚠️ APERTO (sessione 15)

**Sintomo** — Caricando un'immagine dal cellulare (Android) la richiesta multimodale a `llama-server` (8080) torna **HTTP 400**. Il modello in uso (Magistral-Small-2509) ha il mmproj caricato (auto-match su `Magistral-` in `Selmo.bat`), quindi la visione è attiva e da desktop ha funzionato.

**Già fatto (v0.708, non risolutivo)**
- Normalizzazione immagini lato client: `createImageBitmap`→canvas→JPEG, cap lato lungo 1280px, `accept="image/*"` (gestisce foto grandi e HEIC iPhone via decode di Safari).
- `max_tokens` cappato a 1200 quando c'è un'immagine (per non sforare la ctx 8192 coi token immagine).
- Il client mostra ora il **corpo dell'errore** del server invece di "HTTP 400" secco.

**Prossimo passo** — Leggere il messaggio reale del server (ora visibile nella bolla) e distinguere: overflow ctx, errore di decode immagine, o "multimodal not supported" per Magistral. Se è Magistral a non reggere la visione, ripiegare su Gemma 4 per i task immagine.

---

## BUG-IMG-03 · Visione + ricerca web insieme non funziona ⚠️ APERTO (sessione 15)

**Sintomo** — Con un'immagine caricata **e** WEB attivo (o comando `/web`), l'immagine non viene analizzata.

**Causa (individuata)** — In `sendMsg`, quando `IS_WEB_ON`/`isWebSearch` è vero, il flusso entra nel ramo web (≈riga 1643) che costruisce un prompt **solo testo** (contesto fonti) e gestisce/chiude la propria fetch **prima** di arrivare al blocco multimodale `if(fileImage)` (≈riga 1706): l'immagine allegata viene quindi ignorata. Inoltre `recentClean` fa `.replace(...)` su `m.content` che, per un messaggio-immagine precedente, è un **array** → possibile eccezione.

**Fix proposto** — Nel ramo web includere anche `imgContent` nel content array (testo contesto + `image_url`), oppure stabilire una priorità esplicita con avviso ("web ignora l'immagine"). Gestire il caso `content` array dentro `recentClean` (saltarlo o serializzarlo).

---

## Risolti

### BUG-IMG-01 · Visione + IMG/OCR (immagini/PDF) — ✓ RISOLTO (v0.702)

Tre cause distinte, finalmente isolate:
1. **Crash runtime mmproj** — l'encoder vision di Gemma 4 usa attenzione non-causale: tutti i token immagine devono stare in un solo ubatch. Con ubatch default (512) e immagine grande scattava `GGML_ASSERT(n_ubatch >= n_tokens)`. Fix: `--batch-size 2048 --ubatch-size 2048`.
2. **Immagine sovradimensionata/concatenata** — inutile: Gemma 4 ridimensiona al token-budget. Fix: una immagine **per pagina** a ~1280px + budget OCR `--image-min-tokens 1120 --image-max-tokens 1120`.
3. **Crash all'avvio del launcher (s13)** — NON erano i flag: era `Selmo.bat` corrotto (NUL + LF). Vedi BUG-META-02.

**Implementazione v0.702**
- `chat.html`: pulsante dedicato **+ IMG/OCR**; `loadFileAsImage` (immagini as-is, PDF una immagine per pagina ~1280px); invio come array multimodale; **thumbnail cliccabili** (apertura a piena risoluzione).
- `Selmo.bat` (ramo mmproj): `--image-min-tokens 1120 --image-max-tokens 1120 --batch-size 2048 --ubatch-size 2048`.
- Verificato funzionante su Gemma 4 12B, RTX 4070 Ti 12GB.

### Archiviati
- **BUG-04** · `/web` TDZ su `chatHistory` — risolto (s13).
- **BUG-05** · `input()` doppio click in `chunk_pipeline.py` — risolto s9.
- **BUG-01 / BUG-02 / BUG-03** · vecchi problemi UI s7–s9 — da riverificare solo se si ripresentano.

---

*Nota mount bash (s9): il mount Linux può restare congelato; verificare con il tool Read. Vedi BUG-META-02 per la corruzione NUL.*
