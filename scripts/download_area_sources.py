#!/usr/bin/env python3
"""Download the public source records for a study area other than Manhattan (Brooklyn, Long Island City).

This is the first step of extending STROLLANE beyond Manhattan and the only one that needs open internet access to
NYC Open Data, data.ny.gov, ArcGIS and Overpass. It downloads; it scores nothing and changes nothing the app reads.

Standard library only. Run from the repository root, on a computer with normal internet access:

    python3 scripts/download_area_sources.py                # Brooklyn and Long Island City
    python3 scripts/download_area_sources.py --area lic     # one area
    python3 scripts/download_area_sources.py --places       # only the place-recommendation sources (below)

Writes data/cache/sources/<area>/<name>.json (git-ignored) and data/cache/sources/<area>/download-report.json, which
lists every source with its record count, size, time, query and any error. A finished source is not downloaded again;
rerun the same command to retry only what failed, or pass --refresh to download everything again.

The queries are those of scripts/streetwise_indicators.py download_sources() (the Manhattan build) with the borough
swapped, plus the pedestrian-ramp survey the map build reads. Nothing is invented for a source that returns nothing:
its error or empty count is written to the report.

Place-recommendation sources (read by scripts/build_area_places.py, the discovery index of food, cafés, sights and
hotels): places_osm (the Overpass query of scripts/build_place_index.py, all tags it keeps), lpc_places (landmark lots
with name, address, date, style and report), restrooms (NYC Public Restrooms cut to the box), hotel_lots (NYC DOF
hotel-class tax lots in the borough) and wikidata (sitelink counts for the Wikidata IDs in places_osm).
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib import parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import streetwise_indicators as si  # noqa: E402  (get / socrata / arcgis helpers and the source URLs)
from areas import AREAS, in_box, touches_box  # noqa: E402

RAMPS = si.SOCRATA + 'ufzp-rrqu.json'  # NYC DOT Pedestrian Ramp Locations (scripts/build_urban_layers.py)
OSM_TILE_DEG = 0.06                    # Overpass is asked for the area in tiles of this size, so no request times out


def points(rows, box, lat='latitude', lon='longitude'):
    """(lon, lat) of every row with usable coordinates inside the area's box. si.latlon_points() is not used: it keeps
    only points inside the MANHATTAN box, which would silently drop every Brooklyn record."""
    out = []
    for r in rows:
        try:
            p = (float(r[lon]), float(r[lat]))
        except (KeyError, TypeError, ValueError):
            continue
        if in_box(p[0], p[1], box):
            out.append(p)
    return out


def osm_tiles(box, step=OSM_TILE_DEG):
    w, s, e, n = box
    y = s
    while y < n - 1e-9:
        x = w
        while x < e - 1e-9:
            yield (x, y, min(x + step, e), min(y + step, n))
            x += step
        y += step


OVERPASS = [si.SOURCES['osm'], 'https://overpass.kumi.systems/api/interpreter', 'https://overpass.private.coffee/api/interpreter']


def overpass(query):
    """One Overpass request. The public servers answer 502/504/429 when busy, so each is tried in turn, three rounds."""
    last = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                return si.get(url, data=parse.urlencode({'data': query}).encode(), timeout=240, tries=1)
            except Exception as e:
                last = e
                time.sleep(5 * (attempt + 1))
    raise RuntimeError(f'Overpass unavailable on {len(OVERPASS)} servers: {last}')


def fetch_osm(box, tile_dir=None):
    """Named places and amenities, as fetch_osm() of the Manhattan build, tile by tile; an element is kept once.
    With tile_dir each finished tile is kept on disk, so a busy server costs one tile, not the whole area."""
    seen, out = set(), []
    for i, (w, s, e, n) in enumerate(osm_tiles(box)):
        path = tile_dir and os.path.join(tile_dir, f'{i:03d}.json')
        if path and os.path.exists(path):
            elements = json.load(open(path))
        else:
            b = f'{s},{w},{n},{e}'
            q = (f'[out:json][timeout:180];(nwr["amenity"]({b});nwr["shop"]({b});nwr["tourism"]({b});nwr["leisure"]({b});'
                 f'nwr["historic"]({b}););out tags center;')
            elements = overpass(q)['elements']
            if path:
                os.makedirs(tile_dir, exist_ok=True)
                with open(path + '.tmp', 'w') as f:
                    json.dump(elements, f)
                os.replace(path + '.tmp', path)
            print(f'    osm tile {i + 1}: {len(elements):,} elements', flush=True)
            time.sleep(2)  # be polite to the public Overpass servers
        for x in elements:
            key = (x['type'], x['id'])
            if key in seen:
                continue
            seen.add(key)
            lat, lon = (x.get('lat'), x.get('lon')) if x['type'] == 'node' else (x.get('center', {}).get('lat'), x.get('center', {}).get('lon'))
            if lat is None:
                continue
            t = x.get('tags', {})
            out.append([lon, lat, {k: t[k] for k in ('amenity', 'shop', 'tourism', 'leisure', 'historic', 'name') if k in t}])
    return out


# Place-recommendation sources: same query and tags as scripts/build_place_index.py, so area records match Manhattan's.
PLACE_TAGS = ('name', 'tourism', 'historic', 'amenity', 'shop', 'leisure', 'cuisine', 'opening_hours', 'website', 'website:menu', 'wikidata',
              'wikipedia', 'brand', 'operator', 'stars', 'wheelchair', 'addr:housenumber', 'addr:street', 'phone', 'fee', 'toilets:wheelchair',
              'charge', 'reservation', 'description', 'rooms', 'beds', 'internet_access', 'air_conditioning', 'check_in', 'check_out', 'contact:phone',
              'contact:website', 'diet:vegetarian', 'diet:vegan', 'outdoor_seating', 'takeaway', 'delivery', 'payment:cash', 'access')


def place_query(b):
    return (f'[out:json][timeout:180];(nwr["tourism"]["name"]({b});nwr["historic"]["name"]({b});'
            f'nwr["amenity"~"^(cafe|restaurant|fast_food|bar|pub|ice_cream|pharmacy|hospital|clinic|bank|atm|toilets|marketplace|arts_centre|theatre|library|place_of_worship|luggage_locker)$"]({b});'
            f'nwr["shop"~"^(bakery|pastry|confectionery|supermarket|convenience|mall|department_store|chemist|deli|coffee|books|gift|luggage_storage)$"]({b});'
            f'nwr["leisure"~"^(park|garden|nature_reserve)$"]["name"]({b}););out tags center;')


def fetch_places(box, tile_dir=None):
    """Discovery places, tile by tile (finished tiles kept on disk). Returns {"osm_timestamp", "elements"} with each element
    once, its position (node or centre) and the tags scripts/build_place_index.py reads (plus drink:* and diet:*)."""
    seen, out, stamp = set(), [], None
    for i, (w, s, e, n) in enumerate(osm_tiles(box)):
        path = tile_dir and os.path.join(tile_dir, f'{i:03d}.json')
        if path and os.path.exists(path):
            d = json.load(open(path))
        else:
            d = overpass(place_query(f'{s},{w},{n},{e}'))
            d = {'stamp': d.get('osm3s', {}).get('timestamp_osm_base'), 'elements': d['elements']}
            if path:
                os.makedirs(tile_dir, exist_ok=True)
                with open(path + '.tmp', 'w') as f:
                    json.dump(d, f)
                os.replace(path + '.tmp', path)
            print(f'    place tile {i + 1}: {len(d["elements"]):,} elements', flush=True)
            time.sleep(2)
        stamp = max(filter(None, (stamp, d['stamp'])), default=None)
        for x in d['elements']:
            if (x['type'], x['id']) in seen:
                continue
            seen.add((x['type'], x['id']))
            lat, lon = (x.get('lat'), x.get('lon')) if x['type'] == 'node' else (x.get('center', {}).get('lat'), x.get('center', {}).get('lon'))
            if lat is None:
                continue
            t = x.get('tags', {})
            out.append({'type': x['type'], 'id': x['id'], 'lat': lat, 'lon': lon,
                        'tags': {k: v for k, v in t.items() if k in PLACE_TAGS or k.startswith(('drink:', 'diet:'))}})
    return {'osm_timestamp': stamp, 'elements': out}


def fetch_wikidata(area):
    """{QID: [sitelinks, English label, English description, official website]} for the Wikidata IDs in places_osm."""
    d = json.load(open(os.path.join(ROOT, 'data', 'cache', 'sources', area, 'places_osm.json')))
    ids = sorted({x['tags']['wikidata'] for x in d['elements'] if str(x['tags'].get('wikidata', '')).startswith('Q')})
    out = {}
    for k in range(0, len(ids), 50):
        q = parse.urlencode({'action': 'wbgetentities', 'ids': '|'.join(ids[k:k + 50]), 'props': 'sitelinks|labels|descriptions|claims', 'languages': 'en', 'format': 'json'})
        for attempt in range(4):
            try:
                r = si.get('https://www.wikidata.org/w/api.php?' + q, timeout=60, tries=1)
                break
            except Exception:
                r = None
                time.sleep(5 * (attempt + 1))
        if not r:
            raise RuntimeError('Wikidata unavailable')
        for qid, ent in r.get('entities', {}).items():
            if 'sitelinks' in ent:
                site = next((c['mainsnak'].get('datavalue', {}).get('value') for c in ent.get('claims', {}).get('P856', []) if c.get('mainsnak', {}).get('datavalue')), None)
                out[qid] = [len(ent['sitelinks']), ent.get('labels', {}).get('en', {}).get('value', ''), ent.get('descriptions', {}).get('en', {}).get('value'), site]
        time.sleep(1)
    return out


PLACE_SOURCES = ('places_osm', 'lpc_places', 'restrooms', 'hotel_lots', 'wikidata')


def jobs_for(area, now=None):
    """{source name: (description of the query, function returning the records)} for one area."""
    a = AREAS[area]
    w, s, e, n = a['box']
    now = now or datetime.now(timezone.utc)
    noise_from = (now - timedelta(days=365)).strftime('%Y-%m-%dT00:00:00')
    crash_from = (now - timedelta(days=365 * 3)).strftime('%Y-%m-%dT00:00:00')
    box_sql = f'{n},{w},{s},{e}'  # Socrata within_box(north, west, south, east)
    clip = a['clip_to_box']
    feats = (lambda rows: [f for f in rows if touches_box(f.get('geometry'), a['box'])]) if clip else (lambda rows: rows)
    in_lat_lon = f" AND latitude>{s} AND latitude<{n} AND longitude>{w} AND longitude<{e}" if clip else ''
    q = {
        'streets_v4': (f"NYC Street Centerline, borocode='{a['borocode']}'",
                       lambda: feats(si.arcgis(si.SOURCES['streets'], f"borocode='{a['borocode']}'", 'FID,physicalid,rw_type,st_label,st_name,st_width'))),
        'lpc': (f"LPC individual landmark lots, BORO='{a['lpc_boro']}'",
                lambda: feats(si.arcgis(si.SOURCES['lpc'], f"BORO='{a['lpc_boro']}'", 'FID,LPC_NAME'))),
        'forestry_trees': (f"Forestry tree points, tpstructure='Full', within_box({box_sql})",
                           lambda: [p['location']['coordinates'] for p in si.socrata(si.SOURCES['trees'], 'location', f"tpstructure='Full' AND within_box(location,{box_sql})") if p.get('location')]),
        'parks': (f"Parks properties, borough='{a['parks_borough']}'",
                  lambda: [r for r in si.socrata(si.SOURCES['parks'], 'signname,typecategory,multipolygon', f"borough='{a['parks_borough']}'") if not clip or touches_box(r.get('multipolygon'), a['box'])]),
        'sidewalks': (f'Sidewalk polygons, within_box({box_sql})',
                      lambda: si.socrata(si.SOURCES['sidewalks'], 'the_geom', f'within_box(the_geom,{box_sql})', 5000)),
        'noise': (f"311 noise complaints since {noise_from[:10]}, borough='{a['borough_upper']}', inside the area's box",
                  lambda: points(si.socrata(si.SOURCES['noise'], 'latitude,longitude', f"borough='{a['borough_upper']}' AND starts_with(complaint_type,'Noise') AND created_date>='{noise_from}'{in_lat_lon}"), a['box'])),
        'collisions': (f"Crashes with pedestrians injured or killed since {crash_from[:10]}, borough='{a['borough_upper']}', inside the area's box",
                       lambda: points(si.socrata(si.SOURCES['collisions'], 'latitude,longitude', f"borough='{a['borough_upper']}' AND (number_of_pedestrians_injured>0 OR number_of_pedestrians_killed>0) AND crash_date>='{crash_from}'"), a['box'])),
        'subway': ("Subway entrances with entry allowed, all boroughs, cut to the area's box",
                   lambda: points(si.socrata(si.SOURCES['subway'], 'entrance_latitude,entrance_longitude', "entry_allowed='YES'"), a['box'], 'entrance_latitude', 'entrance_longitude')),
        'ramps': (f'Pedestrian ramp survey, within_box({box_sql})',
                  lambda: si.socrata(RAMPS, 'rampid,cornerid,the_geom', f'within_box(the_geom,{box_sql})')),
        'osm': (f'OpenStreetMap amenity / shop / tourism / leisure / historic elements in the box, {sum(1 for _ in osm_tiles(a["box"]))} Overpass tiles',
                lambda: fetch_osm(a['box'], os.path.join(ROOT, 'data', 'cache', 'sources', area, 'osm-tiles'))),
        'places_osm': (f'OpenStreetMap discovery places (query of scripts/build_place_index.py), {sum(1 for _ in osm_tiles(a["box"]))} Overpass tiles',
                       lambda: fetch_places(a['box'], os.path.join(ROOT, 'data', 'cache', 'sources', area, 'place-tiles'))),
        'lpc_places': (f"LPC individual landmark lots with name, address, date, style and report, BORO='{a['lpc_boro']}'",
                       lambda: feats(si.arcgis(si.SOURCES['lpc'], f"BORO='{a['lpc_boro']}'", 'LPC_LPNumb,LPC_NAME,Address,DesDate,Style_Prim,Arch_Prima,BuildType,Date_Low,URL_REPORT'))),
        'restrooms': ("NYC Open Data Public Restrooms (i7jb-7jku), cut to the area's box",
                      lambda: [r for r in si.socrata(si.SOCRATA + 'i7jb-7jku.json', 'facility_name,location_type,operator,status,open,hours_of_operation,accessibility,website,latitude,longitude', 'latitude IS NOT NULL')
                               if in_box(float(r['longitude']), float(r['latitude']), a['box'])]),
        'hotel_lots': (f"NYC DOF Hotels Properties Citywide (tjus-cn27), borough {a['borough_upper']}",
                       lambda: si.socrata(si.SOCRATA + 'tjus-cn27.json', 'bbl,parid,taxyear,bldg_class,latitude,longitude',
                                          f"borough in('{a['borough_upper']}','{a['borocode']}') and latitude is not null")),
        'wikidata': ('Wikidata sitelinks, labels, descriptions and official websites for the Wikidata IDs in places_osm',
                     lambda: fetch_wikidata(area)),
    }
    return q, {'noise_window_from': noise_from[:10], 'collision_window_from': crash_from[:10]}


def count(rows):
    return len(rows['elements']) if isinstance(rows, dict) and 'elements' in rows else len(rows)


def download(area, refresh=False, only=None):
    cache = os.path.join(ROOT, 'data', 'cache', 'sources', area)
    os.makedirs(cache, exist_ok=True)
    jobs, windows = jobs_for(area)
    report = {'area': area, 'label': AREAS[area]['label'], 'box_west_south_east_north': AREAS[area]['box'], 'windows': windows,
              'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'sources': {}}
    print(f'\n== {AREAS[area]["label"]} ==', flush=True)
    for name, (what, fn) in jobs.items():
        if only and name not in only:
            continue
        path = os.path.join(cache, name + '.json')
        entry = {'query': what}
        if os.path.exists(path) and not refresh:
            entry.update(status='already downloaded', records=count(json.load(open(path))), bytes=os.path.getsize(path))
            print(f'  {name}: already downloaded ({entry["records"]:,} records)', flush=True)
        else:
            t = time.time()
            print(f'  {name}: downloading…', flush=True)
            try:
                rows = fn()
                with open(path + '.tmp', 'w') as f:
                    json.dump(rows, f)
                os.replace(path + '.tmp', path)
                entry.update(status='ok', records=count(rows), bytes=os.path.getsize(path), seconds=round(time.time() - t))
                print(f'  {name}: {count(rows):,} records, {entry["bytes"] / 1e6:.1f} MB, {entry["seconds"]} s', flush=True)
            except Exception as e:  # one source failing must not lose the others; the report says what failed
                entry.update(status='FAILED', error=str(e)[:400], seconds=round(time.time() - t))
                print(f'  {name}: FAILED — {entry["error"]}', flush=True)
        report['sources'][name] = entry
    report['finished_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with open(os.path.join(cache, 'download-report.json'), 'w') as f:
        json.dump(report, f, indent=1)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', choices=list(AREAS), action='append', help='default: every area in scripts/areas.py')
    ap.add_argument('--only', action='append', help='download only this source (repeatable), e.g. --only osm')
    ap.add_argument('--refresh', action='store_true', help='download again even if a file exists')
    ap.add_argument('--places', action='store_true', help='only the place-recommendation sources: ' + ', '.join(PLACE_SOURCES))
    args = ap.parse_args()
    if args.places:
        args.only = list(PLACE_SOURCES)
    failed = []
    for area in args.area or list(AREAS):
        r = download(area, args.refresh, args.only)
        failed += [f'{area}/{k}' for k, v in r['sources'].items() if v['status'] == 'FAILED']
    print('\nDone.' + (f' FAILED: {", ".join(failed)}. Run the same command again to retry only these.' if failed else ' Every source downloaded.'))
    print('Reports: data/cache/sources/<area>/download-report.json')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
