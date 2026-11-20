#!/usr/bin/env python3
"""Join the Manhattan, Brooklyn and Queens walk networks into the one network the router uses.

    python3 scripts/merge_networks.py
    python3 scripts/compile_network.py --area nyc

Reads, per area, <area>-walk-graph.json.gz and its scored edges (edge-scores.json.gz for Manhattan,
<area>-edge-scores.json.gz otherwise; all on the one combined scale, scripts/dimensions/combine_areas.py), and writes
data/pedestrian/nyc-walk-graph.json.gz and nyc-edge-scores.json.gz in the same formats.

The networks are separate OSMnx downloads, joined on OSM node IDs, which are global: a bridge or a street that crosses
an area boundary appears in both downloads with the same nodes, so the joined network is continuous there. Where the
same directed edge (u, v, key) is in more than one network, the copy from the first area in AREAS is kept, with that
area's scores; the order puts each street with the area whose street segments scored it (walk graphs cut by an
OSM boundary keep edges that cross it, so neighbouring areas share border streets). Node attributes come from the
first network that has the node. Routable = the largest strongly connected component of the JOINED network, recomputed
here, as build_pedestrian_network.py does for one area.

Nothing is invented: every edge, geometry and score is copied from an input file; only indices and the component
labels are new.
"""
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data', 'pedestrian')
AREAS = ['manhattan', 'brooklyn', 'lic']
OUT_GRAPH, OUT_SCORES = os.path.join(P, 'nyc-walk-graph.json.gz'), os.path.join(P, 'nyc-edge-scores.json.gz')
OUT_EVIDENCE = os.path.join(P, 'area-segment-evidence.json.gz')


def scores_path(area):
    return os.path.join(P, 'edge-scores.json.gz' if area == 'manhattan' else f'{area}-edge-scores.json.gz')


def strongly_connected(nodes, edges):
    """Component label per node (0 = largest), iterative Kosaraju over directed edges."""
    out, inn = {n: [] for n in nodes}, {n: [] for n in nodes}
    for u, v in edges:
        out[u].append(v); inn[v].append(u)
    order, seen = [], set()
    for s in nodes:
        if s in seen:
            continue
        seen.add(s)
        stack = [(s, iter(out[s]))]
        while stack:
            n, it = stack[-1]
            for m in it:
                if m not in seen:
                    seen.add(m); stack.append((m, iter(out[m])))
                    break
            else:
                stack.pop(); order.append(n)
    comp, comps = {}, []
    for s in reversed(order):
        if s in comp:
            continue
        members, stack = [], [s]
        comp[s] = len(comps)
        while stack:
            n = stack.pop(); members.append(n)
            for m in inn[n]:
                if m not in comp:
                    comp[m] = len(comps); stack.append(m)
        comps.append(members)
    rank = {c: r for r, c in enumerate(sorted(range(len(comps)), key=lambda c: (-len(comps[c]), min(comps[c]))))}
    return {n: rank[c] for n, c in comp.items()}, len(comps)


def metres(line):
    from math import cos, hypot, radians
    return sum(hypot((b[0] - a[0]) * 111320 * cos(radians((a[1] + b[1]) / 2)), (b[1] - a[1]) * 110540) for a, b in zip(line, line[1:]))


