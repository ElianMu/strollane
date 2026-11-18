"""The joined network of Manhattan, Brooklyn and Long Island City (scripts/merge_networks.py) the router uses.

Run: python3 -m unittest tests.test_joined_network
"""
import gzip
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from routing import engine, netpack  # noqa: E402

P = ROOT / 'data' / 'pedestrian'
AREAS = ['manhattan', 'brooklyn', 'lic']
load = lambda p: json.load(gzip.open(p, 'rt', encoding='utf-8'))
JG, JS = load(P / 'nyc-walk-graph.json.gz'), load(P / 'nyc-edge-scores.json.gz')
NET = engine.get_planner().net
PLANNER = engine.get_planner()


def shortest(o, d):
    r = PLANNER.plan({'lon': o[0], 'lat': o[1]}, {'lon': d[0], 'lat': d[1]}, {'weights': {'Nature': 60}})
    s = next(x for x in r['routes'] if x['objective'] == 'shortest')
    names = {str(NET.edge_object(NET.by_id.get(e))['name']) for e in s['ordered_edge_ids']}
    return s['distance_m'], names


class JoinedNetwork(unittest.TestCase):
    def test_router_uses_the_current_joined_pack(self):
        h = netpack.read_header(P / 'nyc-network.bin.gz')['inputs']
        self.assertEqual(h, {'graph_sha256': netpack.sha256(P / 'nyc-walk-graph.json.gz'), 'scores_sha256': netpack.sha256(P / 'nyc-edge-scores.json.gz')},
                         'recompile: python3 scripts/merge_networks.py && python3 scripts/compile_network.py --area nyc')
        self.assertEqual(NET.loaded_from, 'pack'); self.assertEqual(NET.network_version, JG['metadata']['network_version'])
        self.assertEqual(JG['metadata']['areas'], AREAS)

    def test_every_edge_and_score_is_copied_from_its_area(self):
        graphs = {a: load(P / f'{a}-walk-graph.json.gz') for a in AREAS}
        scores = {a: load(P / ('edge-scores.json.gz' if a == 'manhattan' else f'{a}-edge-scores.json.gz'))['geoms'] for a in AREAS}
        first = {}
        for a in AREAS:
            for e in graphs[a]['edges']:
                first.setdefault((e[0], e[1], e[2]), (a, e))
        self.assertEqual(len(JG['edges']), len(first), 'each directed edge once')
        for e in JG['edges'][::53]:
            a, src = first[(e[0], e[1], e[2])]
            self.assertEqual(e[4:], src[4:], 'reversal flag, length, ways and tags copied')
            self.assertEqual(JG['geoms'][e[3]], graphs[a]['geoms'][src[3]])
            self.assertEqual(JS['geoms'][e[3]], scores[a][src[3]], 'scores copied from the area the edge came from')
        self.assertEqual(JG['metadata']['counts']['by_area']['manhattan']['skipped_duplicates'], 0, 'Manhattan keeps all of its edges')

    def test_scores_are_one_scale(self):
        self.assertEqual(len({load(P / ('edge-scores.json.gz' if a == 'manhattan' else f'{a}-edge-scores.json.gz'))['metadata']['score_version'] for a in AREAS}), 1)
        self.assertEqual(JS['metadata']['score_version'], NET.score_version)

    def test_one_routable_component_spans_the_three_areas(self):
        c = JG['metadata']['counts']
        self.assertGreater(c['main_component_nodes'] / c['nodes'], .9)
        for name, (lon, lat) in {'Times Square': (-73.9855, 40.7580), 'Prospect Park': (-73.9690, 40.6600), 'Court Square, LIC': (-73.9440, 40.7470)}.items():
            i = NET.snap(lon, lat, name)
            self.assertIsNotNone(i, name)

    def test_river_crossings(self):
        """Walks that must cross the East River or Newtown Creek on a footway of the named bridge, measured 2026-11-17."""
        for o, d, bridge, max_km in (((-74.0060, 40.7127), (-73.9897, 40.7033), 'Brooklyn Bridge', 3.0),
                                     ((-73.9960, 40.7150), (-73.9880, 40.7020), 'Manhattan Bridge', 2.5),
                                     ((-73.9620, 40.7590), (-73.9440, 40.7470), 'Queensboro Bridge', 3.5),
                                     ((-73.9585, 40.7460), (-73.9510, 40.7210), 'Pulaski Bridge', 4.5)):
            dist, names = shortest(o, d)
            self.assertTrue(any(bridge in n or bridge.replace('Brooklyn', 'Brookyln') in n for n in names), (bridge, sorted(n for n in names if 'ridge' in n)))
            self.assertLess(dist, max_km * 1000, bridge)

    def test_queensboro_walks_pass_route_qa(self):
        """The sidewalks at the Manhattan end of the Queensboro Bridge are foot=designated + access=no; OSM's specific
        key wins, so route QA must not fail Queens–Manhattan walks over them (it did until 2026-11-18)."""
        from routing.validation import foot_allowed
        self.assertTrue(foot_allowed({'foot': 'designated', 'access': 'no'}))
        self.assertFalse(foot_allowed({'access': 'no'}))
        self.assertFalse(foot_allowed({'foot': ['yes', 'no']}))
        r = PLANNER.plan({'lon': -73.9585, 'lat': 40.7455}, {'lon': -73.9776, 'lat': 40.7614}, {'weights': {'Architecture': 80}})
        self.assertTrue(r['routes'])
        for route in r['routes']:
            self.assertEqual(route['validation']['blocking_issues'], [], route['objective'])

    def test_williamsburg_bridge_gap_is_known(self):
        """Known limit (METHODOLOGY.md): the Williamsburg Bridge walkway stops over the river in Manhattan's 2026-10-23 OSM
        download, so walks between the Lower East Side and Williamsburg detour. If this fails, the gap has been fixed:
        update the documentation and turn this into a crossing test."""
        dist, names = shortest((-73.9868, 40.7177), (-73.9634, 40.7112))
        self.assertFalse(any('Williamsburg' in n for n in names))
        self.assertGreater(dist, 5000)


if __name__ == '__main__':
    unittest.main()
