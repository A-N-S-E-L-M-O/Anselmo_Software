// selmo-agent.js — agentic loop module
// Pattern: pure function declarations, no self-executing code, no globals.
// Loaded before selmo-boot.js which sets up IS_AGENT_ON and event wiring.

const AGENT_CONFIG_URL = '/proxy/8088/agent/config';

async function loadAgentConfig() {
  const r = await fetch(AGENT_CONFIG_URL);
  if (!r.ok) throw new Error('agent/config ' + r.status);
  return r.json();
}

function buildToolSchemas(cfg) {
  // Combine builtin + custom (filtered by agent_tools_enabled + enabled flag)
  const enabled = new Set(cfg.agent_tools_enabled || []);
  const allowWrites = !!cfg.agent_allow_writes;
  const webOn = (typeof IS_WEB_ON !== 'undefined' && IS_WEB_ON);
  const builtins = (cfg.agent_builtin_tools || [])
    // write_file needs writes enabled for the folder; web_search needs WEB toggled
    // on — without it the agent has no way out of the local machine.
    .filter(t => enabled.has(t.name)
      && (t.name !== 'write_file' || allowWrites)
      && (t.name !== 'web_search' || webOn));
  const customs  = (cfg.agent_custom_tools  || []).filter(t => enabled.has(t.name) && t.enabled !== false);
  return [...builtins, ...customs].map(tool => ({
    type: 'function',
    function: {
      name: tool.name,
      // The model needs a real sentence, not the short UI trace label.
      description: tool.desc || t(tool.label_key),
      parameters: tool.schema
    },
    _def: tool   // keep the full def for execTool
  }));
}

// Documents whose text lives in a binary container: extract them in the browser
// with the same engines the + FILE button uses (PDF.js / JSZip / SheetJS), so the
// agent inherits the proven pipeline and needs no server-side PDF/office library.
async function agentExtractBinary(path, ext) {
  const r = await fetch('/proxy/8088/fs/raw?' + new URLSearchParams({ path }),
                        { signal: AbortSignal.timeout(30000) });
  if (!r.ok) {
    let msg = 'fs/raw ' + r.status;
    try { const j = await r.json(); if (j && j.error) msg = j.error; } catch (e) {}
    throw new Error(msg);
  }
  const blob = await r.blob();   // extractors only need .arrayBuffer(), which Blob has
  switch (ext) {
    case 'pdf':  return await extractPdf(blob);
    case 'docx': return await extractDocx(blob);
    case 'odt':  return await extractOdt(blob);
    case 'xlsx':
    case 'xls':
    case 'ods':  return await extractSpreadsheet(blob);
    case 'pptx': return await extractPptx(blob);
    case 'odp':  return await extractOdp(blob);
    default: throw new Error('unsupported binary type: ' + ext);
  }
}

// System prompt for AGENT mode: makes the folder-access contract explicit so the
// model actually uses the tools instead of inventing restrictions. Notes about
// write / web are added only when those are enabled this turn.
function agentSystemPrompt(cfg) {
  const canWrite = !!(cfg && cfg.agent_allow_writes);
  const canWeb   = (typeof IS_WEB_ON !== 'undefined' && IS_WEB_ON);
  let s =
    'You are operating in AGENT mode with direct tool access to a folder on the user\'s computer. ' +
    'You have FULL read access to EVERY file inside the allowed folder — there is NO "only specified files" restriction, and files you have listed are readable. ' +
    'To read a file, call read_file with its path relative to the folder (e.g. "index.html"); for a file in a subfolder use "sub/name.ext".\n\n' +
    'Rules:\n' +
    '- ALWAYS use the tools to check before answering. NEVER claim you cannot access, read or find a file without first calling read_file (or list_dir/search_text) on it. NEVER invent access restrictions.\n' +
    '- Do not ask the user for anything you can obtain yourself by listing, reading or searching the folder.\n' +
    '- Work concisely: chain the tools you need, then give the result.';
  if (canWrite) s += '\n- You can create or overwrite files in the folder with write_file (send the COMPLETE file content, not a diff).';
  if (canWeb)   s += '\n- You can search the live web with web_search for external or current information.';
  s += '\n\nReply in the user\'s language.';
  return s;
}

