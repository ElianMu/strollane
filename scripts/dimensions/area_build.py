"""Build the 12 Experience Dimensions for a study area other than Manhattan (Brooklyn, Long Island City).

    python3 -m scripts.dimensions.area_build --area lic
    python3 -m scripts.dimensions.area_build --area brooklyn --budget 3000      # resumable, like build.py

It runs the Manhattan build (build.py) unchanged: the same indicator definitions, the same functions, the same
percentile and aggregation rules. Only the inputs are swapped, by pointing the source loaders at the area's own
downloads (scripts/download_area_sources.py) before the build starts:

  LION street segments, landmarks, trees, parks, sidewalks, OSM, 311 noise, crashes, subway, ramps
                                  → data/cache/sources/<area>/
  OSM walk network                → data/pedestrian/<area>-walk-graph.json.gz   (scripts/build_pedestrian_network.py)
  DOT seating, NYPD complaints    → the citywide files already in the repo, filtered to the area's borough
  hydrography, waterfront access  → the citywide files already in the repo (unchanged)

Nothing is borrowed from Manhattan. Two Manhattan-only inputs are NOT used, because no equivalent was downloaded:
  ped_counts (DOT pedestrian counts, 36 Manhattan locations): validation only, never part of a score;
  dohmh_no2 (NO₂ by Manhattan Community District): context only, never part of a score.
Canopy cover and impervious surface stay N/A, exactly as in Manhattan.

Percentiles are ranked among the segments of THIS area, as the method states. A Brooklyn 80 means "better than 80 %
of Brooklyn segments"; it is not on the same scale as a Manhattan 80. The manifest says so in comparison_scope.

This module patches the loaders instead of editing sources.py / build.py, so Manhattan's calculation_version (a hash
of those files) and every Manhattan output stay exactly as they are. An area build's calculation_version hashes this
file and scripts/areas.py too.
"""
import argparse
import hashlib
import json
import os
import pickle
import sys

import numpy as np
import shapely

from . import build, geo, indicators, sources, spec

sys.path.insert(0, os.path.join(sources.ROOT, 'scripts'))
from areas import AREAS  # noqa: E402

PREFIX = {'3': 'BK', '4': 'QN'}                 # LION borocode → segment ID prefix (Manhattan uses MN)
BOROUGH_NAME = {'3': 'Brooklyn', '4': 'Queens'}
MANHATTAN_ONLY = ('ped_counts', 'dohmh_no2')
SKIP = ('ped_flow_observed', 'no2_area_context')  # their only inputs are Manhattan-only (validation / context, never scored)
PAD = 0.01                                       # degrees around the area box for point sources and segment checks


def box_ring(b):
    w, s, e, n = b
    return [(w, s), (e, s), (e, n), (w, n), (w, s)]


