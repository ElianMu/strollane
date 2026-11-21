'use strict';
/* How well the AI reads a walk request: eval/interpret_cases.jsonl (50 requests, half Chinese) sent to a running
   /api/interpret, each result checked against what the request plainly says. The checks are rules, never another
   model's opinion:

   origin / destination   the place the request names is the one returned (any of the listed spellings)
   high / low             the dimensions the request asks for more / less of are set that way (weight >= 60)
   interests, food, named_stops, end_mode, outing (minutes range)
   clarification          false: the request is clear and must not be answered with a question; true: it must
   unsupported            false: nothing the request asks for is declared impossible
   no_waterfront          the request does not mention water, so no waterfront preference is added
   zh_text                a question or reason shown to a Chinese-interface walker is written in Chinese

   Run against the live API host (12 requests a minute per client, so this takes about 5 minutes):
     node eval/interpret_eval.js                         # https://streetwise-api.onrender.com
     node eval/interpret_eval.js http://127.0.0.1:8080   # a local server.py with OPENAI_API_KEY set
   Results: eval/interpret_results.json. The same checkCase() runs in a browser page (it needs only fetch). */

function lower(x) { return String(x == null ? '' : x).toLowerCase(); }
function anyIn(value, spellings) { const v = lower(value); return spellings.some((s) => v.includes(lower(s))); }

/** Every failed check of one case, as short sentences; [] = passed. */
function checkCase(c, r) {
  const e = c.expect, j = r.journey || {}, fails = [];
  const w = r.weights || {}, d = r.directions || {};
  if (e.origin && !anyIn(j.origin, e.origin)) fails.push(`origin ${JSON.stringify(j.origin)}, expected ${e.origin[0]}`);
  if (e.destination && !anyIn(j.destination, e.destination)) fails.push(`destination ${JSON.stringify(j.destination)}, expected ${e.destination[0]}`);
  for (const k of e.high || []) if (!((w[k] || 0) >= 60 && d[k] !== 'low')) fails.push(`${k} not raised (weight ${w[k] ?? 'unset'}, ${d[k] || 'no direction'})`);
  for (const k of e.low || []) if (d[k] !== 'low') fails.push(`${k} not lowered (${d[k] || 'no direction'})`);
  for (const i of e.interests || []) if (!(j.interests || []).includes(i)) fails.push(`interest ${i} missing (${JSON.stringify(j.interests || [])})`);
  for (const f of e.food || []) {
    const hit = (j.food || []).some((x) => x.category === f.category && (!f.item || anyIn(x.item, [f.item]) || anyIn(x.cuisine, [f.item])));
    if (!hit) fails.push(`food ${f.category}${f.item ? ' / ' + f.item : ''} missing (${JSON.stringify(j.food || [])})`);
  }
  for (const n of e.named_stops || []) if (!(j.named_stops || []).some((s) => anyIn(s.name, n))) fails.push(`stop ${n[0]} missing (${JSON.stringify((j.named_stops || []).map((s) => s.name))})`);
  if (e.end_mode && j.end_mode !== e.end_mode) fails.push(`end_mode ${j.end_mode}, expected ${e.end_mode}`);
  if (e.outing) {
    const m = j.outing_minutes ?? j.walking_minutes ?? r.time_minutes;
    if (!(m >= e.outing[0] && m <= e.outing[1])) fails.push(`time ${m ?? 'unset'} min, expected ${e.outing[0]}–${e.outing[1]}`);
  }
  if (e.clarification === false && r.clarification) fails.push(`asked "${r.clarification}" instead of planning`);
  if (e.clarification === true && !r.clarification) fails.push('planned an unclear request instead of asking');
  if (e.unsupported === false && (r.unsupported || []).length) fails.push(`declared unsupported: ${(r.unsupported || []).map((u) => u.request).join('; ')}`);
  if (e.no_waterfront && r.waterfront && r.waterfront.mode === 'set') fails.push(`added a waterfront preference nobody asked for (weight ${r.waterfront.weight})`);
  if (e.zh_text) {
    const text = [r.clarification, ...(r.unsupported || []).map((u) => u.reason)].filter(Boolean).join(' ');
    if (text && !/[一-鿿]/.test(text)) fails.push(`shown in English to a Chinese-interface walker: "${text.slice(0, 60)}"`);
  }
  return fails;
}

async function runCase(base, c) {
  const body = {message: c.message, ...(c.reply_language ? {reply_language: c.reply_language} : {})};
  const res = await fetch(base.replace(/\/$/, '') + '/api/interpret', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const r = await res.json().catch(() => ({}));
  if (!res.ok) return {id: c.id, lang: c.lang, message: c.message, status: res.status, fails: [`HTTP ${res.status}: ${r.error || ''}`.trim()], result: r};
  return {id: c.id, lang: c.lang, message: c.message, status: res.status, fails: checkCase(c, r), result: r};
}

function summary(rows) {
  const by = (pred) => { const x = rows.filter(pred); return {cases: x.length, passed: x.filter((r) => !r.fails.length).length}; };
  return {all: by(() => true), english: by((r) => r.lang === 'en' && !r.id.startsWith('zh')), chinese_interface: by((r) => r.id.startsWith('zh'))};
}

if (typeof module !== 'undefined' && require.main === module) {
  const fs = require('fs'), path = require('path');
  const base = process.argv[2] || 'https://streetwise-api.onrender.com';
  const cases = fs.readFileSync(path.join(__dirname, 'interpret_cases.jsonl'), 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));
  (async () => {
    const rows = [];
    for (const c of cases) {
      rows.push(await runCase(base, c));
      const r = rows.at(-1);
      console.log(`${r.fails.length ? 'FAIL' : 'ok  '} ${c.id} ${c.message}${r.fails.length ? '\n     ' + r.fails.join('\n     ') : ''}`);
      await new Promise((ok) => setTimeout(ok, 5500)); // the API allows 12 interpretations a minute per client
    }
    const out = {base, run_at: new Date().toISOString(), summary: summary(rows), cases: rows};
    fs.writeFileSync(path.join(__dirname, 'interpret_results.json'), JSON.stringify(out, null, 1));
    console.log(JSON.stringify(out.summary));
  })();
}
if (typeof module !== 'undefined') module.exports = {checkCase, runCase, summary};
