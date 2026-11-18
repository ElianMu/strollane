"""scripts/download_area_sources.py with the network replaced by a stub: queries, clipping, resume and failure handling.

No real records are involved; the stub returns a handful of made-up rows so the plumbing can be checked offline.
Run: python3 -m unittest tests.test_area_sources
"""
import json
import pathlib
import sys
import tempfile
import os
import unittest
from unittest import mock
from urllib import parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import download_area_sources as D  # noqa: E402
import streetwise_indicators as si  # noqa: E402
from areas import AREAS, in_box, touches_box  # noqa: E402

LIC = AREAS['lic']['box']
INSIDE, OUTSIDE = (-73.94, 40.75), (-73.80, 40.70)   # one point in the LIC box, one elsewhere in Queens
BK = (-73.95, 40.65)                                 # in Brooklyn, outside the Manhattan box of the original build


NON_LAYER = set(D.jobs_for('lic')[0]) - set(D.LAYER_SOURCES)


class Stub:
    """Stands in for si.get: records every request and answers with two rows, one inside the LIC box and one outside."""

    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def __call__(self, url, params=None, data=None, timeout=120, tries=3):
        self.calls.append((url, params, data))
        for name in self.fail:
            if name in url:
                raise RuntimeError('stub outage')
        if 'wikidata.org' in url:
            return {'entities': {'Q1': {'sitelinks': {'enwiki': {}, 'frwiki': {}}, 'labels': {'en': {'value': 'x'}}, 'descriptions': {'en': {'value': 'a café'}},
                                        'claims': {'P856': [{'mainsnak': {'datavalue': {'value': 'https://x.example'}}}]}}}}
        if 'overpass' in url:
            return {'osm3s': {'timestamp_osm_base': '2026-11-17T00:00:00Z'},
                    'elements': [{'type': 'node', 'id': 1, 'lat': INSIDE[1], 'lon': INSIDE[0], 'tags': {'amenity': 'cafe', 'name': 'x', 'cuisine': 'y', 'wikidata': 'Q1', 'opening_hours': 'Mo-Su 08:00-18:00', 'fixme': 'z'}},
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
        if sel.startswith('facility_name'):
            return [{'facility_name': 'in', 'latitude': str(INSIDE[1]), 'longitude': str(INSIDE[0])}, {'facility_name': 'out', 'latitude': str(OUTSIDE[1]), 'longitude': str(OUTSIDE[0])}]
        if 'bldg_class' in sel:
            return [{'bbl': '4000010001', 'bldg_class': 'H2', 'taxyear': '2026', 'latitude': str(INSIDE[1]), 'longitude': str(INSIDE[0])}]
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
        report = D.download('lic', only=NON_LAYER)
        self.assertEqual({k: v['status'] for k, v in report['sources'].items()}, {k: 'ok' for k in report['sources']})
        self.assertEqual(len(report['sources']), len(NON_LAYER))
        for name in ('streets_v4', 'lpc', 'parks', 'noise', 'collisions', 'subway'):
            self.assertEqual(len(self.cache('lic', name)), 1, f'{name}: the record outside the box is dropped')
        self.assertEqual(self.cache('lic', 'forestry_trees'), [list(INSIDE)])
        self.assertEqual(self.cache('lic', 'osm'), [[INSIDE[0], INSIDE[1], {'amenity': 'cafe', 'name': 'x'}], [INSIDE[0], INSIDE[1], {'shop': 'books'}]],
                         'same tag subset as the Manhattan build; an element without a position is skipped')
        wheres = ' | '.join(str((p or {}).get('where') or (p or {}).get('$where') or '') for _, p, _ in stub.calls)
        for expected in ("borocode='4'", "BORO='Queens'", "borough='Q'", "borough='QUEENS'", 'within_box(location,40.785,-73.965,40.728,-73.87)',
                         "starts_with(complaint_type,'Noise')", 'number_of_pedestrians_injured>0'):
            self.assertIn(expected, wheres)
        self.assertNotIn('MANHATTAN', wheres.upper())
        overpass = [parse.unquote_plus(d.decode()) for u, _, d in stub.calls if 'overpass' in u]
        tiles = list(D.osm_tiles(LIC))
        self.assertEqual(len(overpass), 2 * len(tiles), 'every tile, once for osm and once for places_osm')
        self.assertTrue(all(f'({t[1]},{t[0]},{t[3]},{t[2]})' in q for t in tiles for q in overpass if f'({t[1]},{t[0]},' in q))
        self.assertTrue(any('(40.728,-73.965,' in q for q in overpass))
        places = self.cache('lic', 'places_osm')
        self.assertEqual(places['osm_timestamp'], '2026-11-17T00:00:00Z')
        self.assertEqual(places['elements'][0]['tags'], {'amenity': 'cafe', 'name': 'x', 'cuisine': 'y', 'wikidata': 'Q1', 'opening_hours': 'Mo-Su 08:00-18:00'},
                         'the tags scripts/build_place_index.py reads are kept (cuisine, hours, Wikidata); others are not')
        self.assertEqual(len(places['elements']), 2, 'an element without a position is skipped')
        self.assertEqual(self.cache('lic', 'wikidata'), {'Q1': [2, 'x', 'a café', 'https://x.example']})
        self.assertEqual([r['facility_name'] for r in self.cache('lic', 'restrooms')], ['in'], 'restrooms are cut to the box')
        self.assertIn("borough in('QUEENS','4')", wheres)
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
        kept = sorted((pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'brooklyn' / ('osm-tiles-' + D.box_key(AREAS['brooklyn']['box']))).glob('*.json'))
        self.assertEqual(len(kept), tiles, 'each finished tile is kept on disk')
        si.get = stub = Stub(fail={'overpass'})          # every server down on the next run
        (pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'brooklyn' / 'osm.json').unlink()
        report = D.download('brooklyn', only={'osm'})
        self.assertEqual(report['sources']['osm']['status'], 'ok', 'the area is rebuilt from the kept tiles without the network')
        self.assertEqual(stub.calls, [])

    def test_a_failed_source_is_reported_and_only_it_is_retried(self):
        si.get = Stub(fail={'erm2-nwe9'})           # the 311 dataset is down
        report = D.download('lic', only=NON_LAYER)
        self.assertEqual(report['sources']['noise']['status'], 'FAILED'); self.assertIn('stub outage', report['sources']['noise']['error'])
        self.assertEqual(sum(v['status'] == 'ok' for v in report['sources'].values()), 14, 'the other sources are not lost')
        self.assertFalse((pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'lic' / 'noise.json').exists(), 'nothing is written for a failed source')
        si.get = stub = Stub()
        report = D.download('lic', only=NON_LAYER)
        self.assertEqual(report['sources']['noise']['status'], 'ok')
        self.assertEqual({v['status'] for k, v in report['sources'].items() if k != 'noise'}, {'already downloaded'})
        self.assertTrue(all('erm2-nwe9' in u for u, _, _ in stub.calls), 'the retry asks only for what failed')
        saved = json.load(open(pathlib.Path(self.tmp.name) / 'data' / 'cache' / 'sources' / 'lic' / 'download-report.json'))
        self.assertEqual(saved['sources']['noise']['records'], 1)


if __name__ == '__main__':
    unittest.main()


class LayerStub:
    """Answers every map-layer query with one record inside the LIC box and one outside, in each coordinate form."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, params=None, data=None, timeout=120, tries=3):
        self.calls.append((url, params, data))
        if 'gbfs' in url:
            return {'last_updated': 1, 'data': {'stations': [{'station_id': 'in', 'lon': INSIDE[0], 'lat': INSIDE[1]}, {'station_id': 'out', 'lon': OUTSIDE[0], 'lat': OUTSIDE[1]}]}}
        if 'overpass' in url:
            return {'osm3s': {'timestamp_osm_base': 't'}, 'elements': [{'type': 'node', 'id': 1, 'lat': INSIDE[1], 'lon': INSIDE[0], 'tags': {'amenity': 'bench', 'note': 'dropped'}}]}
        if 'FeatureServer' in url:
            if params['resultOffset']:
                return {'features': []}
            poly = lambda p: {'type': 'Polygon', 'coordinates': [[list(p), [p[0] + .001, p[1]], [p[0], p[1] + .001], list(p)]]}
            return {'features': [{'type': 'Feature', 'properties': {'LPC_NAME': n}, 'geometry': poly(p)} for n, p in (('in', INSIDE), ('out', OUTSIDE))]}
        if params['$offset']:
            return []
        row = lambda n, p: {'id': n, 'latitude': str(p[1]), 'longitude': str(p[0]), 'gtfs_latitude': str(p[1]), 'gtfs_longitude': str(p[0]),
                            'entrance_latitude': str(p[1]), 'entrance_longitude': str(p[0]),
                            'the_geom': {'type': 'Point', 'coordinates': list(p)}, 'location': {'type': 'Point', 'coordinates': list(p)},
                            'multipolygon': {'type': 'MultiPolygon', 'coordinates': [[[list(p), [p[0] + .001, p[1]], [p[0], p[1] + .001], list(p)]]]}}
        return [row('in', INSIDE), row('out', OUTSIDE)]


class DownloadAreaLayers(unittest.TestCase):
    def test_every_layer_source_downloads_and_small_citywide_sets_are_cut_to_the_box(self):
        self.tmp = tempfile.mkdtemp()
        stub = LayerStub()
        with mock.patch.object(D, 'ROOT', self.tmp), mock.patch.object(D.si, 'get', stub), mock.patch.object(D.time, 'sleep', lambda s: None):
            report = D.download('lic', only=set(D.LAYER_SOURCES))
        self.assertEqual({k: v['status'] for k, v in report['sources'].items()}, {k: 'ok' for k in D.LAYER_SOURCES})
        read = lambda n: json.load(open(os.path.join(self.tmp, 'data', 'cache', 'sources', 'lic', n + '.json')))
        for name in ('layer_gardens', 'layer_plazas', 'layer_fountains', 'layer_pops', 'layer_linknyc', 'layer_subway_stations', 'layer_subway', 'layer_crashes', 'layer_lpc'):
            rows = read(name)
            self.assertEqual(len(rows), 1, name)
        self.assertEqual([x['station_id'] for x in read('layer_citibike')['stations']], ['in'])
        self.assertEqual(read('layer_osm')['elements'][0]['tags'], {'amenity': 'bench'}, 'only the tags build_urban_layers.py keeps')
        self.assertEqual(read('layer_pops')[0]['id'], 'in', 'whole rows are kept, not just coordinates')
