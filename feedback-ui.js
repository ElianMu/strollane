/** STROLLANE walker feedback (the professor's Human-in-the-Loop item): a walker reports that a street felt worse or
    better than its score on one dimension. The server (routing/feedback.py) keeps the report apart from the data score,
    and changes routing only after several agreeing reports on different days. Nothing personal is sent: a segment ID,
    a dimension, a direction and the score that was shown. */
const WALKER_WORDS={
 architecture:['Less architectural interest than rated','More architectural interest than rated'],
 nature:['Less green than rated','Greener than rated'],
 culture:['Less culture than rated','More culture than rated'],
 quiet:['Louder than rated','Quieter than rated'],
 spatial_comfort:['More cramped than rated','Roomier than rated'],
 urban_vibrancy:['Less lively than rated','Livelier than rated'],
 food_retail:['Fewer shops and food than rated','More shops and food than rated'],
 scenic_visual:['Less scenic than rated','More scenic than rated'],
 walkability:['Harder to walk than rated','Easier to walk than rated'],
 access_safety:['Felt less safe than rated','Felt safer than rated'],
 environment:['Worse air or heat than rated','Better air or shade than rated'],
 transit_connectivity:['Transit farther than rated','Transit closer than rated']};
const WALKER_KEYS=Object.keys(WALKER_WORDS);
const WALKER_LABELS=['Architecture','Nature','Culture','Quiet & Relax','Spatial Comfort','Urban Vibrancy','Food & Retail','Scenic & Visual','Walkability','Access & Safety','Environment','Transit Connectivity'];
const walkerKeyOf=label=>WALKER_KEYS[WALKER_LABELS.indexOf(label)]||label;
const walkerLabelOf=key=>WALKER_LABELS[WALKER_KEYS.indexOf(key)]||key;

async function sendWalkerReport(body){
 const res=await streetwiseFetch('/api/feedback',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(30000)});
 const j=await res.json().catch(()=>({}));
 if(!res.ok)throw new Error(j.error||`HTTP ${res.status}`);
 return j;
}
function walkerStatusText(s){
 if(!s)return 'No walker reports yet.';
 const tally=`${s.n} report${s.n===1?'':'s'} (${s.worse} worse, ${s.better} better) on ${s.days} day${s.days===1?'':'s'}`;
 if(s.status==='applied')return `${tally}: routing now adjusts this score by ${s.delta>0?'+':''}${s.delta}${s.time_sensitive?' at the reported time of day':''}. The data score is unchanged.`;
 if(s.status==='mixed')return `${tally}: reports disagree, so nothing changes.`;
 return `${tally}: not enough yet to change anything.`;
}
/** Explore inspector block for one segment and dimension. */
function walkerFeedbackBox(segmentId,dimKey,score){
 if(!dimKey||!WALKER_WORDS[dimKey])return '';
 const [worse,better]=WALKER_WORDS[dimKey];
 return `<section class="walker-feedback" data-seg="${esc(segmentId)}" data-dim="${esc(dimKey)}" data-rated="${score==null?'':score}" aria-label="Walker feedback">
  <h4>Walked here? Did it match?</h4>
  <div class="walker-buttons"><button type="button" data-dir="worse">${esc(worse)}</button><button type="button" data-dir="better">${esc(better)}</button></div>
  <small class="walker-status" data-k="walker-status">Checking walker reports…</small>
  <small class="walker-note">Sends only this street's ID, the dimension and your answer. One report changes nothing; several on different days adjust routing a little, never the data score.</small></section>`;
}
function wireWalkerFeedback(root){
 root.querySelectorAll('.walker-feedback').forEach(box=>{
  const seg=box.dataset.seg,dim=box.dataset.dim,status=box.querySelector('[data-k="walker-status"]');
  streetwiseFetch('/api/feedback/segments/'+encodeURIComponent(seg),{signal:AbortSignal.timeout(30000)}).then(r=>r.json()).then(j=>{
   if(!j.enabled){status.textContent='Walker feedback is not switched on for this server yet.';box.querySelectorAll('button').forEach(b=>b.disabled=true);return;}
   status.textContent=walkerStatusText(j.dimensions?.[dim]);
  }).catch(()=>{status.textContent='Walker reports could not be loaded.';});
  box.querySelectorAll('button[data-dir]').forEach(b=>b.addEventListener('click',async()=>{
   box.querySelectorAll('button').forEach(x=>x.disabled=true);status.textContent='Sending…';
   try{
    const j=await sendWalkerReport({segment_id:seg,dimension:dim,direction:b.dataset.dir,rated:box.dataset.rated===''?null:Number(box.dataset.rated),
     score_version:typeof exploreMap!=='undefined'?exploreMap.manifest?.calculation_version:undefined});
    status.textContent='Thanks, saved. '+walkerStatusText(j.segment);
   }catch(e){status.textContent='Not saved: '+e.message;box.querySelectorAll('button').forEach(x=>x.disabled=false);}
  }));
 });
}
/** Why-this-route block: what walker reports changed on this route, and a form to report a street on it. */
function walkerFeedbackWhy(r){
 const w=r.walker_feedback;if(!w)return '';
 const applied=w.applied||[];
 const changed=applied.length?`<h4>Changed by walker reports</h4>${applied.slice(0,6).map(a=>`<div class="data-pair"><span>${esc(a.street_name||a.segment_id)} · ${esc(walkerLabelOf(a.dimension))}</span><span>${a.delta>0?'+':''}${a.delta} (${a.reports} reports, ${a.days} days)</span></div>`).join('')}<small>Route scores with these changes; from the data alone: ${Object.entries(w.dimension_scores_from_data||{}).filter(([d,v])=>v!=null&&v!==r.dimension_scores[d]).map(([d,v])=>`${esc(d)} ${v}`).join(', ')||'the same'}.</small>`:'';
 const seen=new Map();
 for(const e of r.edges||[])for(const m of e.matched_segments||[]){if(!m.segment_id)continue;const x=seen.get(m.segment_id)||{name:m.street_name||m.segment_id,m:0};x.m+=e.traversed_length_m||0;seen.set(m.segment_id,x);}
 const streets=[...seen.entries()].sort((a,b)=>b[1].m-a[1].m).slice(0,40);
 if(!streets.length)return changed;
 return `${changed}<details class="walker-route" data-route="${esc(r.route_id)}"><summary>Did a street feel different from its score?</summary>
  <label>Street <select data-k="seg">${streets.map(([id,x])=>`<option value="${esc(id)}">${esc(x.name)} (${Math.round(x.m)} m)</option>`).join('')}</select></label>
  <label>Dimension <select data-k="dim">${WALKER_KEYS.map(k=>`<option value="${k}">${esc(walkerLabelOf(k))}</option>`).join('')}</select></label>
  <div class="walker-buttons"><button type="button" data-dir="worse">Worse than rated</button><button type="button" data-dir="better">Better than rated</button></div>
  <small class="walker-status" data-k="walker-status">${esc(w.rule||'')}</small></details>`;
}
function wireWalkerRoute(root,r){
 const box=root.querySelector('.walker-route');if(!box)return;
 const status=box.querySelector('[data-k="walker-status"]');
 box.querySelectorAll('button[data-dir]').forEach(b=>b.addEventListener('click',async()=>{
  const seg=box.querySelector('[data-k="seg"]').value,dim=box.querySelector('[data-k="dim"]').value;
  status.textContent='Sending…';
  try{
   const j=await sendWalkerReport({segment_id:seg,dimension:dim,direction:b.dataset.dir,rated:null,score_version:r.score_version});
   status.textContent='Thanks, saved. '+walkerStatusText(j.segment);
  }catch(e){status.textContent='Not saved: '+e.message;}
 }));
}

