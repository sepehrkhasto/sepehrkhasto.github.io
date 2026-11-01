"""Checks run in CI before every deploy:  python -m unittest discover -s tests

They build the site, then check content parity, links, assets and page structure.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT))
import build  # noqa: E402


def shape(value):
    """Structure of a JSON value with the text stripped out."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(v) for v in value]
    return type(value).__name__


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.refs: list[tuple[str, str]] = []
        self.headings: list[int] = []
        self.imgs_without_alt = 0
        self.attrs: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.attrs.append((tag, a))
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key):
                self.refs.append((tag, a[key]))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag == "img" and "alt" not in a:
            self.imgs_without_alt += 1


def parse(path: Path) -> Collector:
    c = Collector()
    c.feed(path.read_text(encoding="utf-8"))
    return c


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build.build()
        cls.pages = {lang: DIST / folder / "index.html" for lang, folder in build.PAGES.items()}

    def test_languages_have_identical_structure(self):
        en, fa = build.load("en"), build.load("fa")
        self.assertEqual(shape(en), shape(fa))
        self.assertEqual([p["id"] for p in en["work"]["projects"]], [p["id"] for p in fa["work"]["projects"]])

    def test_screenshots_are_real_files(self):
        for lang in build.PAGES:
            for p in build.load(lang)["work"]["projects"]:
                for key in ("main", "inset"):
                    if "media" in p:
                        src = p["media"][key]["src"]
                        self.assertIn(src, build.IMAGES, src)
                        self.assertTrue(p["media"][key]["alt"].strip(), f"{lang}: {src} needs alt text")
                        for name, _ in build.IMAGES[src]["files"]:
                            self.assertTrue((DIST / "assets" / "img" / "work" / name).exists(), name)

    def test_public_repositories_use_https_github(self):
        for lang in build.PAGES:
            for p in build.load(lang)["work"]["projects"]:
                if p["repo"]:
                    self.assertRegex(p["repo"], r"^https://github\.com/sepehrkhasto/[\w.-]+$")

    def test_internal_links_and_assets_resolve(self):
        for lang, page in self.pages.items():
            doc = parse(page)
            base = f"http://site/{build.PAGES[lang]}index.html"
            for tag, ref in doc.refs:
                if ref.startswith(("mailto:", "data:")):
                    continue
                if ref.startswith("#"):
                    self.assertIn(ref[1:], doc.ids, f"{lang}: missing anchor {ref}")
                    continue
                url = urlparse(urljoin(base, ref))
                if url.netloc != "site":
                    self.assertEqual(url.scheme, "https", f"{lang}: insecure link {ref}")
                    continue
                target = DIST / url.path.lstrip("/")
                if url.path.endswith("/"):
                    target = target / "index.html"
                self.assertTrue(target.exists(), f"{lang}: {ref} -> {target}")

    def test_pages_are_well_formed(self):
        for lang, page in self.pages.items():
            html = page.read_text(encoding="utf-8")
            doc = parse(page)
            self.assertIn(f'<html lang="{lang}" dir="{build.load(lang)["dir"]}">', html)
            self.assertEqual(doc.headings.count(1), 1, f"{lang}: exactly one h1")
            for prev, cur in zip(doc.headings, doc.headings[1:]):
                self.assertLessEqual(cur - prev, 1, f"{lang}: heading level skipped (h{prev} -> h{cur})")
            self.assertEqual(doc.imgs_without_alt, 0)
            self.assertIn('rel="canonical"', html)
            self.assertIn('hreflang="x-default"', html)
            self.assertIn("Content-Security-Policy", html)
            json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))

    def test_downloads_exist(self):
        for lang in build.PAGES:
            for f in build.load(lang)["contact"]["resume_files"]:
                self.assertTrue((DIST / "resume" / f["file"]).stat().st_size > 10_000, f["file"])

    def test_buttons_have_a_purpose(self):
        for page in self.pages.values():
            for tag, attrs in parse(page).attrs:
                if tag == "button":
                    self.assertTrue(attrs.get("type") == "button" and ("id" in attrs or "class" in attrs))

    def test_seo_files(self):
        sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
        for lang in build.PAGES:
            self.assertIn(build.page_url(lang), sitemap)
        self.assertIn("Sitemap:", (DIST / "robots.txt").read_text(encoding="utf-8"))
        self.assertTrue((DIST / "404.html").exists())


if __name__ == "__main__":
    unittest.main()
