"""Render the brand images with headless Chromium, in the site's Nocturne identity.

    static/assets/img/og.png       1200x630   share card for the English page
    static/assets/img/og-fa.png    1200x630   share card for the Persian page
    brand/linkedin-banner.png      1584x396   LinkedIn background photo
    brand/github-banner.png        1600x400   header image for the GitHub profile README
    brand/social/*.png             1280x640   social preview image for each repository

The mark and its colours come from build.py, so the images always match the header and the favicon.
Fonts are the full files in assets-src/fonts (the site's copies are cut to the characters it uses).
The script stops with an error if a font does not load, instead of quietly using a fallback face.

Needs Playwright (pip install playwright && python -m playwright install chromium) and Pillow, which
reduces each image to a 256-colour palette with dithering (about a quarter of the size, no visible banding).
Run from the repository root: python tools/make_brand.py
"""
import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import MARK_BG, MARK_GOLD, MARK_STAR, MARK_TQ, mark_svg  # noqa: E402

FONT_DIR = "assets-src/fonts"
FONTS = [  # family, file, weight, style
    ("BrandSerif", "instrument-serif-latin-400-normal", 400, "normal"),
    ("BrandSerif", "instrument-serif-latin-400-italic", 400, "italic"),
    ("BrandSans", "geist-sans-latin-400-normal", 400, "normal"),
    ("BrandSans", "geist-sans-latin-500-normal", 500, "normal"),
    ("BrandSans", "geist-sans-latin-600-normal", 600, "normal"),
    ("BrandMono", "geist-mono-latin-400-normal", 400, "normal"),
    ("BrandFa", "vazirmatn-arabic-400-normal", 400, "normal"),
    ("BrandFa", "vazirmatn-arabic-500-normal", 500, "normal"),
    ("BrandFa", "vazirmatn-arabic-600-normal", 600, "normal"),
]

FACES = "".join(
    f"@font-face{{font-family:{fam};src:url(/{FONT_DIR}/{name}.woff2) format('woff2');font-weight:{w};font-style:{st}}}"
    for fam, name, w, st in FONTS
)

# The same tokens as the night theme in static/assets/css/site.css.
BASE_CSS = FACES + f"""
*{{box-sizing:border-box;margin:0}}
body{{background:#070B1F;color:#F4ECDD;font-family:BrandSans,sans-serif;position:relative;overflow:hidden;
  -webkit-font-smoothing:antialiased}}
.wash{{position:absolute;inset:0;background:
  radial-gradient(ellipse 70% 90% at 92% 0%,rgba(38,58,140,.55),transparent 62%),
  radial-gradient(ellipse 50% 70% at 0% 100%,rgba(61,194,180,.07),transparent 70%)}}
.frame{{position:absolute;border:1px solid rgba(217,178,106,.26)}}
.star{{position:absolute}}
.star path{{fill:none;stroke:rgba(217,178,106,.24);stroke-width:.09;stroke-linejoin:round}}
.mark{{display:block}}
.role{{color:{MARK_GOLD};font-weight:500;letter-spacing:.005em}}
.name{{font-family:BrandSerif,serif;font-weight:400;color:#F4ECDD;line-height:.95;letter-spacing:-.01em}}
.text{{color:#CFC6B4;line-height:1.42}}
.mono{{font-family:BrandMono,monospace;color:#A9B1CB}}
.sep{{color:#59627F;margin:0 .5em}}
.tq{{color:{MARK_TQ}}}
[lang=fa]{{font-family:BrandFa,sans-serif;direction:rtl;letter-spacing:0}}
"""


def star(size: int, right: int, top: int, side: str = "right") -> str:
    """The mark's eight-point star as a large outline, the same path scaled up."""
    return (f'<svg class="star" viewBox="0 0 32 32" style="width:{size}px;height:{size}px;{side}:{right}px;top:{top}px">'
            f'<path d="{MARK_STAR}"/></svg>')


def mark(px: int) -> str:
    return mark_svg(stroke=1.6, radius=6).replace("<svg ", f'<svg class="mark" width="{px}" height="{px}" ', 1)


def share_card(lang: str) -> tuple[int, int, str]:
    if lang == "fa":
        return (1200, 630, f"""
<div class="wash" style="transform:scaleX(-1)"></div>{star(560, -40, 60, "left")}<div class="frame" style="inset:28px"></div>
<div lang="fa" style="position:absolute;right:92px;left:92px;top:88px">
  <div style="display:flex;align-items:center;gap:18px">{mark(52)}<span class="role" style="font-family:BrandFa;font-size:30px">توسعه‌دهندهٔ جونیور بک‌اند</span></div>
  <div style="margin-top:44px;font-weight:600;font-size:118px;line-height:1.05;color:#F4ECDD">سپهر خستو</div>
  <div class="text" style="margin-top:30px;font-size:31px;line-height:1.75;max-width:760px">توسعهٔ بک‌اند با <span dir="ltr">Python</span> و <span dir="ltr">Django</span>، با تمرکز بر امنیت نرم‌افزار و یکپارچگی داده‌ها.</div>
</div>
<div class="mono" style="position:absolute;right:92px;bottom:76px;font-size:24px" dir="ltr">sepehrkhasto.github.io/fa/</div>""")
    return (1200, 630, f"""
<div class="wash"></div>{star(560, -40, 60)}<div class="frame" style="inset:28px"></div>
<div style="position:absolute;left:92px;top:88px;right:92px">
  <div style="display:flex;align-items:center;gap:18px">{mark(52)}<span class="role" style="font-size:30px">Junior Backend Developer</span></div>
  <div class="name" style="margin-top:52px;font-size:132px">Sepehr Khastoo</div>
  <div class="text" style="margin-top:36px;font-size:31px;max-width:760px">Python and Django, with a focus on application security and data integrity.</div>
</div>
<div class="mono" style="position:absolute;left:92px;bottom:76px;font-size:24px">sepehrkhasto.github.io</div>""")


