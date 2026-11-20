#!/usr/bin/env python3
"""One small city-wide file per sparse map layer, for zoomed-out views (data/layers/overview/<tileset>.json).

The map keeps each layer in 1 km tiles. With Manhattan, Brooklyn and Queens on one map, a city-wide view covers
hundreds of tiles per layer: the page skipped the layer ("Zoom in to load") or sent so many requests that GitHub Pages
answered 429. For point and polygon layers small enough to draw city-wide, this writes all features in one file, with
only what a zoomed-out map needs: feature_id, a name, area, the fields a dataset filter reads (catalog "filter") and, for
parks, type and size. Polygons are simplified (about 5 m) and coordinates rounded to 5 decimals (about 1 m). Zoomed in,
the page reads the full tiles as before; a click on an overview feature shows what the overview holds.

Run after scripts/build_urban_layers.py or scripts/build_area_layers.py:  python3 scripts/build_layer_overviews.py
"""
import json
import os
import sys

from shapely.geometry import mapping, shape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_urban_layers as U  # noqa: E402

OUT_DIR = os.path.join(U.OUT, 'overview')
MAX_POINTS, MAX_POLYGONS = 6000, 1500  # larger layers stay "zoom in to load"
NAME_KEYS = ('name', 'signname', 'LPC_NAME', 'area_name', 'stop_name', 'facility_name', 'gardenname', 'plazaname', 'building_name',
             'street_address', 'property')
EXTRA = {'parks': ('typecategory', 'acres')}


def rounded(c):
    return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [rounded(x) for x in c]


def main():
    catalog = json.load(open(os.path.join(U.OUT, 'catalog.json')))
    geometry = {d['tileset']: d['geometry'] for d in catalog['datasets'] if d.get('tileset')}
    filters = {}
    for d in catalog['datasets']:
        if d.get('tileset') and d.get('filter'):
            filters.setdefault(d['tileset'], set()).update(d['filter'])
    os.makedirs(OUT_DIR, exist_ok=True)
    for tid, ts in catalog['tilesets'].items():
        kind = geometry.get(tid)
        cap = MAX_POINTS if kind == 'Point' else MAX_POLYGONS if kind == 'Polygon' else 0
        path = os.path.join(OUT_DIR, tid + '.json')
        if ts['features'] > cap:
            ts.pop('overview', None)
            if os.path.exists(path):
                os.remove(path)
            continue
        seen, feats = set(), []
        for key in ts['tiles']:
            for f in json.load(open(os.path.join(U.TILES, tid, key + '.json')))['features']:
                p = f['properties']
                if p['feature_id'] in seen:
                    continue
                seen.add(p['feature_id'])
                name = next((p[k] for k in NAME_KEYS if p.get(k)), None)
                props = {'feature_id': p['feature_id'], **({'name': name} if name else {}), **({'area': p['area']} if p.get('area') else {}),
                         **{k: p.get(k) for k in sorted(set(filters.get(tid, ())) | set(EXTRA.get(tid, ()))) if p.get(k) is not None}, 'overview': True}
                g = f['geometry']
                if kind == 'Polygon':
                    g = mapping(shape(g).simplify(0.00005, preserve_topology=True))
                feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': g['type'], 'coordinates': rounded(g['coordinates'])}})
        with open(path + '.tmp', 'w', encoding='utf-8') as fh:
            json.dump({'type': 'FeatureCollection', 'features': feats}, fh, separators=(',', ':'), ensure_ascii=False)
        os.replace(path + '.tmp', path)
        ts['overview'] = {'features': len(feats), 'bytes': os.path.getsize(path)}
    with open(os.path.join(U.OUT, 'catalog.json'), 'w') as fh:
        json.dump(catalog, fh, indent=1, ensure_ascii=False)
    made = {t: ts['overview'] for t, ts in catalog['tilesets'].items() if 'overview' in ts}
    print(len(made), 'overviews,', round(sum(v['bytes'] for v in made.values()) / 1e6, 1), 'MB')
    for t, v in sorted(made.items(), key=lambda x: -x[1]['bytes']):
        print(f"  {t}: {v['features']:,} features, {v['bytes'] / 1e3:.0f} kB")


if __name__ == '__main__':
    main()
