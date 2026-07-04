'use strict';
// PROFILES — Selmo (blue) / Mizan (red) / Custom (neutral). activeSP() feeds chatHistory[0].
function activeSP(){
  if(currentProfile==='mizan')return SP_MIZAN;
  if(currentProfile==='custom')return CUSTOM_SP||SP_SELMO;
  return SP_SELMO;
}
function syncSampling(){
  if(currentProfile==='mizan'){currentTemp=0.01;currentTopP=1.0;currentTopK=0;}
  else if(currentProfile==='custom'){currentTemp=customTemp;currentTopP=customTopP;currentTopK=customTopK;}
  else {currentTemp=0.75;currentTopP=0.9;currentTopK=40;}
}
function setProfile(name){
  if(name!=='mizan'&&name!=='custom')name='selmo';
  currentProfile=name;
  try{localStorage.setItem('sprofile',name);}catch(_){}
  document.body.classList.remove('mizan','custom');
  if(name!=='selmo')document.body.classList.add(name);
  syncSampling();
  const wm=document.getElementById('wm');
  if(wm)wm.innerHTML=((name==='mizan')?'Mizan':(name==='custom')?'Custom':'A.N.S.E.L.M.O')+'<span class="wm-mode">mode</span>';
  syncThinkPrompt();
  updateProfileUI();
}
function updateProfileUI(){
  ['selmo','mizan','custom'].forEach(p=>{const b=document.getElementById('pm-badge-'+p);if(b)b.classList.toggle('active',p===currentProfile);});
  const t=document.getElementById('pm-temp'),pp=document.getElementById('pm-topp'),pk=document.getElementById('pm-topk'),sp=document.getElementById('pm-sys'),hint=document.getElementById('pm-hint');
  if(!t)return;
  const custom=(currentProfile==='custom');
  if(currentProfile==='mizan'){t.value=0.01;pp.value=1.0;pk.value=0;sp.value=SP_MIZAN;}
  else if(custom){t.value=customTemp;pp.value=customTopP;pk.value=customTopK;sp.value=CUSTOM_SP;}
  else {t.value=0.75;pp.value=0.9;pk.value=40;sp.value=SP_SELMO;}
  [t,pp,pk,sp].forEach(el=>{el.disabled=!custom;el.style.opacity=custom?'':'0.55';});
  if(hint)hint.textContent=custom?'Editable — these values are sent with every request.':'Preset (read-only). Switch to Custom to edit.';
}
function onCustomParam(){
  if(currentProfile!=='custom')return;
  const t=parseFloat(document.getElementById('pm-temp').value),pp=parseFloat(document.getElementById('pm-topp').value),pk=parseInt(document.getElementById('pm-topk').value),sp=document.getElementById('pm-sys').value;
  if(!isNaN(t))customTemp=t;
  if(!isNaN(pp))customTopP=pp;
  if(!isNaN(pk))customTopK=pk;
  CUSTOM_SP=sp||SP_SELMO;
  try{localStorage.setItem('scustomtemp',String(customTemp));localStorage.setItem('scustomtopp',String(customTopP));localStorage.setItem('scustomtopk',String(customTopK));localStorage.setItem('scustomsp',CUSTOM_SP);}catch(_){}
  syncSampling();syncThinkPrompt();
}
function openProfile(){updateProfileUI();const m=document.getElementById('profile-modal');if(m)m.classList.add('show');}
function closeProfile(){const m=document.getElementById('profile-modal');if(m)m.classList.remove('show');}
// Build the message array actually sent to the model. We store assistant turns
// as [THINK]reasoning[/THINK]answer (for the panel + saved sessions), but a
// completed reasoning block must NEVER be fed back to a reasoning model: seeing
// a finished [THINK]...[/THINK] in the history makes it emit a fresh think block
// and then stop, producing zero answer tokens (the "reasoning complete, no
// answer" failure that appears from the 2nd turn on, any model, any ctx size).
// So the model only ever sees the clean answer of past turns. (BUG-NOANS-01)
function apiMessages(){
  return chatHistory.map(m=>{
    if(m&&m.role==='assistant'&&typeof m.content==='string'){
      const a=m.content.indexOf('[THINK]'),b=m.content.indexOf('[/THINK]');
      if(a!==-1&&b>a){
        const clean=(m.content.slice(0,a)+m.content.slice(b+8)).trim();
        return {role:'assistant',content:clean};
      }
    }
    return m;
  });
}
function maxTok(){
  try{
    for(let i=chatHistory.length-1;i>=0;i--){
      if(chatHistory[i].role==='user'){
        if(Array.isArray(chatHistory[i].content)){
          // vision: reserve ~1300 tok per image (encoder budget) + prompt headroom,
          // give the rest of the context to the answer (was a flat 1200 cap)
          const imgs=chatHistory[i].content.filter(p=>p&&p.type==='image_url').length||1;
          return Math.min(8000,Math.max(1024,Math.floor(N_CTX-imgs*1300-800)));
        }
        break;
      }
    }
  }catch(_){}
  return Math.min(8000,Math.max(512,Math.floor(N_CTX*0.55)));
}
function setThinkEnabled(on){
  const btn=document.getElementById('think-btn');
  if(!btn)return;
  if(!THINK_CAPABLE){   // non-reasoning model: greyed and disabled, not hidden
    btn.setAttribute('aria-disabled','true'); btn.style.opacity='.35'; btn.style.cursor='not-allowed';
    btn.title='This model has no reasoning mode';
    return;
  }
  btn.removeAttribute('aria-disabled');
  btn.disabled=!on;
  btn.style.opacity=on?'':'.35';
  btn.style.cursor='';
  btn.title='Extended reasoning ON/OFF';
}
// Inject the [THINK] instruction only for models that need it (Magistral);
// native reasoners (Olmo/Gemma) reason on their own, so we never push it to them.
function syncThinkPrompt(){
  if(chatHistory[0])chatHistory[0].content=(IS_THINK_ON&&INSTRUCTED)?(activeSP()+THINK_INSTR):activeSP();
}
// For 'kwarg' models (Qwen3 hybrid): the supported, template-proof reasoning
// switch. Sent ONLY for that mode (some llama.cpp builds 400 on an unknown
// kwarg), so it is gated strictly on THINK_KWARG.
function thinkKwargs(){
  return THINK_KWARG?{chat_template_kwargs:{enable_thinking:IS_THINK_ON}}:{};
}
// Derive the reasoning-control mode. The ini (THINK_MODE) is authoritative; when
// it is empty we fall back to sniffing the chat template (the old behaviour).
// Called from /props (with the template) and from the config fetch (no arg).
function configureThink(_ct){
  if(typeof _ct==='string')_chatTpl=_ct; _ct=_chatTpl||'';
  // REASON_FIRST is a STREAM-PARSING hint (Olmo opens <think> in its prompt
  // template), independent of control, so it always comes from the template.
  REASON_FIRST=_ct.includes('<think>')&&_ct.lastIndexOf('<think>')>_ct.lastIndexOf('</think>');
  if(THINK_MODE){                       // declared in the ini -> authoritative
    THINK_CAPABLE = THINK_MODE!=='off';
    INSTRUCTED    = THINK_MODE==='instr';
    THINK_KWARG   = THINK_MODE==='kwarg';
    THINK_NATIVE  = THINK_MODE==='native';
  }else{                                // undeclared -> best-effort detection
    THINK_CAPABLE=_ct.toLowerCase().includes('think');
    INSTRUCTED=THINK_CAPABLE&&!REASON_FIRST&&!_ct.includes('<|think|>');
    THINK_KWARG=false;
    THINK_NATIVE=THINK_CAPABLE&&!INSTRUCTED;
  }
  console.log('Selmo think:',{mode:THINK_MODE||'(auto)',capable:THINK_CAPABLE,instr:INSTRUCTED,kwarg:THINK_KWARG,native:THINK_NATIVE});
  applyThinkMode();
}
// The THINK button is the single source of truth for controllable models
// (instr/kwarg): ON = reason, OFF = don't, and the choice is remembered across
// reloads. 'native' models always reason, so the button is locked ON.
function applyThinkMode(){
  const btn=document.getElementById('think-btn');
  if(!btn)return;
  if(!THINK_CAPABLE){            // non-reasoning model: keep it visible but greyed/disabled
    btn.style.display='';
    btn.setAttribute('aria-disabled','true'); btn.style.opacity='.35'; btn.style.cursor='not-allowed';
    btn.classList.remove('on'); btn.textContent='THINK';
    btn.title='This model has no reasoning mode';
    IS_THINK_ON=false; syncThinkPrompt(); return;
  }
  btn.style.display='';
  if(THINK_NATIVE){
    IS_THINK_ON=true;
    btn.setAttribute('aria-disabled','true');btn.style.opacity='.6';btn.style.cursor='default';
    btn.classList.add('on');btn.textContent='THINK ●';
    btn.title='This model always reasons';
  }else{
    IS_THINK_ON=localStorage.getItem('sthink')!=='0'; // default ON, remembered
    btn.removeAttribute('aria-disabled');btn.disabled=false;btn.style.opacity='';btn.style.cursor='';
    btn.classList.toggle('on',IS_THINK_ON);btn.textContent=IS_THINK_ON?'THINK ●':'THINK';
    btn.title='Extended reasoning ON/OFF';
  }
  syncThinkPrompt();
}
function modelInfoLine(){
  const ctx=N_CTX?('ctx '+N_CTX.toLocaleString('en')+' tok'):'ctx ?';
  const mode=THINK_CAPABLE?'reasoning: on':'reasoning: off';
  return MODEL_FULL+'  ·  '+ctx+'  ·  '+mode;
}
function traceLine(){
  const info=document.createElement('div');
  info.style.cssText='margin:4px 0 10px;font-size:11px;opacity:.55;text-align:center';
  info.textContent=modelInfoLine();
  return info;
}
function showStartupTrace(){
  if(_startupTraced)return; _startupTraced=true;
  const bub=document.querySelector('#messages .msg.assistant .bubble');
  const host=bub?bub.parentNode:null;
  if(!host)return;
  const info=document.createElement('div');
  info.style.cssText='margin-top:5px;font-size:11px;opacity:.6';
  info.textContent=modelInfoLine();
  host.appendChild(info);
}
function announceModel(startupOnly){
  const box=document.getElementById('messages');
  if(startupOnly&&box&&box.children.length>0)return; // chat not empty: skip the startup trace
  const r=addMsg('assistant',(typeof t==='function'?t('welcome.line1'):'New conversation.'));
  const info=document.createElement('div');
  info.style.cssText='margin-top:5px;font-size:11px;opacity:.6';
  info.textContent=modelInfoLine();
  r.inner.appendChild(info);
}
// A reasoning token arrived mid-stream. When the model's mode is declared in the
// ini (or it is a controllable model) the button is the single source of truth,
// so we never latch it on from the stream -- that was the v0.806 regression that
// made Magistral's THINK-off impossible to hold. Only an UNDECLARED, otherwise
// non-controllable model (an unexpected reasoner behind [default]) surfaces the
// panel this way.
function markThinking(){
  if(THINK_MODE||INSTRUCTED||THINK_KWARG)return;
  THINK_CAPABLE=true; THINK_NATIVE=true; IS_THINK_ON=true;
  const btn=document.getElementById('think-btn');
  if(btn){btn.style.display='';btn.classList.add('on');btn.textContent='THINK ●';}
  syncThinkPrompt();
}
function toggleThink(){
  IS_THINK_ON=!IS_THINK_ON;
  localStorage.setItem('sthink',IS_THINK_ON?'1':'0');
  syncThinkPrompt();
  const btn=document.getElementById('think-btn');
  if(btn){btn.classList.toggle('on',IS_THINK_ON);btn.textContent=IS_THINK_ON?'THINK ●':'THINK';}
}
