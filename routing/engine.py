"""STREETWISE pedestrian routing engine (standard library only).

Routes are computed on the joined OSM pedestrian graph of Manhattan, Brooklyn and Queens
(data/pedestrian/nyc-walk-graph.json.gz, scripts/merge_networks.py; read from nyc-network.bin.gz when current) and scored with
the 12 experience scores transferred to each OSM edge (data/pedestrian/edge-scores.json.gz). NYC LION is never
routed on; it only supplies scores through street_osm_edge_mapping. Every route keeps its ordered edge list, and
its geometry, distance and scores are all derived from that one list.
"""
import gzip, hashlib, heapq, json, math, os, threading, time, uuid
from array import array
from collections import OrderedDict
from .geometry_store import PackedPolylines, ProjectedPolylines
from .compact import Adjacency, EdgeIds, EdgeTable, GeomIndex, NodeTable, PackedScores, intern_edges
from . import netpack

try:
    from . import weather as wx
    from . import validation as qa
    from . import maneuvers as mv
except ImportError:  # run as a top-level module (tests import routing.engine; server.py imports routing.engine)
    import weather as wx
    import validation as qa
    import maneuvers as mv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH = os.path.join(ROOT, 'data', 'pedestrian', 'nyc-walk-graph.json.gz')
SCORES = os.path.join(ROOT, 'data', 'pedestrian', 'nyc-edge-scores.json.gz')
DIMENSIONS = ['Architecture', 'Nature', 'Culture', 'Quiet & Relax', 'Spatial Comfort', 'Urban Vibrancy', 'Food & Retail',
              'Scenic & Visual', 'Walkability', 'Access & Safety', 'Environment', 'Transit Connectivity']
MIN_WALK_MINUTES = 10  # smallest accepted max walking time; there is deliberately no upper cap
WALK_SPEED_M_PER_MIN = 80.0  # 4.8 km/h, a common planning pace; no live pace data is used
MAX_SNAP_M = 150.0
LOW_COVERAGE = 0.6
OFF_ROUTE_M = 35.0
LAT0 = 40.78
MX, MY = 111320 * math.cos(math.radians(LAT0)), 110540


class RoutingError(ValueError):
    """A request the network cannot satisfy (bad input, too far from a path, unreachable)."""


def xy(lon, lat):
    return (lon * MX, lat * MY)


def as_list(v):
    return v if isinstance(v, list) else [] if v is None else [v]


