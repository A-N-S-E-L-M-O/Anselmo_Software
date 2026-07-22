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
  { code: 'it', name: 'Italiano' },
  { code: 'fr', name: 'Français' }
];

/* ---- Dictionary: key -> { en, it, ... } -------------------------------------
   Semantic dotted keys (NOT the English text), so rewording English never
   breaks other languages. 'en' values mirror the current markup exactly. */
/* ---- Dictionary: key -> { en, it, fr } ------------------------------------- */
var I18N = {
  // header toolbar
  'nav.new_chat'      : { en: 'New chat',            it: 'Nuova chat',         fr: 'Nouveau chat' },
  'nav.export'        : { en: 'Export',              it: 'Esporta',            fr: 'Exporter' },
  'toolbar.web'       : { en: 'Web search ON/OFF',   it: 'Ricerca web ON/OFF', fr: 'Recherche web ON/OFF' },
  'toolbar.think'     : { en: 'Extended reasoning ON/OFF', it: 'Ragionamento esteso ON/OFF', fr: 'Raisonnement étendu ON/OFF' },
  'toolbar.history'   : { en: 'History',             it: 'Cronologia',         fr: 'Historique' },
  'toolbar.dashboard' : { en: 'Dashboard',           it: 'Cruscotto',          fr: 'Tableau de bord' },
  'toolbar.model'     : { en: 'Click to change model / runtime settings', it: 'Clicca per cambiare modello / impostazioni', fr: 'Cliquez pour changer le modèle / les paramètres d\'exécution' },
  'toolbar.profile'   : { en: 'Switch mode (A.N.S.E.L.M.O / Mizan / Custom)', it: 'Cambia modalità (A.N.S.E.L.M.O / Mizan / Custom)', fr: 'Changer de mode (A.N.S.E.L.M.O / Mizan / Personnalisé)' },
  // input row
  'input.file'        : { en: '+ FILE',              it: '+ FILE',             fr: '+ FICHIER' },
  'input.imgocr'      : { en: '+ IMG/OCR',           it: '+ IMG/OCR',          fr: '+ IMG/OCR' },
  'input.imgocr_t'    : { en: "Image or PDF for the model's vision / OCR", it: 'Immagine o PDF per la vista / OCR del modello', fr: "Image ou PDF pour la vision/OCR du modèle" },
  'input.placeholder' : { en: 'Type a message...',   it: 'Scrivi un messaggio...', fr: 'Tapez un message...' },
  'input.send_t'      : { en: 'Generate document',   it: 'Genera documento',   fr: 'Générer le document' },
  'input.genimg_t'    : { en: 'Generate an image from your prompt - click to choose the mode (text-to-image / img2img)', it: "Genera un'immagine dal tuo prompt - clicca per scegliere la modalita' (text-to-image / img2img)", fr: "Générer une image à partir de votre prompt - cliquez pour choisir le mode (texte-vers-image / image-à-image)" },
  'input.stop'        : { en: 'STOP',                it: 'STOP',               fr: 'ARRÊTER' },
  'input.mic_t'       : { en: 'Voice transcription (Whisper)', it: 'Trascrizione vocale (Whisper)', fr: "Transcription vocale (Whisper)" },
  'input.vad_t'       : { en: 'Hands-free conversation (VAD) - detects pauses and sends on its own', it: 'Conversazione a mani libere (VAD) - rileva le pause e invia da solo', fr: "Conversation mains libres (VAD) - détecte les pauses et envoie automatiquement" },
  'input.tts_t'       : { en: 'Read responses aloud (Kokoro TTS)', it: 'Leggi le risposte ad alta voce (Kokoro TTS)', fr: "Lire les réponses à voix haute (Kokoro TTS)" },
  // profile modal
  'profile.title'     : { en: 'PROFILE',             it: 'PROFILO',            fr: 'PROFIL' },
  'profile.close'     : { en: 'Close',               it: 'Chiudi',             fr: 'Fermer' },
  // left sidebar + dashboard panel labels
  'panel.history'     : { en: 'history',             it: 'cronologia',         fr: 'historique' },
  'panel.power'       : { en: 'system power draw',   it: 'potenza di sistema', fr: 'consommation système' },
  'panel.watthours'   : { en: 'session watt-hours',  it: 'watt-ora sessione',  fr: 'wattheures de session' },
  'stat.toksec'       : { en: 'tok/sec',             it: 'tok/sec',            fr: 'tok/sec' },
  'stat.wh_session'   : { en: 'Wh session',          it: 'Wh sessione',        fr: 'Wh session' },
  'stat.wh_total'     : { en: 'kWh total',           it: 'kWh totali',         fr: 'kWh total' },
  'stat.session_cost' : { en: 'session cost',        it: 'costo sessione',     fr: 'coût de session' },
  'stat.total_cost'   : { en: 'total cost',          it: 'costo totale',       fr: 'coût total' },
  'stat.eur_kwh'      : { en: 'euro/kWh',            it: 'euro/kWh',           fr: '€/kWh' },
  'stat.tokens_gen'   : { en: 'tokens generated',    it: 'token generati',     fr: 'tokens générés' },
  // conversation + footer
  'welcome.line1'     : { en: 'New conversation.',   it: 'Nuova conversazione.', fr: 'Nouvelle conversation.' },
  'footer.privacy'    : { en: 'Only web searches transmitted', it: 'Solo le ricerche web vengono trasmesse', fr: 'Seules les recherches Web sont transmises' },
  // RAG mode: corpus bar + folder/format picker + status messages
  'rag.pick.title'    : { en: 'RAG - folder, subfolders and formats', it: 'RAG - cartella, sottocartelle e formati', fr: 'RAG - dossier, sous-dossiers et formats' },
  'rag.pick.root'     : { en: 'Root folder',         it: 'Cartella radice',    fr: 'Dossier racine' },
  'rag.pick.browse'   : { en: 'Browse',              it: 'Sfoglia',            fr: 'Parcourir' },
  'rag.pick.cancel'   : { en: 'Cancel',              it: 'Annulla',            fr: 'Annuler' },
  'rag.pick.index'    : { en: 'Index',               it: 'Indicizza',          fr: ' indexer' }, // "Index" as verb is tricky; often kept or "Créer l'index". Let's use "indexer" for action.
  'rag.pick.hint'     : { en: 'Enter a folder and press Browse.', it: 'Inserisci una cartella e premi Sfoglia.', fr: 'Entrez un dossier et cliquez sur Parcourir.' },
  'rag.pick.reading'  : { en: 'Reading folder...',   it: 'Leggo la cartella...', fr: "Lecture du dossier..." },
  'rag.pick.enterpath': { en: 'Enter a folder path.',it: 'Inserisci un percorso cartella.', fr: 'Entrez le chemin d\'un dossier.' },
  'rag.pick.invalid'  : { en: 'Invalid folder',      it: 'Cartella non valida', fr: 'Dossier invalide' },
  'picker.local_only' : { en: 'Folder selection is only available on the PC itself, not from a phone or another device.', it: 'La selezione della cartella è disponibile solo sul PC, non da telefono o altri dispositivi.', fr: "La sélection de dossier n'est disponible que sur le PC lui-même, pas depuis un téléphone ou un autre appareil." },
  'rag.pick.subs'     : { en: 'Subfolders to include', it: 'Sottocartelle da includere', fr: 'Sous-dossiers à inclure' },
  'rag.pick.formats'  : { en: 'File formats',        it: 'Formati file',       fr: "Formats de fichiers" },
  'rag.pick.nosubs'   : { en: 'No subfolders.',      it: 'Nessuna sottocartella.', fr: 'Aucun sous-dossier.' },
  'rag.pick.nofmt'    : { en: 'No indexable formats found.', it: 'Nessun formato indicizzabile trovato.', fr: "Aucun format indexable trouvé." },
  'rag.bar.choose'    : { en: 'click to choose the folder to index', it: 'clicca per scegliere la cartella da indicizzare', fr: 'cliquez pour choisir le dossier à indexer' },
  'rag.bar.change'    : { en: 'click to change',     it: 'clicca per cambiare', fr: 'cliquez pour changer' },
  'rag.bar.noindex'   : { en: 'no index',            it: 'nessun indice',      fr: 'aucun index' },
  'rag.chunks'        : { en: '{n} chunks',          it: '{n} chunk',          fr: '{n} chunks' }, // "chunks" is standard in RAG context, even in FR.
  'rag.notactive'     : { en: 'RAG bridge not active - start selmo_rag.py.', it: 'RAG bridge non attivo - avvia selmo_rag.py.', fr: 'Pont RAG inactif - lancez selmo_rag.py.' },
  'rag.embedderoff'   : { en: 'Embedder not reachable - start a llama.cpp --embeddings server (or set embed_autostart). RAG needs it to index and search.', it: "Embedder non raggiungibile - avvia un server llama.cpp --embeddings (o imposta embed_autostart). Serve per indicizzare e cercare.", fr: 'Embedder inaccessible - lancez un serveur llama.cpp --embeddings (ou définissez embed_autostart). Le RAG en a besoin pour indexer et rechercher.' },
  'rag.indexing'      : { en: 'Indexing {dir}... this can take a while.', it: "Indicizzo {dir}... puo' volerci un po'.", fr: "Indexation de {dir}... cela peut prendre un moment." },
  'rag.indexed'       : { en: 'Indexed {files} files -> {chunks} chunks.', it: 'Indicizzati {files} file -> {chunks} chunk.', fr: '{files} fichiers indexés -> {chunks} chunks.' },
  'rag.failed'        : { en: 'Indexing failed: {err}', it: 'Indicizzazione fallita: {err}', fr: "Échec de l'indexation : {err}" },
  'rag.error'         : { en: 'Error: {msg}',        it: 'Errore: {msg}',      fr: 'Erreur : {msg}' },
  'rag.prog.scanning' : { en: 'Scanning... {files} files', it: 'Scansione... {files} file', fr: 'Analyse... {files} fichiers' },
  'rag.prog.embedding': { en: 'Embedding {done}/{total} chunks ({pct}%)', it: 'Embedding {done}/{total} chunk ({pct}%)', fr: 'Embedding {done}/{total} chunks ({pct}%)' },
  'rag.prog.saving'   : { en: 'Saving index...', it: 'Salvo indice...', fr: "Sauvegarde de l'index..." },
  'ml.loading'        : { en: 'preparing the wash cycle', it: 'preparando il ciclo di lavaggio', fr: 'préparation du cycle de lavage' },
  // agent mode
  'agent.toggle_t'                     : { en: 'Agent ON/OFF',                        it: 'Agente ON/OFF',                                              fr: 'Agent ON/OFF' },
  'agent.step'                         : { en: 'Step {n}/{max}',                       it: 'Passo {n}/{max}',                                            fr: 'Étape {n}/{max}' },
  'agent.tool.list_dir'                : { en: 'listing {dir}',                        it: 'elenco {dir}',                                               fr: 'liste {dir}' },
  'agent.tool.read_file'               : { en: 'reading {path}',                       it: 'lettura {path}',                                             fr: 'lecture {path}' },
  'agent.tool.search_text'             : { en: 'grep: {q}',                            it: 'grep: {q}',                                                  fr: 'grep : {q}' },
  'agent.tool.write_file'              : { en: 'writing {path}',                       it: 'scrittura {path}',                                           fr: 'écriture {path}' },
  'agent.tool.web_search'              : { en: 'web search: {q}',                      it: 'ricerca web: {q}',                                           fr: 'recherche web : {q}' },
  'agent.tool.fetch_page'              : { en: 'reading page: {url}',                  it: 'lettura pagina: {url}',                                      fr: 'lecture de la page : {url}' },
  'agent.reasoning'                    : { en: 'reasoning',                            it: 'ragionamento',                                               fr: 'raisonnement' },
  'chat.you'                           : { en: 'you',                                  it: 'tu',                                                         fr: 'toi' },
  'agent.allow_writes'                 : { en: 'Let the agent write in this folder',    it: "Consenti all'agente di scrivere in questa cartella",          fr: "Autoriser l'agent à écrire dans ce dossier" },
  'agent.bar.writes_on'                : { en: 'writable',                              it: 'scrivibile',                                                 fr: 'inscriptible' },
  'agent.tool.rag_search'              : { en: 'RAG search: {q}',                      it: 'Ricerca RAG: {q}',                                           fr: 'Recherche RAG : {q}' },
  'agent.tool.open_url_in_firefox'     : { en: 'opening in Firefox: {url}',            it: 'apro in Firefox: {url}',                                     fr: 'ouverture dans Firefox : {url}' },
  'agent.tool.open_document_libreoffice': { en: 'opening in LibreOffice: {path}',      it: 'apro in LibreOffice: {path}',                                fr: 'ouverture dans LibreOffice : {path}' },
  'agent.tool.compose_email_thunderbird': { en: 'composing email to {to}',             it: 'compongo email a {to}',                                      fr: "rédaction d'un email à {to}" },
  'agent.stopped'                      : { en: 'Agent stopped.',                       it: 'Agente fermato.',                                            fr: 'Agent arrêté.' },
  'agent.max_steps'                    : { en: 'Max steps ({max}) reached.',           it: 'Passi massimi ({max}) raggiunti.',                            fr: "Nombre maximal d'étapes ({max}) atteint." },
  'agent.error'                        : { en: 'Agent error: {msg}',                   it: 'Errore agente: {msg}',                                       fr: "Erreur de l'agent : {msg}" },
  'agent.no_tool_support'              : { en: 'This model does not support tool calling. Load a compatible model with --jinja.', it: 'Questo modello non supporta il tool calling. Carica un modello compatibile con --jinja.', fr: 'Ce modèle ne prend pas en charge les appels d’outils. Chargez un modèle compatible avec --jinja.' },
  'agent.context_full'                 : { en: 'Context window full — stopped here. Ask a shorter follow-up or start a new chat to continue.', it: 'Finestra di contesto piena — mi fermo qui. Fai una domanda più breve o apri una nuova chat per continuare.', fr: 'Fenêtre de contexte pleine — arrêt ici. Posez une question plus courte ou ouvrez une nouvelle discussion pour continuer.' },
  'agent.context_approaching'          : { en: 'Context limit approaching — wrapping up.', it: 'Limite di contesto vicino — concludo.', fr: 'Limite de contexte proche — je conclus.' },
  'agent.finalizing'                   : { en: 'Context nearly full — synthesizing what I have gathered.', it: 'Contesto quasi pieno — sintetizzo quello che ho raccolto.', fr: 'Contexte presque plein — je synthétise ce que j’ai rassemblé.' },
  'agent.server_down'                  : { en: 'Model server unreachable. VRAM may be full — restart llama-server.', it: 'Server modello non raggiungibile. La VRAM potrebbe essere piena — riavvia llama-server.', fr: 'Serveur de modèle inaccessible. La VRAM est peut-être pleine — redémarrez llama-server.' },
  'service.fatal'                      : { en: 'A background service crashed and could not be restarted. Reload Selmo to try again.', it: 'Un servizio in background ha fallito e non è stato possibile riavviarlo. Ricarica Selmo per riprovare.', fr: 'Un service en arrière-plan a planté et n’a pas pu être redémarré. Rechargez Selmo pour réessayer.' },
  'server.notrunning'                  : { en: 'Server not running. Selmo has been closed.', it: 'Server non attivo. Selmo è stato chiuso.', fr: 'Serveur arrêté. Selmo a été fermé.' },
  'agent.bridge_off'                   : { en: 'Agent bridge not running (start selmo_rag.py).', it: 'Bridge agente non attivo (avvia selmo_rag.py).', fr: "Le bridge de l'agent n'est pas actif (lancez selmo_rag.py)." },
  'agent.bar.change'                   : { en: 'change', it: 'cambia', fr: 'changer' },
  'agent.roots_empty'                  : { en: 'No agent roots configured. Add folders in agent settings.', it: 'Nessuna cartella radice configurata. Aggiungine nelle impostazioni agente.', fr: "Aucun dossier racine configuré. Ajoutez des dossiers dans les paramètres de l'agent." },
  'agent.roots_panel'                  : { en: 'Agent folders',                        it: 'Cartelle agente',                                            fr: "Dossiers de l'agent" },
  'agent.roots_label'                  : { en: 'Folders the agent can access:',        it: "Cartelle a cui l'agente può accedere:",                  fr: "Dossiers accessibles par l'agent :" },
  'agent.btn_label'                    : { en: 'Agent',                                it: 'Agente',                                                     fr: 'Agent' },
  'agent.not_capable'                  : { en: "This model can't run agent mode. Switch to an agent-capable model.", it: "Questo modello non può usare la modalità agente. Passa a un modello compatibile.", fr: "Ce modèle ne peut pas exécuter le mode agent. Passez à un modèle compatible." }
};
/* ---- Bindings: which element gets which key, and via which property ----------
   prop: 'text' -> textContent (only for elements with NO child markup)
         'title'/'placeholder' -> the matching attribute
   Applied only when the active language is not English. */
