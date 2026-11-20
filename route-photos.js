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
  if (found && typeof done === 'function') done();
  if (routePhotos.queue.size) photosLoad([], done);
 }).catch(() => { routePhotos.inflight = null; routePhotos.failed = true; batch.forEach((p) => routePhotos.cache.set(p.wd, {none: true})); });
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
   if (wd) photosLoad([{...p, wd}], done);
  }).catch(() => { photoIds.cache.set(p.id, null); photoIds.pending.delete(p.id); });
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
const photoEsc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
/** A row of photos, each with the place name and its credit (author · licence, linked to the Commons page). */
function photoFigures(photos, cls) {
 if (!photos.length) return '';
 return `<div class="${cls}">${photos.map((x) => {
  const credit = [x.author, x.license].filter(Boolean).join(' · ');
  return `<figure class="rp-photo"><img src="${photoEsc(x.thumb)}" alt="${photoEsc(x.name)}" decoding="async" referrerpolicy="no-referrer" width="${x.w || 320}" height="${x.h || 213}"><figcaption><strong>${photoEsc(x.name)}</strong><a href="${photoEsc(x.page)}" target="_blank" rel="noopener" title="${photoEsc(credit)} — Wikimedia Commons">${photoEsc(credit)}</a></figcaption></figure>`;
 }).join('')}</div>`;
}

if (typeof window !== 'undefined') { window.routePhotos = routePhotos; Object.assign(routePhotos, {for: photosFor, load: photosLoad, resolve: photosResolve, idFor: photoIdFor, figures: photoFigures, LIMITS: PHOTO}); }
