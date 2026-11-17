"""Committed 12-dimension outputs for Brooklyn and Long Island City (scripts/dimensions/area_build.py).

Run: python3 -m unittest tests.test_area_dimensions
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from scripts.dimensions import build, spec  # noqa: E402
from areas import AREAS  # noqa: E402

D = ROOT / 'data' / 'dimensions'
MANHATTAN = json.load(open(D / 'manhattan' / 'manifest.json'))
PREFIX = {'brooklyn': 'BK-', 'lic': 'QN-'}


def load(area):
    return (json.load(open(D / area / 'manifest.json')), json.load(open(D / area / 'segments.geojson'))['features'],
            json.load(open(D / area / 'indicators.json')))


class AreaDimensions(unittest.TestCase):
    def test_manhattan_build_is_untouched(self):
        """area_build patches loaders at run time; it must not change the Manhattan code hash or outputs."""
        self.assertEqual(build.calc_version(), MANHATTAN['calculation_version'])

    def test_each_area(self):
        for area in ('brooklyn', 'lic'):
            with self.subTest(area=area):
                m, feats, ind = load(area)
                self.assertEqual(m['area'], area)
                self.assertNotEqual(m['calculation_version'], MANHATTAN['calculation_version'])
                self.assertTrue(m['calculation_version'].startswith(spec.SPEC_VERSION + '+'))
                self.assertEqual([d['label'] for d in m['dimensions']], [d['label'] for d in MANHATTAN['dimensions']], 'same 12 dimensions, same order')
                self.assertEqual(len(feats), m['segments']); self.assertEqual(ind['ids'], [f['properties']['id'] for f in feats])
                self.assertTrue(all(i.startswith(PREFIX[area]) for i in ind['ids'])); self.assertEqual(len(set(ind['ids'])), len(ind['ids']))
                self.assertIn('not on the same scale as Manhattan', m['comparison_scope'])
                for k in ('ped_counts', 'dohmh_no2'):
                    self.assertIsNone(m['sources'][k]['file']); self.assertEqual(m['sources'][k]['status'], 'not available for this area')
                self.assertFalse((D / area / 'context_no2.geojson').exists(), 'no Manhattan NO2 layer in another area')
                for k in ('ped_flow_observed', 'no2_area_context', 'canopy_pct', 'impervious_pct'):
                    self.assertNotIn(k, ind['raw'], f'{k} is not computed for this area')
                for f in feats[::97]:
                    p = f['properties']
                    for j in range(12):
                        v = p[f'd{j}']
                        self.assertTrue(v is None or 0 <= v <= 100)
                        self.assertEqual(v is None, p[f'n{j}'] == 0, 'N/A exactly when no indicator contributed')
                for x in m['indicators']:
                    if x['role'] in spec.SCORED_ROLES and x['status'] == 'computed':
                        self.assertGreater(x['coverage'], 0.8, x['key'])
                lion = m['sources']['lion']['qa']
                self.assertEqual(lion['file'], f'data/cache/sources/{area}/streets_v4.json')

    def test_percentiles_are_ranked_within_the_area(self):
        """The top-ranked segment of an area scores 100 on an 'up' indicator, whatever Manhattan's values are."""
        for area in ('brooklyn', 'lic'):
            _, _, ind = load(area)
            vals = [v for v in ind['raw']['tree_km'] if v is not None]
            pct = [p for p, v in zip(ind['pct']['tree_km'], ind['raw']['tree_km']) if v == max(vals)]
            self.assertEqual(pct[0], 100.0)

    def test_lic_is_inside_its_box(self):
        w, s, e, n = AREAS['lic']['box']
        _, feats, _ = load('lic')
        for f in feats:
            c = f['geometry']['coordinates']; x, y = c[len(c) // 2]
            self.assertTrue(w - .01 <= x <= e + .01 and s - .01 <= y <= n + .01)


if __name__ == '__main__':
    unittest.main()
