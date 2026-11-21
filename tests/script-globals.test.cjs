'use strict';
// Every page script is a classic script sharing one global scope: a top-level const/let/class declared in two of
// them (or also declared as a function) is a SyntaxError that stops the later file from running at all. On
// 2026-11-20 route-photos.js and street-photos.js both declared `streetPhotos`, so street-photos.js never ran and
// no walk showed its street-level photos.
const fs = require('fs'), path = require('path'), assert = require('assert');
const root = path.join(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const files = [...html.matchAll(/<script[^>]*\bsrc="([^"?]+\.js)(?:\?[^"]*)?"/g)].map((m) => m[1]).filter((f) => !/^https?:/.test(f) && fs.existsSync(path.join(root, f)));
assert(files.length > 20, 'found the page scripts');
const lexical = new Map(), fns = new Map();
for (const f of files) {
 const src = fs.readFileSync(path.join(root, f), 'utf8');
 if (/^\s*(\(function|\(\(\)|!function)/.test(src.replace(/^'use strict';\s*/, '').replace(/^\/\*[\s\S]*?\*\/\s*/, ''))) continue; // wrapped: nothing global
 for (const m of src.matchAll(/^(?:const|let|class)\s+([A-Za-z_$][\w$]*)/gm)) { if (!lexical.has(m[1])) lexical.set(m[1], []); lexical.get(m[1]).push(f); }
 for (const m of src.matchAll(/^(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)/gm)) { if (!fns.has(m[1])) fns.set(m[1], []); fns.get(m[1]).push(f); }
}
const clashes = [];
for (const [name, where] of lexical) {
 if (where.length > 1) clashes.push(`${name}: declared in ${where.join(', ')}`);
 if (fns.has(name)) clashes.push(`${name}: const/let in ${where.join(', ')} and function in ${fns.get(name).join(', ')}`);
}
assert.deepStrictEqual(clashes, [], 'global names declared twice across page scripts');
console.log(`script-globals: ok (${files.length} scripts, ${lexical.size} top-level const/let/class)`);
