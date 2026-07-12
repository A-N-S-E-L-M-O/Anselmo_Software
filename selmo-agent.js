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
  const builtins = (cfg.agent_builtin_tools || [])
    // write_file is only offered to the model when writes are enabled for the folder.
    .filter(t => enabled.has(t.name) && (t.name !== 'write_file' || allowWrites));
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

async function agentLoop(userMsg, chatHistory, targetDiv, cfg) {
  const schemas = buildToolSchemas(cfg);
  window._agentSchemas = schemas;
  window._agentCfg = cfg;

  const maxSteps = cfg.agent_max_steps ?? 12;
  const timeoutMs = (cfg.agent_timeout_s ?? 120) * 1000;
  const deadline = Date.now() + timeoutMs;

  // Build messages array (same format as normal path)
  const messages = apiMessages(chatHistory, userMsg);

  const stepEl = document.getElementById('agent-step');
  let step = 0;
  let lastContent = '';   // keep last assistant text so a timeout still shows something

  const toolMap = Object.fromEntries(schemas.map(s => [s.function.name, s._def]));

  // Intermediate history (tool turns) — not persisted to session
  const toolHistory = [];

  if (stepEl) stepEl.style.display = 'inline-block';

  try {
    while (step < maxSteps && Date.now() < deadline) {
      if (!gen) break;   // gen is the global abort flag set by abort()

      step++;
      if (stepEl) stepEl.textContent = t('agent.step', { n: step, max: maxSteps });

      const body = {
        model: (typeof MODEL_FULL!=='undefined'?MODEL_FULL:'local'),
        messages: [...messages, ...toolHistory],
        tools: schemas.map(({ type, function: fn }) => ({ type, function: fn })),
        tool_choice: 'auto',
        stream: false,
        temperature: 0.1
      };

      const r = await fetch('/proxy/8089/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(60000)
      });
      if (!r.ok) {
        // The most common cause is a model/server without tool support
        // (no --jinja, or a chat template that declares no tools).
        const detail = await r.text().catch(() => '');
        if (r.status === 400 || r.status === 500 || /tool|jinja|template/i.test(detail)) {
          return t('agent.no_tool_support');
        }
        throw new Error('llama ' + r.status);
      }
      const data = await r.json();
      const choice = data.choices?.[0];
      if (!choice) throw new Error('no choices');

      const msg = choice.message;
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

async function toggleAgent() {
  // Toggle freely like WEB/RAG — never block on the bridge poll (AGENT_OK flaps
  // when selmo_rag.py is briefly slow to answer). sendMsg handles a down bridge.
  IS_AGENT_ON = !IS_AGENT_ON;
  const btn = document.getElementById('agent-btn');
  if (btn) {
    btn.classList.toggle('on', IS_AGENT_ON);   // icon button: state shown by .on border/glow
    btn.setAttribute('aria-pressed', IS_AGENT_ON);
  }
  // Agent, Web and RAG are three ways to ground a turn — only one at a time.
  if (IS_AGENT_ON) {
    if (typeof IS_WEB_ON !== 'undefined' && IS_WEB_ON) {
      IS_WEB_ON = false;
      const wb = document.getElementById('web-btn');
      if (wb) { wb.classList.remove('on'); }
    }
    if (typeof IS_RAG_ON !== 'undefined' && IS_RAG_ON) {
      IS_RAG_ON = false;
      const rb = document.getElementById('rag-btn');
      if (rb) { rb.classList.remove('on'); rb.textContent = 'RAG'; }
    }
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
