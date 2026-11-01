'use strict';
const $=id=>document.getElementById(id);
let config=null,liveProgram=null,dirty=false,connected=false,applying=false,version=0,rate=44100,ratePinned=false;
const clone=x=>JSON.parse(JSON.stringify(x));
const showError=s=>{$('error').textContent=s||'';$('error').hidden=!s;};
async function request(path,options){const r=await fetch(path,options);if(!r.ok)throw Error(await r.text()||'Device request failed.');return r;}
function draftProgram(){return config?NookEQ.program(config):null;}
function updateButtons(){let valid=false;try{valid=!!draftProgram();}catch{}$('apply').disabled=!valid||!connected||applying||!dirty;$('add').disabled=!config||config.bands.length>=8;$('revert').disabled=!dirty||!connected;$('revert').hidden=!dirty;$('export').disabled=!valid;}
function changed(){version++;dirty=true;$('preset').value='';$('edit-state').textContent='Draft';showError('');try{draftProgram();draw();}catch(e){showError(e.message);}updateButtons();}
function element(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function field(b,key,label,min,max,step,index){const n=document.createElement('input');n.type='number';n.min=min;n.max=max;n.step=step;n.value=b[key];n.setAttribute('aria-label',`Band ${index+1} ${label}`);n.addEventListener('input',()=>{b[key]=n.valueAsNumber;changed();});return n;}
function render(){
 $('bands').replaceChildren();
 if(config)config.bands.forEach((b,i)=>{const row=element('div','band');row.append(element('span','band-id',String(i+1)),field(b,'frequency_hz','frequency',10,22049,1,i),field(b,'gain_db','gain',-12,12,.1,i),field(b,'q','Q',.1,20,.1,i));const remove=element('button','remove','×');remove.setAttribute('aria-label',`Remove band ${i+1}`);remove.onclick=()=>{config.bands.splice(i,1);render();changed();};row.append(remove);$('bands').append(row);});
 $('empty').hidden=!!config?.bands.length;
 $('empty').textContent=config?'No bands · flat response':'Current EQ retained. Choose a preset to edit.';
 $('preamp').disabled=!config;$('enabled').disabled=!config;
 if(config){$('preamp').value=config.preamp_db;$('preamp-value').textContent=`${config.preamp_db.toFixed(1)} dB`;$('enabled').setAttribute('aria-checked',String(config.enabled));$('enabled').textContent=config.enabled?'EQ on':'Bypass';}
 else{$('preamp-value').textContent='—';$('enabled').textContent='EQ';}
 updateButtons();draw();
}
function svg(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,v));if(text!==undefined)n.textContent=text;return n;}
function draw(){
 let p;try{p=draftProgram()||liveProgram;}catch{return;}if(!p)return;
 const points=NookEQ.curve(p,rate),chart=$('chart');chart.replaceChildren();
 const width=Math.max(280,chart.clientWidth||800),height=width<560?150:176;chart.setAttribute('viewBox',`0 0 ${width} ${height}`);
 const lo=Math.min(-18,Math.floor(Math.min(...points.map(x=>x[1]))/6)*6),hi=Math.max(6,Math.ceil(Math.max(...points.map(x=>x[1]))/6)*6),x=f=>32+Math.log(f/20)/Math.log(1100)*(width-44),y=d=>height-31-(d-lo)/(hi-lo)*(height-43);
 const step=Math.max(6,Math.ceil((hi-lo)/30)*6);
 for(let d=lo;d<=hi;d+=step){chart.append(svg('line',{x1:32,x2:width-12,y1:y(d),y2:y(d),stroke:d===0?'#2a3d47':'#1e2c34','stroke-dasharray':d===0?'3 4':'none'}),svg('text',{x:24,y:y(d)+3,'text-anchor':'end'},`${d>0?'+':''}${d}`));}
 for(const f of [20,100,1000,10000,20000])chart.append(svg('text',{x:x(f),y:height-8,'text-anchor':'middle'},f>=1000?`${f/1000}k`:String(f)));
 chart.append(svg('path',{d:points.map(([f,d],i)=>`${i?'L':'M'}${x(f).toFixed(2)},${y(d).toFixed(2)}`).join(' '),fill:'none',stroke:'#5cc8e8','stroke-width':1.8,'stroke-linejoin':'round'}));
 $('curve-mode').textContent=dirty?'DRAFT':NookEQ.decode(p).enabled?'':'BYPASS';
}
function matchedConfig(p,candidate){try{return candidate&&NookEQ.equal(p,NookEQ.program(candidate))?clone(candidate):null;}catch{return null;}}
async function loadCurrent(){
 const p=new Uint8Array(await (await request('/api/program')).arrayBuffer());NookEQ.decode(p);liveProgram=p;
 let metadata=null;try{metadata=await (await request('/api/config')).json();}catch{}
 let saved=null;try{saved=JSON.parse(localStorage.getItem('nook-eq-draft'));}catch{}
 config=matchedConfig(p,metadata)||matchedConfig(p,saved);
 const decoded=NookEQ.decode(p);
 const actualLevel=Math.max(-60,20*Math.log10(decoded.preamp||.001));
 let match=factoryPresets.find(preset=>matchedConfig(p,{...preset.config,enabled:decoded.enabled,preamp_db:actualLevel}));
 if(!config&&match)config={...clone(match.config),enabled:decoded.enabled,preamp_db:actualLevel};
 if(!config&&NookEQ.decode(p).stages===0){const d=NookEQ.decode(p);const candidate={enabled:d.enabled,preamp_db:Math.max(-60,20*Math.log10(d.preamp||.001)),bands:[]};if(NookEQ.equal(NookEQ.program(candidate),p))config=candidate;}
 $('preset').value=match?.id||'';dirty=false;connected=true;$('edit-state').textContent='';$('preset-description').textContent=match?.description||'Current settings · changes apply when you choose Apply.';showError('');render();
}
function status(bytes){if(bytes.byteLength!==36)throw Error('Unexpected driver status.');const d=new DataView(bytes);if(d.getUint32(0)!==0x45513130||d.getUint32(4)!==1)throw Error('Unexpected driver version.');return {requested:d.getUint32(8),applied:d.getUint32(12),rate:d.getUint32(16),bits:d.getUint32(20),channels:d.getUint32(24),output:d.getUint32(28),internal:d.getUint32(32)};}
function showStatus(s){connected=true;$('status-dot').classList.add('live');$('device-status').textContent=s.rate?`${(s.rate/1000).toFixed(1)}k · ${s.bits||'—'} bit · ${s.channels===2?'stereo':s.channels===1?'mono':'ready'}`:'Connected · waiting for audio';$('clip-status').textContent=`${s.output} output clips · ${s.internal} internal`;
 if(!dirty)$('edit-state').textContent=s.requested!==s.applied?'Queued':'';
 if(s.rate&&!ratePinned&&rate!==s.rate){rate=s.rate;updateRate();draw();}updateButtons();}
