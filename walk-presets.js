'use strict';
/* Walk presets: ready-made city-walk experiences a visitor can start without typing.

   A preset is NOT a new dimension, score or route. It sets one of the existing 12 experience dimensions to the same
   importance the quick-preference chips use (80, direction high) and then runs the app's existing manual planning
   path (no AI interpretation call). Dimension names, definitions and weights are untouched; the fine-tune sliders,
   chips and the "describe your walk" box keep working and stay in sync, because all of them read planner state.

   Only presets the router's data supports are offered (see benchmarks/ROUTE_BENCHMARK.md and METHODOLOGY.md):
     Green Walk  → Nature          (street-tree density, share beside parkland)
     Quiet Walk  → Quiet & Relax   (311 noise-complaint intensity, roadway width — proxies, not measured sound)
   "Scenic" is deliberately not a preset: the Scenic & Visual score measures nearness to mapped viewpoints, public art,
   fountains and memorials, not whether a street looks nice.

   The "Based on" line is read from data/pedestrian/score-indicators.json (the router's real indicator definitions,
   loaded by route-client.js) and is shown only when that file is available; nothing is hard-coded about the data. */

const WALK_PRESETS = [
 {key: 'green', title: 'Green Walk', dim: 'Nature', blurb: 'Streets with more trees and park edges.',
  request: 'Green Walk: streets with more trees and park edges.'},
 {key: 'quiet', title: 'Quiet Walk', dim: 'Quiet & Relax', blurb: 'Narrower streets with fewer noise complaints.',
  request: 'Quiet Walk: narrower streets with fewer noise complaints.'},
];
const WALK_PRESET_WEIGHT = 80; // same as mobile-ui.js QUICK_WEIGHT
const walkPresets = {active: null, busy: false};

function presetAvailable(p) { return typeof DIMENSIONS !== 'undefined' && DIMENSIONS.some((d) => d.name === p.dim); }
function presetIsOn(p) { return typeof planner !== 'undefined' && planner.origins[p.dim] !== 'default' && planner.weights[p.dim] >= 70 && planner.directions[p.dim] !== 'low'; }
/** Scored indicators behind the preset's dimension, from the router's definitions file (empty until it has loaded). */
function presetBasis(p) {
 const doc = typeof scoreBasis !== 'undefined' ? scoreBasis.doc : null;
 return doc?.dimensions?.[p.dim] ? doc.dimensions[p.dim].filter((i) => i.role === 'up' || i.role === 'down').map((i) => i.label) : [];
}
function setPresetDimension(dim, on) {
 planner.weights[dim] = on ? WALK_PRESET_WEIGHT : 50;
 planner.origins[dim] = on ? 'manual' : 'default';
 planner.directions[dim] = 'high';
}
/** Choose a preset: its dimension goes to 80; the previously chosen preset's dimension returns to "not expressed"
    (only if it is still exactly what the preset set — a slider the user moved since is left alone). */
function applyWalkPreset(key) {
 const p = WALK_PRESETS.find((x) => x.key === key);
 if (!p || !presetAvailable(p) || typeof planner === 'undefined') return null;
 const prev = WALK_PRESETS.find((x) => x.key === walkPresets.active);
 if (prev && prev !== p && planner.origins[prev.dim] === 'manual' && planner.weights[prev.dim] === WALK_PRESET_WEIGHT) setPresetDimension(prev.dim, false);
 setPresetDimension(p.dim, true);
 walkPresets.active = p.key;
 if (typeof renderPreferenceSummary === 'function') renderPreferenceSummary();
 if (typeof renderDimensions === 'function') renderDimensions();
 if (typeof window.strollaneRenderChips === 'function') window.strollaneRenderChips();
 renderWalkPresets();
 return p;
}
/** Start the chosen preset through the existing manual planning path: same validation, same routing calls, no AI call. */
async function startWalkPreset(key) {
 if (walkPresets.busy || (typeof state !== 'undefined' && state.routingBusy) || (typeof planner !== 'undefined' && planner.parsing)) return;
 const p = applyWalkPreset(key);
 if (!p) return;
 // The request box shows what was asked, in words, so the walk on screen is never labelled with an unrelated sentence.
 const box = document.getElementById('intentText'); if (box) { box.value = p.request; box.dispatchEvent(new Event('input', {bubbles: true})); }
 walkPresets.busy = true; renderWalkPresets();
 try {
  if (typeof window.strollanePlanFromPrefs === 'function' && window.strollanePlanFromPrefs(p.request)) return; // phone layout
  // desktop: the same steps as handlePlan() after interpretation
  for (const kind of ['start', 'end']) {
   if (kind === 'end' && typeof journey !== 'undefined' && journey.endMode !== 'fixed') continue;
   const typed = document.getElementById(kind === 'start' ? 'searchStart' : 'searchEnd').value.trim(), chosen = getPlace(kind);
   if (typed !== (chosen?.name || '')) { toast(`Search and choose a ${kind === 'start' ? 'starting point' : 'destination'} result first, or clear the box.`); return; }
  }
  appendChat('user', p.request);
  appendChat('assistant', `${p.title}: ${dimLabel(p.dim)} set to ${WALK_PRESET_WEIGHT}. Checking feasible pedestrian paths…`);
  const problem = await ensurePlanStart();
  if (problem) { document.getElementById('rankingStatus').textContent = problem; appendChat('assistant', problem + ' The displayed previous route has not been recalculated.'); return; }
  const rec = typeof prepareRecommendedWalk === 'function' ? prepareRecommendedWalk('') : null;
  if (rec) appendChat('assistant', rec);
  if (typeof journeyMode === 'function' && journeyMode()) await planJourney(false); else await generateRoutes(null, false);
 } finally { walkPresets.busy = false; renderWalkPresets(); }
}
function renderWalkPresets() {
 for (const root of document.querySelectorAll('[data-walk-presets]')) {
  root.textContent = '';
  for (const p of WALK_PRESETS) {
   if (!presetAvailable(p)) continue; // registry check: never offer a dimension that does not exist
   const b = document.createElement('button'); b.type = 'button'; b.className = 'walk-preset'; b.dataset.preset = p.key;
   b.setAttribute('aria-pressed', String(walkPresets.active === p.key && presetIsOn(p)));
   b.disabled = walkPresets.busy;
   const t = document.createElement('strong'); t.textContent = p.title;
   const d = document.createElement('span'); d.className = 'walk-preset-blurb'; d.textContent = p.blurb;
   b.append(t, d);
   const basis = presetBasis(p);
   if (basis.length) { const m = document.createElement('small'); m.textContent = 'Based on: ' + basis.join(' · '); b.appendChild(m); }
   const go = document.createElement('span'); go.className = 'walk-preset-go'; go.setAttribute('aria-hidden', 'true'); go.textContent = '→';
   b.appendChild(go);
   b.setAttribute('aria-label', `${p.title}. ${p.blurb}${basis.length ? ' Based on: ' + basis.join(', ') + '.' : ''} Plan this walk.`);
   b.addEventListener('click', () => startWalkPreset(p.key));
   root.appendChild(b);
  }
  root.classList.toggle('hidden', !root.children.length);
 }
}
if (typeof window !== 'undefined') {
 Object.assign(window, {WALK_PRESETS, walkPresets, applyWalkPreset, startWalkPreset, renderWalkPresets});
 const boot = () => { renderWalkPresets(); if (typeof loadScoreBasis === 'function') loadScoreBasis().then((d) => { if (d) renderWalkPresets(); }); };
 if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else setTimeout(boot, 0);
}
