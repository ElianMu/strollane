'use strict';
/* Place photo index builder (shared by scripts/build_place_photos.mjs and a browser run).

   For every place in the given lists, find ONE real photo of that place, with its author and licence:
     1. its own Wikidata entry (place.wd), or
     2. the Wikidata entry carrying its NYC Landmarks Preservation Commission number (P4273), for LPC records, or
     3. a Wikidata entry within 150 m of the place whose English label names the same place (two distinctive words
        in common, or the whole name for one-word names);
   then that entry's image (P18), or failing that the free lead image of its English Wikipedia article.
   Only freely licensed files (CC BY / CC BY-SA / CC0 / public domain) with a named author (or public domain / CC0)
   are kept. A place with no match gets no entry: nothing is guessed or substituted.

   Output: {items: {placeId: [thumbPath, author, license, wikidataId, via, lat, lon, name]}} where thumbPath is the part
   after https://upload.wikimedia.org/wikipedia/commons/thumb/ (Commons may serve it from thumb.wikimedia.org too) of a 330 px thumbnail, and via is
   'wd' | 'lpc' | 'name' (how the entry was found) + ':p18' | ':wiki' (where the image came from). */
const PP = {MATCH_M: 150, WIDTH: 330, FREE: /^(CC[ -]?BY|CC0|CC-BY|Public domain|PD)/i,
 BOX: [-74.26, 40.49, -73.69, 40.92], TILES: 8, UA: 'STROLLANE-NYC-photo-index/1.0 (Columbia GSAPP course project)'};
const PP_STOP = new Set(['the', 'of', 'and', 'a', 'an', 'at', 'in', 'on', 'st', 'saint', 'street', 'church', 'building', 'house', 'houses', 'new', 'york', 'nyc', 's', 'former', 'old',
 'branch', 'public', 'borough', 'queens', 'brooklyn', 'manhattan', 'bronx', 'n', 'y', 'inc', 'hotel', 'company', 'co']);

function ppWords(name) {
 return new Set(String(name || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').replace(/['’]s\b/g, '')
  .split(/[^a-z0-9]+/).filter((w) => w.length > 1 && !PP_STOP.has(w)));
}
/** Words that name a part of, or a thing inside, a bigger place: a name that adds one of these is a different
    thing (a park's tablet is not the park; a park's zoo is not the park). */
const PP_PART = new Set(['tablet', 'plaque', 'monument', 'memorial', 'statue', 'sculpture', 'bust', 'fountain', 'flagpole', 'marker', 'tree', 'trees', 'section',
 'improvement', 'gate', 'gates', 'entrance', 'playground', 'pool', 'station', 'bench', 'mural', 'carousel', 'bandshell', 'boathouse', 'zoo', 'reservoir',
 'lake', 'pond', 'arch', 'bridge', 'tower', 'stairs', 'steps', 'wall', 'clock', 'sign', 'lamppost', 'pavilion', 'comfort', 'dog', 'run', 'field', 'court',
 'courts', 'garage', 'annex', 'addition', 'wing', 'interior', 'lobby', 'parsonage', 'rectory', 'school', 'chapel', 'cemetery', 'grandiflora']);
/** Same place by name. `ours` is the place's own name, `label` the candidate entry's label:
    - at least 75 % of our place's distinctive words are in the label (and two or more of them; one-word names must
      match whole), and
    - neither name adds a word naming a part of something bigger (PP_PART) that the other lacks. */
