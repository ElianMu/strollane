"""Compact in-memory forms of the routing network's per-edge data (standard library only).

The network used to keep the parsed JSON as it was: one list and one tag dictionary per directed edge, one dictionary
per edge geometry for its scores, and two dictionaries with an entry per edge for lookups. For Manhattan that was about
200 MB of Python objects; Brooklyn's network is 1.8 times larger. These classes hold the same values in far less memory
and answer the same questions with the same results:

  PackedScores   net.gscores[gi] still returns {'s': [...], 'c': [...], 'o': ..., 'src': ..., ...}; scores and
                 coverage live in byte arrays, direct-edge raw values in a float array with a fixed key order.
  EdgeIds        net.by_id.get('u-v-k') / 'u-v-k' in net.by_id, answered from the adjacency lists.
  GeomIndex      net.by_geom.get((gi, rev)), from two integer arrays.
  intern_edges   edges become tuples; identical tag dictionaries and OSM way lists are shared.

Values round-trip exactly: scores are integers 0–100 (or None), coverage has two decimals (stored ×100), match share
and raw values are kept as float64 with a flag for values that were integers in the JSON.
"""
from array import array
import math

NONE8 = 255


class PackedScores:
    """Read-only sequence of edge-score dictionaries, stored packed. Each access returns a new dict (callers may not
    mutate what they get; nothing in the routing code does)."""

    def __init__(self, geoms, dims=12):
        n = len(geoms)
        self.dims = dims
        self.S = array('B', bytes(n * dims))
        self.C = array('B', bytes(n * dims))
        self.O = array('h', [-1]) * n
        self.F = array('d', [0.0]) * n
        self.src, self.q, self.kind, self.m = [None] * n, [None] * n, [None] * n, [None] * n
        self.raw_at = {}                       # gi → offset into R, only for geometries that carry raw values
        self.raw_keys, raw_index = [], {}
        self.R = array('d')
        self.RI = array('B')                  # 1 where the JSON value was an integer, so it comes back as int
        self.extra = {}                        # any other key, kept as is (none today; keeps the class lossless)
        strings = {}
        empty = ()
        for gi, g in enumerate(geoms):
            s, c = g['s'], g['c']
            for j in range(dims):
                v = s[j]
                self.S[gi * dims + j] = NONE8 if v is None else int(v)
                self.C[gi * dims + j] = round(c[j] * 100)
            self.O[gi] = -1 if g.get('o') is None else int(g['o'])
            self.F[gi] = g.get('frac', 0.0)
            self.src[gi] = strings.setdefault(g.get('src'), g.get('src'))
            self.q[gi] = strings.setdefault(g.get('q'), g.get('q'))
            self.kind[gi] = strings.setdefault(g.get('kind'), g.get('kind'))
            m = g.get('m') or empty
            self.m[gi] = tuple(strings.setdefault(x, x) for x in m) if m else empty
            raw = g.get('raw')
            if raw is not None:
                for k in raw:
                    if k not in raw_index:
                        raw_index[k] = len(self.raw_keys)
                        self.raw_keys.append(k)
                self.raw_at[gi] = (len(self.R), tuple(raw))
                for k in raw:
                    v = raw[k]
                    self.R.append(math.nan if v is None else float(v))
                    self.RI.append(1 if isinstance(v, int) and not isinstance(v, bool) else 0)
            rest = {k: v for k, v in g.items() if k not in ('s', 'c', 'o', 'frac', 'src', 'q', 'kind', 'm', 'raw')}
            if rest:
                self.extra[gi] = rest
        self.n = n
        # Remember which geometries had an explicit 'frac' / 'o' key so dictionaries come back with the same keys.
        pool = {}
        self.keys_of = [pool.setdefault(tuple(g.keys()), tuple(g.keys())) for g in geoms] if _varied_keys(geoms) else None  # a few shared key orders
        self.common_keys = tuple(geoms[0].keys()) if geoms and self.keys_of is None else None

    def __len__(self):
        return self.n

    def scores(self, gi):
        """(scores, coverage) as two lists: the hot path of route search, without building the whole dict."""
        b = gi * self.dims
        return ([None if x == NONE8 else x for x in self.S[b:b + self.dims]], [x / 100 for x in self.C[b:b + self.dims]])

    def __getitem__(self, gi):
        if isinstance(gi, slice):
            return [self[i] for i in range(*gi.indices(self.n))]
        if gi < 0:
            gi += self.n
        if not 0 <= gi < self.n:
            raise IndexError(gi)
        s, c = self.scores(gi)
        full = {'s': s, 'o': None if self.O[gi] == -1 else self.O[gi], 'c': c, 'src': self.src[gi], 'q': self.q[gi],
                'kind': self.kind[gi], 'frac': self.F[gi], 'm': list(self.m[gi])}
        if gi in self.raw_at:
            off, keys = self.raw_at[gi]
            full['raw'] = {k: (None if math.isnan(self.R[off + n]) else int(self.R[off + n]) if self.RI[off + n] else self.R[off + n]) for n, k in enumerate(keys)}
        if gi in self.extra:
            full.update(self.extra[gi])
        keys = self.keys_of[gi] if self.keys_of is not None else self.common_keys
        return {k: full[k] for k in keys if k in full} if keys else full

    def __iter__(self):
        return (self[i] for i in range(self.n))


