'use strict';
function getSessions(){
  try{return JSON.parse(localStorage.getItem(SESS_KEY)||'[]');}catch{return [];}
}
function sessionTitle(){
  const first=chatHistory.slice(1).find(m=>m.role==='user');
  if(!first)return null;
  const raw=Array.isArray(first.content)
    ?(first.content.find(p=>p.type==='text')||{text:''}).text
    :first.content;
  return raw
    .replace(/^\[Attached file\][\s\S]*?\n\n---\n\n/,'')  // strip file header, keep user prompt
    .replace(/^Web search results[\s\S]*?\n\n/,'')
    .replace(/^\/web\s+/i,'')
    .replace(/^Current date\/time:[^\n]*\n\n/,'')
    .slice(0,50).trim()||'(chat)';
}
// Image mode = the LLM is unloaded for image generation. WEB and THINK need the
// LLM, so grey them out until the next chat reloads it.
function setImageMode(on){
  ['web-btn','think-btn'].forEach(id=>{ const b=document.getElementById(id); if(b)b.disabled=!!on; });
}
function toggleWeb(){
  IS_WEB_ON=!IS_WEB_ON;
  const btn=document.getElementById('web-btn');
  if(btn){btn.classList.toggle('on',IS_WEB_ON);btn.textContent=IS_WEB_ON?'WEB ●':'WEB';}
}
// Reduce a live chatHistory message to a small, JSON-safe record for storage.
// Base64 image data is dropped (kept only as an image COUNT): full-res images in
// localStorage overflowed the phone quota, so the whole session save threw and
// the conversation vanished. The live session keeps its thumbnails in the DOM;
// only reloaded-from-history turns show a placeholder marker.
function storableMsg(m){
  if(Array.isArray(m.content)){
    const imgs=m.content.filter(p=>p&&p.type==='image_url').length;
    const txt=(m._orig!=null)?m._orig
      :m.content.filter(p=>p&&p.type==='text').map(p=>(p&&p.text)||'').join('\n');
    const r={role:m.role,content:String(txt==null?'':txt)};
    if(imgs)r.imgs=imgs;
    return r;
  }
  // User turns: the bubble shows clean text while content may carry injected
  // web/doc context — store the clean text (_orig) so reloaded bubbles read
  // cleanly. Assistant turns have no _orig: keep full content ([THINK] + answer).
  let c=(m.role==='user'&&m._orig!=null)?m._orig:m.content;
  const r={role:m.role,content:(c==null?'':String(c))};
  if(m.imgs)r.imgs=m.imgs;
  return r;
}
function saveSession(){
  const msgs=chatHistory.slice(1);
  if(!msgs.length)return;
  const title=sessionTitle();if(!title)return;
  let sessions=getSessions();
  const idx=sessions.findIndex(s=>s.id===currentSessionId);
  const entry={id:currentSessionId,date:new Date().toISOString().slice(0,16),title,history:msgs.map(storableMsg)};
  if(idx>=0){sessions[idx]=entry;}else{sessions.unshift(entry);}
  while(sessions.length>MAX_SESS)sessions.pop();
  // Persist. If the quota is hit, evict the oldest OTHER session and retry, so
  // the current conversation is never the one dropped (and never silently).
  while(true){
    try{localStorage.setItem(SESS_KEY,JSON.stringify(sessions));break;}
    catch(e){
      let i=sessions.length-1;
      for(;i>=0;i--){if(sessions[i].id!==currentSessionId)break;}
      if(i<0){console.warn('session save failed (quota) even alone',e);break;}
      sessions.splice(i,1);
    }
  }
  renderSessionList();
}
// Render one stored turn. A saved turn may be a clean record
// {role,content:<string>,imgs?}, an assistant string carrying
// [THINK]reasoning[/THINK]answer, or (legacy sessions) a raw multimodal array.
// Everything is normalized to a string + an image count, so the bubble can
// never show [object Object] and text is never lost; dropped images render as a
// placeholder marker.
function renderStored(m){
  let role=m.role, content=m.content, imgs=m.imgs||0;
  if(Array.isArray(content)){
    imgs=imgs||content.filter(p=>p&&p.type==='image_url').length;
    content=(m._orig!=null)?m._orig
      :content.filter(p=>p&&p.type==='text').map(p=>(p&&p.text)||'').join('\n');
  } else if(content==null){ content=''; }
  else if(typeof content!=='string'){ content=String(content); }
  if(role==='assistant'){
    const a=content.indexOf('[THINK]'), b=content.indexOf('[/THINK]');
    let reason='', answer=content;
    if(a!==-1&&b>a){ reason=content.slice(a+7,b); answer=(content.slice(0,a)+content.slice(b+8)).trim(); }
    const r=addMsg('assistant','',false);
    if(reason){ const tp=makeThinkPanel(r.inner); tp.append(reason); tp.seal(); }
    try{ r.bub.innerHTML=marked.parse(answer); }catch(_){ r.bub.textContent=answer; }
    addDownloadBar(r.bub,r.inner,answer);
    return;
  }
  const prefix=imgs?('🖼️ '+(imgs>1?'['+imgs+'p] ':'')):'';
  addMsg(role, prefix+content, false);
}
function loadSession(id){
  if(gen)return;
  saveSession();
  const s=getSessions().find(x=>x.id===id);
  if(!s)return;
  currentSessionId=id;
  chatHistory.length=1;
  s.history.forEach(m=>chatHistory.push(m));
  syncSampling();
  syncThinkPrompt();
  document.getElementById('messages').innerHTML='';
  document.getElementById('messages').appendChild(traceLine()); // keep the model/params trace when viewing history
  s.history.forEach(renderStored);
  wh=0;sessStart=Date.now();clearFile();updCost();
  scrollBot();
  renderSessionList();
}
function deleteSession(e,id){
  e.stopPropagation();
  const sessions=getSessions().filter(s=>s.id!==id);
  try{localStorage.setItem(SESS_KEY,JSON.stringify(sessions));}catch{}
  if(id===currentSessionId){
    currentSessionId=(()=>Date.now().toString(36)+Math.random().toString(36).slice(2,6))();
  }
  renderSessionList();
}
function renderSessionList(){
  const list=document.getElementById('session-list');
  if(!list)return;
  const sessions=getSessions();
  list.innerHTML='';
  if(!sessions.length){
    const empty=document.createElement('div');
    empty.style.cssText='font-size:11px;color:var(--dim);padding:4px 2px;';
    empty.textContent='no saved sessions';
    list.appendChild(empty);
    return;
  }
  for(const s of sessions){
    const item=document.createElement('div');
    item.className='sess-item'+(s.id===currentSessionId?' active':'');
    const title=document.createElement('div');title.className='sess-title';title.textContent=s.title;
    const date=document.createElement('div');date.className='sess-date';date.textContent=s.date.replace('T',' ');
    const del=document.createElement('span');del.className='sess-del';del.textContent='\xd7';
    del.addEventListener('click',e=>deleteSession(e,s.id));
    item.appendChild(title);item.appendChild(date);item.appendChild(del);
    item.addEventListener('click',()=>loadSession(s.id));
    list.appendChild(item);
  }
}
// ── Mobile overlay toggle ──────────────────────────────────────────────
function mobToggle(which){
  const nav=document.querySelector('nav');
  const aside=document.querySelector('aside');
  const overlay=document.getElementById('mob-overlay');
  const navBtn=document.getElementById('mob-nav-btn');
  const dashBtn=document.getElementById('mob-dash-btn');
  if(which==='nav'){
    const opening=!nav.classList.contains('open');
    aside.classList.remove('open'); dashBtn.classList.remove('open');
    nav.classList.toggle('open',opening);
    navBtn.classList.toggle('open',opening);
    overlay.classList.toggle('show',opening);
  } else {
    const opening=!aside.classList.contains('open');
    nav.classList.remove('open'); navBtn.classList.remove('open');
    aside.classList.toggle('open',opening);
    dashBtn.classList.toggle('open',opening);
    overlay.classList.toggle('show',opening);
  }
}
function closeOverlays(){
  document.querySelector('nav').classList.remove('open');
  document.querySelector('aside').classList.remove('open');
  document.getElementById('mob-overlay').classList.remove('show');
  document.getElementById('mob-nav-btn').classList.remove('open');
  document.getElementById('mob-dash-btn').classList.remove('open');
}
// Mic needs a secure context. Browsers treat localhost as secure but a LAN IP
// over plain HTTP is not, so on the phone at http://<ip>:8080 getUserMedia (and
// the VAD library) are blocked. Show a one-tap link to the HTTPS front door
// (8443), which serves this same page over TLS. See BUG-MIC-01.
function _micHttpsBanner(){
  try{
    var h=location.hostname;
    var local=(h==='localhost'||h==='127.0.0.1'||h==='::1'||h==='');
    if(window.isSecureContext||local)return;
    if(document.getElementById('mic-https-banner'))return;
    var url='https://'+h+':8443'+location.pathname+location.search;
    var b=document.createElement('div');
    b.id='mic-https-banner';
    b.style.cssText='position:sticky;top:0;z-index:99999;background:#3a2a00;'
      +'color:#ffcc66;border-bottom:1px solid #6b5300;padding:8px 12px;'
      +'font-size:13px;line-height:1.4;text-align:center;font-family:inherit';
    b.innerHTML='\uD83C\uDFA4 Microphone needs HTTPS on a phone. '
      +'<a href="'+url+'" style="color:#ffe28a;text-decoration:underline;'
      +'font-weight:bold">Open the secure page \u2192</a>'
      +' <span style="opacity:.7;cursor:pointer" onclick="this.parentNode.remove()">\u2715</span>';
    document.body.insertBefore(b,document.body.firstChild);
  }catch(e){}
}
