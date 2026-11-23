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

/* Walk feedback (routing/walkcheck.py, RESEARCH_PROTOCOL.md): after a walk the walker rates it. The panel is short on
   purpose (people who just finished a walk do not fill in forms): stars for the walk, whether it matched the request,
   an optional comment. Quiet, greenery, the other requested dimensions, the detour and the walk-along study code are
   one tap further, under "More detail". The server adds its own predicted scores for the walked route, so
   evaluation.html can compare prediction and experience. Voluntary; sends no location, name or account. Comments are
   public: other walkers read them under the walk options. */
const WALK_TYPE_LABEL={tourist:'Tourist','curious-local':'Curious Local',leisure:'Leisure Walker',custom:'Your own priorities'};
const WALK_RATINGS=[['quiet','How quiet did it feel?'],['green','How green did it feel?']];
// "Did it match?" on the same 1–5 scale the evaluation uses: not really 1, partly 3, yes 5
const WALK_MATCH=[[1,'Not really'],[3,'Partly'],[5,'Yes']];
function walkCheckType(){const a=typeof walkActivity==='function'?walkActivity():null;return a?a.key:'custom';}
/** Dimensions the walker expressed: {name: {weight, direction}} (sliders, pills or an entry). */
function walkCheckPriorities(){
 if(typeof planner==='undefined'||typeof DIMENSIONS==='undefined')return {};
 const out={};for(const d of DIMENSIONS){const n=d.name;if(planner.origins[n]!=='default')out[n]={weight:Math.round(planner.weights[n]??50),direction:planner.directions[n]==='low'?'low':'high'};}
 return out;
}
const WALK_PHOTOS_MAX=3,WALK_PHOTO_MAX_CHARS=200000,WALK_PHOTO_MAX_DIM=1024;
/** A photo file, read, scaled to at most WALK_PHOTO_MAX_DIM on its long edge and re-encoded as a JPEG data URL
    (a canvas re-encode carries no EXIF, so this also removes any embedded location on its own, not as an extra
    step). Quality steps down if the result is still over the server's per-photo limit; gives up after a few tries
    rather than sending something oversized. */
