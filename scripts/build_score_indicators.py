#!/usr/bin/env python3
"""Write data/pedestrian/score-indicators.json: what each of the 12 route scores is made of.

A small static copy of the indicator definitions the ROUTER's scores were built with — taken verbatim from the
metadata of data/manhattan-streets.json (which scripts/streetwise_indicators.py wrote), so the route explanation
("Why this route?") can name the real indicators, sources and time windows without loading the 8 MB street file.
Nothing is defined here: labels, units, methods and roles are copied, never rewritten.

The file carries the same score_version as data/pedestrian/edge-scores.json.gz; the browser shows it only when it
matches the score_version of the route on screen, and tests/test_score_indicators.py fails if it goes stale.

Run after scripts/build_manhattan_streets.py / scripts/match_lion_osm.py:   python3 scripts/build_score_indicators.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STREETS = ROOT / 'data' / 'manhattan-streets.json'
OUT = ROOT / 'data' / 'pedestrian' / 'score-indicators.json'


def build():
    from routing.engine import DIMENSIONS
    meta = json.loads(STREETS.read_text())['metadata']
    assert len(meta['keys']) == len(DIMENSIONS) == 12
    return {
        'score_version': meta['score_version'], 'data_version': meta['data_version'], 'retrieved_at': meta['retrieved_at'],
        'value_note': meta['value'], 'score_method': meta['score_method'],
        'windows': {'noise_from': meta.get('noise_window_from'), 'collisions_from': meta.get('collision_window_from'),
                    'trees_inventory_updated': meta.get('trees_inventory_updated')},
        'source_labels': meta['source_labels'], 'record_counts': meta.get('record_counts'),
        'dimensions': {name: meta['indicators'][key] for name, key in zip(DIMENSIONS, meta['keys'])},
    }


if __name__ == '__main__':
    doc = build()
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n')
    print(f"wrote {OUT.relative_to(ROOT)} · {doc['score_version']} · {sum(len(v) for v in doc['dimensions'].values())} indicators")
