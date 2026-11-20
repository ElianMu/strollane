#!/usr/bin/env python3
"""Summarise the post-walk checks (routing/walkcheck.py) per user type, as a Markdown table for the study write-up.

Reads walk-checks/*.jsonl from the feedback-data branch of this repository:

    git fetch origin feedback-data
    python3 scripts/summarize_walk_checks.py                  # all checks
    python3 scripts/summarize_walk_checks.py --study-only     # only answers with a study code (walk-along participants)

Nothing is invented: with no checks it says so.
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from routing import walkcheck as wc  # noqa: E402


def load(ref):
    names = subprocess.run(['git', 'ls-tree', '--name-only', ref, 'walk-checks/'], cwd=ROOT, capture_output=True, text=True)
    if names.returncode:
        sys.exit(f'No {ref} branch here: run git fetch origin feedback-data first.')
    rows = []
    for n in sorted(names.stdout.split()):
        if n.endswith('.jsonl'):
            text = subprocess.run(['git', 'show', f'{ref}:{n}'], cwd=ROOT, capture_output=True, text=True, check=True).stdout
            rows += [json.loads(line) for line in text.splitlines() if line.strip()]
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--ref', default='origin/feedback-data')
    ap.add_argument('--study-only', action='store_true')
    a = ap.parse_args()
    rows = load(a.ref)
    if a.study_only:
        rows = [r for r in rows if r.get('study_code')]
    if not rows:
        print('No post-walk checks yet.')
        return
    s = wc.summary(rows)
    print(f"{len(rows)} post-walk checks, {rows[0]['at'][:10]} to {rows[-1]['at'][:10]}" + (' (study participants only)' if a.study_only else ''))
    print()
    print('| User type | Checks | Mean match (1–5) | 1 / 2 / 3 / 4 / 5 | Detour worth it: yes / no | Fitted better: this / shortest / same | Participants |')
    print('|---|---|---|---|---|---|---|')
    for t in wc.USER_TYPES + ('all',):
        if t in s:
            x = s[t]
            print(f"| {t} | {x['n']} | {x['mean_match']} | {' / '.join(str(x['match_counts'][str(k)]) for k in range(1, 6))} | "
                  f"{x['worth_detour']['yes']} / {x['worth_detour']['no']} | "
                  f"{' / '.join(str(x['compared_with_shortest'][k]) for k in wc.COMPARED)} | {x['study_participants']} |")


if __name__ == '__main__':
    main()
