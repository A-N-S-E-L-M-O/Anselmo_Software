# Selmo — istruzioni per Claude

Leggi **per primo** `selmo-dev.md` (sezione "Lezioni apprese") e `selmo-bug-report.md`.

## Workflow git — regola Fabio (sessione 13) · NON DEROGARE

Git è l'**unico** safety net. I backup via `bk.bat` / `restore.bat` / cartelle `bk*` sono **deprecati**: non usarli, non crearne, non proporli.

A **ogni feedback positivo di Fabio** (es. "funziona", "ok", "perfetto", "ci siamo"):
1. Committa **subito** la modifica confermata, con messaggio chiaro.
2. **Avanza la versione** di **+0.001** (millesimi): badge `v0.x` in `chat.html` (cerca `class="hbadge"`, ~riga 421) **e** intestazione di `selmo-dev.md`. Es: v0.7 → v0.701 → v0.702. La **v1.0 è riservata** alla release "vera"; non arrivarci con i bump incrementali.

Non accumulare modifiche non committate. Ogni stato confermato-buono deve finire in un commit, così non si perde mai (lezione costosa s13: la versione vision che funzionava era solo nel working tree e non è stata committata → persa).

Non committare stati **non** confermati: se è un tentativo, dillo e aspetta il test di Fabio prima del commit + bump.

## chat.html — regole permanenti

- **MAI** il tool Edit su `chat.html` (tronca silenziosamente). Solo Python via bash — vedi BUG-META-01.
- `node --check` sullo script estratto dopo ogni modifica; verifica con il tool Read, non con `cat`/`wc` da bash.
- Riavviare `llama-server` dopo modifica (può servire la cache); meta anti-cache + Ctrl+F5.
