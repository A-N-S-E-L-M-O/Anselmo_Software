'use strict';
// --- Local QR code generator (byte mode, ECC L/M/Q/H, auto version+mask). ---
// Self-contained, offline: builds a scannable QR of any short string (used for
// the phone-access URL). Algorithm after Project Nayuki's QR generator (MIT).
// Verified: versions 1-7 decode cleanly; the phone URL is ~38 chars (version 3).
function selmoQrMatrix(text, eclName){
  var ECC={L:0,M:1,Q:2,H:3}, ecl=ECC[eclName]!==undefined?ECC[eclName]:ECC.M;
  var ECC_FORMAT=[1,0,3,2];
  var ECC_CW=[
    [0,7,10,15,20,26,18,20,24,30,18,20,24,26,30,22,24,28,30,28,28,28,28,30,30,26,28,30,30,30,30,30,30,30,30,30,30,30,30,30,30],
    [0,10,16,26,18,24,16,18,22,22,26,30,22,22,24,24,28,28,26,26,26,26,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28],
    [0,13,22,18,26,18,24,18,22,20,24,28,26,24,20,30,24,28,28,26,30,28,30,30,30,30,28,30,30,30,30,30,30,30,30,30,30,30,30,30,30],
    [0,17,28,22,16,22,28,26,26,24,28,24,28,22,24,24,30,28,28,26,28,30,24,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30]];
  var ECC_BLK=[
    [0,1,1,1,1,1,2,2,2,2,4,4,4,4,4,6,6,6,6,7,8,8,9,9,10,12,12,12,13,14,15,16,17,18,19,19,20,21,22,24,25],
    [0,1,1,1,2,2,4,4,4,5,5,5,8,9,9,10,10,11,13,14,16,17,17,18,20,21,23,25,26,28,29,31,33,35,37,38,40,43,45,47,49],
    [0,1,1,2,2,4,4,6,6,8,8,8,10,12,16,12,17,16,18,21,20,23,23,25,27,29,34,34,35,38,40,43,45,48,51,53,56,59,62,65,68],
    [0,1,1,2,4,4,4,5,6,8,8,11,11,16,16,18,16,19,21,25,25,25,34,30,32,35,37,40,42,45,48,51,54,57,60,63,66,70,74,77,81]];
  function mul(x,y){var z=0;for(var i=7;i>=0;i--){z=(z<<1)^((z>>>7)*0x11D);z^=((y>>>i)&1)*x;}return z&0xFF;}
  function rsDiv(deg){var r=[];for(var i=0;i<deg;i++)r.push(0);r[deg-1]=1;var root=1;
    for(var i=0;i<deg;i++){for(var j=0;j<r.length;j++){r[j]=mul(r[j],root);if(j+1<r.length)r[j]^=r[j+1];}root=mul(root,2);}return r;}
  function rsRem(data,div){var r=div.map(function(){return 0;});data.forEach(function(b){var f=b^r.shift();r.push(0);div.forEach(function(c,i){r[i]^=mul(c,f);});});return r;}
  function rawMods(v){var r=(16*v+128)*v+64;if(v>=2){var a=Math.floor(v/7)+2;r-=(25*a-10)*a-55;if(v>=7)r-=36;}return r;}
  function dataCw(v){return Math.floor(rawMods(v)/8)-ECC_CW[ecl][v]*ECC_BLK[ecl][v];}
  function alignPos(v){if(v===1)return [];var a=Math.floor(v/7)+2,step=(v===32)?26:Math.ceil((v*4+4)/(a*2-2))*2,r=[6];
    for(var p=v*4+10;r.length<a;p-=step)r.splice(1,0,p);return r;}
  var bytes=[];
  for(var i=0;i<text.length;i++){var c=text.charCodeAt(i);
    if(c<0x80)bytes.push(c);
    else if(c<0x800)bytes.push(0xC0|(c>>6),0x80|(c&0x3F));
    else if(c>=0xD800&&c<0xDC00&&i+1<text.length){var c2=text.charCodeAt(++i),cp=0x10000+((c-0xD800)<<10)+(c2-0xDC00);bytes.push(0xF0|(cp>>18),0x80|((cp>>12)&0x3F),0x80|((cp>>6)&0x3F),0x80|(cp&0x3F));}
    else bytes.push(0xE0|(c>>12),0x80|((c>>6)&0x3F),0x80|(c&0x3F));}
  var ver;
  for(ver=1;ver<=40;ver++){var cc=(ver<=9)?8:16;if(4+cc+bytes.length*8<=dataCw(ver)*8)break;}
  if(ver>40)throw new Error('QR: data too long');
  var ccBits=(ver<=9)?8:16, bits=[];
  function put(val,len){for(var i=len-1;i>=0;i--)bits.push((val>>>i)&1);}
  put(4,4);put(bytes.length,ccBits);bytes.forEach(function(b){put(b,8);});
  var cap=dataCw(ver)*8;
  put(0,Math.min(4,cap-bits.length));
  while(bits.length%8!==0)bits.push(0);
  for(var pad=0xEC;bits.length<cap;pad^=0xEC^0x11)put(pad,8);
  var dcw=[];for(var i=0;i<bits.length;i+=8){var b=0;for(var j=0;j<8;j++)b=(b<<1)|bits[i+j];dcw.push(b);}
  var nb=ECC_BLK[ecl][ver], el=ECC_CW[ecl][ver], raw=Math.floor(rawMods(ver)/8);
  var nsh=nb-raw%nb, shl=Math.floor(raw/nb), div=rsDiv(el), blks=[], k=0;
  for(var i=0;i<nb;i++){var dl=shl-el+(i<nsh?0:1),dat=dcw.slice(k,k+dl);k+=dl;blks.push({dat:dat,ecc:rsRem(dat,div)});}
  var cw=[], maxd=shl-el+1;
  for(var i=0;i<maxd;i++)for(var b=0;b<blks.length;b++)if(i<blks[b].dat.length)cw.push(blks[b].dat[i]);
  for(var i=0;i<el;i++)for(var b=0;b<blks.length;b++)cw.push(blks[b].ecc[i]);
  var n=ver*4+17, mods=[], fn=[];
  for(var y=0;y<n;y++){mods.push(new Array(n).fill(false));fn.push(new Array(n).fill(false));}
  function sf(x,y,d){mods[y][x]=d;fn[y][x]=true;}
  function finder(cx,cy){for(var dy=-4;dy<=4;dy++)for(var dx=-4;dx<=4;dx++){var x=cx+dx,y=cy+dy;if(x<0||x>=n||y<0||y>=n)continue;var d=Math.max(Math.abs(dx),Math.abs(dy));sf(x,y,d!==2&&d!==4);}}
  finder(3,3);finder(n-4,3);finder(3,n-4);
  for(var i=0;i<n;i++){if(!fn[6][i])sf(i,6,i%2===0);if(!fn[i][6])sf(6,i,i%2===0);}
  var ap=alignPos(ver);
  for(var a=0;a<ap.length;a++)for(var b=0;b<ap.length;b++){var cx=ap[a],cy=ap[b];
    if((cx<=8&&cy<=8)||(cx<=8&&cy>=n-9)||(cx>=n-9&&cy<=8))continue;
    for(var dy=-2;dy<=2;dy++)for(var dx=-2;dx<=2;dx++)sf(cx+dx,cy+dy,Math.max(Math.abs(dx),Math.abs(dy))!==1);}
  for(var i=0;i<=8;i++){if(i!==6){fn[8][i]=true;fn[i][8]=true;}}
  for(var i=0;i<8;i++){fn[8][n-1-i]=true;fn[n-1-i][8]=true;}
  fn[8][8]=true;sf(8,n-8,true);
  if(ver>=7){var rem=ver;for(var i=0;i<12;i++)rem=(rem<<1)^((rem>>>11)*0x1F25);var vb=(ver<<12)|rem;
    for(var i=0;i<18;i++){var bit=((vb>>>i)&1)===1,a=Math.floor(i/3),c=i%3;sf(n-11+c,a,bit);sf(a,n-11+c,bit);}}
  var bi=0;function gb(){if(bi>=cw.length*8)return false;var v=(cw[bi>>3]>>>(7-(bi&7)))&1;bi++;return v===1;}
  for(var right=n-1;right>=1;right-=2){if(right===6)right=5;
    for(var vert=0;vert<n;vert++)for(var jj=0;jj<2;jj++){var x=right-jj,up=((right+1)&2)===0,y=up?(n-1-vert):vert;if(!fn[y][x])mods[y][x]=gb();}}
  function mask(m,x,y){switch(m){case 0:return (x+y)%2===0;case 1:return y%2===0;case 2:return x%3===0;case 3:return (x+y)%3===0;
    case 4:return (Math.floor(x/3)+Math.floor(y/2))%2===0;case 5:return (x*y)%2+(x*y)%3===0;case 6:return ((x*y)%2+(x*y)%3)%2===0;case 7:return ((x+y)%2+(x*y)%3)%2===0;}}
  function fmt(m){var d=(ECC_FORMAT[ecl]<<3)|m,rem=d;for(var i=0;i<10;i++)rem=(rem<<1)^((rem>>>9)*0x537);var bits=((d<<10)|rem)^0x5412;
    for(var i=0;i<=5;i++)mods[i][8]=((bits>>>i)&1)===1;mods[7][8]=((bits>>>6)&1)===1;mods[8][8]=((bits>>>7)&1)===1;mods[8][7]=((bits>>>8)&1)===1;
    for(var i=9;i<15;i++)mods[8][14-i]=((bits>>>i)&1)===1;
    for(var i=0;i<8;i++)mods[8][n-1-i]=((bits>>>i)&1)===1;for(var i=8;i<15;i++)mods[n-15+i][8]=((bits>>>i)&1)===1;mods[n-8][8]=true;}
  function applyMask(m){for(var y=0;y<n;y++)for(var x=0;x<n;x++)if(!fn[y][x]&&mask(m,x,y))mods[y][x]=!mods[y][x];}
  function penalty(){var p=0;
    for(var y=0;y<n;y++){var r=1;for(var x=1;x<n;x++){if(mods[y][x]===mods[y][x-1]){r++;if(r===5)p+=3;else if(r>5)p++;}else r=1;}}
    for(var x=0;x<n;x++){var r=1;for(var y=1;y<n;y++){if(mods[y][x]===mods[y-1][x]){r++;if(r===5)p+=3;else if(r>5)p++;}else r=1;}}
    for(var y=0;y<n-1;y++)for(var x=0;x<n-1;x++){var c=mods[y][x];if(c===mods[y][x+1]&&c===mods[y+1][x]&&c===mods[y+1][x+1])p+=3;}
    var pat=[true,false,true,true,true,false,true];
    function chk(arr){var cnt=0;for(var i=0;i+7<=arr.length;i++){var ok=true;for(var j=0;j<7;j++)if(arr[i+j]!==pat[j])ok=false;
      if(ok){var b1=(i>=4)&&!arr[i-1]&&!arr[i-2]&&!arr[i-3]&&!arr[i-4];var b2=(i+11<=arr.length)&&!arr[i+7]&&!arr[i+8]&&!arr[i+9]&&!arr[i+10];if(b1||b2)cnt++;}}return cnt;}
    for(var y=0;y<n;y++){var row=[];for(var x=0;x<n;x++)row.push(mods[y][x]);p+=40*chk(row);}
    for(var x=0;x<n;x++){var col=[];for(var y=0;y<n;y++)col.push(mods[y][x]);p+=40*chk(col);}
    var dark=0;for(var y=0;y<n;y++)for(var x=0;x<n;x++)if(mods[y][x])dark++;
    p+=Math.floor(Math.abs(dark*20-n*n*10)/(n*n))*10;return p;}
  var base=mods.map(function(r){return r.slice();}), best=0, bestS=Infinity;
  for(var m=0;m<8;m++){for(var y=0;y<n;y++)for(var x=0;x<n;x++)mods[y][x]=base[y][x];applyMask(m);fmt(m);var s=penalty();if(s<bestS){bestS=s;best=m;}}
  for(var y=0;y<n;y++)for(var x=0;x<n;x++)mods[y][x]=base[y][x];applyMask(best);fmt(best);
  return {size:n,modules:mods,version:ver};
}
// Render a QR of `url` onto a fresh canvas element and return it.
function selmoRenderQr(url, cell){
  cell=cell||5;var quiet=4;
  var qr=selmoQrMatrix(url,'M'),n=qr.size,px=(n+quiet*2)*cell;
  var cv=document.createElement('canvas');cv.width=px;cv.height=px;
  cv.style.cssText='width:'+px+'px;height:'+px+'px;image-rendering:pixelated;border-radius:8px;display:block';
  var ctx=cv.getContext('2d');
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,px,px);
  ctx.fillStyle='#000000';
  for(var y=0;y<n;y++)for(var x=0;x<n;x++)if(qr.modules[y][x])ctx.fillRect((x+quiet)*cell,(y+quiet)*cell,cell,cell);
  return cv;
}
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
  if(btn){btn.classList.toggle('on',IS_WEB_ON);}  // icon button: state shown by .on border/glow
  // RAG and WEB are mutually exclusive: only one retrieval source per turn.
  if(IS_WEB_ON&&IS_RAG_ON){IS_RAG_ON=false;const rb=document.getElementById('rag-btn');if(rb){rb.classList.remove('on');rb.textContent='RAG';}}
  // Agent is a third grounding source — turn it off too.
  if(IS_WEB_ON&&typeof agentOffFor==='function')agentOffFor('web');
}
// RAG mode: an explicit, separate retrieval mode (twin of WEB). Turning it on
// only checks the bridge + embedder; folder selection and indexing happen in
// the corpus picker (the folder bar under the welcome). Normal chat and web are
// untouched while it is off.
async function toggleRag(){
  const btn=document.getElementById('rag-btn');
  if(!IS_RAG_ON){                                   // turning ON
    if(!ragOk){addMsg('assistant','⚠ '+t('rag.notactive'));return;}
    if(IS_WEB_ON){IS_WEB_ON=false;const wb=document.getElementById('web-btn');if(wb){wb.classList.remove('on');}}
    if(typeof agentOffFor==='function')agentOffFor('rag');
    try{ ragStatus=await(await fetch(`${RAG}/status`)).json(); ragOk=true; }catch(e){}
    if(ragStatus&&!ragStatus.embedder_up){addMsg('assistant','⚠ '+t('rag.embedderoff'));return;}
  }
  IS_RAG_ON=!IS_RAG_ON;
  if(btn){btn.classList.toggle('on',IS_RAG_ON);btn.textContent=IS_RAG_ON?'RAG ●':'RAG';}
  checkRagBridge();
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
  if(typeof updateRagCorpusBar==='function')updateRagCorpusBar(); // RAG folder bar in loaded sessions
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

// Desktop-only: a phone icon in the header toolbar. Clicking it opens a popup
// with the LAN address to type in the phone's browser to reach Selmo. Reads the
// LAN IP the front door baked into selmo-cert-ip.txt and shows the HTTPS 8443 URL
// (so the phone mic works). The icon is added only on the PC (localhost view);
// on a phone it never appears (you are already there).
function _openPhonePopup(url){
  var ov=document.getElementById('phone-popup');
  if(ov){ov.remove();return;}                        // toggle: a second click closes it
  ov=document.createElement('div');
  ov.id='phone-popup';
  ov.style.cssText='position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);'
    +'display:flex;align-items:center;justify-content:center;padding:16px';
  ov.onclick=function(e){if(e.target===ov)ov.remove();};   // click outside to close
  var card=document.createElement('div');
  card.style.cssText='background:var(--panel,#12161c);color:var(--white,#dfe8f0);'
    +'border:1px solid var(--steel,#2a3340);border-radius:10px;max-width:420px;width:100%;'
    +'padding:20px;font-family:inherit;box-shadow:0 8px 40px rgba(0,0,0,.5)';
  var title=document.createElement('div');
  title.textContent='📱 Use Selmo from your phone';
  title.style.cssText='font-size:16px;font-weight:bold;margin-bottom:12px';
  // QR of the same URL — scan it with the phone camera instead of typing.
  var qrWrap=document.createElement('div');
  qrWrap.style.cssText='display:flex;flex-direction:column;align-items:center;gap:8px;margin-bottom:14px';
  var qrCap=document.createElement('div');
  qrCap.textContent='Scan with your phone camera:';
  qrCap.style.cssText='font-size:13px;opacity:.9';
  try{
    var qrPad=document.createElement('div');
    qrPad.style.cssText='background:#fff;padding:10px;border-radius:10px;line-height:0';
    qrPad.appendChild(selmoRenderQr(url,5));
    qrWrap.appendChild(qrCap);qrWrap.appendChild(qrPad);
  }catch(e){ qrWrap=null; }   // if anything fails, fall back to the address text only
  var p1=document.createElement('div');
  p1.textContent='…or type this address in your phone browser bar:';
  p1.style.cssText='font-size:13px;opacity:.9;margin-bottom:8px';
  var link=document.createElement('code');
  link.textContent=url;
  link.style.cssText='display:block;color:var(--cyan,#7fdfff);background:rgba(127,223,255,.08);'
    +'padding:8px 10px;border-radius:6px;user-select:all;word-break:break-all;font-size:14px;margin-bottom:12px';
  var row=document.createElement('div');
  row.style.cssText='display:flex;gap:8px;margin-bottom:14px';
  var copy=document.createElement('button');
  copy.textContent='⧉ copy address';
  copy.style.cssText='background:none;border:1px solid var(--steel,#2a3340);color:inherit;'
    +'border-radius:6px;padding:6px 12px;cursor:pointer;font-family:inherit;font-size:13px';
  copy.onclick=function(){copyToClipboard(url,this);};
  var close=document.createElement('button');
  close.textContent='Close';
  close.style.cssText='background:none;border:1px solid var(--steel,#2a3340);color:inherit;'
    +'border-radius:6px;padding:6px 12px;cursor:pointer;font-family:inherit;font-size:13px;margin-left:auto';
  close.onclick=function(){ov.remove();};
  var help=document.createElement('div');
  help.style.cssText='font-size:12px;opacity:.8;line-height:1.55';
  help.textContent='The phone and the PC must be on the same Wi-Fi network. The first time, the phone '
    +'shows a certificate warning: accept it to continue (it is needed for the microphone).';
  // Phone-access toggle: flips the front door's LAN gate (loopback-only API,
  // so only this PC can change it). Default is OFF on a public network.
  var acc=document.createElement('label');
  acc.style.cssText='display:flex;align-items:center;gap:8px;font-size:13px;margin-bottom:6px;cursor:pointer';
  var cb=document.createElement('input');cb.type='checkbox';
  var accTxt=document.createElement('span');accTxt.textContent='Allow phone access on this network';
  acc.appendChild(cb);acc.appendChild(accTxt);
  var warn=document.createElement('div');
  warn.style.cssText='font-size:12px;color:var(--yellow,#e6c463);margin-bottom:12px;display:none';
  warn.textContent='Public network detected — off by default so others on the same Wi-Fi cannot reach Selmo.';
  fetch('/phone/status',{cache:'no-store'}).then(function(r){return r.json();}).then(function(s){
    cb.checked=!!s.enabled; warn.style.display=s.public?'block':'none';
  }).catch(function(){});
  cb.onchange=function(){ fetch('/phone/'+(cb.checked?'on':'off'),{method:'POST'}).catch(function(){}); };
  row.appendChild(copy);row.appendChild(close);
  card.appendChild(title);if(qrWrap)card.appendChild(qrWrap);card.appendChild(p1);card.appendChild(link);card.appendChild(acc);card.appendChild(warn);card.appendChild(row);card.appendChild(help);
  ov.appendChild(card);
  document.body.appendChild(ov);
}
function _phoneField(){
  try{
    var h=location.hostname;
    var local=(h==='localhost'||h==='127.0.0.1'||h==='::1'||h==='');
    if(!local)return;                                 // only on the desktop/PC view
    if(document.getElementById('phone-btn'))return;
    var box=document.querySelector('header .h-left');
    if(!box)return;
    fetch('/selmo-cert-ip.txt',{cache:'no-store'})
      .then(function(r){return r.ok?r.text():'';})
      .then(function(ip){
        ip=(ip||'').trim();
        if(!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip))return;   // no valid LAN IP -> skip silently
        var url='https://'+ip+':8443'+location.pathname;
        var btn=document.createElement('button');
        btn.id='phone-btn';
        btn.title='Use Selmo from your phone';
        btn.style.cssText='font-family:var(--mono);font-size:13px;letter-spacing:.07em;'
          +'padding:7px 12px;border-radius:var(--radius-xs);cursor:pointer;'
          +'transition:all .18s var(--ease);white-space:nowrap;flex-shrink:0;'
          +'background:rgba(255,255,255,.025);border:1px solid var(--steel);color:var(--dim);';
        btn.onmouseover=function(){btn.style.borderColor='var(--cyan)';btn.style.color='var(--cyan)';};
        btn.onmouseout=function(){btn.style.borderColor='var(--steel)';btn.style.color='var(--dim)';};
        btn.textContent='📱';
        btn.onclick=function(){_openPhonePopup(url);};
        box.appendChild(btn);
      }).catch(function(){});
  }catch(e){}
}