async function execTool(toolDef, args) {
  const maxOut = window._agentCfg?.agent_max_tool_output ?? 16384;

  // read_file on a binary document → browser-side extraction (see above).
  if (toolDef.name === 'read_file' && args && typeof args.path === 'string') {
    const ext = (args.path.split('.').pop() || '').toLowerCase();
    if (['pdf','docx','odt','xlsx','xls','ods','pptx','odp'].indexOf(ext) !== -1) {
      try {
        const text = await agentExtractBinary(args.path, ext);
        if (!text || !text.trim()) {
          return JSON.stringify({ path: args.path, text: '',
            note: 'No extractable text (the document may be scanned/image-only).' });
        }
        return JSON.stringify({ path: args.path, text: text.slice(0, maxOut),
          truncated: text.length > maxOut });
      } catch (e) {
        return JSON.stringify({ error: 'extraction failed: ' + (e.message || String(e)) });
      }
    }
  }

  let url = toolDef.endpoint;
  const opts = { signal: AbortSignal.timeout(30000) };
  if ((toolDef.method || 'GET').toUpperCase() === 'GET') {
    url += '?' + new URLSearchParams(args);
  } else {
    opts.method = 'POST';
    opts.headers = { 'Content-Type': 'application/json' };
    // Server (/agent/tool/run) reads payload.name — must match.
    opts.body = JSON.stringify({ name: toolDef.name, args });
  }
  const r = await fetch(url, opts);
  const text = await r.text();
  // read_file sizes itself server-side (a line range is honoured in full; only a
  // range-less read is capped), so don't re-clip it here — clipping would corrupt
  // the JSON and drop lines the model explicitly asked for. Other tools keep the
  // safety cap.
  if (toolDef.name === 'read_file') return text;
  return text.slice(0, maxOut);
}

