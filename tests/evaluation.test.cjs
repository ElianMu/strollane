// Evaluation dashboard (evaluation.js): empty state, and every figure drawn from the API answer only.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {JSDOM}=require(process.env.JSDOM_PATH||'jsdom');
const root=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(root,'evaluation.html'),'utf8').replace(/<script[\s\S]*?<\/script>/g,'');
const dom=new JSDOM(html,{runScripts:'outside-only'});const w=dom.window;
w.module={};w.eval(fs.readFileSync(path.join(root,'evaluation.js'),'utf8'));
const {render}=w.module.exports;
const main=()=>w.document.getElementById('eval');
render({enabled:true,n:0,sources:['src A'],limitations:['lim B']});
assert(main().textContent.includes('暂无评估数据')&&main().textContent.includes('No evaluation data yet'));
assert(main().textContent.includes('src A')&&main().textContent.includes('lim B'));
assert.equal(main().querySelectorAll('svg').length,0,'no chart without data');
render({enabled:false,n:0,sources:[],limitations:[]});assert(main().textContent.includes('not switched on'));
const d={enabled:true,n:6,first_at:'2026-11-20T23:00:00+00:00',last_at:'2026-11-21T01:00:00+00:00',study_participants:2,score_versions:['v1'],
 ratings:{overall:{n:6,missing:0,mean:3.67,counts:{1:0,2:1,3:1,4:2,5:2}},match:{n:5,missing:1,mean:3.4,counts:{1:0,2:1,3:2,4:1,5:1}},quiet:{n:5,missing:1,mean:4,counts:{1:0,2:0,3:1,4:3,5:1}},green:{n:0,missing:6,mean:null,counts:{1:0,2:0,3:0,4:0,5:0}}},
 by_user_type:{leisure:{n:4,mean_overall:4,mean_match:3.5,mean_quiet:4,mean_green:null},tourist:{n:2,mean_overall:3,mean_match:3,mean_quiet:null,mean_green:null}},
 dimension_ratings:{'Quiet & Relax':{n:5,mean:4}},
 comparison:{'Quiet & Relax':{n:5,mean_predicted:60,mean_rating:4,mean_perceived_0_100:75,mean_deviation:15,mean_abs_deviation:20,spearman:0.7,points:[[20,3],[40,4],[60,4],[80,4],[100,5]]}},
 missing:{prediction_unavailable:1,no_priorities:0,rating_overall:0,rating_match:1,rating_quiet:1,rating_green:6},
 worth_detour:{yes:3,no:1,'no-detour':2},compared_with_shortest:{this:1,shortest:1,same:0},comments:2,sources:['S'],limitations:['L']};
render(d);
const t=main().textContent;
assert(t.includes('6')&&t.includes('3.67')&&t.includes('2 study participants'));
assert(t.includes('Only 6 answers so far'),'small samples are flagged');
assert.equal(main().querySelectorAll('svg circle').length,5,'one dot per real answer');
assert(t.includes('+15.0')&&t.includes('0.70'));
assert(t.includes('Leisure Walker')&&t.includes('Tourist'));
assert(t.includes('prediction unavailable')&&t.includes('1 of 6'));
assert(t.includes('No answers yet.'),'a rating nobody gave is shown as missing, not as zero');
console.log('evaluation dashboard ok');
