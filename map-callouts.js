'use strict';
/* Photo callouts on the map: real photos of the places the selected walk passes, drawn beside the route and tied to
   each place by a leader line.

   Places: on a City Walk, its stops (numbered as on the map); otherwise the named places within reach of the route
   (route-story.js storyPlacesNear), best known first. Photos: route-photos.js only (Wikimedia Commons through the
   place's own Wikidata entry, with author and licence); a place without a usable photo gets no callout. The caption
   line is the place's own data: the stop's purpose and category, or the place's Wikidata description.

   Layout: each card is tried at 8 positions around its place and takes the one that stays inside the free part of
   the map, does not cover other cards or the route line, and lies on the far side of the route; places are laid out
   in order of importance, and a place with no free position gets no card. Cards follow the map while it moves and
   are laid out again when it stops. Phones show at most 2 smaller cards, above the routes sheet. */
const CALLOUT = {MAX: 4, MAX_PHONE: 2, W: 132, W_PHONE: 108, GAP: 64, MIN_ZOOM: 12.5, PAD: 10};
const mapCallouts = {on: true, items: [], root: null, svg: null, raf: 0, key: ''};

function calloutEsc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }
function calloutPhone() { return typeof window !== 'undefined' && window.matchMedia?.('(max-width:740px)').matches; }

/** The places to show, in walking order, each {key, lat, lon, name, seq, note, wd}. */
function calloutPlaces() {
 if (typeof state === 'undefined') return [];
 const plan = typeof journey !== 'undefined' ? journey.plan : null;
 if (plan?.stops?.length) {
  return plan.stops.filter((s) => s.role !== 'end' && s.lat != null).map((s) => {
   const p = (typeof placeCache !== 'undefined' && placeCache[s.id]) || {};
   return {key: s.id, id: s.id, lat: s.lat, lon: s.lon, name: s.name, seq: s.seq, wd: p.wd || p.wikidata || s.wd || null, rank: s.seq,
    note: [s.slot_label ? `for “${s.slot_label}”` : '', s.category].filter(Boolean).join(' · ')};
  });
 }
 const r = state.routes.find((x) => x.id === state.activeRoute)?.raw;
 if (!r || typeof routePhotoPlaces !== 'function') return [];
 return routePhotoPlaces(r).map((p, i) => ({key: p.id || p.wd, id: p.id || p.wd, lat: p.lat, lon: p.lon, name: p.name, wd: p.wd || null, rank: i,
  note: p.wdesc ? p.wdesc.replace(/ in (Manhattan|Brooklyn|Queens|New York City|New York)(, [^,]+)*$/i, '') : ''}));
}

/** Where one card goes: 8 positions around its place (two distances), inside `box`, clear of the cards already
    placed and of the other places, covering as little of the route as possible, preferably on the far side of the
    route from its middle. Returns {x,y,w,h} or null when there is no free position. */
