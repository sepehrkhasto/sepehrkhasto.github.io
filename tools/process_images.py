"""Convert the source screenshots in assets-src/screenshots/ to responsive WebP files.

Run from the repository root:  python tools/process_images.py   (needs Pillow)
Writes static/assets/img/work/<name>-<width>.webp and prints the sizes the build uses.
Screenshots are the projects' own README screenshots, taken from the running applications.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets-src" / "screenshots"
OUT = ROOT / "static" / "assets" / "img" / "work"
WIDTHS = (640, 1280)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for src in sorted(SRC.glob("*.png")):
        im = Image.open(src).convert("RGB")
        manifest[src.stem] = {"w": im.width, "h": im.height, "files": []}
        widths = (320, 600) if im.height > im.width else WIDTHS  # phone screenshots render small
        for width in sorted({min(w, im.width) for w in widths}):
            height = round(im.height * width / im.width)
            out = OUT / f"{src.stem}-{width}.webp"
            im.resize((width, height), Image.LANCZOS).save(out, "WEBP", quality=82, method=6)
            manifest[src.stem]["files"].append([out.name, width])
            print(f"{out.relative_to(ROOT)}  {out.stat().st_size // 1024} KB")
    (ROOT / "assets-src" / "images.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
