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
from bisect import bisect_left
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


class EdgeTable:
    """Read-only sequence of the network's directed edges, stored as columns instead of one tuple per edge.

    net.edges[i] still returns (u, v, k, gi, rev, length, osmids, tags) with the same values (tags and OSM way lists are
    shared objects, as intern_edges made them). A tuple per edge cost about 160 bytes; the columns cost about 30. The
    search loops read the two columns they need (v, length) directly, which is also faster than building a tuple."""

    def __init__(self, node_ids, U, V, K, G, R, L, W, T, ways, tags):
        self.node_ids = node_ids                  # node position → OSM node id
        self.U, self.K, self.G, self.R, self.L, self.W, self.T = U, K, G, R, L, W, T
        self.v = array('q', (node_ids[x] for x in V))   # head node id per edge (the search loops' hot read)
        self.ways, self.tags = ways, tags

    @classmethod
    def from_tuples(cls, edges):
        """From intern_edges output (the JSON load path), keeping its shared tag and way objects."""
        pos, ids, tag_ix, way_ix, tags, ways = {}, [], {}, {}, [], []
        cols = [array('i'), array('i'), array('i'), array('i'), array('b'), array('d'), array('i'), array('i')]
        for u, v, k, gi, rev, length, osmids, t in edges:
            for n in (u, v):
                if n not in pos:
                    pos[n] = len(ids); ids.append(n)
            w = way_ix.get(id(osmids))
            if w is None:
                w = way_ix[id(osmids)] = len(ways); ways.append(osmids)
            x = tag_ix.get(id(t))
            if x is None:
                x = tag_ix[id(t)] = len(tags); tags.append(t)
            for c, val in zip(cols, (pos[u], pos[v], k, gi, rev, length, w, x)):
                c.append(val)
        return cls(ids, *cols, ways, tags)

    def __len__(self):
        return len(self.U)

    def __eq__(self, other):
        return len(self) == len(other) and all(a == b for a, b in zip(self, other))

    def steps(self, i):
        """edges[i][7]['_steps'] without building the tuple."""
        return self.tags[self.T[i]]['_steps']

    def __getitem__(self, i):
        if i < 0:
            i += len(self.U)
        return (self.node_ids[self.U[i]], self.v[i], self.K[i], self.G[i], self.R[i], self.L[i],
                self.ways[self.W[i]], self.tags[self.T[i]])

    def __iter__(self):
        ids, ways, tags, v = self.node_ids, self.ways, self.tags, self.v
        for i, (u, k, gi, rev, length, w, t) in enumerate(zip(self.U, self.K, self.G, self.R, self.L, self.W, self.T)):
            yield (ids[u], v[i], k, gi, rev, length, ways[w], tags[t])


class NodeTable:
    """node id → [lon, lat, count, component], stored as columns sorted by node id (lookups by binary search).

    Same answers as the dictionary it replaces (each lookup returns a new list; callers only read it). A dictionary
    with a list per node cost about 170 bytes per node; the columns cost 32."""

    def __init__(self, ids, lonlat, count, comp):
        order = sorted(range(len(ids)), key=ids.__getitem__)
        self.ids = array('q', (ids[i] for i in order))
        self.lonlat = array('d', (x for i in order for x in (lonlat[2 * i], lonlat[2 * i + 1])))
        self.count = array('i', (count[i] for i in order))
        self.comp = array('i', (comp[i] for i in order))

    @classmethod
    def from_dict(cls, nodes):
        ids = list(nodes)
        return cls(ids, [x for n in ids for x in nodes[n][:2]], [nodes[n][2] for n in ids], [nodes[n][3] for n in ids])

    def pos(self, node):
        """Position of a node id, or -1."""
        try:
            p = bisect_left(self.ids, node)
        except TypeError:
            return -1
        return p if p < len(self.ids) and self.ids[p] == node else -1

    def at(self, p):
        return [self.lonlat[2 * p], self.lonlat[2 * p + 1], self.count[p], self.comp[p]]

    def __getitem__(self, node):
        p = self.pos(node)
        if p < 0:
            raise KeyError(node)
        return self.at(p)

    def get(self, node, default=None):
        p = self.pos(node)
        return default if p < 0 else self.at(p)

    def __contains__(self, node):
        return self.pos(node) >= 0

    def __len__(self):
        return len(self.ids)

    def __iter__(self):
        return iter(self.ids)

    def keys(self):
        return iter(self.ids)

    def values(self):
        return (self.at(p) for p in range(len(self.ids)))

    def items(self):
        return ((n, self.at(p)) for p, n in enumerate(self.ids))

    def __eq__(self, other):
        return dict(self.items()) == (dict(other.items()) if hasattr(other, 'items') else other)


class Adjacency:
    """node id → indexes of the edges leaving it, in edge order (compressed rows over NodeTable positions).

    Replaces a dictionary of lists (about 65 bytes per edge plus a list per node) with two integer arrays."""

    def __init__(self, nodes, edge_tails):
        n = len(nodes)
        tails = array('i', (nodes.pos(u) for u in edge_tails))
        off = array('i', bytes(4 * (n + 1)))
        for p in tails:
            off[p + 1] += 1
        for p in range(n):
            off[p + 1] += off[p]
        fill = array('i', off[:-1])
        idx = array('i', bytes(4 * len(tails)))
        for i, p in enumerate(tails):            # ascending i: each row keeps edge order
            idx[fill[p]] = i
            fill[p] += 1
        self.nodes, self.off, self.idx = nodes, off, idx

    def get(self, node, default=()):
        p = self.nodes.pos(node)
        if p < 0:
            return default
        a, b = self.off[p], self.off[p + 1]
        return self.idx[a:b] if b > a else default

    def __getitem__(self, node):
        r = self.get(node, None)
        if r is None:
            raise KeyError(node)
        return r

    def __contains__(self, node):
        return self.get(node, None) is not None


class WayPool:
    """The pack's OSM way-id lists as one flat column: pool[w] returns the list (a new one each time; callers only
    read it). 260,000 small Python lists of large integers cost about 30 MB; the columns cost about 4."""

    def __init__(self, ways):
        self.flat, self.off = array('q'), array('i', [0])
        for w in ways:
            self.flat.extend(w)
            self.off.append(len(self.flat))

    def __len__(self):
        return len(self.off) - 1

    def __getitem__(self, w):
        return list(self.flat[self.off[w]:self.off[w + 1]])
