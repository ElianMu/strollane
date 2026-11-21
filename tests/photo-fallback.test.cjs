/* route-photos.js: a place photo from the index is loaded from the copy published with the site first, then from
   Wikimedia, and only when both fail is it dropped (the place then gets its street photo). Never a broken-image icon. */
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const {JSDOM}=require(process.env.JSDOM_PATH||'jsdom');
const dom=new JSDOM('<!doctype html><body></body>',{runScripts:'outside-only',url:'https://elianmu.github.io/strollane/'}),w=dom.window;
w.fetch=()=>Promise.reject(new Error('no network in this test'));
w.eval(fs.readFileSync(path.join(__dirname,'..','route-photos.js'),'utf8')+';window.__t={photoIndex,placePhoto,photoFigures,photoBroken,photoOk,photoImg};');
const {photoIndex,placePhoto,photoFigures,photoBroken}=w.__t;
photoIndex.doc={thumb_base:'https://upload.wikimedia.org/wikipedia/commons/thumb/',items:{'osm:way/318329003':['8/8a/Roosevelt_Triangle_HDR_2022_jeh.jpg/330px-Roosevelt_Triangle_HDR_2022_jeh.jpg','Jim.henderson','CC BY-SA 4.0','Q34858736','wd:p18',40.811332,-73.954394,'Roosevelt Triangle']}};
const place={id:'osm:way/318329003',name:'Roosevelt Triangle',lat:40.8113,lon:-73.9544};
const remote='https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Roosevelt_Triangle_HDR_2022_jeh.jpg/330px-Roosevelt_Triangle_HDR_2022_jeh.jpg';
const ph=placePhoto(place);
assert.equal(ph.local,'data/places/thumbs/8/8a/Roosevelt_Triangle_HDR_2022_jeh.jpg/330px-Roosevelt_Triangle_HDR_2022_jeh.jpg');
w.document.body.innerHTML=photoFigures([ph],'rp-row');
let img=w.document.querySelector('.rp-photo img');
assert.equal(img.getAttribute('src'),ph.local,'the copy published with the site is tried first');
assert.equal(img.getAttribute('data-fallback'),remote);
img.dispatchEvent(new w.Event('error'));
assert.equal(img.getAttribute('src'),remote,'a missing copy falls back to Wikimedia');assert(!img.hasAttribute('data-fallback'));
assert(img.isConnected&&!photoBroken.has(remote),'one failure is not the end');
img.dispatchEvent(new w.Event('error'));
assert(photoBroken.has(remote),'both failed: the photo is dropped');assert.equal(placePhoto(place),null,'and not offered again (street photo instead)');
assert(!w.document.querySelector('.rp-photo img'),'no broken-image icon left on the card');
console.log('PHOTO FALLBACK PASS: copy with the site → Wikimedia → dropped, never a broken icon');
