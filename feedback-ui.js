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
