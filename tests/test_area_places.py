"""Brooklyn and Long Island City records in the discovery place index (scripts/build_area_places.py)."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from areas import AREAS, in_box  # noqa: E402

PLACES = os.path.join(ROOT, 'data', 'places')
INDEX = json.load(open(os.path.join(PLACES, 'index.json')))
DOCS = {c['id']: json.load(open(os.path.join(PLACES, c['id'] + '.json')))['records'] for c in INDEX['categories']}
ALL = [r for recs in DOCS.values() for r in recs]


class AreaPlaces(unittest.TestCase):
    def test_both_areas_are_in_the_index(self):
        self.assertEqual(set(INDEX.get('areas', {})), {'brooklyn', 'lic'})
        for area, meta in INDEX['areas'].items():
            self.assertTrue(meta['osm_timestamp'] and meta['network_version'].startswith('nyc3-'))
            self.assertEqual(meta['records'], sum(1 for r in ALL if r.get('area') == area))
            self.assertIn(AREAS[area]['label'], INDEX['coverage'])

    def test_every_area_record_is_in_its_box_and_reachable_on_foot(self):
        boro = {'brooklyn': 'Brooklyn', 'lic': 'Queens'}
        for r in ALL:
            if r.get('area'):
                self.assertTrue(in_box(r['lon'], r['lat'], AREAS[r['area']]['box']), r['id'])
                self.assertEqual(r['boro'], boro[r['area']], r['id'])
                self.assertIsNotNone(r.get('snap'), r['id'])
                self.assertLessEqual(r['snap'], 150, r['id'])

    def test_manhattan_records_are_unchanged_and_ids_unique(self):
        for c in INDEX['categories']:
            self.assertEqual(c['by_area']['manhattan'], sum(1 for r in DOCS[c['id']] if not r.get('area')))
            self.assertEqual(c['count'], len(DOCS[c['id']]))
        ids = [r['id'] for r in ALL]
        self.assertEqual(len(ids), len(set(ids)), 'a place is in the index once')
        cids = [r['cid'] for r in ALL if r.get('cid') and not r['id'].startswith('lpc:')]
        self.assertEqual(len(cids), len(set(cids)), 'canonical IDs are not shared (except a landmark linked to its building)')

    def test_food_choice_exists_in_each_area(self):
        for area, least in (('brooklyn', 500), ('lic', 50)):
            food = [r for c in ('restaurants', 'cafes', 'bakeries', 'bars') for r in DOCS[c] if r.get('area') == area]
            self.assertGreater(len(food), least, area)
            self.assertTrue(any(r.get('cuisine') for r in food) and any(r.get('hours') for r in food), 'OSM cuisine and hours are kept')

    def test_server_store_finds_area_places_and_does_not_list_them_twice(self):
        from routing.places import PlaceStore
        st = PlaceStore()
        near = {'lat': 40.6872, 'lon': -73.9900}  # Cobble Hill, Brooklyn
        res = st.search(near, ['restaurants', 'cafes'], radius_m=600, limit=200)
        pool = lambda p: st.ref[p['index_id']][0]
        indexed = [p for p in res if pool(p) in ('restaurants', 'cafes')]
        self.assertTrue(indexed, 'Brooklyn food comes from the discovery index')
        self.assertTrue(all(p['borough'] == 'Brooklyn' for p in indexed))
        self.assertEqual(len({p['place_id'] for p in res}), len(res), 'no place twice')
        linked = {p['provider_ids']['dohmh'] for p in indexed if 'dohmh' in p['provider_ids']}
        self.assertTrue(linked, 'Brooklyn food permits are linked')
        search_only = {p['provider_ids'].get('dohmh') for p in res if pool(p) == '_dohmh'}
        self.assertFalse(linked & search_only, 'a permit in the index is not also listed as a search-only record')

if __name__ == '__main__':
    unittest.main()
