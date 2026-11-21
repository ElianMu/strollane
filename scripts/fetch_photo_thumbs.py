#!/usr/bin/env python3
"""Copies of the place photos (data/places/photos.json) for the published site: data/places/thumbs/<path>.

Why: the photos were loaded straight from upload.wikimedia.org. On an iPhone some of them came back as broken images
(2026-11-21: Roosevelt Triangle, Sheltering Arms Playground) while the same files loaded on a desktop: Wikimedia
answers some connections with refusals (rate limits on shared addresses such as iCloud Private Relay, thumbnails still
being rendered). A copy served with the site itself does not depend on that. The browser loads the copy first and
Wikimedia only when the copy is missing (route-photos.js photoImg), then the street photo.

The files are the same 330 px thumbnails, under their Commons licences; the credit (author · licence, linked to the
Commons page) is shown with every photo as before. They are not committed: the GitHub Pages workflow runs this script,
with a cache, so only new photos are downloaded.

Wikimedia throttles downloads from GitHub's machines (the first deploy got fewer than half the photos in its 15
minutes), so the downloading is done by its own daily workflow (.github/workflows/place-photos.yml), a little more
each run into an Actions cache; the site deploy only copies what that cache holds, after a short top-up.

Usage: python3 scripts/fetch_photo_thumbs.py --out _site/data/places/thumbs [--cache .thumb-cache] [--budget S] [--workers N]
"""
import argparse
import json
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'data' / 'places' / 'photos.json'
UA = 'STROLLANE/1.0 (https://github.com/ElianMu/strollane; site build, place photo thumbnails)'


def thumb_paths(doc):
    """The thumbnail paths of the index, as written there (percent-encoded), each once."""
    return sorted({str(v[0]) for v in (doc.get('items') or {}).values() if v and v[0]})


def disk_path(path):
    """Where a thumbnail lives under the thumbs folder. The browser asks for data/places/thumbs/<path as written>;
    the web server decodes the percent-encoding, so the file carries the decoded name."""
    p = parse.unquote(path)
    if p.startswith('/') or '..' in Path(p).parts:
        raise ValueError(f'unsafe thumbnail path: {path}')
    return p


def fetch(url, opener=request.urlopen, tries=4, sleep=time.sleep, seen=None):
    """Bytes of one thumbnail, or None. Waits and tries again on 429 and 5xx (Retry-After, at most 60 s).
    seen, a Counter, gets one count per attempt: 'ok', 'not an image', 'HTTP <code>' or 'network'."""
    seen = seen if seen is not None else Counter()
    for k in range(tries):
        try:
            with opener(request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                body = r.read()
                good = body[:3] in (b'\xff\xd8\xff', b'\x89PN', b'GIF', b'RIF')
                seen['ok' if good else 'not an image'] += 1
                return body if good else None
        except error.HTTPError as e:
            seen[f'HTTP {e.code}'] += 1
            if e.code != 429 and e.code < 500:
                return None
            wait = e.headers.get('Retry-After') if e.headers else None
            sleep(min(60, float(wait) if wait and wait.isdigit() else 2 ** (k + 2)))
        except (error.URLError, TimeoutError, OSError):
            seen['network'] += 1
            sleep(2 ** (k + 1))
    return None


def build(out, cache=None, index=INDEX, opener=request.urlopen, workers=4, sleep=time.sleep, budget_s=15 * 60):
    """Downloads what the cache lacks, then copies every thumbnail it has into out. Returns (have, total)."""
    doc = json.loads(Path(index).read_text(encoding='utf-8'))
    base = doc.get('thumb_base') or 'https://upload.wikimedia.org/wikipedia/commons/thumb/'
    store = Path(cache or out)
    paths = thumb_paths(doc)
    missing = [p for p in paths if not (store / disk_path(p)).is_file()]
    started = time.time()
    seen = Counter()

    def one(p):
        if time.time() - started > budget_s:
            seen['skipped, out of time'] += 1
            return False
        body = fetch(base + p, opener=opener, sleep=sleep, seen=seen)
        if not body:
            return False
        f = store / disk_path(p)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
        return True

    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = sum(pool.map(one, missing))
    have = 0
    for p in paths:
        src = store / disk_path(p)
        if not src.is_file():
            continue
        have += 1
        if cache and Path(cache).resolve() != Path(out).resolve():
            dst = Path(out) / disk_path(p)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    print(f'{have}/{len(paths)} photo thumbnails in {out} ({len(missing) - got} not downloaded this time)')
    if missing:
        # An annotation, so the reason a run fell short can be read from the run summary.
        tally = ', '.join(f'{k} {v}' for k, v in seen.most_common())
        print(f'::notice::photos: {have}/{len(paths)} on hand; {got} of {len(missing)} missing downloaded; tries: {tally}')
    return have, len(paths)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--cache', type=Path)
    ap.add_argument('--budget', type=float, default=15 * 60, help='seconds to spend downloading')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args(argv)
    have, total = build(a.out, a.cache, workers=a.workers, budget_s=a.budget)
    if total and have < total * 0.5:
        print('::warning::fewer than half the photos were copied; the site falls back to Wikimedia for the rest', file=sys.stderr)


if __name__ == '__main__':
    main()
