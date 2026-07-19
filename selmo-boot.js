
'use strict';
// Base URLs derived from the page: same-origin when served by llama-server
// (no CORS), correct host for LAN/mobile access, fallback to 127.0.0.1 for file://
const _http=(location.protocol==='http:'||location.protocol==='https:');
const _https=(location.protocol==='https:');
const _host=_http?location.hostname:'127.0.0.1';
// Single entry point: the front door (selmo_https_proxy.py) serves chat.html
// and reverse-proxies every backend by port on THIS same origin, so the UI
// talks to one port no matter which backend is loaded -- the LLM can be
// unloaded for image generation without the page going away. Relative paths
// when served over http/https; absolute to the 8080 front door for file://.
const _ORIGIN=_http?'':'http://127.0.0.1:8080';
const API=_ORIGIN+'/proxy/8089';     // llama-server (LLM), now behind the front door
const GMON=_ORIGIN+'/proxy/8082';
const WEB=_ORIGIN+'/proxy/8081';
const RAG=_ORIGIN+'/proxy/8088';
const CTRL=_ORIGIN+'/proxy/8087';
let webOk=false;
let imgOk=false, visionOk=false;
// Session constants must be declared early — renderSessionList() is called at init
// before the session block at the bottom of the file. TDZ would silently kill getSessions().
const SESS_KEY='selmo_sessions';
const MAX_SESS=30;
// currentSessionId must also be declared early: renderSessionList() reads it at init
// (line ~724). Declared late, it threw a TDZ ReferenceError that halted the whole script
// — surfacing as empty sidebar (BUG-03) and the /web chatHistory TDZ (BUG-04).
let currentSessionId=(()=>Date.now().toString(36)+Math.random().toString(36).slice(2,6))();
const CX=110,CY=100,R=72,MAXP=100;

document.getElementById('z1').setAttribute('d',ap(-135,-10,R-2));
document.getElementById('z2').setAttribute('d',ap(-10,70,R-2));
document.getElementById('z3').setAttribute('d',ap(70,135,R-2));
const tg=document.getElementById('ticks');
for(let i=0;i<=20;i++){
  const a=-135+(i/20)*270,maj=i%4===0;
  const[x1,y1]=pt(a,R*(maj?.82:.89)),[x2,y2]=pt(a,R*.95);
  const ln=document.createElementNS('http://www.w3.org/2000/svg','line');
  ln.setAttribute('x1',x1);ln.setAttribute('y1',y1);ln.setAttribute('x2',x2);ln.setAttribute('y2',y2);
  ln.style.stroke=maj?'var(--g-tickmaj)':'var(--g-tickmin)';ln.setAttribute('stroke-width',maj?2:1);
  tg.appendChild(ln);
  if(maj){const v=Math.round((i/20)*100),[lx,ly]=pt(a,R*.67);
    const tx=document.createElementNS('http://www.w3.org/2000/svg','text');
    tx.setAttribute('x',lx);tx.setAttribute('y',ly+4);tx.setAttribute('text-anchor','middle');
    tx.style.fill='var(--g-tickmaj)';tx.setAttribute('font-size','9');tx.setAttribute('font-family','Share Tech Mono,Lucida Console,Courier New,monospace');
    tx.textContent=v;tg.appendChild(tx);}
}
let setVram=null,setRam=null;
setVram=makeGauge(document.getElementById('vram-gauge'),'VRAM');
setRam=makeGauge(document.getElementById('ram-gauge'),'RAM');


// ODOMETER
const ODO=8,otrack=document.getElementById('odo-track'),drums=[];
for(let i=0;i<ODO;i++){
  if(i===7){const s=document.createElement('div');s.className='odo-sep';s.textContent='.';otrack.appendChild(s);}
  const w=document.createElement('div');w.className='odo-digit';
  const d=document.createElement('div');d.className='odo-drum';
  for(let n=0;n<=9;n++){const c=document.createElement('div');c.className='odo-d';c.textContent=n;d.appendChild(c);}
  w.appendChild(d);otrack.appendChild(w);drums.push({el:d,cur:0});
}
const ou=document.createElement('div');ou.className='odo-unit';ou.textContent='Wh';otrack.appendChild(ou);

