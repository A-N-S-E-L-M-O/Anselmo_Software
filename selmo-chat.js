'use strict';
// CHAT
function scrollBot(){const m=document.getElementById('messages');m.scrollTop=m.scrollHeight;}
// Enter follows whichever mode the header shows: 'image mode' (LLM swapped
// out for image gen) -> Enter behaves exactly like clicking the palette
// button (toggleImgMenu: text-to-image, or opens the picker if an image is
// loaded); any other state -> normal chat send. Fixes the "distracted Enter"
// trap: hitting Enter out of habit while in image mode used to fall through
// to sendMsg(), which silently reloaded the chat LLM just because Enter was
// pressed without thinking.
function handleKey(e){
  if(e.key==='Enter'&&!e.shiftKey){
    e.preventDefault();
    const h=document.getElementById('hdr-model');
    if(h&&h.textContent==='image mode'){toggleImgMenu();}
    else{sendMsg();}
  }
}
function autoResize(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,140)+'px';}
function addMsg(role,text,streaming){
  const wrap=document.createElement('div');wrap.className='msg '+role;
  const av=document.createElement('div');av.className='av';
  if(role==='user'){av.textContent='tu';}
  else{av.innerHTML='<img src="selmo-icon-preview.png" alt="Selmo" draggable="false">';if(streaming)av.classList.add('thinking');}
  const inner=document.createElement('div');
  const bub=document.createElement('div');bub.className='bubble';
  if(streaming){bub.innerHTML='<span style="opacity:.5">&#x25ca;</span>';}else{bub.textContent=text;}
  inner.appendChild(bub);
  if(role==='user'){wrap.appendChild(inner);wrap.appendChild(av);}else{wrap.appendChild(av);wrap.appendChild(inner);}
  document.getElementById('messages').appendChild(wrap);scrollBot();
  return{bub,inner,wrap,av};
}
function imgThumbStrip(urls){
  const strip=document.createElement('div');
  strip.style.cssText='display:flex;flex-wrap:wrap;gap:6px;margin-top:8px';
  urls.forEach((u,i)=>{
    const im=new Image();
    im.src=u;im.title='page '+(i+1)+' - click to enlarge';
    im.style.cssText='max-height:160px;max-width:120px;border:1px solid var(--cyan);border-radius:4px;cursor:zoom-in;background:#fff';
    im.onclick=()=>window.open(u,'_blank');
    strip.appendChild(im);
  });
  return strip;
}
function newChat(){
  if(gen)stopMsg();
  saveSession();
  currentSessionId=(()=>Date.now().toString(36)+Math.random().toString(36).slice(2,6))();
  document.getElementById('messages').innerHTML='';
  chatHistory.splice(1);
  wh=0;sessStart=Date.now();
  clearFile();updCost();
  announceModel(false);
  document.getElementById('input').focus();
  renderSessionList();
}
function exportChat(){
  const msgs=chatHistory.slice(1);
  if(!msgs.length){alert('Nothing to export.');return;}
  const mode='Selmo';
  const model=document.getElementById('hdr-model').textContent||'local';
  const now=new Date();
  const stamp=now.toISOString().slice(0,16).replace('T',' ');
  const fname=`selmo-chat-${now.toISOString().slice(0,16).replace(/[T:]/g,'-')}.md`;
  let md=`# ${mode} — Chat log\n`;
  md+=`*${stamp} · model: ${model} · Wh: ${wh.toFixed(3)}*\n\n---\n\n`;
  for(const m of msgs){
    const who=m.role==='user'?'**Tu**':`**${mode}**`;
    let c=m._orig;
    if(c==null){
      c=m.content;
      if(Array.isArray(c)) c=c.filter(p=>p&&p.type==='text').map(p=>p.text).join('\n');
    }
    md+=`${who}\n\n${c}\n\n---\n\n`;
  }
  const blob=new Blob([md],{type:'text/markdown'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=fname;
  a.click();
  URL.revokeObjectURL(a.href);
}
function stamp(){return new Date().toISOString().slice(0,16).replace(/[T:]/g,'-');}
function dlBlob(text,fname,mime){
  const blob=new Blob([text],{type:mime});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);a.download=fname;a.click();
  URL.revokeObjectURL(a.href);
}
// Output download (single reply, not the whole chat).
// .md = the reply verbatim. .tsv = the first Markdown table in the reply,
// tab-separated. TSV is deliberate: in the Italian locale the comma is the
// decimal separator and the semicolon the CSV list separator, so a comma-CSV
// misparses on double-click in Excel/Calc; a tab never collides. A UTF-8 BOM
// is prepended so accented characters survive in Excel.
function mdTableToTSV(md){
  const out=[];
  for(let ln of md.split(/\r?\n/)){
    let t=ln.trim();
    if(t.indexOf('|')===-1){ if(out.length)break; else continue; }
    if(t.startsWith('|'))t=t.slice(1);
    if(t.endsWith('|'))t=t.slice(0,-1);
    if(/^[\s:\-|]+$/.test(t))continue;            // separator row |---|:--:|
    out.push(t.split('|').map(c=>c.trim().replace(/\\\|/g,'|')).join('\t'));
  }
  return out.join('\r\n');
}
function dlReplyMd(md){ dlBlob(md,'selmo-output-'+stamp()+'.md','text/markdown;charset=utf-8'); }
function dlReplyTsv(md){
  const tsv=mdTableToTSV(md);
  if(!tsv){alert('No table in this reply. Ask the model to format the data as a Markdown table, then download .tsv.');return;}
  dlBlob('\uFEFF'+tsv,'selmo-output-'+stamp()+'.tsv','text/tab-separated-values;charset=utf-8');
}
// Copy text to the clipboard. Uses the async Clipboard API on a secure context
// (HTTPS / localhost); falls back to a hidden-textarea execCommand on plain HTTP
// (the phone over 8080), where navigator.clipboard is unavailable.
function copyToClipboard(text,btn){
  const flash=(label)=>{if(btn){const o=btn.textContent;btn.textContent=label;setTimeout(()=>{btn.textContent=o;},1300);}};
  const ok=()=>flash('✓ copied'), fail=()=>flash('✕ blocked');
  if(navigator.clipboard&&navigator.clipboard.writeText&&window.isSecureContext){
    navigator.clipboard.writeText(text).then(ok,fail);return;
  }
  try{
    const ta=document.createElement('textarea');ta.value=text;
    ta.style.cssText='position:fixed;top:-1000px;left:-1000px;opacity:0';
    document.body.appendChild(ta);ta.focus();ta.select();
    const done=document.execCommand('copy');document.body.removeChild(ta);
    done?ok():fail();
  }catch(_){fail();}
}
function addDownloadBar(bub,inner,md){
  if(!md||!md.trim())return;
  const bar=document.createElement('div');
  bar.style.cssText='display:flex;gap:8px;margin-top:6px;';
  const mk=(label,fn)=>{const b=document.createElement('button');b.textContent=label;
    b.style.cssText='background:none;border:1px solid var(--steel);color:var(--dim);border-radius:4px;padding:2px 9px;cursor:pointer;font-family:inherit;font-size:12px;';
    b.onclick=fn;b.onmouseover=()=>{b.style.borderColor='var(--cyan)';b.style.color='var(--cyan)';};
    b.onmouseout=()=>{b.style.borderColor='var(--steel)';b.style.color='var(--dim)';};return b;};
  bar.appendChild(mk('⧉ copy',function(){copyToClipboard(md,this);}));
  bar.appendChild(mk('↓ .md',()=>dlReplyMd(md)));
  bar.appendChild(mk('↓ .tsv',()=>dlReplyTsv(md)));
  inner.appendChild(bar);
}
function stopMsg(){if(abort){abort.abort();abort=null;}stopTts();}
// Robust SSE reader: buffers between reads (no tokens lost if
// a 'data:' line is split in half) and reads both content and reasoning_content
// (reasoning models like Gemma write the reasoning in reasoning_content).
async function streamTokens(res,onContent,onReason){
  const reader=res.body.getReader(),dec=new TextDecoder();
  // inTk starts true for reasoning-first models (Olmo opens <think> in its
  // prompt template, so the stream begins inside the reasoning block and only
  // ever emits the closing tag). REASON_FIRST is detected from /props.
  let buf='',tb='',inTk=REASON_FIRST;
  // Two tag families: Magistral [THINK]/[/THINK], Olmo <think>/</think>.
  const OPENS=['[THINK]','<think>'],CLOSES=['[/THINK]','</think>'],HOLD=7; // longest tag is 8 chars
  function firstOf(str,arr){let bi=-1,bl=0;for(const t of arr){const i=str.indexOf(t);if(i!==-1&&(bi===-1||i<bi)){bi=i;bl=t.length;}}return{i:bi,len:bl};}
  function flush(){
    while(tb.length>0){
      if(!inTk){
        const m=firstOf(tb,OPENS);
        if(m.i===-1){const s=tb.slice(0,Math.max(0,tb.length-HOLD));if(s){onContent(s);tb=tb.slice(s.length);}break;}
        if(m.i>0)onContent(tb.slice(0,m.i));tb=tb.slice(m.i+m.len);inTk=true;
      }else{
        const m=firstOf(tb,CLOSES);
        if(m.i===-1){const s=tb.slice(0,Math.max(0,tb.length-HOLD));if(s&&onReason){onReason(s);tb=tb.slice(s.length);}break;}
        if(m.i>0&&onReason)onReason(tb.slice(0,m.i));tb=tb.slice(m.i+m.len);inTk=false;
      }
    }
  }
  while(true){
    const{done,value}=await reader.read();
    if(done){if(tb)inTk?(onReason&&onReason(tb)):onContent(tb);break;}
    buf+=dec.decode(value,{stream:true});
    const lines=buf.split('\n');buf=lines.pop();
    for(const line of lines){
      if(!line.startsWith('data:'))continue;
      const raw=line.slice(5).trim();if(!raw||raw==='[DONE]')continue;
      try{const dl=JSON.parse(raw).choices?.[0]?.delta||{};
        if(dl.reasoning_content&&onReason){inTk=false;onReason(dl.reasoning_content);}  // Gemma/Qwen: reasoning_content (disarm implicit-open)
        if(dl.content){tb+=dl.content;flush();}  // independent if, NOT else-if (v0.901, BUG-NOANS-01): a delta carrying BOTH reasoning_content and content must not drop the answer (Qwen short answers rode along combined deltas -> 0 tok)
      }catch{}
    }
  }
}
// Create the thinking panel and return { panel, append, seal }
function makeThinkPanel(inner){
  const panel=document.createElement('div');
  panel.className='think-panel collapsed';
  const toggle=document.createElement('div');toggle.className='think-toggle';
  const arrow=document.createElement('span');arrow.textContent='▶';
  const label=document.createElement('span');label.textContent='reasoning (0 tok)';
  toggle.appendChild(arrow);toggle.appendChild(label);
  const body=document.createElement('div');body.className='think-body';
  panel.appendChild(toggle);panel.appendChild(body);
  inner.insertBefore(panel,inner.firstChild);
  let rtok=0,sealed=false,expanded=false;
  panel.style.display='none';
  toggle.addEventListener('click',()=>{
    expanded=!expanded;
    panel.classList.toggle('collapsed',!expanded);
    arrow.textContent=expanded?'▼':'▶';
  });
  function append(chunk){
    if(sealed)return;
    if(rtok===0)panel.style.display='';
    body.textContent+=chunk;rtok++;
    label.textContent='reasoning ('+rtok+' tok)';
    if(expanded)panel.scrollTop=panel.scrollHeight;
    scrollBot();
  }
  function seal(){
    sealed=true;
    if(rtok===0){panel.remove();return;}
    label.textContent='reasoning complete ('+rtok+' tok)';
  }
  return{panel,append,seal};
}
// Simple split: pieces of at most `size` characters, cut at a paragraph
// boundary, then sentence, then word. Full coverage, no overlap.
function splitDoc(text,size){
  text=text.replace(/\x00/g,'');
  const out=[];let i=0;const n=text.length;
  while(i<n){
    let end=Math.min(i+size,n);
    if(end<n){
      const seg=text.slice(i,end);
      let br=seg.lastIndexOf('\n\n');
      if(br<size*0.5)br=seg.lastIndexOf('\n');
      if(br<size*0.5)br=seg.lastIndexOf('. ');
      if(br<size*0.5)br=seg.lastIndexOf(' ');
      if(br>0)end=i+br+1;
    }
    const piece=text.slice(i,end).trim();
    if(piece)out.push(piece);
    i=end;
  }
  return out;
}
// Chunked document analysis. The chunk size depends ON THE PROMPT and on
// the model's real context: ctx - system - prompt - response - margin. This way
// it never overflows, with any model, and stays GPU-friendly (small context).
function notReadyMsg(){
  addMsg('assistant','\u26A0 Model not ready: the header still shows "local" and the context window is the 4 KB fallback, so each chunk would be capped at ~512 output tokens and most of the result lost. Refresh the page (Ctrl+F5), wait for the model name to appear in the header, then start the job again.');
}
async function processDoc(prompt){
  const btn=document.getElementById('send'),stopBtn=document.getElementById('stop');
  const tk=s=>Math.ceil((s||'').length/3.2);   // stima conservativa char->token
  const SAFETY=256;
  // System prompt for this chunk: SP_TASK base; if model needs [THINK] instruction, append it.
  const chunkSys=SP_TASK; // no THINK_INSTR in chunking: native reasoning is enough, explicit invitation causes overthinking
  const avail=Math.max(512,N_CTX-tk(chunkSys)-tk(prompt)-SAFETY);
  const inT=CHUNK_SIZE_TOK;   // from INI via selmo-config.json
  const maxTok=Math.max(512,avail-inT); // full ctx headroom for output
  const chunkChars=Math.max(800,Math.floor(inT*3.2));
  const parts=splitDoc(fileDoc,chunkChars);
  const total=parts.length;
  console.log('Selmo chunking: ctx='+N_CTX+' chunk='+chunkChars+'char x'+total+' max_tokens='+maxTok);
  if(!MODEL_READY||maxTok<=512){ notReadyMsg(); return; }

  gen=true;_genT0=Date.now();_genTok=0;btn.style.display='none';stopBtn.style.display='inline-block';
  addMsg('user',prompt+'  ('+total+' chunk \xb7 '+fileDoc.length.toLocaleString('en')+' char)');
  chatHistory.push({role:'user',content:prompt+' ('+total+' chunks)'});

  const results=[];
  for(let i=0;i<total;i++){
    if(!gen)break;
    const prog=addMsg('assistant','',true);
    prog.bub.innerHTML='<span style="color:var(--yellow);">▶ '+(i+1)+'/'+total+'</span>';
    const msgs=[{role:'system',content:chunkSys},{role:'user',content:prompt+'\n\n---\n\n'+parts[i]}];
    abort=new AbortController();
    try{
      const res=await fetch(`${API}/v1/chat/completions`,{
        method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,
        body:JSON.stringify({model:'local',messages:msgs,stream:true,temperature:0.2,max_tokens:maxTok,repeat_penalty:1.1})});
      if(!res.ok){let _d='';try{_d=(await res.text()).slice(0,400);}catch(_){}const _srv=res.headers.get('server')||'(no server header)';const _cl=res.headers.get('content-length');const _ct=res.headers.get('content-type')||'?';throw new Error('HTTP '+res.status+' '+(res.statusText||'')+' [server='+_srv+' ct='+_ct+' len='+(_cl==null?'?':_cl)+']'+(_d?' \u2014 '+_d:' \u2014 (empty body)'));}
      prog.bub.innerHTML='';
      let full='',t=0;
      // The reasoning (reasoning_content or <think>..</think>) goes in the panel,
      // NEVER in the document stitch: only the clean response ends up in 'full'.
      const tp=makeThinkPanel(prog.inner);
      await streamTokens(res,
        c=>{full+=c;t++;_genTok++;prog.bub.textContent=full;scrollBot();},
        r=>{_genTok++;tp.append(r);});
      tp.seal();
      toks+=t;localStorage.setItem('stoks',toks);
      document.getElementById('tok-tot').textContent=toks.toLocaleString('en');
      const ci=document.createElement('div');ci.className='chunk-info';
      ci.textContent=(i+1)+'/'+total+' \xb7 '+t+' tok';prog.inner.appendChild(ci);
      if(full.trim())results.push(full.trim());
    }catch(e){
      if(e.name==='AbortError'){prog.bub.textContent='[stop '+(i+1)+'/'+total+']';break;}
      prog.bub.textContent='Error chunk '+(i+1)+': '+e.message;break;
    }
  }

  if(results.length){
    if(total>1){
      const now=new Date();
      const fname='selmo-'+now.toISOString().slice(0,16).replace(/[T:]/g,'-')+'.md';
      const md='# '+prompt+'\n\n*'+now.toISOString().slice(0,16).replace('T',' ')+' \xb7 '+results.length+'/'+total+' chunk*\n\n---\n\n'+results.join('\n\n---\n\n');
      const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'}));a.download=fname;a.click();URL.revokeObjectURL(a.href);
      const done=addMsg('assistant','',false);
      done.bub.textContent='✓ '+results.length+'/'+total+' chunk \xb7 '+fname+' scaricato.';
      chatHistory.push({role:'assistant',content:done.bub.textContent});
    }else{
      chatHistory.push({role:'assistant',content:results[0]});
    }
    saveSession();
  }else{
    addMsg('assistant','No content produced.');
  }
  fileDoc=null;
  document.getElementById('file-badge').style.display='none';
  gen=false;btn.style.display='inline-block';stopBtn.style.display='none';abort=null;
  setThinkEnabled(true);
  document.getElementById('input').focus();
}
async function processChunks(prompt){
  const btn=document.getElementById('send');
  const stopBtn=document.getElementById('stop');
  const total=chunks.length;
  if(!MODEL_READY){ notReadyMsg(); return; }
  gen=true;_genT0=Date.now();_genTok=0;btn.style.display='none';stopBtn.style.display='inline-block';

  addMsg('user',prompt+' ('+total+' chunks)');
  chatHistory.push({role:'user',content:prompt+' ('+total+' chunks)'});

  const results=[]; // collect responses for the final summary
  let interrupted=false;

  for(let i=0;i<total;i++){
    if(!gen){interrupted=true;break;}
    chunkIdx=i;
    const prog=addMsg('assistant','',true);
    prog.bub.innerHTML=
      '<span style="color:var(--yellow);">▶ Chunk '+(i+1)+'/'+total+'</span>';

    // Extract chapter metadata and clean text
    const capMatch=chunks[i].match(/^\[CHAPTER: (.+)\]\n/);
    const capInfo=capMatch?capMatch[1]:'';
    const cleanChunk=chunks[i]
      .replace(/^\[CHAPTER: .+\]\n/,'')
      .replace(/^\[ctx\]/mg,'[CONTEXT — do not analyze, continuity only]');

    const chunkHistory=[
      chatHistory[0],
      {role:'user',content:
        'Fragment '+(i+1)+' of '+total+(capInfo?' — chapter: «'+capInfo+'»':'')+
        ':\n\n'+cleanChunk+
        '\n\n---\nTask: '+prompt+
        '\n\nLines marked [CONTEXT] are the tail of the previous fragment: do not analyze them, they only prevent losing sentences split at the cut.'+
        (capInfo?'\nIf you need to cite the chapter title, use exactly «'+capInfo+'», do not invent other numbering.':'')+
        '\nReply in the same language used in the Task. Never append "Nothing in this fragment" or similar phrases at the end of a real response: that phrase must be used ONLY as the complete and sole response when the fragment is entirely devoid of relevant content.'+
        '\nIf you find nothing relevant in the fragment, reply only: "Nothing in this fragment."'}
    ];

    abort=new AbortController();
    try{
      const res=await fetch(`${API}/v1/chat/completions`,{
        method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,
        body:JSON.stringify({model:'local',messages:chunkHistory,stream:true,
          temperature:currentTemp,top_p:currentTopP,top_k:currentTopK,max_tokens:maxTok(),repeat_penalty:1.1})
      });
      if(!res.ok){let _d='';try{_d=(await res.text()).slice(0,400);}catch(_){}const _srv=res.headers.get('server')||'(no server header)';const _cl=res.headers.get('content-length');const _ct=res.headers.get('content-type')||'?';throw new Error('HTTP '+res.status+' '+(res.statusText||'')+' [server='+_srv+' ct='+_ct+' len='+(_cl==null?'?':_cl)+']'+(_d?' \u2014 '+_d:' \u2014 (empty body)'));}
      prog.bub.innerHTML='';
      const reader=res.body.getReader(),dec=new TextDecoder();
      let full='',t=0;
      while(true){
        const{done,value}=await reader.read();if(done)break;
        for(const line of dec.decode(value).split('\n')){
          if(!line.startsWith('data: '))continue;
          const raw=line.slice(6).trim();if(raw==='[DONE]')continue;
          try{const d=JSON.parse(raw).choices?.[0]?.delta?.content||'';
            if(d){full+=d;t++;_genTok++;prog.bub.textContent=full;scrollBot();}}catch{}
        }
      }
      toks+=t;localStorage.setItem('stoks',toks);
      document.getElementById('tok-tot').textContent=toks.toLocaleString('en');
      const ci=document.createElement('div');ci.className='chunk-info';
      ci.textContent='chunk '+(i+1)+'/'+total+' \xb7 '+t+' tok';
      prog.inner.appendChild(ci);
      // Removes a trailing "nothing in this fragment" added after a real response
      const BLANK_RE=/\b(nothing in this (chunk|fragment)|niente in questo frammento|rien dans ce fragment|nada en este fragmento|nichts in diesem abschnitt)[.…]?\s*$/i;
      const cleaned=full.trim().replace(BLANK_RE,'').trim();
      if(cleaned!==full.trim()) prog.bub.textContent=cleaned;
      // Detects a completely empty response
      const isBlank=!cleaned||/^\s*(nothing|niente|rien|nada|nichts|нет|ingen|niets|inget|nič|semmi|nimic|hiçbir|hakuna)\b/i.test(cleaned);
      // If the current chapter is the same as the previous chunk, it's a continuation
      const prevCapMatch=i>0?chunks[i-1].match(/^\[CHAPTER: (.+)\]\n/):null;
      const isCont=capInfo&&prevCapMatch&&prevCapMatch[1]===capInfo;
      const label=capInfo?('**'+capInfo+(isCont?' (cont.)':'')+'**'):'**Fragment '+(i+1)+'**';
      if(!isBlank) results.push(label+':\n'+cleaned);
    }catch(e){
      if(e.name==='AbortError'){
        prog.bub.textContent='[stopped at chunk '+(i+1)+'/'+total+']';
        interrupted=true;break;
      }
      prog.bub.textContent='Error chunk '+(i+1)+': '+e.message;
      break;
    }
  }

  // Assemble and download — no LLM touches the output
  if(results.length===0){
    addMsg('assistant','No relevant content found in '+total+' chunks.');
  }else{
    const now=new Date();
    const stamp=now.toISOString().slice(0,16).replace('T',' ');
    const fname='selmo-chunks-'+now.toISOString().slice(0,16).replace(/[T:]/g,'-')+'.md';
    const model=document.getElementById('hdr-model').textContent||'local';
    let md='# '+prompt+'\n';
    md+='*'+stamp+' · model: '+model+' · '+results.length+'/'+total+' chunks*\n\n---\n\n';
    md+=results.join('\n\n---\n\n');
    const blob=new Blob([md],{type:'text/markdown'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=fname;
    a.click();
    URL.revokeObjectURL(a.href);
    const done=addMsg('assistant','',false);
    done.bub.innerHTML=
      '\u2713 Done: '+results.length+'/'+total+' chunks assembled.'+
      ' <a href="#" style="color:var(--cyan)" onclick="(()=>{'+
        'const b=new Blob(['+JSON.stringify('')+'],{type:\'text/markdown\'});'+
      '})()">'+fname+'</a>';
    done.bub.textContent='\u2713 Done: '+results.length+'/'+total+' chunks — '+fname+' downloaded.';
    scrollBot();
    chatHistory.push({role:'assistant',content:'\u2713 Done: '+results.length+'/'+total+' chunks — '+fname+' downloaded.'});
    saveSession();
  }

  chunks=[];chunkIdx=0;
  document.getElementById('file-badge').style.display='none';
  gen=false;btn.style.display='inline-block';stopBtn.style.display='none';abort=null;
  setThinkEnabled(true);
  document.getElementById('input').focus();
}
function askFileMode(prompt){
  const tok=Math.ceil(fileDoc.length/3.2);
  const {bub}=addMsg('assistant','',false);
  bub.innerHTML='<div style="margin-bottom:8px"><b>Large file loaded</b> (~'+tok.toLocaleString('en')+' tokens). Process it as a chunked task?<br><span style="opacity:.65">Chunking is for analysis, extraction and translation only \u2014 not for reasoning (\u201Cwhy / explain\u201D) questions.</span></div>';
  const wrap=document.createElement('div');wrap.style.cssText='display:flex;gap:8px;flex-wrap:wrap';
  const mk=(label,primary)=>{const b=document.createElement('button');b.textContent=label;b.style.cssText='font-size:12px;letter-spacing:.04em;padding:5px 12px;cursor:pointer;border-radius:3px;border:1px solid var(--cyan);background:'+(primary?'var(--cyan)':'transparent')+';color:'+(primary?'var(--dark)':'var(--cyan)')+'';return b;};
  const b1=mk('Chunk it',true),b2=mk('Normal chat',false);
  b1.onclick=()=>{wrap.remove();processDoc(prompt);};
  b2.onclick=()=>{wrap.remove();fileChat=fileDoc;fileDoc=null;document.getElementById('file-badge').style.display='none';document.getElementById('input').value=prompt;sendMsg();};
  wrap.appendChild(b1);wrap.appendChild(b2);bub.appendChild(wrap);scrollBot();
}
// VRAM swap coordination (v0.830). Image generation unloads the LLM to run on
// the GPU; the tray control API (8087) is the source of truth. Before a chat
// turn we reload the LLM if it was swapped out -- works even across devices.
async function ensureLLM(){
  let st=null;
  try{ st=await fetch(`${CTRL}/status`,{signal:AbortSignal.timeout(2500)}).then(r=>r.json()); }
  catch(e){ return; }                 // control API down -> assume LLM up, proceed
  if(!st||!st.swapped_for_image)return;
  _reloading=true;                    // a deliberate reload: checkServer shows thumbs, not grey
  const note=addMsg('assistant','',false);
  // animated braille spinner so the reload never looks frozen
  const _spin=['\u280b','\u2819','\u2839','\u2838','\u283c','\u2834','\u2826','\u2827','\u2807','\u280f'];
  let _si=0;
  const _draw=()=>{ note.bub.innerHTML='<span style="color:var(--cyan)">'+_spin[_si=(_si+1)%_spin.length]+'</span> reloading the model after image generation\u2026'; };
  _draw();
  const _timer=setInterval(_draw,120);
  try{
    await fetch(`${CTRL}/llm/reload`,{method:'POST',signal:AbortSignal.timeout(180000)});
    for(let i=0;i<180;i++){
      try{ if((await fetch(`${API}/props`,{signal:AbortSignal.timeout(2000)})).ok)break; }catch(e){}
      await new Promise(r=>setTimeout(r,1000));
    }
  }catch(e){}
  _reloading=false;
  loadProps();          // re-read the real ctx after the model came back
  clearInterval(_timer);
  if(note&&note.wrap)note.wrap.remove();
  setImageMode(false);
}
