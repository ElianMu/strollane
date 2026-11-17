"""scripts/download_area_sources.py with the network replaced by a stub: queries, clipping, resume and failure handling.

No real records are involved; the stub returns a handful of made-up rows so the plumbing can be checked offline.
Run: python3 -m unittest tests.test_area_sources
"""
import json
import pathlib
import sys
import tempfile
import unittest
from urllib import parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import download_area_sources as D  # noqa: E402
import streetwise_indicators as si  # noqa: E402
from areas import AREAS, in_box, touches_box  # noqa: E402

LIC = AREAS['lic']['box']
INSIDE, OUTSIDE = (-73.94, 40.75), (-73.80, 40.70)   # one point in the LIC box, one elsewhere in Queens
BK = (-73.95, 40.65)                                 # in Brooklyn, outside the Manhattan box of the original build


class Stub:
    """Stands in for si.get: records every request and answers with two rows, one inside the LIC box and one outside."""

    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def __call__(self, url, params=None, data=None, timeout=120, tries=3):
        self.calls.append((url, params, data))
        for name in self.fail:
            if name in url:
                raise RuntimeError('stub outage')
        if 'overpass' in url:
            return {'elements': [{'type': 'node', 'id': 1, 'lat': INSIDE[1], 'lon': INSIDE[0], 'tags': {'amenity': 'cafe', 'name': 'x', 'cuisine': 'y'}},
                                 {'type': 'way', 'id': 2, 'center': {'lat': INSIDE[1], 'lon': INSIDE[0]}, 'tags': {'shop': 'books'}},
                                 {'type': 'relation', 'id': 3, 'tags': {'leisure': 'park'}}]}
        if 'FeatureServer' in url:
            if params['resultOffset']:
                return {'features': []}
            line = lambda p: {'type': 'Feature', 'properties': {'FID': 1}, 'geometry': {'type': 'LineString', 'coordinates': [list(p), [p[0] + .001, p[1]]]}}
            return {'features': [line(INSIDE), line(OUTSIDE)]}
        if params['$offset']:
            return []
        sel = params['$select']
        if sel == 'location':
            return [{'location': {'coordinates': list(INSIDE)}}, {}]
        if 'multipolygon' in sel:
            poly = lambda p: {'type': 'MultiPolygon', 'coordinates': [[[list(p), [p[0] + .001, p[1]], [p[0], p[1] + .001], list(p)]]]}
            return [{'signname': 'in', 'multipolygon': poly(INSIDE)}, {'signname': 'out', 'multipolygon': poly(OUTSIDE)}]
        if 'entrance_latitude' in sel:
            return [{'entrance_latitude': str(INSIDE[1]), 'entrance_longitude': str(INSIDE[0])}, {'entrance_latitude': str(OUTSIDE[1]), 'entrance_longitude': str(OUTSIDE[0])}]
        if sel == 'latitude,longitude':
            return [{'latitude': str(INSIDE[1]), 'longitude': str(INSIDE[0])}, {'latitude': str(OUTSIDE[1]), 'longitude': str(OUTSIDE[0])},
                    {'latitude': str(BK[1]), 'longitude': str(BK[0])}, {'latitude': None, 'longitude': None}]
        return [{'the_geom': {'type': 'Point', 'coordinates': list(INSIDE)}}]