function ppSameName(ours, label) {
 // a name in two languages or with a second name ("Holyrood Episcopal Church-Iglesia Santa Cruz") may match by either part
 const parts = String(ours || '').split(/\s+[-–\/]\s+|\s*\/\s*|-(?=[A-Z])/).map((x) => x.trim()).filter(Boolean);
 if (parts.length > 1 && parts.some((x) => ppSameOne(x, label))) return true;
 return ppSameOne(ours, label);
}
function ppSameOne(ours, label) {
 const A = ppWords(ours), B = ppWords(label);
 if (!A.size || !B.size) return false;
 const shared = [...A].filter((w) => B.has(w)).length;
 if (A.size === 1 || B.size === 1) return A.size === B.size && shared === 1;
 if (shared < 2 || shared / A.size < 0.75) return false;
 for (const w of A) if (!B.has(w) && PP_PART.has(w)) return false;
 for (const w of B) if (!A.has(w) && PP_PART.has(w)) return false;
 return true;
}
function ppMetres(a, b) {
 const k = Math.PI / 180, x = (b.lon - a.lon) * Math.cos((a.lat + b.lat) / 2 * k);
 return Math.hypot(x, b.lat - a.lat) * k * 6371008.8;
}
const ppStrip = (h) => String(h || '').replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#0?39;/g, "'").replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();
/** The author's name from Commons' Artist HTML: the first linked name, else the plain text without notes. */
function ppAuthor(html) {
 const a = /<a\b[^>]*>(.*?)<\/a>/is.exec(String(html || ''));
 const t = ppStrip(a ? a[1] : html).replace(/\s*\(.*$/, '').replace(/^(Photo|Photograph|Image)( by)?:?\s*/i, '').trim();
 // a link to a source file (a derivative work) is not a name
 return /\.(jpe?g|png|gif|tiff?|svg)$/i.test(t) ? '' : t.slice(0, 80);
}

async function ppJson(fetchFn, url, opts) {
 for (let i = 0; i < 4; i++) {
  try {
   const r = await fetchFn(url, opts);
   if (r.status === 429 || r.status >= 500) throw new Error('HTTP ' + r.status);
   return await r.json();
  } catch (e) { if (i === 3) throw e; await new Promise((res) => setTimeout(res, 1500 * (i + 1))); }
 }
}
const ppChunks = (a, n) => { const out = []; for (let i = 0; i < a.length; i += n) out.push(a.slice(i, i + n)); return out; };
async function ppPool(items, n, fn) { const q = [...items]; await Promise.all(Array.from({length: n}, async () => { while (q.length) await fn(q.shift()); })); }

/** places: [{id, name, lat, lon, wd?, src?}] → {items, counts} */
async function buildPlacePhotoIndex(places, {fetch: fetchFn = fetch, log = () => {}, node = false} = {}) {
 const H = node ? {headers: {'User-Agent': PP.UA}} : undefined;
 const WD = 'https://www.wikidata.org/w/api.php', SPARQL = 'https://query.wikidata.org/sparql';
 const sparql = (q) => ppJson(fetchFn, `${SPARQL}?format=json&query=${encodeURIComponent(q)}`, H).then((d) => d.results.bindings);
 const qid = (uri) => uri.replace(/^.*\//, '');
 const file = (uri) => decodeURIComponent(uri.replace(/^.*Special:FilePath\//, '')).replace(/_/g, ' ');
 const found = new Map();   // placeId -> {wd, via}

 // 1. own Wikidata IDs
 for (const p of places) if (p.wd) found.set(p.id, {wd: p.wd, via: 'wd'});
 // 2. LPC numbers (P4273 holds "1299" for LP-01299)
 const lpc = places.filter((p) => !found.has(p.id) && /^lpc:LP-\d+/.test(p.id));
 if (lpc.length) {
  const rows = await sparql('SELECT ?item ?n WHERE { ?item wdt:P4273 ?n . }');
  const byNum = new Map(); for (const r of rows) byNum.set(String(Number(r.n.value)), qid(r.item.value));
  for (const p of lpc) { const n = String(Number(p.id.replace(/^lpc:LP-0*/, '').replace(/\D.*$/, ''))); if (byNum.has(n)) found.set(p.id, {wd: byNum.get(n), via: 'lpc'}); }
  log(`LPC numbers: ${lpc.filter((p) => found.has(p.id)).length}/${lpc.length}`);
 }
 // 3. name within 150 m, against every Wikidata entry with coordinates and an image in the NYC box (tiled)
 const rest = places.filter((p) => !found.has(p.id) && p.lat != null);
 if (rest.length) {
  const [w, s, e, n] = PP.BOX, cand = [];
  const tiles = [];
  for (let i = 0; i < PP.TILES; i++) for (let j = 0; j < PP.TILES; j++) tiles.push([w + (e - w) * i / PP.TILES, s + (n - s) * j / PP.TILES, w + (e - w) * (i + 1) / PP.TILES, s + (n - s) * (j + 1) / PP.TILES]);
  await ppPool(tiles, 3, async ([x0, y0, x1, y1]) => {
   if (!rest.some((p) => p.lon >= x0 - 0.002 && p.lon <= x1 + 0.002 && p.lat >= y0 - 0.002 && p.lat <= y1 + 0.002)) return;
   const rows = await sparql(`SELECT ?item ?loc ?l WHERE { SERVICE wikibase:box { ?item wdt:P625 ?loc . bd:serviceParam wikibase:cornerSouthWest "Point(${x0} ${y0})"^^geo:wktLiteral . bd:serviceParam wikibase:cornerNorthEast "Point(${x1} ${y1})"^^geo:wktLiteral . } ?item rdfs:label ?l . FILTER(LANG(?l) = "en") }`);
   for (const r of rows) { const m = /Point\(([-\d.]+) ([-\d.]+)\)/.exec(r.loc.value); if (m) cand.push({wd: qid(r.item.value), lon: +m[1], lat: +m[2], label: r.l.value}); }
  });
  log(`Wikidata entries with coordinates in NYC: ${cand.length}`);
  // grid for the 150 m search
  const cell = 0.002, grid = new Map(), key = (x, y) => `${Math.floor(x / cell)},${Math.floor(y / cell)}`;
  for (const c of cand) { const k = key(c.lon, c.lat); if (!grid.has(k)) grid.set(k, []); grid.get(k).push(c); }
  for (const p of rest) {
   let best = null; const gx = Math.floor(p.lon / cell), gy = Math.floor(p.lat / cell);
   for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const c of grid.get(`${gx + dx},${gy + dy}`) || []) {
    const d = ppMetres(p, c); if (d > PP.MATCH_M || !ppSameName(p.name, c.label)) continue;
    if (!best || d < best.d) best = {wd: c.wd, d};
   }
   if (best) found.set(p.id, {wd: best.wd, via: 'name'});
  }
  log(`name within ${PP.MATCH_M} m: ${rest.filter((p) => found.has(p.id)).length}/${rest.length}`);
 }
 // images: P18, else the free lead image of the English Wikipedia article
 const ids = [...new Set([...found.values()].map((f) => f.wd))], img = new Map(), wiki = new Map();
 await ppPool(ppChunks(ids, 50), 3, async (b) => {
  const d = await ppJson(fetchFn, `${WD}?action=wbgetentities&ids=${b.join('|')}&props=claims|sitelinks&sitefilter=enwiki&format=json&origin=*`, H);
  for (const id of b) {
   const en = d.entities?.[id]; if (!en) continue;
   const f = en.claims?.P18?.[0]?.mainsnak?.datavalue?.value;
   if (f) img.set(id, {file: f, from: 'p18'}); else if (en.sitelinks?.enwiki?.title) wiki.set(en.sitelinks.enwiki.title, id);
  }
 });
 await ppPool(ppChunks([...wiki.keys()], 50), 3, async (b) => {
  const d = await ppJson(fetchFn, `https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&piprop=name&pilicense=free&titles=${encodeURIComponent(b.join('|'))}&format=json&origin=*&redirects=1`, H);
  const back = {}; for (const n of d.query?.normalized || []) back[n.to] = n.from; for (const n of d.query?.redirects || []) back[n.to] = back[n.from] || n.from;
  for (const pg of Object.values(d.query?.pages || {})) { const t = back[pg.title] || pg.title, id = wiki.get(t); if (id && pg.pageimage) img.set(id, {file: pg.pageimage.replace(/_/g, ' '), from: 'wiki'}); }
 });
 log(`entries with an image: ${img.size}/${ids.length}`);
 // file metadata: thumbnail, author, licence
 const files = [...new Set([...img.values()].map((x) => x.file))], meta = new Map();
 await ppPool(ppChunks(files, 50), 3, async (b) => {
  const d = await ppJson(fetchFn, `https://commons.wikimedia.org/w/api.php?action=query&titles=${encodeURIComponent(b.map((f) => 'File:' + f).join('|'))}&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=${PP.WIDTH}&iiextmetadatafilter=Artist|LicenseShortName&format=json&origin=*`, H);
  const back = {}; for (const n of d.query?.normalized || []) back[n.to] = n.from;
  for (const pg of Object.values(d.query?.pages || {})) {
   const info = pg.imageinfo?.[0]; if (!info?.thumburl) continue;
   const lic = ppStrip(info.extmetadata?.LicenseShortName?.value), auth = ppAuthor(info.extmetadata?.Artist?.value);
   const pd = /public domain|^PD|^CC0/i.test(lic);
   if (!PP.FREE.test(lic) || (!auth && !pd)) continue;
   const thumb = info.thumburl.replace(/^https:\/\/(upload|thumb)\.wikimedia\.org\/wikipedia\/commons\/thumb\//, '').replace(/\?.*$/, '');
   if (thumb === info.thumburl || !/^[0-9a-f]\/[0-9a-f]{2}\//.test(thumb)) continue; // not a Commons thumbnail
   const t = (back[pg.title] || pg.title).replace(/^File:/, '');
   meta.set(t, [thumb, auth, lic]);
  }
 });
 const items = {}, counts = {places: places.length, matched: found.size, photo: 0, wd: 0, lpc: 0, name: 0, p18: 0, wiki: 0};
 for (const p of places) {
  const f = found.get(p.id); if (!f) continue; const im = img.get(f.wd); if (!im) continue; const m = meta.get(im.file); if (!m) continue;
  items[p.id] = [...m, f.wd, `${f.via}:${im.from}`, Math.round(p.lat * 1e6) / 1e6, Math.round(p.lon * 1e6) / 1e6, p.name]; counts.photo++; counts[f.via]++; counts[im.from]++;
 }
 log(`places with a photo: ${counts.photo}/${places.length}`);
 return {items, counts};
}

if (typeof module !== 'undefined' && module.exports) module.exports = {buildPlacePhotoIndex, ppSameName, ppAuthor, ppWords};
if (typeof window !== 'undefined') window.buildPlacePhotoIndex = buildPlacePhotoIndex;