class PedestrianNetwork:
    def __init__(self, graph_path=GRAPH, scores_path=SCORES):
        t0 = time.time()
        pack = graph_path.replace('-walk-graph.json.gz', '-network.bin.gz')
        self.loaded_from = 'json'
        if os.path.exists(pack) and self._pack_matches(pack, graph_path, scores_path):
            self._load_pack(pack)
            self.loaded_from = 'pack'
        else:
            self._load_json(graph_path, scores_path)
        if self.score_meta['network_version'] != self.meta['network_version']:
            raise RuntimeError('edge-scores.json.gz was built for a different network version; rerun scripts/match_lion_osm.py')
        self.network_version = self.meta['network_version']
        self.score_version = self.score_meta['score_version']
        self.adj = Adjacency(self.nodes, (self.edges.node_ids[u] for u in self.edges.U))
        # per edge: 1 when its head node is outside the main component (the search loops skip those edges)
        # and the head node's NodeTable position, so A* reads its coordinates without a lookup
        comp = self.nodes.comp
        self.head_pos = array('i', (self.nodes.pos(v) for v in self.edges.v))
        self.head_off = bytearray(1 if comp[p] != 0 else 0 for p in self.head_pos)
        self.by_id = EdgeIds(self.edges, self.adj)
        self.by_geom = GeomIndex(self.edges, len(self.geoms))
        # Metric polylines and a 100 m bucket index of routable edge geometries (both endpoints in the main component).
        self.gxy = ProjectedPolylines(self.geoms, xy)
        self.glen = [sum(math.dist(a, b) for a, b in zip(g, g[1:])) for g in self.gxy]
        self.index = {}
        for i, (u, v, k, gi, rev, *_rest) in enumerate(self.edges):
            if rev or self.nodes[u][3] != 0 or self.nodes[v][3] != 0:
                continue
            geom = self.gxy[gi]
            for a, b in zip(geom, geom[1:]):
                for bx in range(int(min(a[0], b[0]) // 100), int(max(a[0], b[0]) // 100) + 1):
                    for by in range(int(min(a[1], b[1]) // 100), int(max(a[1], b[1]) // 100) + 1):
                        cell = self.index.setdefault((bx, by), [])
                        if not cell or cell[-1] != i:
                            cell.append(i)
        self._step_free = None
        streets = os.path.join(ROOT, 'data', 'manhattan-streets.json')
        compact = os.path.join(ROOT, 'data', 'pedestrian', 'segment-evidence.json.gz')
        evidence = None
        if os.path.exists(compact) and os.path.exists(streets):
            with gzip.open(compact, 'rt') as f: cached = json.load(f)
            with open(streets, 'rb') as f: signature = hashlib.file_digest(f, 'sha256').hexdigest()
            if cached['metadata']['source_sha256'] == signature:
                evidence = cached['records']
        if evidence is None:
            feats=[]
            if os.path.exists(streets):
                with open(streets, encoding='utf-8') as f: feats = json.load(f)['features']
            evidence = {f['properties']['id']: f['properties'] for f in feats}
        extra = os.path.join(ROOT, 'data', 'pedestrian', 'area-segment-evidence.json.gz')  # Brooklyn and Queens (scripts/merge_networks.py)
        if os.path.exists(extra):
            with gzip.open(extra, 'rt') as f: evidence = {**evidence, **json.load(f)['records']}
        self.segment_names = {sid: (p.get('name'), p.get('source_segment_id')) for sid, p in evidence.items()}
        # Raw Nature sub-indicators per LION segment: the spatial evidence for the weather heat term (routing/weather.py).
        self.segment_raw = {sid: {k: p.get(k) for k in ('tree_km', 'park_pct')} for sid, p in evidence.items()}
        self._exposure = None
        self.load_seconds = round(time.time() - t0, 1)

    @staticmethod
    def _pack_matches(pack, graph_path, scores_path):
        """The binary pack is used only when it was compiled from exactly these JSON files."""
        try:
            h = netpack.read_header(pack)['inputs']
        except (OSError, ValueError, KeyError):
            return False
        return h.get('graph_sha256') == netpack.sha256(graph_path) and h.get('scores_sha256') == netpack.sha256(scores_path)

    def _load_json(self, graph_path, scores_path):
        # The parsed JSON is converted to compact forms as soon as each part is read, and dropped (routing/compact.py).
        scores = json.load(gzip.open(scores_path, 'rt', encoding='utf-8'))
        self.score_meta = scores['metadata']
        self.gscores = PackedScores(scores.pop('geoms'), len(DIMENSIONS))
        del scores
        graph = json.load(gzip.open(graph_path, 'rt', encoding='utf-8'))
        self.meta = graph['metadata']
        nodes = {int(k): v for k, v in graph.pop('nodes').items()}
        self.geoms = PackedPolylines(graph.pop('geoms'))
        raw_edges = graph.pop('edges')
        del graph
        for e in raw_edges:
            e[7]['_steps'] = 'steps' in as_list(e[7].get('highway'))
        self.edges = EdgeTable.from_tuples(intern_edges(raw_edges, {n: n for n in nodes}))
        self.nodes = NodeTable.from_dict(nodes)

    def _load_pack(self, pack):
        """Same structures as _load_json, from the compiled arrays (routing/netpack.py): no large JSON parse."""
        header, A = netpack.unpack(pack)
        self.meta, self.score_meta = header['graph_metadata'], header['score_metadata']
        ids = A['node_id']
        ll, cnt, comp = A['node_lonlat'], A['node_count'], A['node_comp']
        self.nodes = NodeTable(A['node_id'], ll, cnt, comp)
        self.geoms = PackedPolylines.from_arrays(A['coords'], A['offsets'])
        tags = header['tags']
        for t in tags:
            t['_steps'] = 'steps' in as_list(t.get('highway'))
        ways = header['ways']
        U, V, K, G, R, L, W, T = (A[c] for c in ('e_u', 'e_v', 'e_k', 'e_gi', 'e_rev', 'e_len', 'e_ways', 'e_tags'))
        self.edges = EdgeTable(ids, U, V, K, G, R, L, W, T, ways, tags)
        self.gscores = netpack.scores_from_pack(header, A, len(DIMENSIONS))

    def heat_exposure(self):
        """(per-geometry exposure 0..1, has-evidence flags, neutral median) — computed once, on the first hot-weather request."""
        if self._exposure is None:
            self._exposure = wx.exposure_table(self.gscores, self.segment_raw)
        return self._exposure

    def step_free_nodes(self):
        """Nodes of the largest network reachable without any steps (computed once). Snapping for 'avoid stairs'
        targets this network, so a start inside a pocket enclosed by stairs is not chosen."""
        if self._step_free is None:
            adj = {}
            for u, v, k, gi, rev, length, osmids, tags in self.edges:
                if not tags['_steps'] and self.nodes[u][3] == 0 and self.nodes[v][3] == 0:
                    adj.setdefault(u, []).append(v)
            seen, best = set(), set()
            for start in adj:
                if start in seen:
                    continue
                comp, stack = {start}, [start]
                while stack:
                    for nb in adj.get(stack.pop(), ()):
                        if nb not in comp:
                            comp.add(nb); stack.append(nb)
                seen |= comp
                if len(comp) > len(best):
                    best = comp
            self._step_free = best
        return self._step_free

    # --- identities and lookups ------------------------------------------------------------------------------
    def edge_id(self, i):
        u, v, k = self.edges[i][:3]
        return f'{u}-{v}-{k}'

    def twin(self, i):
        gi, rev = self.edges.G[i], self.edges.R[i]
        return self.by_geom.get((gi, 1 - rev))

    def coords(self, i):
        gi, rev = self.edges.G[i], self.edges.R[i]
        g = self.geoms[gi]
        return g[::-1] if rev else g

    def coords_xy(self, i):
        gi, rev = self.edges.G[i], self.edges.R[i]
        g = self.gxy[gi]
        return g[::-1] if rev else g

    def status(self):
        c = self.meta['counts']
        return {'network_version': self.network_version, 'score_version': self.score_version, 'data_version': self.score_meta['data_version'],
                'nodes': c['nodes'], 'edges': c['edges'], 'main_component_nodes': c['main_component_nodes'], 'components': c['components'],
                'edge_score_sources': self.score_meta['sources'], 'dimension_length_coverage': self.score_meta['routable_length_coverage_by_dimension'],
                'load_seconds': self.load_seconds}

    def edge_object(self, i, traversed=None, offsets=None):
        """Pedestrian Edge Object (shared data contract)."""
        u, v, k, gi, rev, length, osmids, tags = self.edges[i]
        s = self.gscores[gi]
        geom = self.coords(i) if offsets is None else self.clip(i, *offsets)
        return {
            'edge_id': f'{u}-{v}-{k}', 'u': u, 'v': v, 'key': k, 'osm_way_ids': osmids, 'geometry_index': gi,
            'name': (as_list(tags.get('name')) or [None])[0], 'highway': tags.get('highway'),
            'geometry': {'type': 'LineString', 'coordinates': geom},
            'length_m': round(length, 1), 'traversed_length_m': round(traversed if traversed is not None else length, 1),
            'pedestrian_access': {'foot': tags.get('foot'), 'access': tags.get('access'), 'steps': tags['_steps'],
                                  'footway': tags.get('footway'), 'crossing': tags.get('crossing'), 'bridge': tags.get('bridge'),
                                  'tunnel': tags.get('tunnel'), 'layer': tags.get('layer'), 'surface': tags.get('surface')},
            'dimension_scores': dict(zip(DIMENSIONS, s['s'])), 'overall_score': s['o'],
            'data_coverage': dict(zip(DIMENSIONS, s['c'])), 'score_source': s['src'], 'match_quality': s['q'],
            'matched_segment_ids': s['m'], 'lion_match_share': s['frac'],
            'matched_segments': [{'segment_id': m, 'street_name': self.segment_names.get(m, (None, None))[0], 'source_segment_id': self.segment_names.get(m, (None, None))[1]} for m in s['m']],
            'lion_match': 'matched' if s['m'] else 'unmatched',
            'street_name': (as_list(tags.get('name')) or [None])[0] or (self.segment_names.get(s['m'][0], (None,))[0] if s['m'] else None),
            'direct_sub_indicators': s.get('raw'), 'network_version': self.network_version, 'score_version': self.score_version,
        }

    # --- snapping --------------------------------------------------------------------------------------------
    def snap(self, lon, lat, label, allowed=None):
        """Project a coordinate onto the nearest routable edge (never straight onto a node); allowed(i) can exclude edges."""
        p = xy(lon, lat)
        bx, by = int(p[0] // 100), int(p[1] // 100)
        best = None
        for r in range(0, int(MAX_SNAP_M // 100) + 2):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) != r:
                        continue
                    for i in self.index.get((bx + dx, by + dy), ()):
                        if allowed and not allowed(i):
                            continue
                        g = self.coords_xy(i); run = 0.0
                        for a, b in zip(g, g[1:]):
                            ux, uy = b[0] - a[0], b[1] - a[1]; l2 = ux * ux + uy * uy; seg = math.sqrt(l2)
                            t = max(0.0, min(1.0, ((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) / l2)) if l2 else 0.0
                            d = math.hypot(p[0] - a[0] - t * ux, p[1] - a[1] - t * uy)
                            if best is None or d < best[0]:
                                best = (d, i, run + t * seg)
                            run += seg
            if best and best[0] <= r * 100:
                break
        if not best or best[0] > MAX_SNAP_M:
            raise RoutingError(f'{label} is more than {MAX_SNAP_M:.0f} m from any walkable path in the Manhattan, Brooklyn and Queens pedestrian network'
                               + (' that avoids stairs.' if allowed else '. Roosevelt, Randall\'s and Governors Island connect only through other boroughs and are not routable.'))
        d, i, along = best
        geo_len = self.glen[self.edges.G[i]] or 1
        return {'edge': i, 'offset_m': along / geo_len * self.edges.L[i], 'snap_distance_m': round(d, 1),
                'edge_id': self.edge_id(i), 'input': [lon, lat]}

    # --- geometry helpers ------------------------------------------------------------------------------------
    def clip(self, i, a_m, b_m):
        """Edge coordinates between two offsets (metres of the edge's own length, in its direction)."""
        length = self.edges.L[i] or 1
        g, gx = self.coords(i), self.coords_xy(i)
        cum = [0.0]
        for p, q in zip(gx, gx[1:]):
            cum.append(cum[-1] + math.dist(p, q))
        scale = (cum[-1] or 1) / length
        a, b = a_m * scale, b_m * scale

        def at(d):
            for j in range(1, len(cum)):
                if d <= cum[j] or j == len(cum) - 1:
                    t = 0 if cum[j] == cum[j - 1] else max(0.0, min(1.0, (d - cum[j - 1]) / (cum[j] - cum[j - 1])))
                    return [round(g[j - 1][0] + (g[j][0] - g[j - 1][0]) * t, 7), round(g[j - 1][1] + (g[j][1] - g[j - 1][1]) * t, 7)], j
            return g[-1], len(g) - 1
        start, js = at(a)
        end, je = at(b)
        return [start] + [list(c) for c in g[js:je]] + [end]

    # --- search ----------------------------------------------------------------------------------------------
    def distances(self, origin, dests, edge_cost=lambda i: 1.0):
        """One-to-many Dijkstra from a snapped origin to several snapped destinations (cost = multiplier × metres).
        Returns a list of costs (None when unreachable). Same virtual endpoints as search(), so the matrix agrees
        with the routes that are later drawn."""
        E_v, E_len, E_off = self.edges.v, self.edges.L, self.head_off
        cost_cache = {}

        def cost(i):
            if i not in cost_cache:
                cost_cache[i] = edge_cost(i)
            return cost_cache[i]

        def step_cost(step):
            c = cost(step[0])
            return None if c is None else c * (step[2] - step[1])

        out = [None] * len(dests)
        ends = {}  # node -> [(dest index, step into that dest)]
        for k, d in enumerate(dests):
            i, off = d['edge'], d['offset_m']
            ends.setdefault(self.edges[i][0], []).append((k, (i, 0.0, off)))
            j = self.twin(i)
            if j is not None:
                ends.setdefault(self.edges[j][0], []).append((k, (j, 0.0, self.edges.L[j] - off)))
            if d['edge'] in (origin['edge'], self.twin(origin['edge'])):  # same edge: walk straight along it
                along = abs((origin['offset_m'] if origin['edge'] == i else self.edges.L[i] - origin['offset_m']) - off)
                c = cost(i)
                if c is not None:
                    out[k] = c * along
        best, heap, tie, done = {}, [], iter(range(1 << 62)), set()
        i, off = origin['edge'], origin['offset_m']
        starts = [(self.edges.v[i], (i, off, self.edges.L[i]))]
        j = self.twin(i)
        if j is not None:
            starts.append((self.edges.v[j], (j, self.edges.L[j] - off, self.edges.L[j])))
        for node, step in starts:
            c = step_cost(step)
            if c is not None and c < best.get(node, math.inf):
                best[node] = c
                heapq.heappush(heap, (c, next(tie), node))
        remaining = set(range(len(dests)))
        while heap and remaining:
            g, _, node = heapq.heappop(heap)
            if node in done or g > best.get(node, math.inf):
                continue
            done.add(node)
            # A destination is final once the frontier passes its best known cost.
            for k in [k for k in remaining if out[k] is not None and out[k] <= g]:
                remaining.discard(k)
            for k, step in ends.get(node, ()):
                c = step_cost(step)
                if c is not None and (out[k] is None or g + c < out[k]):
                    out[k] = g + c
            for e in self.adj.get(node, ()):
                v = E_v[e]
                if E_off[e] or v in done:
                    continue
                c = cost(e)
                if c is None:
                    continue
                ng = g + c * E_len[e]
                if ng < best.get(v, math.inf):
                    best[v] = ng
                    heapq.heappush(heap, (ng, next(tie), v))
        return out

    def search(self, origin, dest, edge_cost):
        """A* over the graph with virtual origin/destination nodes on their snapped edges.
        edge_cost(i) returns cost per metre multiplier (>= 1, so straight-line distance stays admissible) or None."""
        E_v, E_len, E_off = self.edges.v, self.edges.L, self.head_off
        O, D = 'O', 'D'
        tx, ty = xy(*self.clip(dest['edge'], dest['offset_m'], dest['offset_m'])[0])

        LL, HP = self.nodes.lonlat, self.head_pos

        def h(node):
            lon, lat = self.nodes[node][:2]
            x, y = xy(lon, lat)
            return math.hypot(x - tx, y - ty)

        def h_head(i):  # h() of edge i's head node, read from the columns
            p = 2 * HP[i]
            x, y = xy(LL[p], LL[p + 1])
            return math.hypot(x - tx, y - ty)

        def leaving(snapped):
            """(node, step) choices from a snapped point: forward along its edge, or backward along the twin."""
            i, off = snapped['edge'], snapped['offset_m']
            out = [(self.edges.v[i], (i, off, self.edges.L[i]))]
            j = self.twin(i)
            if j is not None:
                out.append((self.edges.v[j], (j, self.edges.L[j] - off, self.edges.L[j])))
            return out

        def arriving(snapped):
            """node -> step that ends at the snapped destination point."""
            i, off = snapped['edge'], snapped['offset_m']
            out = {self.edges[i][0]: (i, 0.0, off)}
            j = self.twin(i)
            if j is not None:
                out[self.edges[j][0]] = (j, 0.0, self.edges.L[j] - off)
            return out

        cost_cache = {}

        def cost(i):
            if i not in cost_cache:
                cost_cache[i] = edge_cost(i)
            return cost_cache[i]

        def step_cost(step):
            i, a, b = step
            c = cost(i)
            return None if c is None else c * (b - a)

        ends = arriving(dest)
        best = {O: 0.0}
        pred = {}
        heap = []
        tie = iter(range(1 << 62))  # equal (f, g) must never fall through to comparing node ids (ints vs 'O'/'D')
        # Same-edge trip: walk directly between the two snapped points.
        if origin['edge'] in (dest['edge'], self.twin(dest['edge'])):
            i = dest['edge']
            a, b = (origin['offset_m'] if origin['edge'] == i else self.edges.L[i] - origin['offset_m']), dest['offset_m']
            step = (i, a, b) if a <= b else (self.twin(i), self.edges.L[i] - a, self.edges.L[i] - b) if self.twin(i) is not None else None
            if step and step_cost(step) is not None:
                best[D] = step_cost(step); pred[D] = (O, step)
                heapq.heappush(heap, (best[D], best[D], next(tie), D))
        for node, step in leaving(origin):
            c = step_cost(step)
            if c is not None and c < best.get(node, math.inf):
                best[node] = c; pred[node] = (O, step)
                heapq.heappush(heap, (c + h(node), c, next(tie), node))
        done = set()
        while heap:
            f, g, _, node = heapq.heappop(heap)
            if node in done or g > best.get(node, math.inf):
                continue
            if node == D:
                break
            done.add(node)
            if node in ends:
                c = step_cost(ends[node])
                if c is not None and g + c < best.get(D, math.inf):
                    best[D] = g + c; pred[D] = (node, ends[node])
                    heapq.heappush(heap, (best[D], best[D], next(tie), D))
            for i in self.adj.get(node, ()):
                v = E_v[i]
                if E_off[i] or v in done:
                    continue
                c = cost(i)
                if c is None:
                    continue
                ng = g + c * E_len[i]
                if ng < best.get(v, math.inf):
                    best[v] = ng; pred[v] = (node, (i, 0.0, E_len[i]))
                    heapq.heappush(heap, (ng + h_head(i), ng, next(tie), v))
        if D not in pred:
            return None
        steps, node = [], D
        while node != O:
            node, step = pred[node]
            steps.append(step)
        return steps[::-1]


def preference_weights(preferences):
    """Expressed preferences only (weight > 0); if none are expressed every dimension counts equally.
    Weights describe the user, never the street: they are kept separate from the objective scores."""
    prefs = preferences or {}
    weights, dirs = prefs.get('weights') or {}, prefs.get('directions') or {}
    expressed = {d: float(w) for d, w in weights.items() if d in DIMENSIONS and w and float(w) > 0}
    if expressed:
        return {d: (w, dirs.get(d, 'high')) for d, w in expressed.items()}, True
    return {d: (50.0, 'high') for d in DIMENSIONS}, False


class RoutePlanner:
    def __init__(self, network):
        self.net = network
        self.routes = OrderedDict()  # route_id -> navigation-ready route, for progress/off-route queries
        self.route_sizes = {}
        self.nav_routes = OrderedDict()
        self.nav_sizes = {}
        self.lock = threading.Lock()

    def edge_utility(self, gi, weights):
        """0..1 preference fit of one edge; missing dimensions count as neutral 0.5 (never as good or bad)."""
        sv, cv = self.net.gscores.scores(gi)
        num = den = 0.0
        for j, d in enumerate(DIMENSIONS):
            if d not in weights:
                continue
            w, direction = weights[d]
            den += w
            v, c = sv[j], cv[j]
            if v is None:
                continue
            fit = (v if direction == 'high' else 100 - v) / 100
            num += w * c * (fit - .5)
        return .5 + (num / den if den else 0.0)

    def plan(self, origin, destination, preferences=None, constraints=None, weather=None):
        t0 = time.time()
        net = self.net
        constraints = constraints or {}
        avoid_stairs = bool(constraints.get('avoid_stairs'))
        sf = net.step_free_nodes() if avoid_stairs else None
        no_steps = (lambda i: not net.edges.steps(i) and net.edges[i][0] in sf and net.edges.v[i] in sf) if avoid_stairs else None
        o = net.snap(origin['lon'], origin['lat'], 'Origin', no_steps)
        d = net.snap(destination['lon'], destination['lat'], 'Destination', no_steps)
        weights, expressed = preference_weights(preferences)
        crime_pref = crime_field = None
        if (preferences or {}).get('crime') is not None:
            from . import crime
            crime_pref = crime.validate(preferences['crime'])
            crime_field = crime.edge_field(net, crime_pref)
        water_pref=water_data=None
        if (preferences or {}).get('waterfront') is not None:
            from . import waterfront
            water_pref=waterfront.validate(preferences['waterfront']);water_data=waterfront.data(net)
        # Weather: a dynamic context, separate from the 12 static scores. It adds a cost only when assess() finds a factor
        # with spatial evidence (daytime heat → tree-cover proxy); otherwise every search below is exactly the static one.
        wctx = wx.assess(wx.validate_snapshot(weather), evidence_available=bool(net.segment_raw) or bool(net.gscores.raw_at))
        heat = wctx['routing']['level'] * wctx['routing']['multiplier'] if wctx['routing']['active'] else 0.0
        exposure = net.heat_exposure()[0] if heat else None
        heat_coef = wx.CONFIG['heat']['edge_coefficient'] * heat

        def allowed(i):
            return not (avoid_stairs and net.edges.steps(i))

        def length_cost(i):
            return 1.0 if allowed(i) else None

        def experience_cost(lam, penalties=None):
            def f(i):
                if not allowed(i):
                    return None
                gi = net.edges.G[i]
                c = 1.0 + lam * (1.0 - net_utility(gi))
                return c * (penalties.get(gi, 1.0) if penalties else 1.0)
            return f

        util_cache = {}

        def net_utility(gi):
            if gi not in util_cache:
                util_cache[gi] = self.edge_utility(gi, weights)
            return util_cache[gi]

        def weather_cost(i):
            c = experience_cost(0.8)(i)
            return None if c is None else c + heat_coef * exposure[net.edges.G[i]]

        specs = [('shortest', 'Shortest Walk', length_cost)]
        specs += [('experience', 'Best Experience Match', experience_cost(2.0)), ('experience_balanced', 'Balanced Experience Route', experience_cost(0.8))]
        if crime_pref:
            # Use the same high/low candidate pool for a comparable ranking, regardless of requested direction.
            def crime_cost(direction, strength):
                def cost(i):
                    base = experience_cost(.8)(i)
                    if base is None: return None
                    value = crime.fit(crime_field['values'][net.edges.G[i]], direction, crime_field['scale'])
                    return base + strength*(1-value)
                return cost
            for direction in ('high', 'low'):
                for strength in (.6, 2.0):
                    specs.append(('crime_'+direction, 'Reported Complaint Density · '+direction, crime_cost(direction,strength)))
        if water_pref:
            def water_cost(direction,strength):
                def cost(i):
                    base=experience_cost(.8)(i)
                    if base is None:return None
                    share=water_data['within_100m_share'][net.edges.G[i]]
                    return base+strength*(1-(share if direction=='high' else 1-share))
                return cost
            for direction in ('high','low'):
                for strength in (.6,2.0):specs.append(('waterfront_'+direction,'Water Proximity · '+direction,water_cost(direction,strength)))
        if (crime_pref or water_pref) and (expressed or (crime_pref and water_pref)):
            def combined_cost(i):
                if not allowed(i):return None
                gi=net.edges.G[i];core_weight=sum(w for w,_ in weights.values()) if expressed else 0
                total=core_weight;matched=core_weight*net_utility(gi)
                if crime_pref:
                    total+=crime_pref['weight'];matched+=crime_pref['weight']*crime.fit(crime_field['values'][gi],crime_pref['direction'],crime_field['scale'])
                if water_pref:
                    share=water_data['within_100m_share'][gi];total+=water_pref['weight'];matched+=water_pref['weight']*(share if water_pref['direction']=='high' else 1-share)
                return 1+2*(1-matched/total)
            specs.append(('multi_objective','Combined Independent + Experience Route',combined_cost))
        candidates = []
        for objective, name, fn in specs:
            steps = net.search(o, d, fn)
            if steps is None:
                if objective == 'shortest':
                    raise RoutingError('No walkable connection exists between these points' + (' without stairs.' if avoid_stairs else '.'))
                continue
            candidates.append((objective, name, steps))
        # Diversity: penalise edges already used and search again, so alternatives are genuinely different paths.
        used = {}
        for _, _, steps in candidates:
            for i, *_ in steps:
                used[net.edges.G[i]] = 1.8
        for _ in range(2):
            steps = net.search(o, d, experience_cost(1.2, used))
            if steps is None:
                break
            candidates.append(('alternative', 'Alternative Experience Route', steps))
            for i, *_ in steps:
                used[net.edges.G[i]] = used.get(net.edges.G[i], 1.0) * 1.8
        # The static candidates above are unchanged by weather; a hot day adds one more search with the heat term.
        if heat:
            steps = net.search(o, d, weather_cost)
            if steps is not None:
                candidates.append(('weather_heat', 'Cooler Route (tree-cover proxy)', steps))

        routes = []
        for objective, name, steps in candidates:
            r = self.build_route(objective, name, steps, o, d, origin, destination)
            if any(overlap(r, x) > .85 for x in routes):
                continue  # same path found by another objective: keep one copy, never relabel duplicates
            routes.append(r)
        alts = [r for r in routes if r['objective'] == 'alternative']
        for n, r in enumerate(alts[1:], 2):
            r['route_name'] = f'Alternative Experience Route {n}'
        shortest = min(r['distance_m'] for r in routes)
        max_minutes = constraints.get('max_minutes')
        max_km = constraints.get('max_km')
        max_detour = constraints.get('max_detour_pct') if constraints.get('avoid_detours', True) else None
        for r in routes:
            r['detour_percentage'] = round((r['distance_m'] / shortest - 1) * 100, 1) if shortest else 0.0
            violations = []
            if max_minutes is not None and r['estimated_duration_min'] > max_minutes + 1e-6:
                violations.append(f"{r['estimated_duration_min']:.0f} min exceeds the {max_minutes:g}-minute limit")
            if max_km is not None and r['distance_m'] > max_km * 1000 + 1e-6:
                violations.append(f"{r['distance_m'] / 1000:.1f} km exceeds the {max_km:g} km limit")
            if max_detour is not None and r['detour_percentage'] > max_detour + 1e-6:
                violations.append(f"{r['detour_percentage']:.0f}% detour exceeds the {max_detour:g}% limit")
            r['constraints'] = {'feasible': not violations, 'violations': violations, 'avoid_stairs': avoid_stairs,
                                'contains_steps': any(e['pedestrian_access']['steps'] for e in r['edges'])}
            self.personalize(r, weights, expressed)
            self.weather_fields(r, wctx, heat)
            if crime_pref:
                crime.apply(r, crime_pref, crime_field, weights if expressed else {})
            if water_pref:waterfront.apply(r,water_pref,net,weights if expressed else {})
            r['maneuvers'] = mv.build(r, net)
            r['route_signature'] = route_signature(r)
            r['validation'] = qa.validate(r, net, {'max_minutes': max_minutes, 'max_km': max_km, 'avoid_stairs': avoid_stairs},
                                          [{'name': 'Destination', 'lat': destination['lat'], 'lon': destination['lon'], 'required': True,
                                            'snap_distance_m': d['snap_distance_m']}])
        static_key = lambda r: (not r['constraints']['feasible'], -r['personalized_score']['utility'] - r['personalized_score'].get('weather_adjustment', 0), r['distance_m'])
        baseline = min((r for r in routes if r['objective'] != 'weather_heat'), key=static_key, default=None)
        ranked = sorted(routes, key=lambda r: (not r['constraints']['feasible'], -r['personalized_score']['utility'], r['distance_m']))
        for n, r in enumerate(ranked, 1):
            r['rank'] = n
            r['recommended'] = n == 1 and r['constraints']['feasible']
            r['ranking_explanation'] = explain(r, ranked, weights, expressed)
        wctx['routing']['effect'] = weather_effect(ranked, baseline, heat)
        self.remember(ranked)
        return {
            'network_version': net.network_version, 'score_version': net.score_version,
            'origin': o, 'destination': d, 'shortest_distance_m': shortest,
            'preferences_used': {k: {'weight': w, 'direction': dr} for k, (w, dr) in weights.items()}, 'preferences_expressed': expressed or bool(crime_pref) or bool(water_pref),
            'independent_preferences_used': {**({'crime':crime.public_preference(crime_pref)} if crime_pref else {}),**({'waterfront':water_pref} if water_pref else {})},
            'constraints_used': {'max_minutes': max_minutes, 'max_km': max_km, 'max_detour_pct': max_detour, 'avoid_detours': constraints.get('avoid_detours', True), 'avoid_stairs': avoid_stairs},
            'feasible_count': sum(r['constraints']['feasible'] for r in ranked),
            'routes': ranked, 'compute_seconds': round(time.time() - t0, 2), 'weather_routing': wctx,
            'notes': ['Walking time uses a fixed 4.8 km/h planning pace; no live pedestrian or traffic data.',
                      'Scores are relative ranks among the street segments of Manhattan, Brooklyn and Queens (0–100), not calibrated experience scores. N/A dimensions are excluded, never counted as zero.'],
        }

    def remember(self, routes):
        """Only navigation geometry is needed after responding; full scored objects stay with the client."""
        with self.lock:
            for r in routes:
                slim={k:r[k] for k in ('route_id','geometry','distance_m','network_version','ordered_edge_ids')}
                slim['edges']=[{k:e[k] for k in ('edge_id','traversed_length_m')} for e in r['edges']]
                self.nav_routes[r['route_id']]=slim
                self.nav_sizes[r['route_id']]=len(json.dumps(slim,separators=(',',':')))
            while len(self.nav_routes)>200 or sum(self.nav_sizes.values())>4*1024*1024:
                rid,_=self.nav_routes.popitem(last=False);self.nav_sizes.pop(rid,None)

    def build_route(self, objective, name, steps, o, d, origin, destination):
        """Route Object: geometry, distance and scores all come from the same ordered edge list."""
        net = self.net
        coords, edges, total = [], [], 0.0
        num, scored = [0.0] * 12, [0.0] * 12
        for i, a, b in steps:
            seg = net.clip(i, a, b)
            if coords and seg and coords[-1] == seg[0]:
                seg = seg[1:]
            coords += seg
            length = b - a
            total += length
            e = net.edge_object(i, traversed=length, offsets=(a, b))
            e['partial'] = a > 0.01 or b < net.edges.L[i] - 0.01
            edges.append(e)
            s = net.gscores[net.edges.G[i]]
            for j in range(12):
                if s['s'][j] is not None:
                    w = length * s['c'][j]
                    num[j] += w * s['s'][j]; scored[j] += w
        dims = {DIMENSIONS[j]: (round(num[j] / scored[j]) if scored[j] else None) for j in range(12)}
        cov = {DIMENSIONS[j]: round(scored[j] / total, 3) if total else 0.0 for j in range(12)}
        have = [v for v in dims.values() if v is not None]
        rid = 'rt-' + uuid.uuid4().hex[:10]
        duration = total / WALK_SPEED_M_PER_MIN
        return {
            'route_id': rid, 'route_name': name, 'objective': objective,
            'origin': {'input': origin, 'snapped_edge_id': o['edge_id'], 'snap_distance_m': o['snap_distance_m']},
            'destination': {'input': destination, 'snapped_edge_id': d['edge_id'], 'snap_distance_m': d['snap_distance_m']},
            'geometry': {'type': 'LineString', 'coordinates': coords},
            'ordered_edge_ids': [e['edge_id'] for e in edges], 'edges': edges,
            'distance_m': round(total, 1), 'estimated_duration_min': round(duration, 1),
            'dimension_scores': dims, 'overall_score': round(sum(have) / len(have)) if have else None,
            'data_coverage': {'by_dimension': cov, 'mean': round(sum(cov.values()) / 12, 3),
                              'low_coverage_dimensions': [k for k, v in cov.items() if v < LOW_COVERAGE]},
            'network_version': net.network_version, 'score_version': net.score_version,
            'navigation': {'state': 'planned', 'progress_m': 0.0, 'remaining_m': round(total, 1),
                           'remaining_min': round(duration, 1), 'off_route': False, 'current_edge_id': edges[0]['edge_id'] if edges else None,
                           'progress_endpoint': '/api/navigation/progress'},
        }

    def personalize(self, r, weights, expressed):
        """PersonalizedUtility = WeightedExperience − TravelCostPenalty. A dimension's route score is pulled toward the
        neutral 50 in proportion to its missing coverage, so sparse data can't produce a false high score."""
        parts, num, den = {}, 0.0, 0.0
        for dim, (w, direction) in weights.items():
            v, c = r['dimension_scores'][dim], r['data_coverage']['by_dimension'][dim]
            fit = None if v is None else (v if direction == 'high' else 100 - v)
            adjusted = 50 + c * (fit - 50) if fit is not None else 50
            parts[dim] = {'weight': w, 'direction': direction, 'route_score': v, 'coverage': c, 'adjusted_fit': round(adjusted, 1)}
            num += w * adjusted; den += w
        experience = num / den if den else 50.0
        penalty = 0.4 * max(0.0, r['detour_percentage'])  # 0.4 points per % longer than the shortest path
        r['personalized_score'] = {'utility': round(experience - penalty, 1), 'weighted_experience': round(experience, 1),
                                   'travel_cost_penalty': round(penalty, 1), 'components': parts, 'preferences_expressed': expressed,
                                   'formula': 'Σ w·(50 + coverage·(fit − 50)) / Σ w − 0.4 × detour %'}

    def weather_fields(self, r, wctx, heat):
        """Route heat exposure on the tree-cover proxy (always reported when weather data exists) and, only while heat routing
        is active, its ranking adjustment folded into the personalized utility."""
        if not wctx['data_available']:
            return
        exp, has, _ = self.net.heat_exposure()
        total = sum(e['traversed_length_m'] for e in r['edges']) or 1.0
        share = sum(exp[e['geometry_index']] * e['traversed_length_m'] for e in r['edges']) / total
        cov = sum(e['traversed_length_m'] for e in r['edges'] if has[e['geometry_index']]) / total
        r['weather'] = {'heat_exposure_share': round(share, 3), 'tree_cover_proxy_share': round(1 - share, 3), 'evidence_coverage': round(cov, 3),
                        'evidence': wx.EVIDENCE['heat']}
        if heat:
            ps = r['personalized_score']
            adj = round(wx.CONFIG['heat']['rank_points'] * heat * share, 1)
            ps['weather_adjustment'] = adj
            ps['utility'] = round(ps['utility'] - adj, 1)
            ps['formula'] += f" − {wx.CONFIG['heat']['rank_points']:g} × heat level × heat-exposed share (weather)"

    # --- navigation readiness ------------------------------------------------------------------------------
    def route_from_snapshot(self, snap):
        """Rebuild a route's geometry from this server's own network for a client-held snapshot (ordered edge IDs +
        network version). A snapshot from another network version is refused: the route must be planned again, never
        silently replaced by a different path."""
        if not isinstance(snap, dict) or snap.get('network_version') != self.net.network_version:
            raise RoutingError('This route was planned on another network version; plan it again.')
        ids = snap.get('ordered_edge_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 5000:
            raise RoutingError('Route snapshot has no edges.')
        coords, edges, total = [], [], 0.0
        for eid in ids:
            i = self.net.by_id.get(str(eid))
            if i is None:
                raise RoutingError(f'Edge {eid} is not on network {self.net.network_version}; plan the route again.')
            g = self.net.coords(i)
            if coords and coords[-1] == g[0]:
                g = g[1:]
            elif coords and math.dist(xy(*coords[-1]), xy(*g[0])) > 1.0:
                raise RoutingError('Route snapshot edges do not join; plan the route again.')
            coords += g
            total += self.net.edges.L[i]
            edges.append({'edge_id': str(eid), 'traversed_length_m': self.net.edges.L[i]})
        r = {'route_id': snap.get('route_id') or 'snapshot', 'geometry': {'type': 'LineString', 'coordinates': coords}, 'edges': edges, 'distance_m': total,
             'network_version': self.net.network_version, 'ordered_edge_ids': [str(x) for x in ids]}
        if snap.get('route_signature') and snap['route_signature'] != route_signature(r):
            raise RoutingError('Route snapshot signature does not match its edges.')
        return r

    def progress(self, route_id, lon, lat, accuracy_m=None, snapshot=None):
        """Where a reported position sits on a planned route. Pure geometry: no live tracking is claimed. Works from the
        in-memory route when this process planned it, otherwise from a client snapshot (restart-safe)."""
        with self.lock:
            r = self.routes.get(route_id) or self.nav_routes.get(route_id)
        if not r and snapshot:
            r = self.route_from_snapshot(snapshot)
        if not r:
            raise RoutingError('Unknown or expired route_id; plan the route again.')
        p = xy(lon, lat)
        g = [xy(*c) for c in r['geometry']['coordinates']]
        best, run = None, 0.0
        for a, b in zip(g, g[1:]):
            ux, uy = b[0] - a[0], b[1] - a[1]; l2 = ux * ux + uy * uy; seg = math.sqrt(l2)
            t = max(0.0, min(1.0, ((p[0] - a[0]) * ux + (p[1] - a[1]) * uy) / l2)) if l2 else 0.0
            dist = math.hypot(p[0] - a[0] - t * ux, p[1] - a[1] - t * uy)
            if best is None or dist < best[0]:
                best = (dist, run + t * seg)
            run += seg
        dist, along = best
        geo_total = run or 1
        progress = along / geo_total * r['distance_m']
        acc_ok = accuracy_m is None or accuracy_m <= 60
        off = dist > OFF_ROUTE_M and acc_ok
        cum, current = 0.0, None
        for e in r['edges']:
            cum += e['traversed_length_m']
            if cum >= progress:
                current = e['edge_id']; break
        remaining = max(0.0, r['distance_m'] - progress)
        state = 'off_route' if off else 'arrived' if remaining < 20 else 'on_route'
        return {'route_id': route_id, 'state': state, 'distance_from_route_m': round(dist, 1), 'progress_m': round(progress, 1),
                'remaining_m': round(remaining, 1), 'remaining_min': round(remaining / WALK_SPEED_M_PER_MIN, 1),
                'current_edge_id': current, 'off_route': off, 'reroute_recommended': off,
                'accuracy_considered': acc_ok, 'reroute_hint': 'POST /api/routes with origin = current position' if off else None}


def route_signature(r):
    """Stable identity of a route's path on a network version (for navigation sessions that survive restarts)."""
    import hashlib
    return hashlib.sha1((r['network_version'] + '|' + ','.join(r['ordered_edge_ids'])).encode()).hexdigest()[:16]


def weather_effect(ranked, baseline, heat):
    """How weather changed the recommendation, against the recommendation the static ranking alone would make."""
    best = next((r for r in ranked if r['recommended']), None)
    if not heat or not best or not baseline:
        return None
    changed = best['route_id'] != baseline['route_id']
    return {'baseline_route_id': baseline['route_id'], 'recommended_route_id': best['route_id'], 'changed': changed,
            'extra_minutes': round(best['estimated_duration_min'] - baseline['estimated_duration_min'], 1) if changed else 0.0,
            'exposure_reduction': round(baseline['weather']['heat_exposure_share'] - best['weather']['heat_exposure_share'], 3) if changed else 0.0}


def overlap(a, b):
    """Share of route a's length on street geometries that route b also uses (either direction)."""
    used = {e['geometry_index'] for e in b['edges']}
    return sum(e['traversed_length_m'] for e in a['edges'] if e['geometry_index'] in used) / (a['distance_m'] or 1)


def explain(r, ranked, weights, expressed):
    ps = r['personalized_score']
    top = sorted(ps['components'].items(), key=lambda kv: -kv[1]['weight'])[:4]
    shortest = min(ranked, key=lambda x: x['distance_m'])
    bits = []
    for dim, c in top:
        if c['route_score'] is None:
            bits.append(f'{dim} N/A')
            continue
        delta = '' if r is shortest or shortest['dimension_scores'][dim] is None else f" ({c['route_score'] - shortest['dimension_scores'][dim]:+d} vs shortest)"
        bits.append(f"{dim} {c['route_score']}{' (prefer less)' if c['direction'] == 'low' else ''}{delta}")
    basis = 'your expressed preferences' if expressed else 'all 12 dimensions equally (no preference expressed)'
    status = 'Recommended' if r.get('recommended') else 'Not feasible: ' + '; '.join(r['constraints']['violations']) if not r['constraints']['feasible'] else f"Ranked {r['rank']} of {len(ranked)}"
    low = r['data_coverage']['low_coverage_dimensions']
    if r.get('independent_metrics', {}).get('crime'):
        metric = r['independent_metrics']['crime']
        direction = ps['independent_components']['crime']['direction']
        return (f"{status}. Historical reported complaint density: {metric['count']} unique complaints within {metric['corridor_m']} m; "
                f"{metric['reported_incidents_per_route_km']:.1f} reports per route km, {metric['from']} to {metric['to_exclusive']} (exclusive). "
                f"Preference: {'higher' if direction=='high' else 'lower'} recorded density. Utility {ps['utility']} includes this independent objective, "
                f"{'your expressed experience weights and ' if expressed else ''}the {ps['travel_cost_penalty']} detour penalty. "
                "NYPD approximate historical locations; this is not a crime rate or a prediction of present personal safety.")
    if r.get('independent_metrics',{}).get('waterfront'):
        m=r['independent_metrics']['waterfront']
        return (f"{status}. {m['within_100m_share']:.1%} of sampled walking length lies within 100 m of official mapped water; "
                f"preference {'more' if m['direction']=='high' else 'less'} proximity. Utility {ps['utility']} includes this independent objective, "
                f"experience preferences and the {ps['travel_cost_penalty']} detour penalty. Physical proximity is not a verified view or promenade.")
    return (f"{status}. Personalized score {ps['utility']} = weighted experience {ps['weighted_experience']} − {ps['travel_cost_penalty']} detour penalty "
            f"(+{r['detour_percentage']}% vs shortest), weighted by {basis}. Route scores: {', '.join(bits)}."
            + (f" Low data coverage: {', '.join(low)}." if low else ''))


_planner, _error, _lock = None, None, threading.Lock()


def reset_planner():
    """Drop the loaded network so the next request reads freshly rebuilt files."""
    global _planner, _error
    with _lock:
        _planner, _error = None, None


def get_planner():
    """Load the network once per process; later requests reuse it."""
    global _planner, _error
    with _lock:
        if _planner is None and _error is None:
            try:
                _planner = RoutePlanner(PedestrianNetwork())
            except FileNotFoundError as e:
                _error = f'Pedestrian network not built: {os.path.basename(e.filename or "")} missing. Run scripts/build_pedestrian_network.py then scripts/match_lion_osm.py.'
            except Exception as e:  # corrupted or mismatched build
                _error = f'Pedestrian network unavailable: {e}'
    if _error:
        raise RuntimeError(_error)
    return _planner