function calloutPlace(a, others, route, box, w, h, gap, placed, prev) {
 const dirs = [[1, 0], [-1, 0], [0, -1], [0, 1], [1, -1], [-1, -1], [1, 1], [-1, 1]];
 const mid = route.length ? {x: route.reduce((s, p) => s + p.x, 0) / route.length, y: route.reduce((s, p) => s + p.y, 0) / route.length} : a;
 const hit = (r, p) => r.x < p.x + p.w + 6 && p.x < r.x + r.w + 6 && r.y < p.y + p.h + 6 && p.y < r.y + r.h + 6;
 let best = null;
 // keep the card where it was if that spot is still free: cards should not jump after every pan
 if (prev) {
  const r = {x: a.x + prev.dx, y: a.y + prev.dy, w, h};
  const ok = r.x >= box.x0 && r.y >= box.y0 && r.x + w <= box.x1 && r.y + h <= box.y1 && !placed.some((p) => hit(r, p)) &&
   !others.some((o) => o.x > r.x - 4 && o.x < r.x + w + 4 && o.y > r.y - 4 && o.y < r.y + h + 4) &&
   !route.some((p) => p.x > r.x + 2 && p.x < r.x + w - 2 && p.y > r.y + 2 && p.y < r.y + h - 2);
  if (ok) return r;
 }
 for (const g of [gap, gap * 1.6, gap * 2.4]) for (const [dx, dy] of dirs) for (const slide of (dx === 0 ? [0.5, 0.12, 0.88] : [0.5])) {
  const n = Math.hypot(dx, dy), ox = dx / n * g, oy = dy / n * g;
  // above / below a place the card may also sit left- or right-aligned, not only centred
  const r = {x: a.x + ox - (dx < 0 ? w : dx > 0 ? 0 : w * slide), y: a.y + oy - (dy < 0 ? h : dy > 0 ? 0 : h / 2), w, h};
  if (r.x < box.x0 || r.y < box.y0 || r.x + w > box.x1 || r.y + h > box.y1) continue;
  if (placed.some((p) => hit(r, p))) continue;
  if (others.some((o) => o.x > r.x - 4 && o.x < r.x + w + 4 && o.y > r.y - 4 && o.y < r.y + h + 4)) continue;
  const onRoute = route.filter((p) => p.x > r.x - 3 && p.x < r.x + w + 3 && p.y > r.y - 3 && p.y < r.y + h + 3).length;
  const toward = (r.x + w / 2 - a.x) * (a.x - mid.x) + (r.y + h / 2 - a.y) * (a.y - mid.y) < 0 ? 1 : 0;
  const score = onRoute * 10 + toward * 3 + (g / gap - 1) * 3 + (dx && dy ? 0.5 : 0) + (slide !== 0.5 ? 0.3 : 0);
  if (!best || score < best.score) best = {r, score};
 }
 return best ? best.r : null;
}

/** Place the cards greedily, most important first; if some place gets no card, try again with the places that
    failed laid out first, and keep the arrangement that shows the most cards (then the most important ones). */
function calloutArrange(order, route, box, gap, max) {
 const run = (seq) => {
  const placed = [...box.obstacles], out = [];
  for (const o of seq) {
   if (out.length >= max) break;
   const rect = calloutPlace(o.a, order.filter((x) => x !== o).map((x) => x.a), route, box, o.w, o.h, gap, placed, o.prev);
   if (rect) { placed.push(rect); out.push({o, rect}); }
  }
  return out;
 };
 const want = order.slice(0, max);
 let best = run(order);
 const missed = want.filter((o) => !best.some((p) => p.o === o));
 for (const m of missed) {
  const alt = run([m, ...want.filter((o) => o !== m), ...order.slice(max)]);
  const rankSum = (r) => r.reduce((s, p) => s + p.o.it.rank, 0);
  if (alt.length > best.length || (alt.length === best.length && rankSum(alt) < rankSum(best))) best = alt;
 }
 return best;
}

/** The free part of the map: below the floating controls, above the phone routes sheet. */
function calloutBox(map) {
 const el = map.getContainer(), rect = el.getBoundingClientRect(), b = {x0: CALLOUT.PAD, y0: CALLOUT.PAD, x1: rect.width - CALLOUT.PAD, y1: rect.height - 34};
 const cover = (sel) => { const n = document.querySelector(sel); if (!n || n.offsetParent === null) return null; const r = n.getBoundingClientRect(); return r.width && r.height ? r : null; };
 if (calloutPhone()) {
  const top = cover('#mComposer'); if (top) b.y0 = Math.max(b.y0, top.bottom - rect.top + 8);
  const sheet = cover('#rightPanel'); if (sheet) b.y1 = Math.min(b.y1, sheet.top - rect.top - 8);
  b.x1 = Math.min(b.x1, rect.width - 60); // keep clear of the map buttons on the right
 } else {
  const tools = cover('.map-actions'); if (tools) b.x1 = Math.min(b.x1, tools.left - rect.left - 8);
 }
 // floating map panels (legend, layer controls, weather, explore) are obstacles, like placed cards
 b.obstacles = ['.map-legend', '.ud-legend', '.map-layer-switch', '.map-mode-control', '.wx-panel', '.explore-panel', '.map-top-left', '#selectedRouteSummary', '.nav-overlay']
  .map(cover).filter(Boolean).map((r) => ({x: r.left - rect.left, y: r.top - rect.top, w: r.width, h: r.height}));
 return b;
}

