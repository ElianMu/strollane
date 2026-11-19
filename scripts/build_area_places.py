#!/usr/bin/env python3
"""Add Brooklyn and Queens to the discovery place index (data/places), next to Manhattan's records.

Reads only files already downloaded by scripts/download_area_sources.py --places (no network):
    data/cache/sources/<area>/places_osm.json   OpenStreetMap places, the query and tags of scripts/build_place_index.py
    data/cache/sources/<area>/lpc_places.json   NYC LPC individual landmark lots
    data/cache/sources/<area>/restrooms.json    NYC Open Data Public Restrooms in the area's box
    data/cache/sources/<area>/hotel_lots.json   NYC DOF hotel-class tax lots in the borough
    data/cache/sources/<area>/wikidata.json     Wikidata sitelinks for the places' Wikidata IDs
plus the citywide DOHMH inspection file already in the repo (data/inspections/dohmh.json.gz).

Every record is built by the same functions as Manhattan's (scripts/build_place_index.py) and kept only when it lies in
the area's box, its nearest NYC LION street segment is in that area (the boxes reach into Manhattan, and Brooklyn's box
and Queens share Newtown Creek and the Brooklyn–Queens line), and it is within 150 m of the joined walk network, so each one can be
routed to. Records get "area" and "boro";
Manhattan's records are not changed. Rerunning replaces an area's records. An OpenStreetMap element already in the
Manhattan index (a few at the river edges) stays there once.

Run: python3 scripts/build_area_places.py              (both areas)
     python3 scripts/build_area_places.py --area lic
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import build_place_index as bpi  # noqa: E402
from areas import AREAS, in_box  # noqa: E402
from routing.engine import PedestrianNetwork, RoutingError  # noqa: E402

ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, 'data', 'cache', 'sources')
BORO = {'brooklyn': 'Brooklyn', 'lic': 'Queens'}
NEEDED = ('places_osm', 'lpc_places', 'restrooms', 'hotel_lots', 'wikidata')
PREFIX_AREA = {'MN': 'manhattan', 'BK': 'brooklyn', 'QN': 'lic'}
CELL = 0.002  # degrees, about 170 m north–south


def inside_outline(lon, lat, polygons):
    """Point in a GeoJSON MultiPolygon's coordinates (even-odd rule over every ring, so holes count)."""
    inside = False
    for polygon in polygons:
        for ring in polygon:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                    inside = not inside
    return inside


