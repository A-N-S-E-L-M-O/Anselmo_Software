'use strict';
async function extractDocx(file){
  if(typeof JSZip==='undefined') throw new Error('JSZip not loaded');
  const buf=await file.arrayBuffer();
  const zip=await JSZip.loadAsync(buf);
  const xmlFile=zip.file('word/document.xml');
  if(!xmlFile) throw new Error('Invalid docx file');
  const xml=await xmlFile.async('string');
  const NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main';
  const parser=new DOMParser();
  const doc=parser.parseFromString(xml,'application/xml');
  if(doc.querySelector('parsererror')){
    // fallback regex
    return xml.split(/<\/w:p>/).map(para=>{
      return [...para.matchAll(/<w:t[^>]*>([^<]*)<\/w:t>/g)].map(m=>m[1]).join('');
    }).filter(l=>l.trim()).join('\n').replace(/\n{3,}/g,'\n\n').trim();
  }
  return Array.from(doc.getElementsByTagNameNS(NS,'p')).map(p=>
    Array.from(p.getElementsByTagNameNS(NS,'t')).map(t=>t.textContent).join('')
  ).filter(l=>l.trim()).join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
async function extractOdt(file){
  if(typeof JSZip==='undefined') throw new Error('JSZip not loaded');
  const buf=await file.arrayBuffer();
  const zip=await JSZip.loadAsync(buf);
  const xmlFile=zip.file('content.xml');
  if(!xmlFile) throw new Error('Invalid odt file');
  const xml=await xmlFile.async('string');
  const parser=new DOMParser();
  const doc=parser.parseFromString(xml,'application/xml');
  if(doc.querySelector('parsererror')) throw new Error('ODT content.xml not parsable');
  // Attraversa l'albero raccogliendo text:p e text:h.
  // Headings (text:h) are marked with \x00 as a chapter separator,
  // così splitChunks può tagliare preferenzialmente lì.
  const lines=[];
  const NS='urn:oasis:names:tc:opendocument:xmlns:text:1.0';
  function walk(node){
    if(node.namespaceURI===NS&&(node.localName==='p'||node.localName==='h')){
      const t=node.textContent.trim();
      if(t){
        if(node.localName==='h') lines.push('\x00'+t); // chapter marker
        else lines.push(t);
      }
      return;
    }
    for(const child of node.children) walk(child);
  }
  walk(doc.documentElement);
  return lines.join('\n').replace(/\n{3,}/g,'\n\n').trim();
}
async function extractPdf(file){
  if(typeof pdfjsLib==='undefined') throw new Error('PDF.js not loaded');
  const buf=await file.arrayBuffer();
  const pdf=await pdfjsLib.getDocument({data:buf}).promise;
  let text='';
  for(let i=1;i<=pdf.numPages;i++){
    const page=await pdf.getPage(i);
    const content=await page.getTextContent();
    const pageText=content.items.map(it=>it.str).join(' ').replace(/\s+/g,' ').trim();
    if(pageText) text+=`[Page ${i}]\n${pageText}\n\n`;
  }
  return text.trim();
}
async function extractSpreadsheet(file){
  if(typeof XLSX==='undefined') throw new Error('SheetJS not loaded');
  const buf=await file.arrayBuffer();
  const wb=XLSX.read(buf,{type:'array'});
  let text='';
  for(const sheetName of wb.SheetNames){
    const ws=wb.Sheets[sheetName];
    const csv=XLSX.utils.sheet_to_csv(ws,{blankrows:false});
    if(csv.trim()) text+=`[Foglio: ${sheetName}]\n${csv}\n\n`;
  }
  return text.trim();
}
async function extractPptx(file){
  if(typeof JSZip==='undefined') throw new Error('JSZip not loaded');
  const buf=await file.arrayBuffer();
  const zip=await JSZip.loadAsync(buf);
  const slideFiles=Object.keys(zip.files)
    .filter(n=>/^ppt\/slides\/slide\d+\.xml$/.test(n))
    .sort((a,b)=>{
      const na=parseInt(a.match(/\d+/)[0]),nb=parseInt(b.match(/\d+/)[0]);
      return na-nb;
    });
  let text='';
  for(const sf of slideFiles){
    const xml=await zip.files[sf].async('string');
    const doc=new DOMParser().parseFromString(xml,'text/xml');
    const parts=Array.from(doc.querySelectorAll('t')).map(t=>t.textContent).filter(t=>t.trim());
    if(parts.length){
      const n=sf.match(/\d+/)[0];
      text+=`[Slide ${n}]\n${parts.join(' ')}\n\n`;
    }
  }
  return text.trim();
}
async function extractOdp(file){
  if(typeof JSZip==='undefined') throw new Error('JSZip not loaded');
  const buf=await file.arrayBuffer();
  const zip=await JSZip.loadAsync(buf);
  const xmlFile=zip.file('content.xml');
  if(!xmlFile) throw new Error('content.xml not found');
  const xml=await xmlFile.async('string');
  const doc=new DOMParser().parseFromString(xml,'text/xml');
  // ODP uses namespaces: try querySelectorAll with escape, then fallback via NS
  const NS_DRAW='urn:oasis:names:tc:opendocument:xmlns:drawing:1.0';
  const NS_TEXT='urn:oasis:names:tc:opendocument:xmlns:text:1.0';
  const pages=Array.from(doc.getElementsByTagNameNS(NS_DRAW,'page'));
  let text='';
  pages.forEach((page,i)=>{
    const name=page.getAttributeNS(null,'name')||page.getAttribute('draw:name')||('Slide '+(i+1));
    const parts=Array.from(page.getElementsByTagNameNS(NS_TEXT,'p'))
      .map(t=>t.textContent.trim()).filter(Boolean);
    if(parts.length) text+=`[${name}]\n${parts.join(' ')}\n\n`;
  });
  if(!text.trim()){
    const allText=Array.from(doc.getElementsByTagNameNS(NS_TEXT,'p'))
      .map(t=>t.textContent.trim()).filter(Boolean);
    text=allText.join('\n');
  }
  return text.trim();
}
// + IMG/OCR: direct vision. Images -> as-is. PDF -> one image per page
// (no concatenated canvas): Gemma 4 resizes to the token budget, so one
// page at ~1280px on the long side is enough. See selmo-dev "Vision Gemma 4".
async function imgToJpegDataUrl(file,MAX_SIDE,quality){
  MAX_SIDE=MAX_SIDE||1280; quality=quality||0.85;
  let src,W,H,bmp=null;
  try{
    bmp=await createImageBitmap(file,{imageOrientation:'from-image'});
    src=bmp; W=bmp.width; H=bmp.height;
  }catch(_){
    src=await new Promise((res,rej)=>{
      const im=new Image(); const url=URL.createObjectURL(file);
      im.onload=()=>{URL.revokeObjectURL(url);res(im);};
      im.onerror=()=>{URL.revokeObjectURL(url);rej(new Error('Image not decodable by the browser (try saving it as JPG)'));};
      im.src=url;
    });
    W=src.naturalWidth; H=src.naturalHeight;
  }
  const scale=Math.min(1, MAX_SIDE/Math.max(W,H));
  const cw=Math.max(1,Math.round(W*scale)), ch=Math.max(1,Math.round(H*scale));
  const cv=document.createElement('canvas'); cv.width=cw; cv.height=ch;
  const ctx=cv.getContext('2d');
  ctx.fillStyle='#fff'; ctx.fillRect(0,0,cw,ch);
  ctx.drawImage(src,0,0,cw,ch);
  if(bmp&&bmp.close) bmp.close();
  return cv.toDataURL('image/jpeg',quality);
}
// Shared image-attach pipeline: used by the + IMG/OCR picker AND clipboard paste.
async function addImageFiles(files){
  const IMG_EXTS=['jpg','jpeg','png','gif','webp','heic','heif','bmp'];
  for(const file of files){
    const ext=(file.name||'').split('.').pop().toLowerCase();
    let dataUrls=[];
    const isImg=(file.type&&file.type.indexOf('image/')===0)||IMG_EXTS.includes(ext);
    if(isImg){
      dataUrls=[await imgToJpegDataUrl(file,1280,0.85)];
    } else if(ext==='pdf'){
      const buf=await file.arrayBuffer();
      const pdf=await pdfjsLib.getDocument({data:buf}).promise;
      const MAX_PAGES=8, MAX_SIDE=1280;
      const numPages=Math.min(pdf.numPages,MAX_PAGES);
      for(let i=1;i<=numPages;i++){
        const pg=await pdf.getPage(i);
        const base=pg.getViewport({scale:1});
        const scale=Math.min(2.5, MAX_SIDE/Math.max(base.width,base.height));
        const vp=pg.getViewport({scale});
        const cv=document.createElement('canvas');
        cv.width=Math.ceil(vp.width);cv.height=Math.ceil(vp.height);
        const c2=cv.getContext('2d');
        c2.fillStyle='#fff';c2.fillRect(0,0,cv.width,cv.height);
        await pg.render({canvasContext:c2,viewport:vp}).promise;
        dataUrls.push(cv.toDataURL('image/jpeg',0.85));
      }
      if(numPages<pdf.numPages) console.warn('Long PDF: only the first '+MAX_PAGES+' pages of '+pdf.numPages);
    } else {
      alert('Unsupported format for vision: '+(file.name||'(clipboard)')+'. Use + FILE for text documents.');
      continue;
    }
    const nm=file.name||('pasted-'+Date.now()+'.jpg');
    if(fileImage){fileImage.dataUrls=fileImage.dataUrls.concat(dataUrls);fileImage.names.push(nm);fileImage.pages=fileImage.dataUrls.length;}
    else{fileImage={dataUrls,mimeType:'image/jpeg',name:nm,names:[nm],pages:dataUrls.length};}
  }
  if(fileImage){
    fileDoc=null;fileDocNames=[];fileCtx=null;chunks=[];chunkIdx=0;
    document.getElementById('file-badge').style.display='flex';
    const nm=fileImage.names.length>1?fileImage.names.length+' files':fileImage.name;
    const pg=fileImage.pages>1?' ('+fileImage.pages+'p)':'';
    document.getElementById('file-name').textContent='🖼️ '+nm+pg;
    document.getElementById('input').placeholder='Image/PDF loaded for vision. Ask a question or request OCR...';
  }
}
async function loadFileAsImage(inp){
  const files=Array.from(inp.files);if(!files.length)return;
  const btn=document.getElementById('upload-img-btn');
  btn.textContent='...';
  try{ await addImageFiles(files); }
  catch(e){console.error('loadFileAsImage:',e);alert('Error: '+e.message);}
  btn.textContent='+ IMG/OCR';inp.value='';
}
// Clipboard paste: an image in the clipboard (screenshot, copied picture) is
// attached exactly like + IMG/OCR. Non-image pastes fall through to text paste.
async function handlePaste(e){
  const items=(e.clipboardData&&e.clipboardData.items)?Array.from(e.clipboardData.items):[];
  const imgs=items.filter(it=>it.kind==='file'&&it.type&&it.type.indexOf('image/')===0)
                  .map(it=>it.getAsFile()).filter(Boolean);
  if(!imgs.length)return;           // not an image: let the browser paste text
  e.preventDefault();
  const btn=document.getElementById('upload-img-btn');
  const prev=btn?btn.textContent:'';
  if(btn)btn.textContent='...';
  try{ await addImageFiles(imgs); }
  catch(err){console.error('paste image:',err);alert('Error: '+err.message);}
  if(btn)btn.textContent=prev||'+ IMG/OCR';
}
async function loadFile(inp){
  const files=Array.from(inp.files);if(!files.length)return;
  const btn=document.getElementById('upload-btn');
  btn.textContent='...';
  try{
    for(const file of files){
      const ext=file.name.split('.').pop().toLowerCase();
      let text='';
      if(ext==='docx') text=await extractDocx(file);
      else if(ext==='odt') text=await extractOdt(file);
      else if(['xlsx','xls','ods'].includes(ext)) text=await extractSpreadsheet(file);
      else if(ext==='pdf') text=await extractPdf(file);
      else if(ext==='pptx') text=await extractPptx(file);
      else if(ext==='odp') text=await extractOdp(file);
      else text=await file.text();
      if(!text.trim()){alert('Empty or unreadable file: '+file.name);continue;}
      // Multiple documents accepted: append and mark each file boundary.
      // On send, the combined text stays in context if it fits, otherwise
      // processDoc chunks it serially starting from the first loaded file.
      if(fileDoc){fileDoc=fileDoc+'\n\n===== FILE: '+file.name+' =====\n\n'+text;fileDocNames.push(file.name);}
      else{fileDoc=text;fileDocNames=[file.name];}
    }
    fileCtx=null;chunks=[];chunkIdx=0;fileImage=null;
    if(fileDoc){
      document.getElementById('file-badge').style.display='flex';
      document.getElementById('file-name').textContent=(fileDocNames.length>1?fileDocNames.length+' files \xb7 ':fileDocNames[0]+' \xb7 ')+fileDoc.length.toLocaleString('en')+' char';
      document.getElementById('input').placeholder='Document loaded. Type the task to run on the whole text (analysis, translation, extraction...).';
    }
  }catch(e){console.error('Error loadFile:',e);alert('Error: '+e.message+' (F12 for details)');}
  btn.textContent='+ FILE';inp.value='';
}
function detectHeadings(text){
  const lines=text.split('\n');
  return lines.map((line,i)=>{
    if(line.startsWith('\x00'))return line; // already marked (ODT structural)
    const t=line.trim();
    if(!t||t.length>100)return line;
    if(/[,;]$/.test(t))return line; // mid-sentence
    const prev=(lines[i-1]||'').trim();
    const next=(lines[i+1]||'').trim();
    // explicit heading keywords (IT + EN)
    if(/^(capitolo|chapter|parte|part|sezione|section|prologo|prologue|epilogo|epilogue|prefazione|preface|appendice|appendix)\b/i.test(t))return '\x00'+t;
    // roman numerals alone or plain number alone
    if(/^[IVXLCDM]{1,8}\.?\s*$/.test(t)||/^\d{1,3}\.?\s*$/.test(t))return '\x00'+t;
    // ALL CAPS short line (with Italian accented chars)
    if(/^[A-ZÀÈÉÌÒÙ][A-ZÀÈÉÌÒÙ\s\-\']{2,}$/.test(t)&&t.length<60)return '\x00'+t;
    // short line surrounded by blank lines on both sides
    if(t.length<60&&!prev&&!next)return '\x00'+t;
    return line;
  }).join('\n');
}
function splitChunks(text,size){
  // Paragraphs: every non-empty line. ODT headings have an \x00 prefix (from extractOdt).
  const paras=text.split('\n').filter(p=>p.trim());
  const result=[];
  let cur=[],len=0;
  let currentChapter='';   // current chapter title (updated on each heading)
  let chunkChapter='';     // chapter title at the start of the chunk being built
  const OVERLAP_LINES=2;
  let prevTail=[];

  function flush(){
    if(cur.length===0)return;
    const lines=cur.map(l=>l.startsWith('\x00')?l.slice(1):l);
    // Insert chapter metadata as the first line, so the prompt can use it
    const header=chunkChapter?'[CHAPTER: '+chunkChapter+']\n':'';
    result.push(header+lines.join('\n'));
    cur.length=0;len=0;
  }

  for(let i=0;i<paras.length;i++){
    const p=paras[i];
    const isHeading=p.startsWith('\x00');
    const budgetFull=(len+p.length>size&&cur.length>0);
    const atChapterBreak=(isHeading&&cur.length>0&&len>size*0.4);

    if(budgetFull||atChapterBreak){
      prevTail=cur.filter(l=>!l.startsWith('\x00')).slice(-OVERLAP_LINES);
      flush();
      // If we're at a new chapter, update the metadata; otherwise the chapter stays the same
      if(isHeading) currentChapter=p.slice(1);
      chunkChapter=currentChapter;
      if(prevTail.length>0){
        const ctx=prevTail.map(l=>l.startsWith('\x00')?l.slice(1):l);
        for(const l of ctx){cur.push('[ctx] '+l);len+=l.length+1;}
      }
    }

    // First heading of an empty chunk: record the chapter
    if(isHeading&&cur.length===0){currentChapter=p.slice(1);chunkChapter=currentChapter;}
    cur.push(p);len+=p.length+1;
  }
  flush();
  return result.filter(c=>c.replace(/^\[CHAPTER:.*\]$/m,'').replace(/^\[ctx\].*$/mg,'').trim().length>20);
}
function clearFile(){
  fileCtx=null;fileDoc=null;fileDocNames=[];fileImage=null;fileChat=null;chunks=[];chunkIdx=0;
  document.getElementById('file-badge').style.display='none';
  document.getElementById('input').placeholder='Type a message...';
}
