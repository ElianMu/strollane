'use strict';
/* Route photos: real photos of the real places a walk passes, with their authors and licences.

   Source: Wikimedia Commons, through the place's own Wikidata entry (image property P18). Only places in the
   place index that carry a Wikidata ID (data/places/*.json, field `wd`) and lie within 50 m of the route are used
   (route-story.js storyPlacesNear). Nothing is generated, guessed or substituted: a place without a usable photo
   simply shows none.

   Safeguards:
   - the Wikidata entry's own coordinates (P625) must be within 300 m of the place, so a wrong ID never shows a
     photo of something else;
   - only free licences (CC BY / BY-SA / CC0 / public domain) with a named author (or public domain) are shown;
   - every photo carries its author, licence and a link to its Commons page.

   Cost and limits: free, no key. Requests go from the visitor's browser straight to wikidata.org and
   commons.wikimedia.org (anonymous CORS, `origin=*`), batched (≤ 50 ids per call) and cached for the session, so
   Wikimedia sees the visitor's IP and the places looked up. Thumbnails are 320 px from thumb.wikimedia.org.
   Turn off with window.STROLLANE_PHOTOS = false.                                                                 */

const PHOTO = {MAX_KM: 0.3, WIDTH: 320, BATCH: 50, FREE: /^(CC[ -]?BY|CC0|CC-BY|Public domain|PD)/i};
const routePhotos = {cache: new Map(), inflight: null, queue: new Set(), failed: false};

/** Commons metadata is third-party HTML. Parse it in an inert document (DOMParser: no scripts, no image loads, no
    event handlers) rather than through innerHTML on an element of the live page. */
function photoHtml(html) { return new DOMParser().parseFromString(String(html || ''), 'text/html').body; }
function photoStrip(html) { return (photoHtml(html).textContent || '').replace(/\s+/g, ' ').trim(); }
/** The author's name from Commons' Artist HTML: the first linked name, without notes such as "This panoramic image
    was created with…", "(talk)" or "No machine-readable author provided … assumed". */
function photoAuthor(html) {
 if (!html) return '';
 const d = photoHtml(html);
 d.querySelectorAll('div, small, .signature-talk').forEach((n) => n.remove());
 const named = d.querySelector('bdi, a');
 const text = (named ? named.textContent : d.textContent || '').replace(/No machine-readable author provided\.?/i, '').replace(/\s*assumed \(based on copyright claims\)\.?/i, '');
 return text.replace(/\s+/g, ' ').trim();
}
function photoKm(a, b) { const k = Math.PI / 180, x = (b.lon - a.lon) * Math.cos((a.lat + b.lat) / 2 * k), y = b.lat - a.lat; return Math.hypot(x, y) * k * 6371; }
function photosEnabled() { return typeof window !== 'undefined' && window.STROLLANE_PHOTOS !== false && typeof fetch === 'function'; }

