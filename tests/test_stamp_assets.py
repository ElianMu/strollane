"""scripts/stamp_assets.py: the published site's asset URLs follow the files' contents."""
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import stamp_assets  # noqa: E402


class StampAssets(unittest.TestCase):
    def site(self):
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        (d / 'a.js').write_text('one')
        (d / 'b.css').write_text('two')
        (d / 'index.html').write_text('<link href="b.css?v=3"><script src="a.js?v=9"></script>'
                                      '<script src="https://cdn.example/x.js?v=1"></script><script src="gone.js?v=2"></script>')
        (d / 'sw.js').write_text("'use strict';\nconst CACHE = 'strollane-shell-v72'; // note\nconst X = 1;\n")
        return d

    def test_urls_follow_contents(self):
        d = self.site()
        stamp_assets.main(d)
        html = (d / 'index.html').read_text()
        self.assertIn(f'a.js?v={stamp_assets.digest(d / "a.js")}', html)
        self.assertIn(f'b.css?v={stamp_assets.digest(d / "b.css")}', html)
        self.assertIn('https://cdn.example/x.js?v=1', html, 'an external URL is left as it is')
        self.assertIn('gone.js?v=2', html, 'a file that is not there is left as it is')
        first_sw = (d / 'sw.js').read_text()
        self.assertRegex(first_sw, r"const CACHE = 'strollane-shell-[0-9a-f]{10}';")
        self.assertIn('const X = 1;', first_sw)
        # a changed script gets a new URL and a new service worker cache; an unchanged stylesheet keeps its URL
        (d / 'a.js').write_text('one, changed')
        css_before = stamp_assets.digest(d / 'b.css')
        stamp_assets.main(d)
        html2 = (d / 'index.html').read_text()
        self.assertIn(f'a.js?v={stamp_assets.digest(d / "a.js")}', html2)
        self.assertIn(f'b.css?v={css_before}', html2)
        self.assertNotEqual(first_sw, (d / 'sw.js').read_text())

    def test_real_site(self):
        """The repository's own pages: every local script and stylesheet index.html loads exists, and gets stamped."""
        d = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        for name in [p.name for p in ROOT.glob('*') if p.suffix in ('.html', '.js', '.css')]:
            shutil.copy(ROOT / name, d / name)
        assets = stamp_assets.main(d)
        self.assertGreater(len(assets), 30)
        self.assertNotRegex((d / 'index.html').read_text(), r'src="[a-z-]+\.js\?v=\d{1,3}"', 'no hand-kept number left')


if __name__ == '__main__':
    unittest.main()