function calloutCard(it, w) {
 const p = it.photo, credit = p.kind === 'street' ? ['Street view here', p.date, p.author, 'Mapillary'].filter(Boolean).join(' · ') : [p.author, p.license].filter(Boolean).join(' · ');
 const ih = Math.round(w * 0.62);
 return `<figure class="map-callout" data-key="${calloutEsc(it.key)}" style="width:${w}px"><img src="${calloutEsc(p.thumb)}" alt="${calloutEsc(it.name)}" style="height:${ih}px" decoding="async" referrerpolicy="no-referrer"><figcaption>${it.seq != null ? `<span class="mc-seq">${calloutEsc(it.seq)}</span>` : ''}<strong>${calloutEsc(it.name)}</strong>${it.note ? `<small>${calloutEsc(it.note)}</small>` : ''}<a href="${calloutEsc(p.page)}" target="_blank" rel="noopener" title="${calloutEsc(credit)} — Wikimedia Commons">${calloutEsc(credit)}</a></figcaption></figure>`;
}

function calloutsEnsureRoot(map) {
 if (mapCallouts.root && mapCallouts.root.isConnected) return mapCallouts.root;
 const root = document.createElement('div'); root.className = 'map-callouts'; root.setAttribute('aria-label', 'Photos of places along this walk');
 root.innerHTML = '<svg class="mc-lines" aria-hidden="true"></svg><div class="mc-cards"></div>';
 map.getContainer().appendChild(root);
 mapCallouts.root = root; mapCallouts.svg = root.querySelector('svg');
 map.on('move', () => { if (!mapCallouts.raf) mapCallouts.raf = requestAnimationFrame(() => { mapCallouts.raf = 0; calloutsFollow(); }); });
 map.on('moveend', () => calloutsLayout());
 window.addEventListener('resize', () => calloutsLayout());
 return root;
}

/** Rebuild the cards for the selected walk (call after route, stop or photo changes). */
function calloutsRefresh() {
 const map = typeof state !== 'undefined' ? state.map : null;
 if (!map || typeof map.project !== 'function' || typeof placePhoto !== 'function') return;
 const root = calloutsEnsureRoot(map), places = calloutPlaces();
 placePhotosEnsure(places, () => calloutsRefresh());
 // a street view only stands in for a City Walk stop (a stop the walk is built around); along an ordinary route
 // only real photos of the places themselves are drawn
 const withPhoto = places.map((p) => { const ph = placePhoto(p); return ph && (ph.kind !== 'street' || p.seq != null) ? {...p, photo: ph} : null; }).filter(Boolean);
 const key = withPhoto.map((p) => p.key + p.photo.thumb).join('|') + (calloutPhone() ? 'm' : 'd');
 if (key !== mapCallouts.key) {
  mapCallouts.key = key; mapCallouts.items = withPhoto;
  const w = calloutPhone() ? CALLOUT.W_PHONE : CALLOUT.W;
  root.querySelector('.mc-cards').innerHTML = withPhoto.map((it) => calloutCard(it, w)).join('');
  root.querySelectorAll('.map-callout').forEach((el) => el.addEventListener('click', (e) => {
   if (e.target.closest('a')) return;
   const it = mapCallouts.items.find((x) => x.key === el.dataset.key); if (it) map.easeTo({center: [it.lon, it.lat], zoom: Math.max(map.getZoom(), 16), duration: 500});
  }));
  root.querySelectorAll('.map-callout img').forEach((img) => img.addEventListener('load', () => calloutsLayout(), {once: true}));
 }
 calloutsLayout();
}

function calloutsVisible(map) {
 return mapCallouts.on && !document.body.classList.contains('nav-mode') && mapCallouts.items.length && map.getZoom() >= CALLOUT.MIN_ZOOM;
}