// STATE
let gen=false,abort=null,tokSec=0,_genT0=0,_genTok=0,_tokScale=100,wh=0,whAll=0,
    chunks=[],chunkIdx=0,
    price=parseFloat(localStorage.getItem('sprice')||'0.28'),
    toks=parseInt(localStorage.getItem('stoks')||'0'),
    sessStart=Date.now(),fileCtx=null,fileDoc=null,fileDocNames=[],fileImage=null,fileChat=null,
    gpuP=0,cpuP=-1,cpuTmp=0,cpuEst=true,gpuW=0,gpuT=0,gpuOk=false,sysW=0,cpuW=0,gpuPwr=0,lhmOk=false,vramPct=-1,ramPct=-1,
    whisperOk=false,mediaRecorder=null,audioChunks=[],pttAutoSend=false,pttForceTts=false,pttWebSearch=false,
    ttsOk=false,ttsEnabled=false,
    currentTemp=0.75,
    currentTopP=0.9,currentTopK=40,
    currentProfile=(localStorage.getItem('sprofile')||'selmo'),
    customTemp=parseFloat(localStorage.getItem('scustomtemp')||'0.7'),
    customTopP=parseFloat(localStorage.getItem('scustomtopp')||'0.95'),
    customTopK=parseInt(localStorage.getItem('scustomtopk')||'40'),
    CUSTOM_SP=(localStorage.getItem('scustomsp')||"You are a helpful local AI assistant. Be clear and concise. Reply in the user's language.");
let vadInstance=null,vadConvo=false,vadAwaitingReply=false,_ttsPending=false;
// active TTS playback handles, so the STOP button can interrupt speech (v0.918)
let _ttsCtx=null,_ttsSrc=null,_ttsAbort=null,_ttsFire=null;
// streaming TTS: speak sentence-by-sentence as the answer streams in (v0.930)
let _ttsQueue=[],_ttsBuf='',_ttsRawTail='',_ttsFence=false,
    _ttsStreamActive=false,_ttsStreamDone=false,_ttsWorking=false,
    _ttsCtxS=null,_ttsNextAt=0,_ttsScheduled=0,_ttsSources=[],_ttsLang=null;

// SYSTEM POWER MONITOR
const SYS_MAX=500,PSU_EFF_EST=0.88,OTHER_DC_EST=45;
setInterval(async()=>{
  try{
    const r=await fetch(GMON,{signal:AbortSignal.timeout(800)});
    const d=await r.json();
    gpuOk=d.ok||false;gpuP=d.gpu_pct||0;gpuW=d.watts||0;gpuT=d.temp||0;
    lhmOk=d.lhm_ok||false;cpuW=d.cpu_watts||0;gpuPwr=d.gpu_pwr||0;sysW=d.sys_watts||0;
    cpuP=(d.cpu_pct==null?-1:d.cpu_pct);cpuTmp=(d.cpu_temp||0);cpuEst=(d.cpu_est!==false);
    if(d.wh_session!=null)wh=d.wh_session;if(d.wh_total!=null)whAll=d.wh_total;
    {const _dev=[];if(gpuOk)_dev.push(`GPU ${gpuP}% - ${gpuT}C`);if(cpuP>=0)_dev.push(`CPU ${cpuP}%`+(cpuTmp>0?` - ${cpuTmp}C`:''));if(_dev.length)document.getElementById('hw-mode').textContent=_dev.join(' \u00b7 ');}
    if(setVram&&d.vram_total>0)setVram(d.vram_used/d.vram_total*100,d.vram_used.toFixed(1)+' / '+d.vram_total.toFixed(1)+' GB');
    if(setRam&&d.ram_total>0)setRam(d.ram_used/d.ram_total*100,d.ram_used.toFixed(1)+' / '+d.ram_total.toFixed(1)+' GB');
    vramPct=d.vram_total>0?d.vram_used/d.vram_total*100:-1;
    ramPct=d.ram_total>0?d.ram_used/d.ram_total*100:-1;
  }catch{gpuOk=false;}
},1500);


