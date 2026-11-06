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

    def test_no_inline_styles_or_scripts(self):
        """The Content-Security-Policy forbids them, so a stray style attribute would silently do nothing."""
        for page in list(self.pages.values()) + [DIST / "404.html"]:
            html = page.read_text(encoding="utf-8")
            self.assertNotRegex(html, r'\sstyle="', f"{page}: inline style attribute")
            self.assertNotRegex(html, r"<style[\s>]", f"{page}: <style> element")

    def test_fonts_are_self_hosted_and_exist(self):
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        for name in re.findall(r"url\(\.\./fonts/([^)]+)\)", css):
            self.assertTrue((DIST / "assets" / "fonts" / name).exists(), name)
        self.assertNotIn("http", css.replace("http-equiv", ""))

    def test_seo_files(self):
        sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
        for lang in build.PAGES:
            self.assertIn(build.page_url(lang), sitemap)
        self.assertIn("Sitemap:", (DIST / "robots.txt").read_text(encoding="utf-8"))
        self.assertTrue((DIST / "404.html").exists())

    def test_share_cards_and_icons(self):
        for lang in build.PAGES:
            html = (DIST / ("index.html" if lang == "en" else f"{lang}/index.html")).read_text(encoding="utf-8")
            card = "og-fa.png" if lang == "fa" else "og.png"
            self.assertIn(f"/assets/img/{card}", html)
            self.assertRegex(html, r'og:image:alt" content="[^"]{20,}"')
            for icon in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
                self.assertIn(icon, html)
        for name in ("og.png", "og-fa.png", "favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
            self.assertTrue((DIST / "assets" / "img" / name).exists(), name)
        for name in ("og.png", "og-fa.png"):  # chat apps skip large cards
            self.assertLess((DIST / "assets" / "img" / name).stat().st_size, 300_000, name)
        self.assertIn("apple-touch-icon", (DIST / "404.html").read_text(encoding="utf-8"))

    def test_page_works_without_scripting(self):
        """Controls that need JavaScript stay hidden until theme.js marks the page as js."""
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        self.assertIn("html:not(.js) .vault", css)
        self.assertIn('classList.add("js")', (DIST / "assets" / "js" / "theme.js").read_text(encoding="utf-8"))

    def test_print_stylesheet(self):
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        self.assertIn("@media print", css)
        printed = css[css.index("@media print"):]
        for hidden in (".site-header", ".vault", ".theme-btn"):
            self.assertIn(hidden, printed)

    def test_icons_carry_names_and_moving_parts(self):
        """Each icon is addressable (.i-name), and the ones that move on hover keep their moving part in its own group."""
        for name in build.ICONS:
            self.assertIn(f'class="icon i-{name}"', build.icon(name))
        for name, part in (("download", "a"), ("external", "a"), ("copy", "b"), ("menu", "l2"), ("expand", "a2"), ("mail", "a")):
            self.assertIn(f'class="{part}"', build.ICONS[name], name)

    def test_touch_motion_only_with_motion_allowed(self):
        """Hover and press travel (translate, keyframes, view transitions) must sit inside prefers-reduced-motion:no-preference."""
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        outside, i = [], 0
        marker = "@media (prefers-reduced-motion:no-preference)"
        while True:
            j = css.find(marker, i)
            if j < 0:
                outside.append(css[i:])
                break
            outside.append(css[i:j])
            depth, k = 0, css.index("{", j)
            while True:
                depth += css[k] == "{"
                depth -= css[k] == "}"
                k += 1
                if depth == 0:
                    break
            i = k
        rest = "".join(outside)
        self.assertNotIn("translate:", rest.replace("transition:translate", ""), "translate outside no-preference")
        self.assertNotIn("@view-transition", rest)
        self.assertNotRegex(re.sub(r"animation:none!important", "", rest.split("@media print")[0]), r"animation:[a-z]")
        js = (DIST / "assets" / "js" / "site.js").read_text(encoding="utf-8")
        self.assertIn("prefers-reduced-motion: reduce", js)

    def test_scroll_choreography_is_progressive(self):
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        # Scroll-driven rules live only where timelines are supported and motion is allowed.
        for m in re.finditer(r"animation-timeline:", css):
            before = css[: m.start()]
            if before.endswith("@supports ("):
                continue
            self.assertGreater(before.rfind("@supports (animation-timeline"), before.rfind("@media print"), "timeline outside @supports")
            self.assertGreater(before.rfind("prefers-reduced-motion:no-preference"), before.rfind("@media print"))
        # View timelines need a scroll container that is not the hero or contact itself.
        self.assertNotRegex(css, r"\.hero\s*\{[^}]*overflow:hidden")
        self.assertIn("overflow:clip", css)
        for page in ("index.html", "fa/index.html"):
            html = (DIST / page).read_text(encoding="utf-8")
            self.assertGreaterEqual(html.count('class="rv"'), 6, page)
            for depth in ("d1", "d2", "d3"):
                self.assertRegex(html, rf'class="t(?:e|mb|pn) {depth}"', page)

    def test_text_size_follows_the_reader(self):
        css = (DIST / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        # Sizes are rem/em, so the browser's own text-size setting reaches every piece of text.
        self.assertEqual(re.findall(r"font-size:[^;}]*\d+(?:\.\d+)?px", css), [])
        # Breakpoints are in em, so a larger default text size switches to the narrow layouts sooner.
        self.assertEqual(re.findall(r"@media[^{]*(?:min|max)-(?:width|height):[\d.]+px", css), [])
        js = (DIST / "assets" / "js" / "site.js").read_text(encoding="utf-8")
        self.assertNotRegex(js, r"min-width:\s*\d+px")
        # Safeguards for large text exist and are scoped so the default layout is untouched.
        self.assertIn("@media (max-width:19.9em)", css)
        # The skip link is hidden by its own height, not by a fixed offset.
        self.assertRegex(css, r"\.skip\{[^}]*transform:translateY\(-1\d\d%\)")
        # An open menu can scroll inside a short window.
        self.assertRegex(css, r"\.site-nav\{max-height:calc\(100vh - var\(--header\)\);max-height:calc\(100dvh - var\(--header\)\);overflow-y:auto")

    def test_job_title_and_claims_agree_everywhere(self):
        """One title on every surface, and no claim the repositories do not support."""
        en = json.loads((ROOT / "content" / "en.json").read_text(encoding="utf-8"))
        fa = json.loads((ROOT / "content" / "fa.json").read_text(encoding="utf-8"))
        self.assertEqual(en["hero"]["role"], "Junior Backend Developer")
        self.assertIn("Junior Backend Developer", en["meta"]["title"])
        self.assertIn("Junior backend developer", en["footer"]["statement"])
        self.assertIn("جونیور", fa["hero"]["role"])
        self.assertIn("جونیور", fa["meta"]["title"])
        self.assertIn("جونیور", fa["footer"]["statement"])
        self.assertIn("Junior Backend Developer", (ROOT / "build.py").read_text(encoding="utf-8"))
        # The old title must not survive in any source that carries it.
        sources = [ROOT / "content" / "en.json", ROOT / "content" / "fa.json", ROOT / "build.py",
                   ROOT / "tools" / "make_brand.py", *(ROOT / "resume").glob("*.html")]
        for f in sources:
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("Backend Engineer", text, f.name)
            self.assertNotIn("مهندس بک‌اند", text, f.name)
            self.assertNotIn("مهندس نرم‌افزار بک‌اند", text, f.name)
        # Testing is a working skill now, and DRF is the only item still being learned.
        for data, learn_name in ((en, "Currently learning"), (fa, "در حال یادگیری")):
            tier = next(t for t in data["skills"]["tiers"] if t["name"] == learn_name)
            items = [i for g in tier["groups"] for i in g["items"]]
            self.assertEqual(items, ["Django REST Framework"])
            self.assertNotIn("B2", data["skills"]["spoken"])
        # Claims the repositories contradict stay out of the hero text.
        for data in (en, fa):
            blob = json.dumps(data["hero"], ensure_ascii=False)
            self.assertNotIn("FastAPI", blob)
            self.assertNotIn("PostgreSQL", blob)
        # The testing principle names where tests do not exist yet.
        self.assertIn("do not have test suites yet", en["approach"]["principles"][3]["evidence"])
        for f in (ROOT / "resume").glob("*.html"):
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("working toward B2", text, f.name)
            self.assertNotIn("در مسیر", text.split("انگلیسی", 1)[-1][:60] if "انگلیسی" in text else "", f.name)


    def test_resume_fonts_travel_with_the_resume(self):
        """The resume PDFs must be built with their own fonts, not a fallback."""
        css = (ROOT / "resume" / "resume.css").read_text(encoding="utf-8")
        urls = re.findall(r"url\(([^)]+)\)", css)
        self.assertTrue(urls)
        for u in urls:
            self.assertFalse(u.startswith(".."), u)
            self.assertTrue((ROOT / "resume" / u).exists(), u)

    def test_case_study_claims_are_honest_and_agree(self):
        en = json.loads((ROOT / "content" / "en.json").read_text(encoding="utf-8"))
        fa = json.loads((ROOT / "content" / "fa.json").read_text(encoding="utf-8"))

        def proj(data, pid):
            return next(p for p in data["work"]["projects"] if p["id"] == pid)

        # Refinery: the page says how the backend was built and that its tests are not written yet.
        self.assertIn("AI coding tools", proj(en, "refinery")["design"])
        self.assertIn("have not been written yet", proj(en, "refinery")["verification"])
        self.assertIn("هوش مصنوعی", proj(fa, "refinery")["design"])
        self.assertIn("هنوز نوشته نشده", proj(fa, "refinery")["verification"])
        # Andarun says what it has not been through, and is described as designed, not proven.
        for data in (en, fa):
            a = proj(data, "andarun")
            self.assertTrue(a["limits"])
            self.assertNotIn("keeps working", a["tagline"] + a["problem"])
        # Aegis Web: the limit that the server delivers the encryption code is stated, and no unsupported pointer remains.
        self.assertIn("delivers the JavaScript", proj(en, "aegis-web")["limits"])
        self.assertNotIn("SECURITY.md", proj(en, "aegis-web")["limits"] + proj(fa, "aegis-web")["limits"])
        # The save path has the same shape in both languages and the numbers match the design text.
        fe, ff = proj(en, "aegis-web")["flow"], proj(fa, "aegis-web")["flow"]
        self.assertEqual((len(fe["steps"]), len(fe["outcomes"])), (4, 2))
        self.assertEqual((len(ff["steps"]), len(ff["outcomes"])), (4, 2))
        self.assertIn("600,000", fe["steps"][0]["d"])
        self.assertIn("۶۰۰٬۰۰۰", ff["steps"][0]["d"])
        for flow in (fe, ff):
            self.assertIn("409", flow["outcomes"][1]["d"])
        # The pages render it once, as an ordered list with the server step numbered after the browser steps.
        for lang, path in self.pages.items():
            html = path.read_text(encoding="utf-8")
            self.assertEqual(html.count('class="flow"'), 1, lang)
            self.assertEqual(html.count('class="flow-step '), 4, lang)
            self.assertIn('<ol start="4">', html, lang)
        # Resumes: no claim that the system "keeps working during shutdowns", and the AI-built backend is stated.
        for f in (ROOT / "resume").glob("*.html"):
            text = f.read_text(encoding="utf-8")
            self.assertNotIn("keeps working during shutdowns", text, f.name)
            self.assertNotIn("Implemented JWT", text, f.name)
        for name in ("en.html", "ats-en.html"):
            self.assertIn("built with AI coding tools", (ROOT / "resume" / name).read_text(encoding="utf-8"), name)
        self.assertIn("ابزارهای هوش مصنوعی", (ROOT / "resume" / "fa.html").read_text(encoding="utf-8"))

    # ---- Claim ledger: every number on the page has a recorded source (tests/claims.json) ----
    @staticmethod
    def _strings(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("url", "href", "file", "id", "src", "alt", "lang", "dir", "locale"):
                    continue
                yield from SiteTests._strings(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from SiteTests._strings(v)
        elif isinstance(obj, str):
            yield obj

    @staticmethod
    def _numbers(text):
        text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٫٬", "0123456789.,"))
        return re.findall(r"\d+(?:[.,]\d+)*", text)

    def test_every_number_has_a_recorded_source(self):
        ledger = json.loads((ROOT / "tests" / "claims.json").read_text(encoding="utf-8"))["numbers"]
        known = {t for row in ledger for t in row["tokens"]}
        for row in ledger:
            self.assertTrue(row["source"] and row["status"] in ("verified", "stated"), row)
        en = json.loads((ROOT / "content" / "en.json").read_text(encoding="utf-8"))
        # Skip fields that are not claims: the name of the site and the e-mail address.
        en["contact"].pop("email", None)
        used = {n for s in self._strings(en) for n in self._numbers(s)}
        self.assertEqual(used - known, set(), "a number without a recorded source")
        self.assertEqual(known - used, set(), "a ledger entry for a number that is no longer on the page")
        for name in ("en.html", "ats-en.html"):
            text = re.sub(r"<style.*?</style>|<[^>]+>", " ", (ROOT / "resume" / name).read_text(encoding="utf-8"), flags=re.S)
            self.assertEqual(set(self._numbers(text)) - known, set(), name)

    def test_numbers_agree_between_english_and_persian(self):
        en = json.loads((ROOT / "content" / "en.json").read_text(encoding="utf-8"))
        fa = json.loads((ROOT / "content" / "fa.json").read_text(encoding="utf-8"))
        # Years differ by calendar (2024 and 1403), so those paths are compared by the ledger test instead.
        skip = ("footer", "education", "year")
        # The Persian page quotes a Persian sentence typed into the quick-add box, which has a number in it.
        only_in_persian = {"/work/projects[1]/highlights[2]"}

        def pairs(a, b, path=""):
            if isinstance(a, dict):
                for k in a:
                    yield from pairs(a[k], b[k], f"{path}/{k}")
            elif isinstance(a, list):
                for i, (x, y) in enumerate(zip(a, b)):
                    yield from pairs(x, y, f"{path}[{i}]")
            elif isinstance(a, str):
                yield path, a, b

        checked = 0
        for path, x, y in pairs(en, fa):
            if path in only_in_persian or any(s in path for s in skip) or path.endswith(("/url", "/href", "/email", "/meta", "/file")):
                continue
            checked += 1
            self.assertEqual(sorted(self._numbers(x)), sorted(self._numbers(y)), path)
        self.assertGreater(checked, 100)

    def test_statements_without_digits_are_recorded(self):
        statements = json.loads((ROOT / "tests" / "claims.json").read_text(encoding="utf-8"))["statements"]
        en = json.loads((ROOT / "content" / "en.json").read_text(encoding="utf-8"))
        blob = json.dumps(en, ensure_ascii=False)
        self.assertIn("team of four", blob.lower())
        self.assertIn("top three", blob.lower())
        self.assertEqual({s["status"] for s in statements}, {"stated", "unverified"})

    def test_persian_terms_stay_decided(self):
        """Wording that was chosen on purpose, and wording that was rejected, in the page and the résumé."""
        text = (ROOT / "content" / "fa.json").read_text(encoding="utf-8") + (ROOT / "resume" / "fa.html").read_text(encoding="utf-8")
        for rejected in ("دانش صفر", "شکست امن", "امنیت به‌عنوان پیش‌فرض", "خواستو", "صحت داده", "مهندس بک‌اند", "کنترل نسخه با", "در برنامه است"):
            self.assertNotIn(rejected, text, rejected)
        for chosen in ("یکپارچگی داده‌ها", "توقف امن (Fail closed)", "مدیریت صریح هم‌زمانی", "آشنایی کاربردی", "سپهر خستو"):
            self.assertIn(chosen, text, chosen)

    def test_header_mark_and_favicon_are_one_drawing(self):
        fav = (ROOT / "static" / "assets" / "img" / "favicon.svg").read_text(encoding="utf-8")
        for part in (build.MARK_STAR, build.MARK_BG, build.MARK_GOLD, build.MARK_TQ, 'rx="6"', 'r="2.4"'):
            self.assertIn(part, fav, part)
            self.assertIn(part, build.MARK, part)
        # Only the line weight may differ, so the favicon stays readable at 16 px.
        strip = lambda svg: re.sub(r'stroke-width="[^"]+"|\sclass="mark"|\saria-hidden="true"|\sxmlns="[^"]+"', "", svg).strip()
        self.assertEqual(strip(fav), strip(build.MARK))
        # The page and the generator agree, and the PNGs are real (corner is the background, centre the dot).
        self.assertEqual(fav.strip(), build.mark_svg(stroke=2.0, radius=6))
        from struct import unpack
        for name, size in (("favicon-32.png", 32), ("apple-touch-icon.png", 180)):
            data = (ROOT / "static" / "assets" / "img" / name).read_bytes()
            self.assertEqual(unpack(">II", data[16:24]), (size, size), name)

    def test_day_theme_accent_text_is_readable(self):
        """The day turquoise is used for small text; it must reach 4.5:1 on the darkest day background."""
        css = (ROOT / "static" / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        day = css[css.index('html[data-theme="day"]{--bg:'):]
        tq = re.search(r"--tq:(#[0-9A-Fa-f]{6})", day).group(1)
        bg2 = re.search(r"--bg2:(#[0-9A-Fa-f]{6})", day).group(1)

        def lum(h):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
            f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        hi, lo = sorted((lum(tq), lum(bg2)), reverse=True)
        self.assertGreaterEqual((hi + 0.05) / (lo + 0.05), 4.5)

    def test_persian_text_scale_is_one_step_larger(self):
        css = (ROOT / "static" / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        self.assertIn('html[lang="fa"]{--s1:0.875rem;--s2:0.96875rem;--s3:1rem}', css)
        # Every small-text size goes through the scale, so English keeps its sizes and Persian gains a step.
        self.assertNotRegex(re.sub(r"[^{}]*tree-svg[^{}]*\{[^}]*\}", "", css), r"font-size:0\.(8125|90625|9375)rem")


    def test_page_weight_stays_inside_the_budget(self):
        """Limits set from the measured sizes (EN HTML 56 KB, FA 74 KB, CSS 61 KB, JS 15 KB, whole site 0.94 MB)
        with some room. A change that crosses one needs a decision, not an accident."""
        kb = lambda path: path.stat().st_size / 1024
        self.assertLess(kb(DIST / "index.html"), 80)
        self.assertLess(kb(DIST / "fa" / "index.html"), 100)
        self.assertLess(kb(DIST / "assets" / "css" / "site.css"), 80)
        self.assertLess(kb(DIST / "assets" / "js" / "site.js"), 25)
        total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1024
        self.assertLess(total, 1250)

    def test_loading_stays_light(self):
        for page in (DIST / "index.html", DIST / "fa" / "index.html"):
            html = page.read_text(encoding="utf-8")
            # Only our own files: no third-party request can block the first paint.
            loaded = re.findall(r'<script[^>]+src="(https?://[^"]+)"', html)
            loaded += re.findall(r'<link[^>]+rel="(?:stylesheet|preload|preconnect|modulepreload)"[^>]+href="(https?://[^"]+)"', html)
            self.assertEqual(loaded, [], f"{page.name}: external resource")
            self.assertEqual(len(re.findall(r'<link rel="preload"[^>]+as="font"', html)) >= 2, True)
            # Pictures: a size reserved (no layout shift) and lazy loading; the empty dialog image is filled later.
            for img in re.findall(r"<img[^>]*>", html):
                if 'alt=""' in img and "src=" not in img:
                    continue
                self.assertIn("width=", img)
                self.assertIn("height=", img)
                self.assertIn('loading="lazy"', img)

    def test_deep_links_are_not_left_to_content_visibility(self):
        """Tried in phase 56: `content-visibility:auto` on the sections cut load work (TBT about 80 ms lower on a
        throttled phone) but sections above a link stayed unmeasured, so /#work-refinery and the nav links landed
        hundreds of pixels off. Links matter more than that gain."""
        css = (ROOT / "static" / "assets" / "css" / "site.css").read_text(encoding="utf-8")
        self.assertNotIn("content-visibility", css)


    def test_brand_images_use_fonts_that_exist(self):
        """Phase 54.2 regenerated the share card after its fonts had moved, and Chromium quietly drew it in a
        fallback face. The script now fails on a missing font; this test also catches it without a browser."""
        import struct
        src = (ROOT / "tools" / "make_brand.py").read_text(encoding="utf-8")
        self.assertIn("from build import", src)  # the mark comes from the same place as the header and favicon
        fonts = re.search(r'FONT_DIR = "([^"]+)"', src).group(1)
        names = re.findall(r'\("Brand\w+", "([\w-]+)"', src)
        self.assertGreaterEqual(len(names), 6)
        for name in names:
            self.assertTrue((ROOT / fonts / f"{name}.woff2").is_file(), name)
        # A custom family must not be named like a generic one (an unquoted `Serif` means the generic serif face).
        for family in set(re.findall(r'\("(Brand\w+)"', src)):
            self.assertNotIn(family.lower(), {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"})
        for card in ("og.png", "og-fa.png"):
            head = (ROOT / "static" / "assets" / "img" / card).read_bytes()[:24]
            self.assertEqual(head[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", head[16:24]), (1200, 630), card)


if __name__ == "__main__":
    unittest.main()