/* Walk feedback (routing/walkcheck.py, RESEARCH_PROTOCOL.md): after a walk the walker rates it 1–5 (overall, match
   with the request, quiet, greenery, optionally the dimensions they asked for) and may leave a comment. The server
   adds its own predicted scores for the walked route, so evaluation.html can compare prediction and experience.
   Voluntary; sends no location, name or account. Comments are public in the project's data branch. */
const WALK_TYPE_LABEL={tourist:'Tourist','curious-local':'Curious Local',leisure:'Leisure Walker',custom:'Your own priorities'};
const WALK_RATINGS=[['overall','Overall, how satisfied are you with this walk?'],['match','How well did it match what you asked for?'],['quiet','How quiet did it feel?'],['green','How green did it feel?']];
function walkCheckType(){const a=typeof walkActivity==='function'?walkActivity():null;return a?a.key:'custom';}
/** Dimensions the walker expressed: {name: {weight, direction}} (sliders, pills or an entry). */
function walkCheckPriorities(){
 if(typeof planner==='undefined'||typeof DIMENSIONS==='undefined')return {};
 const out={};for(const d of DIMENSIONS){const n=d.name;if(planner.origins[n]!=='default')out[n]={weight:Math.round(planner.weights[n]??50),direction:planner.directions[n]==='low'?'low':'high'};}
 return out;
}
function walkScale(key){return `<span class="walk-check-scale" role="group">${[1,2,3,4,5].map(k=>`<button type="button" data-rate="${esc(key)}" data-v="${k}" aria-pressed="false">${k}</button>`).join('')}</span>`;}
function walkCheckBox(r){
 if(!r)return '';
 const detour=Number(r.detour_percentage)||0,type=walkCheckType(),pri=walkCheckPriorities();
 const extra=Object.keys(pri).filter(n=>n!=='Nature'&&n!=='Quiet & Relax'&&pri[n].direction==='high');
 return `<details class="walk-check" data-route="${esc(r.route_id)}"><summary>After your walk: rate it (optional)</summary>
  <small class="walk-check-type">Walk type: ${esc(WALK_TYPE_LABEL[type])}${Object.keys(pri).length?' · '+esc(Object.keys(pri).join(', ')):''}</small>
  ${WALK_RATINGS.map(([k,q])=>`<div class="walk-check-q">${esc(q)}${k==='overall'?' <b>*</b>':''} ${walkScale(k)}</div>`).join('')}
  <small class="walk-check-hint">1 not at all · 5 very. Only the first is required.</small>
  ${extra.length?`<div class="walk-check-dims"><small>The other dimensions you asked for:</small>${extra.map(n=>`<div class="walk-check-q">${esc(typeof dimLabel==='function'?dimLabel(n):n)} ${walkScale('dim:'+n)}</div>`).join('')}</div>`:''}
  ${detour>=1?`<div class="walk-check-q">Was the extra ${Math.round(detour)}% distance worth it? <span class="walk-check-scale">${['yes','no'].map(k=>`<button type="button" data-worth="${k}" aria-pressed="false">${k==='yes'?'Yes':'No'}</button>`).join('')}</span></div>`:''}
  <label class="walk-check-code">Anything else? (optional; public, so no names, contacts or addresses) <textarea data-k="comment" maxlength="500" rows="3"></textarea></label>
  <label class="walk-check-code">Study code (walk-along participants only) <input data-k="code" maxlength="6" placeholder="e.g. P07" autocomplete="off"></label>
  <div class="walk-check-q hidden" data-k="compare">Walk-along: of your two walks for this trip, which fitted your request better? <span class="walk-check-scale">${[['this','This one'],['shortest','The other one'],['same','No difference']].map(([k,l])=>`<button type="button" data-compared="${k}" aria-pressed="false">${l}</button>`).join('')}</span></div>
  <button type="button" class="walk-check-send" data-k="send" disabled>Send</button>
  <small class="walker-status" data-k="walk-check-status">Sends your ratings, the walk type, your priorities and this route's ID. The server adds its own predicted scores for the route. No location or name. <a href="./evaluation.html" target="_blank" rel="noopener">See all results</a></small></details>`;
}
function walkCheckPayload(r,st,code,comment){
 const dims={};for(const [k,v] of Object.entries(st.rate))if(k.startsWith('dim:'))dims[k.slice(4)]=v;
 return {user_type:walkCheckType(),priorities:walkCheckPriorities(),
  ratings:{overall:st.rate.overall??null,match:st.rate.match??null,quiet:st.rate.quiet??null,green:st.rate.green??null},dimension_ratings:dims,
  comment:comment||null,worth_detour:st.worth,study_code:code||null,compared_with_shortest:code?st.compared:null,
  route_id:r.route_id,route_signature:r.route_signature,score_version:r.score_version,network_version:r.network_version,distance_m:r.distance_m,detour_pct:r.detour_percentage,
  route_snapshot:{route_id:r.route_id,network_version:r.network_version,route_signature:r.route_signature,ordered_edge_ids:r.ordered_edge_ids}};
}
function wireWalkCheck(root,r){
 const box=root.querySelector('.walk-check');if(!box)return;
 const st={rate:{},worth:(Number(r.detour_percentage)||0)<1?'no-detour':null,compared:null};
 const send=box.querySelector('[data-k="send"]'),status=box.querySelector('[data-k="walk-check-status"]');
 box.querySelectorAll('[data-rate]').forEach(b=>b.addEventListener('click',()=>{
  st.rate[b.dataset.rate]=Number(b.dataset.v);
  box.querySelectorAll('[data-rate]').forEach(x=>{if(x.dataset.rate===b.dataset.rate)x.setAttribute('aria-pressed',String(x===b));});
  send.disabled=st.rate.overall==null;
 }));
 for(const attr of ['worth','compared'])box.querySelectorAll(`[data-${attr}]`).forEach(b=>b.addEventListener('click',()=>{
  st[attr]=b.dataset[attr];box.querySelectorAll(`[data-${attr}]`).forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
 }));
 const codeIn=box.querySelector('[data-k="code"]'),compare=box.querySelector('[data-k="compare"]');
 if(codeIn&&compare&&codeIn.addEventListener)codeIn.addEventListener('input',()=>compare.classList.toggle('hidden',!codeIn.value.trim()));
 send.addEventListener('click',async()=>{
  send.disabled=true;status.textContent='Sending…';
  try{
   const res=await streetwiseFetch('/api/walk-checks',{method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.timeout(30000),
    body:JSON.stringify(walkCheckPayload(r,st,(codeIn?.value||'').trim(),(box.querySelector('[data-k="comment"]')?.value||'').trim()))});
   const j=await res.json().catch(()=>({}));
   if(!res.ok)throw new Error(j.code==='feedback_disabled'?'feedback is not switched on for this server yet.':(j.error||`HTTP ${res.status}`));
   status.textContent=j.check?.predicted?'Thanks, saved, with this route\'s predicted scores for comparison.':'Thanks, saved (the route could not be verified, so it is left out of the prediction comparison).';
   box.querySelectorAll('button,input,textarea').forEach(x=>x.disabled=true);
  }catch(e){status.textContent='Not saved: '+e.message;send.disabled=st.rate.overall==null;}
 });
}
/** After arriving: point the walker to the form (the route's Why panel holds it). */
function promptWalkCheck(){
 if(typeof toast==='function')toast('You have arrived. How was the walk? Rate it under “Why this route”.');
 const box=document.querySelector('#whyRoute .walk-check');if(box)box.open=true;
}
