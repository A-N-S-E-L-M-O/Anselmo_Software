'use strict';
// Tray-in-browser settings (v0.905): switch LLM + image models, edit srv/params
// at switch time, and service controls. Talks to the tray control API on 8087
// through the front door (CTRL=/proxy/8087). Pure function module, no top-level init.

let _llmModels=[], _imgModels=[], _selLlm=null, _selImg=null;

function _esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function _setStatus(t){var s=document.getElementById('set-status');if(s)s.textContent=t;}
function _clip(n){return n.length>26?n.slice(0,26)+'…':n;}

function openSettings(){var m=document.getElementById('settings-modal');if(m){m.classList.add('show');loadSettingsModels();loadImageModels();}}
function closeSettings(){var m=document.getElementById('settings-modal');if(m)m.classList.remove('show');}

// ---------- LLM models ----------
async function loadSettingsModels(){
  var list=document.getElementById('set-model-list');
  var ed=document.getElementById('set-llm-editor');if(ed)ed.style.display='none';
  _selLlm=null;
  list.innerHTML='<div class="set-empty">loading...</div>';
  try{
    var r=await fetch(CTRL+'/models',{cache:'no-store'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    var d=await r.json();_llmModels=d.models||[];
    var cur=d.current||'';
    _setStatus(d.loaded?('LLM loaded: '+(cur||'-')):(cur?('LLM unloaded ('+cur+')'):'no model loaded'));
    if(!_llmModels.length){list.innerHTML='<div class="set-empty">no models in models\\</div>';return;}
    list.innerHTML='';
    _llmModels.forEach(function(m){
      var act=(m.name===cur);
      var it=document.createElement('button');
      it.className='set-item'+(act?' active':'');
      it.innerHTML='<span>'+_esc(m.name)+'</span><small>'+(act?'current':'edit & load')+'</small>';
      it.onclick=function(){selectLLM(m.name);};
      list.appendChild(it);
    });
  }catch(e){
    _setStatus('control API unreachable: '+e.message);
    list.innerHTML='<div class="set-empty">cannot reach the tray control API (8087). Is Selmo running on the host?</div>';
  }
}
function selectLLM(name){
  _selLlm=_llmModels.find(function(m){return m.name===name;});if(!_selLlm)return;
  document.getElementById('set-srv').value=_selLlm.srv||'';
  document.getElementById('set-chunk').value=_selLlm.chunking_size||0;
  document.getElementById('set-load-name').textContent=_clip(name);
  var b=document.getElementById('set-load-btn');b.disabled=false;
  document.getElementById('set-llm-editor').style.display='';
  _setStatus('editing flags for '+name+' — review and Load');
}
async function confirmSwitch(){
  if(!_selLlm)return;
  var name=_selLlm.name;
  var srv=document.getElementById('set-srv').value;
  var chunk=document.getElementById('set-chunk').value;
  if(!confirm('Load model:\n'+name+'\n\nThis stops the current model and starts the new one.'))return;
  document.getElementById('set-load-btn').disabled=true;
  _setStatus('switching to '+name+' ...');
  if(typeof setModelState==='function')setModelState('loading');
  try{
    var r=await fetch(CTRL+'/llm/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,srv:srv,chunking_size:chunk})});
    var d=await r.json().catch(function(){return{};});
    if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status));
    _setStatus('loading '+name+' ... (waiting for the model to come up)');
    await waitLLMReady(120);
    _setStatus('ready — reloading the page...');
    location.reload();
  }catch(e){
    _setStatus('switch failed: '+e.message);
    document.getElementById('set-load-btn').disabled=false;
  }
}

// ---------- image models ----------
async function loadImageModels(){
  var list=document.getElementById('set-img-list');
  var ed=document.getElementById('set-img-editor');if(ed)ed.style.display='none';
  _selImg=null;
  list.innerHTML='<div class="set-empty">loading...</div>';
  try{
    var r=await fetch(CTRL+'/image/models',{cache:'no-store'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    var d=await r.json();_imgModels=d.models||[];
    var cur=d.current||'';
    if(!_imgModels.length){list.innerHTML='<div class="set-empty">no image models in image\\</div>';return;}
    list.innerHTML='';
    _imgModels.forEach(function(m){
      var act=(m.name===cur);
      var it=document.createElement('button');
      it.className='set-item'+(act?' active':'');
      it.innerHTML='<span>'+_esc(m.name)+'</span><small>'+(act?'current':'edit & apply')+'</small>';
      it.onclick=function(){selectImg(m.name);};
      list.appendChild(it);
    });
  }catch(e){
    list.innerHTML='<div class="set-empty">image models unavailable: '+_esc(e.message)+'</div>';
  }
}
function selectImg(name){
  _selImg=_imgModels.find(function(m){return m.name===name;});if(!_selImg)return;
  document.getElementById('set-img-params').value=_selImg.params||'';
  document.getElementById('set-img-name').textContent=_clip(name);
  var b=document.getElementById('set-img-btn');b.disabled=false;
  document.getElementById('set-img-editor').style.display='';
}
async function confirmImage(){
  if(!_selImg)return;
  var name=_selImg.name;var params=document.getElementById('set-img-params').value;
  document.getElementById('set-img-btn').disabled=true;
  try{
    var r=await fetch(CTRL+'/image/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name,params:params})});
    var d=await r.json().catch(function(){return{};});
    if(!r.ok||d.ok===false)throw new Error(d.error||('HTTP '+r.status));
    _setStatus('image model set: '+name+' (applies on the next generation)');
    loadImageModels();
  }catch(e){
    _setStatus('image select failed: '+e.message);
  }
  document.getElementById('set-img-btn').disabled=false;
}

// ---------- service ----------
async function waitLLMReady(tries){
  for(var i=0;i<tries;i++){
    try{var r=await fetch(API+'/props',{cache:'no-store'});if(r.ok)return true;}catch(e){}
    await new Promise(function(res){setTimeout(res,1500);});
  }
  return false;
}
async function unloadLLM(){_setStatus('unloading (freeing VRAM)...');try{await fetch(CTRL+'/llm/unload',{method:'POST'});}catch(e){}if(typeof setModelState==='function')setModelState('unloaded');setTimeout(loadSettingsModels,700);}
async function reloadLLM(){_setStatus('reloading model...');if(typeof setModelState==='function')setModelState('loading');try{await fetch(CTRL+'/llm/reload',{method:'POST'});await waitLLMReady(120);location.reload();return;}catch(e){}loadSettingsModels();}
async function exitSelmo(){
  if(!confirm('Exit Selmo?\n\nThis stops the model AND all services. The web UI will be unreachable until you start Selmo again from your computer.'))return;
  _setStatus('shutting down...');
  try{await fetch(CTRL+'/control/exit',{method:'POST'});}catch(e){}
  setTimeout(function(){document.body.innerHTML='<div style="font-family:monospace;color:#88aabb;padding:48px;text-align:center;font-size:14px">Selmo has shut down.<br><br>Start it again from your computer to reconnect.</div>';},900);
}