function walkPhotoRead(file){
 return new Promise((resolve,reject)=>{
  const reader=new FileReader();
  reader.onerror=()=>reject(new Error('unreadable'));
  reader.onload=()=>{
   const img=new Image();
   img.onerror=()=>reject(new Error('not an image'));
   img.onload=()=>{
    let w=img.naturalWidth,h=img.naturalHeight;
    if(!w||!h)return reject(new Error('not an image'));
    const longEdge=Math.max(w,h);
    if(longEdge>WALK_PHOTO_MAX_DIM){const scale=WALK_PHOTO_MAX_DIM/longEdge;w=Math.round(w*scale);h=Math.round(h*scale);}
    const canvas=document.createElement('canvas');canvas.width=w;canvas.height=h;
    canvas.getContext('2d').drawImage(img,0,0,w,h);
    let url='';for(const q of [0.72,0.5,0.35]){url=canvas.toDataURL('image/jpeg',q);if(url.length<=WALK_PHOTO_MAX_CHARS)break;}
    if(url.length>WALK_PHOTO_MAX_CHARS)return reject(new Error('too large even after resizing'));
    resolve(url);
   };
   img.src=reader.result;
  };
  reader.readAsDataURL(file);
 });
}
function walkCheckPhotosBox(){
 return `<div class="walk-check-photos" data-k="photos">
  <input type="file" accept="image/*" multiple data-k="photo-input" class="hidden" aria-label="Add photos, up to ${WALK_PHOTOS_MAX}">
  <button type="button" class="walk-check-photo-add" data-k="photo-add">+ Add photos<small>up to ${WALK_PHOTOS_MAX}</small></button>
 </div>
 <small class="walk-check-hint walk-check-photo-note">Your comment and photos are shown to other walkers. Photos are resized and their location data removed.</small>`;
}
function walkCheckRenderPhotos(box,st){
 const row=box.querySelector('[data-k="photos"]'),add=row.querySelector('[data-k="photo-add"]');
 row.querySelectorAll('.walk-check-photo').forEach(x=>x.remove());
 st.photos.forEach((url,i)=>{
  const fig=document.createElement('span');fig.className='walk-check-photo';
  fig.innerHTML=`<img src="${esc(url)}" alt=""><button type="button" data-remove="${i}" aria-label="Remove photo ${i+1}">×</button>`;
  row.insertBefore(fig,add);
 });
 add.classList.toggle('hidden',st.photos.length>=WALK_PHOTOS_MAX);
}
function walkScale(key){return `<span class="walk-check-scale" role="group">${[1,2,3,4,5].map(k=>`<button type="button" data-rate="${esc(key)}" data-v="${k}" aria-pressed="false">${k}</button>`).join('')}</span>`;}
function walkStars(key,label){return `<span class="walk-stars" role="group" aria-label="${esc(label)}">${[1,2,3,4,5].map(k=>`<button type="button" data-rate="${esc(key)}" data-v="${k}" aria-pressed="false" aria-label="${k} of 5">★</button>`).join('')}</span>`;}
function walkCheckBox(r){
 if(!r)return '';
 const detour=Number(r.detour_percentage)||0,type=walkCheckType(),pri=walkCheckPriorities();
 const extra=Object.keys(pri).filter(n=>n!=='Nature'&&n!=='Quiet & Relax'&&pri[n].direction==='high');
 return `<details class="walk-check" data-route="${esc(r.route_id)}" open><summary>Rate this walk (optional)</summary>
  <div class="walk-check-main">${walkStars('overall','Overall, how satisfied are you with this walk?')}</div>
  <div class="walk-check-q walk-check-match"><span>Did it match what you asked for?</span><span class="walk-check-scale">${WALK_MATCH.map(([v,l])=>`<button type="button" data-rate="match" data-v="${v}" aria-pressed="false">${l}</button>`).join('')}</span></div>
  <textarea class="walk-check-comment" data-k="comment" maxlength="500" rows="3" placeholder="Add a comment (optional, public)" aria-label="Comment, optional and shown to other walkers"></textarea>
  ${walkCheckPhotosBox()}
  <button type="button" class="walk-check-send" data-k="send" disabled>Send rating</button>
  <details class="walk-check-more"><summary>More detail (optional)</summary>
   <small class="walk-check-type">Walk type: ${esc(WALK_TYPE_LABEL[type])}${Object.keys(pri).length?' · '+esc(Object.keys(pri).join(', ')):''}</small>
   ${WALK_RATINGS.map(([k,q])=>`<div class="walk-check-q">${esc(q)} ${walkScale(k)}</div>`).join('')}
   ${extra.map(n=>`<div class="walk-check-q">${esc(typeof dimLabel==='function'?dimLabel(n):n)} ${walkScale('dim:'+n)}</div>`).join('')}
   ${detour>=1?`<div class="walk-check-q">Was the extra ${Math.round(detour)}% distance worth it? <span class="walk-check-scale">${['yes','no'].map(k=>`<button type="button" data-worth="${k}" aria-pressed="false">${k==='yes'?'Yes':'No'}</button>`).join('')}</span></div>`:''}
   <small class="walk-check-hint">1 not at all · 5 very.</small>
   <label class="walk-check-code">Study code (walk-along participants only) <input data-k="code" maxlength="6" placeholder="e.g. P07" autocomplete="off"></label>
   <div class="walk-check-q hidden" data-k="compare">Walk-along: of your two walks for this trip, which fitted your request better? <span class="walk-check-scale">${[['this','This one'],['shortest','The other one'],['same','No difference']].map(([k,l])=>`<button type="button" data-compared="${k}" aria-pressed="false">${l}</button>`).join('')}</span></div>
  </details>
  <small class="walker-status" data-k="walk-check-status">No location or name is sent. <a href="./evaluation.html" target="_blank" rel="noopener">All results</a></small></details>`;
}
function walkCheckPayload(r,st,code,comment){
 const dims={};for(const [k,v] of Object.entries(st.rate))if(k.startsWith('dim:'))dims[k.slice(4)]=v;
 return {user_type:walkCheckType(),priorities:walkCheckPriorities(),
  ratings:{overall:st.rate.overall??null,match:st.rate.match??null,quiet:st.rate.quiet??null,green:st.rate.green??null},dimension_ratings:dims,
  comment:comment||null,photos:st.photos,worth_detour:st.worth,study_code:code||null,compared_with_shortest:code?st.compared:null,
  route_id:r.route_id,route_signature:r.route_signature,score_version:r.score_version,network_version:r.network_version,distance_m:r.distance_m,detour_pct:r.detour_percentage,
  route_snapshot:{route_id:r.route_id,network_version:r.network_version,route_signature:r.route_signature,ordered_edge_ids:r.ordered_edge_ids}};
}
function wireWalkCheck(root,r,showFeed){
 const box=root.querySelector('.walk-check');if(!box)return;
 const st={rate:{},worth:(Number(r.detour_percentage)||0)<1?'no-detour':null,compared:null,photos:[]};
 const send=box.querySelector('[data-k="send"]'),status=box.querySelector('[data-k="walk-check-status"]');
 const photoInput=box.querySelector('[data-k="photo-input"]'),photoAdd=box.querySelector('[data-k="photo-add"]'),photoRow=box.querySelector('[data-k="photos"]');
 photoAdd?.addEventListener('click',()=>photoInput.click());
 photoInput?.addEventListener('change',async()=>{
  // disabled for the duration: picking again before this batch finishes resizing could otherwise push past
  // WALK_PHOTOS_MAX (each change event only caps against the count it sees when it starts)
  photoAdd.disabled=true;
  const files=[...photoInput.files].slice(0,WALK_PHOTOS_MAX-st.photos.length);photoInput.value='';
  for(const f of files){
   try{st.photos.push(await walkPhotoRead(f));}
   catch(e){if(typeof toast==='function')toast('Could not use that photo: '+e.message);}
  }
  st.photos.length=Math.min(st.photos.length,WALK_PHOTOS_MAX);
  photoAdd.disabled=false;
  walkCheckRenderPhotos(box,st);
 });
 photoRow?.addEventListener('click',e=>{
  const rm=e.target.closest('[data-remove]');if(!rm)return;
  st.photos.splice(Number(rm.dataset.remove),1);walkCheckRenderPhotos(box,st);
 });
 box.querySelectorAll('[data-rate]').forEach(b=>b.addEventListener('click',()=>{
  st.rate[b.dataset.rate]=Number(b.dataset.v);
  box.querySelectorAll('[data-rate]').forEach(x=>{if(x.dataset.rate===b.dataset.rate){x.setAttribute('aria-pressed',String(x===b));
   if(x.closest('.walk-stars'))x.classList.toggle('on',Number(x.dataset.v)<=Number(b.dataset.v));}}); // stars fill up to the one tapped
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
   status.textContent=j.check?.predicted?'Thanks, saved.':'Thanks, saved (this route could not be verified, so it is left out of the score comparison).';
   box.querySelectorAll('button,input,textarea').forEach(x=>x.disabled=true);
   if(typeof loadWalkerEvaluation==='function')loadWalkerEvaluation(true).then(d=>{if(d&&showFeed)showFeed(d);});   // the walker's own comment joins the feed below
  }catch(e){status.textContent='Not saved: '+e.message;send.disabled=st.rate.overall==null;}
 });
}
/** The rating form in a dialog, right away: on arrival in navigation, or from "I walked this – rate it now". */
function openWalkRating(r){
 r=r||(typeof state!=='undefined'?state.routes.find(x=>x.id===state.activeRoute)?.raw:null);
 const overlay=document.getElementById('modalOverlay');
 if(!r||!overlay){if(typeof toast==='function')toast('Choose a route first.');return;}
 const over=document.getElementById('modalOverline');if(over)over.textContent='';
 document.getElementById('modalTitle').textContent='How was your walk?';
 const c=document.getElementById('modalContent');
 c.innerHTML=walkCheckBox(r)+walkerSaysFeed(walkerSays.evaluation,walkCheckType());
 wireWalkCheck(c,r,wireWalkerFeed(c));
 overlay.classList.remove('hidden');
 // the dialog itself takes focus, not the first star: a screen reader still announces the dialog and Tab reaches the
 // stars, without a focus ring sitting on a control the walker has not chosen yet
 const dialog=overlay.querySelector('[role="dialog"]');
 if(dialog){dialog.tabIndex=-1;dialog.focus();}
}
function promptWalkCheck(){openWalkRating();}