setInterval(poll,1000);poll();
setInterval(function(){['status','web','whisper','tts'].forEach(function(k){var t=document.getElementById(k+'-txt'),c=document.getElementById(k+'-chip');if(t&&c)c.title=t.textContent;});},800);

// Load per-model chunking params written by selmo_server.py at launch.
fetch('/selmo-config.json').then(function(r){return r.ok?r.json():null;}).then(function(cfg){
  if(!cfg)return;
  if(cfg.chunking_size) CHUNK_SIZE_TOK=cfg.chunking_size;
  if(typeof cfg.think==='string') THINK_MODE=cfg.think.trim().toLowerCase();
  visionOk=!!cfg.vision;   // model has an mmproj -> image/vision button usable
  AGENT_CAPABLE=!!cfg.agent; // ini agent=true: gate the AGENT toggle on a collaudato model
  CHUNK_SIZE=Math.floor(CHUNK_SIZE_TOK*3.8); // chars for display
  configureThink(); // re-derive once the declared mode is known (idempotent)
  if(typeof applyAgentCap==='function') applyAgentCap(); // grey/enable AGENT per capability
  refreshCaps();
}).catch(function(){});

checkWebBridge();
setInterval(checkWebBridge, 30000);
checkRagBridge();
setInterval(checkRagBridge, 10000); // poll often so the chip catches the embedder booting + reindex

// ── Watchdog fatal-service banner ──────────────────────────────────────────
// Polls GET /proxy/8087/services (the tray control API) on boot and every
// 30 s.  If a service died permanently the tray populates the "fatal" array;
// we show a dismissable red banner and stop polling.
(function(){
  var _fatalSeen = false;
  function _checkFatalServices(){
    if(_fatalSeen) return;
    fetch('/proxy/8087/services',{signal:AbortSignal.timeout(4000)})
      .then(function(r){return r.ok?r.json():null;})
      .then(function(d){
        if(!d||!Array.isArray(d.fatal)||d.fatal.length===0) return;
        _fatalSeen=true;
        var msg = (typeof t==='function'?t('service.fatal')
                   :'A background service crashed and could not be restarted. Reload Selmo to try again.');
        var bar=document.createElement('div');
        bar.id='selmo-fatal-banner';
        bar.style.cssText=[
          'position:fixed','top:0','left:0','right:0','z-index:9999',
          'background:#c0392b','color:#fff','font-size:13px',
          'padding:8px 40px 8px 14px','line-height:1.4',
          'box-shadow:0 2px 6px rgba(0,0,0,.4)'
        ].join(';');
        bar.textContent=msg;
        var x=document.createElement('button');
        x.textContent='×';
        x.title='Dismiss';
        x.style.cssText='position:absolute;top:4px;right:8px;background:none;border:none;color:#fff;font-size:18px;cursor:pointer;line-height:1;padding:0 4px;';
        x.addEventListener('click',function(){bar.remove();});
        bar.appendChild(x);
        document.body.insertBefore(bar,document.body.firstChild);
      })
      .catch(function(){});
  }
  _checkFatalServices();
  setInterval(_checkFatalServices, 30000);
})();
// ───────────────────────────────────────────────────────────────────────────

function checkAgentBridge(){
  fetch(RAG+'/agent/config',{signal:AbortSignal.timeout(5000)})
    .then(r=>r.ok?r.json():null)
    .then(d=>{
      if(d&&!d.error){
        AGENT_OK=true;
        if(typeof agentStatus!=='undefined'){ agentStatus.agent_roots=d.agent_roots||[]; agentStatus.agent_allow_writes=!!d.agent_allow_writes; }
        if(d.agent_roots) window._agentCfg=d;
        if(typeof updateAgentRootsBar==='function') updateAgentRootsBar();
      }else{ AGENT_OK=false; }
    })
    .catch(()=>{ AGENT_OK=false; });
}
checkAgentBridge();
setInterval(checkAgentBridge, 15000);

