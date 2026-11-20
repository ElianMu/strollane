#!/usr/bin/env python3
"""Shared paths that OSMnx's walk network leaves out: highway=cycleway ways that OpenStreetMap marks as open to people
on foot (foot=yes, designated or permissive).

    python3 scripts/download_foot_paths.py          writes data/pedestrian/foot-paths.json (needs Overpass)
    python3 scripts/merge_networks.py                adds them to the joined network
    python3 scripts/compile_network.py --area nyc

OSMnx's network_type="walk" drops every highway=cycleway, whatever its foot tag. In New York several of these are the
only walkway across a bridge: the Cross Bay Bridge path (ways 47839497, 1218659797, ...) is the one walkable link
between the Rockaway peninsula and the rest of Queens, and the Flatbush Avenue Greenway leads to the Marine Parkway
Bridge walkway. Without them the peninsula was its own component of 8,649 nodes and could not be routed to.

Only the ways the map itself opens to walkers are kept; a cycleway with no foot tag, or foot=no, is not added.
Standard library only. Overpass servers are tried in turn; a busy server is retried after a pause.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from areas import AREAS  # noqa: E402

OUT = os.path.join(ROOT, 'data', 'pedestrian', 'foot-paths.json')
MANHATTAN_BOX = (-74.0479, 40.6829, -73.9067, 40.8820)  # Manhattan with its islands and bridge landings
SERVERS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter',
           'https://overpass.private.coffee/api/interpreter']
FOOT_OPEN = {'yes', 'designated', 'permissive'}
KEEP_TAGS = ['highway', 'name', 'foot', 'bicycle', 'access', 'bridge', 'tunnel', 'layer', 'surface', 'lit', 'segregated',
             'incline', 'wheelchair', 'covered']


def boxes():
    out = {'manhattan': MANHATTAN_BOX}
    out.update({a: spec['box'] for a, spec in AREAS.items()})
    return out


def overpass(query):
    last = None
    for attempt in range(3):
        for url in SERVERS:
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': query}).encode(),
                                             headers={'User-Agent': 'strollane-nyc/1.0 (walk network build)'})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read().decode())
            except Exception as e:  # busy server, timeout, refused: try the next one
                last = e
        time.sleep(20 * (attempt + 1))  # 502 / 429 from a busy server: wait, then try again
    raise SystemExit(f'Overpass did not answer: {last}')


TILES = {'manhattan': 1, 'brooklyn': 1, 'lic': 4}  # Queens in one query timed out on 2026-11-20; 4 x 4 tiles answer


def tiles(box, k):
    w, s, e, n = box
    dx, dy = (e - w) / k, (n - s) / k
    for i in range(k):
        for j in range(k):
            yield (w + i * dx, s + j * dy, w + (i + 1) * dx, s + (j + 1) * dy)


def fetch(box, depth=0):
    """Elements of one tile; a tile that fails is split in four (once more at most)."""
    w, s, e, n = box
    q = (f'[out:json][timeout:60];way["highway"="cycleway"]["foot"~"^(yes|designated|permissive)$"]'
         f'({s:.6f},{w:.6f},{n:.6f},{e:.6f});out body geom;')
    try:
        return overpass(q).get('elements', [])
    except SystemExit:
        if depth >= 1:
            raise
        return [el for sub in tiles(box, 2) for el in fetch(sub, depth + 1)]


def main():
    ways, per_box = {}, {}
    for name, box in boxes().items():
        elements = [el for tile in tiles(box, TILES[name]) for el in fetch(tile)]
        kept = 0
        for el in elements:
            t = el.get('tags', {})
            if el.get('type') != 'way' or t.get('foot') not in FOOT_OPEN or t.get('access') in ('no', 'private'):
                continue
            geom = el.get('geometry') or []
            if len(geom) < 2 or len(geom) != len(el.get('nodes', [])):
                continue
            kept += el['id'] not in ways
            ways[el['id']] = {'id': el['id'], 'nodes': el['nodes'], 'coords': [[g['lon'], g['lat']] for g in geom],
                              'tags': {k: t[k] for k in KEEP_TAGS if k in t}}
        per_box[name] = kept
        time.sleep(2)
    doc = {'metadata': {'source': 'OpenStreetMap via Overpass API: way[highway=cycleway][foot~yes|designated|permissive]',
                        'retrieved_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                        'boxes': {k: list(v) for k, v in boxes().items()}, 'ways_per_box': per_box, 'ways': len(ways),
                        'why': 'OSMnx network_type="walk" drops all highway=cycleway; these are open to walkers.'},
           'ways': sorted(ways.values(), key=lambda x: x['id'])}
    with open(OUT + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(doc, f, separators=(',', ':'), ensure_ascii=False)
    os.replace(OUT + '.tmp', OUT)
    print(json.dumps(doc['metadata'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