/* Before walking: what walkers said, about walks of this type and about the streets of this route. */
const walkerSays={evaluation:null,loading:null};
function loadWalkerEvaluation(force){
 if(force)walkerSays.evaluation=null;
 if(walkerSays.evaluation)return Promise.resolve(walkerSays.evaluation);
 if(walkerSays.loading)return walkerSays.loading;
 walkerSays.loading=streetwiseFetch('/api/evaluation',{signal:AbortSignal.timeout(30000)}).then(r=>r.json()).then(d=>(walkerSays.evaluation=d)).catch(()=>null).finally(()=>{walkerSays.loading=null;});
 return walkerSays.loading;
}
function routeSegmentIds(r){const ids=new Set();for(const e of r.edges||[])for(const m of e.matched_segments||[])if(m.segment_id)ids.add(m.segment_id);return [...ids].slice(0,600);}
const walkStarText=v=>v?'★'.repeat(v)+'☆'.repeat(5-v):'';
/** The average rating, in one line: "★ 4.2 · 12 rated walks · Tourist walks 4.5 (5)". */
function walkerSaysRatings(d,type){
 if(!d)return '<small class="walker-status">Loading what walkers said…</small>';
 if(!d.n)return `<p class="walker-says-empty">No walker has rated a walk yet${d.enabled===false?'':'. Be the first: rate this one when you finish'}.</p>`;
 const t=d.by_user_type?.[type],r=d.ratings,f=(v)=>v==null?'—':Number(v).toFixed(1);
 return `<div class="walker-says-score"><strong>★ ${f(r.overall.mean)}</strong><span>${d.n} rated walk${d.n===1?'':'s'} · matched the request ${f(r.match.mean)} / 5</span></div>
  ${t?`<small class="walker-says-type">${esc(WALK_TYPE_LABEL[type])} walks (${t.n}): ★ ${f(t.mean_overall)}</small>`:''}`;
}
/** What walkers wrote: walks of the same type first, then the newest. Three shown, the rest one tap away. */
function walkerSaysComments(d,type,all=false){
 const list=(d?.recent_comments||[]).slice().sort((a,b)=>(b.user_type===type)-(a.user_type===type)||String(b.date).localeCompare(String(a.date)));
 if(!list.length)return d?.n?'<p class="walker-says-empty">No comments yet.</p>':'';
 const day=s=>{const t=new Date(s+'T12:00:00Z');return isNaN(t)?s:t.toLocaleDateString(undefined,{month:'short',day:'numeric'});};
 const shown=all?list:list.slice(0,3);
 return `<ul class="walker-comments">${shown.map(c=>`<li><small>${c.overall?`<span class="wc-stars" aria-label="${c.overall} of 5">${walkStarText(c.overall)}</span> · `:''}${esc(WALK_TYPE_LABEL[c.user_type]||'')} · ${esc(day(c.date))}</small>${c.comment?`<p>${esc(c.comment)}</p>`:''}${(c.photos||[]).map(p=>`<img class="wc-photo" src="${esc(p)}" alt="" loading="lazy">`).join('')}${walkerCommentActions(c)}</li>`).join('')}</ul>
  ${!all&&list.length>3?`<button type="button" class="walker-comments-more" data-k="more-comments">${list.length-3} more comment${list.length-3===1?'':'s'}</button>`:''}`;
}
/* Likes and replies on one "what other walkers said" comment (server: routing/walkcheck.py ReactionBook). WALK_LIKED
   is this tab's own session only (a like is also deduplicated per client on the server for a day); replies and the
   like count a walker adds are folded back into walkerSays.evaluation so they survive a re-render (e.g. "more comments"). */
