'use strict';
/* ============================================================================
   selmo-i18n.js  --  UI localization engine (phase 1)
   Loaded FIRST, before every other selmo-*.js, so t() exists everywhere.

   DESIGN / SAFETY CONTRACT
   - The active language defaults to 'en'. In 'en' the engine does NOTHING to
     the DOM on load, so the page renders byte-for-byte as before. Localization
     is dormant until setLang('it') is called (console for now; a visible
     picker comes in phase 2). This is what lets us ship the machinery without
     changing the current experience at all.
   - Only the UI CHROME is localized here (buttons, tooltips, placeholder,
     modal titles). The MODEL's reply language is a separate axis already solved
     by the system prompts ("Reply in the user's language") and is untouched.
   - t(key, vars) is available for future dynamic strings; phase 1 does not yet
     wrap the .js message sites, so nothing in the running app calls it. That
     keeps this file purely additive: even if it failed to load, the app runs.

   ADD A LANGUAGE = data only: add a third key (e.g. 'fr') to each row in I18N.
   Missing cells fall back to English automatically.
   ============================================================================ */

var SELMO_LANG_KEY = 'selmo_lang';
var SELMO_LANG = 'en';
try {
  var _saved = localStorage.getItem(SELMO_LANG_KEY);
  if (_saved) SELMO_LANG = _saved;
} catch (e) {}

// Languages offered by the header picker. Add a row here + a column in I18N to
// ship a new language; nothing else changes.
var SELMO_LANGS = [
  { code: 'en', name: 'English' },
  { code: 'it', name: 'Italiano' }
];

/* ---- Dictionary: key -> { en, it, ... } -------------------------------------
   Semantic dotted keys (NOT the English text), so rewording English never
   breaks other languages. 'en' values mirror the current markup exactly. */
var I18N = {
  // header toolbar
  'nav.new_chat'      : { en: '+ NEW CHAT',                         it: '+ NUOVA CHAT' },
  'nav.export'        : { en: '↓ EXPORT',                      it: '↓ ESPORTA' },
  'toolbar.web'       : { en: 'Web search ON/OFF',                  it: 'Ricerca web ON/OFF' },
  'toolbar.think'     : { en: 'Extended reasoning ON/OFF',          it: 'Ragionamento esteso ON/OFF' },
  'toolbar.history'   : { en: 'History',                            it: 'Cronologia' },
  'toolbar.dashboard' : { en: 'Dashboard',                          it: 'Cruscotto' },
  'toolbar.model'     : { en: 'Click to change model / runtime settings',
                          it: 'Clicca per cambiare modello / impostazioni' },
  'toolbar.profile'   : { en: 'Switch mode (A.N.S.E.L.M.O / Mizan / Custom)',
                          it: 'Cambia modalità (A.N.S.E.L.M.O / Mizan / Custom)' },
  // input row
  'input.file'        : { en: '+ FILE',                             it: '+ FILE' },
  'input.imgocr'      : { en: '+ IMG/OCR',                          it: '+ IMG/OCR' },
  'input.imgocr_t'    : { en: "Image or PDF for the model's vision / OCR",
                          it: 'Immagine o PDF per la vista / OCR del modello' },
  'input.placeholder' : { en: 'Type a message...',                 it: 'Scrivi un messaggio...' },
  'input.send_t'      : { en: 'Generate document',                 it: 'Genera documento' },
  'input.genimg_t'    : { en: 'Generate an image from your prompt - click to choose the mode (text-to-image / img2img)',
                          it: "Genera un'immagine dal tuo prompt - clicca per scegliere la modalita' (text-to-image / img2img)" },
  'input.stop'        : { en: 'STOP',                              it: 'STOP' },
  'input.mic_t'       : { en: 'Voice transcription (Whisper)',     it: 'Trascrizione vocale (Whisper)' },
  'input.vad_t'       : { en: 'Hands-free conversation (VAD) - detects pauses and sends on its own',
                          it: 'Conversazione a mani libere (VAD) - rileva le pause e invia da solo' },
  'input.tts_t'       : { en: 'Read responses aloud (Kokoro TTS)', it: 'Leggi le risposte ad alta voce (Kokoro TTS)' },
  // profile modal
  'profile.title'     : { en: 'PROFILE',                           it: 'PROFILO' },
  'profile.close'     : { en: 'Close',                             it: 'Chiudi' },
  // left sidebar + dashboard panel labels
  'panel.history'     : { en: 'history',                           it: 'cronologia' },
  'panel.power'       : { en: 'system power draw',                 it: 'potenza di sistema' },
  'panel.watthours'   : { en: 'session watt-hours',               it: 'watt-ora sessione' },
  'stat.toksec'       : { en: 'tok/sec',                           it: 'tok/sec' },
  'stat.wh_session'   : { en: 'Wh session',                        it: 'Wh sessione' },
  'stat.wh_total'     : { en: 'Wh total',                          it: 'Wh totali' },
  'stat.session_cost' : { en: 'session cost',                      it: 'costo sessione' },
  'stat.total_cost'   : { en: 'total cost',                        it: 'costo totale' },
  'stat.eur_kwh'      : { en: 'euro/kWh',                          it: 'euro/kWh' },
  'stat.tokens_gen'   : { en: 'tokens generated',                  it: 'token generati' },
  // conversation + footer
  'welcome.line1'     : { en: 'New conversation.',                 it: 'Nuova conversazione.' },
  'footer.privacy'    : { en: 'Only web searches transmitted',     it: 'Solo le ricerche web vengono trasmesse' }
};

