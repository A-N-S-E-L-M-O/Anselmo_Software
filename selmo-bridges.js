'use strict';
// ── Web bridge ────────────────────────────────────────────────────────────────
async function checkWebBridge(){
  const dot=document.getElementById('web-dot');
  const txt=document.getElementById('web-txt');
  function paint(col,label){
    dot.style.background='var('+col+')';dot.style.borderColor='var('+col+')';
    dot.style.boxShadow=col==='--dim'?'none':'0 0 4px var('+col+')';
    txt.style.color='var('+col+')';txt.textContent=label;
  }
  try{
    const r=await fetch(`${WEB}/status`);
    if(!r.ok) throw new Error();
    const d=await r.json();
    webOk=true;
    if(d.searx_local){
      paint('--green','web locale'+(d.trafilatura?'':' (no traf.)'));
    } else {
      // bridge active but local SearXNG down: the search would fall back to public instances
      paint('--yellow','⚠ SearXNG locale OFF — fallback pubblico');
    }
  }catch(e){
    webOk=false;
    paint('--dim','web off');
  }
  refreshCaps();
}
// ── RAG bridge (local retrieval, port 8088) ──────────────────────────────────
let ragStatus={corpus_dir:'',n_chunks:0,embedder_up:false};
async function checkRagBridge(){
  const dot=document.getElementById('rag-dot');
  const txt=document.getElementById('rag-txt');
  function paint(col,label){
    if(!dot||!txt)return;
    dot.style.background='var('+col+')';dot.style.borderColor='var('+col+')';
    dot.style.boxShadow=col==='--dim'?'none':'0 0 4px var('+col+')';
    txt.style.color='var('+col+')';txt.textContent=label;
  }
  try{
    // 6s: /status probes the embedder server-side (can take a few seconds while
    // it boots), so a short client timeout would abort and mislabel the chip.
    const r=await fetch(`${RAG}/status`,{signal:AbortSignal.timeout(6000)});
    if(!r.ok) throw new Error();
    const d=await r.json();
    ragOk=true; ragStatus=d;
    if(!d.embedder_up)         paint('--yellow','⚠ embedder OFF');
    else if(!d.n_chunks)       paint('--yellow','rag: no index');
    else                       paint('--green','rag: '+d.n_chunks+' chunks');
  }catch(e){
    ragOk=false; paint('--dim','rag off');
  }
  if(typeof updateRagCorpusBar==='function')updateRagCorpusBar();
  if(typeof refreshCaps==='function')refreshCaps();
}
// The RAG corpus bar: a clickable line under the first conversation message,
// shown only in RAG mode, with the current folder + chunk count. Opens the
// folder/format picker on click. Lives inside #messages, re-created on demand.
function updateRagCorpusBar(){
  const msgs=document.getElementById('messages');
  let bar=document.getElementById('rag-corpus');
  if(!IS_RAG_ON){ if(bar)bar.remove(); return; }
  if(!msgs) return;
  if(!bar){
    bar=document.createElement('div'); bar.id='rag-corpus'; bar.onclick=openRagPicker;
    const first=msgs.querySelector('.msg');
    if(first&&first.nextSibling) msgs.insertBefore(bar,first.nextSibling);
    else msgs.appendChild(bar);
  }
  const dir=(ragStatus&&ragStatus.corpus_dir)||'';
  const n=(ragStatus&&ragStatus.n_chunks)||0;
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
  bar.innerHTML = dir
    ? '<span class="rc-ic">&#128193;</span> <span class="rc-path">'+esc(dir)+'</span> <span class="rc-n">· '+(n?t('rag.chunks',{n:n.toLocaleString('en')}):t('rag.bar.noindex'))+' · '+t('rag.bar.change')+'</span>'
    : '<span class="rc-ic">&#128193;</span> <em>'+t('rag.bar.choose')+'</em>';
}
// Corpus picker modal: root folder + subfolder checkboxes + format checkboxes.
function openRagPicker(){
  if(!ragOk){addMsg('assistant','⚠ '+t('rag.notactive'));return;}
  const cur=(ragStatus&&ragStatus.corpus_dir)||'';
  const ov=document.createElement('div'); ov.className='rag-overlay'; ov.id='rag-overlay';
  ov.addEventListener('click',e=>{ if(e.target===ov) ov.remove(); });
  ov.innerHTML='<div class="rag-card">'
    +'<div class="rag-h">'+t('rag.pick.title')+'</div>'
    +'<div class="rag-lab">'+t('rag.pick.root')+'</div>'
    +'<div class="rag-row"><input id="ragp-root" type="text" placeholder="C:\\\\...\\\\folder" value="'+cur.replace(/"/g,'&quot;')+'"><button id="ragp-browse" class="rag-btn">'+t('rag.pick.browse')+'</button></div>'
    +'<div id="ragp-body" class="rag-body"><div class="rag-hint">'+t('rag.pick.hint')+'</div></div>'
    +'<div class="rag-act"><button id="ragp-cancel" class="rag-btn">'+t('rag.pick.cancel')+'</button><button id="ragp-index" class="rag-btn rag-primary">'+t('rag.pick.index')+'</button></div>'
    +'</div>';
  document.body.appendChild(ov);
  document.getElementById('ragp-cancel').onclick=()=>ov.remove();
  document.getElementById('ragp-browse').onclick=ragBrowse;
  document.getElementById('ragp-index').onclick=ragDoIndex;
  const inp=document.getElementById('ragp-root');
  inp.addEventListener('keydown',e=>{ if(e.key==='Enter'){e.preventDefault();ragBrowse();} });
  if(cur) ragBrowse();
}
async function ragBrowse(){
  const root=document.getElementById('ragp-root').value.trim();
  const body=document.getElementById('ragp-body');
  if(!root){ body.innerHTML='<div class="rag-hint">'+t('rag.pick.enterpath')+'</div>'; return; }
  body.innerHTML='<div class="rag-hint">'+t('rag.pick.reading')+'</div>';
  let d;
  try{ d=await(await fetch(`${RAG}/browse?`+new URLSearchParams({dir:root}))).json(); }
  catch(e){ body.innerHTML='<div class="rag-hint">'+t('rag.error',{msg:e.message})+'</div>'; return; }
  if(!d.ok){ body.innerHTML='<div class="rag-hint">'+t('rag.pick.invalid')+(d.error?' ('+d.error+')':'')+'.</div>'; return; }
  const curExcl=(ragStatus&&ragStatus.exclude_dirs)||[];
  const curFmts=(ragStatus&&ragStatus.formats)||[];
  const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  const subHtml=d.subdirs.length
    ? d.subdirs.map(s=>'<label class="rag-ck"><input type="checkbox" class="ragp-sub" value="'+esc(s)+'"'+(curExcl.indexOf(s)>=0?'':' checked')+'> '+esc(s)+'</label>').join('')
    : '<div class="rag-hint">'+t('rag.pick.nosubs')+'</div>';
  const fmtHtml=d.formats.length
    ? d.formats.map(f=>'<label class="rag-ck"><input type="checkbox" class="ragp-fmt" value="'+esc(f.ext)+'"'+((!curFmts.length||curFmts.indexOf(f.ext)>=0)?' checked':'')+'> '+esc(f.ext)+' <span class="rc-n">('+f.count+')</span></label>').join('')
    : '<div class="rag-hint">'+t('rag.pick.nofmt')+'</div>';
  body.innerHTML='<div class="rag-lab">'+t('rag.pick.subs')+'</div><div class="rag-grid">'+subHtml+'</div>'
    +'<div class="rag-lab">'+t('rag.pick.formats')+'</div><div class="rag-grid">'+fmtHtml+'</div>';
}
async function ragDoIndex(){
  const rootEl=document.getElementById('ragp-root'); if(!rootEl)return;
  const root=rootEl.value.trim(); if(!root){ ragBrowse(); return; }
  const excl=[...document.querySelectorAll('.ragp-sub:not(:checked)')].map(c=>c.value);
  const fmts=[...document.querySelectorAll('.ragp-fmt:checked')].map(c=>c.value);
  const ov=document.getElementById('rag-overlay'); if(ov) ov.remove();
  // Indexing runs in the bridge in the background; we poll /progress and draw a
  // bar, so there is no single long request that times out through the proxy.
  const m=addMsg('assistant','');
  m.bub.innerHTML='<div>⏳ '+t('rag.indexing',{dir:root})+'</div>'
    +'<div class="rag-prog"><div class="rag-prog-fill"></div></div>'
    +'<div class="rag-prog-txt"></div>';
  const fill=m.bub.querySelector('.rag-prog-fill');
  const ptxt=m.bub.querySelector('.rag-prog-txt');
  if(m.av)m.av.classList.add('thinking'); // spin the drum while indexing too
  try{
    await fetch(`${RAG}/config`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({corpus_dir:root,exclude_dirs:excl,formats:fmts})});
    await(await fetch(`${RAG}/reindex`,{method:'POST'})).json();
    await new Promise(resolve=>{
      const iv=setInterval(async()=>{
        let p; try{ p=await(await fetch(`${RAG}/progress`)).json(); }catch(e){ return; }
        if(p.phase==='scanning'){ ptxt.textContent=t('rag.prog.scanning',{files:p.files}); }
        else if(p.phase==='embedding'&&p.chunks_total){
          const pct=Math.min(100,Math.round(p.chunks/p.chunks_total*100));
          fill.style.width=pct+'%';
          ptxt.textContent=t('rag.prog.embedding',{done:p.chunks,total:p.chunks_total,pct:pct});
        }
        else if(p.phase==='saving'){ fill.style.width='100%'; ptxt.textContent=t('rag.prog.saving'); }
        if(p.done||p.indexing===false){
          clearInterval(iv);
          if(p.error){ m.bub.innerHTML='⚠ '+t('rag.failed',{err:p.error}); }
          else { m.bub.innerHTML='✓ '+t('rag.indexed',{files:p.n_files,chunks:p.n_chunks}); }
          if(m.av)m.av.classList.remove('thinking');
          checkRagBridge(); scrollBot(); resolve();
        } else { scrollBot(); }
      },700);
    });
  }catch(e){ if(m.av)m.av.classList.remove('thinking'); m.bub.innerHTML='⚠ '+t('rag.error',{msg:e.message}); }
}
// Retrieve top-k chunks from the local corpus. Same {title,url,snippet} shape
// as webSearch, so the send loop treats RAG results exactly like web results.
async function ragSearch(query, n=5){
  try{
    const url=`${RAG}/search?${new URLSearchParams({q:query,n})}`;
    const r=await fetch(url,{signal:AbortSignal.timeout(20000)});
    if(!r.ok) return [];
    const d=await r.json();
    return Array.isArray(d)?d:[];
  }catch(e){ return []; }
}
async function checkWhisperBridge(){
  try{
    const r=await fetch(`${WHISPER}/status`,{signal:AbortSignal.timeout(2000)});
    if(!r.ok)throw new Error();
    const d=await r.json();
    whisperOk=true;
    const dot=document.getElementById('whisper-dot');
    const txt=document.getElementById('whisper-txt');
    dot.style.background='var(--green)';dot.style.borderColor='var(--green)';
    dot.style.boxShadow='0 0 4px var(--green)';
    txt.style.color='var(--green)';
    txt.textContent='whisper OK ('+d.model+')';
    document.getElementById('mic-btn').title='Record and transcribe (Whisper '+d.model+')';
  }catch{
    whisperOk=false;
    const dot=document.getElementById('whisper-dot');
    const txt=document.getElementById('whisper-txt');
    dot.style.background='var(--dim)';dot.style.borderColor='var(--dim)';
    dot.style.boxShadow='';
    txt.style.color='var(--dim)';
    txt.textContent='whisper off';
  }
  refreshCaps();
}

