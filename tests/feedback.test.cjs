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
 const body=run("walkCheckPayload(r2,{rate:{overall:4,quiet:5,'dim:Architecture':3},worth:'no-detour',compared:'this'},'P07','Nice')");
 assert.deepEqual(Object.keys(body).sort(),['comment','compared_with_shortest','detour_pct','dimension_ratings','distance_m','network_version','priorities','ratings','route_id','route_signature','route_snapshot','score_version','study_code','user_type','worth_detour']);
 assert.equal(JSON.stringify(body.ratings),'{"overall":4,"match":null,"quiet":5,"green":null}');
 assert.equal(JSON.stringify(body.dimension_ratings),'{"Architecture":3}');
 assert.equal(JSON.stringify(body.priorities),'{"Nature":{"weight":80,"direction":"high"},"Quiet & Relax":{"weight":80,"direction":"high"},"Architecture":{"weight":70,"direction":"high"}}');
 assert.equal(body.route_snapshot.ordered_edge_ids.length,2);assert(!('predicted' in body),'the client never sends a prediction');
 assert.equal(run("walkCheckPayload(r2,{rate:{overall:2},worth:null,compared:'this'},'','')").compared_with_shortest,null,'comparison only with a study code');
 console.log('feedback UI ok');
})().catch(e=>{console.error(e);process.exit(1);});
