/* map-callouts.js layout: cards stay inside the free map area, never overlap each other or the map's own panels,
   never cover another place, and a crowded corner still gets its card. Numbers from a real Harlem City Walk
   (Columbia → Apollo Theater, 1440×900 desktop, legend open). */
const assert=require('node:assert/strict');
const {calloutPlace,calloutArrange}=require('../map-callouts.js');
const box={x0:10,y0:10,x1:649,y1:798,obstacles:[{x:458,y:429,w:236,h:363},{x:18,y:762,w:182,h:31},{x:18,y:16,w:205,h:41},{x:165,y:70,w:115,h:35},{x:266,y:16,w:380,h:46}]};
const pts=[[175,475],[233,504],[453,318],[603,389]];
const order=pts.map(([x,y],i)=>({a:{x,y},it:{rank:i+1},w:132,h:i===3?148:176}));
const route=[];for(let i=0;i<=40;i++){const t=i/40;route.push({x:175+(603-175)*t,y:475+(389-475)*t-80*Math.sin(Math.PI*t)});}
const out=calloutArrange(order,route,box,64,4);
assert.equal(out.length,4,'all four stops get a card, the crowded Apollo corner included');
const hit=(r,p)=>r.x<p.x+p.w&&p.x<r.x+r.w&&r.y<p.y+p.h&&p.y<r.y+r.h;
for(const {o,rect} of out){
 assert(rect.x>=box.x0&&rect.y>=box.y0&&rect.x+rect.w<=box.x1&&rect.y+rect.h<=box.y1,'inside the free map area');
 for(const ob of box.obstacles)assert(!hit(rect,ob),'clear of the legend and map controls');
 for(const p of out)if(p!==out.find(x=>x.o===o)&&p.rect!==rect)assert(!hit(rect,p.rect),'cards do not overlap');
 for(const q of order)if(q!==o)assert(!(q.a.x>rect.x&&q.a.x<rect.x+rect.w&&q.a.y>rect.y&&q.a.y<rect.y+rect.h),'a card never covers another place');
}
// no room at all → no card (never forced onto the map controls)
assert.equal(calloutPlace({x:30,y:30},[],[],{x0:10,y0:10,x1:60,y1:60,obstacles:[]},132,150,64,[]),null);
// after a pan a card keeps its spot while that spot is still free (no jumping), and moves when it is not
{const b={x0:0,y0:0,x1:500,y1:500,obstacles:[]};
 const kept=calloutPlace({x:200,y:200},[],[],b,100,80,64,[],{dx:-170,dy:-100});assert.deepEqual([kept.x,kept.y],[30,100]);
 const moved=calloutPlace({x:200,y:200},[],[],b,100,80,64,[],{dx:-260,dy:-100});assert(moved.x>=0,'off-map spot is not kept');}
console.log('map-callouts: ok');
