'use strict';
/* Walk priorities: one row of the 12 experience dimensions a visitor can pick without typing.

   A pill is NOT a new dimension, score or route. Tapping one does exactly what the quick-preference chips do: it sets
   that existing dimension to importance 80 (direction high), or back to "not expressed" when tapped again. Several can
   be on at once. Names, definitions and weights of the 12 dimensions are untouched; sliders, chips and the "describe
   your walk" box stay in sync because all of them read planner state.

   The request box then shows the choice in words. "Create My Walk" / "Plan My Walk" stays the only start button; when
   the box holds exactly that generated sentence, planning uses the app's existing manual path (no AI interpretation
   call), so the weights planned with are exactly the ones the pills set.

   Order = mean gain on the requested dimension in the route benchmark, strongest first
   (benchmarks/ROUTE_BENCHMARK.md, "By dimension"; tests/test_route_benchmark.py fails if the two drift apart).
   Each pill's tooltip names the indicators its score is built from, read from data/pedestrian/score-indicators.json
   (the router's real definitions, loaded by route-client.js); nothing about the data is hard-coded here. */

const WALK_PRESET_ORDER = ['Spatial Comfort', 'Access & Safety', 'Nature', 'Quiet & Relax', 'Transit Connectivity', 'Architecture',
 'Walkability', 'Food & Retail', 'Culture', 'Environment', 'Urban Vibrancy', 'Scenic & Visual'];
const WALK_PRESET_WEIGHT = 80; // same as mobile-ui.js QUICK_WEIGHT
const WALK_REQUEST_PREFIX = 'Prioritise: ';
const walkPresets = {lastRequest: ''};

function walkPresetDims() { return typeof DIMENSIONS === 'undefined' ? [] : WALK_PRESET_ORDER.filter((n) => DIMENSIONS.some((d) => d.name === n)); }
function walkPresetOn(dim) { return typeof planner !== 'undefined' && planner.origins[dim] !== 'default' && planner.weights[dim] >= 70 && planner.directions[dim] !== 'low'; }
function walkPresetLabel(dim) { return typeof dimLabel === 'function' ? dimLabel(dim) : dim; }
/** Scored indicators behind a dimension, from the router's definitions file (empty until it has loaded). */
function walkPresetBasis(dim) {
 const doc = typeof scoreBasis !== 'undefined' ? scoreBasis.doc : null;
 return doc?.dimensions?.[dim] ? doc.dimensions[dim].filter((i) => i.role === 'up' || i.role === 'down').map((i) => i.label) : [];
}
/** The choice in words, in the pills' order; '' when nothing is chosen. */
function walkPresetRequest() {
 const on = walkPresetDims().filter(walkPresetOn);
 return on.length ? WALK_REQUEST_PREFIX + on.map(walkPresetLabel).join(', ') + '.' : '';
}
/** True when `text` is exactly the sentence the pills generated for the current choice (so no AI call is needed). */
function isWalkPresetRequest(text) { const t = (text || '').trim(); return Boolean(t) && t === walkPresetRequest(); }
/** Write the choice into the request box — only if the box is empty, still holds the sample sentence, or holds an
    earlier generated sentence. Words the visitor typed themselves are never overwritten. */
function syncWalkPresetRequest() {
 const box = document.getElementById('intentText'); if (!box) return;
 const cur = box.value.trim(), next = walkPresetRequest();
 const replaceable = !cur || cur === walkPresets.lastRequest || cur === (box.defaultValue || '').trim() || cur.startsWith(WALK_REQUEST_PREFIX);
 if (!replaceable) return;
 box.value = next; walkPresets.lastRequest = next;
 box.dispatchEvent(new Event('input', {bubbles: true}));
 if (typeof window.strollaneMarkSubmitted === 'function') window.strollaneMarkSubmitted(next); // phone: not an "unsent request"
}
function toggleWalkPreset(dim) {
 if (typeof planner === 'undefined' || !walkPresetDims().includes(dim)) return false;
 const on = !walkPresetOn(dim);
 planner.weights[dim] = on ? WALK_PRESET_WEIGHT : 50;
 planner.origins[dim] = on ? 'manual' : 'default';
 planner.directions[dim] = 'high';
 if (typeof renderPreferenceSummary === 'function') renderPreferenceSummary();
 if (typeof renderDimensions === 'function') renderDimensions();
 if (typeof window.strollaneRenderChips === 'function') window.strollaneRenderChips();
 syncWalkPresetRequest();
 renderWalkPresets();
 // with a walk already on screen this is the same as moving that dimension's slider
 if (typeof state !== 'undefined' && state.routes.length && typeof queueMapReplan === 'function') queueMapReplan();
 return on;
}
/** Desktop "Plan My Walk" when the box holds the pills' own sentence: handlePlan() without the interpretation call. */
async function planFromWalkPresets() {
 if (state.routingBusy || planner.parsing) return;
 for (const kind of ['start', 'end']) {
  if (kind === 'end' && typeof journey !== 'undefined' && journey.endMode !== 'fixed') continue;
  const typed = document.getElementById(kind === 'start' ? 'searchStart' : 'searchEnd').value.trim(), chosen = getPlace(kind);
  if (typed !== (chosen?.name || '')) { toast(`Search and choose a ${kind === 'start' ? 'starting point' : 'destination'} result first, or clear the box.`); return; }
 }
 const on = walkPresetDims().filter(walkPresetOn);
 appendChat('user', walkPresetRequest());
 appendChat('assistant', `Your priorities: ${on.map((d) => `${walkPresetLabel(d)} ${planner.weights[d]}`).join(' · ')}. Checking feasible pedestrian paths…`);
 const problem = await ensurePlanStart();
 if (problem) { document.getElementById('rankingStatus').textContent = problem; appendChat('assistant', problem + ' The displayed previous route has not been recalculated.'); return; }
 const rec = typeof prepareRecommendedWalk === 'function' ? prepareRecommendedWalk('') : null;
 if (rec) appendChat('assistant', rec);
 if (typeof journeyMode === 'function' && journeyMode()) await planJourney(false); else await generateRoutes(null, false);
}
function renderWalkPresets() {
 for (const root of document.querySelectorAll('[data-walk-presets]')) {
  const scroll = root.scrollLeft;
  root.textContent = '';
  for (const dim of walkPresetDims()) {
   const b = document.createElement('button'); b.type = 'button'; b.className = 'walk-pill'; b.dataset.dim = dim;
   b.textContent = walkPresetLabel(dim);
   b.setAttribute('aria-pressed', String(walkPresetOn(dim)));
   const basis = walkPresetBasis(dim);
   b.title = `Sets ${dim} to ${WALK_PRESET_WEIGHT}.` + (basis.length ? ` Based on: ${basis.join(' · ')}.` : '');
   b.addEventListener('click', () => toggleWalkPreset(dim));
   root.appendChild(b);
  }
  root.scrollLeft = scroll;
  root.classList.toggle('hidden', !root.children.length);
 }
}
if (typeof window !== 'undefined') {
 Object.assign(window, {WALK_PRESET_ORDER, walkPresets, walkPresetRequest, isWalkPresetRequest, toggleWalkPreset, planFromWalkPresets, renderWalkPresets});
 const boot = () => { renderWalkPresets(); if (typeof loadScoreBasis === 'function') loadScoreBasis().then((d) => { if (d) renderWalkPresets(); }); };
 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else setTimeout(boot, 0);
}
