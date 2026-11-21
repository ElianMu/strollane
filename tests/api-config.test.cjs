'use strict';
// api-config.js: a walk request that times out right after the route server wakes is sent once more (2026-11-21).
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const calls = [];
let mode = 'timeout-then-ok';
const fakeFetch = (url, opt) => {
 calls.push([url, opt.signal ? 'signal' : 'none']);
 if (mode === 'timeout-then-ok' && calls.length === 1) { const e = new Error('signal timed out'); e.name = 'TimeoutError'; return Promise.reject(e); }
 if (mode === 'network') return Promise.reject(new TypeError('Failed to fetch'));
 return Promise.resolve({ok: true, status: 200, json: () => Promise.resolve({routes: []})});
};
const ctx = {location: {hostname: 'elianmu.github.io'}, fetch: fakeFetch, AbortSignal, console, setTimeout, Promise, window: undefined};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, '..', 'api-config.js'), 'utf8') + ';this.api={streetwiseRetryOnce,STREETWISE_SLOW_MESSAGE};', ctx);
const {streetwiseRetryOnce, STREETWISE_SLOW_MESSAGE} = ctx.api;
(async () => {
 const notes = [];
 const res = await streetwiseRetryOnce('/api/routes', {method: 'POST'}, 30000, (t) => notes.push(t));
 assert.equal(res.status, 200);
 assert.equal(calls.length, 2, 'sent once more after the timeout');
 assert.equal(calls[0][0], 'https://streetwise-api.onrender.com/api/routes');
 assert.deepEqual(notes, [STREETWISE_SLOW_MESSAGE], 'the walker is told why it takes longer');
 // anything other than a timeout is not retried
 calls.length = 0; mode = 'network';
 await assert.rejects(streetwiseRetryOnce('/api/routes', {method: 'POST'}, 30000, () => {}), /Failed to fetch/);
 assert.equal(calls.length, 1);
 console.log('api-config: ok');
})().catch((e) => { console.error(e); process.exit(1); });