def configure(area):
    """Point the map build at one area's inputs. Returns the area description."""
    a = AREAS[area]
    root = f'data/cache/sources/{area}/'
    w, s, e, n = a['box']
    sources.BOX = (w - PAD, s - PAD, e + PAD, n + PAD)
    spec.AREAS[area] = {'label': a['label'], 'polygon': box_ring(a['box']) if a['clip_to_box'] else None}
    files = {'lion': 'streets_v4.json', 'lpc': 'lpc.json', 'trees': 'forestry_trees.json', 'parks': 'parks.json', 'osm': 'osm.json',
             'noise': 'noise.json', 'sidewalks': 'sidewalks.json', 'collisions': 'collisions.json', 'subway': 'subway.json', 'ramps': 'ramps.json'}
    for k, f in files.items():
        spec.SOURCES[k] = {**spec.SOURCES[k], 'file': root + f}
    spec.SOURCES['osm_walk'] = {**spec.SOURCES['osm_walk'], 'file': f'data/pedestrian/{area}-walk-graph.json.gz'}
    for k in MANHATTAN_ONLY:   # a path that does not exist, so build.export() adds no Manhattan context layer
        spec.SOURCES[k] = {**spec.SOURCES[k], 'file': f'(not available for {area})'}
    boro, upper = a['borocode'], a['borough_upper']
    report = sources.load_json(root + 'download-report.json')

    def segments():
        """LION analysis segments, the rule of build_manhattan_streets.lion_segments() with this area's bounds and prefix."""
        import streetwise_indicators as si
        rel = spec.SOURCES['lion']['file']
        raw = {'streets_v4': sources.load_json(rel)}
        skip_types, path_types = {2, 3, 4, 9, 13, 14}, {6, 7}
        bw, bs, be, bn = sources.BOX
        segs, misplaced = [], []
        for p, rw, i, line in si.lion_lines(raw):
            if rw in skip_types:
                continue
            if not all(bw <= x <= be and bs <= y <= bn for x, y in line):
                misplaced.append(p.get('physicalid'))
                continue
            it = si.make_item(line, name=p.get('st_label') or p.get('st_name') or '', width=p.get('st_width') or None,
                              rw=rw, path=rw in path_types, physicalid=p.get('physicalid'), fid=p.get('FID'), part=i)
            if it['len'] >= 1:
                it['pid'] = f"{PREFIX[boro]}-{int(it['physicalid'])}" if it['physicalid'] else f"{PREFIX[boro]}-FID{it['fid']}"
                segs.append(it)
        groups = {}
        for it in segs:
            groups.setdefault(it['pid'], []).append(it)
        for pid, group in groups.items():
            group.sort(key=lambda x: (round(x['line'][0][0], 6), round(x['line'][0][1], 6), round(x['line'][-1][0], 6), round(x['line'][-1][1], 6), len(x['line'])))
            for k, it in enumerate(group):
                it['id'] = pid if len(group) == 1 else f'{pid}-{k + 1}'
        lines = np.array([shapely.linestrings(np.column_stack(sources.TO_M.transform(*np.asarray(x['line']).T))) for x in segs], dtype=object)
        width = np.array([float(x['width']) if x.get('width') not in (None, '', 0) and float(x['width']) > 0 else np.nan for x in segs])
        rec = {'id': np.array([x['id'] for x in segs]), 'name': np.array([x['name'] for x in segs]), 'rw_type': np.array([x['rw'] for x in segs]),
               'is_path': np.array([bool(x['path']) for x in segs]), 'width_ft': width, 'geometry': lines, 'lonlat': [x['line'] for x in segs]}
        rec['length_m'] = shapely.length(lines)
        rec['end_keys'] = [((round(x['line'][0][0], 6), round(x['line'][0][1], 6)), (round(x['line'][-1][0], 6), round(x['line'][-1][1], 6))) for x in segs]
        highways = [shapely.linestrings(np.column_stack(sources.TO_M.transform(*np.asarray(line).T))) for p, rw, i, line in si.lion_lines(raw) if rw in (2, 9)]
        q = sources.qa('lion', rel, len(raw['streets_v4']), len(segs), excluded_types='2 highway, 3 bridge, 4 tunnel, 9 ramp, 13/14 ferry & other non-walkable',
                       scope=f"borocode = '{boro}'" + (' touching the area box' if a['clip_to_box'] else ''), misplaced_outside_area_box=len(misplaced),
                       width_missing=int(np.isnan(width).sum()), expressway_ramp_lines=len(highways), duplicate_ids=int(len(rec['id']) - len(set(rec['id']))))
        return rec, np.array(highways, dtype=object), q

    def lpc():
        lots, q = orig['lpc']()
        q['scope'] = f"BORO='{a['lpc_boro']}' landmark lots" + (' touching the area box' if a['clip_to_box'] else '')
        return lots, q

    def parks():
        g, q = orig['parks']()
        q['scope'] = f"borough = '{a['parks_borough']}'" + (' touching the area box' if a['clip_to_box'] else '')
        return g, q

    def sidewalks():
        g, q = orig['sidewalks']()
        q['scope'] = 'area bounding box'
        return g, q

    def noise(window):
        rel = spec.SOURCES['noise']['file']
        return sources.clean_points(sources.load_json(rel), 'noise', rel, time_window=window, filter=f"complaint_type starts with 'Noise', borough = {upper}")

    def collisions(window):
        rel = spec.SOURCES['collisions']['file']
        return sources.clean_points(sources.load_json(rel), 'collisions', rel, time_window=window, filter=f'pedestrians injured > 0 OR pedestrians killed > 0, borough = {upper}')

    def subway():
        rel = spec.SOURCES['subway']['file']
        return sources.clean_points(sources.load_json(rel), 'subway', rel, filter="entry_allowed = 'YES', inside the area box")

    def seating():
        rel = 'data/urban/context/seating.geojson.gz'
        fs = sources.load_json(rel)['features']
        m = [f['geometry']['coordinates'] for f in fs if (f['properties'].get('boroname') or '').lower() == BOROUGH_NAME[boro].lower() and f.get('geometry')]
        return sources.clean_points(m, 'seating', rel, filter=f"boroname = '{BOROUGH_NAME[boro]}'", citywide_records=len(fs))

    def ramps():
        """DOT ramp survey rows from the area download (Socrata rows, not the Manhattan map tiles); one point per ramp ID."""
        rel = spec.SOURCES['ramps']['file']
        rows = sources.load_json(rel)
        seen, pts = set(), []
        for r in rows:
            g = r.get('the_geom') or {}
            if r.get('rampid') in seen or g.get('type') != 'Point':
                continue
            seen.add(r.get('rampid'))
            pts.append(g['coordinates'])
        return sources.clean_points(pts, 'ramps', rel, duplicate_ramp_ids=len(rows) - len(seen))

    def crime():
        import sqlite3
        import datetime as dt
        rel = spec.SOURCES['nypd_complaints']['file']
        db_path = os.path.expanduser('~/work/complaints.sqlite')
        if not os.path.exists(db_path):
            import gzip
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            with gzip.open(sources.path(rel)) as src, open(db_path, 'wb') as dst:
                dst.write(src.read())
        db = sqlite3.connect(db_path)
        total = db.execute('select count(*) from incidents where borough=?', (upper,)).fetchone()[0]
        rows = db.execute("select lon, lat from incidents where borough=? and law in ('FELONY','MISDEMEANOR')", (upper,)).fetchall()
        d0, d1 = db.execute('select min(day), max(day) from incidents').fetchone()
        return sources.clean_points(rows, 'nypd_complaints', rel, time_window=f'{dt.date.fromordinal(d0)} / {dt.date.fromordinal(d1)}',
                                    borough_all_law_classes=total, filter=f'borough = {upper}, law IN (FELONY, MISDEMEANOR)')

    def windows():
        wnd = report['windows']
        got = report.get('finished_at') or report.get('started_at')
        return {'noise': f"{wnd['noise_window_from']} → {got[:10]} (12 months before retrieval)",
                'collisions': f"{wnd['collision_window_from']} → {got[:10]} (3 years before retrieval)", 'retrieved_at': got}

    orig = {'lpc': sources.lpc, 'parks': sources.parks, 'sidewalks': sources.sidewalks}
    for name, fn in (('segments', segments), ('lpc', lpc), ('parks', parks), ('sidewalks', sidewalks), ('noise', noise), ('collisions', collisions),
                     ('subway', subway), ('seating', seating), ('ramps', ramps), ('crime', crime), ('windows', windows)):
        setattr(sources, name, fn)
    here = [os.path.abspath(__file__), os.path.join(sources.ROOT, 'scripts', 'areas.py')]

    def calc_version():
        h = hashlib.sha1()
        for f in build.CODE_FILES:
            h.update(open(os.path.join(os.path.dirname(build.__file__), f), 'rb').read())
        for f in here:
            h.update(open(f, 'rb').read())
        h.update(area.encode())
        return f'{spec.SPEC_VERSION}+{h.hexdigest()[:10]}'
    build.calc_version = calc_version
    return a