/** Choose where each card goes for the current view. */
function calloutsLayout() {
 const map = typeof state !== 'undefined' ? state.map : null, root = mapCallouts.root;
 if (!map || !root) return;
 root.classList.toggle('hidden', !calloutsVisible(map));
 if (root.classList.contains('hidden')) return;
 const phone = calloutPhone(), max = phone ? CALLOUT.MAX_PHONE : CALLOUT.MAX, box = calloutBox(map);
 const r = state.routes.find((x) => x.id === state.activeRoute)?.raw, coords = r?.geometry?.coordinates || [];
 const step = Math.max(1, Math.floor(coords.length / 400));
 const route = coords.filter((_, i) => i % step === 0).map((c) => map.project(c));
 const els = [...root.querySelectorAll('.map-callout')];
 // most important first (stop order on a City Walk; best-known places otherwise), only places in view
 const order = mapCallouts.items.map((it, i) => ({it, el: els[i], a: map.project([it.lon, it.lat])}))
  .filter((o) => o.el && o.a.x > box.x0 && o.a.x < box.x1 && o.a.y > box.y0 && o.a.y < box.y1)
  .sort((a, b) => a.it.rank - b.it.rank);
 order.forEach((o) => { o.prev = o.el.dataset.dx !== '' && o.el.dataset.dx != null && o.el.style.display !== 'none' ? {dx: Number(o.el.dataset.dx), dy: Number(o.el.dataset.dy)} : null; });
 els.forEach((el) => { el.style.display = 'none'; el.dataset.dx = ''; });
 const gap = phone ? CALLOUT.GAP * 0.75 : CALLOUT.GAP;
 order.forEach((o) => { o.el.style.display = ''; o.w = o.el.offsetWidth; o.h = o.el.offsetHeight; o.el.style.display = 'none'; });
 const pick = calloutArrange(order, route, box, gap, max);
 for (const {o, rect} of pick) { o.el.style.display = ''; o.el.dataset.dx = rect.x - o.a.x; o.el.dataset.dy = rect.y - o.a.y; }
 calloutsFollow();
}

/** Keep cards and leader lines attached to their places while the map moves. */
function calloutsFollow() {
 const map = typeof state !== 'undefined' ? state.map : null, root = mapCallouts.root;
 if (!map || !root || root.classList.contains('hidden')) return;
 const lines = [];
 root.querySelectorAll('.map-callout').forEach((el, i) => {
  if (el.style.display === 'none' || el.dataset.dx === '') return;
  const it = mapCallouts.items[i]; if (!it) return;
  const a = map.project([it.lon, it.lat]), x = a.x + Number(el.dataset.dx), y = a.y + Number(el.dataset.dy), w = el.offsetWidth, h = el.offsetHeight;
  el.style.transform = `translate(${Math.round(x)}px,${Math.round(y)}px)`;
  // the line meets the card at the nearest point of its edge
  const ex = Math.max(x, Math.min(a.x, x + w)), ey = Math.max(y, Math.min(a.y, y + h));
  // start the line at a ring around the place, so the place's own map marker (a stop number) stays visible
  const L = Math.hypot(ex - a.x, ey - a.y) || 1, R = it.seq != null ? 13 : 6, sx = a.x + (ex - a.x) / L * R, sy = a.y + (ey - a.y) / L * R;
  const seg = `x1="${sx.toFixed(1)}" y1="${sy.toFixed(1)}" x2="${ex.toFixed(1)}" y2="${ey.toFixed(1)}"`;
  lines.push(`<line class="halo" ${seg}/><line ${seg}/><circle cx="${a.x.toFixed(1)}" cy="${a.y.toFixed(1)}" r="${R}"/>`);
 });
 mapCallouts.svg.innerHTML = lines.join('');
}

function calloutsToggle(on) {
 mapCallouts.on = on ?? !mapCallouts.on;
 document.getElementById('mapPhotosToggle')?.setAttribute('aria-pressed', String(mapCallouts.on));
 calloutsLayout();
}

if (typeof window !== 'undefined') {
 window.mapCallouts = mapCallouts;
 document.getElementById('mapPhotosToggle')?.addEventListener('click', () => calloutsToggle());
 // nav mode hides them; leaving it shows them again
 new MutationObserver(() => calloutsLayout()).observe(document.body, {attributes: true, attributeFilter: ['class']});
}
if (typeof module !== 'undefined' && module.exports) module.exports = {calloutPlace, calloutArrange};