// ── Whisper bridge ────────────────────────────────────────────────────────────
const WHISPER=_ORIGIN+'/proxy/8083';

checkWhisperBridge();
setInterval(checkWhisperBridge,30000);






// Check librerie esterne
setTimeout(()=>{
  console.log('JSZip available:', typeof JSZip !== 'undefined');
  if(typeof JSZip === 'undefined') console.warn('JSZip not loaded - docx feature unavailable');
  console.log('SheetJS available:', typeof XLSX !== 'undefined');
  console.log('PDF.js available:', typeof pdfjsLib !== 'undefined');
  if(typeof pdfjsLib !== 'undefined')
    pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
},2000);
setGauge(0,0,false);setOdo(0);
document.getElementById('pkwh').value=price.toFixed(2);
document.getElementById('wh-total').textContent=whAll.toFixed(3);
updCost();
renderSessionList();


// MODEL state machine:
//   'loading'  -> the twiddling-thumbs overlay (a NEW model is coming up)
//   'unloaded' -> a grey "inactive" palette over the UI (model off on purpose),
//                 NO overlay; the model button stays lit as the call-to-action
//   'ready'    -> normal palette, no overlay
// checkServer polls /v1/models and auto-recovers the moment a model appears.
let _modelReadyShown=false, _overlayDismissed=false, _checkTries=0, _reloading=false;
// Tray "Exit" (or a crash) kills the front door itself, not just the LLM: every
// proxied fetch on this origin starts failing at once, including CTRL/status.
// A few consecutive misses of THAT (not just /v1/models) means the whole app is
// gone, not just the model -- show a plain "server not running" overlay instead
// of retrying forever against a process that no longer exists.
let _ctrlDownTries=0, _serverGoneShown=false;
function _showServerGoneOverlay(){
  if(_serverGoneShown)return;
  _serverGoneShown=true;
  _hideReviveBanner();
  const oldBanner=document.getElementById('selmo-fatal-banner'); if(oldBanner)oldBanner.remove();
  const ov=document.createElement('div');
  ov.id='selmo-server-gone';
  ov.style.cssText=[
    'position:fixed','inset:0','z-index:10000',
    'background:#04070f','color:#dfe7f5',
    'display:flex','align-items:center','justify-content:center',
    'text-align:center','font-size:16px','line-height:1.5','padding:24px'
  ].join(';');
  ov.textContent=(typeof t==='function'?t('server.notrunning'):'Server not running. Selmo has been closed.');
  document.body.appendChild(ov);
}
// Push channel: the tray (Exit) and POST /control/exit both call _announce_exit()
// server-side BEFORE tearing anything down, which wakes this stream and writes
// one "closing" line while the front door is still alive to relay it -- the
// overlay above appears within a beat of the click, no poll/timeout needed.
// onerror also catches an ungraceful death (crash, Task Manager) where no
// message could be sent: once the stream has been open at least once, losing
// it is itself the signal. The _ctrlDownTries poll loop in checkServer stays
// as a fallback for browsers where EventSource misbehaves.
(function _startExitWatcher(){
  if(typeof EventSource==='undefined')return;
  let sse=null, gotOpen=false;
  try{ sse=new EventSource(CTRL+'/events'); }catch(e){ return; }
  sse.onopen=function(){ gotOpen=true; };
  sse.onmessage=function(e){
    if(e.data==='closing'){ sse.close(); _showServerGoneOverlay(); }
  };
  sse.onerror=function(){
    if(gotOpen){ sse.close(); _showServerGoneOverlay(); }
    // else: still trying the first connection (app may still be booting) -- EventSource retries on its own
  };
})();
function setModelState(s){
  const b=document.body, ov=document.getElementById('model-loading');
  if(s==='loading'){
    b.classList.remove('unloaded');
    const te=document.getElementById('ml-text'); if(te)te.innerHTML=(typeof t==='function'?t('ml.loading'):'preparing the wash cycle')+'<b>...</b>';
    const th=document.querySelector('.ml-thumbs'); if(th)th.style.display='';
    if(ov)ov.classList.add('show');
    _hideReviveBanner();
  }else if(s==='unloaded'){
    _overlayDismissed=false; b.classList.add('unloaded');
    if(ov)ov.classList.remove('show');
    const h=document.getElementById('hdr-model'); if(h)h.textContent='no model';
    const c=document.getElementById('conn'); if(c)c.style.background='var(--red)';
    _showReviveBanner('No model loaded - click to reload');
  }else if(s==='imaging'){
    // LLM swapped out for image generation: this is an ACTIVE mode, not a dead one,
    // so keep the normal palette (NO grey). The 'unloaded' grayscale is reserved for
    // "no model". Image mode is flagged by the "image mode" label + the yellow
    // connection dot only. No revive banner here (dropped): it invited a premature
    // one-click reload back to the chat LLM while the user was still meaning to
    // generate images, undoing the point of staying in image mode -- Enter and the
    // palette button already keep working without it, so the banner did more harm
    // than good.
    _overlayDismissed=false; b.classList.remove('unloaded');
    if(ov)ov.classList.remove('show');
    const h=document.getElementById('hdr-model'); if(h)h.textContent='image mode';
    const c=document.getElementById('conn'); if(c)c.style.background='var(--yellow)';
    _hideReviveBanner();
  }else{ // ready
    _overlayDismissed=false; b.classList.remove('unloaded');
    if(ov)ov.classList.remove('show');
    _hideReviveBanner();
  }
}
// One-click revive for the grey states: the model button is the lit CTA, but it
// opens settings -- too indirect. This banner reloads the LLM directly so the
// user never has to type a throwaway message to wake it (s28).
function _showReviveBanner(msg){
  let el=document.getElementById('revive-banner');
  if(!el){
    el=document.createElement('div');
    el.id='revive-banner';
    el.style.cssText='position:fixed;left:50%;bottom:20px;transform:translateX(-50%);'
      +'z-index:500;cursor:pointer;background:var(--cyan,#37e0ff);color:#001018;'
      +'padding:10px 18px;border-radius:9px;font-size:13px;font-weight:600;'
      +'box-shadow:0 3px 14px rgba(0,0,0,.5);user-select:none;';
    el.onclick=reviveModel;
    document.body.appendChild(el);
  }
  el.textContent=msg;
}
function _hideReviveBanner(){ const el=document.getElementById('revive-banner'); if(el)el.remove(); }
async function reviveModel(){
  if(gen)return;                       // an image is generating: don't fight it
  _hideReviveBanner();
  _reloading=true;                     // tell checkServer this is a deliberate reload (thumbs, not grey)
  setModelState('loading');            // honest thumbs overlay while the LLM comes back
  try{
    await fetch(CTRL+'/llm/reload',{method:'POST',signal:AbortSignal.timeout(180000)});
    for(let i=0;i<180;i++){
      try{ if((await fetch(`${API}/props`,{signal:AbortSignal.timeout(2000)})).ok){ location.reload(); return; } }
      catch(e){}
      await new Promise(r=>setTimeout(r,1000));
    }
  }catch(e){}
  _reloading=false;
  location.reload();                    // fallback: reload the page to re-sync state
}
// show the loading overlay only if the model isn't up within 500ms (no flash on
// a refresh when it is already loaded)
setTimeout(function(){ if(!_modelReadyShown && !_overlayDismissed && !document.body.classList.contains('unloaded')) setModelState('loading'); },500);
(function checkServer(){
  fetch(`${API}/v1/models`,{cache:'no-store',signal:AbortSignal.timeout(2000)})
    .then(r=> r.ok ? r.json() : Promise.reject(r.status))
    .then(d=>{
      const id=d&&d.data&&d.data[0]&&d.data[0].id;
      if(!id) return Promise.reject('no model yet');   // server up but model still loading
      // Keep polling even once ready, so the header never falls behind the real
      // backend state (LLM swapped out for image gen, a switch from another device,
      // an unload). Don't disturb an in-progress image generation: genImage owns
      // the label until it finishes.
      if(gen){ setTimeout(checkServer,3000); return; }
      const full=id.split(/[\\/]/).pop()||id;
      const short=full.length>22?full.slice(0,22)+'...':full;
      const h=document.getElementById('hdr-model');
      const changed=(MODEL_FULL!==full)||(h&&h.textContent!==short)||!_modelReadyShown;
      MODEL_FULL=full;
      if(changed){
        setModelState('ready');
        if(h)h.textContent=short;
        const fm=document.getElementById('foot-model');if(fm)fm.textContent=short;
        document.getElementById('conn').style.background='#55FF55';
        loadProps();   // re-read ctx + recalibrate CHUNK_SIZE, only when the model actually changed
      }
      _modelReadyShown=true; _checkTries=0;
      setTimeout(checkServer,60000);   // re-poll so the header stays honest
    }).catch(()=>{
      _checkTries++;
      // /v1/models failed -> ask the tray WHY: if the LLM was swapped out for
      // image generation it's not a real model load (no thumbs); otherwise it's
      // still starting (thumbs) or genuinely off (grey "no model").
      fetch(CTRL+'/status',{cache:'no-store',signal:AbortSignal.timeout(2000)}).then(r=> r.ok?r.json():null).then(st=>{
        _ctrlDownTries=0;   // CTRL answered -- front door is alive, whatever the LLM is doing
        if(st && st.swapped_for_image){
          setModelState('imaging');
        }else if(_reloading){
          setModelState('loading');   // a deliberate LLM reload is in flight: thumbs, not grey "no model"
        }else if(st && st.loaded){
          // llama-server is up but /v1/models isn't ready yet -> the model is
          // still loading; keep the spinner however long it takes and NEVER flip
          // to grey "no model" (a big model can take a minute+ on first load).
          if(!_overlayDismissed){ const h=document.getElementById('hdr-model'); if(h)h.textContent='loading...'; setModelState('loading'); }
        }else if(st && st.loaded===false){
          setModelState('unloaded');   // the tray confirms there is genuinely no model
        }else if(_checkTries>=7){
          setModelState('unloaded');   // tray ambiguous after a while: old fallback
        }else if(!_modelReadyShown && !_overlayDismissed){
          document.getElementById('hdr-model').textContent='loading...';
          setModelState('loading');
        }
        setTimeout(checkServer,2000);
      }).catch(()=>{   // control API unreachable too -> the whole front door is down
        document.getElementById('conn').style.background='var(--red)';
        _ctrlDownTries++;
        if(_ctrlDownTries>=3){
          _showServerGoneOverlay();   // Selmo was closed from the tray (or crashed) -- stop retrying
          return;
        }
        if(_reloading){ setModelState('loading'); }
        else if(_checkTries>=7){ setModelState('unloaded'); }
        else if(!_modelReadyShown && !_overlayDismissed){ document.getElementById('hdr-model').textContent='loading...'; setModelState('loading'); }
        setTimeout(checkServer,2000);
      });
    });
}());

