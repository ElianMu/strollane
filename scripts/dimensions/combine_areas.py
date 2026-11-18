"""Rank Manhattan, Brooklyn and western Queens on ONE scale (approved by the project owner on 2026-11-17).

    python3 -m scripts.dimensions.combine_areas

Each area is first built on its own (build.py for Manhattan, area_build.py for the others). That gives raw indicator
values per segment, measured with identical definitions, and percentiles ranked within the area. This step keeps every
raw value exactly as it is and re-ranks: for each scored indicator, a segment's percentile is its rank among ALL
segments of the three areas (same rule as scoring.percentile: ties take the lowest rank, "lower is better" reversed,
N/A stays N/A). Dimension scores are then the equal-weight mean of the available indicator percentiles, as before.

So a score of 80 means "better than 80 % of street segments in Manhattan, Brooklyn and western Queens together",
and a Brooklyn 80 and a Manhattan 80 mean the same thing. Routes that cross the East River can compare them.

Each area's files in data/dimensions/<area>/ are rewritten in place with the combined percentiles and scores. Their
manifest keeps the area's own build version as `raw_calculation_version` and gets a new `calculation_version` that
hashes this file and the three raw builds. data/dimensions/combined.json lists the areas and that version.

Run again after rebuilding any one area; it reads the raw values, so it gives the same result every time.
"""
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np

from . import scoring, spec

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'dimensions')
AREAS = ['manhattan', 'brooklyn', 'lic']
AREA_NAME = {'manhattan': 'Manhattan', 'brooklyn': 'Brooklyn', 'lic': 'western Queens'}  # 'lic' is the western Queens box (scripts/areas.py)
COMBINED = os.path.join(OUT, 'combined.json')


def arr(v):
    return np.array([np.nan if x is None else x for x in v], float)


def num(v, nd):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def load(area):
    d = os.path.join(OUT, area)
    m = json.load(open(os.path.join(d, 'manifest.json')))
    ind = json.load(open(os.path.join(d, 'indicators.json')))
    seg = json.load(open(os.path.join(d, 'segments.geojson')))
    raw_version = m.get('raw_calculation_version', m['calculation_version'])
    return m, ind, seg, raw_version


