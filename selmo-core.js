'use strict';
// GAUGE
function pt(deg,r){const a=(deg-90)*Math.PI/180;return[CX+r*Math.cos(a),CY+r*Math.sin(a)];}
function ap(a1,a2,r){const[sx,sy]=pt(a1,r),[ex,ey]=pt(a2,r);return`M ${sx} ${sy} A ${r} ${r} 0 ${a2-a1>180?1:0} 1 ${ex} ${ey}`;}
function makeGauge(mount,labelText){
  const NS='http://www.w3.org/2000/svg';
  mount.innerHTML='<svg class="mini-gauge" viewBox="0 0 220 190">'
    +'<circle cx="110" cy="100" r="88" fill="url(#bz)"/>'
    +'<circle cx="110" cy="100" r="81" fill="#000033" stroke="#555" stroke-width="1"/>'
    +'<circle cx="110" cy="100" r="76" fill="url(#dF)"/>'
    +'<path class="zz1" fill="none" stroke="#004400" stroke-width="7" stroke-linecap="round"/>'
    +'<path class="zz2" fill="none" stroke="#444400" stroke-width="7" stroke-linecap="round"/>'
    +'<path class="zz3" fill="none" stroke="#440000" stroke-width="7" stroke-linecap="round"/>'
    +'<path class="garc" fill="none" stroke="#55FF55" stroke-width="5" stroke-linecap="round" style="transition:stroke .4s;"/>'
    +'<g class="gticks"></g>'
    +'<text class="glab" x="110" y="138" text-anchor="middle" fill="#CCD8F0" font-size="14" font-weight="bold" font-family="Share Tech Mono,Lucida Console,Courier New,monospace" letter-spacing=".06em">'+labelText+'</text>'
    +'<text class="gv" x="110" y="160" text-anchor="middle" fill="#55FF55" font-size="22" font-family="Share Tech Mono,Lucida Console,Courier New,monospace" font-weight="bold" style="transition:fill .3s;">0%</text>'
    +'<text class="gsb" x="110" y="178" text-anchor="middle" fill="#AAAAAA" font-size="12" font-family="Share Tech Mono,Lucida Console,Courier New,monospace"></text>'
    +'<polygon class="gn" fill="url(#ng)" style="transform-origin:110px 100px;transition:transform .4s cubic-bezier(.4,0,.2,1);filter:drop-shadow(0 0 3px rgba(255,0,0,.5));"/>'
    +'<polygon class="gnw" fill="#770000" style="transform-origin:110px 100px;transition:transform .4s cubic-bezier(.4,0,.2,1);"/>'
    +'<circle cx="110" cy="100" r="8" fill="#222" stroke="#888" stroke-width="1.5"/>'
    +'<circle cx="110" cy="100" r="5" fill="#111"/>'
    +'<circle cx="110" cy="100" r="2.5" fill="#AAAAAA"/>'
    +'</svg>';
  const q=s=>mount.querySelector(s);
  q('.zz1').setAttribute('d',ap(-135,-10,R-2));
  q('.zz2').setAttribute('d',ap(-10,70,R-2));
  q('.zz3').setAttribute('d',ap(70,135,R-2));
  const tg=q('.gticks');
  for(let i=0;i<=20;i++){
    const a=-135+(i/20)*270,maj=i%4===0;
    const p1=pt(a,R*(maj?.82:.89)),p2=pt(a,R*.95);
    const ln=document.createElementNS(NS,'line');
    ln.setAttribute('x1',p1[0]);ln.setAttribute('y1',p1[1]);ln.setAttribute('x2',p2[0]);ln.setAttribute('y2',p2[1]);
    ln.setAttribute('stroke',maj?'#FFFF00':'#555577');ln.setAttribute('stroke-width',maj?2:1);
    tg.appendChild(ln);
  }
  const arc=q('.garc'),gv=q('.gv'),gsb=q('.gsb'),needle=q('.gn'),needlew=q('.gnw');
  return function(pct,sub){
    pct=Math.max(0,Math.min(pct,100));
    const a=-135+(pct/100)*270,col=pct<30?'#55FF55':pct<70?'#FFFF00':'#FF5555';
    const aRad=a*Math.PI/180;
    if(pct>0.5){arc.setAttribute('d',ap(-135,a,R-2));arc.style.stroke=col;arc.style.filter='drop-shadow(0 0 3px '+col+')';}
    else arc.setAttribute('d','');
    const tipR=R*.76,tx=CX+tipR*Math.sin(aRad),ty=CY-tipR*Math.cos(aRad);
    const bw=5,al=(a-90)*Math.PI/180,ar=(a+90)*Math.PI/180;
    const b1x=CX+bw*Math.sin(al),b1y=CY-bw*Math.cos(al),b2x=CX+bw*Math.sin(ar),b2y=CY-bw*Math.cos(ar);
    needle.setAttribute('points',tx+','+ty+' '+b1x+','+b1y+' '+b2x+','+b2y);
    const wRad=((a+180)*Math.PI)/180,wx=CX+R*.22*Math.sin(wRad),wy=CY-R*.22*Math.cos(wRad);
    needlew.setAttribute('points',b1x+','+b1y+' '+b2x+','+b2y+' '+wx+','+wy);
    gv.textContent=Math.round(pct)+'%';gv.style.fill=col;gv.style.filter='drop-shadow(0 0 5px '+col+'60)';
    gsb.textContent=sub||'';
  };
}
function setGauge(pct,watts,real){
  pct=Math.max(0,Math.min(pct,100));
  const a=-135+(pct/100)*270,col=pct<30?'#55FF55':pct<70?'#FFFF00':'#FF5555';
  const aRad=a*Math.PI/180;
  const arc=document.getElementById('arc');
  if(pct>0.5){arc.setAttribute('d',ap(-135,a,R-2));arc.style.stroke=col;arc.style.filter=`drop-shadow(0 0 3px ${col})`;}
  else{arc.setAttribute('d','');}
  const tipR=R*.76,tx=CX+tipR*Math.sin(aRad),ty=CY-tipR*Math.cos(aRad);
  const bw=5,al=(a-90)*Math.PI/180,ar=(a+90)*Math.PI/180;
  const b1x=CX+bw*Math.sin(al),b1y=CY-bw*Math.cos(al),b2x=CX+bw*Math.sin(ar),b2y=CY-bw*Math.cos(ar);
  document.getElementById('needle').setAttribute('points',`${tx},${ty} ${b1x},${b1y} ${b2x},${b2y}`);
  const wRad=((a+180)*Math.PI)/180,wx=CX+R*.22*Math.sin(wRad),wy=CY-R*.22*Math.cos(wRad);
  document.getElementById('needlew').setAttribute('points',`${b1x},${b1y} ${b2x},${b2y} ${wx},${wy}`);
  const gv=document.getElementById('gval');
  gv.textContent=Math.round(watts)+'W';
  gv.style.fill=col;gv.style.filter=`drop-shadow(0 0 5px ${col}60)`;
  {const _gw=gpuPwr>0?gpuPwr:gpuW;
   const _t=(cpuW>0||_gw>0)?((cpuEst?'~':'')+'CPU '+Math.round(cpuW)+'W \u00b7 GPU '+Math.round(_gw)+'W'):'-';
   const _ps=document.getElementById('pw-split');if(_ps)_ps.textContent=_t;
   const _gs=document.getElementById('gsub');if(_gs)_gs.textContent='';}
  document.getElementById('glabel').textContent='SYSTEM';
  // mobile horizontal bar
  const barFill=document.getElementById('watt-bar-fill');
  const barLabel=document.getElementById('watt-bar-label');
  if(barFill){
    const barPct=Math.min(pct,100);
    barFill.style.width=barPct+'%';
    barFill.style.background=col;
    barFill.style.boxShadow='0 0 6px '+col;
  }
  if(barLabel){
    barLabel.textContent=Math.round(watts)+'W'+((real&&!cpuEst)?'':' ~');
    barLabel.style.color=col;
  }
  const tbFill=document.getElementById('gpu-topbar-fill');
  if(tbFill){tbFill.style.width=Math.min(pct,100)+'%';tbFill.style.background=col;tbFill.style.boxShadow='0 0 6px '+col;}
  // CPU + GPU utilisation segments (device topbar)
  const _uc=v=>v<50?'var(--green)':v<80?'var(--yellow)':'var(--red)';
  const cpuFill=document.getElementById('tb-cpu-fill'),cpuLbl=document.getElementById('tb-cpu-lbl');
  if(cpuFill){const v=cpuP>=0?cpuP:0;cpuFill.style.width=Math.min(v,100)+'%';cpuFill.style.background=_uc(v);}
  if(cpuLbl)cpuLbl.textContent='CPU '+(cpuP>=0?Math.round(cpuP)+'%':'--');
  const gFill=document.getElementById('tb-gpu-fill'),gLbl=document.getElementById('tb-gpu-lbl');
  if(gFill){const v=gpuOk?gpuP:0;gFill.style.width=Math.min(v,100)+'%';gFill.style.background=_uc(v);}
  if(gLbl)gLbl.textContent='GPU '+(gpuOk?Math.round(gpuP)+'%':'--');
  const vF=document.getElementById('tb-vram-fill'),vL=document.getElementById('tb-vram-lbl');
  if(vF){const v=vramPct>=0?vramPct:0;vF.style.width=Math.min(v,100)+'%';vF.style.background=_uc(v);}
  if(vL)vL.textContent='VRAM '+(vramPct>=0?Math.round(vramPct)+'%':'--');
  const rF=document.getElementById('tb-ram-fill'),rL=document.getElementById('tb-ram-lbl');
  if(rF){const v=ramPct>=0?ramPct:0;rF.style.width=Math.min(v,100)+'%';rF.style.background=_uc(v);}
  if(rL)rL.textContent='RAM '+(ramPct>=0?Math.round(ramPct)+'%':'--');
}
function setOdo(v){
  const s=v.toFixed(1).replace('.','').padStart(ODO,'0');  // 0.1 Wh resolution
  s.split('').forEach((c,i)=>{
    const n=parseInt(c),dr=drums[i];
    if(n!==dr.cur){dr.cur=n;dr.el.style.transform=`translateY(${-n*36}px)`;
      dr.el.querySelectorAll('.odo-d').forEach((el,j)=>el.classList.toggle('lit',j===n));}
  });
}
// PRICE
function savePrice(v){price=parseFloat(v)||0.28;localStorage.setItem('sprice',price.toFixed(3));}
function updCost(){
  document.getElementById('cost-s').textContent='E'+(wh/1000*price).toFixed(4);
  document.getElementById('cost-t').textContent='E'+(whAll/1000*price).toFixed(4);
}
function resetWh(){if(!confirm('Reset total Wh?'))return;fetch(GMON+'/reset_total').catch(()=>{});whAll=0;document.getElementById('wh-total').textContent='0.000';updCost();}
function resetWhSession(){if(!confirm('Reset session Wh?'))return;fetch(GMON+'/reset_session').catch(()=>{});wh=0;document.getElementById('wh-s').textContent='0.000';updCost();}
function resetToks(){if(!confirm('Reset total token counter?'))return;toks=0;localStorage.setItem('stoks','0');document.getElementById('tok-tot').textContent='0';}
// POLL
async function poll(){
  // tok/sec: client-side from stream timing (reliable across llama.cpp versions)
  tokSec=gen&&_genT0>0?_genTok/((Date.now()-_genT0)/1000):0;

  let watts,real;
  if(sysW>0){watts=sysW;real=true;}
  else{
    // monitor unreachable: rough estimate from generation speed, then add losses
    const comp=gen?(tokSec>20?80+(tokSec-20)*2:tokSec>8?45+(tokSec-8)*2.5:25+tokSec*2.5):8;
    watts=Math.round((comp+OTHER_DC_EST)/PSU_EFF_EST);real=false;
  }
  const dp=Math.min((watts/SYS_MAX)*100,100);
  setGauge(dp,watts,real);

  // Energy (Wh) is integrated by the backend monitor (8082) as the single
  // source of truth, so any number of open UIs can never double-count. wh and
  // whAll are filled from its JSON in the monitor-fetch handler above.
  setOdo(wh);
  document.getElementById('wh-s').textContent=wh.toFixed(3);
  const _tbLbl=document.getElementById('gpu-topbar-lbl');
  if(_tbLbl)_tbLbl.textContent='SYS '+(real?'':'~')+Math.round(watts)+'W';
  document.getElementById('wh-total').textContent=whAll.toFixed(3);
  updCost();
  document.getElementById('tok-tot').textContent=toks.toLocaleString('en');
  {const sf=document.getElementById('speed-fill');
  sf.style.width=Math.min((tokSec/_tokScale)*100,100)+'%';
  sf.style.background=tokSec>0?(tokSec<10?'#ff4444':tokSec<20?'#ffcc00':'var(--cyan)'):'var(--cyan)';}
  document.getElementById('tok-sec').textContent=tokSec>0?tokSec.toFixed(1):'-';
  const dot=document.getElementById('status-dot'),stxt=document.getElementById('status-txt');
  if(gen){dot.className='on';stxt.textContent='running';}
  else{dot.className='';stxt.textContent=tokSec>0?'ready':'waiting';}
  const el=Math.floor((Date.now()-sessStart)/1000);
  document.getElementById('hdr-session').textContent=String(Math.floor(el/60)).padStart(2,'0')+':'+String(el%60).padStart(2,'0');
}