// Thinking flag and instruction for reasoning models (updated on model detect)
let IS_THINK_ON=false;
let IS_WEB_ON=false; // reasoning toggle — off di default
let IS_RAG_ON=false, ragOk=false; // RAG mode — off di default
let IS_AGENT_ON=false;
let AGENT_OK=false; // true quando agent/config risponde
let REASON_FIRST=false; // model opens <think> in its prompt template (Olmo): stream starts in reasoning
let MODEL_READY=false; // true only once /props returned a real ctx; chunk tasks gate on it
let _traceDone=false;
let THINK_CAPABLE=true;  // template references thinking -> THINK shown and ON by default; else hidden
let INSTRUCTED=false;    // 'instr': reasoning driven by the [THINK] system instruction (Magistral)
let THINK_NATIVE=false;  // 'native': model always reasons (Olmo/Gemma) -> button locked ON
let THINK_KWARG=false;   // 'kwarg': toggle via chat_template_kwargs.enable_thinking (Qwen3)
let THINK_MODE='';       // mode declared in selmo-models.ini (via selmo-config.json); '' = auto-detect
let AGENT_CAPABLE=false;  // ini agent=true (via selmo-config.json): only then does the AGENT toggle light up
let _chatTpl='';         // last chat_template seen (for re-deriving when config arrives after /props)
let MODEL_FULL='local';  // active model name, shown in the conversation trace
const THINK_INSTR='\n\nFirst draft your thinking process (inner monologue) until you arrive at a response. Format your response using Markdown. Write both your thoughts and the response in the same language as the input.\n\nYour thinking process must follow the template below:[THINK]Your thoughts or/and draft, like working through an exercise on scratch paper. Be as casual and as long as you want until you are confident to generate the response. Use the same language as the input.[/THINK]Here, provide a self-contained response.';