/** Photos already loaded for these places (in their order), each {wd, name, thumb, w, h, page, author, license}. */
function photosFor(places) {
 return (places || []).map((p) => { const x = routePhotos.cache.get(p.wd); return x && x.thumb ? {...x, name: p.name} : null; }).filter(Boolean);
}
/** Load photos for places not seen yet; calls `done` once new photos arrived. Network errors leave no photos. */
function photosLoad(places, done) {
 if (!photosEnabled() || routePhotos.failed) return;
 for (const p of places || []) if (p.wd && !routePhotos.cache.has(p.wd)) routePhotos.queue.add(p);
 if (routePhotos.inflight || !routePhotos.queue.size) return;
 const batch = [...routePhotos.queue].slice(0, PHOTO.BATCH);
 batch.forEach((p) => routePhotos.queue.delete(p));
 routePhotos.inflight = photosFetch(batch).then((found) => {
  routePhotos.inflight = null;
  // also when nothing was found: the caller then moves on to the next source (street view at the place)
  if (typeof done === 'function') done();
  if (routePhotos.queue.size) photosLoad([], done);
 }).catch(() => { routePhotos.inflight = null; routePhotos.failed = true; batch.forEach((p) => routePhotos.cache.set(p.wd, {none: true})); if (typeof done === 'function') done(); });
}
async function photosFetch(places) {
 const ids = places.map((p) => p.wd);
 const wd = await fetch(`https://www.wikidata.org/w/api.php?action=wbgetentities&ids=${ids.join('|')}&props=claims&format=json&origin=*`).then((r) => r.json());
 const want = {};
 for (const p of places) {
  const claims = wd.entities?.[p.wd]?.claims || {}, file = claims.P18?.[0]?.mainsnak?.datavalue?.value, at = claims.P625?.[0]?.mainsnak?.datavalue?.value;
  // the entry must be this place: its own coordinates within 300 m of the place index point
  const here = at && photoKm({lat: p.lat, lon: p.lon}, {lat: at.latitude, lon: at.longitude}) <= PHOTO.MAX_KM;
  if (file && here) want['File:' + file] = p.wd; else routePhotos.cache.set(p.wd, {none: true});
 }
 const titles = Object.keys(want);
 if (!titles.length) return false;
 const cm = await fetch(`https://commons.wikimedia.org/w/api.php?action=query&titles=${encodeURIComponent(titles.join('|'))}&prop=imageinfo&iiprop=url|extmetadata&iiurlwidth=${PHOTO.WIDTH}&iiextmetadatafilter=Artist|LicenseShortName|LicenseUrl|Credit&format=json&origin=*`).then((r) => r.json());
 const alias = Object.fromEntries((cm.query?.normalized || []).map((n) => [n.to, n.from]));
 let found = false;
 for (const page of Object.values(cm.query?.pages || {})) {
  const id = want[alias[page.title] || page.title]; if (!id) continue;
  const info = page.imageinfo?.[0], m = info?.extmetadata || {};
  const license = photoStrip(m.LicenseShortName?.value), author = photoAuthor(m.Artist?.value) || (/public domain|^PD|^CC0/i.test(license) ? '' : null); // no author → only public domain / CC0 can be shown
  if (!info?.thumburl || !PHOTO.FREE.test(license) || author == null) { routePhotos.cache.set(id, {none: true}); continue; }
  routePhotos.cache.set(id, {wd: id, thumb: info.thumburl, w: info.thumbwidth, h: info.thumbheight, page: info.descriptionurl, author: author.slice(0, 80), license, licenseUrl: m.LicenseUrl?.value || null});
  found = true;
 }
 for (const t of titles) if (!routePhotos.cache.has(want[t])) routePhotos.cache.set(want[t], {none: true});
 return found;
}
/* Places with no Wikidata ID in the place index (most NYC LPC landmark records): find the entry by the place's own
   name on Wikidata, then keep it only if that entry's coordinates (P625) are within 150 m of the place and it has an
   image (P18); failing that, an entry placed within 150 m whose label names the same place. No match → no photo. Results cached per place id for the session. */