def social_preview(repo: str, title: str, desc: str, footer: list[str], extra: str = "") -> tuple[int, int, str]:
    """A 1280x640 repository social preview in the same style as the share cards."""
    sep = '<span class="sep">·</span>'
    return (1280, 640, f"""
<div class="wash"></div>{star(600, -70, 40)}<div class="frame" style="inset:28px"></div>
<div style="position:absolute;left:92px;top:84px;right:92px">
  <div style="display:flex;align-items:center;gap:16px">{mark(44)}<span class="mono" style="font-size:25px">sepehrkhasto / {repo}</span></div>
  <div class="name" style="margin-top:46px;font-size:112px">{title}{extra}</div>
  <div class="text" style="margin-top:32px;font-size:33px;max-width:960px">{desc}</div>
</div>
<div class="mono" style="position:absolute;left:92px;bottom:78px;font-size:24px">{sep.join(footer)}</div>""")


PAGES = {
    "static/assets/img/og.png": share_card("en"),
    "static/assets/img/og-fa.png": share_card("fa"),

    # LinkedIn covers the left part of the banner with the profile photo (on phones, the middle too),
    # so the text sits on the right.
    "brand/linkedin-banner.png": (1584, 396, f"""
<div class="wash"></div>{star(520, 1040, -60)}
<div style="position:absolute;left:640px;right:88px;top:78px">
  <div style="display:flex;align-items:center;gap:14px">{mark(38)}<span class="role" style="font-size:24px">Junior Backend Developer<span class="sep">·</span>Python and Django</span></div>
  <div class="name" style="margin-top:24px;font-size:68px;line-height:1.02">Application security<br>and data integrity</div>
  <div class="mono" style="margin-top:28px;font-size:20px">sepehrkhasto.github.io<span class="sep">·</span>github.com/sepehrkhasto</div>
</div>"""),

    "brand/github-banner.png": (1600, 400, f"""
<div class="wash"></div>{star(560, -20, -80)}<div class="frame" style="inset:22px"></div>
<div style="position:absolute;left:88px;top:74px;right:88px">
  <div style="display:flex;align-items:center;gap:16px">{mark(42)}<span class="role" style="font-size:27px">Junior Backend Developer</span></div>
  <div class="name" style="margin-top:22px;font-size:118px">Sepehr Khastoo</div>
  <div class="text" style="margin-top:20px;font-size:29px">Python and Django<span class="sep">·</span>Application security<span class="sep">·</span>Data integrity</div>
</div>"""),

    "brand/social/aegis-zk-planner.png": social_preview(
        "aegis-zk-planner", "Aegis Planner",
        "A zero-knowledge planner. Data is encrypted in the browser; the server stores only ciphertext.",
        ["Django", "Web Crypto API", "AES-256-GCM", "v7.1.0"]),
    "brand/social/aegis-planner.png": social_preview(
        "aegis-planner", "Aegis Planner",
        "An offline, encrypted planner for Windows, in Persian with a Jalali calendar.",
        ["Python", "PyQt6", "AES-256-GCM", "v2.11.10"]),
    "brand/social/refinery-risk-monitor.png": social_preview(
        "refinery-risk-monitor", "Refinery Risk Monitor",
        "Live risk scoring, P10/P50/P90 forecasts and anomaly detection for refinery process units.",
        ["FastAPI", "SQLAlchemy", "WebSocket", "scikit-learn"]),
    "brand/social/andarun.png": social_preview(
        "andarun", "Andarun",
        "A text-only, invite-only social network, designed to run on a domestic network when international access is cut.",
        ["Python 3.12", "Django 6.1", "In development"],
        extra=f'<span lang="fa" style="font-weight:600;font-size:66px;color:{MARK_TQ};margin-left:30px;vertical-align:14px">اندرون</span>'),
    "brand/social/sepehrkhasto.github.io.png": social_preview(
        "sepehrkhasto.github.io", "Sepehr Khastoo",
        "Portfolio. Junior backend developer working in Python and Django on application security and data integrity.",
        ["English", '<span lang="fa">فارسی</span>']),
}


def main() -> None:
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tmp = ROOT / "_brand.html"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for out, (w, h, body) in PAGES.items():
                tmp.write_text(
                    f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><style>{BASE_CSS}"
                    f"body{{width:{w}px;height:{h}px}}</style></head><body>{body}</body></html>",
                    encoding="utf-8",
                )
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/_brand.html", wait_until="networkidle")
                # Load every face and fail if one is missing: a fallback font must never reach a published image.
                failed = page.evaluate(
                    """async () => {
                        const bad = [];
                        await Promise.all([...document.fonts].map(f => f.load().catch(() => bad.push(f.family + ' ' + f.weight + ' ' + f.style))));
                        await document.fonts.ready;
                        return bad;
                    }"""
                )
                if failed:
                    raise SystemExit(f"{out}: fonts did not load: {', '.join(failed)}")
                (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(ROOT / out))
                page.close()
                # Median cut keeps the wash smooth; the faster methods leave visible rings.
                img = Image.open(ROOT / out).convert("RGB")
                img.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(
                    ROOT / out, optimize=True)
                print(f"wrote {out}")
            browser.close()
    finally:
        server.shutdown()
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