class SegmentArea:
    """Which study area a point belongs to: that of its nearest LION street segment vertex (segment IDs carry the
    borough: MN-, BK-, QN-), from data/dimensions/<area>/segments.geojson."""

    def __init__(self):
        self.grid = {}
        for area in ('manhattan', 'brooklyn', 'lic'):
            for f in json.load(open(os.path.join(ROOT, 'data', 'dimensions', area, 'segments.geojson')))['features']:
                a = PREFIX_AREA[f['properties']['id'][:2]]
                for lon, lat in f['geometry']['coordinates']:
                    self.grid.setdefault((int(lon // CELL), int(lat // CELL)), []).append((lon, lat, a))
        # An area whose box reaches beyond its borough into a county with no LION segments (Queens: Nassau County) also
        # needs its own outline, else a point just over the line would take the nearest Queens street.
        self.outlines = {}
        for area in ('brooklyn', 'lic'):
            path = os.path.join(ROOT, 'data', 'pedestrian', f'{area}-boundary.json')
            if os.path.exists(path):
                g = json.load(open(path))['geometry']
                self.outlines[area] = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']

    def __call__(self, lon, lat):
        a = self._nearest(lon, lat)
        outline = self.outlines.get(a)
        return a if outline is None or inside_outline(lon, lat, outline) else None

    def _nearest(self, lon, lat):
        gx, gy = int(lon // CELL), int(lat // CELL)
        for r in (1, 2, 4):
            best = None
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for x, y, a in self.grid.get((gx + dx, gy + dy), ()):
                        d = ((x - lon) * 0.7578) ** 2 + (y - lat) ** 2  # cos(40.7°) scales longitude
                        if best is None or d < best[0]:
                            best = (d, a)
            if best:
                return best[1]
        return None


def load(area, name):
    path = os.path.join(CACHE, area, name + '.json')
    if not os.path.exists(path):
        raise SystemExit(f'Missing {path}. Run: python3 scripts/download_area_sources.py --places --area {area}')
    return json.load(open(path))


def _date(v):
    """ArcGIS dates come as epoch milliseconds; the Manhattan tiles hold ISO dates."""
    if isinstance(v, (int, float)) and v > 10 ** 10:
        return datetime.fromtimestamp(v / 1000, timezone.utc).strftime('%Y-%m-%d')
    return v


def landmark_records(features):
    """LPC landmark lots → name + vertex mean, as scripts/build_place_index.py landmark_records()."""
    out, seen = [], set()
    for f in features:
        p = f.get('properties') or {}
        fid = p.get('LPC_LPNumb')
        if not fid or fid in seen or not p.get('LPC_NAME') or p.get('BuildType') in ('Lamppost', 'Clock', 'Sidewalk Clock') or not f.get('geometry'):
            continue
        seen.add(fid)
        g = f['geometry']
        ring = g['coordinates'][0] if g['type'] == 'Polygon' else g['coordinates'][0][0]
        lon, lat = sum(c[0] for c in ring) / len(ring), sum(c[1] for c in ring) / len(ring)
        rec = {'id': 'lpc:' + fid, 'name': p['LPC_NAME'], 'lat': round(lat, 6), 'lon': round(lon, 6), 'addr': p.get('Address'),
               'sub': 'lpc=individual_landmark', 'src': 'lpc', 'designated': _date(p.get('DesDate')), 'style': (p.get('Style_Prim') or '').strip() or None,
               'architect': p.get('Arch_Prima'), 'built': p.get('Date_Low'), 'report': p.get('URL_REPORT'), 'type': p.get('BuildType')}
        out.append({k: v for k, v in rec.items() if v not in (None, '', 0)})
    return out


def restroom_records(rows):
    out = []
    for r in rows:
        lat, lon = float(r['latitude']), float(r['longitude'])
        name = r.get('facility_name') or 'Public restroom'
        rec = {'id': f'nycrr:{name}-{lat:.5f},{lon:.5f}', 'name': name, 'lat': round(lat, 6), 'lon': round(lon, 6),
               'sub': 'nyc=public_restroom', 'src': 'nyc_restrooms', 'hours': r.get('hours_of_operation'), 'status': r.get('status'),
               'operator': r.get('operator'), 'access': r.get('accessibility'), 'web': (r.get('website') or {}).get('url') if isinstance(r.get('website'), dict) else r.get('website')}
        out.append({k: v for k, v in rec.items() if v not in (None, '')})
    return out


def build_area(area, routable, taken, built, area_of):
    """The records of one area, per category, and what was kept or dropped."""
    box, extra = AREAS[area]['box'], {'area': area, 'boro': BORO[area]}
    d = load(area, 'places_osm')
    groups = {c[0]: [] for c in bpi.CATEGORIES}
    groups['historic_lpc'] = []
    stats = {'osm_elements': len(d['elements']), 'outside_box': 0, 'in_another_area': 0, 'outside_walk_network': 0, 'already_in_index': 0}

    def keep(rec_id, lon, lat):
        if rec_id in taken:
            stats['already_in_index'] += 1
            return None
        if not in_box(lon, lat, box):
            stats['outside_box'] += 1
            return None
        if area_of(lon, lat) != area:
            stats['in_another_area'] += 1
            return None
        snap = routable(lon, lat)
        if snap is None:
            stats['outside_walk_network'] += 1
        return snap

    for x in d['elements']:
        t = x['tags']
        cat = next((c for c, _, m in bpi.CATEGORIES if m(t)), None)
        if not cat or not (t.get('name') or cat in bpi.UNNAMED_LABEL):
            continue
        if cat == 'banks' and not t.get('name') and t.get('amenity') != 'atm':
            continue
        eid = f"osm:{x['type']}/{x['id']}"
        snap = keep(eid, x['lon'], x['lat'])
        if snap is not None:
            groups[cat].append({**bpi.osm_record(eid, cat, x['lat'], x['lon'], t, snap), **extra})
    for rec in restroom_records(load(area, 'restrooms')):
        snap = keep(rec['id'], rec['lon'], rec['lat'])
        if snap is not None:
            groups['restrooms'].append({**rec, 'snap': round(snap, 1), **extra})
    for rec in landmark_records(load(area, 'lpc_places')):
        snap = keep(rec['id'], rec['lon'], rec['lat'])
        if snap is not None:
            groups['historic_lpc'].append({**rec, 'snap': round(snap, 1), **extra})
    wd = load(area, 'wikidata')
    stats['wikidata_failed_ids'] = len(wd.get('_failed', {}))
    bpi.apply_wikidata(groups, {q: tuple(v) for q, v in wd.items() if q.startswith('Q')})
    stats['inspections'] = bpi.link_inspections(groups, lambda lon, lat: routable(lon, lat) if in_box(lon, lat, box) else None,
                                                boros=(BORO[area],), keep=lambda lon, lat: in_box(lon, lat, box), extra=extra)
    stats['hotel_lots'] = bpi.link_hotel_lots(groups, load(area, 'hotel_lots'))
    stats['quality'] = bpi.resolve_entities(groups, d.get('osm_timestamp'), built)
    stats['records'] = sum(len(v) for v in groups.values())
    return groups, stats, d.get('osm_timestamp')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', choices=list(BORO), action='append', help='default: Brooklyn and Queens')
    areas = ap.parse_args().area or list(BORO)
    t0 = time.time()
    for area in areas:
        for name in NEEDED:
            load(area, name)  # fail before any work if a download is missing
    net = PedestrianNetwork()
    area_of = SegmentArea()

    def routable(lon, lat):
        try:
            return net.snap(lon, lat, 'poi')['snap_distance_m']
        except RoutingError:
            return None

    index = json.load(open(os.path.join(bpi.OUT, 'index.json')))
    docs = {c['id']: json.load(open(os.path.join(bpi.OUT, c['id'] + '.json'))) for c in index['categories']}
    for doc in docs.values():  # drop earlier runs of these areas; Manhattan records have no "area"
        doc['records'] = [r for r in doc['records'] if r.get('area') not in areas]
    taken = {p for doc in docs.values() for r in doc['records'] for p in [r['id'], *(r.get('pids') or [])]}
    built = datetime.now(timezone.utc).isoformat(timespec='seconds')
    area_meta = dict(index.get('areas') or {})
    for area in areas:
        groups, stats, stamp = build_area(area, routable, taken, built, area_of)
        for cat, recs in groups.items():
            docs[cat]['records'] += recs
            taken.update(p for r in recs for p in [r['id'], *(r.get('pids') or [])])
        area_meta[area] = {'label': AREAS[area]['label'], 'box_west_south_east_north': AREAS[area]['box'], 'built_at': built, 'osm_timestamp': stamp,
                           'network_version': net.network_version, **stats,
                           'by_category': {c: len(v) for c, v in groups.items()}}
        print(area, json.dumps(area_meta[area]['by_category']), {k: stats[k] for k in ('osm_elements', 'outside_box', 'in_another_area', 'already_in_index', 'outside_walk_network', 'records')}, flush=True)
    for cat, doc in docs.items():
        doc['records'].sort(key=lambda r: (r['name'].lower(), r['id']))
    for c in index['categories']:
        recs = docs[c['id']]['records']
        c['count'] = len(recs)
        # Manhattan's merge counts are kept from its own build; each area adds its own. Missing fields are counted on the records.
        base = c.setdefault('manhattan_quality', {k: c.get(k, 0) for k in ('merged_duplicates', 'records_with_conflicts')})
        for k in ('merged_duplicates', 'records_with_conflicts'):
            c[k] = base[k] + sum(m.get('quality', {}).get(c['id'], {}).get(k, 0) for m in area_meta.values())
        if 'missing' in c:
            c['missing'] = {f: sum(1 for r in recs if not r.get(f)) for f in c['missing']}
        c['by_area'] = {a: sum(1 for r in recs if r.get('area', 'manhattan') == a) for a in ['manhattan', *sorted(area_meta)]}
    index['areas'] = area_meta
    index['coverage'] = ('Within 150 m of the routable pedestrian graph: Manhattan (' + index['network_version'] + ', built ' + index['built_at'][:10] + '); '
                         + '; '.join(f"{AREAS[a]['label']} ({m['network_version']}, built {m['built_at'][:10]})" for a, m in sorted(area_meta.items())))
    index['fields'].update({'area': 'study area of a record added by scripts/build_area_places.py (absent = Manhattan)', 'boro': 'borough'})
    from snapshot_io import publish
    documents = {cat + '.json': doc for cat, doc in docs.items()}
    documents['index.json'] = index
    publish(bpi.OUT, documents, os.path.join(os.path.dirname(ROOT), 'streetwise-data-history', 'poi-index'))
    print(f'done in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
