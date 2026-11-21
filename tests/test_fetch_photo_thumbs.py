"""scripts/fetch_photo_thumbs.py: copies of the place photos for the published site (no network: a fake opener)."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib import error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import fetch_photo_thumbs as fpt  # noqa: E402

JPEG = b'\xff\xd8\xff\xe0' + b'0' * 100


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class FetchPhotoThumbs(unittest.TestCase):
    def index(self, d, paths):
        f = Path(d) / 'photos.json'
        f.write_text(json.dumps({'thumb_base': 'https://upload.wikimedia.org/wikipedia/commons/thumb/',
                                 'items': {f'p{k}': [p, 'a', 'CC BY-SA 4.0'] for k, p in enumerate(paths)}}))
        return f

    def test_saved_under_the_decoded_name_the_web_server_looks_up(self):
        p = '1/1a/View_%28north%29.jpg/330px-View_%28north%29.jpg'
        self.assertEqual(fpt.disk_path(p), '1/1a/View_(north).jpg/330px-View_(north).jpg')
        with self.assertRaises(ValueError):
            fpt.disk_path('../../etc/passwd')

    def test_downloads_once_then_copies_from_the_cache(self):
        calls = []

        def opener(req, timeout=0):
            calls.append(req.full_url)
            self.assertIn('STROLLANE', req.get_header('User-agent'))
            return Resp(JPEG)
        with tempfile.TemporaryDirectory() as d:
            idx = self.index(d, ['8/8a/A.jpg/330px-A.jpg', '5/5c/B.jpg/330px-B.jpg', '5/5c/B.jpg/330px-B.jpg'])
            have, total = fpt.build(Path(d) / 'out', Path(d) / 'cache', index=idx, opener=opener, sleep=lambda s: None)
            self.assertEqual((have, total, len(calls)), (2, 2, 2))
            self.assertEqual((Path(d) / 'out/8/8a/A.jpg/330px-A.jpg').read_bytes(), JPEG)
            fpt.build(Path(d) / 'out2', Path(d) / 'cache', index=idx, opener=opener, sleep=lambda s: None)
            self.assertEqual(len(calls), 2, 'the second build downloads nothing')
            self.assertTrue((Path(d) / 'out2/5/5c/B.jpg/330px-B.jpg').is_file())

    def test_waits_on_429_and_gives_up_on_404_and_on_html(self):
        answers = {'A': [error.HTTPError('u', 429, 'slow down', {'Retry-After': '1'}, None), Resp(JPEG)],
                   'B': [error.HTTPError('u', 404, 'gone', {}, None)], 'C': [Resp(b'<html>error</html>')]}
        waits = []

        def opener(req, timeout=0):
            r = answers[req.full_url.rsplit('/', 1)[-1][6]].pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        with tempfile.TemporaryDirectory() as d:
            idx = self.index(d, ['a/aa/A.jpg/330px-A.jpg', 'b/bb/B.jpg/330px-B.jpg', 'c/cc/C.jpg/330px-C.jpg'])
            have, total = fpt.build(Path(d) / 'out', None, index=idx, opener=opener, sleep=waits.append, workers=1)
            self.assertEqual((have, total), (1, 3))
            self.assertEqual(waits, [1.0])

    def test_the_site_workflow_runs_it_and_keeps_wikimedia_as_fallback(self):
        wf = (ROOT / '.github/workflows/pages.yml').read_text()
        self.assertIn('scripts/fetch_photo_thumbs.py --cache .thumb-cache --out _site/data/places/thumbs', wf)
        self.assertIn('continue-on-error: true', wf)
        js = (ROOT / 'route-photos.js').read_text()
        self.assertIn("LOCAL: 'data/places/thumbs/'", js)
        self.assertIn('data-fallback', js)


if __name__ == '__main__':
    unittest.main()