const PHOTO_MATCH_KM = 0.15;
const photoIds = {cache: new Map(), pending: new Set()};
function photoSearchNames(name) {
 const n = String(name || '').replace(/\(.*?\)/g, ' ').replace(/\s+/g, ' ').trim();
 const first = n.split(/,| and /i)[0].trim();
 return [...new Set([n, first].filter((x) => x.length > 2))];
}
/** The Wikidata ID to use for a place: its own (`wd`/`wikidata`), else one resolved by name + location, else null. */
function photoIdFor(p) { return p?.wd || p?.wikidata || photoIds.cache.get(p?.id) || null; }
/** Resolve IDs for places that lack one, then load their photos; `done` runs when new photos arrive. */
function photosResolve(places, done) {
 if (!photosEnabled()) return;
 const ready = [], todo = [];
 for (const p of places || []) {
  if (!p || p.lat == null || p.lon == null) continue;
  const wd = photoIdFor(p);
  if (wd) ready.push({...p, wd});
  else if (p.id && !photoIds.cache.has(p.id) && !photoIds.pending.has(p.id)) todo.push(p);
 }
 if (ready.length) photosLoad(ready, done);
 for (const p of todo) {
  photoIds.pending.add(p.id);
  photoResolveOne(p).then((wd) => {
   photoIds.cache.set(p.id, wd || null); photoIds.pending.delete(p.id);
   // no Wikidata entry: tell the caller, so it can ask for a street-level photo instead (this was never reached
   // before 2026-11-20, so City Walk stops without a Wikidata entry stayed without a photo)
   if (wd) photosLoad([{...p, wd}], done); else if (typeof done === 'function') done();
  }).catch(() => { photoIds.cache.set(p.id, null); photoIds.pending.delete(p.id); if (typeof done === 'function') done(); });
 }
}
/** Words that name the place, without generic ones ("church", "the", "st"), for comparing a nearby entry's label. */
const PHOTO_STOP = new Set(['the','of','and','a','an','at','in','on','st','saint','street','church','building','house','new','york','nyc','s']);
function photoWords(name) {
 return new Set(String(name || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/['’]s\b/g, '').split(/[^a-z0-9]+/).filter((w) => w.length > 1 && !PHOTO_STOP.has(w)));
}
/** Same place by name: the shorter word set is (almost) all in the longer one, and at least two words are shared
    (one is enough only when both names have a single word). */
function photoSameName(a, b) {
 const A = photoWords(a), B = photoWords(b), [s, l] = A.size <= B.size ? [A, B] : [B, A];
 if (!s.size) return false;
 const shared = [...s].filter((w) => l.has(w)).length;
 return shared >= Math.min(2, s.size) && shared / s.size >= 0.75;
}
async function photoResolveOne(p) {
 const ids = new Set();
 for (const q of photoSearchNames(p.name)) {
  const r = await fetch(`https://www.wikidata.org/w/api.php?action=wbsearchentities&search=${encodeURIComponent(q)}&language=en&type=item&limit=7&format=json&origin=*`).then((x) => x.json());
  (r.search || []).forEach((h) => ids.add(h.id));
  if (ids.size) break;
 }
 // entries placed within 150 m of the stop, used only when their label names the same place (Wikidata often words
 // it differently: "St. Joseph of the Holy Family's Church" for "Church of St. Joseph of the Holy Family")
 const near = new Set();
 const g = await fetch(`https://www.wikidata.org/w/api.php?action=query&list=geosearch&gscoord=${p.lat}|${p.lon}&gsradius=${Math.round(PHOTO_MATCH_KM * 1000)}&gslimit=30&format=json&origin=*`).then((x) => x.json()).catch(() => ({}));
 (g.query?.geosearch || []).forEach((h) => { if (!ids.has(h.title)) near.add(h.title); });
 const all = [...ids, ...near].slice(0, 50);
 if (!all.length) return null;
 const wd = await fetch(`https://www.wikidata.org/w/api.php?action=wbgetentities&ids=${all.join('|')}&props=claims|labels&languages=en&format=json&origin=*`).then((x) => x.json());
 let best = null;
 for (const id of all) {
  const e = wd.entities?.[id] || {}, c = e.claims || {}, at = c.P625?.[0]?.mainsnak?.datavalue?.value;
  if (!at || !c.P18) continue;
  if (near.has(id) && !photoSameName(p.name, e.labels?.en?.value)) continue;
  const km = photoKm({lat: p.lat, lon: p.lon}, {lat: at.latitude, lon: at.longitude});
  if (km <= PHOTO_MATCH_KM && (!best || km < best.km)) best = {id, km};
 }
 return best ? best.id : null;
}

/* ---------- one photo per place, from the best real source (v5) ----------
   1. the place photo index (data/places/photos.json, built by scripts/build_place_photos.mjs: Wikidata / Wikipedia
      images matched by the place's own ID, its NYC landmark number or its name within 150 m);
   2. the place's Wikidata image fetched live (own ID, or resolved by name + location: photosResolve);
   3. failing both, a street-level photo taken within 30 m of the place (Mapillary, via this app's API host),
      labelled "Street view here": it shows the street at the place, not a portrait of it.
   No source → no photo. */
const photoIndex = {doc: null, loading: null, failed: false};
const PHOTO_INDEX_URL = './data/places/photos.json';
function photoIndexLoad(done) {
 if (photoIndex.doc || photoIndex.failed || !photosEnabled()) return photoIndex.loading;
 if (!photoIndex.loading) {
  const get = typeof streetwiseJson === 'function' ? streetwiseJson(PHOTO_INDEX_URL) : fetch(PHOTO_INDEX_URL).then((r) => r.json());
  photoIndex.loading = get.then((d) => { photoIndex.doc = d && d.items ? d : {items: {}}; return photoIndex.doc; })
   .catch(() => { photoIndex.failed = true; photoIndex.doc = {items: {}}; return photoIndex.doc; });
 }
 if (typeof done === 'function') photoIndex.loading.then(done);
 return photoIndex.loading;
}
/** The index entry as a photo, or null. Fields: [thumb, author, license, wikidata, via, lat, lon, name]. */
function photoFromIndex(id, name) {
 const e = photoIndex.doc?.items?.[id]; if (!e) return null;
 const base = photoIndex.doc.thumb_base || 'https://upload.wikimedia.org/wikipedia/commons/thumb/';
 const file = decodeURIComponent(String(e[0]).split('/')[2] || '');
 return {kind: 'commons', wd: e[3] || null, name: name || e[7] || '', thumb: base + e[0], page: 'https://commons.wikimedia.org/wiki/File:' + encodeURIComponent(file.replace(/ /g, '_')),
  author: e[1] || '', license: e[2] || '', via: e[4] || ''};
}
const streetPhotos = {cache: new Map(), asked: new Set(), inflight: false, failed: false};
/** The photo to show for one place {id, wd?, name, lat, lon}, or null (not found yet, or none). */
function placePhoto(p) {
 if (!p) return null;
 const ix = photoFromIndex(p.id, p.name); if (ix) return ix;
 const wd = photoIdFor(p);
 if (wd) { const x = routePhotos.cache.get(wd); if (x && x.thumb) return {kind: 'commons', ...x, name: p.name}; }
 const st = streetPhotos.cache.get(p.id); return st ? {...st, name: p.name} : null;
}
/** Has every Wikimedia route been tried for this place, with nothing found? */
function photoWikimediaNone(p) {
 if (!photoIndex.doc || photoIndex.doc.items?.[p.id]) return false;
 const wd = photoIdFor(p);
 if (wd) return Boolean(routePhotos.cache.get(wd)?.none);
 return photoIds.cache.has(p.id) && photoIds.cache.get(p.id) == null;
}
/** Start whatever loading these places still need; `done` runs when new photos arrive (call again from it). */
function placePhotosEnsure(places, done) {
 if (!photosEnabled()) return;
 const list = (places || []).filter((p) => p && p.id && p.lat != null && p.lon != null);
 if (!photoIndex.doc) { photoIndexLoad(() => { if (list.length && typeof done === 'function') done(); }); return; }
 const rest = list.filter((p) => !photoIndex.doc.items[p.id]);
 if (rest.length) photosResolve(rest, done);
 const want = rest.filter((p) => !streetPhotos.asked.has(p.id) && photoWikimediaNone(p)).slice(0, 8);
 if (!want.length || streetPhotos.inflight || streetPhotos.failed || typeof streetwiseFetch !== 'function') return;
 want.forEach((p) => streetPhotos.asked.add(p.id));
 streetPhotos.inflight = true;
 streetwiseFetch('/api/place-photos', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({places: want.map((p) => ({id: String(p.id).slice(0, 80), lon: p.lon, lat: p.lat}))}), signal: AbortSignal.timeout(30000)})
  .then((r) => r.json()).then((d) => {
   if (d && d.configured === false) { streetPhotos.failed = true; return; }
   let any = false;
   for (const [id, ph] of Object.entries(d?.photos || {})) {
    if (!/^https:\/\//.test(ph.thumb || '') || !/^https:\/\/www\.mapillary\.com\//.test(ph.page || '')) continue;
    streetPhotos.cache.set(id, {kind: 'street', thumb: ph.thumb, page: ph.page, author: ph.username || '', license: 'CC BY-SA', date: String(ph.captured_on || '').slice(0, 7), distance: ph.distance_m});
    any = true;
   }
   if (any && typeof done === 'function') done();
  }).catch(() => {}).finally(() => { streetPhotos.inflight = false; if (list.some((p) => !streetPhotos.asked.has(p.id) && photoWikimediaNone(p)) && typeof done === 'function') done(); });
}
/** Places with an index photo within maxM metres of a route line, nearest first: [{id, name, lat, lon, d}]. */
function photoPlacesNear(r, maxM = 50) {
 const items = photoIndex.doc?.items, c = r?.geometry?.coordinates || [];
 if (!items || c.length < 2) return [];
 let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
 for (const [x, y] of c) { w = Math.min(w, x); e = Math.max(e, x); s = Math.min(s, y); n = Math.max(n, y); }
 const pad = 0.001, k = Math.cos((s + n) / 2 * Math.PI / 180), out = [];
 const segD = (p) => { let best = Infinity; for (let i = 1; i < c.length; i++) { const ax = c[i - 1][0] * k, ay = c[i - 1][1], bx = c[i][0] * k, by = c[i][1], px = p.lon * k, py = p.lat, dx = bx - ax, dy = by - ay, L = dx * dx + dy * dy, t = L ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / L)) : 0; best = Math.min(best, Math.hypot(px - ax - t * dx, py - ay - t * dy)); } return best * 111320; };
 for (const [id, v] of Object.entries(items)) {
  const lat = v[5], lon = v[6]; if (lat == null || lon < w - pad || lon > e + pad || lat < s - pad || lat > n + pad) continue;
  const d = segD({lat, lon}); if (d <= maxM) out.push({id, name: v[7], lat, lon, wd: v[3] || null, d: Math.round(d)});
 }
 return out.sort((a, b) => a.d - b.d);
}
const photoEsc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
/** A row of photos, each with the place name and its credit (author · licence, linked to the Commons page). */
function photoFigures(photos, cls) {
 if (!photos.length) return '';
 return `<div class="${cls}">${photos.map((x) => {
  const credit = x.kind === 'street' ? ['Street view here', x.date, x.author, 'Mapillary'].filter(Boolean).join(' · ') : [x.author, x.license].filter(Boolean).join(' · ');
  return `<figure class="rp-photo"><img src="${photoEsc(x.thumb)}" alt="${photoEsc(x.name)}" decoding="async" referrerpolicy="no-referrer" width="${x.w || 320}" height="${x.h || 213}"><figcaption><strong>${photoEsc(x.name)}</strong><a href="${photoEsc(x.page)}" target="_blank" rel="noopener" title="${photoEsc(credit)} — Wikimedia Commons">${photoEsc(credit)}</a></figcaption></figure>`;
 }).join('')}</div>`;
}

if (typeof window !== 'undefined') { window.routePhotos = routePhotos; Object.assign(routePhotos, {for: photosFor, load: photosLoad, resolve: photosResolve, idFor: photoIdFor, figures: photoFigures, LIMITS: PHOTO, place: placePhoto, ensure: placePhotosEnsure, near: photoPlacesNear, index: photoIndex, street: streetPhotos}); }
