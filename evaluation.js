'use strict';
/* Evaluation dashboard (evaluation.html): renders GET /api/evaluation, which routing/walkcheck.py computes from stored
   walk feedback alone. No numbers are made up here: with no answers the page says so and draws nothing. */
const RATING_LABEL = {overall: ['Overall satisfaction', '整体满意度'], match: ['Match with the request', '偏好匹配度'],
  quiet: ['Quiet', '安静程度'], green: ['Greenery', '绿化体验']};
const TYPE_LABEL = {tourist: 'Tourist', 'curious-local': 'Curious Local', leisure: 'Leisure Walker', custom: 'Own priorities'};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const fmt = (v, d = 1) => (v == null ? '—' : Number(v).toFixed(d));
const signed = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(1));

function distribution(counts) {
  const vals = [1, 2, 3, 4, 5].map((k) => counts[String(k)] || 0), max = Math.max(1, ...vals);
  return `<div class="dist">${vals.map((v) => `<div style="height:${Math.round(v / max * 100)}%" title="${v}"><span>${v}</span></div>`).join('')}</div>
    <div class="dist-axis">${[1, 2, 3, 4, 5].map((k) => `<span>${k}</span>`).join('')}</div>`;
}

/** Predicted score (0–100) on x against the rating (1–5) on y, with the linear mapping (r − 1) × 25 as a dashed guide. */
function scatter(label, c) {
  const W = 320, H = 222, L = 34, B = 38, T = 10, R = 10, x = (p) => L + p / 100 * (W - L - R), y = (r) => H - B - (r - 1) / 4 * (H - B - T);
  const seen = {};
  const dots = c.points.map(([p, r]) => { const k = `${p}|${r}`; const n = (seen[k] = (seen[k] || 0) + 1);
    return `<circle cx="${x(p) + (n - 1) * 4}" cy="${y(r)}" r="4" fill="#3b6e4f" fill-opacity=".75"><title>predicted ${p}, rated ${r}</title></circle>`; }).join('');
  const grid = [1, 2, 3, 4, 5].map((r) => `<line x1="${L}" x2="${W - R}" y1="${y(r)}" y2="${y(r)}" stroke="#ececE8"/><text x="${L - 8}" y="${y(r) + 3}" text-anchor="end">${r}</text>`).join('')
    + [0, 25, 50, 75, 100].map((p) => `<text x="${x(p)}" y="${H - B + 14}" text-anchor="middle">${p}</text>`).join('');
  return `<div class="card"><h3>${esc(label)}</h3><div class="sub">n = ${c.n} · Spearman ρ ${c.spearman == null ? 'not shown below 5 pairs' : fmt(c.spearman, 2)}</div>
    <svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(label)}: predicted score against walker rating">
      ${grid}<line x1="${x(0)}" y1="${y(1)}" x2="${x(100)}" y2="${y(5)}" stroke="#9a9a94" stroke-dasharray="4 4"/>${dots}
      <text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle">predicted score (0–100)</text>
      <text x="10" y="${(H - B) / 2}" transform="rotate(-90 10 ${(H - B) / 2})" text-anchor="middle">rating (1–5)</text></svg>
    <div class="sub">Mean predicted ${fmt(c.mean_predicted)} · mean rating ${fmt(c.mean_rating, 2)} (= ${fmt(c.mean_perceived_0_100)} on 0–100) · mean deviation ${signed(c.mean_deviation)} · mean absolute ${fmt(c.mean_abs_deviation)}</div></div>`;
}

