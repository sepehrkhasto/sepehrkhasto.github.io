"""Write the favicon and the touch icon from the same drawing the header uses (build.mark_svg).

The shapes and colours are identical; only the line weight grows at small sizes so the star stays readable.
Run from the site root:  python3 tools/make_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

IMG = ROOT / "static" / "assets" / "img"
FAVICON_STROKE = 2.0  # 1.6 in the header at 32 px; the favicon is shown at 16 px


def render(svg: str, size: int, path: Path) -> None:
    from playwright.sync_api import sync_playwright

    html = f'<body style="margin:0;background:transparent">{svg.replace("<svg", f"<svg width={size} height={size}", 1)}</body>'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": size, "height": size})
        page.set_content(html)
        page.screenshot(path=str(path), omit_background=True)
        browser.close()


def main() -> None:
    fav = build.mark_svg(stroke=FAVICON_STROKE, radius=6)
    (IMG / "favicon.svg").write_text(fav + "\n", encoding="utf-8")
    render(fav, 32, IMG / "favicon-32.png")
    render(build.mark_svg(stroke=FAVICON_STROKE, bleed=True), 180, IMG / "apple-touch-icon.png")
    print("wrote favicon.svg, favicon-32.png, apple-touch-icon.png")


if __name__ == "__main__":
    main()