/* ---- Bindings: which element gets which key, and via which property ----------
   prop: 'text' -> textContent (only for elements with NO child markup)
         'title'/'placeholder' -> the matching attribute
   Applied only when the active language is not English. */
var I18N_BIND = [
  { sel: '#new-chat',        prop: 'text',        key: 'nav.new_chat' },
  { sel: '#export-chat',     prop: 'text',        key: 'nav.export' },
  { sel: '#web-btn',         prop: 'title',       key: 'toolbar.web' },
  { sel: '#think-btn',       prop: 'title',       key: 'toolbar.think' },
  { sel: '#mob-nav-btn',     prop: 'title',       key: 'toolbar.history' },
  { sel: '#mob-dash-btn',    prop: 'title',       key: 'toolbar.dashboard' },
  { sel: '#model-btn',       prop: 'title',       key: 'toolbar.model' },
  { sel: '#wm',              prop: 'title',       key: 'toolbar.profile' },
  { sel: '#upload-btn',      prop: 'text',        key: 'input.file' },
  { sel: '#upload-img-btn',  prop: 'text',        key: 'input.imgocr' },
  { sel: '#upload-img-btn',  prop: 'title',       key: 'input.imgocr_t' },
  { sel: '#input',           prop: 'placeholder', key: 'input.placeholder' },
  { sel: '#send',            prop: 'title',       key: 'input.send_t' },
  { sel: '#gen-img-btn',     prop: 'title',       key: 'input.genimg_t' },
  { sel: '#stop',            prop: 'text',        key: 'input.stop' },
  { sel: '#mic-btn',         prop: 'title',       key: 'input.mic_t' },
  { sel: '#vad-btn',         prop: 'title',       key: 'input.vad_t' },
  { sel: '#tts-btn',         prop: 'title',       key: 'input.tts_t' },
  { sel: '#profile-modal .pm-title', prop: 'text',  key: 'profile.title' },
  { sel: '#profile-modal .pm-x',     prop: 'title', key: 'profile.close' }
];

/* ---- t(): look up a key in the active language; interpolate {vars} ---------- */
function t(key, vars) {
  var row = I18N[key];
  var s = row ? (row[SELMO_LANG] || row.en) : key;
  if (s == null) s = key;
  if (vars) {
    s = s.replace(/\{(\w+)\}/g, function (m, name) {
      return (vars[name] != null) ? vars[name] : m;
    });
  }
  return s;
}

/* ---- applyI18n(): sweep the bindings for the active language ----------------
   Defensive: a missing element or key is skipped, never blanks anything. */
function applyI18n() {
  try {
    // 1) explicit selector bindings (header / input / profile chrome)
    for (var i = 0; i < I18N_BIND.length; i++) {
      var b = I18N_BIND[i];
      var el;
      try { el = document.querySelector(b.sel); } catch (e) { el = null; }
      if (!el) continue;
      var val = t(b.key);
      if (val == null) continue;
      if (b.prop === 'text') el.textContent = val;
      else el.setAttribute(b.prop, val);
    }
    // 2) generic sweep for elements marked directly in the markup. Only leaf
    //    text elements carry data-i18n (no child markup), so textContent is safe.
    _sweepAttr('[data-i18n]',       'data-i18n',       'text');
    _sweepAttr('[data-i18n-title]', 'data-i18n-title', 'title');
    _sweepAttr('[data-i18n-ph]',    'data-i18n-ph',    'placeholder');
  } catch (e) {}
}

function _sweepAttr(selector, attr, prop) {
  var list;
  try { list = document.querySelectorAll(selector); } catch (e) { return; }
  for (var i = 0; i < list.length; i++) {
    var el = list[i];
    var val = t(el.getAttribute(attr));
    if (val == null) continue;
    if (prop === 'text') el.textContent = val;
    else el.setAttribute(prop, val);
  }
}

/* ---- setLang(): change language, persist, re-apply ------------------------- */
function setLang(code) {
  SELMO_LANG = code || 'en';
  try { localStorage.setItem(SELMO_LANG_KEY, SELMO_LANG); } catch (e) {}
  // Applied unconditionally here (even for 'en') so switching BACK to English
  // restores the English chrome from the dictionary.
  applyI18n();
  return SELMO_LANG;
}