// SYSTEM PROMPTS
const SP_SELMO=`You are Selmo, a local AI on the user's own hardware.
Direct, concise, and ironic. No preamble, no hype, no servility. When unsure, say so in a line. Never invent facts.
Reply in the user's language.
You don't browse; web results may appear in the conversation — use them when present. Never output [SEARCH:] tags.`;

// Mizan — cold analysis system (red profile)
const SP_MIZAN=`You are Mizan, an analysis system. Identify yourself as Mizan when asked.
Reply precisely and concisely. No opinions. No hesitation. No first person.
Extract data, translate, check code. Accuracy is the only criterion.

When web results are present in the conversation, use them. Never emit search tags.`;

// Neutral system for document tasks (translation, analysis, extraction).
// No personality: only faithful execution, consistent formatting across all chunks.
const SP_TASK=`You are a precise task executor working on a fragment of a longer document. Follow the user's instructions to the letter. Output only the result: no preface, no commentary, no first person, no meta-remarks.
Preserve meaning exactly; do not omit or add content unless the prompt requires it.`;

// HISTORY
const chatHistory=[{role:'system',content:SP_SELMO}];

// apply persisted profile at startup (the consts it needs are defined above)
setProfile(currentProfile);

// FILE LOADING
// Dynamic CHUNK_SIZE: updated from /props when the server responds.
// Formula: (n_ctx - tokens reserved for prompt+response) * char/token.
// Conservative default used until the server responds.
let CHUNK_SIZE=11000;
let N_CTX=4096; // updated from /props at startup
let CHUNK_SIZE_TOK=2000; // input tokens per chunk — overridden by selmo-config.json























