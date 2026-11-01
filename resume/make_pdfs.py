"""Render the resume HTML sources to PDF with headless Chromium.

Usage (from the repository root):
    pip install playwright && python -m playwright install chromium
    python resume/make_pdfs.py

The two designed PDFs go to static/resume/, which the site links to.
You can also open any of the .html files in Chrome and use Print > Save as PDF
(A4, margins: none, background graphics: on).
"""
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "static" / "resume"

# (source, output path relative to the repo root, use the page's own CSS margins)
JOBS = [
    ("en.html", "static/resume/Sepehr_Khastoo_Resume_EN.pdf", False),
    ("fa.html", "static/resume/Sepehr_Khastoo_Resume_FA.pdf", False),
    # Plain single-column version for job portals; kept out of the published site.
    ("ats-en.html", "resume/Sepehr_Khastoo_Resume_EN_ATS.pdf", True),
]


def serve_repo() -> ThreadingHTTPServer:
    """Fonts are blocked on file:// URLs, so serve the repo over local HTTP."""
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:  # keep the console clean
            pass

    handler = functools.partial(QuietHandler, directory=str(HERE.parent))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    server = serve_repo()
    base = f"http://127.0.0.1:{server.server_address[1]}/resume/"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for source, target, use_css_margins in JOBS:
            page.goto(base + source)
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            page.pdf(
                path=str(HERE.parent / target),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin=None if use_css_margins else {"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            print(f"wrote {target}")
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    main()