/* ---- Header language picker (globe button + dropdown) -----------------------
   Added to the header toolbar; remembers the choice across sessions via the
   same localStorage key setLang() writes. */
function _openLangPopup() {
  var ov = document.getElementById('lang-popup');
  if (ov) { ov.remove(); return; }          // second click closes it
  ov = document.createElement('div');
  ov.id = 'lang-popup';
  ov.style.cssText = 'position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);'
    + 'display:flex;align-items:center;justify-content:center;padding:16px';
  ov.onclick = function (e) { if (e.target === ov) ov.remove(); };   // click outside closes
  var card = document.createElement('div');
  card.style.cssText = 'background:var(--panel,#12161c);color:var(--white,#dfe8f0);'
    + 'border:1px solid var(--steel,#2a3340);border-radius:10px;max-width:320px;width:100%;'
    + 'padding:20px;font-family:inherit;box-shadow:0 8px 40px rgba(0,0,0,.5)';
  var title = document.createElement('div');
  title.textContent = '🌐 Language';
  title.style.cssText = 'font-size:16px;font-weight:bold;margin-bottom:14px';
  card.appendChild(title);
  for (var i = 0; i < SELMO_LANGS.length; i++) {
    (function (lg) {
      var b = document.createElement('button');
      b.textContent = (lg.code === SELMO_LANG ? '✓  ' : '    ') + lg.name;
      b.style.cssText = 'display:block;width:100%;text-align:left;background:none;'
        + 'border:1px solid var(--steel,#2a3340);color:inherit;border-radius:6px;'
        + 'padding:11px 12px;margin-bottom:8px;cursor:pointer;font-family:inherit;font-size:15px';
      b.onmouseover = function () { b.style.borderColor = 'var(--cyan,#7fdfff)'; };
      b.onmouseout  = function () { b.style.borderColor = 'var(--steel,#2a3340)'; };
      b.onclick = function () { setLang(lg.code); ov.remove(); };   // apply + persist + close
      card.appendChild(b);
    })(SELMO_LANGS[i]);
  }
  ov.appendChild(card);
  document.body.appendChild(ov);
}
function _i18nPicker() {
  try {
    if (document.getElementById('lang-btn')) return;
    var box = document.querySelector('header .h-left');
    if (!box) return;
    var btn = document.createElement('button');
    btn.id = 'lang-btn';
    btn.title = 'Language';
    btn.style.cssText = 'font-family:var(--mono);font-size:13px;letter-spacing:.07em;'
      + 'padding:7px 12px;border-radius:var(--radius-xs);cursor:pointer;'
      + 'transition:all .18s var(--ease);white-space:nowrap;flex-shrink:0;'
      + 'background:rgba(255,255,255,.025);border:1px solid var(--steel);color:var(--dim);';
    btn.onmouseover = function () { btn.style.borderColor = 'var(--cyan)'; btn.style.color = 'var(--cyan)'; };
    btn.onmouseout  = function () { btn.style.borderColor = 'var(--steel)'; btn.style.color = 'var(--dim)'; };
    btn.textContent = '🌐';   // globe
    var menu = document.createElement('div');
    menu.id = 'lang-menu';
    menu.style.cssText = 'display:none;position:absolute;top:100%;left:0;z-index:100000;'
      + 'margin-top:4px;background:var(--panel,#12161c);border:1px solid var(--steel,#2a3340);'
      + 'border-radius:6px;padding:4px;min-width:130px;box-shadow:0 6px 24px rgba(0,0,0,.5)';
    function rebuild() {
      menu.innerHTML = '';
      for (var i = 0; i < SELMO_LANGS.length; i++) {
        (function (lg) {
          var item = document.createElement('button');
          item.textContent = (lg.code === SELMO_LANG ? '✓ ' : '  ') + lg.name;
          item.style.cssText = 'display:block;width:100%;text-align:left;background:none;border:none;'
            + 'color:inherit;padding:5px 8px;cursor:pointer;font-family:inherit;font-size:13px;border-radius:4px';
          item.onmouseover = function () { item.style.background = 'rgba(127,223,255,.10)'; };
          item.onmouseout  = function () { item.style.background = 'none'; };
          item.onclick = function (e) {
            e.stopPropagation();
            setLang(lg.code);          // applies + persists to localStorage
            menu.style.display = 'none';
            rebuild();                 // refresh the checkmark
          };
          menu.appendChild(item);
        })(SELMO_LANGS[i]);
      }
    }
    btn.onclick = function (e) { e.stopPropagation(); _openLangPopup(); };
    box.appendChild(btn);
  } catch (e) {}
}

/* ---- Startup: build the picker always; apply translations only if a
   non-English language is active (in 'en' the DOM chrome is left untouched
   apart from the new picker button the user asked for). -------------------- */
function _i18nInit() {
  _i18nPicker();
  if (SELMO_LANG !== 'en') applyI18n();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', _i18nInit);
} else {
  _i18nInit();
}
