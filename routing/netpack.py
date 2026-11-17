"""A compact binary copy of one area's routing network, so the server starts without parsing large JSON files.

Parsing data/pedestrian/<area>-walk-graph.json.gz and edge-scores.json.gz creates millions of short-lived Python
objects (every coordinate pair, every tag). They are freed after loading, but the process keeps most of that memory,
which is what made Manhattan alone use about 330 MB of a 512 MB server. This module writes the same network as a few
typed arrays plus a small JSON header, and reads it back without that peak.

The JSON files stay the source of truth. scripts/compile_network.py writes data/pedestrian/<area>-network.bin.gz from
them and records the SHA-256 of both inputs in the header; the router uses the binary file only when those hashes
match the JSON files on disk, and otherwise reads the JSON as before. tests/test_netpack.py checks that both paths give
identical edges, scores, geometries and routes.

Format (inside gzip): b'SWNET001', uint32 header length, header JSON (UTF-8), then each array as
uint8 typecode-length, typecode, uint64 item count, raw little-endian bytes, in the order listed in header['arrays'].
"""
from array import array
import gzip
import hashlib
import json
import struct
import sys

from .compact import PackedScores
from .geometry_store import PackedPolylines

MAGIC = b'SWNET001'
ARRAYS = ['node_id', 'node_lonlat', 'node_count', 'node_comp', 'coords', 'offsets',
          'e_u', 'e_v', 'e_k', 'e_gi', 'e_rev', 'e_len', 'e_ways', 'e_tags',
          'S', 'C', 'O', 'F', 'R', 'RI', 'g_src', 'g_q', 'g_kind', 'g_m', 'g_keys', 'g_raw_off', 'g_raw_keys']


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _little(a):
    if sys.byteorder != 'little':
        a = array(a.typecode, a)
        a.byteswap()
    return a


def pack(graph_path, scores_path, out_path):
    graph = json.load(gzip.open(graph_path, 'rt', encoding='utf-8'))
    scores = json.load(gzip.open(scores_path, 'rt', encoding='utf-8'))
    A = {}
    ids = list(graph['nodes'])
    pos = {int(k): i for i, k in enumerate(ids)}
    A['node_id'] = array('q', (int(k) for k in ids))
    A['node_lonlat'] = array('d', (x for k in ids for x in graph['nodes'][k][:2]))
    A['node_count'] = array('i', (graph['nodes'][k][2] for k in ids))
    A['node_comp'] = array('i', (graph['nodes'][k][3] for k in ids))
    geoms = PackedPolylines(graph['geoms'])
    A['coords'], A['offsets'] = geoms.coordinates, geoms.offsets
    tags, ways = {}, {}
    cols = {c: [] for c in ('e_u', 'e_v', 'e_k', 'e_gi', 'e_rev', 'e_len', 'e_ways', 'e_tags')}
    for u, v, k, gi, rev, length, osmids, t in graph['edges']:
        cols['e_u'].append(pos[u]); cols['e_v'].append(pos[v]); cols['e_k'].append(k); cols['e_gi'].append(gi)
        cols['e_rev'].append(rev); cols['e_len'].append(length)
        cols['e_ways'].append(ways.setdefault(json.dumps(osmids), len(ways)))
        cols['e_tags'].append(tags.setdefault(json.dumps(t, sort_keys=False, ensure_ascii=False), len(tags)))
    for c, tc in (('e_u', 'i'), ('e_v', 'i'), ('e_k', 'i'), ('e_gi', 'i'), ('e_rev', 'b'), ('e_len', 'd'), ('e_ways', 'i'), ('e_tags', 'i')):
        A[c] = array(tc, cols[c])
    P = PackedScores(scores['geoms'])
    strings, mpool, kpool, rkpool = {}, {}, {}, {}
    sid = lambda s: strings.setdefault(s, len(strings))
    A['S'], A['C'], A['O'], A['F'], A['R'], A['RI'] = P.S, P.C, P.O, P.F, P.R, P.RI
    A['g_src'] = array('i', (sid(x) for x in P.src))
    A['g_q'] = array('i', (sid(x) for x in P.q))
    A['g_kind'] = array('i', (sid(x) for x in P.kind))
    A['g_m'] = array('i', (mpool.setdefault(tuple(sid(x) for x in m), len(mpool)) for m in P.m))
    keys_of = P.keys_of or [P.common_keys] * P.n
    A['g_keys'] = array('i', (kpool.setdefault(k, len(kpool)) for k in keys_of))
    A['g_raw_off'] = array('q', (P.raw_at[gi][0] if gi in P.raw_at else -1 for gi in range(P.n)))
    A['g_raw_keys'] = array('i', (rkpool.setdefault(P.raw_at[gi][1], len(rkpool)) if gi in P.raw_at else -1 for gi in range(P.n)))
    header = {
        'graph_metadata': graph['metadata'], 'score_metadata': scores['metadata'],
        'inputs': {'graph_sha256': sha256(graph_path), 'scores_sha256': sha256(scores_path)},
        'tags': [json.loads(t) for t in tags], 'ways': [json.loads(w) for w in ways],
        'strings': list(strings), 'm_pool': [list(m) for m in mpool], 'key_pool': [list(k) for k in kpool],
        'raw_key_pool': [list(k) for k in rkpool], 'extra': {str(k): v for k, v in P.extra.items()},
        'arrays': ARRAYS,
    }
    h = json.dumps(header, ensure_ascii=False, separators=(',', ':')).encode()
    with open(out_path, 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, compresslevel=6, mtime=0) as f:  # reproducible bytes
        f.write(MAGIC + struct.pack('<I', len(h)) + h)
        for name in ARRAYS:
            a = _little(A[name])
            f.write(struct.pack('<B', len(a.typecode)) + a.typecode.encode() + struct.pack('<Q', len(a)))
            f.write(a.tobytes())
    return header


