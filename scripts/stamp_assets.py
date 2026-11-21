#!/usr/bin/env python3
"""Cache-busting by content, run on the published copy of the site.

    python3 scripts/stamp_assets.py _site        (the Pages workflow, after copying the web files)

Every local script and stylesheet an HTML page loads gets ?v=<first 10 hex digits of the file's SHA-256>, and sw.js's
CACHE name becomes a hash of index.html and all of those files. A changed file therefore always gets a new URL and
reaches visitors; an unchanged one keeps its URL and stays cached.

Until 2026-11-21 the ?v= numbers were raised by hand, and one forgotten raise (route-story.js after PR #47) kept
visitors on the old file. The numbers in the repository are now only what a local copy of the site uses; the
published site's come from this script. External URLs (the MapLibre CDN) are left as they are.
"""
import hashlib
import pathlib
import re
import sys

ASSET = re.compile(r'''((?:src|href)=["'])((?!https?:|//|data:)[^"'?#]+\.(?:js|css))(?:\?[^"'#]*)?(["'])''')
CACHE_LINE = re.compile(r"^const CACHE = '[^']*';.*$", re.M)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def stamp_page(site, page):
    """Rewrite one HTML page's local asset URLs; returns {asset path: digest} for the files it found."""
    text = page.read_text(encoding='utf-8')
    found = {}

    def put(m):
        f = (page.parent / m.group(2)).resolve()
        if not f.is_file() or site not in f.parents:
            return m.group(0)
        rel = str(f.relative_to(site))
        found[rel] = digest(f)
        return f'{m.group(1)}{m.group(2)}?v={found[rel]}{m.group(3)}'

    page.write_text(ASSET.sub(put, text), encoding='utf-8')
    return found


def main(site_dir):
    site = pathlib.Path(site_dir).resolve()
    pages = sorted(site.glob('*.html'))
    if not (site / 'index.html').is_file():
        raise SystemExit(f'{site} has no index.html')
    assets = {}
    for page in pages:
        assets.update(stamp_page(site, page))
    sw = site / 'sw.js'
    if sw.is_file():
        shell = hashlib.sha256((site / 'index.html').read_bytes())
        for rel, d in sorted(assets.items()):
            shell.update(f'{rel}={d};'.encode())
        text = sw.read_text(encoding='utf-8')
        new, n = CACHE_LINE.subn(f"const CACHE = 'strollane-shell-{shell.hexdigest()[:10]}'; // set by scripts/stamp_assets.py", text, count=1)
        if n != 1:
            raise SystemExit('sw.js: no "const CACHE = ..." line to stamp')
        sw.write_text(new, encoding='utf-8')
    print(f'stamped {len(assets)} assets in {len(pages)} pages' + (' and the service worker cache name' if sw.is_file() else ''))
    return assets


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '_site')
