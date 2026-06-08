# Selmo — Bug Report
*Documento vivente · aggiornato sessione 8 · Giugno 2026*

---

## BUG-META-01 · Edit tool tronca chat.html ⚠️ REGOLA PERMANENTE

**Sintomo**
Ogni volta che viene usato il tool `Edit` su `chat.html`, il file viene troncato a metà. Il tool riporta successo ma il file risulta incompleto. Verificato in sessioni 4, 5, 7.

**Causa**
Il file è grande (~1350 righe) con template literals multiriga e caratteri speciali. Il tool Edit ha un limite interno o un problema di encoding.

**Regola operativa — MAI DEROGARE**
Usare sempre Python via bash per modificare chat.html:
```bash
python3 << 'PYEOF'
path = '/sessions/.../mnt/Selmo/chat.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('OLD', 'NEW')
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
PYEOF
```
Verificare sempre dopo ogni modifica:
```bash
awk '/^<script>$/{p=1;next} /^<\/script>/{p=0} p' chat.html > /tmp/check.js && node --check /tmp/check.js && echo OK
tail -5 chat.html  # deve finire con </script></body></html>
```

---

## BUG-01 · Scrolling indipendente mancante
**Stato:** ⏳ Da fixare (sessione 9)

**Sintomo**
Le tre colonne (history / chat / dashboard) non scorrono in modo indipendente.

**Causa**
In CSS Grid, `min-height` default è `auto`: il container si espande ignorando il vincolo di altezza. L'`overflow-y:auto` non ha effetto se il container può crescere liberamente.

**Fix da applicare (via Python)**
```css
nav, main, aside { min-height: 0; }
```
Già identificato, mai applicato stabilmente (ogni volta chat.html è stato corrotto dopo).

---

## BUG-02 · Chat area posizionata troppo in basso
**Stato:** ⏳ Da diagnosticare (sessione 9)

**Sintomo**
I messaggi appaiono nella parte bassa dello spazio chat con un grande vuoto sopra.

**Causa probabile**
`#messages` con `display:flex; flex-direction:column` e `flex:1` — con pochi messaggi il flex container occupa tutta l'altezza. Possibile `align-content` o `margin-top:auto` non voluto.

**Azione necessaria**
Devtools → ispezionare height effettiva di `#messages` → cercare stili che spingono il contenuto verso il basso.

---

## BUG-03 · History sidebar vuota al caricamento
**Stato:** ⏳ Da fixare (sessione 9)

**Sintomo**
La sidebar mostra "no saved sessions" anche quando ci sono sessioni in localStorage.

**Causa**
`renderSessionList()` viene chiamata prima che `const SESS_KEY` venga dichiarata. La `try/catch` in `getSessions()` cattura silenziosamente il ReferenceError (TDZ) e ritorna `[]`.

**Fix da applicare (via Python)**
Spostare `const SESS_KEY` e `const MAX_SESS` all'inizio dello script, prima della prima chiamata a `renderSessionList()`.

---

## BUG-04 · Regressione ricerca web — TDZ su chatHistory
**Stato:** ⏳ Da diagnosticare (sessione 9)

**Sintomo**
Il comando `/web <query>` produce: `Error: can't access lexical declaration 'chatHistory' before initialization`

**Causa (ipotesi)**
`const chatHistory` in TDZ al momento della chiamata. Possibile interferenza con `window.history` del browser, o doppia dichiarazione nascosta.

**Tentativo fallito**
Rinominare `history` → `chatHistory` non ha risolto. Il rename ha anche accidentalmente rotto `loadSession` (cambiato `s.history.forEach` in `s.chatHistory.forEach`).

**Azione necessaria**
Devtools → riprodurre `/web` error → copiare stack trace completo → identificare riga esatta del TDZ.

---

## Fix applicati in sessione 8

| Fix | File | Stato |
|---|---|---|
| Stitch semplificato (join puro, rimosso dedup) | chunk_pipeline.py, translate_chunks.py | ✓ Applicato |
| `--timeout 0` (disabilita timeout server) | Selmo.bat, Mizan.bat | ✓ Applicato |
| Soglia 9500MB in logica launcher (ctx 8192 per 22-24B) | Selmo.bat, Mizan.bat | ✓ Applicato |

---

## Piano sessione 9

1. Aprire devtools → riprodurre `/web` error → copiare stack trace → fix BUG-04
2. Fix BUG-03: spostare SESS_KEY in cima allo script (Python)
3. Fix BUG-01: aggiungere `min-height:0` (Python)
4. Verificare BUG-02 con devtools
5. `node --check` dopo ogni modifica
6. Commit git dopo ogni fix — non aspettare la fine della sessione
