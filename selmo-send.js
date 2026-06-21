'use strict';
async function sendMsg(){
  if(gen)return;
  const inp=document.getElementById('input');
  const btn=document.getElementById('send');
  const stopBtn=document.getElementById('stop');
  const txt=inp.value.trim();if(!txt)return;
  inp.value='';inp.style.height='auto';

  // VRAM swap (v0.830): if image generation unloaded the LLM, bring it back
  // before this chat turn. No-op in the normal case (one fast /status check).
  await ensureLLM();

  if(fileDoc){
    // Threshold: if the file exceeds 50% of the model's window we ask
    // whether to treat it as chunks (analysis) or keep it in normal chat (reasoning).
    if(Math.ceil(fileDoc.length/3.2) > N_CTX*0.5){ askFileMode(txt); return; }
    // Fits in the window: normal chat, document injected as context.
    fileChat=fileDoc; fileDoc=null;
    document.getElementById('file-badge').style.display='none';
  }

  gen=true;_genT0=Date.now();_genTok=0;btn.style.display='none';stopBtn.style.display='inline-block';
  abort=new AbortController();

  // Web access is EXPLICIT only: nothing leaves localhost unless the user types /web.
  // Local date/time stays automatic — it is read from this machine's clock, it never leaves.
  // /think: toggle extended reasoning


  let isWebSearch=false;
  let webQuery='';
  if(IS_WEB_ON&&txt.trim().length>0){
    if(!webOk){addMsg('assistant','⚠ Web bridge not active — start selmo_web.py to use web search.');endTurn();return;}
    isWebSearch=true;
    webQuery=txt.trim();
  }
  const isDateTimeQuery=!isWebSearch&&/^\s*(che (giorno|ora)|what (day|date|time)|date|time|day)\b[^\n]*\??$/i.test(txt);

  let content=txt;
  let proactiveSources=[];
  let imgDbg=null;

  function endTurn(){gen=false;btn.style.display='inline-block';stopBtn.style.display='none';abort=null;inp.focus();if(vadConvo&&vadAwaitingReply){setTimeout(function(){if(vadConvo&&vadAwaitingReply&&!_ttsPending&&!gen)vadResume();},200);}}

  if(isDateTimeQuery&&webOk){
    try{
      const dtr=await fetch(`${WEB}/datetime`,{signal:AbortSignal.timeout(3000)});
      const dtd=await dtr.json();
      content=`Current date/time: ${dtd.datetime}\n\n`+content;
    }catch{/* bridge down — proceed without datetime */}
  }

  if(isWebSearch){
    const um=addMsg('user',(fileImage?(fileImage.pages>1?'\uD83D\uDDBC\uFE0F ['+fileImage.pages+'p] ':'\uD83D\uDDBC\uFE0F '):'')+txt);
    const{bub,inner}=addMsg('assistant','',true);
    const whStart=wh;
    bub.innerHTML=`<span style="color:var(--yellow)">&#x1F50D; Preparing search...</span>`;
    scrollBot();
    try{
      const rawQuery=webQuery;
      // STEP 1 — image: ask the model to describe the image AND emit a SEARCH: query.
      // STEP 1 — doc:   pass a text snippet to rewriteQuery so the query is doc-aware.
      const _docCtx=fileChat?fileChat.slice(0,1500):'';
      let _imgAnalysis='';
      if(fileImage){
        bub.innerHTML=`<span style="color:var(--yellow)">&#x1F50D; Reading image...</span>`;
        scrollBot();
        try{
          const _urls=fileImage.dataUrls;
          const _imgMsg=_urls.map(u=>({type:'image_url',image_url:{url:u}}));
          // BUG-WEB-IMG-01 fix: analyse the image AND compose the query in ONE call,
          // with the user's question sitting next to the pixels. The old "describe
          // everything (600 tok) -> hand the wall of text to rewriteQuery" split lost
          // the link between the question and the one element it was about, so the
          // rewriter fell back to paraphrasing the user's vague words. Forcing a
          // structured SEEN/QUERY answer plus one worked example makes the model read
          // the concrete identifiers off the image first, then build the query from them.
          _imgMsg.push({type:'text',text:
            'You are preparing a web search to answer the user\'s question about this image.\n'
            +'User question: "'+rawQuery+'"\n\n'
            +'Read the image and pull out the concrete things a search engine needs: exact '
            +'product / brand / model names, software or OS name and version, menu / tab / setting '
            +'names, error codes or messages, and any other visible text tied to the question. '
            +'Then write ONE search query that joins those real, image-specific terms with what the '
            +'user wants to know. Do not fall back on the user\'s vague wording when the image gives a '
            +'precise term. Keep the user\'s language.\n\n'
            +'Reply in EXACTLY this format and nothing else:\n'
            +'SEEN: <the key identifiers you can read in the image>\n'
            +'QUERY: <the search query>\n\n'
            +'Example (image shows a camera menu, user asks "what does this setting do"):\n'
            +'SEEN: Canon EOS R6, Shooting menu, "Highlight tone priority" set to D+\n'
            +'QUERY: Canon EOS R6 Highlight tone priority D+ what it does'});
          const _callImg=extra=>fetch(`${API}/v1/chat/completions`,{
            method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(60000),
            body:JSON.stringify(Object.assign({model:'local',messages:[{role:'user',content:_imgMsg}],
              stream:false,temperature:0.2,top_p:0.9,max_tokens:800,repeat_penalty:1.1},extra))
          });
          let _ar=await _callImg({chat_template_kwargs:{enable_thinking:false}});
          if(!_ar.ok) _ar=await _callImg({}); // server rejects the kwarg -> retry plain
          if(_ar.ok){
            const _ad=await _ar.json();
            const _m=(_ad.choices&&_ad.choices[0]&&_ad.choices[0].message)||{};
            const _body=((_m.content||'')+'\n'+(_m.reasoning_content||''))
              .replace(/<think>[\s\S]*?<\/think>/gi,'').replace(/\[THINK\][\s\S]*?\[\/THINK\]/gi,'');
            const _sm=_body.match(/SEEN\s*[:：]\s*([\s\S]*?)(?:\n\s*QUERY\s*[:：]|$)/i);
            const _qm=_body.match(/QUERY\s*[:：]\s*(.+)/i);
            _imgAnalysis=(_sm?_sm[1]:'').trim();
            const _q=(_qm?_qm[1]:'').replace(/["'`]/g,'').trim();
            console.log('[img-query] SEEN',JSON.stringify(_imgAnalysis.slice(0,200)),'| QUERY',JSON.stringify(_q));
            if(_q.length>=2) webQuery=_q;
            else webQuery=await rewriteQuery(rawQuery,chatHistory,_imgAnalysis.slice(0,1500)); // no QUERY line -> fall back to text rewriter
          }
        }catch(_e){console.warn('image analysis failed',_e);}
      }else{
        webQuery=await rewriteQuery(rawQuery,chatHistory,_docCtx);
      }
      if(fileImage){ // visible proof the image->query step ran and what it produced (no console needed)
        const _dbg=document.createElement('div');_dbg.className='tok-meta';_dbg.style.color='var(--yellow)';
        _dbg.textContent='\u26A1 img\u2192query: "'+webQuery+'"'+(webQuery===rawQuery?'  (RAW \u2014 image step did NOT rewrite it)':'');
        um.inner.appendChild(_dbg);scrollBot();
      }
      const _eq=webQuery.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      bub.innerHTML=`<span style="color:var(--yellow)">&#x1F50D; Searching: <em>${_eq}</em>...</span>`;
      scrollBot();
      const results=await webSearch(webQuery,5);
      if(!results.length){
        bub.textContent='No results for "'+webQuery+'".';
        endTurn();return;
      }
      proactiveSources=results;
      const formatted=results.map((r,i)=>
        '['+(i+1)+'] '+r.title+'\n'+r.url+'\n'+(r.snippet||'—')
      ).join('\n\n');
      const recentClean=chatHistory
        .filter(m=>m.role!=='system')
        .slice(-4)
        .map(m=>{
          const role=m.role==='user'?'User':'Selmo';
          let raw=m._orig;
          if(raw==null){
            raw=m.content;
            if(Array.isArray(raw)) raw=raw.filter(p=>p&&p.type==='text').map(p=>p.text).join(' ');
          }
          const c=String(raw||'').replace(/\[THINK\][\s\S]*?\[\/THINK\]/g,'').trim().slice(0,400);
          return role+': '+c;
        }).join('\n');
      const _hasDoc=!!fileChat;
      const _hasImg=!!fileImage;
      const ctxMsg=(recentClean?'Recent conversation:\n'+recentClean+'\n\n':'')
        +(_hasDoc?'Attached document:\n'+fileChat+'\n\n':'')
        +(_imgAnalysis?'Image analysis:\n'+_imgAnalysis+'\n\n':'')
        +'Web search results for: '+webQuery+'\n\n'+formatted
        +'\n\nBased on the image analysis'+((_hasDoc||_hasImg)?' and attached document/image':'')+' and the web search results above, answer the user\'s latest message directly in the same language. Be specific and useful. Cite sources as [1], [2], etc.';
      if(fileImage){
        const urls=fileImage.dataUrls;
        const imgContent=urls.map(u=>({type:'image_url',image_url:{url:u}}));
        imgContent.push({type:'text',text:ctxMsg});
        chatHistory.push({role:'user',content:imgContent,_orig:txt});
        um.inner.appendChild(imgThumbStrip(urls));
        fileImage=null;
        fileChat=null; // clear doc too if both were loaded
        document.getElementById('file-badge').style.display='none';
      }else{
        chatHistory.push({role:'user',content:ctxMsg,_orig:txt});
        fileChat=null; // clear doc after web+doc search
        document.getElementById('file-badge').style.display='none';
      }
      bub.innerHTML='<span style="opacity:.5">&#x25CA;</span>';
      abort=new AbortController();
      const res=await fetch(`${API}/v1/chat/completions`,{
        method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,
        body:JSON.stringify(Object.assign({model:'local',messages:apiMessages(),stream:true,
          temperature:currentTemp,top_p:currentTopP,top_k:currentTopK,max_tokens:maxTok(),repeat_penalty:1.1},thinkKwargs()))
      });
      if(!res.ok){let _d='';try{_d=(await res.text()).slice(0,400);}catch(_){}const _srv=res.headers.get('server')||'(no server header)';const _cl=res.headers.get('content-length');const _ct=res.headers.get('content-type')||'?';throw new Error('HTTP '+res.status+' '+(res.statusText||'')+' [server='+_srv+' ct='+_ct+' len='+(_cl==null?'?':_cl)+']'+(_d?' \u2014 '+_d:' \u2014 (empty body)'));}
      bub.innerHTML='';
      let full='',rthink='',t=0;
      const tp=makeThinkPanel(inner);
      await streamTokens(res,
        c=>{full+=c;t++;_genTok++;bub.textContent=full;scrollBot();},
        r=>{_genTok++;if(!IS_THINK_ON){full+=r;t++;bub.textContent=full;scrollBot();return;}if(!rthink)markThinking();rthink+=r;tp.append(r);});
      tp.seal();
      bub.innerHTML=marked.parse(full);addDownloadBar(bub,inner,full);
      toks+=t;localStorage.setItem('stoks',toks);
      document.getElementById('tok-tot').textContent=toks.toLocaleString('en');
      chatHistory.push({role:'assistant',content:(rthink?'[THINK]'+rthink+'[/THINK]':'')+full});
      const ledger=document.createElement('div');ledger.className='tok-meta';
      const _rq=rawQuery.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      ledger.innerHTML='&#x1F50E; <span title="query sent to the engine">“'+_eq+'”</span>'
        +(rawQuery!==webQuery?' <span style="opacity:.55">← '+_rq+'</span>':'')+'<br>'
        +'&#x1F310; '+results.map((r,i)=>
        '<a href="'+r.url+'" target="_blank" rel="noopener" style="color:var(--cyan);text-decoration:none">['+(i+1)+'] '+r.title+'</a>'
      ).join(' \xb7 ')+' \xb7 '+t+' tok \xb7 '+(wh-whStart).toFixed(4)+' Wh';
      inner.appendChild(ledger);
      saveSession();
      speakText(full);
    }catch(e){
      if(e.name!=='AbortError'){bub.textContent='Error: '+e.message;bub.style.borderColor='var(--red)';}
      else{bub.textContent=bub.textContent||'[stopped]';}
    }
    endTurn();return;
  }

  // NORMAL CHAT PATH
  // Multimodal: if an image is loaded, use a content array
  if(fileImage){
    const urls=fileImage.dataUrls;
    const imgContent=urls.map(u=>({type:'image_url',image_url:{url:u}}));
    imgContent.push({type:'text',text:content});
    chatHistory.push({role:'user',content:imgContent});
    const tag=fileImage.pages>1?'🖼️ ['+fileImage.pages+'p] ':'🖼️ ';
    const um=addMsg('user',tag+content);
    // Thumbnail of what is being sent: click to open at full resolution
    um.inner.appendChild(imgThumbStrip(urls));
    // DIAGNOSTICS BUG-IMG-02: payload size and format, visible on screen
    // (useful on phone where the console can't be read). Shows total KB, image count,
    // data URL prefix (must be data:image/jpeg;base64,...).
    const _kb=Math.round(urls.reduce((a,u)=>a+u.length,0)*0.75/1024);
    const _bodyKB=Math.round(JSON.stringify(chatHistory).length/1024);
    const _pre=(urls[0]||'(empty)').slice(0,32);
    imgDbg=document.createElement('div');imgDbg.className='tok-meta';
    imgDbg.style.color='var(--yellow)';
    imgDbg.textContent='\u26A1 img '+urls.length+' \xb7 immagini ~'+_kb+'KB \xb7 body ~'+_bodyKB+'KB \xb7 '+_pre;
    um.inner.appendChild(imgDbg);
    fileImage=null;
    document.getElementById('file-badge').style.display='none';
  } else {
    let apiContent=content;
    if(fileChat){apiContent='[Attached file]\n\n'+fileChat+'\n\n---\n\n'+content;fileChat=null;}
    chatHistory.push({role:'user',content:apiContent,_orig:content});
    addMsg('user',content);
  }
  const{bub,inner}=addMsg('assistant','',true);
  const whStart=wh;
  try{
    const res=await fetch(`${API}/v1/chat/completions`,{
      method:'POST',headers:{'Content-Type':'application/json'},signal:abort.signal,
      body:JSON.stringify(Object.assign({model:'local',messages:apiMessages(),stream:true,
        temperature:currentTemp,top_p:currentTopP,top_k:currentTopK,max_tokens:maxTok(),repeat_penalty:1.1},thinkKwargs()))
    });
    if(!res.ok){let _d='';try{_d=(await res.text()).slice(0,400);}catch(_){}const _srv=res.headers.get('server')||'(no server header)';const _cl=res.headers.get('content-length');const _ct=res.headers.get('content-type')||'?';throw new Error('HTTP '+res.status+' '+(res.statusText||'')+' [server='+_srv+' ct='+_ct+' len='+(_cl==null?'?':_cl)+']'+(_d?' \u2014 '+_d:' \u2014 (empty body)'));}
    bub.innerHTML='';
    let full='',rthink='',t=0;
    const tp=makeThinkPanel(inner);
    await streamTokens(res,
      c=>{full+=c;t++;_genTok++;bub.textContent=full;scrollBot();},
      r=>{_genTok++;if(!IS_THINK_ON){full+=r;t++;bub.textContent=full;scrollBot();return;}if(!rthink)markThinking();rthink+=r;tp.append(r);});
    tp.seal();
    bub.innerHTML=marked.parse(full);addDownloadBar(bub,inner,full);
    toks+=t;localStorage.setItem('stoks',toks);
    document.getElementById('tok-tot').textContent=toks.toLocaleString('en');
    chatHistory.push({role:'assistant',content:(rthink?'[THINK]'+rthink+'[/THINK]':'')+full});
    const meta=document.createElement('div');meta.className='tok-meta';
    meta.textContent=t+' tok \xb7 '+(wh-whStart).toFixed(4)+' Wh';
    inner.appendChild(meta);
    saveSession();
    speakText(full);
  }catch(e){
    if(e.name!=='AbortError'){
      bub.textContent='Error: '+e.message;bub.style.borderColor='var(--red)';bub.style.color='var(--red)';chatHistory.pop();
      if(imgDbg){imgDbg.textContent+='  \u2192 fetch fallita: '+e.message;}
    }
    else{bub.textContent=bub.textContent||'[stopped]';}
  }
  endTurn();
}
// ── Push-to-Talk (Spazio o tasto centrale mouse) ─────────────────────────────
function isTypingFocus(){
  const el=document.activeElement;
  return el&&(el.tagName==='TEXTAREA'||el.tagName==='INPUT'||el.isContentEditable);
}