// ── Image-generation bridge (health) ──────────────────────────────────────────
async function checkImageBridge(){
  try{
    const r=await fetch(`${IMG_URL}/status`,{signal:AbortSignal.timeout(2000)});
    imgOk=r.ok;
  }catch(e){ imgOk=false; }
  refreshCaps();
}

// ── Capability gating for the bottom-band buttons ─────────────────────────────
// Grey out (disabled, NOT hidden) any action whose capability or backing service
// is missing, so an entry-level / demo box never shows a button that does nothing.
// A service counts as available even in FALLBACK (e.g. TTS via Web Speech).
// NB: we use aria-disabled (not the `disabled` property) so the native title
// tooltip still shows on hover -- a `disabled` button receives no mouse events,
// so its tooltip never appears. Clicks are blocked by _capClickGuard below.
function _setCap(id, ok, offTitle){
  const b=document.getElementById(id);
  if(!b)return;
  if(ok){
    b.removeAttribute('aria-disabled');
    b.style.opacity=''; b.style.cursor='';
  }else{
    b.setAttribute('aria-disabled','true');
    b.style.opacity='.35'; b.style.cursor='not-allowed';
    if(offTitle) b.title=offTitle;
  }
}
// Swallow clicks on anything marked aria-disabled, in the CAPTURE phase so it
// runs before the element's inline onclick. Installed once from boot.
function _capClickGuard(e){
  const el=(e.target instanceof Element)&&e.target.closest('[aria-disabled="true"]');
  if(el){ e.preventDefault(); e.stopImmediatePropagation(); }
}
function refreshCaps(){
  _setCap('web-btn',        webOk,     'Web search bridge not running (start selmo_web.py)');
  _setCap('mic-btn',        whisperOk, 'Voice transcription not available in this edition');
  _setCap('vad-btn',        whisperOk, 'Hands-free voice needs the voice edition');
  _setCap('tts-btn',        ttsOk,     'Text-to-speech not available');
  _setCap('gen-img-btn',    imgOk,     'Image generation not available in this edition');
  _setCap('upload-img-btn', visionOk,  'This model has no vision - load a model with an mmproj');
  // a toggle that goes unavailable while ON must not stay stuck on
  if(!webOk&&typeof IS_WEB_ON!=='undefined'&&IS_WEB_ON){
    IS_WEB_ON=false;
    const b=document.getElementById('web-btn');
    if(b)b.classList.remove('on');
  }
}
// ── Mic / Whisper recording ───────────────────────────────────────────────────
async function toggleMic(){
  if(mediaRecorder&&mediaRecorder.state==='recording'){
    mediaRecorder.stop();
    return;
  }
  if(!whisperOk){
    addMsg('assistant','\u26A0 Whisper not running. Start selmo_whisper.py to use the microphone.');
    return;
  }
  let stream;
  try{
    stream=await navigator.mediaDevices.getUserMedia({audio:true});
  }catch(e){
    addMsg('assistant','\u26A0 Microphone not available: '+e.message);
    return;
  }
  audioChunks=[];
  const mimeType=MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ?'audio/webm;codecs=opus':'audio/webm';
  mediaRecorder=new MediaRecorder(stream,{mimeType});
  mediaRecorder.ondataavailable=e=>{if(e.data.size>0)audioChunks.push(e.data);};
  mediaRecorder.onstop=async()=>{
    const btn=document.getElementById('mic-btn');
    btn.classList.remove('recording');
    btn.textContent='\uD83C\uDFA4';
    stream.getTracks().forEach(t=>t.stop());
    btn.textContent='\u23F3';
    const blob=new Blob(audioChunks,{type:mimeType});
    const fd=new FormData();
    fd.append('audio',blob,'audio.webm');
    try{
      const r=await fetch(`${WHISPER}/transcribe`,{method:'POST',body:fd,signal:AbortSignal.timeout(30000)});
      const d=await r.json();
      if(d.error){addMsg('assistant','\u26A0 Whisper: '+d.error);btn.textContent='\uD83C\uDFA4';return;}
      const inp=document.getElementById('input');
      inp.value=(inp.value?inp.value+' ':'')+d.text.trim();
      autoResize(inp);
      if(pttAutoSend){
        pttAutoSend=false;
        if(pttWebSearch){
          pttWebSearch=false;
          pttForceTts=true;
          inp.value='/web '+inp.value.trim();
          autoResize(inp);
          setTimeout(sendMsg,50);
        }else{
          pttForceTts=true;
          setTimeout(sendMsg,50);
        }
      }
      else inp.focus();
    }catch(e){
      addMsg('assistant','\u26A0 Transcription error: '+e.message);
      pttAutoSend=false;
    }
    btn.textContent='\uD83C\uDFA4';
    mediaRecorder=null;
  };
  mediaRecorder.start();
  const btn=document.getElementById('mic-btn');
  btn.classList.add('recording');
  btn.textContent='\u23F9';
}
async function webSearch(query, n=5){
  try{
    const url=`${WEB}/search?${new URLSearchParams({q:query,n})}`;
    const r=await fetch(url,{signal:AbortSignal.timeout(12000)});
    if(!r.ok) return [];
    return await r.json();
  }catch(e){
    return [];
  }
}
// Turn a conversational message + recent context into a clean, standalone
// web-search query. Runs on the LOCAL model — nothing extra leaves localhost.
// Falls back to the raw message on any error, so behaviour never regresses.
async function rewriteQuery(rawMsg, history, docContext){
  try{
    const recent=(history||[])
      .filter(m=>m.role!=='system')
      .slice(-4)
      .map(m=>{
        const role=m.role==='user'?'User':'Selmo';
        let raw=m._orig;
        if(raw==null){
          raw=m.content;
          if(Array.isArray(raw)) raw=raw.filter(p=>p&&p.type==='text').map(p=>p.text).join(' ');
        }
        const c=String(raw||'').replace(/\[THINK\][\s\S]*?\[\/THINK\]/g,'').trim().slice(0,300);
        return role+': '+c;
      }).join('\n');
    // Standard RAG query-rewriting step (cf. "Rewrite-Retrieve-Read", HyDE):
    // turn the chat turn into a keyword query a search engine can actually use.
    //
    // Reasoning models (Qwen, Gemma) ignore an in-prompt '/no_think', so we
    // disable thinking the supported way — chat_template_kwargs.enable_thinking
    // = false — and retry without it if the server rejects the field. As a
    // safety net the budget is large and we parse the 'QUERY:' line out of the
    // reply even when a <think> block precedes it.
    const sys='You are a search-query rewriter. '
      +(docContext
        ?'Document/image context is provided below. Your query MUST use the specific '
         +'product names, model numbers, menu names, and technical terms from that context. '
         +'Do NOT paraphrase the user\'s words — derive keywords from the context instead. '
        :'Given the conversation and the user\'s latest message, ')
      +'write the single most effective web-search query to find pages that answer it. '
      +'Resolve pronouns from the conversation. Use concise keywords; drop filler. '
      +'Keep the user\'s language. Reply with EXACTLY one line:\nQUERY: <keywords>';
    const usr=(recent?'Conversation:\n'+recent+'\n\n':'')
      +(docContext?'Loaded document/image context:\n'+String(docContext).slice(0,1500)+'\n\n':'')
      +'Latest message: '+rawMsg;
    const callModel=extra=>fetch(`${API}/v1/chat/completions`,{
      method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(30000),
      body:JSON.stringify(Object.assign({model:'local',
        messages:[{role:'system',content:sys},{role:'user',content:usr}],
        stream:false,temperature:0.2,top_p:0.9,max_tokens:1024,repeat_penalty:1.1},extra))
    });
    let res=await callModel({chat_template_kwargs:{enable_thinking:false}});
    if(!res.ok) res=await callModel({}); // server rejects the kwarg -> retry plain
    if(!res.ok) return rawMsg;
    const d=await res.json();
    const msg=(d.choices&&d.choices[0]&&d.choices[0].message)||{};
    const body=((msg.content||'')+'\n'+(msg.reasoning_content||''))
      .replace(/<think>[\s\S]*?<\/think>/gi,'')
      .replace(/\[THINK\][\s\S]*?\[\/THINK\]/gi,'');
    // Pull the QUERY: line; its absence (e.g. unfinished reasoning) -> keep raw.
    const mq=body.match(/QUERY\s*[:：]\s*(.+)/i);
    const q=(mq?mq[1]:'').replace(/["'`]/g,'').trim();
    console.log('[rewrite]',JSON.stringify(rawMsg),'→',JSON.stringify(q),'| out_tok',(d.usage&&d.usage.completion_tokens)||'?');
    return q.length>=2?q:rawMsg;
  }catch(e){
    return rawMsg;
  }
}
function loadProps(tries){
  tries=tries||0;
  fetch(`${API}/props`).then(r=>r.json()).then(p=>{
    const _ct=(typeof p?.chat_template==='string')?p.chat_template:'';
    configureThink(_ct);
    const nCtx=p?.default_generation_settings?.n_ctx||p?.n_ctx||0;
    if(nCtx>=1024){
      N_CTX=nCtx; MODEL_READY=true;
      CHUNK_SIZE=Math.floor(CHUNK_SIZE_TOK*3.8);
      document.getElementById('hdr-model').title=`ctx: ${nCtx.toLocaleString()} tok  ·  chunk max: ${CHUNK_SIZE.toLocaleString()} char`;
    } else if(tries<10){ setTimeout(()=>loadProps(tries+1),1500); }
    if(!_traceDone){_traceDone=true;showStartupTrace();}
  }).catch(()=>{
    if(!_traceDone){_traceDone=true;showStartupTrace();}
    if(tries<10)setTimeout(()=>loadProps(tries+1),1500);
  });
}
