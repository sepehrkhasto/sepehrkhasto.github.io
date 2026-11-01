"""Render the brand images with headless Chromium.

    static/assets/img/og.png       1200x630   social preview for the site
    brand/linkedin-banner.png      1584x396   LinkedIn background photo
    brand/github-banner.png        1600x400   header image for the GitHub profile README
    brand/social/*.png             1280x640   social preview image for each repository

Needs Playwright (pip install playwright && python -m playwright install chromium).
Run from the repository root: python tools/make_brand.py
"""
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

BASE_CSS = """
@font-face{font-family:P;src:url(/static/assets/fonts/ibm-plex-sans-latin-400-normal.woff2)}
@font-face{font-family:P;src:url(/static/assets/fonts/ibm-plex-sans-latin-600-normal.woff2);font-weight:600}
@font-face{font-family:PM;src:url(/static/assets/fonts/ibm-plex-mono-latin-400-normal.woff2)}
@font-face{font-family:PA;src:url(/static/assets/fonts/ibm-plex-sans-arabic-arabic-600-normal.woff2);font-weight:600}
*{box-sizing:border-box}
body{margin:0;background:#0D1833;font-family:P;color:#EEF2FA;position:relative;overflow:hidden}
.art{position:absolute;inset:0;background:url(/static/assets/img/khatam.svg) 0 0/120px;opacity:.17}
.glow{position:absolute;border-radius:50%;background:radial-gradient(circle,rgba(52,179,176,.2),transparent 62%)}
.role{color:#34B3B0;font-weight:600}
.url{color:#A9B6CF}
.sep{color:#5B6E96;margin:0 .45em}
"""


def social_preview(repo: str, title: str, desc: str, footer: list[str], extra: str = "") -> tuple[int, int, str]:
    """A 1280x640 repository social preview in the same style as the banners."""
    sep = '<span class="sep">·</span>'
    return (1280, 640, f"""
<div class="art" style="-webkit-mask-image:linear-gradient(270deg,#000 0%,#000 22%,transparent 60%)"></div>
<div class="glow" style="width:900px;height:900px;right:-330px;top:-430px"></div>
<div style="position:absolute;left:88px;top:92px;right:88px">
  <div class="url" style="font-family:PM;font-size:25px">sepehrkhasto / {repo}</div>
  <div style="margin-top:30px;font-size:88px;line-height:1.02;letter-spacing:-3px;font-weight:600;color:#fff">{title}{extra}</div>
  <div style="margin-top:30px;font-size:34px;line-height:1.32;color:#DCE4F2;max-width:960px">{desc}</div>
</div>
<div class="url" style="position:absolute;left:88px;bottom:76px;font-size:25px">{sep.join(footer)}</div>""")


PAGES = {
    "static/assets/img/og.png": (1200, 630, """
<div class="art" style="-webkit-mask-image:radial-gradient(ellipse 60% 90% at 85% 40%,#000 15%,transparent 70%)"></div>
<div style="position:absolute;left:88px;top:92px;right:88px">
  <div class="role" style="font-size:30px">Backend Engineer</div>
  <div style="margin-top:18px;font-size:118px;line-height:.95;letter-spacing:-5px;font-weight:600;color:#fff">Sepehr Khastoo</div>
  <div style="margin-top:34px;font-size:32px;line-height:1.3;color:#DCE4F2">Python and Django<span class="sep">·</span>Application security<span class="sep">·</span>Data integrity</div>
</div>
<div class="url" style="position:absolute;left:88px;bottom:64px;font-size:24px">sepehrkhasto.github.io</div>"""),

    # The profile photo covers the lower left on LinkedIn, so the text sits on the right
    # and the pattern stays on the left, behind the photo.
    "brand/linkedin-banner.png": (1584, 396, """
<div class="art" style="-webkit-mask-image:linear-gradient(90deg,#000 0%,#000 30%,transparent 62%)"></div>
<div class="glow" style="width:900px;height:900px;left:-300px;top:-420px"></div>
<div style="position:absolute;right:96px;top:76px;width:760px;text-align:left">
  <div class="role" style="font-size:24px">Backend Engineer<span class="sep">·</span>Python and Django</div>
  <div style="margin-top:14px;font-size:48px;line-height:1.14;letter-spacing:-1px;font-weight:600;color:#fff">Application security<br>and data integrity</div>
  <div class="url" style="margin-top:26px;font-size:22px">sepehrkhasto.github.io<span style="display:inline-block;width:1px;height:18px;background:#3A4C78;margin:0 18px;vertical-align:-3px"></span>github.com/sepehrkhasto</div>
</div>"""),

    "brand/github-banner.png": (1600, 400, """
<div class="art" style="-webkit-mask-image:linear-gradient(270deg,#000 0%,#000 25%,transparent 60%)"></div>
<div class="glow" style="width:900px;height:900px;right:-300px;top:-420px"></div>
<div style="position:absolute;left:84px;top:78px;width:980px">
  <div class="role" style="font-size:26px">Backend Engineer</div>
  <div style="margin-top:10px;font-size:92px;line-height:1;letter-spacing:-3.5px;font-weight:600;color:#fff">Sepehr Khastoo</div>
  <div style="margin-top:24px;font-size:30px;line-height:1.3;color:#DCE4F2">Python and Django<span class="sep">·</span>Application security<span class="sep">·</span>Data integrity</div>
</div>"""),
}

PAGES.update({
    "brand/social/aegis-zk-planner.png": social_preview(
        "aegis-zk-planner", "Aegis Planner",
        "Zero-knowledge planner. Data is encrypted in the browser; the server stores only ciphertext.",
        ["Django", "Web Crypto API", "AES-256-GCM", "v7.1.0"]),
    "brand/social/aegis-planner.png": social_preview(
        "aegis-planner", "Aegis Planner",
        "Offline, encrypted planner for Windows, in Persian with a Jalali calendar.",
        ["Python", "PyQt6", "AES-256-GCM", "v2.11.10"]),
    "brand/social/refinery-risk-monitor.png": social_preview(
        "refinery-risk-monitor", "Refinery Risk Monitor",
        "Live risk scoring, P10/P50/P90 forecasts and anomaly detection for refinery process units.",
        ["FastAPI", "SQLAlchemy", "WebSocket", "scikit-learn"]),
    "brand/social/andarun.png": social_preview(
        "andarun", "Andarun",
        "Invite-only, text-only social network, built to keep working during internet shutdowns.",
        ["Python 3.12", "Django 6.1", "In development"],
        extra='<span lang="fa" dir="rtl" style="font-family:PA;font-weight:600;letter-spacing:0;font-size:60px;color:#34B3B0;margin-left:28px;vertical-align:8px">اندرون</span>'),
    "brand/social/sepehrkhasto.github.io.png": social_preview(
        "sepehrkhasto.github.io", "Sepehr Khastoo",
        "Portfolio. Backend engineering in Python and Django, application security and data integrity.",
        ["English", '<span lang="fa" style="font-family:PA">فارسی</span>']),
})


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
                tmp.write_text(f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{BASE_CSS}body{{width:{w}px;height:{h}px}}</style></head><body>{body}</body></html>", encoding="utf-8")
                page = browser.new_page(viewport={"width": w, "height": h})
                page.goto(f"http://127.0.0.1:{server.server_address[1]}/_brand.html", wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(ROOT / out))
                page.close()
                print(f"wrote {out}")
            browser.close()
    finally:
        server.shutdown()
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