var I18N_BIND = [
  { sel: '#new-chat',        prop: 'title',       key: 'nav.new_chat' },
  { sel: '#export-chat',     prop: 'title',       key: 'nav.export' },
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
  { sel: '#profile-modal .pm-x',     prop: 'title', key: 'profile.close' },
  { sel: '#agent-btn',               prop: 'title',       key: 'agent.toggle_t' },
  { sel: '#agent-step',              prop: 'textContent', key: 'agent.step' }
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
    // The #agent-btn tooltip depends on the model's capability, not just the
    // language, so re-assert it after the static sweep set it to agent.toggle_t.
    if (typeof applyAgentCap === 'function') applyAgentCap();
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
  var lb = document.getElementById('lang-btn');
  if (lb) lb.textContent = (SELMO_LANG || 'en').toUpperCase();   // keep the header code in sync
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
    btn.style.cssText = 'font-family:var(--mono);font-size:13px;line-height:1;letter-spacing:.07em;'
      + 'padding:6px 11px;border-radius:var(--radius-xs);cursor:pointer;'
      + 'transition:all .18s var(--ease);white-space:nowrap;flex-shrink:0;'
      + 'background:rgba(255,255,255,.025);border:1px solid var(--steel);color:var(--dim);';
    btn.onmouseover = function () { btn.style.borderColor = 'var(--cyan)'; btn.style.color = 'var(--cyan)'; };
    btn.onmouseout  = function () { btn.style.borderColor = 'var(--steel)'; btn.style.color = 'var(--dim)'; };
    btn.textContent = (SELMO_LANG || 'en').toUpperCase();   // 2-letter code of the current language
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
