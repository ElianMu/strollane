"""The compiled network pack (routing/netpack.py) must give exactly what the JSON gives, and never be used when stale.

Run: python3 -m unittest tests.test_netpack
"""
import gzip
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from routing import engine, netpack  # noqa: E402

P = ROOT / 'data' / 'pedestrian'
GRAPH, SCORES, PACK = P / 'manhattan-walk-graph.json.gz', P / 'edge-scores.json.gz', P / 'manhattan-network.bin.gz'


class NetPack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = pathlib.Path(cls.tmp.name)
        shutil.copy(GRAPH, t / 'manhattan-walk-graph.json.gz'); shutil.copy(SCORES, t / 'edge-scores.json.gz')
        cls.json_net = engine.PedestrianNetwork(str(t / 'manhattan-walk-graph.json.gz'), str(t / 'edge-scores.json.gz'))  # no pack beside it
        cls.pack_net = engine.PedestrianNetwork(str(GRAPH), str(SCORES))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_committed_pack_is_current(self):
        """A stale pack is ignored at run time (safe, but the server then needs ~230 MB more). Recompile when this fails:
        python3 scripts/compile_network.py"""
        h = netpack.read_header(PACK)['inputs']
        self.assertEqual(h, {'graph_sha256': netpack.sha256(GRAPH), 'scores_sha256': netpack.sha256(SCORES)})
        self.assertEqual(self.pack_net.loaded_from, 'pack'); self.assertEqual(self.json_net.loaded_from, 'json')

    def test_same_network(self):
        a, b = self.json_net, self.pack_net
        self.assertEqual(a.meta, b.meta); self.assertEqual(a.score_meta, b.score_meta)
        self.assertEqual(a.nodes, b.nodes)
        self.assertEqual(a.edges, b.edges)
        self.assertEqual(len(a.geoms), len(b.geoms))
        self.assertEqual(a.geoms.coordinates, b.geoms.coordinates); self.assertEqual(a.geoms.offsets, b.geoms.offsets)
        self.assertEqual(len(a.gscores), len(b.gscores))
        for gi in range(len(a.gscores)):
            self.assertEqual(json.dumps(a.gscores[gi]), json.dumps(b.gscores[gi]), gi)

    def test_scores_round_trip_the_json_exactly(self):
        raw = json.load(gzip.open(SCORES, 'rt', encoding='utf-8'))['geoms']
        for gi in range(0, len(raw), 7):
            self.assertEqual(json.dumps(self.pack_net.gscores[gi]), json.dumps(raw[gi]), gi)

    def test_same_routes(self):
        for o, d, w in (((-73.9832, 40.7536), (-73.9787, 40.7587), {'Nature': 90}),
                        ((-74.0168, 40.7032), (-73.9973, 40.7308), {'Quiet & Relax': 80, 'Architecture': 80}),
                        ((-73.9636, 40.8075), (-73.9319, 40.8638), {'Scenic & Visual': 90})):
            ra, rb = (engine.RoutePlanner(n).plan({'lon': o[0], 'lat': o[1]}, {'lon': d[0], 'lat': d[1]}, {'weights': w}) for n in (self.json_net, self.pack_net))
            strip = lambda r: re.sub(r'"validation_timestamp": "[^"]*"', 'T', re.sub(r'rt-[0-9a-f]{10}', 'rt-ID', json.dumps([{k: v for k, v in x.items() if k != 'compute_seconds'} for x in r['routes']])))
            self.assertEqual(strip(ra), strip(rb), 'identical routes; route IDs and validation times differ per request')

    def test_lookups(self):
        n = self.pack_net
        for i in range(0, len(n.edges), 997):
            eid = n.edge_id(i)
            self.assertEqual(n.by_id.get(eid), i); self.assertIn(eid, n.by_id)
            t = n.twin(i)
            if t is not None:
                self.assertEqual(n.edges[t][3], n.edges[i][3]); self.assertNotEqual(n.edges[t][4], n.edges[i][4])
        self.assertIsNone(n.by_id.get('1-2-3')); self.assertIsNone(n.by_id.get('not-an-id'))

    def test_a_stale_pack_is_not_used(self):
        with tempfile.TemporaryDirectory() as t:
            t = pathlib.Path(t)
            shutil.copy(GRAPH, t / 'manhattan-walk-graph.json.gz'); shutil.copy(PACK, t / 'manhattan-network.bin.gz')
            s = json.load(gzip.open(SCORES, 'rt', encoding='utf-8'))
            s['geoms'][0]['o'] = (s['geoms'][0]['o'] or 0) + 1                      # scores changed after the pack was compiled
            with gzip.open(t / 'edge-scores.json.gz', 'wt', encoding='utf-8') as f:
                json.dump(s, f)
            n = engine.PedestrianNetwork(str(t / 'manhattan-walk-graph.json.gz'), str(t / 'edge-scores.json.gz'))
            self.assertEqual(n.loaded_from, 'json'); self.assertEqual(n.gscores[0]['o'], s['geoms'][0]['o'])


if __name__ == '__main__':
    unittest.main()