def read_header(path):
    with gzip.open(path, 'rb') as f:
        if f.read(8) != MAGIC:
            raise ValueError(f'{path}: not a STROLLANE network pack')
        (n,) = struct.unpack('<I', f.read(4))
        return json.loads(f.read(n))


def unpack(path):
    """→ (header, arrays) with every array in native byte order."""
    with gzip.open(path, 'rb') as f:
        if f.read(8) != MAGIC:
            raise ValueError(f'{path}: not a STROLLANE network pack')
        (n,) = struct.unpack('<I', f.read(4))
        header = json.loads(f.read(n))
        A = {}
        for name in header['arrays']:
            (tl,) = struct.unpack('<B', f.read(1))
            tc = f.read(tl).decode()
            (count,) = struct.unpack('<Q', f.read(8))
            a = array(tc)
            a.frombytes(f.read(count * a.itemsize))
            if sys.byteorder != 'little':
                a.byteswap()
            A[name] = a
    return header, A


def scores_from_pack(header, A, dims=12):
    """A PackedScores filled from the arrays, without building per-geometry dictionaries."""
    P = PackedScores.__new__(PackedScores)
    P.dims, P.n = dims, len(A['O'])
    P.S, P.C, P.O, P.F, P.R, P.RI = A['S'], A['C'], A['O'], A['F'], A['R'], A['RI']
    st = header['strings']
    P.src = [st[i] for i in A['g_src']]
    P.q = [st[i] for i in A['g_q']]
    P.kind = [st[i] for i in A['g_kind']]
    mp = [tuple(st[i] for i in m) for m in header['m_pool']]
    P.m = [mp[i] for i in A['g_m']]
    kp = [tuple(k) for k in header['key_pool']]
    P.keys_of, P.common_keys = [kp[i] for i in A['g_keys']], None
    rkp = [tuple(k) for k in header['raw_key_pool']]
    P.raw_at = {gi: (off, rkp[A['g_raw_keys'][gi]]) for gi, off in enumerate(A['g_raw_off']) if off >= 0}
    P.raw_keys = sorted({k for ks in rkp for k in ks})
    P.extra = {int(k): v for k, v in header['extra'].items()}
    return P
