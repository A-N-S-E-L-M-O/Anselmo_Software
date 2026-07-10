'use strict';
async function pttStart(webSearch=false){
  if(!whisperOk||gen)return;
  if(mediaRecorder&&mediaRecorder.state==='recording')return;
  if(vadConvo&&vadInstance){try{vadInstance.pause();}catch(e){}vadAwaitingReply=true;vadSetState('busy');}
  pttAutoSend=true;
  pttWebSearch=webSearch;
  await toggleMic();
}
function pttStop(){
  if(mediaRecorder&&mediaRecorder.state==='recording')mediaRecorder.stop();
}
// ── VAD — conversazione a mani libere (Silero via @ricky0123/vad-web) ─────
// Il push-to-talk (Spazio / tasto centrale) bypassa il VAD: lo mette in pausa
// e usa il percorso MediaRecorder. Il VAD trascrive la frase quando rileva la
// pausa, invia da solo, resta in pausa durante generazione + TTS (anti-eco) e
// torna ad ascoltare a fine risposta.
function f32ToWav(samples,rate){
  const len=samples.length,buf=new ArrayBuffer(44+len*2),v=new DataView(buf);
  const ws=(o,str)=>{for(let i=0;i<str.length;i++)v.setUint8(o+i,str.charCodeAt(i));};
  ws(0,'RIFF');v.setUint32(4,36+len*2,true);ws(8,'WAVE');ws(12,'fmt ');
  v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
  v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);
  ws(36,'data');v.setUint32(40,len*2,true);
  let o=44;for(let i=0;i<len;i++){let x=Math.max(-1,Math.min(1,samples[i]));v.setInt16(o,x<0?x*0x8000:x*0x7FFF,true);o+=2;}
  return new Blob([buf],{type:'audio/wav'});
}
function vadSetState(state){
  const btn=document.getElementById('vad-btn');if(!btn)return;
  btn.classList.remove('listening','speaking','busy');
  if(state)btn.classList.add(state);
}
function vadResume(){
  vadAwaitingReply=false;
  if(vadConvo&&vadInstance&&!gen){
    try{vadInstance.start();}catch(e){}
    vadSetState('listening');
  }
}
function vadAfterSpeak(){
  _ttsPending=false;
  if(vadConvo&&vadAwaitingReply)vadResume();
}
async function vadOnSpeech(audio){
  if(!vadConvo)return;
  try{vadInstance.pause();}catch(e){}      // anti-eco: smetti di ascoltare
  vadSetState('busy');
  vadAwaitingReply=true;
  const blob=f32ToWav(audio,16000);
  const fd=new FormData();fd.append('audio',blob,'audio.wav');
  try{
    const r=await fetch(`${WHISPER}/transcribe`,{method:'POST',body:fd,signal:AbortSignal.timeout(30000)});
    const d=await r.json();
    if(d.error||!d.text||!d.text.trim()){vadResume();return;}  // niente di utile: riascolta
    const inp=document.getElementById('input');
    inp.value=d.text.trim();autoResize(inp);
    pttForceTts=true;                       // hands-free: leggi sempre la risposta
    setTimeout(sendMsg,30);
  }catch(e){
    console.warn('VAD transcribe error',e);
    vadResume();
  }
}
async function toggleVad(){
  const btn=document.getElementById('vad-btn');
  if(vadConvo){
    vadConvo=false;vadAwaitingReply=false;
    if(vadInstance){try{vadInstance.pause();}catch(e){}}
    vadSetState(null);
    if(btn)btn.title='Conversazione a mani libere (VAD) — rileva le pause e invia da solo';
    return;
  }
  if(!whisperOk){addMsg('assistant','\u26A0 Whisper non attivo. Avvia selmo_whisper.py per la conversazione a mani libere.');return;}
  if(typeof window.vad==='undefined'||!window.vad||!window.vad.MicVAD){
    addMsg('assistant','\u26A0 Libreria VAD non disponibile (serve connessione al CDN al primo avvio).');return;
  }
  if(!vadInstance){
    vadSetState('busy');
    try{
      vadInstance=await window.vad.MicVAD.new({
        model:'v5',
        onnxWASMBasePath:'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/',
        baseAssetPath:'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.29/dist/',
        onSpeechStart:()=>{if(vadConvo&&!gen)vadSetState('speaking');},
        onVADMisfire:()=>{if(vadConvo&&!gen)vadSetState('listening');},
        onSpeechEnd:(audio)=>{vadOnSpeech(audio);}
      });
    }catch(e){
      console.warn('VAD init error',e);
      addMsg('assistant','\u26A0 Avvio VAD fallito: '+e.message);
      vadSetState(null);return;
    }
  }
  vadConvo=true;
  try{vadInstance.start();}catch(e){}
  vadSetState('listening');
  if(btn)btn.title='Conversazione attiva — clicca per fermare';
}
// Image generation (port 8086, stable-diffusion.cpp / Z-Image-Turbo).
// No arg -> text-to-image (prompt only). A strength value (from the Subtle/
// Medium/Strong presets) -> image-to-image, reusing the loaded + IMG/OCR image.
function toggleImgMenu(e){
  if(e)e.stopPropagation();
  // No image loaded -> img2img makes no sense; go straight to text-to-image (one click less).
  const hasImg=fileImage&&fileImage.dataUrls&&fileImage.dataUrls.length;
  if(!hasImg){ genImage(); return; }
  const m=document.getElementById('img-menu');
  if(m)m.classList.toggle('open');
}
function pickImg(e,strength){
  if(e)e.stopPropagation();
  const m=document.getElementById('img-menu');if(m)m.classList.remove('open');
  genImage(strength);
}
async function genImage(strength){
  if(gen)return;
  const inp=document.getElementById('input');
  const prompt=inp.value.trim();
  const isI2I=(strength!==undefined)&&fileImage&&fileImage.dataUrls&&fileImage.dataUrls.length;
  if(strength!==undefined&&!isI2I){alert('Load an image with + IMG/OCR first to use image-to-image.');return;}
  if(!isI2I&&!prompt){alert('Type a prompt first.');return;}
  inp.value='';inp.style.height='auto';
  addMsg('user',(isI2I?('🎨 [img2img '+strength+'] '+(prompt||'(from image)')):('🎨 '+prompt)));
  const a=addMsg('assistant','',true);const bub=a.bub;
  bub.innerHTML='<span style="opacity:.6">⚡ '+(isI2I?'transforming':'generating')+' image…</span>';
  gen=true;
  const sendBtn=document.getElementById('send'),stopBtn=document.getElementById('stop');
  sendBtn.style.display='none';stopBtn.style.display='inline-block';
  setImageMode(true);   // image mode starts now: the LLM is being unloaded
  setModelState('imaging');   // flip the header to "image mode" immediately, don't wait for the next poll
  try{
    const body={prompt:prompt,width:1024,height:1024};
    if(isI2I){
      const dim=await new Promise(res=>{const t=new Image();t.onload=()=>res([t.naturalWidth,t.naturalHeight]);t.onerror=()=>res([1024,1024]);t.src=fileImage.dataUrls[0];});
      body.width=Math.round(dim[0]/16)*16;body.height=Math.round(dim[1]/16)*16;
      body.init_image=fileImage.dataUrls[0];body.strength=strength;
    }
    const r=await fetch(IMG_URL+'/generate',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });
    if(!r.ok){
      let msg='HTTP '+r.status;
      try{const j=await r.json();msg=(j.error||msg)+(j.detail?': '+j.detail:'')+(j.missing?' ('+j.missing.join('; ')+')':'');}catch(e){}
      bub.innerHTML='<span style="color:#f66">Image generation failed - '+msg+'</span>';return;
    }
    const secs=r.headers.get('X-Selmo-Gen-Seconds')||'?';
    const mdl=(r.headers.get('X-Selmo-Model')||'image').replace(/\.gguf$/i,'');
    const url=URL.createObjectURL(await r.blob());
    bub.innerHTML='';
    const im=new Image();
    im.src=url;im.title='click to enlarge ('+secs+'s)';
    im.style.cssText='max-width:100%;border:1px solid var(--cyan);border-radius:6px;cursor:zoom-in;background:#fff';
    im.onclick=function(){window.open(url,'_blank');};
    bub.appendChild(im);
    const cap=document.createElement('div');
    cap.style.cssText='font-size:11px;color:var(--dim);margin-top:4px';
    cap.textContent=mdl+' · '+(isI2I?('img2img '+strength+' · '):'')+secs+'s · '+(prompt||'(from image)');
    bub.appendChild(cap);scrollBot();
  }catch(e){
    bub.innerHTML='<span style="color:#f66">Image bridge unreachable - is selmo_image.py running on 8086? ('+e.message+')</span>';
  }finally{
    gen=false;sendBtn.style.display='inline-block';stopBtn.style.display='none';
    try{ const s=await fetch(`${CTRL}/status`,{signal:AbortSignal.timeout(2500)}).then(r=>r.json()); setImageMode(s&&s.swapped_for_image); }catch(e){}
  }
}
async function checkKokoroBridge(){
  const dot=document.getElementById('tts-dot');
  const txt=document.getElementById('tts-txt');
  try{
    const r=await fetch(`${TTS_URL}/status`,{signal:AbortSignal.timeout(2000)});
    if(r.ok){
      kokoroOk=true;ttsOk=true;
      dot.style.background='var(--green)';dot.style.borderColor='var(--green)';
      dot.style.boxShadow='0 0 4px var(--green)';
      txt.style.color='var(--green)';
      txt.textContent='tts kokoro';
      refreshCaps();return;
    }
  }catch(e){}
  // fallback Web Speech
  if('speechSynthesis' in window){
    ttsOk=true;
    dot.style.background='var(--yellow)';dot.style.borderColor='var(--yellow)';
    dot.style.boxShadow='0 0 4px var(--yellow)';
    txt.style.color='var(--yellow)';
    txt.textContent='tts sistema';
  }else{
    txt.textContent='tts n/d';
  }
  refreshCaps();
}
function toggleTts(){
  if(!ttsOk)return;
  ttsEnabled=!ttsEnabled;
  if(!ttsEnabled){
    if(kokoroOk){/* nothing to cancel */}
    else window.speechSynthesis.cancel();
  }
  const btn=document.getElementById('tts-btn');
  btn.classList.toggle('active',ttsEnabled);
  btn.title=ttsEnabled?'Reading on (click to turn off)':'Read responses aloud';
}
function cleanForTts(text){
  return text.replace(/\*+/g,'').replace(/`[^`]*`/g,'').replace(/```[\s\S]*?```/g,'')
             .replace(/#+\s/g,'').replace(/\[([^\]]+)\]\([^)]+\)/g,'$1')
             .replace(/\s+/g,' ').trim();
}
// Show/hide the STOP button while Selmo is speaking, so playback can be cut
// off. Mirrors the generation toggle (send hidden, stop shown) but only flips
// back to "send" when no generation is in flight.
function _ttsShowStop(on){
  const sb=document.getElementById('stop'),send=document.getElementById('send');
  if(!sb||!send)return;
  if(on){send.style.display='none';sb.style.display='inline-block';}
  else if(!gen){sb.style.display='none';send.style.display='inline-block';}
}
// Interrupt any speech in progress (manual STOP button only — NOT VAD/noise
// driven). Aborts the pending Kokoro fetch, stops the audio source, cancels
// Web Speech, then runs the same cleanup as a natural end so the UI returns
// to a ready state for the next interaction.
function stopTts(){
  if(!_ttsPending)return;
  _ttsStreamActive=false;
  _ttsQueue=[];_ttsBuf='';_ttsRawTail='';_ttsFence=false;
  if(_ttsAbort){try{_ttsAbort.abort();}catch(e){}_ttsAbort=null;}
  if(_ttsSources&&_ttsSources.length){_ttsSources.forEach(s=>{try{s.onended=null;s.stop(0);}catch(e){}});}
  _ttsSources=[];
  if(_ttsSrc){try{_ttsSrc.onended=null;_ttsSrc.stop(0);}catch(e){}_ttsSrc=null;}
  if(_ttsCtxS){try{_ttsCtxS.close();}catch(e){}_ttsCtxS=null;}
  if(_ttsCtx){try{_ttsCtx.close();}catch(e){}_ttsCtx=null;}   // legacy single-shot ctx
  if('speechSynthesis' in window){try{window.speechSynthesis.cancel();}catch(e){}}
  _ttsScheduled=0;_ttsNextAt=0;_ttsWorking=false;
  if(_ttsFire){_ttsFire();_ttsFire=null;}   // legacy single-shot fire
  _ttsFinish();
}
// --- TTS language: follow the TEXT, not the UI (models answer in whatever
// language they like). Kokoro is handled by the bridge (langdetect -> voice +
// speed); for the Web Speech fallback we do a light client-side detect here.
// Italian also gets a ~10% speed bump. (Fixes English being read with it-IT.)
function _detectLang(text){
  var t=' '+String(text||'').toLowerCase().replace(/[^a-zàèéìòù\s]/g,' ')+' ';
  var IT=[' il ',' la ',' che ',' di ',' un ',' per ',' non ',' sono ',' con ',' questo ',' anche ',' più ',' come ',' ma ',' una '];
  var EN=[' the ',' and ',' of ',' to ',' is ',' you ',' that ',' it ',' for ',' with ',' this ',' are ',' not ',' what ',' can ',' but '];
  function sc(a){var n=0,i,idx;for(i=0;i<a.length;i++){idx=0;while((idx=t.indexOf(a[i],idx))!==-1){n++;idx++;}}return n;}
  var it=sc(IT),en=sc(EN);
  if(it===0&&en===0)return (typeof SELMO_LANG!=='undefined'&&SELMO_LANG)?SELMO_LANG:'en';
  return it>en?'it':'en';
}
function _ttsProfile(l){
  l=l||'en';
  var web={it:'it-IT',en:'en-US',fr:'fr-FR',de:'de-DE',es:'es-ES',pt:'pt-BR'}[l]||'en-US';
  var rate=(l==='it')?1.10:1.0;                      // +10% for Italian
  return {web:web,rate:rate};
}
function _pickWebVoice(lang){
  try{
    var vs=window.speechSynthesis.getVoices()||[];
    var pre=lang.slice(0,2).toLowerCase();
    return vs.find(function(v){return v.lang&&v.lang.toLowerCase()===lang.toLowerCase();})
        || vs.find(function(v){return v.lang&&v.lang.toLowerCase().slice(0,2)===pre;})
        || null;
  }catch(e){return null;}
}
function _speakWeb(text,_fire){
  if(!('speechSynthesis' in window)){_fire();return;}
  var prof=_ttsProfile(_detectLang(text));
  window.speechSynthesis.cancel();
  var utt=new SpeechSynthesisUtterance(text);
  utt.lang=prof.web; utt.rate=prof.rate;
  var v=_pickWebVoice(prof.web); if(v)utt.voice=v;
  utt.onend=_fire; utt.onerror=_fire;
  _ttsShowStop(true);
  window.speechSynthesis.speak(utt);
}
// ---- Streaming TTS (v0.930) ------------------------------------------------
// Instead of synthesizing the whole answer once it finishes, we cut the
// streamed text into full sentences and speak them as they close, so playback
// starts on the first sentence and continues gaplessly. The language is locked
// from the first sentence so the voice can't flip mid-answer, and ``` code
// fences are skipped (a whole code block would otherwise be read out).
function _ttsKokoroLang(text){
  return {it:'it',en:'en-us',fr:'fr-fr',de:'de',es:'es',pt:'pt-br'}[_detectLang(text)]||'en-us';
}
function _ttsShortLang(){
  return {it:'it','en-us':'en','fr-fr':'fr',de:'de',es:'es','pt-br':'pt'}[_ttsLang]||(_ttsLang?'en':null);
}
// Append raw streamed markdown to the speakable buffer, dropping ``` fenced
// blocks. Keeps up to 2 trailing chars back in case a ``` marker is split
// across chunks.
function _ttsIngest(chunk){
  let s=_ttsRawTail+chunk;_ttsRawTail='';let i=0;
  while(i<s.length){
    const fi=s.indexOf('```',i);
    if(fi===-1){
      const cut=Math.max(i,s.length-2);
      if(!_ttsFence)_ttsBuf+=s.slice(i,cut);
      _ttsRawTail=s.slice(cut);break;
    }
    if(!_ttsFence)_ttsBuf+=s.slice(i,fi);
    _ttsFence=!_ttsFence;i=fi+3;
  }
}
// End index of the first COMPLETE sentence in s, or -1. '.' '!' '?' count only
// when followed by whitespace (so decimals like 3.14 don't split); a newline
// always ends a line. A terminator at the very end waits for more text unless
// the stream has finished.
function _ttsFindEnd(s){
  for(let i=0;i<s.length;i++){
    const c=s[i];
    if(c==='\n')return i;
    if(c==='.'||c==='!'||c==='?'){
      const nx=s[i+1];
      if(nx===undefined)return _ttsStreamDone?i:-1;
      if(/\s/.test(nx))return i;
    }
  }
  return -1;
}
function _ttsDrain(){
  let idx;
  while((idx=_ttsFindEnd(_ttsBuf))!==-1){
    const sentence=cleanForTts(_ttsBuf.slice(0,idx+1));
    _ttsBuf=_ttsBuf.slice(idx+1);
    if(sentence)_ttsEnqueue(sentence);
  }
}
function _ttsEnqueue(sentence){
  if(_ttsLang===null)_ttsLang=_ttsKokoroLang(sentence);
  _ttsQueue.push(sentence);
  _ttsPump();
}
// One consumer at a time. Synthesize + schedule each sentence, returning as
// soon as it is SCHEDULED (not when it finishes) so the next sentence is
// synthesized while the current one is still playing.
async function _ttsPump(){
  if(_ttsWorking||!_ttsStreamActive)return;
  _ttsWorking=true;
  try{
    while(_ttsStreamActive&&_ttsQueue.length){
      await _ttsSynthPlay(_ttsQueue.shift());
    }
  }finally{
    _ttsWorking=false;
    _ttsMaybeFinish();
  }
}
async function _ttsSynthPlay(text){
  if(!kokoroOk){_speakWebQueue(text);return;}
  let buf;
  try{
    _ttsAbort=new AbortController();
    const r=await fetch(`${TTS_URL}/speak`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text,lang:_ttsLang||undefined}),   // lang locked so the voice stays put
      signal:_ttsAbort.signal
    });
    if(!r.ok)throw new Error('TTS error '+r.status);
    buf=await r.arrayBuffer();
  }catch(e){
    if(e&&e.name==='AbortError')return;   // stopped by the user
    console.warn('Kokoro TTS error, fallback Web Speech:',e);
    _speakWebQueue(text);return;
  }
  if(!_ttsStreamActive)return;
  const ctx=_ttsCtxS||(_ttsCtxS=new(window.AudioContext||window.webkitAudioContext)());
  let decoded;
  try{decoded=await ctx.decodeAudioData(buf);}catch(e){return;}
  if(!_ttsStreamActive)return;
  const src=ctx.createBufferSource();
  src.buffer=decoded;src.connect(ctx.destination);
  const startAt=Math.max(ctx.currentTime,_ttsNextAt);   // schedule right after the previous one -> gapless
  _ttsNextAt=startAt+decoded.duration;
  _ttsSources.push(src);_ttsSrc=src;_ttsScheduled++;
  src.onended=()=>{
    const k=_ttsSources.indexOf(src);if(k>=0)_ttsSources.splice(k,1);
    _ttsScheduled--;_ttsMaybeFinish();
  };
  _ttsShowStop(true);
  src.start(startAt);
}
function _speakWebQueue(text){
  if(!('speechSynthesis' in window))return;
  const prof=_ttsProfile(_ttsShortLang()||_detectLang(text));
  const utt=new SpeechSynthesisUtterance(text);
  utt.lang=prof.web;utt.rate=prof.rate;
  const v=_pickWebVoice(prof.web);if(v)utt.voice=v;
  _ttsScheduled++;
  const dec=()=>{_ttsScheduled--;_ttsMaybeFinish();};
  utt.onend=dec;utt.onerror=dec;
  _ttsShowStop(true);
  window.speechSynthesis.speak(utt);   // Web Speech queues utterances natively, so order is preserved
}
function _ttsMaybeFinish(){
  if(_ttsStreamDone&&!_ttsQueue.length&&!_ttsWorking&&_ttsScheduled<=0)_ttsFinish();
}
function _ttsFinish(){
  if(!_ttsPending)return;
  _ttsPending=false;_ttsStreamActive=false;
  try{if(_ttsCtxS)_ttsCtxS.close();}catch(e){}
  _ttsCtxS=null;_ttsSources=[];_ttsScheduled=0;_ttsNextAt=0;_ttsSrc=null;_ttsAbort=null;
  _ttsShowStop(false);
  vadAfterSpeak();
}
// Public API used by the send paths: start before the stream, feed each content
// delta, end when the stream closes.
function ttsSpeakStart(){
  const _force=pttForceTts;pttForceTts=false;
  _ttsStreamActive=!!(ttsOk&&(ttsEnabled||_force));
  _ttsQueue=[];_ttsBuf='';_ttsRawTail='';_ttsFence=false;_ttsStreamDone=false;
  _ttsWorking=false;_ttsLang=null;_ttsNextAt=0;_ttsScheduled=0;_ttsSources=[];_ttsCtxS=null;
  if(_ttsStreamActive)_ttsPending=true;
  return _ttsStreamActive;
}
function ttsSpeakFeed(chunk){
  if(!_ttsStreamActive||!chunk)return;
  _ttsIngest(chunk);
  _ttsDrain();
}
function ttsSpeakEnd(){
  if(!_ttsStreamActive){vadAfterSpeak();return;}
  _ttsStreamDone=true;
  if(_ttsRawTail){if(!_ttsFence)_ttsBuf+=_ttsRawTail;_ttsRawTail='';}
  _ttsDrain();
  const rest=cleanForTts(_ttsBuf);_ttsBuf='';   // trailing text with no terminator
  if(rest)_ttsEnqueue(rest);
  _ttsMaybeFinish();
}
// Back-compat: speak a full string in one shot (start + feed + end).
function speakText(text){
  if(!ttsSpeakStart())return;
  ttsSpeakFeed(text);
  ttsSpeakEnd();
}
