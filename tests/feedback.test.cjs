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
 console.log('feedback UI ok');
})().catch(e=>{console.error(e);process.exit(1);});