const WALK_LIKED=new Set();
function walkerCommentById(id){return (walkerSays.evaluation?.recent_comments||[]).find(c=>c.id===id);}
function walkerCommentActions(c){
 if(!c.id)return '';   // defensive: an older cached /api/evaluation response without comment ids
 const liked=WALK_LIKED.has(c.id),replies=c.replies||[];
 return `<div class="wc-actions">
  <button type="button" class="wc-like${liked?' on':''}" data-like="${esc(c.id)}" aria-pressed="${liked}" aria-label="Like this comment"><span class="wc-heart">♥</span> <span data-like-count>${c.likes||0}</span></button>
  <button type="button" class="wc-reply-toggle" data-reply-toggle="${esc(c.id)}" aria-expanded="false">Reply${replies.length?' · '+replies.length:''}</button>
 </div>
 <div class="wc-replies hidden" data-replies="${esc(c.id)}">
  ${replies.map(r=>`<p class="wc-reply">${esc(r.text)}</p>`).join('')}
  <div class="wc-reply-row"><input type="text" class="wc-reply-input" data-reply-input maxlength="300" placeholder="Write a reply" aria-label="Write a reply, shown to other walkers"><button type="button" class="wc-reply-send" data-reply-send="${esc(c.id)}">Reply</button></div>
 </div>`;
}
async function wcSendLike(btn){
 const id=btn.dataset.like;
 if(btn.disabled||WALK_LIKED.has(id))return;
 btn.disabled=true;
 try{
  const res=await streetwiseFetch('/api/walk-checks/like',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:id}),signal:AbortSignal.timeout(15000)});
  const j=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(j.error||`HTTP ${res.status}`);
  WALK_LIKED.add(id);
  const c=walkerCommentById(id);if(c)c.likes=j.likes??(c.likes||0)+1;
  btn.classList.add('on');btn.setAttribute('aria-pressed','true');
  const count=btn.querySelector('[data-like-count]');if(count)count.textContent=String(c?c.likes:j.likes);
 }catch(e){
  if(typeof toast==='function')toast('Could not like that: '+e.message);
  btn.disabled=false;
 }
}
async function wcSendReply(btn){
 const id=btn.dataset.replySend,box=btn.closest('[data-replies]'),input=box?.querySelector('[data-reply-input]');
 const text=(input?.value||'').trim();
 if(!text||btn.disabled)return;
 btn.disabled=true;
 try{
  const res=await streetwiseFetch('/api/walk-checks/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:id,text}),signal:AbortSignal.timeout(15000)});
  const j=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(j.error||`HTTP ${res.status}`);
  const c=walkerCommentById(id);if(c)c.replies=[...(c.replies||[]),j.reply];
  const p=document.createElement('p');p.className='wc-reply';p.textContent=j.reply.text;
  box.querySelector('.wc-reply-row').insertAdjacentElement('beforebegin',p);
  input.value='';
  const toggle=box.closest('li')?.querySelector('[data-reply-toggle]');
  if(toggle)toggle.textContent='Reply'+(c&&c.replies.length?` · ${c.replies.length}`:'');
 }catch(e){
  if(typeof toast==='function')toast('Could not send that reply: '+e.message);
 }finally{btn.disabled=false;}
}
function walkerSaysStreets(segs,r){
 const names=new Map();for(const e of r.edges||[])for(const m of e.matched_segments||[])if(m.segment_id&&!names.has(m.segment_id))names.set(m.segment_id,m.street_name||m.segment_id);
 const rows=Object.entries(segs||{}).flatMap(([id,dims])=>Object.entries(dims).map(([k,x])=>({id,k,x}))).sort((a,b)=>b.x.n-a.x.n).slice(0,5);
 if(!rows.length)return '';
 return `<div class="walker-says-streets"><small>Streets on this route walkers reported:</small>${rows.map(({id,k,x})=>`<div class="data-pair"><span>${esc(names.get(id)||id)} · ${esc(walkerLabelOf(k))}</span><span>${x.worse} worse · ${x.better} better${x.status==='applied'?` · routing ${x.delta>0?'+':''}${x.delta}`:''}</span></div>`).join('')}</div>`;
}
/** "★ 4.5 · 6 rated walks", the one line that heads the feed. Empty until a walk has been rated. */
function walkerSaysMean(d){
 if(!d?.n)return '';
 const m=d.ratings?.overall?.mean;
 return `★ ${m==null?'—':Number(m).toFixed(1)} · ${d.n} rated walk${d.n===1?'':'s'}`;
}
/** What other walkers said, under the walker's own rating in the dialog: the heading, the average and the comments
    with their likes and replies. The results panel shows the fuller walkerSaysBox (the streets walkers reported, the
    button to rate this walk); neither belongs next to the form the walker is filling in right now. */
function walkerSaysFeed(d,type){
 const comments=d?walkerSaysComments(d,type):'';
 return `<section class="walker-says-feed${comments?'':' hidden'}" aria-label="What other walkers said">
  <div class="walker-says-head"><strong>What other walkers said</strong><span class="walker-says-mean" data-k="walker-says-mean">${walkerSaysMean(d)}</span></div>
  <div data-k="walker-comments">${comments}</div></section>`;
}
function wireWalkerFeed(root){
 const box=root.querySelector('.walker-says-feed');if(!box)return;
 const comments=box.querySelector('[data-k="walker-comments"]');
 wireWalkerComments(comments);
 const show=d=>{
  const mean=box.querySelector('[data-k="walker-says-mean"]');if(mean)mean.textContent=walkerSaysMean(d);
  comments.innerHTML=d?walkerSaysComments(d,walkCheckType()):'';
  box.classList.toggle('hidden',!comments.innerHTML.trim());
  if(typeof i18nApply==='function')i18nApply(box);
 };
 loadWalkerEvaluation().then(d=>{if(d)show(d);});
 return show;   // wireWalkCheck calls this again once the walker's own rating is saved
}
/** The rate area under the walk options: the walkers' average, what they wrote, the streets they reported on this
    route, and the button to rate this walk. */
function walkerSaysBox(r){
 if(!r)return '';
 const d=walkerSays.evaluation,type=walkCheckType();
 return `<section class="walker-says" aria-label="What walkers said"><div class="walker-says-head"><strong>What walkers said</strong></div>
  <div data-k="walker-says-ratings">${walkerSaysRatings(d,type)}</div><div data-k="walker-comments">${d?walkerSaysComments(d,type):''}</div><div data-k="walker-says-streets"></div>
  <button type="button" class="walker-rate-now" data-k="rate-now">I walked this – rate it now</button></section>`;
}
/** Clicks and keys on a list of comments: more, like, open a reply thread, send a reply. The list is replaced wholesale
    on a re-render, so everything is delegated from the container, which stays. */
function wireWalkerComments(comments){
 if(!comments)return;
 comments.addEventListener('click',e=>{
  if(e.target.closest('[data-k="more-comments"]')){comments.innerHTML=walkerSaysComments(walkerSays.evaluation,walkCheckType(),true);return;}
  const like=e.target.closest('[data-like]');if(like){wcSendLike(like);return;}
  const toggle=e.target.closest('[data-reply-toggle]');
  if(toggle){
   const open=!toggle.closest('li').querySelector('.wc-replies').classList.toggle('hidden');
   toggle.setAttribute('aria-expanded',String(open));
   return;
  }
  const send=e.target.closest('[data-reply-send]');if(send){wcSendReply(send);return;}
 });
 comments.addEventListener('keydown',e=>{
  if(e.key==='Enter'&&e.target.matches('[data-reply-input]')){e.preventDefault();wcSendReply(e.target.closest('[data-replies]').querySelector('[data-reply-send]'));}
 });
}
function wireWalkerSays(root,r){
 const box=root.querySelector('.walker-says');if(!box)return;
 box.querySelector('[data-k="rate-now"]').addEventListener('click',()=>openWalkRating(r));
 const comments=box.querySelector('[data-k="walker-comments"]');
 wireWalkerComments(comments);
 loadWalkerEvaluation().then(d=>{const el=box.querySelector('[data-k="walker-says-ratings"]');if(el&&d){el.innerHTML=walkerSaysRatings(d,walkCheckType());if(comments)comments.innerHTML=walkerSaysComments(d,walkCheckType());}});
 const ids=routeSegmentIds(r);
 if(ids.length)streetwiseFetch('/api/feedback/lookup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({segment_ids:ids}),signal:AbortSignal.timeout(30000)})
  .then(x=>x.json()).then(j=>{const el=box.querySelector('[data-k="walker-says-streets"]');if(el&&j.segments)el.innerHTML=walkerSaysStreets(j.segments,r);}).catch(()=>{});
}

/* "Rate walk" in the walk action bar, next to Start Navigation: opens the same post-walk rating dialog. */
if(typeof document!=='undefined')document.getElementById('rateWalk')?.addEventListener('click',()=>openWalkRating());
