#!/usr/bin/env node
/* Build data/places/photos.json: one real, freely licensed photo per place where Wikidata / Wikipedia have one.
   Usage (needs network access to wikidata.org, query.wikidata.org, commons.wikimedia.org, en.wikipedia.org):
     node scripts/build_place_photos.mjs
   Rules: scripts/place-photos-core.js. Re-run after the place lists change. */
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {buildPlacePhotoIndex} = require('./place-photos-core.js');
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
export const PHOTO_CATEGORIES = ['attractions', 'museums', 'historic', 'historic_lpc', 'culture', 'parks', 'hotels', 'shopping'];
const places = [];
for (const c of PHOTO_CATEGORIES) {
 const d = JSON.parse(fs.readFileSync(path.join(root, 'data/places', c + '.json'), 'utf8'));
 for (const r of d.records) if (r.id && r.name && r.lat != null) places.push({id: r.id, name: r.name, lat: r.lat, lon: r.lon, wd: r.wd || null});
}
const seen = new Set(), uniq = places.filter((p) => !seen.has(p.id) && seen.add(p.id));
const {items, counts} = await buildPlacePhotoIndex(uniq, {fetch, node: true, log: (m) => console.log(m)});
const out = {version: 1, built: new Date().toISOString(), categories: PHOTO_CATEGORIES,
 rules: 'scripts/place-photos-core.js', thumb_base: 'https://upload.wikimedia.org/wikipedia/commons/thumb/',
 fields: ['thumb', 'author', 'license', 'wikidata', 'via', 'lat', 'lon', 'name'], counts, items};
fs.writeFileSync(path.join(root, 'data/places/photos.json'), JSON.stringify(out));
console.log(`wrote data/places/photos.json: ${counts.photo} places`);
