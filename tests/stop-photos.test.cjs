/* route-photos.js: a stop without a Wikidata ID gets one only when a Wikidata entry with its name has its own
   coordinates within 150 m and an image; a same-name entry elsewhere is never used. Fixed responses, no network. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('node:assert/strict');
const calls=[];
const ent=(lat,lon,img)=>({claims:{P625:[{mainsnak:{datavalue:{value:{latitude:lat,longitude:lon}}}}],...(img?{P18:[{mainsnak:{datavalue:{value:img}}}]}:{})}});
const fake=(url)=>{calls.push(url);let body;
 if(url.includes('geosearch'))body=url.includes('40.8118')?{query:{geosearch:[{title:'Q7'},{title:'Q8'}]}}:{query:{geosearch:[]}};
 else if(url.includes('wbgetentities')&&url.includes('Q7'))body={entities:{Q7:{...ent(40.8119,-73.9541,'StJoseph.jpg'),labels:{en:{value:"St. Joseph of the Holy Family's Church"}}},Q8:{...ent(40.8117,-73.9540,'Park.jpg'),labels:{en:{value:'Roosevelt Triangle'}}}}};
 else if(url.includes('wbsearchentities'))body=url.includes('Apollo')?{search:[{id:'Q1'},{id:'Q2'},{id:'Q3'}]}:{search:[]};
 else if(url.includes('wbgetentities')&&url.includes('Q1|'))body={entities:{Q1:ent(40.86,-73.80,'Far.jpg'),Q2:ent(40.8100,-73.9500,null),Q3:ent(40.81005,-73.95005,'Apollo.jpg')}};
 else if(url.includes('wbgetentities'))body={entities:{Q3:ent(40.81005,-73.95005,'Apollo.jpg')}};
 else body={query:{pages:{1:{title:'File:Apollo.jpg',imageinfo:[{thumburl:'https://upload.wikimedia.org/a.jpg',thumbwidth:320,thumbheight:240,descriptionurl:'https://commons.wikimedia.org/wiki/File:Apollo.jpg',extmetadata:{Artist:{value:'<a>Jane Doe</a>'},LicenseShortName:{value:'CC BY-SA 4.0'}}}]}}}};
 return Promise.resolve({json:()=>Promise.resolve(body)});};
class DP{parseFromString(h){const t=String(h).replace(/<[^>]+>/g,'');return{body:{textContent:t,querySelectorAll:()=>[],querySelector:()=>({textContent:t})}};}}
const ctx={window:{},fetch:fake,DOMParser:DP,console,Map,Set,Promise,AbortSignal};ctx.window=ctx;vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','route-photos.js'),'utf8')+';this.api={photosResolve,photosFor,photoIdFor,photoSearchNames,photoSameName,placePhotosEnsure,placePhoto};',ctx);
const {photosResolve,photosFor,photoIdFor,photoSearchNames,photoSameName,placePhotosEnsure,placePhoto}=ctx.api;
assert.ok(photoSameName('Church of St. Joseph of the Holy Family',"St. Joseph of the Holy Family's Church"));
assert.ok(!photoSameName("St. Mary's Protestant Episcopal Church, Parish House, and Sunday School",'Sheltering Arms Park'));
assert.ok(!photoSameName('Church of St. Joseph of the Holy Family','Holy Name Church'),'one shared word is not enough');
assert.ok(!photoSameName('St. Paul Church','St. Peter Church'));
assert.deepEqual([...photoSearchNames("St. Mary's Church, Parish House, and Sunday School")],["St. Mary's Church, Parish House, and Sunday School","St. Mary's Church"]);
const joseph={id:'lpc:LP-00303',name:'Church of St. Joseph of the Holy Family',lat:40.811801,lon:-73.954059};
const apollo={id:'lpc:LP-01299',name:'Apollo Theater',lat:40.81,lon:-73.95},nowhere={id:'lpc:X',name:'Nothing Here',lat:40.7,lon:-74};
photosResolve([apollo,joseph,nowhere,{id:'own',name:'Own',lat:40.81,lon:-73.95,wd:'Q3'}],()=>{});
setTimeout(()=>{
 assert.equal(photoIdFor(apollo),'Q3','nearest entry with an image within 150 m; Q1 is 6 km away, Q2 has no image');
 assert.equal(photoIdFor(joseph),'Q7','nearby entry with the same name; the park next door is not used');
 assert.equal(photoIdFor(nowhere),null,'no match → no photo');
 const ph=photosFor([{...apollo,wd:'Q3'}])[0];
 assert.equal(ph.author,'Jane Doe');assert.equal(ph.license,'CC BY-SA 4.0');
 const n=calls.length;photosResolve([apollo,nowhere],()=>{});
 setTimeout(()=>{assert.equal(calls.length,n,'resolved once per session');
  // a stop with no Wikidata entry (a café) ends with a street-level photo: the lookup that finds nothing still
  // reports back, and the next pass asks the API host for a photo at the place
  const cafe={id:'osm:node/1',name:'Corner Café',lat:40.7307,lon:-73.9985},asked=[];
  ctx.streetwiseFetch=(url,opt)=>{asked.push([url,JSON.parse(opt.body)]);return Promise.resolve({json:()=>Promise.resolve({configured:true,photos:{'osm:node/1':{thumb:'https://images.example/t.jpg',page:'https://www.mapillary.com/app/?pKey=1',username:'walker',captured_on:'2025-06-01',distance_m:12}}})});};
  let renders=0;const render=()=>{renders++;if(renders<20)placePhotosEnsure([cafe],render);};
  render();
  setTimeout(()=>{
   assert.equal(asked.length,1,'asked the API host once');assert.equal(asked[0][0],'/api/place-photos');assert.equal(asked[0][1].places[0].id,'osm:node/1');
   const ph=placePhoto(cafe);assert.equal(ph&&ph.kind,'street','street-level photo shown');assert.equal(ph.author,'walker');
   assert(renders<20,'no endless redraw');
   console.log('stop-photos: ok');},80);
 },20);
},50);