class DownloadAreaSources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.real = (D.ROOT, si.get, D.time.sleep)
        D.ROOT, D.time.sleep = self.tmp.name, lambda s: None

    def tearDown(self):
        D.ROOT, si.get, D.time.sleep = self.real
        self.tmp.cleanup()

    def cache(self, area, name):
        return json.load(open(pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / area / f'{name}.json'))

    def test_areas_are_described_for_every_source(self):
        self.assertEqual(set(AREAS), {'brooklyn', 'lic'})
        for a in AREAS.values():
            w, s, e, n = a['box']
            self.assertTrue(-74.3 < w < e < -73.6 and 40.4 < s < n < 41.0, 'box is (west, south, east, north) inside New York City')
            for key in ('borocode', 'lpc_boro', 'parks_borough', 'borough_upper', 'label'):
                self.assertTrue(a[key])
        self.assertTrue(in_box(*INSIDE, LIC)); self.assertFalse(in_box(*OUTSIDE, LIC))
        self.assertTrue(touches_box({'type': 'LineString', 'coordinates': [list(OUTSIDE), list(INSIDE)]}, LIC))

    def test_lic_is_cut_to_its_box_and_queries_name_queens(self):
        si.get = stub = Stub()
        report = D.download('lic')
        self.assertEqual({k: v['status'] for k, v in report['sources'].items()}, {k: 'ok' for k in report['sources']})
        self.assertEqual(len(report['sources']), 10)
        for name in ('streets_v4', 'lpc', 'parks', 'noise', 'collisions', 'subway'):
            self.assertEqual(len(self.cache('lic', name)), 1, f'{name}: the record outside the box is dropped')
        self.assertEqual(self.cache('lic', 'forestry_trees'), [list(INSIDE)])
        self.assertEqual(self.cache('lic', 'osm'), [[INSIDE[0], INSIDE[1], {'amenity': 'cafe', 'name': 'x'}], [INSIDE[0], INSIDE[1], {'shop': 'books'}]],
                         'same tag subset as the Manhattan build; an element without a position is skipped')
        wheres = ' | '.join(str((p or {}).get('where') or (p or {}).get('$where') or '') for _, p, _ in stub.calls)
        for expected in ("borocode='4'", "BORO='Queens'", "borough='Q'", "borough='QUEENS'", 'within_box(location,40.775,-73.965,40.728,-73.915)',
                         "starts_with(complaint_type,'Noise')", 'number_of_pedestrians_injured>0'):
            self.assertIn(expected, wheres)
        self.assertNotIn('MANHATTAN', wheres.upper())
        overpass = [parse.unquote_plus(d.decode()) for u, _, d in stub.calls if 'overpass' in u]
        self.assertEqual(len(overpass), 1); self.assertIn('(40.728,-73.965,40.775,-73.915)', overpass[0])
        self.assertEqual(report['windows'].keys(), {'noise_window_from', 'collision_window_from'})

    def test_brooklyn_is_not_clipped_and_asks_overpass_in_tiles(self):
        si.get = stub = Stub()
        D.download('brooklyn', only={'streets_v4', 'osm', 'noise'})
        self.assertEqual(len(self.cache('brooklyn', 'streets_v4')), 2, 'a borough is kept whole')
        self.assertFalse(si.BOX[1] <= BK[1] <= si.BOX[3], 'the test point lies outside the Manhattan box')
        self.assertEqual(self.cache('brooklyn', 'noise'), [list(BK)], 'Brooklyn points survive (the Manhattan parser would drop them); rows outside the box or without coordinates do not')
        tiles = [d for u, _, d in stub.calls if 'overpass' in u]
        self.assertEqual(len(tiles), sum(1 for _ in D.osm_tiles(AREAS['brooklyn']['box'])))
        self.assertGreater(len(tiles), 1)
        self.assertEqual(len(self.cache('brooklyn', 'osm')), 2, 'an element returned by several tiles is kept once')

    def test_a_busy_overpass_server_costs_one_tile_not_the_area(self):
        """Seen on the first real run (2026-11-16): overpass-api.de answered 502 partway through Brooklyn."""
        class Busy(Stub):
            def __call__(self, url, params=None, data=None, timeout=120, tries=3):
                if 'overpass-api.de' in url:
                    self.calls.append((url, params, data)); raise RuntimeError('HTTP Error 502: Bad Gateway')
                return super().__call__(url, params, data, timeout, tries)
        si.get = stub = Busy()
        report = D.download('brooklyn', only={'osm'})
        self.assertEqual(report['sources']['osm']['status'], 'ok', 'another Overpass server answers')
        tiles = sum(1 for _ in D.osm_tiles(AREAS['brooklyn']['box']))
        kept = sorted((pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'brooklyn' / 'osm-tiles').glob('*.json'))
        self.assertEqual(len(kept), tiles, 'each finished tile is kept on disk')
        si.get = stub = Stub(fail={'overpass'})          # every server down on the next run
        (pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'brooklyn' / 'osm.json').unlink()
        report = D.download('brooklyn', only={'osm'})
        self.assertEqual(report['sources']['osm']['status'], 'ok', 'the area is rebuilt from the kept tiles without the network')
        self.assertEqual(stub.calls, [])

    def test_a_failed_source_is_reported_and_only_it_is_retried(self):
        si.get = Stub(fail={'erm2-nwe9'})           # the 311 dataset is down
        report = D.download('lic')
        self.assertEqual(report['sources']['noise']['status'], 'FAILED'); self.assertIn('stub outage', report['sources']['noise']['error'])
        self.assertEqual(sum(v['status'] == 'ok' for v in report['sources'].values()), 9, 'the other sources are not lost')
        self.assertFalse((pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'lic' / 'noise.json').exists(), 'nothing is written for a failed source')
        si.get = stub = Stub()
        report = D.download('lic')
        self.assertEqual(report['sources']['noise']['status'], 'ok')
        self.assertEqual({v['status'] for k, v in report['sources'].items() if k != 'noise'}, {'already downloaded'})
        self.assertTrue(all('erm2-nwe9' in u for u, _, _ in stub.calls), 'the retry asks only for what failed')
        saved = json.load(open(pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'lic' / 'download-report.json'))
        self.assertEqual(saved['sources']['noise']['records'], 1)


if __name__ == '__main__':
    unittest.main()
