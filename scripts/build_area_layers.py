#!/usr/bin/env python3
"""Add Brooklyn and western Queens to the map layers (data/layers), next to Manhattan's features.

scripts/build_urban_layers.py builds the 1 km tiles for Manhattan from live downloads. This script adds the other areas
from files already downloaded (python3 scripts/download_area_sources.py --layers) and from the area walk graphs, with
the same datasets, fields and feature IDs, so the page and its catalog do not change shape. No network.

Per area it reads data/cache/sources/<area>/layer_*.json, streets_v4.json and restrooms.json, and
data/pedestrian/<area>-walk-graph.json.gz. A feature is added when it lies in the area's box and its nearest LION street
segment belongs to the area (the boxes reach into Manhattan and overlap along Newtown Creek; see
scripts/build_area_places.py). Each added feature carries "area"; rerunning replaces that area's features and leaves
Manhattan's alone. Features are de-duplicated by feature_id within a tile (a walkway shared by two downloads, for example).

Not built for the areas (project owner's choice, 2026-11-18, to keep the site well under GitHub Pages' 1 GB): building
footprints (and the height / age views), tax lots (land use), all activity places, 311 noise complaints and the sidewalk
surface. The catalog marks them "Manhattan only".

Run: python3 scripts/build_area_layers.py              (both areas)
     python3 scripts/build_area_layers.py --area lic
"""
import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import build_urban_layers as U  # noqa: E402
from areas import AREAS, in_box  # noqa: E402
from build_area_places import SegmentArea  # noqa: E402

ROOT = U.ROOT
CACHE = os.path.join(ROOT, 'data', 'cache', 'sources')
NAME = {'manhattan': 'Manhattan', 'brooklyn': 'Brooklyn', 'lic': 'western Queens'}
MANHATTAN_ONLY = {'building_footprints', 'pluto_lots', 'activity_places', 'noise_complaints', 'sidewalk_surface'}
ROAD_TYPE = {1: 'Street', 2: 'Highway', 3: 'Bridge', 4: 'Tunnel', 5: 'Boardwalk', 6: 'Path/Trail', 7: 'Step street', 8: 'Driveway', 9: 'Ramp',
             10: 'Alley', 13: 'U-turn', 14: 'Ferry route'}
LION_WALK_TYPES = U.si.LION_WALK_TYPES


def load(area, name):
    path = os.path.join(CACHE, area, name + '.json')
    if not os.path.exists(path):
        raise SystemExit(f'Missing {path}. Run: python3 scripts/download_area_sources.py --layers --area {area}')
    return json.load(open(path))


