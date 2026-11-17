#!/usr/bin/env python3
"""Match a new area's street segments to its walk network, and measure the edges that match no street.

    python3 scripts/match_area.py --area lic
    python3 scripts/match_area.py --area brooklyn

The Manhattan pipeline for the same step is scripts/match_lion_osm.py; this runs its matching function
(match_geometries) unchanged, on:
  data/pedestrian/<area>-walk-graph.json.gz         the area's OSM walk network (build_pedestrian_network.py --area)
  data/dimensions/<area>/segments.geojson            the area's LION analysis segments (scripts/dimensions/area_build.py)
and measures every routable edge that is mostly unmatched (crossings, park paths, bridges) with the same indicator
code as Manhattan (streetwise_indicators.Measurer, records within distance) on the area's own downloads
(data/cache/sources/<area>/, scripts/download_area_sources.py).

Writes, in the same format as Manhattan's files:
  data/pedestrian/<area>-street_osm_edge_mapping.csv.gz
  data/pedestrian/<area>-edge-scores.json.gz          matching and raw values; the 12 scores are left empty here and
                                                       filled by scripts/transfer_dimension_scores.py --area <area>
"""
import argparse
import csv
import gzip
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import match_lion_osm as M  # noqa: E402
import streetwise_indicators as si  # noqa: E402

ROOT = si.ROOT
SOURCE_NAMES = ['streets_v4', 'lpc', 'forestry_trees', 'parks', 'sidewalks', 'noise', 'collisions', 'subway', 'osm']


def files(area):
    p = os.path.join(ROOT, 'data', 'pedestrian')
    return {'graph': os.path.join(p, f'{area}-walk-graph.json.gz'), 'segments': os.path.join(ROOT, 'data', 'dimensions', area, 'segments.geojson'),
            'manifest': os.path.join(ROOT, 'data', 'dimensions', area, 'manifest.json'), 'cache': os.path.join(ROOT, 'data', 'cache', 'sources', area),
            'mapping': os.path.join(p, f'{area}-street_osm_edge_mapping.csv.gz'), 'scores': os.path.join(p, f'{area}-edge-scores.json.gz')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', required=True, choices=['brooklyn', 'lic'])
    area = ap.parse_args().area
    F = files(area)
    t0 = time.time()
    graph = json.load(gzip.open(F['graph'], 'rt', encoding='utf-8'))
    feats = json.load(open(F['segments'], encoding='utf-8'))['features']
    manifest = json.load(open(F['manifest'], encoding='utf-8'))
    segs, info = M.match_geometries(graph, feats, t0)
    geoms, edges = graph['geoms'], graph['edges']

    direct = [gi for gi, x in info.items() if x['frac'] < M.MIN_LION_SHARE and x['routable']]
    print(f'Measuring {len(direct)} unmatched routable edges directly…', flush=True)
    raw = {k: json.load(open(os.path.join(F['cache'], k + '.json'), encoding='utf-8')) for k in SOURCE_NAMES}
    items = [si.make_item(geoms[gi], path=info[gi]['kind'] != 'road', width=None) for gi in direct]
    t1 = time.time()
    values = si.Measurer(raw).measure(items, nearest_snap=False) if items else {}
    print(f'  measured in {time.time() - t1:.0f}s', flush=True)
    pos = {gi: n for n, gi in enumerate(direct)}

    stats, out = {'lion': 0, 'direct': 0, 'none': 0}, []
    for gi in range(len(geoms)):
        x = info[gi]
        if x['frac'] >= M.MIN_LION_SHARE:
            rows = x['rows']
            q = 'high' if x['frac'] >= .9 and all(r['angle'] <= 8 for r in rows.values()) else 'medium' if x['frac'] >= .75 else 'low'
            src, rawv = 'lion_match', None
            stats['lion'] += 1
        elif gi in pos:
            q, src = 'direct_measurement', 'direct_osm'
            rawv = {k: values[k][pos[gi]] for k in values}
            stats['direct'] += 1
        else:
            q, src, rawv = 'unscored', 'none', None
            stats['none'] += 1
        out.append({'s': [None] * 12, 'o': None, 'c': [0.0] * 12, 'src': src, 'q': q, 'kind': x['kind'], 'frac': round(x['frac'], 2),
                    'm': sorted(segs[i]['p']['id'] for i in x['rows']), **({'raw': rawv} if rawv else {})})

    gmeta = graph['metadata']
    versions = {'network_version': gmeta['network_version'], 'score_version': manifest['calculation_version'],
                'data_version': (manifest.get('windows', {}).get('retrieved_at') or manifest['built_at'])[:10]}
    meta = {**versions, 'area': area, 'built_at': si.NOW.isoformat(timespec='seconds'), 'keys': [d['key'] for d in manifest['dimensions']],
            'geometries': len(out), 'sources': stats, 'routable_length_coverage_by_dimension': {},
            'fields': {'s': '12 dimension scores (None = N/A)', 'o': 'overall', 'c': 'per-dimension coverage share of edge length',
                       'src': 'lion_match | direct_osm | none', 'q': 'match quality', 'm': 'matched analysis segment IDs',
                       'frac': 'share of edge length matched to LION', 'raw': 'directly measured sub-indicators'},
            'method': 'Matching: scripts/match_lion_osm.match_geometries. Direct edges measured with streetwise_indicators.Measurer on the '
                      f'area downloads. Scores filled by scripts/transfer_dimension_scores.py --area {area}.'}
    with gzip.open(F['scores'] + '.tmp', 'wt', encoding='utf-8') as f:
        json.dump({'metadata': meta, 'geoms': out}, f, separators=(',', ':'), ensure_ascii=False)
    os.replace(F['scores'] + '.tmp', F['scores'])

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['mapping_id', 'lion_segment_id', 'analysis_segment_id', 'osm_edge_id', 'graph_u', 'graph_v', 'graph_key', 'osm_way_ids',
                'overlap_length', 'overlap_share', 'match_distance', 'angle_difference', 'name_check', 'match_quality', 'matching_method', 'used_for_scores',
                'network_version', 'score_version', 'data_version'])
    mid = 0
    for u, v, k, gi, rev, length, osmids, tags in edges:
        x = info[gi]
        for i, r in sorted(x['rows'].items(), key=lambda y: segs[y[0]]['p']['id']):
            mid += 1
            p = segs[i]['p']
            q = 'high' if r['angle'] <= 8 and r['dist'] <= (20 if x['kind'] == 'sidewalk' else 6) else 'medium' if r['angle'] <= 14 else 'low'
            w.writerow([mid, p['id'].split('-', 1)[1].split('-')[0], p['id'], f'{u}-{v}-{k}', u, v, k, ' '.join(map(str, osmids)),
                        round(r['overlap'], 1), round(r['overlap'] / (x['len'] or 1), 2), round(r['dist'], 1), round(r['angle'], 1), r['name'], q,
                        {'sidewalk': 'sidewalk_offset', 'road': 'centerline_overlap'}.get(x['kind'], 'path_overlap') + '+direction+name+layer',
                        x['frac'] >= M.MIN_LION_SHARE, *versions.values()])
    with gzip.open(F['mapping'] + '.tmp', 'wt', encoding='utf-8', newline='') as f:
        f.write(buf.getvalue())
    os.replace(F['mapping'] + '.tmp', F['mapping'])
    print(json.dumps({'area': area, **stats, 'mapping_rows': mid, 'seconds': round(time.time() - t0)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