def stitch_borders(graphs, scores):
    """Split an edge of one area at a node where another area's network stops.

    Each area's download is cut at its own boundary, so on a long bridge the two downloads can each end at a node that
    the other one only passes through: the Queensboro Bridge path in the Queens download ends at node 2089938148 near
    the Manhattan shore, which in the Manhattan download is a vertex inside its edge 593215787–3785591409. Joining on
    node IDs alone then leaves the bridge broken. For every dead end of one download that is not a node of any other but
    is an interior vertex of another download's edge (same OSM node, same coordinates), that edge and its reverse twin
    are split there into two edges. Geometry and scores are the original edge's (both halves keep its score record);
    the length is shared out in proportion to the measured lengths of the two halves."""
    node_sets = {a: set(g['nodes']) for a, g in graphs.items()}
    where = {}
    for a, g in graphs.items():
        for ei, e in enumerate(g['edges']):
            if e[4]:
                continue
            line = g['geoms'][e[3]]
            for vi in range(1, len(line) - 1):
                where.setdefault(tuple(line[vi]), []).append((a, ei, vi))
    cuts = []
    for a, g in graphs.items():
        for n, v in g['nodes'].items():
            if v[2] != 1 or any(n in node_sets[b] for b in graphs if b != a):
                continue
            for b, ei, vi in where.get((v[0], v[1]), ()):
                if b != a:
                    cuts.append((b, ei, vi, int(n), v))
    done = []
    # several cuts on one edge: the later vertex first, so each earlier cut still indexes the remaining first half
    for b, ei, vi, n, nv in sorted(cuts, key=lambda c: (c[0], c[1], -c[2])):
        g, sg = graphs[b], scores[b]['geoms']
        u, v, k, gi, rev, length, osmids, tags = g['edges'][ei]
        line = g['geoms'][gi]
        first, second = line[:vi + 1], line[vi:]
        share = metres(first) / max(metres(first) + metres(second), 1e-9)
        ga, gb = len(g['geoms']), len(g['geoms']) + 1
        g['geoms'] += [first, second]
        sg += [sg[gi], sg[gi]]
        la, lb = round(length * share, 2), round(length * (1 - share), 2)
        twin = next((j for j, t in enumerate(g['edges']) if t[0] == v and t[1] == u and t[2] == k and t[3] == gi and t[4] == 1), None)
        g['edges'][ei] = [u, n, k, ga, 0, la, osmids, tags]
        g['edges'].append([n, v, k, gb, 0, lb, osmids, tags])
        if twin is not None:
            g['edges'][twin] = [v, n, k, gb, 1, lb, osmids, tags]
            g['edges'].append([n, u, k, ga, 1, la, osmids, tags])
        g['nodes'].setdefault(str(n), [nv[0], nv[1], 2, 0])
        done.append({'area': b, 'edge': f'{u}-{v}-{k}', 'at_node': n, 'name': tags.get('name')})
    return done