def centre(geom):
    """A representative point for the area test: a point, a line's middle vertex, a polygon's vertex mean."""
    pts = U.coords_of(geom)
    if geom['type'] in ('LineString', 'MultiLineString'):
        return pts[len(pts) // 2]
    return [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]


def area_tiles(area, area_of):
    box = AREAS[area]['box']
    mine = lambda lon, lat: in_box(lon, lat, box) and area_of(lon, lat) == area
    mine_g = lambda g: bool(g) and bool(U.coords_of(g)) and mine(*centre(g))
    F, pt = U.feature, U.pt
    T = {}

    # A. Streets & pedestrian infrastructure ------------------------------------------------------------------------
    degree, centre_l, express = {}, [], []
    for i, f in enumerate(load(area, 'streets_v4')):
        p, g = f.get('properties') or {}, f.get('geometry')
        if not g:
            continue
        lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates'] if g['type'] == 'MultiLineString' else []
        rw = p.get('rw_type')
        rw = int(rw) if str(rw).isdigit() else rw
        for j, line in enumerate(lines):
            if len(line) < 2:
                continue
            if rw in LION_WALK_TYPES:
                for end in (line[0], line[-1]):
                    k = (round(end[0], 6), round(end[1], 6)); degree[k] = degree.get(k, 0) + 1
            if not mine(*line[len(line) // 2]):
                continue
            props = {'lion_physicalid': p.get('physicalid'), 'street_name': p.get('st_label') or p.get('st_name'),
                     'road_type': ROAD_TYPE.get(rw, str(rw)), 'street_width_ft': p.get('st_width')}
            feat = F(f"{p.get('physicalid')}-{j}", props, {'type': 'LineString', 'coordinates': line})
            centre_l.append(feat)
            if rw in (2, 9):
                express.append(feat)
    T['lion_centerline'], T['expressways'] = centre_l, express
    T['intersections'] = [F(f'X{lon:.6f},{lat:.6f}', {'joining_segments': d}, pt(lon, lat)) for (lon, lat), d in degree.items() if d >= 3 and mine(lon, lat)]

    graph = json.load(gzip.open(os.path.join(ROOT, 'data', 'pedestrian', f'{area}-walk-graph.json.gz'), 'rt', encoding='utf-8'))
    walk = {'osm_sidewalks': [], 'osm_crosswalks': [], 'osm_paths': [], 'pedestrian_bridges': []}
    for u, v, k, gi, rev, length, osmids, tags in graph['edges']:
        if rev:
            continue
        geom = graph['geoms'][gi]
        if not mine(*geom[len(geom) // 2]):
            continue
        fw = tags.get('footway'); fw = fw if isinstance(fw, list) else [fw]
        hw = tags.get('highway'); hw = hw if isinstance(hw, list) else [hw]
        props = {'osm_way_ids': ' '.join(map(str, osmids)), 'highway': '/'.join(map(str, hw)), 'footway': '/'.join(str(x) for x in fw if x),
                 'name': tags.get('name') if not isinstance(tags.get('name'), list) else '/'.join(tags['name']), 'surface': tags.get('surface'), 'length_m': length,
                 'bridge': tags.get('bridge') if not isinstance(tags.get('bridge'), list) else '/'.join(tags['bridge'])}
        f = F(f'{u}-{v}-{k}', props, {'type': 'LineString', 'coordinates': geom})
        kind = 'osm_sidewalks' if 'sidewalk' in fw else 'osm_crosswalks' if 'crossing' in fw else 'osm_paths' if set(hw) & {'footway', 'path', 'pedestrian', 'steps', 'bridleway', 'track', 'corridor'} else None
        if kind:
            walk[kind].append(f)
        if kind and tags.get('bridge') not in (None, 'no'):
            walk['pedestrian_bridges'].append(f)
    T.update(walk)

    T['pedestrian_ramps'] = [F(r.get('rampid') or f'ramp-{area}-{i}', {k: r.get(k) for k in ('cornerid', 'stname1', 'stname2', 'ramp_width', 'ramp_running_slope_total', 'curb_reveal', 'dws_conditions', 'ponding')}, r['the_geom'])
                             for i, r in enumerate(load(area, 'layer_ramps')) if r.get('the_geom') and mine_g(r['the_geom'])]
    T['pedestrian_plazas'] = [F(p['objectid'], {k: p.get(k) for k in ('plazaname', 'onstreet', 'fromstreet', 'tostreet', 'partner')}, p['the_geom'])
                              for p in load(area, 'layer_plazas') if p.get('the_geom') and mine_g(p['the_geom'])]
    T['bike_routes'] = [F(f"{b.get('segmentid')}-{i}", {k: b.get(k) for k in ('street', 'fromstreet', 'tostreet', 'facilitycl', 'allclasses', 'bikedir', 'onoffst', 'instdate', 'status')}, b['the_geom'])
                        for i, b in enumerate(load(area, 'layer_bike_routes')) if b.get('the_geom') and mine_g(b['the_geom'])]
    nodes = load(area, 'layer_osm_street_nodes')
    for tid, hw in (('traffic_signals', 'traffic_signals'), ('bus_stops', 'bus_stop')):
        T[tid] = [F(x['id'], x['tags'], pt(x['lon'], x['lat'])) for x in nodes['elements'] if x['tags'].get('highway') == hw and mine(x['lon'], x['lat'])]
    T['drinking_fountains'] = [F(f['system'], {'fountain_type': f.get('fountainty'), 'position': f.get('position'), 'property': f.get('propertyna'), 'feature_status': f.get('featuresta')}, f['the_geom'])
                               for f in load(area, 'layer_fountains') if f.get('the_geom') and mine_g(f['the_geom'])]
    T['public_restrooms'] = [F(f"{r['facility_name']}-{area}-{i}", {k: r.get(k) for k in ('facility_name', 'location_type', 'operator', 'status', 'open', 'hours_of_operation', 'accessibility', 'restroom_type', 'changing_stations', 'website')},
                               pt(r['longitude'], r['latitude'])) for i, r in enumerate(load(area, 'restrooms')) if mine(float(r['longitude']), float(r['latitude']))]

    # B. Nature -------------------------------------------------------------------------------------------------------
    T['street_trees'] = [F(r['objectid'], {k: r.get(k) for k in ('genusspecies', 'dbh', 'tpcondition', 'tpstructure', 'planteddate', 'updateddate', 'riskrating')}, r['location'])
                         for r in load(area, 'layer_trees') if r.get('location') and mine(*r['location']['coordinates'])]
    T['parks'] = [F(p['gispropnum'], {k: p.get(k) for k in ('signname', 'typecategory', 'subcategory', 'acres', 'address')}, p['multipolygon'])
                  for p in load(area, 'layer_parks') if p.get('multipolygon') and mine_g(p['multipolygon'])]
    T['community_gardens'] = [F(g.get('parksid') or g['gardenname'], {k: g.get(k) for k in ('gardenname', 'address', 'status', 'juris', 'openhrsm', 'openhrstu', 'openhrsw', 'openhrsth', 'openhrsf', 'openhrssa', 'openhrssu')}, g['multipolygon'])
                              for g in load(area, 'layer_gardens') if g.get('multipolygon') and mine_g(g['multipolygon'])]
    T['pops'] = [F(p['pops_number'], {k: p.get(k) for k in ('building_name', 'building_address_with_zip', 'public_space_type', 'year_completed', 'hour_of_access_required', 'amenities_required')}, pt(p['longitude'], p['latitude']))
                 for p in load(area, 'layer_pops') if mine(float(p['longitude']), float(p['latitude']))]

    # D. Historic & cultural ----------------------------------------------------------------------------------------
    epoch_date = lambda v: datetime.fromtimestamp(v / 1000, timezone.utc).date().isoformat() if isinstance(v, (int, float)) else v
    T['landmarks'] = [F(f['properties'].get('LPC_LPNumb') or f"BBL{f['properties'].get('BBL')}", {k: epoch_date(v) if k == 'DesDate' else v for k, v in f['properties'].items() if k != 'LPC_LPNumb'}, f['geometry'])
                      for f in load(area, 'layer_lpc') if f.get('geometry') and mine_g(f['geometry'])]
    from pyproj import Transformer
    to_wgs = Transformer.from_crs(2263, 4326, always_xy=True).transform

    def reproject(g):
        def r(cs):
            return list(to_wgs(*cs)) if isinstance(cs[0], (int, float)) else [r(x) for x in cs]
        return {'type': g['type'], 'coordinates': r(g['coordinates'])}
    hd = []
    for i, h in enumerate(load(area, 'layer_historic_districts')):
        if h.get('the_geom'):
            g = reproject(h['the_geom'])
            if mine_g(g):
                hd.append(F(h['lp_number'] + (f"-{i}" if h.get('extension') else ''), {'area_name': h.get('area_name'), 'lp_number': h.get('lp_number'), 'status': h.get('status_of_'),
                                                                                      'designated': h.get('desdate'), 'calendared': h.get('caldate'), 'extension': h.get('extension')}, g))
    T['historic_districts'] = hd

    osm = load(area, 'layer_osm')
    osm_layer = lambda pred: [F(x['id'], x['tags'], pt(x['lon'], x['lat'])) for x in osm['elements'] if pred(x['tags']) and mine(x['lon'], x['lat'])]
    T['museums'] = osm_layer(lambda t: t.get('tourism') == 'museum')
    T['galleries'] = osm_layer(lambda t: t.get('tourism') == 'gallery')
    T['theaters'] = osm_layer(lambda t: t.get('amenity') in ('theatre', 'music_venue', 'concert_hall', 'arts_centre'))
    T['cinemas'] = osm_layer(lambda t: t.get('amenity') == 'cinema')
    T['libraries'] = osm_layer(lambda t: t.get('amenity') == 'library')
    T['public_art'] = osm_layer(lambda t: t.get('tourism') == 'artwork')
    T['monuments'] = osm_layer(lambda t: t.get('historic') in ('memorial', 'monument'))
    T['restaurants'] = osm_layer(lambda t: t.get('amenity') in ('restaurant', 'fast_food', 'food_court'))
    T['cafes'] = osm_layer(lambda t: t.get('amenity') in ('cafe', 'ice_cream'))
    T['bars'] = osm_layer(lambda t: t.get('amenity') in ('bar', 'pub', 'biergarten'))
    T['bakeries'] = osm_layer(lambda t: t.get('shop') in ('bakery', 'pastry'))
    T['grocery'] = osm_layer(lambda t: t.get('shop') in ('supermarket', 'convenience', 'greengrocer', 'deli', 'grocery'))
    T['retail'] = osm_layer(lambda t: 'shop' in t and t['shop'] not in ('bakery', 'pastry', 'supermarket', 'convenience', 'greengrocer', 'deli', 'grocery'))
    T['markets'] = osm_layer(lambda t: t.get('amenity') == 'marketplace')
    T['entertainment'] = osm_layer(lambda t: t.get('amenity') in ('nightclub', 'casino') or t.get('leisure') in ('amusement_arcade', 'bowling_alley', 'escape_game'))
    T['recreation'] = osm_layer(lambda t: t.get('leisure') in ('sports_centre', 'fitness_centre', 'playground', 'pitch', 'swimming_pool', 'track'))
    T['hospitals_clinics'] = osm_layer(lambda t: t.get('amenity') in ('hospital', 'clinic', 'doctors'))
    T['pharmacies'] = osm_layer(lambda t: t.get('amenity') == 'pharmacy')
    T['schools'] = osm_layer(lambda t: t.get('amenity') == 'school')
    T['benches'] = osm_layer(lambda t: t.get('amenity') == 'bench' or t.get('leisure') == 'picnic_table')
    T['ferry_terminals'] = osm_layer(lambda t: t.get('amenity') == 'ferry_terminal')
    T['viewpoints'] = osm_layer(lambda t: t.get('tourism') == 'viewpoint')
    T['linknyc'] = [F(k['link_site_id'], {x: k.get(x) for x in ('street_address', 'cross_street_1', 'cross_street_2', 'link_installation_status', 'planned_kiosk_type', 'link_installation')}, pt(k['longitude'], k['latitude']))
                    for k in load(area, 'layer_linknyc') if mine(float(k['longitude']), float(k['latitude']))]

    # F. Safety -------------------------------------------------------------------------------------------------------
    for tid, name, who in (('pedestrian_crashes', 'layer_crashes', 'pedestrians'), ('cyclist_crashes', 'layer_cyclist_crashes', 'cyclist')):
        T[tid] = [F(r['collision_id'], {k: r.get(k) for k in ('crash_date', 'crash_time', 'on_street_name', 'cross_street_name', 'off_street_name', f'number_of_{who}_injured', f'number_of_{who}_killed', 'contributing_factor_vehicle_1')},
                    pt(r['longitude'], r['latitude'])) for r in load(area, name) if r.get('latitude') and mine(float(r['longitude']), float(r['latitude']))]
    T['speed_limits'] = [F(f'sl-{area}-{i}', {'street': s.get('street'), 'speed_limit_mph': s.get('postvz_sl')}, s['the_geom'])
                         for i, s in enumerate(load(area, 'layer_speed_limits')) if s.get('the_geom') and mine_g(s['the_geom'])]

    # H. Transit ------------------------------------------------------------------------------------------------------
    T['subway_stations'] = [F(s['gtfs_stop_id'], {k: s.get(k) for k in ('station_id', 'complex_id', 'stop_name', 'daytime_routes', 'line', 'structure', 'ada', 'ada_notes')}, pt(s['gtfs_longitude'], s['gtfs_latitude']))
                            for s in load(area, 'layer_subway_stations') if mine(float(s['gtfs_longitude']), float(s['gtfs_latitude']))]
    T['subway_entrances'] = [F(f"{r.get('gtfs_stop_id')}-{area}-{i}", {k: r.get(k) for k in ('stop_name', 'daytime_routes', 'line', 'division', 'entrance_type', 'entry_allowed', 'exit_allowed', 'station_id', 'gtfs_stop_id')},
                               pt(r['entrance_longitude'], r['entrance_latitude'])) for i, r in enumerate(load(area, 'layer_subway')) if r.get('entrance_latitude') and mine(float(r['entrance_longitude']), float(r['entrance_latitude']))]
    T['bike_share'] = [F(s['station_id'], {'name': s.get('name'), 'short_name': s.get('short_name'), 'capacity': s.get('capacity'), 'station_type': s.get('station_type')}, pt(s['lon'], s['lat']))
                       for s in load(area, 'layer_citibike')['stations'] if mine(s['lon'], s['lat'])]
    for feats in T.values():
        for f in feats:
            f['properties']['area'] = area
    return T, graph['metadata']['network_version']


def merge_tiles(tileset, area, feats):
    """Replace `area`'s features in every tile of `tileset` with `feats`; Manhattan's (no "area") and other areas' stay."""
    d = os.path.join(U.TILES, tileset)
    os.makedirs(d, exist_ok=True)
    new = {}
    for f in feats:
        xs, ys = zip(*(U.xy(*p) for p in U.coords_of(f['geometry'])))
        (tx0, ty0), (tx1, ty1) = U.tile_of(min(xs), min(ys)), U.tile_of(max(xs), max(ys))
        for tx in range(tx0, tx1 + 1):
            for ty in range(ty0, ty1 + 1):
                new.setdefault(f'{tx}_{ty}', []).append(f)
    keys = set(new) | {n[:-5] for n in os.listdir(d) if n.endswith('.json')}
    counts = {}
    for key in keys:
        path = os.path.join(d, key + '.json')
        old = json.load(open(path))['features'] if os.path.exists(path) else []
        keep = [f for f in old if f['properties'].get('area') != area]
        seen = {f['properties']['feature_id'] for f in keep}
        out = keep + [f for f in new.get(key, []) if f['properties']['feature_id'] not in seen and not seen.add(f['properties']['feature_id'])]
        if out:
            with open(path + '.tmp', 'w', encoding='utf-8') as fh:
                json.dump({'type': 'FeatureCollection', 'features': out}, fh, separators=(',', ':'), ensure_ascii=False)
            os.replace(path + '.tmp', path)
            counts[key] = len(out)
        elif os.path.exists(path):
            os.remove(path)
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', choices=[a for a in AREAS], action='append', help='default: Brooklyn and western Queens')
    areas = ap.parse_args().area or list(AREAS)
    t0 = time.time()
    area_of = SegmentArea()
    catalog = json.load(open(os.path.join(U.OUT, 'catalog.json')))
    built = datetime.now(timezone.utc).isoformat(timespec='seconds')
    meta = dict(catalog.get('areas') or {})
    for area in areas:
        T, net = area_tiles(area, area_of)
        for tid, feats in T.items():
            assert tid not in MANHATTAN_ONLY and tid in catalog['tilesets'], tid
            catalog['tilesets'][tid]['tiles'] = merge_tiles(tid, area, feats)
        meta[area] = {'label': AREAS[area]['label'], 'built_at': built, 'network_version': net, 'features': {tid: len(f) for tid, f in T.items()}}
        print(area, sum(len(f) for f in T.values()), 'features', json.dumps({k: len(v) for k, v in T.items()}), flush=True)
    covered = ['manhattan'] + [a for a in AREAS if a in meta]
    for tid, ts in catalog['tilesets'].items():
        ts['features'] = len({f['properties']['feature_id'] for key in ts['tiles'] for f in json.load(open(os.path.join(U.TILES, tid, key + '.json')))['features']})
        ts['areas'] = ['manhattan'] if tid in MANHATTAN_ONLY else covered
    for d in catalog['datasets']:
        ts = catalog['tilesets'].get(d.get('tileset'))
        if ts:
            d['feature_count'] = ts['features']
            d['coverage'] = ', '.join(NAME[a] for a in ts['areas'])
    catalog['areas'] = meta
    catalog['note'] = (catalog.get('note') or '').split(' Brooklyn and western Queens:')[0] + (
        ' Brooklyn and western Queens: added by scripts/build_area_layers.py; building footprints, tax lots, activity places, '
        'noise complaints and sidewalk surface are Manhattan only.')
    with open(os.path.join(U.OUT, 'catalog.json'), 'w') as fh:
        json.dump(catalog, fh, indent=1, ensure_ascii=False)
    print(f'done in {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