function render(d) {
  const root = document.getElementById('eval');
  const status = !d.enabled
    ? '<div class="status warn">Walk feedback is not switched on for this server yet (no store configured), so no answers can be collected. 服务器尚未开启反馈存储。</div>'
    : d.store_error ? `<div class="status warn">The feedback store did not answer: ${esc(d.store_error)}. Figures below are from the last copy this server holds.</div>` : '';
  if (!d.n) {
    root.innerHTML = `${status}<div class="empty"><strong>No evaluation data yet · 暂无评估数据</strong>
      <p>No walker has sent feedback after a walk yet. Results appear here as soon as the first answer is saved, from the form under “Why this route” → “After your walk”.</p></div>
      ${sourcesAndLimits(d)}`;
    return;
  }
  const r = d.ratings;
  root.innerHTML = `${status}
    <div class="grid">
      <div class="card"><h3>Answers · 样本数</h3><div class="kpi">${d.n}</div><div class="sub">${esc(d.first_at.slice(0, 10))} → ${esc(d.last_at.slice(0, 10))}${d.study_participants ? ` · ${d.study_participants} study participants` : ''}</div></div>
      ${['overall', 'match', 'quiet', 'green'].map((k) => `<div class="card"><h3>${RATING_LABEL[k][0]} · ${RATING_LABEL[k][1]}</h3>
        <div class="kpi">${fmt(r[k].mean, 2)}<small> / 5 · n ${r[k].n}${r[k].missing ? `, ${r[k].missing} missing` : ''}</small></div>${r[k].n ? distribution(r[k].counts) : '<div class="sub">No answers yet.</div>'}</div>`).join('')}
    </div>
    <section><h2>Predicted vs experienced · 预测与实际感受</h2>
      <p class="sub">Each dot is one answer: the score the system predicted for the walked route (x, recomputed by the server) against the walker's rating (y). The dashed line is the linear mapping rating = 1 + score / 25; dots above it felt better than predicted, below it worse. “Match” compares with the mean predicted score of the dimensions the walker asked for.</p>
      ${Object.keys(d.comparison).length ? `<div class="scatters">${Object.entries(d.comparison).map(([k, c]) => scatter(k, c)).join('')}</div>
      <table style="margin-top:14px"><thead><tr><th>Dimension</th><th class="num">n</th><th class="num">Mean predicted (0–100)</th><th class="num">Mean rating (1–5)</th><th class="num">Rating on 0–100</th><th class="num">Mean deviation</th><th class="num">Mean |deviation|</th><th class="num">Spearman ρ</th></tr></thead><tbody>
      ${Object.entries(d.comparison).map(([k, c]) => `<tr><td>${esc(k)}</td><td class="num">${c.n}</td><td class="num">${fmt(c.mean_predicted)}</td><td class="num">${fmt(c.mean_rating, 2)}</td><td class="num">${fmt(c.mean_perceived_0_100)}</td><td class="num">${signed(c.mean_deviation)}</td><td class="num">${fmt(c.mean_abs_deviation)}</td><td class="num">${c.spearman == null ? '—' : fmt(c.spearman, 2)}</td></tr>`).join('')}
      </tbody></table>` : '<div class="status">No answer can be compared yet: the walked routes could not be verified, or no dimension was rated.</div>'}
    </section>
    <section><h2>By user type · 按用户类型</h2>
      <table><thead><tr><th>Type</th><th class="num">n</th><th class="num">Overall</th><th class="num">Match</th><th class="num">Quiet</th><th class="num">Greenery</th></tr></thead><tbody>
      ${Object.entries(d.by_user_type).map(([t, x]) => `<tr><td>${esc(TYPE_LABEL[t] || t)}</td><td class="num">${x.n}</td><td class="num">${fmt(x.mean_overall, 2)}</td><td class="num">${fmt(x.mean_match, 2)}</td><td class="num">${fmt(x.mean_quiet, 2)}</td><td class="num">${fmt(x.mean_green, 2)}</td></tr>`).join('')}
      </tbody></table></section>
    <section><h2>Dimension ratings · 各维度反馈</h2>
      <table><thead><tr><th>Dimension</th><th class="num">Ratings</th><th class="num">Mean (1–5)</th></tr></thead><tbody>
      ${Object.entries(d.dimension_ratings).map(([k, x]) => `<tr><td>${esc(k)}</td><td class="num">${x.n}</td><td class="num">${fmt(x.mean, 2)}</td></tr>`).join('') || '<tr><td colspan="3">No dimension rated yet.</td></tr>'}
      </tbody></table></section>
    <section><h2>Detours and comparisons · 绕路与对比</h2>
      <table><tbody>
        <tr><td>Extra distance worth it</td><td class="num">yes ${d.worth_detour.yes} · no ${d.worth_detour.no} · no detour ${d.worth_detour['no-detour']}</td></tr>
        <tr><td>Walk-along: which of two walks fitted better</td><td class="num">recommended ${d.compared_with_shortest.this} · shortest ${d.compared_with_shortest.shortest} · no difference ${d.compared_with_shortest.same}</td></tr>
        <tr><td>Answers with a comment (comments are read in the data, not shown here)</td><td class="num">${d.comments}</td></tr>
      </tbody></table></section>
    <section><h2>Missing values · 缺失值</h2>
      <table><tbody>${Object.entries(d.missing).map(([k, v]) => `<tr><td>${esc(k.replace(/_/g, ' '))}</td><td class="num">${v} of ${d.n}</td></tr>`).join('')}</tbody></table>
      <p class="sub">Score builds in these answers: ${d.score_versions.map(esc).join(', ') || '—'}.</p></section>
    ${sourcesAndLimits(d)}`;
}

function sourcesAndLimits(d) {
  return `<section><h2>Data sources · 数据来源</h2><ul class="lim">${(d.sources || []).map((s) => `<li>${esc(s)}</li>`).join('')}</ul></section>
    <section><h2>Limitations · 数据局限性</h2><ul class="lim">${(d.n && d.n < 30 ? [`Only ${d.n} answers so far: every figure is descriptive and can move a lot with the next answers.`] : []).concat(d.limitations || []).map((s) => `<li>${esc(s)}</li>`).join('')}</ul></section>`;
}

async function loadEvaluation() {
  const st = document.getElementById('evalStatus');
  try {
    if (typeof streetwiseAwake === 'function') await streetwiseAwake((t) => { if (st) st.textContent = t; });
    const d = await streetwiseJson('/api/evaluation', {signal: AbortSignal.timeout(60000)});
    render(d);
  } catch (e) {
    document.getElementById('eval').innerHTML = `<div class="status warn">Could not load the evaluation data: ${esc(e.message)}. Nothing is shown rather than made up.</div>`;
  }
}
if (typeof module !== 'undefined') module.exports = {render, scatter, distribution};
else loadEvaluation();