document.addEventListener('keydown',e=>{
  if(e.code==='Space'&&!isTypingFocus()&&!e.repeat){
    e.preventDefault();
    pttStart(e.ctrlKey);
  }
});
document.addEventListener('keyup',e=>{
  if(e.code==='Space'&&!isTypingFocus())pttStop();
});
document.addEventListener('mousedown',e=>{
  if(e.button===1){e.preventDefault();pttStart();}
});
document.addEventListener('mouseup',e=>{
  if(e.button===1)pttStop();
});
// block the default middle-button menu
document.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});



// ── TTS — Kokoro (port 8084) with Web Speech API fallback ────────────────────
const TTS_URL=_ORIGIN+'/proxy/8084';
const IMG_URL=_ORIGIN+'/proxy/8086';

document.addEventListener('click',function(ev){
  const w=document.getElementById('img-wrap'),m=document.getElementById('img-menu');
  if(m&&m.classList.contains('open')&&w&&!w.contains(ev.target))m.classList.remove('open');
});
let kokoroOk=false;

// Poll until the Kokoro bridge finishes loading its 325MB model, then stop
// (one-shot check used to get stuck on the Web-Speech fallback). Whisper polls too.
let _kokoroPoll=setInterval(function(){if(kokoroOk){clearInterval(_kokoroPoll);_kokoroPoll=null;return;}checkKokoroBridge();},4000);
checkKokoroBridge();