function renderAgentTrace(toolName, args, stepN, stepMax) {
  // Find toolDef in cached schemas
  const toolDef = (window._agentSchemas || []).find(s => s.function.name === toolName)?._def || {};
  const icon = toolDef.icon || '⚙';
  const label = t('agent.tool.' + toolName, args) || (toolName + ' ' + JSON.stringify(args));
  const stepLabel = t('agent.step', { n: stepN, max: stepMax });
  const div = document.createElement('div');
  div.className = 'agent-trace';
  div.setAttribute('aria-label', stepLabel);
  div.innerHTML = '<span class="agent-trace-icon">' + icon + '</span><span class="agent-trace-label">' + escHtml(label) + '</span><span class="agent-trace-step">' + escHtml(stepLabel) + '</span>';
  return div;
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// A collapsed reasoning panel for one agent step (THINK on). Reuses the normal
// think-panel CSS; static (one-shot text), unlike the streaming makeThinkPanel.
function agentReasonPanel(text) {
  const panel = document.createElement('div'); panel.className = 'think-panel collapsed';
  const toggle = document.createElement('div'); toggle.className = 'think-toggle';
  const arrow = document.createElement('span'); arrow.textContent = '▶';
  const label = document.createElement('span'); label.textContent = '💭 ' + t('agent.reasoning');
  toggle.appendChild(arrow); toggle.appendChild(label);
  const body = document.createElement('div'); body.className = 'think-body'; body.textContent = text;
  panel.appendChild(toggle); panel.appendChild(body);
  let expanded = false;
  toggle.addEventListener('click', () => {
    expanded = !expanded;
    panel.classList.toggle('collapsed', !expanded);
    arrow.textContent = expanded ? '▼' : '▶';
  });
  return panel;
}

// Estimate token count of messages (~4 chars per token). Used by the context
// guard to stop the agent loop before an OOM / context-overflow crash.
function _agentEstimateTokens(msgs) {
  let chars = 0;
  for (const m of msgs) {
    if (typeof m.content === 'string') chars += m.content.length;
    else if (Array.isArray(m.content)) {
      for (const c of m.content) { if (typeof c.text === 'string') chars += c.text.length; }
    }
    if (m.tool_calls) chars += JSON.stringify(m.tool_calls).length;
    if (typeof m.name === 'string') chars += m.name.length;
  }
  return Math.ceil(chars / 4);
}

async function agentLoop(userMsg, chatHistory, targetDiv, cfg) {
  const schemas = buildToolSchemas(cfg);
  window._agentSchemas = schemas;
  window._agentCfg = cfg;

  const maxSteps = cfg.agent_max_steps ?? 50;
  // No wall-clock timeout: local generation takes as long as it takes, and the
  // user controls it with the Stop button, which aborts the in-flight call via the
  // shared abort controller. maxSteps stays only as a runaway guard.

  // Build messages, with an AGENT-mode system prompt prepended. The plain chat
  // system prompt does not tell the model it has real folder access, so weak /
  // instruct models confabulate restrictions ("only specified files are
  // accessible") and refuse to call read_file. This makes the contract explicit.
  const baseMessages = apiMessages(chatHistory, userMsg);
  const agentSys = agentSystemPrompt(cfg);
  const messages = (baseMessages[0] && baseMessages[0].role === 'system')
    ? [{ role: 'system', content: agentSys + '\n\n' + (baseMessages[0].content || '') }, ...baseMessages.slice(1)]
    : [{ role: 'system', content: agentSys }, ...baseMessages];

  const stepEl = document.getElementById('agent-step');
  let step = 0;
  let lastContent = '';   // keep last assistant text so a timeout still shows something

  const toolMap = Object.fromEntries(schemas.map(s => [s.function.name, s._def]));

  // Intermediate history (tool turns) — not persisted to session
  const toolHistory = [];

  if (stepEl) stepEl.style.display = 'inline-block';

  try {
    while (step < maxSteps) {
      if (!gen) break;   // gen is the global abort flag set by abort()

      step++;
      if (stepEl) stepEl.textContent = t('agent.step', { n: step, max: maxSteps });

      // Context guard: if accumulated messages+toolHistory exceed 50% of N_CTX,
      // wrap up now rather than risk a VRAM OOM crash on the next generation call.
      const _nCtx = (typeof N_CTX !== 'undefined' && N_CTX > 0) ? N_CTX : 32768;
      if (_agentEstimateTokens([...messages, ...toolHistory]) > _nCtx * 0.5) {
        const _warnEl = document.createElement('div');
        _warnEl.className = 'agent-trace';
        _warnEl.innerHTML = '<span class="agent-trace-icon">⚠️</span>'
          + '<span class="agent-trace-label">' + escHtml(t('agent.context_approaching')) + '</span>';
        targetDiv.appendChild(_warnEl);
        if (typeof scrollBot === 'function') scrollBot();
        return lastContent
          ? lastContent + '\n\n_' + t('agent.context_approaching') + '_'
          : t('agent.context_approaching');
      }

      // thinkKwargs() adds chat_template_kwargs.enable_thinking for kwarg models
      // (Qwen3) so the THINK button controls the agent's reasoning too. Instr models
      // already carry the reasoning instruction via the system prompt in messages.
      const body = Object.assign({
        model: (typeof MODEL_FULL!=='undefined'?MODEL_FULL:'local'),
        messages: [...messages, ...toolHistory],
        tools: schemas.map(({ type, function: fn }) => ({ type, function: fn })),
        tool_choice: 'auto',
        stream: false,
        temperature: 0.1
      }, (typeof thinkKwargs === 'function' ? thinkKwargs() : {}));

      let r;
      try {
        r = await fetch('/proxy/8089/v1/chat/completions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: (typeof abort !== 'undefined' && abort) ? abort.signal : undefined
        });
      } catch (e) {
        // Stop button aborted the in-flight generation — end cleanly, keep partial text.
        if (e && (e.name === 'AbortError' || !gen)) return lastContent || t('agent.stopped');
        // fetch() throws TypeError on network failure (server down, VRAM OOM crash, etc.).
        if (e && e.name === 'TypeError') {
          const _sd = t('agent.server_down');
          return lastContent ? lastContent + '\n\n_' + _sd + '_' : _sd;
        }
        throw e;
      }
      if (!r.ok) {
        const detail = await r.text().catch(() => '');
        // Context overflow FIRST — it also comes back as HTTP 400, so without this
        // it was misreported as "no tool support". Surface it honestly and keep any
        // partial text. (This is the hook we'll later use for context compaction.)
        if (/exceed|context size|n_ctx|kv cache|larger than the context|slot with enough/i.test(detail)) {
          return lastContent
            ? (lastContent + '\n\n_' + t('agent.context_full') + '_')
            : t('agent.context_full');
        }
        // The most common remaining cause is a model/server without tool support
        // (no --jinja, or a chat template that declares no tools).
        if (r.status === 400 || r.status === 500 || /tool|jinja|template/i.test(detail)) {
          return t('agent.no_tool_support');
        }
        throw new Error('llama ' + r.status);
      }
      const data = await r.json();
      const choice = data.choices?.[0];
      if (!choice) throw new Error('no choices');

      const msg = choice.message;
      // Show the step's reasoning (THINK on) as a collapsed panel. It stays
      // ephemeral: only content + tool_calls are pushed back into history.
      if (msg.reasoning_content && msg.reasoning_content.trim()) {
        targetDiv.appendChild(agentReasonPanel(msg.reasoning_content.trim()));
        if (typeof scrollBot === 'function') scrollBot();
      }
      if (msg.content) lastContent = msg.content;

      // No tool calls? Final answer.
      if (!msg.tool_calls?.length) {
        return msg.content || '';
      }

      // Push assistant turn with tool_calls into history
      toolHistory.push({ role: 'assistant', content: msg.content || null, tool_calls: msg.tool_calls });

      // Execute each tool call
      for (const call of msg.tool_calls) {
        const toolName = call.function.name;
        let args;
        try { args = JSON.parse(call.function.arguments || '{}'); }
        catch (e) { args = {}; }
        const toolDef = toolMap[toolName];

        // Render trace in UI (persists in the transcript)
        const traceEl = renderAgentTrace(toolName, args, step, maxSteps);
        targetDiv.appendChild(traceEl);
        if (typeof scrollBot === 'function') scrollBot();

        let result;
        try {
          result = toolDef ? await execTool(toolDef, args) : JSON.stringify({ error: 'unknown tool: ' + toolName });
        } catch (e) {
          result = JSON.stringify({ error: String(e) });
        }

        toolHistory.push({
          role: 'tool',
          tool_call_id: call.id,
          name: toolName,
          content: result
        });
      }
    }
  } finally {
    if (stepEl) { stepEl.style.display = 'none'; stepEl.textContent = ''; }
  }

  // Stopped, timed out, or hit the step cap — surface any partial text.
  const reason = t(step >= maxSteps ? 'agent.max_steps' : 'agent.stopped', { max: maxSteps });
  return lastContent ? (lastContent + '\n\n_' + reason + '_') : reason;
}