class AreaContext(build.Context):
    """build.Context with the segment cache kept per area (build.Context shares one for Manhattan and its pilot)."""

    def __init__(self, area):
        self.area = area
        d = os.path.join(build.WORK, area)
        os.makedirs(d, exist_ok=True)
        seg_cache = os.path.join(d, 'segments.pkl')
        if os.path.exists(seg_cache):
            self.rec, self.highways, self.seg_qa = pickle.load(open(seg_cache, 'rb'))
        else:
            self.rec, self.highways, self.seg_qa = sources.segments()
            pickle.dump((self.rec, self.highways, self.seg_qa), open(seg_cache, 'wb'))
        self.T = np.flatnonzero(sources.in_area(self.rec, area))
        self.lines = self.rec['geometry'][self.T]
        self.mids = geo.midpoints(self.lines)
        self.mids_ll = np.column_stack(sources.TO_LL.transform(self.mids[:, 0], self.mids[:, 1])) if len(self.mids) else np.zeros((0, 2))
        self._src, self._samples, self._graph, self._nodes = {}, {}, None, None
        self.qa = {'lion': self.seg_qa}


def finish_manifest(area):
    """State plainly in the manifest what this area build did not use."""
    p = os.path.join(build.OUT, area, 'manifest.json')
    m = json.load(open(p))
    prefix = PREFIX[AREAS[area]['borocode']]
    m['id_scheme'] = f'segment_id = "{prefix}-" + LION physicalid (+ "-n" when several LION records share one).'
    for k in MANHATTAN_ONLY:
        m['sources'][k] = {**m['sources'][k], 'file': None, 'status': 'not available for this area',
                           'note': 'Manhattan-only input in this repository; its indicator is validation / context only and never part of a score.'}
    for x in m['indicators']:
        if x['key'] in SKIP:
            x['status'], x['notes'] = 'not available for this area', ['Its only input covers Manhattan. Never part of a score.']
    m['comparison_scope'] += ' Scores are not on the same scale as Manhattan scores: each area is ranked within itself.'
    m['area_definition'] = AREAS[area]
    json.dump(m, open(p + '.tmp', 'w'), ensure_ascii=False, indent=1, allow_nan=False)
    os.replace(p + '.tmp', p)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', choices=list(AREAS), required=True)
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--budget', type=float, default=150, help='seconds per invocation; stages resume on the next run')
    a = ap.parse_args(argv)
    configure(a.area)
    ctx = AreaContext(a.area)
    keys = a.only or [k for k in indicators.COMPUTE if k not in SKIP]
    if not build.run_stages(ctx, keys, a.budget, a.force):
        print('BUDGET: stopped early, run again to continue', flush=True)
        return 3
    build.export(ctx)
    m = finish_manifest(a.area)
    print(json.dumps({'area': a.area, 'segments': m['segments'], 'calculation_version': m['calculation_version'],
                      'dimensions': {d['label']: [d['model_coverage'], d['segment_coverage']] for d in m['dimensions']}}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
