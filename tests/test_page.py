"""The built page: every word the script asks for exists, nothing private ships, and nothing inline breaks the CSP."""
import re
import unittest
from pathlib import Path

from app import never, words

HERE = Path(__file__).resolve().parent.parent
SITE = HERE.joinpath("site")


@unittest.skipUnless(SITE.joinpath("data.js").exists(), "build the page first")
class Page(unittest.TestCase):
    def test_every_word_the_script_uses_exists(self):
        js = SITE.joinpath("app.js").read_text(encoding="utf-8")
        ui = words.load().ui()
        used = set(re.findall(r'word\("([a-z0-9_.]+)"', js)) | set(re.findall(r'U\["([a-z0-9_.]+)"\]', js))
        missing = sorted(k for k in used if k not in ui)
        self.assertEqual(missing, [])

    def test_nothing_private_ships(self):
        found = {}
        for name in ("index.html", "app.js", "app.css", "claims.js", "data.js", "code.js"):
            hits = never.hits(SITE.joinpath(name).read_text(encoding="utf-8"))
            if hits:
                found[name] = len(hits)
        self.assertEqual(found, {})

    def test_nothing_inline(self):
        html = SITE.joinpath("index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"\sstyle=")
        self.assertNotRegex(html, r"<script>[^<]")
        self.assertNotRegex(html, r"\son[a-z]+=")

    def test_no_request_leaves_the_site(self):
        html = SITE.joinpath("index.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"src=['\"](?:https?:)?//")
        for name in ("app.js", "claims.js"):
            self.assertNotRegex(SITE.joinpath(name).read_text(encoding="utf-8"), r"fetch\(['\"]https?:")

    def test_the_tab_labels_fit_a_phone(self):
        labels = words.load().table("page.tabs").values()
        self.assertLessEqual(sum(len(x) for x in labels), 32)


if __name__ == "__main__":
    unittest.main()