def main():
    graphs = {a: json.load(gzip.open(os.path.join(P, f'{a}-walk-graph.json.gz'), 'rt', encoding='utf-8')) for a in AREAS}
    scores = {a: json.load(gzip.open(scores_path(a), 'rt', encoding='utf-8')) for a in AREAS}
    stitched = stitch_borders(graphs, scores)
    versions = {a: scores[a]['metadata']['score_version'] for a in AREAS}
    if len(set(versions.values())) != 1:
        sys.exit(f'edge scores are on different scales: {versions}. Rerun the transfer for every area.')
    for a in AREAS:
        if scores[a]['metadata']['network_version'] != graphs[a]['metadata']['network_version']:
            sys.exit(f'{a}: edge scores and walk graph are from different network versions.')

    nodes, edges, geoms, gscores, gmap = {}, [], [], [], {}
    seen_edges, from_area = set(), {a: {'edges': 0, 'skipped_duplicates': 0} for a in AREAS}
    for a in AREAS:
        g, sg = graphs[a], scores[a]['geoms']
        for k, v in g['nodes'].items():
            nodes.setdefault(k, list(v))
        for u, v, k, gi, rev, length, osmids, tags in g['edges']:
            if (u, v, k) in seen_edges:
                from_area[a]['skipped_duplicates'] += 1
                continue
            seen_edges.add((u, v, k))
            key = (a, gi)
            if key not in gmap:
                gmap[key] = len(geoms)
                geoms.append(g['geoms'][gi]); gscores.append(sg[gi])
            edges.append([u, v, k, gmap[key], rev, length, osmids, tags])
            from_area[a]['edges'] += 1

    comp, n_comp = strongly_connected(list(map(int, nodes)), [(e[0], e[1]) for e in edges])
    for k, v in nodes.items():
        v[3] = comp[int(k)]
    main_nodes = sum(1 for v in nodes.values() if v[3] == 0)

    digest = hashlib.sha1(json.dumps([graphs[a]['metadata']['network_version'] for a in AREAS]).encode()).hexdigest()[:8]
    built = datetime.now(timezone.utc).isoformat(timespec='seconds')
    m0 = graphs['manhattan']['metadata']
    gmeta = {**{k: m0[k] for k in ('source', 'osmnx_version', 'edge_fields', 'node_fields', 'edge_id', 'oneway_rule') if k in m0},
             'network_version': f'nyc3-{digest}', 'built_at': built, 'areas': AREAS,
             'area_network_versions': {a: graphs[a]['metadata']['network_version'] for a in AREAS},
             'boundary': 'Manhattan, Brooklyn and Queens (scripts/areas.py), joined on OSM node IDs',
             'boundary_bounds': [min(graphs[a]['metadata']['boundary_bounds'][0] for a in AREAS), min(graphs[a]['metadata']['boundary_bounds'][1] for a in AREAS),
                                 max(graphs[a]['metadata']['boundary_bounds'][2] for a in AREAS), max(graphs[a]['metadata']['boundary_bounds'][3] for a in AREAS)],
             'counts': {'nodes': len(nodes), 'edges': len(edges), 'geometries': len(geoms), 'components': n_comp, 'main_component_nodes': main_nodes,
                        'by_area': from_area},
             'merge': 'scripts/merge_networks.py: first area wins for a directed edge present in several downloads; components recomputed on the joined network.',
             'stitched_at_borders': stitched}
    routable_len, cov = 0.0, [0.0] * 12
    seen_g = set()
    for u, v, k, gi, rev, length, *_ in edges:
        if gi in seen_g or nodes[str(u)][3] != 0 or nodes[str(v)][3] != 0:
            continue
        seen_g.add(gi)
        routable_len += length
        for j in range(12):
            cov[j] += length * gscores[gi]['c'][j]
    s0 = scores['manhattan']['metadata']
    smeta = {'network_version': gmeta['network_version'], 'score_version': versions['manhattan'],
             'data_version': max(scores[a]['metadata']['data_version'] for a in AREAS), 'built_at': built, 'keys': s0['keys'],
             'geometries': len(gscores), 'sources': {s: sum(1 for x in gscores if x['src'] == s) for s in ('lion_match', 'direct_osm', 'none')},
             'routable_length_coverage_by_dimension': {k: round(cov[j] / max(routable_len, 1), 3) for j, k in enumerate(s0['keys'])},
             'by_area': {a: {k: scores[a]['metadata'].get(k) for k in ('network_version', 'indicator_basis', 'routable_length_coverage_by_dimension', 'direct_edge_indicators')} for a in AREAS},
             'ranking_reference_areas': s0.get('ranking_reference_areas'), 'fields': s0['fields'],
             'method': 'Per-area edge scores (scripts/transfer_dimension_scores.py) joined by scripts/merge_networks.py; all on one combined scale.'}
    for path, obj in ((OUT_GRAPH, {'metadata': gmeta, 'nodes': nodes, 'geoms': geoms, 'edges': edges}), (OUT_SCORES, {'metadata': smeta, 'geoms': gscores})):
        with open(path + '.tmp', 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as f:
            f.write(json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode())
        os.replace(path + '.tmp', path)
    # Street names and the two raw Nature values per street segment of the new areas, as segment-evidence.json.gz holds
    # them for Manhattan: names for route descriptions, tree_km / park_pct for the heat term of routing/weather.py.
    # park_pct is stored as 0–100 there; the map build stores a 0–1 share, so it is multiplied by 100 (same quantity).
    evidence = {}
    for a in AREAS[1:]:
        feats = json.load(open(os.path.join(ROOT, 'data', 'dimensions', a, 'segments.geojson'), encoding='utf-8'))['features']
        ind = json.load(open(os.path.join(ROOT, 'data', 'dimensions', a, 'indicators.json'), encoding='utf-8'))
        pos = {sid: i for i, sid in enumerate(ind['ids'])}
        for f in feats:
            p, i = f['properties'], pos[f['properties']['id']]
            t, pk = ind['raw']['tree_km'][i], ind['raw']['park_pct'][i]
            evidence[p['id']] = {'name': p['name'], 'source_segment_id': int(p['id'].split('-')[1]) if p['id'].split('-')[1].isdigit() else None,
                                 'tree_km': t, 'park_pct': None if pk is None else round(pk * 100, 1)}
    with open(OUT_EVIDENCE + '.tmp', 'wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as f:
        f.write(json.dumps({'metadata': {'areas': AREAS[1:], 'score_version': versions['manhattan'], 'records': len(evidence),
                                          'fields': {'tree_km': 'street trees per km (map build)', 'park_pct': 'share of samples in park land, 0–100'}},
                            'records': evidence}, separators=(',', ':'), ensure_ascii=False).encode())
    os.replace(OUT_EVIDENCE + '.tmp', OUT_EVIDENCE)
    print(json.dumps({'network_version': gmeta['network_version'], **gmeta['counts'], 'routable_km': round(routable_len / 1000),
                      'coverage': smeta['routable_length_coverage_by_dimension']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