def _varied_keys(geoms):
    first = tuple(geoms[0].keys()) if geoms else ()
    return any(tuple(g.keys()) != first for g in geoms)


class EdgeIds:
    """'u-v-k' → edge index, computed from the adjacency lists instead of a dictionary with one string per edge."""

    def __init__(self, edges, adj):
        self.edges, self.adj = edges, adj

    def get(self, eid, default=None):
        try:
            u, v, k = (int(x) for x in str(eid).split('-'))
        except ValueError:
            return default
        for i in self.adj.get(u, ()):
            e = self.edges[i]
            if e[1] == v and e[2] == k:
                return i
        return default

    def __contains__(self, eid):
        return self.get(eid) is not None

    def __getitem__(self, eid):
        i = self.get(eid)
        if i is None:
            raise KeyError(eid)
        return i

    def __len__(self):
        return len(self.edges)


class GeomIndex:
    """(geometry index, reversed?) → edge index, from two arrays."""

    def __init__(self, edges, n_geoms):
        self.fwd = array('i', [-1]) * n_geoms
        self.rev = array('i', [-1]) * n_geoms
        for i, e in enumerate(edges):
            (self.rev if e[4] else self.fwd)[e[3]] = i

    def get(self, key, default=None):
        gi, rev = key
        if not 0 <= gi < len(self.fwd):
            return default
        i = (self.rev if rev else self.fwd)[gi]
        return default if i < 0 else i

    def __getitem__(self, key):
        i = self.get(key)
        if i is None:
            raise KeyError(key)
        return i

    def __contains__(self, key):
        return self.get(key) is not None


def intern_edges(edges, node_ids):
    """Edges as tuples; node ids, tag dictionaries and OSM way lists shared between edges that carry the same values.
    Tag dictionaries must already hold every derived key (e.g. '_steps') before this runs, since they become shared."""
    tag_pool, way_pool, out = {}, {}, []
    for u, v, k, gi, rev, length, osmids, tags in edges:
        tkey = tuple(sorted((a, tuple(b) if isinstance(b, list) else b) for a, b in tags.items()))
        tags = tag_pool.setdefault(tkey, tags)
        wkey = tuple(osmids) if isinstance(osmids, list) else osmids
        osmids = way_pool.setdefault(wkey, osmids)
        out.append((node_ids.get(u, u), node_ids.get(v, v), k, gi, rev, length, osmids, tags))
    return out
