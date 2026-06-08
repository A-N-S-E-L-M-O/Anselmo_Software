# Selmo — Bug Report
*Documento vivente · aggiornato sessione 13 · Giugno 2026*

---

## BUG-META-01 · Mai il tool Edit su chat.html ⚠️ REGOLA PERMANENTE

**Sintomo** — Usando il tool `Edit` su `chat.html` il file viene troncato a metà: il tool riporta successo ma il contenuto è incompleto (verificato sessioni 4, 5, 7).

**Causa** — File grande (~2000 righe) con template literals multiriga e caratteri speciali.

**Regola — MAI DEROGARE**
- Modificare `chat.html` solo con Python via bash (`open` → `replace` → `write`), mai col tool Edit.
- Dopo ogni modifica: estrarre lo script inline e `node --check`; verificare con il tool **Read** (non `cat`/`wc` da bash, il mount può desincronizzarsi); il file deve finire con `</script></body></html>`.
- Riavviare `llama-server` dopo la modifica (può servire la cache) + Ctrl+F5.

```bash
awk '/^<script>$/{p=1;next} /^<\/script>/{p=0} p' chat.html > /tmp/check.js && node --check /tmp/check.js && echo OK
```

---

## Aperti / differiti

### BUG-IMG-01 · Visione + IMAGE (immagini/PDF) — differito, da ricostruire
**Stato:** ↩️ rollbackato a `16f02c8` (sessione 13), da ricostruire con commit a ogni step confermato.

Il path `+ IMAGE` (PDF renderizzato su canvas → vision) è stato rimosso col rollback: instabile e mai committato nella prima versione funzionante. La visione "classica" sulle sole immagini (jpg/png via `+ FILE` → `fileImage` multimodale) resta attiva.

Lezioni dalla diagnosi, da tenere a mente nella ricostruzione:
- Mai concatenare più pagine PDF in un canvas verticale gigante: aspect ratio estremo + base64 multi-MB → HTTP 400 / crash mmproj. Una immagine **per pagina**, lato lungo cap ~1280px.
- Il base64 che resta in `chatHistory` viene ri-inviato a ogni turno e pesa sul contesto: decidere se tenerlo o stripparlo dopo il primo turno.
- La visione richiede un modello multimodale + mmproj (Gemma 4). Su Mistral/EuroLLM le immagini vengono semplicemente ignorate.

---

## Risolti / archiviati

- **BUG-04** · `/web` TDZ su `chatHistory` — risolto: `/web` funziona (s13 mostra anche bolla utente + risposta nella lingua dell'utente).
- **BUG-05** · `input()` non appare al doppio click in `chunk_pipeline.py` — risolto s9: flag CLI `--thinking` / `--thinking-buffer`, domanda condizionata a `isatty`, wrapper `.bat`.
- **BUG-01 / BUG-02 / BUG-03** · vecchi problemi UI s7–s9 (scrolling colonne indipendente, posizione area chat, sidebar history vuota). Predatano il rework s12–s13: da riverificare solo se si ripresentano nell'interfaccia attuale.

---

*Nota mount bash (s9, ancora valida): il mount Linux può restare congelato allo stato di inizio sessione e non riflettere le scritture dei tool. Verificare sempre con il tool Read.*
