# Selmo — Bug Report
*Documento vivente · aggiornato sessione 13 · Giugno 2026*

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