async function poll(){try{showStatus(status(await (await request('/api/status')).arrayBuffer()));}catch{connected=false;$('status-dot').classList.remove('live');$('device-status').textContent='Offline';$('clip-status').textContent='Driver unavailable';updateButtons();}setTimeout(poll,5000);}
function updateRate(){document.querySelectorAll('[data-rate]').forEach(b=>b.setAttribute('aria-pressed',String(Number(b.dataset.rate)===rate)));}
factoryPresets.forEach(p=>{const option=document.createElement('option');option.value=p.id;option.textContent=p.name;$('preset').append(option);});$('preset').disabled=false;
$('preset').onchange=()=>{const p=factoryPresets.find(x=>x.id===$('preset').value);if(!p)return;config=clone(p.config);render();changed();$('preset').value=p.id;$('preset-description').textContent=p.description;};
$('preamp').oninput=()=>{if(!config)return;config.preamp_db=$('preamp').valueAsNumber;$('preamp-value').textContent=`${config.preamp_db.toFixed(1)} dB`;changed();};
$('enabled').onclick=()=>{if(!config)return;config.enabled=!config.enabled;render();changed();};
$('add').onclick=()=>{if(!config||config.bands.length>=8)return;config.bands.push({type:'peaking',frequency_hz:1000,gain_db:0,q:1});render();changed();};
$('revert').onclick=()=>loadCurrent().catch(e=>showError(e.message));
document.querySelectorAll('[data-rate]').forEach(b=>b.onclick=()=>{rate=Number(b.dataset.rate);ratePinned=true;updateRate();draw();});
$('apply').onclick=async()=>{
 if(applying||!connected)return;
 try{const current=version,snapshot=clone(config),p=NookEQ.program(snapshot),meta=new TextEncoder().encode(JSON.stringify(snapshot)),body=new Uint8Array(p.length+meta.length);body.set(p);body.set(meta,p.length);applying=true;updateButtons();showError('');
  const result=status(await (await request('/api/program',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body})).arrayBuffer());
  const readback=new Uint8Array(await (await request('/api/program')).arrayBuffer());if(!NookEQ.equal(readback,p))throw Error('Settings readback differs. Check the current EQ before retrying.');
  liveProgram=p;if(version===current){dirty=false;try{localStorage.setItem('nook-eq-draft',JSON.stringify(snapshot));}catch{}}showStatus(result);draw();
 }catch(e){showError(e.message);}finally{applying=false;updateButtons();}
};
$('export').onclick=()=>{if(!config)return;const url=URL.createObjectURL(new Blob([JSON.stringify(config,null,2)+'\n'],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='nook-eq.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
window.addEventListener('resize',draw);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
request('/api/mode').then(r=>r.json()).then(mode=>{$('install-mode').textContent=mode.persistent?'Saved on device':'RAM · clears on restart';}).catch(()=>{});
loadCurrent().catch(e=>{config=clone(factoryPresets[0].config);$('preset-description').textContent='Offline editor · choose a preset to begin.';render();showError(e.message);}).finally(poll);
