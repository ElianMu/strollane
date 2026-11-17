#!/usr/bin/env python3
"""Compile an area's routing network into data/pedestrian/<area>-network.bin.gz (routing/netpack.py).

    python3 scripts/compile_network.py                 # Manhattan
    python3 scripts/compile_network.py --area brooklyn

Run after anything rewrites <area>-walk-graph.json.gz or the area's edge scores. The router checks the SHA-256 of
both JSON inputs recorded in the pack and falls back to the JSON when they differ, so a stale pack is never used.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from routing import netpack  # noqa: E402


def paths(area):
    p = os.path.join(ROOT, 'data', 'pedestrian')
    scores = 'edge-scores.json.gz' if area == 'manhattan' else f'{area}-edge-scores.json.gz'
    return os.path.join(p, f'{area}-walk-graph.json.gz'), os.path.join(p, scores), os.path.join(p, f'{area}-network.bin.gz')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--area', default='manhattan')
    graph, scores, out = paths(ap.parse_args().area)
    h = netpack.pack(graph, scores, out)
    print(f"wrote {os.path.relpath(out, ROOT)} ({os.path.getsize(out) / 1e6:.1f} MB) · {h['graph_metadata']['network_version']} · {h['score_metadata']['score_version']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