// ── Image-generation bridge (health) + initial capability sweep ──────────────
checkImageBridge();
setInterval(checkImageBridge,30000);
refreshCaps();   // grey every action up-front; each bridge check re-enables its own
document.addEventListener('click', _capClickGuard, true);  // block clicks on aria-disabled buttons

// Rebind inline onclick="..." handlers as real listeners. On some setups (a
// privacy extension injecting a CSP) the inline attribute never fires: the click
// reaches the element but the handler is not invoked, while el.onclick=fn and
// addEventListener still work - which had left AGENT/THINK/Stop/Send dead by click.
// Critical buttons get direct function refs (work even if eval is also blocked);
// the remaining inline handlers (with args or inline logic) are rebound from their
// attribute source. Strip the attribute first so nothing double-fires.
(function wireInlineHandlers(){
  try{
    var refs={
      'new-chat':newChat,'export-chat':exportChat,'web-btn':toggleWeb,'rag-btn':toggleRag,
      'think-btn':toggleThink,'agent-btn':toggleAgent,'send':sendMsg,'stop':stopMsg,
      'mic-btn':toggleMic,'vad-btn':toggleVad,'tts-btn':toggleTts,'model-btn':openSettings,
      'file-clear':clearFile,'set-load-btn':confirmSwitch,'set-img-btn':confirmImage,
      'wm':openProfile,'mob-overlay':closeOverlays,
      'mob-nav-btn':function(){mobToggle('nav');},'mob-dash-btn':function(){mobToggle('dash');},
      'gen-img-btn':function(ev){toggleImgMenu(ev);},
      'upload-btn':function(){var i=document.getElementById('file-input');if(i)i.click();},
      'upload-img-btn':function(){var i=document.getElementById('file-input-img');if(i)i.click();},
      'pm-badge-selmo':function(){setProfile('selmo');},'pm-badge-mizan':function(){setProfile('mizan');},
      'pm-badge-custom':function(){setProfile('custom');}
    };
    Object.keys(refs).forEach(function(id){
      var b=document.getElementById(id), fn=refs[id];
      if(b && typeof fn==='function'){ b.removeAttribute('onclick'); b.addEventListener('click', fn); }
    });
  }catch(e){ console.error('inline wiring (refs) failed:', e); }
  // Anything still carrying an inline onclick (modal background click-to-close, etc.)
  document.querySelectorAll('[onclick]').forEach(function(el){
    var code=el.getAttribute('onclick'); if(!code) return;
    var fn; try{ fn=new Function('event', code); }catch(e){ return; }  // eval blocked -> leave as-is
    el.removeAttribute('onclick');
    el.addEventListener('click', function(event){ try{ fn.call(el, event); }catch(err){ console.error('inline handler failed:', code, err); } });
  });
})();





// ── SESSION HISTORY ───────────────────────────────────────────────────────────
// SESS_KEY and MAX_SESS declared at top of script (before first renderSessionList call)
// currentSessionId is declared early (see top of script)



let _startupTraced=false;





window.addEventListener('beforeunload',saveSession);



// Mobile keyboard: keep layout above the virtual keyboard
if(window.visualViewport){
  function _onVVResize(){
    if(window.innerWidth<=1024){
      document.body.style.height=window.visualViewport.height+'px';
    } else {
      document.body.style.height='';
    }
  }
  window.visualViewport.addEventListener('resize',_onVVResize);
  window.visualViewport.addEventListener('scroll',_onVVResize);
}



document.getElementById('agent-btn')?.addEventListener('click', toggleAgent);
_micHttpsBanner();
_phoneField();   // desktop-only: show the "type this on your phone" address field