// Grey / enable the AGENT toggle from the model's capability flag (AGENT_CAPABLE,
// read from selmo-config.json's `agent` key). Agent mode is an advanced feature:
// it only behaves with a collaudato tool-calling model (Qwen3.6-35B-A3B via the
// ini agent=true flag), so on every other model the button stays visible but
// greyed, with a localized tooltip — same pattern as the THINK button. Called
// from the config fetch (selmo-boot.js) and after each language switch (applyI18n).
function applyAgentCap() {
  const btn = document.getElementById('agent-btn');
  if (!btn) return;
  let cap = false;
  try { cap = !!AGENT_CAPABLE; } catch (_) { cap = false; }
  const tip = (k) => (typeof t === 'function' ? t(k) : k);
  if (!cap) {
    if (typeof IS_AGENT_ON !== 'undefined' && IS_AGENT_ON) {
      IS_AGENT_ON = false;
      if (typeof updateAgentRootsBar === 'function') updateAgentRootsBar();
    }
    btn.classList.remove('on');
    btn.setAttribute('aria-disabled', 'true');
    btn.setAttribute('aria-pressed', 'false');
    btn.style.opacity = '.35';
    btn.style.cursor = 'not-allowed';
    btn.title = tip('agent.not_capable');
    return;
  }
  btn.removeAttribute('aria-disabled');
  btn.style.opacity = '';
  btn.style.cursor = '';
  btn.title = tip('agent.toggle_t');
}

async function toggleAgent() {
  // Gate: agent mode needs a collaudato tool-calling model. On an incapable
  // model the button is greyed (applyAgentCap) and a click is a no-op.
  let cap = false;
  try { cap = !!AGENT_CAPABLE; } catch (_) { cap = false; }
  if (!cap) { applyAgentCap(); return; }
  // Toggle freely like WEB/RAG — never block on the bridge poll (AGENT_OK flaps
  // when selmo_rag.py is briefly slow to answer). sendMsg handles a down bridge.
  IS_AGENT_ON = !IS_AGENT_ON;
  const btn = document.getElementById('agent-btn');
  if (btn) {
    btn.classList.toggle('on', IS_AGENT_ON);   // icon button: state shown by .on border/glow
    btn.setAttribute('aria-pressed', IS_AGENT_ON);
  }
  // WEB may stay on together with AGENT: it becomes the agent's web_search tool
  // (explicitly gated — no WEB, no way out of the local machine). RAG-as-injection
  // is redundant in agent mode (the agent already has rag_search), so drop it.
  if (IS_AGENT_ON && typeof IS_RAG_ON !== 'undefined' && IS_RAG_ON) {
    IS_RAG_ON = false;
    const rb = document.getElementById('rag-btn');
    if (rb) { rb.classList.remove('on'); rb.textContent = 'RAG'; }
  }
  if (typeof updateAgentRootsBar === 'function') updateAgentRootsBar();
  if (IS_AGENT_ON && !window._agentCfg) {
    try {
      window._agentCfg = await loadAgentConfig();
    } catch(e) {
      console.warn('agent config load failed:', e);
    }
  }
}

// Called by toggleWeb/toggleRag to drop agent mode when another source turns on.
function agentOffFor(otherLabel) {
  if (typeof IS_AGENT_ON === 'undefined' || !IS_AGENT_ON) return;
  IS_AGENT_ON = false;
  const btn = document.getElementById('agent-btn');
  if (btn) { btn.classList.remove('on'); btn.setAttribute('aria-pressed', false); }
  if (typeof updateAgentRootsBar === 'function') updateAgentRootsBar();
}
