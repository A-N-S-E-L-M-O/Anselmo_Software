# Selmo — Multilanguage (i18n) strategy
*Analysis + plan only. Nothing applied. July 2026.*

## 1. Where we stand (verified)

There is **no i18n scaffolding** at all: `navigator.language`, no `t()` lookup, no
locale table. Every user-facing string is hardcoded, across three separate
surfaces:

- **`chat.html` markup** — ~30+ `title=` / `placeholder=` / `aria-label=`
  attributes, button captions, the welcome bubble.
- **The 9 `.js` files** — ~39 dynamic message sites (`addMsg`, toasts, the status
  pills, error lines).
- **`selmo_tray.py`** — the tkinter menu labels and the Windows notifications
  (a Python GUI, not the browser — its own surface).

It is **already drifting**: some strings are English, some are Italian
(`"Conversazione a mani libere"`, `"Whisper non attivo"`, `"SearXNG locale OFF —
fallback pubblico"`). That drift is the proof of the problem — with no single
place for text, languages leak in ad hoc and the UI ends up half-and-half.

## 2. One distinction that must stay clean

Two different "languages" live in this app, and only one of them is the target:

- **Model output language** — already solved. `SP_SELMO` / `SP_MIZAN` and
  `THINK_INSTR` say *"Reply in the user's language"*, so the model already
  follows the user. This axis needs **nothing**. Do not fold the `SP_` prompts
  into the UI table — they are model-facing English instructions with their own
  lifecycle, and English is what the model follows best.
- **UI chrome language** — the buttons, tooltips, placeholders, error lines,
  tray menu. This is hardcoded and is the whole job.

Keeping these two apart avoids the classic mistake of "translating" the system
prompts and degrading model behaviour.

## 3. The data format — your instinct is right, with one refinement

Your idea (first column = key, then one column per language) is exactly the right
data model: **one row per string** means keys can never drift between languages,
and a missing cell is a visible gap. The only refinement is to express that table
as **one JSON file** instead of CSV, so both the browser (JS) and the tray
(Python) can read it natively with no CSV parser and no build step:

```json
{
  "send.placeholder":   { "en": "Type a message...", "it": "Scrivi un messaggio..." },
  "toolbar.web.title":  { "en": "Web search ON/OFF", "it": "Ricerca web ON/OFF" },
  "err.whisper_off":    { "en": "Whisper not active. Start selmo_whisper.py.",
                          "it": "Whisper non attivo. Avvia selmo_whisper.py." },
  "web.results":        { "en": "{n} results", "it": "{n} risultati" }
}
```

This is literally your columnar table (key, then a column per language), just in a
shape the code can load directly. Adding a language = adding one key per row (e.g.
`"fr"`), and any untranslated cell falls back to English automatically.

If you would rather **edit in a spreadsheet**, we author a `selmo-i18n.tsv`
(TAB-separated — note `selmo-chat.js` already prefers TSV because the Italian
locale uses the comma) and a ~10-line script emits the JSON. But for a project
with no build step, I would start with the JSON directly and only add the TSV
source if hand-editing JSON gets annoying.

**Keys are semantic, not English text.** `send.placeholder`, not
`"Type a message..."`. English-as-key looks tempting (nothing to invent) but it
breaks every language the moment you reword the English, and long tooltips make
grotesque keys. Semantic dotted ids are a little more work up front and stable
forever.

## 4. The mechanism (fits the no-bundler, classic-script architecture)

- A new **`selmo-i18n.js`**, loaded **first** (before the other modules, same
  "definitions early, boot last" rule as the v0.902 split), exposing two globals:
  `t(key, vars)` and `setLang(code)`. It `fetch`es `selmo-i18n.json` once at
  startup (served statically by the front door like the other assets).
- **Default language** from `navigator.language`; a **switcher** in the settings
  panel; the choice **persisted in `localStorage`** (the profile is already stored
  there, so the pattern exists).
- **Interpolation** is required, not optional — several strings are dynamic
  (`reasoning complete (96 tok)`, chunk counts, `{n} results`). `t()` takes a
  vars object: `t('web.results', {n:5})`.
- **Static markup** in `chat.html`: give each element a `data-i18n="key"` (and
  `data-i18n-title` / `data-i18n-placeholder` for attributes), then one boot sweep
  fills them from the table. That is one attribute per element and one function,
  far cleaner than wrapping every literal.
- **Dynamic strings** in the `.js`: replace the literal with a `t('key')` call.
- **Tray (`selmo_tray.py`)**: a tiny `tr(key)` helper reads the *same*
  `selmo-i18n.json`. Lower priority — a family user rarely opens the tray menu —
  so plan it, don't let it block the browser work.

## 5. How to land it without pain

The real cost is a **one-time mechanical refactor** that touches every hardcoded
string once. `chat.html` is Python-only edits (BUG-META-01), so this is exactly
the kind of large sweep that wants its own checkpoint. Two phases:

1. **Machinery + extraction, English-only.** Build `selmo-i18n.js`, add the
   `data-i18n` attributes and `t()` calls, and inventory every string into the
   table with a proposed key — with the **`en` column only**. The app looks
   byte-identical to today, so the regression test is "nothing changed on
   screen". Land and commit this as its own version bump before any translation.
2. **Add languages as pure data.** Fill the `it` column (and fix the drifted
   Italian strings while doing it), then `fr`, `es`, whatever. From here a new
   language never touches code — it is only new cells in the JSON.

Doing phase 1 alone already **fixes the current English/Italian drift** by forcing
every string through one place, even before a second language ships.

## 6. Edges to keep in mind (not now, just noted)

- **Pluralization**: most of our strings are fine with `{n} x`; if a language ever
  needs true plural rules, `t()` can grow a `count` branch later. Don't build it
  up front.
- **RTL** (Arabic/Hebrew): would need `dir="rtl"` on the root and some CSS
  mirroring. Out of scope until someone actually wants it.
- **String count**: the raw grep is ~1000 but that includes code noise; the real
  set of distinct UI strings is more like 150–250. Manageable in one focused pass.

## 7. Recommendation

Adopt your table, expressed as one `selmo-i18n.json` (key → per-language object),
semantic keys, a `t()`/`data-i18n` mechanism in a new first-loaded script, and the
tray reading the same file. Do the English-only extraction as its own committed
checkpoint first (it also cleans the current drift), then add languages as data.
This keeps model-output language (already handled by the system prompts) strictly
separate from UI chrome (the thing we are actually localizing).