def main():
    data = {a: load(a) for a in AREAS}
    sizes = {a: len(data[a][1]['ids']) for a in AREAS}
    n_all = sum(sizes.values())
    h = hashlib.sha1(open(__file__, 'rb').read())
    for a in AREAS:
        h.update(f'{a}:{data[a][3]}'.encode())
    version = f'{spec.SPEC_VERSION}+nyc3-{h.hexdigest()[:10]}'

    scored = [x['key'] for x in spec.INDICATORS if x['role'] in spec.SCORED_ROLES]
    # Every scored indicator either exists in all three areas or in none (canopy / impervious): never rank a partial set.
    present = [k for k in scored if all(k in data[a][1]['raw'] for a in AREAS)]
    partial = [k for k in scored if k not in present and any(k in data[a][1]['raw'] for a in AREAS)]
    if partial:
        sys.exit(f'indicators present in some areas only: {partial}; rebuild the missing areas first.')

    combined_pct = {}
    for k in present:
        allv = np.concatenate([arr(data[a][1]['raw'][k]) for a in AREAS])
        combined_pct[k] = scoring.percentile(allv, invert=spec.BY_KEY[k]['role'] == 'down')

    built_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    start, summary = 0, {}
    for a in AREAS:
        m, ind, seg, raw_version = data[a]
        n = sizes[a]
        pct = {k: v[start:start + n] for k, v in combined_pct.items()}
        start += n
        scores, counts = scoring.aggregate(pct, n)
        before = {dim: np.array([np.nan if f['properties'][f'd{j}'] is None else f['properties'][f'd{j}'] for f in seg['features']])
                  for j, dim in enumerate(spec.DIM_KEYS)}
        for i, f in enumerate(seg['features']):
            p = f['properties']
            dims = []
            for j, dim in enumerate(spec.DIM_KEYS):
                s = scores[dim][i]
                p[f'd{j}'] = None if not np.isfinite(s) else round(float(s), 1)
                p[f'n{j}'] = int(counts[dim][i])
                if np.isfinite(s):
                    dims.append(s)
            p['overall'] = round(float(np.mean(dims)), 1) if dims else None
            p['coverage'] = len(dims)
        seg['metadata'] = {**seg.get('metadata', {}), 'calculation_version': version, 'raw_calculation_version': raw_version}
        ind['pct'] = {**{k: v for k, v in ind['pct'].items() if k not in pct}, **{k: [num(x, 1) for x in v] for k, v in pct.items()}}
        ind['calculation_version'], ind['raw_calculation_version'] = version, raw_version
        m['raw_calculation_version'] = raw_version
        m['calculation_version'] = version
        m['combined_at'] = built_at
        m['comparison_scope'] = (f'Percentiles are ranked among the {n_all:,} street segments of Manhattan, Brooklyn and western Queens '
                                 f'together ({", ".join(f"{sizes[x]:,} {AREA_NAME[x]}" for x in AREAS)}); this area has {n:,}. One scale for all three areas '
                                 '(scripts/dimensions/combine_areas.py).')
        for d in m['dimensions']:
            j = int(d['prop'][1:])
            s = scores[spec.DIM_KEYS[j]]
            d['segments_with_score'], d['segment_coverage'] = int(np.isfinite(s).sum()), round(float(np.isfinite(s).mean()), 4)
        if a == 'manhattan' and m.get('validation', {}).get('urban_vibrancy_vs_ped_flow') and 'ped_flow_observed' in ind['raw']:
            from scipy.stats import spearmanr
            flow, vi = arr(ind['raw']['ped_flow_observed']), arr(ind['raw']['vibr_idx'])
            ok = np.isfinite(flow) & np.isfinite(vi)
            m['validation']['urban_vibrancy_vs_ped_flow']['spearman_dimension_score'] = round(float(spearmanr(flow[ok], scores['urban_vibrancy'][ok]).correlation), 3)
        d = os.path.join(OUT, a)
        for name, obj in (('segments.geojson', seg), ('indicators.json', ind), ('manifest.json', m)):
            tmp = os.path.join(d, name + '.tmp')
            json.dump(obj, open(tmp, 'w'), ensure_ascii=False, separators=(',', ':') if name != 'manifest.json' else None,
                      indent=None if name != 'manifest.json' else 1, allow_nan=False)
            os.replace(tmp, os.path.join(d, name))
        moved = {}
        for dim in spec.DIM_KEYS:
            b, c = before[dim], scores[dim]
            ok = np.isfinite(b) & np.isfinite(c)
            moved[dim] = {'median_before': round(float(np.median(b[ok])), 1), 'median_after': round(float(np.median(c[ok])), 1),
                          'moved_over_20': round(float((np.abs(b[ok] - c[ok]) > 20).mean()), 3)}
        summary[a] = {'segments': n, 'raw_calculation_version': raw_version, 'change_from_previous_scale': moved}
    doc = {'calculation_version': version, 'combined_at': built_at, 'areas': AREAS, 'segments': sizes, 'total_segments': n_all,
           'indicators_ranked': present, 'not_ranked': [k for k in scored if k not in present],
           'method': 'Raw values per area unchanged; each scored indicator re-ranked as a percentile among all segments of the listed areas.',
           'summary': summary}
    json.dump(doc, open(COMBINED, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({'calculation_version': version, 'segments': sizes}, ensure_ascii=False))
    for a in AREAS:
        print(a, {dim: (v['median_before'], v['median_after'], v['moved_over_20']) for dim, v in summary[a]['change_from_previous_scale'].items()})
    return 0


if __name__ == '__main__':
    sys.exit(main())
