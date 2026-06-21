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
