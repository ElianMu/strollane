// Walker feedback UI (feedback-ui.js): what a report sends, and how the Why panel shows applied changes.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.join(__dirname,'..');
const sent=[];
const ctx={esc:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),AbortSignal:{timeout:()=>undefined},
 streetwiseFetch:async(url,opt)=>{sent.push({url,body:opt&&opt.body?JSON.parse(opt.body):null});return {ok:true,json:async()=>({saved:true,segment:{n:1,worse:1,better:0,days:1,status:'pending',delta:0}})};}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'feedback-ui.js'),'utf8'),ctx);
(async()=>{
 const run=s=>vm.runInContext(s,ctx);
 await run("sendWalkerReport({segment_id:'QN-1',dimension:'quiet',direction:'worse',rated:70})");
 assert.deepEqual(Object.keys(sent[0].body).sort(),['dimension','direction','rated','segment_id']);
 assert.equal(sent[0].url,'/api/feedback');
 assert(run("walkerFeedbackBox('QN-1','quiet',70)").includes('Louder than rated'));
 assert.equal(run("walkerFeedbackBox('QN-1',null,70)"),'');
 const route={route_id:'rt-1',score_version:'v',dimension_scores:{'Quiet & Relax':60},edges:[{traversed_length_m:120,matched_segments:[{segment_id:'QN-1',street_name:'31 Ave'}]}],
  walker_feedback:{applied:[{segment_id:'QN-1',street_name:'31 Ave',dimension:'quiet',delta:-7.5,reports:3,days:3}],dimension_scores_from_data:{'Quiet & Relax':64},rule:'r'}};
 ctx.route=route;const html=run('walkerFeedbackWhy(route)');
 assert(html.includes('Changed by walker reports')&&html.includes('31 Ave · Quiet &amp; Relax')&&html.includes('-7.5 (3 reports, 3 days)')&&html.includes('Quiet &amp; Relax 64'));
 assert(html.includes('<option value="QN-1">31 Ave (120 m)</option>'));
 ctx.route={...route,walker_feedback:{applied:[],rule:'r'}};assert(!run('walkerFeedbackWhy(route)').includes('Changed by walker reports'));
 assert(run("walkerStatusText({n:4,worse:3,better:1,days:3,status:'applied',delta:-6.2,time_sensitive:true})").includes('adjusts this score by -6.2 at the reported time of day'));
 // After-walk feedback: ratings, comment, walk type, priorities and the route's identity (the server adds the prediction).
 ctx.walkActivity=()=>({key:'leisure'});ctx.DIMENSIONS=[{name:'Nature'},{name:'Quiet & Relax'},{name:'Culture'},{name:'Architecture'}];
 ctx.planner={origins:{Nature:'manual','Quiet & Relax':'manual',Culture:'default',Architecture:'manual'},directions:{Architecture:'high'},weights:{Nature:80,'Quiet & Relax':80,Culture:50,Architecture:70}};
 ctx.r2={route_id:'rt-2',route_signature:'sig',score_version:'s',network_version:'n',distance_m:2400,detour_percentage:6.3,ordered_edge_ids:['1','2']};
 const box=run('walkCheckBox(r2)');
 assert(box.includes('Walk type: Leisure Walker · Nature, Quiet &amp; Relax, Architecture'));
 assert(box.includes('Overall, how satisfied')&&box.includes('How quiet did it feel?')&&box.includes('How green did it feel?')&&box.includes('extra 6% distance worth it'));
 assert(box.includes('data-rate="dim:Architecture"')&&!box.includes('data-rate="dim:Nature"'),'other requested dimensions can be rated; Nature and Quiet have their own questions');
 assert(box.includes('./evaluation.html'));
 ctx.r2.detour_percentage=0;assert(!run('walkCheckBox(r2)').includes('worth it'),'no detour, no detour question');
 const body=run("walkCheckPayload(r2,{rate:{overall:4,quiet:5,'dim:Architecture':3},worth:'no-detour',compared:'this',photos:['data:image/jpeg;base64,AA==']},'P07','Nice')");
 assert.deepEqual(Object.keys(body).sort(),['comment','compared_with_shortest','detour_pct','dimension_ratings','distance_m','network_version','photos','priorities','ratings','route_id','route_signature','route_snapshot','score_version','study_code','user_type','worth_detour']);
 assert.deepEqual(body.photos,['data:image/jpeg;base64,AA==']);
 assert.equal(JSON.stringify(body.ratings),'{"overall":4,"match":null,"quiet":5,"green":null}');
 assert.equal(JSON.stringify(body.dimension_ratings),'{"Architecture":3}');
 assert.equal(JSON.stringify(body.priorities),'{"Nature":{"weight":80,"direction":"high"},"Quiet & Relax":{"weight":80,"direction":"high"},"Architecture":{"weight":70,"direction":"high"}}');
 assert.equal(body.route_snapshot.ordered_edge_ids.length,2);assert(!('predicted' in body),'the client never sends a prediction');
 assert.equal(run("walkCheckPayload(r2,{rate:{overall:2},worth:null,compared:'this'},'','')").compared_with_shortest,null,'comparison only with a study code');
 // Before walking: what walkers said (ratings of walks of this type, reported streets on this route).
 assert(run('walkerSaysRatings({n:0,enabled:true},"leisure")').includes('No walker has rated a walk yet. Be the first'));
 const said=run('walkerSaysRatings({n:5,ratings:{overall:{mean:4.2},match:{mean:3.8},quiet:{n:3,mean:4},green:{n:0,mean:null}},by_user_type:{leisure:{n:2,mean_overall:4.5,mean_match:4}}},"leisure")');
 assert(said.includes('★ 4.2')&&said.includes('5 rated walks')&&said.includes('matched the request 3.8 / 5')&&said.includes('Leisure Walker walks (2): ★ 4.5'));
 // What walkers wrote: the same walk type first, then the newest; three shown, the rest behind a button
 ctx.evalD={n:6,recent_comments:[{date:'2026-11-20',user_type:'tourist',overall:3,comment:'Busy but fine'},{date:'2026-11-19',user_type:'leisure',overall:5,comment:'So <b>quiet</b>'},
  {date:'2026-11-18',user_type:'custom',overall:null,comment:'Ok'},{date:'2026-11-10',user_type:'leisure',overall:4,comment:'Nice trees'},{date:'2026-11-01',user_type:'tourist',overall:2,comment:'Too long'}]};
 const wrote=run('walkerSaysComments(evalD,"leisure")');
 assert(wrote.indexOf('So &lt;b&gt;quiet&lt;/b&gt;')<wrote.indexOf('Nice trees')&&wrote.indexOf('Nice trees')<wrote.indexOf('Busy but fine'),'same walk type first, newest first, text escaped');
 assert(!wrote.includes('Too long')&&wrote.includes('2 more comments')&&wrote.includes('★★★★★'));
 assert(run('walkerSaysComments(evalD,"leisure",true)').includes('Too long'),'all of them on request');
 assert(run('walkerSaysComments({n:2,recent_comments:[]},"leisure")').includes('No comments yet'));
 // One comment in full: the walker and day read above what they wrote, the like and reply chips below it.
 {const one=run('walkerSaysComments({n:1,recent_comments:[{id:"c1",date:"2026-11-20",user_type:"tourist",overall:5,comment:"Lovely",photos:[],likes:5,replies:[{text:"Agreed",date:"2026-11-21"}]}]},"tourist")');
  assert(one.indexOf('Tourist')<one.indexOf('Lovely'),'the walker and day read above the comment');
  assert(one.indexOf('Lovely')<one.indexOf('data-like='),'the like and reply chips sit under the comment');
  assert(one.includes('>5</span>')&&one.includes('Reply · 1')&&one.includes('Agreed'),'like count, reply count, and the reply itself');}
 // The dialog's own feed: heading, average, comments. Nothing said yet means no empty heading.
 const feed=run('walkerSaysFeed(evalD,"leisure")');
 assert(feed.includes('What other walkers said')&&feed.includes('6 rated walks')&&feed.includes('Busy but fine'));
 // Nothing rated yet still shows the section and says so: hiding it told the walker the feature was not there.
 {const empty=run('walkerSaysFeed({n:0,enabled:true},"leisure")');
  assert(!empty.includes('hidden')&&empty.includes('What other walkers said'),'the section stays on screen');
  assert(empty.includes('Yours would be the first'),'and invites the walker to be the first');
  assert(run('walkerSaysFeed({n:0,enabled:false},"leisure")').includes('not storing ratings'),'a site that cannot store a rating says so, and does not invite one');}
 assert.equal(run('walkerSaysMean({n:6,ratings:{overall:{mean:4.5}}})'),'★ 4.5 · 6 rated walks');
 // The rating dialog itself holds both: the walker's own form, then what other walkers said (PR #53 shipped the
 // likes and replies into a section the dialog never rendered).
 {run('walkerSays.evaluation=evalD');
  const content={innerHTML:'',querySelector:()=>null};
  const overlayClasses=new Set();
  ctx.document={getElementById:id=>({modalOverlay:{classList:{add:c=>overlayClasses.add(c),remove:c=>overlayClasses.delete(c)},querySelector:()=>null},modalOverline:{},modalTitle:{},modalContent:content}[id])};
  run('openWalkRating(r2)');
  assert(overlayClasses.has('modal-sheet'),'on a phone the rating fills the screen instead of floating as a card');
  run('walkerSays.evaluation=null');   // the later checks read it as a fresh page would
  assert(content.innerHTML.includes('class="walk-check"'),'the walker rates the walk');
  assert(content.innerHTML.includes('walker-says-feed')&&content.innerHTML.includes('Busy but fine'),'and reads what other walkers said, in the same dialog');
  assert(content.innerHTML.indexOf('class="walk-check"')<content.innerHTML.indexOf('walker-says-feed'),'own rating first, others below');}
 ctx.r3={edges:[{matched_segments:[{segment_id:'QN-1',street_name:'31 Ave'}]},{matched_segments:[{segment_id:'QN-2',street_name:'Steinway St'}]}]};
 assert.equal(run('JSON.stringify(routeSegmentIds(r3))'),'["QN-1","QN-2"]');
 const st=run("walkerSaysStreets({'QN-1':{quiet:{n:4,worse:3,better:1,status:'applied',delta:-6.5}}},r3)");
 assert(st.includes('31 Ave · Quiet &amp; Relax')&&st.includes('3 worse · 1 better · routing -6.5'));
 assert.equal(run("walkerSaysStreets({},r3)"),'');
 assert(run('walkerSaysBox(r3)').includes('I walked this – rate it now'));
 assert(run('walkCheckBox(r2)').includes('<details class="walk-check" data-route="rt-2" open>'),'the rating form opens ready to answer');
 // a short panel: stars, did it match, a comment and Send; everything else under "More detail"
 {const b=run('walkCheckBox(r2)'),main=b.slice(0,b.indexOf('walk-check-more'));
  assert(main.includes('class="walk-stars"')&&main.includes('>Not really<')&&main.includes('>Yes<')&&main.includes('data-k="comment"')&&main.includes('Send rating'));
  assert(!main.includes('How quiet')&&!main.includes('Study code')&&!main.includes('worth it'),'the research questions are one tap further');
  assert(b.slice(b.indexOf('walk-check-more')).includes('Study code'));}
 console.log('feedback UI ok');
})().catch(e=>{console.error(e);process.exit(1);});
