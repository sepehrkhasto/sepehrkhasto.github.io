"""Browser checks, run by hand:  python tests/browser_check.py   (needs: pip install playwright; playwright install chromium)

Serves dist/ and checks, in Chromium only: no console errors or failed requests, no sideways scrolling at
320 to 1920 px wide in both themes and both languages, every keyboard stop has a visible focus ring and is
not hidden under the sticky header, the lightbox opens and closes from the keyboard, the day theme persists,
the page works with scripting off, and nothing keeps moving under reduced motion.
"""
from __future__ import annotations
import functools, http.server, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright

DIST = Path(__file__).resolve().parent.parent / "dist"
SIZES = [(320, 640), (375, 812), (768, 1024), (1280, 800), (1920, 1080)]
problems: list[str] = []

def check(ok, msg):
    if not ok: problems.append(msg)

class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(DIST)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"

OVERFLOW = "document.documentElement.scrollWidth > document.documentElement.clientWidth"
FOCUS = """() => { const e = document.activeElement; if (!e || e === document.body) return null;
  const r = e.getBoundingClientRect(), s = getComputedStyle(e), hdr = document.querySelector('.site-header');
  const chrome = hdr.contains(e) || e.classList.contains('skip');
  return { name: (e.getAttribute('aria-label') || e.innerText || e.tagName).trim().slice(0, 30),
    ring: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none',
    hidden: !chrome && r.top < hdr.getBoundingClientRect().bottom - 1, off: r.bottom <= 0 || r.top >= innerHeight } }"""

def main() -> int:
    srv, base = serve()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path in ("/", "/fa/", "/404.html"):
            for theme in ("night", "day"):
                for w, h in SIZES:
                    ctx = b.new_context(viewport={"width": w, "height": h})
                    ctx.add_init_script(f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
                    pg = ctx.new_page(); seen = []
                    pg.on("console", lambda m: seen.append(m.text) if m.type in ("error", "warning") else None)
                    pg.on("pageerror", lambda e: seen.append(str(e)))
                    pg.on("response", lambda r: seen.append(f"{r.status} {r.url}") if r.status >= 400 and not (path == "/404.html" and r.url.endswith("404.html")) else None)
                    pg.goto(base + path); pg.wait_for_timeout(400)
                    check(not pg.evaluate(OVERFLOW), f"{path} {theme} {w}px: sideways scroll")
                    check(not seen, f"{path} {theme} {w}px: {seen[:2]}")
                    ctx.close()
        for path in ("/", "/fa/"):
            ctx = b.new_context(viewport={"width": 1280, "height": 800}); pg = ctx.new_page(); pg.goto(base + path); pg.wait_for_timeout(400)
            for _ in range(60):
                pg.keyboard.press("Tab"); pg.wait_for_timeout(650)  # smooth scrolling needs to settle
                d = pg.evaluate(FOCUS)
                if d is None: break
                check(d["ring"] and not d["hidden"] and not d["off"], f"{path} focus: {d}")
            ctx.close()
        ctx = b.new_context(viewport={"width": 1280, "height": 800}); pg = ctx.new_page(); pg.goto(base + "/"); pg.wait_for_timeout(400)
        link = pg.locator("a[data-lightbox]").first; link.scroll_into_view_if_needed(); link.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
        check(pg.evaluate("document.querySelector('#lightbox').open"), "lightbox did not open")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        check(pg.evaluate("document.activeElement.matches('a[data-lightbox]')"), "focus did not return after closing the lightbox")
        pg.locator(".theme-btn").click(); pg.reload(); pg.wait_for_timeout(300)
        check(pg.evaluate("document.documentElement.dataset.theme") == "day", "day theme not kept after reload")
        ctx.close()
        for path in ("/", "/fa/"):
            ctx = b.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 800}); pg = ctx.new_page(); pg.goto(base + path); pg.wait_for_timeout(300)
            for sel in (".vault", ".theme-btn", "[data-copy]"):
                check(not pg.locator(sel).first.is_visible(), f"{path} no-JS: {sel} is visible but cannot work")
            check(pg.locator("h1").is_visible(), f"{path} no-JS: heading hidden")
            ctx.close()
        ctx = b.new_context(reduced_motion="reduce", viewport={"width": 1280, "height": 800}); pg = ctx.new_page(); pg.goto(base + "/"); pg.wait_for_timeout(1500)
        running = pg.evaluate("document.getAnimations().filter(a => a.playState === 'running').length")
        check(running == 0, f"reduced motion: {running} animations still running")
        b.close()
    srv.shutdown()
    print("\n".join(problems) or "all browser checks passed (Chromium only)")
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
