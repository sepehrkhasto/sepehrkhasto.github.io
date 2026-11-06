#!/usr/bin/env python3
"""Subset the web fonts to the characters the site can show.

Reads the full fonts from assets-src/fonts/ and writes smaller copies to
static/assets/fonts/. Run `python3 build.py` first so dist/ holds the text of
both pages, then run this, then build again. Needs: pip install fonttools brotli

If you add text with a letter the fonts were not cut for, run this script again.
"""
import re, sys, html
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets-src" / "fonts"
OUT = ROOT / "static" / "assets" / "fonts"

# Always kept, so a new sentence in the content files rarely needs a re-run.
ASCII = {chr(c) for c in range(0x20, 0x7F)}
PUNCT = set(" ©®°±·×–—‘’“”•…←↑→↓≈≤≥™‌‍‎‏")
# The Persian alphabet, Persian digits and Persian punctuation.
FA = set()
for a, b in ((0x0621, 0x063A), (0x0640, 0x0652), (0x06F0, 0x06F9), (0x0660, 0x0669)):
    FA |= {chr(c) for c in range(a, b + 1)}
FA |= set("پچژکگی،؛؟٪٫٬«»ٰٔەة")


def page_text():
    chars = set()
    for f in (ROOT / "dist").rglob("*.html"):
        t = f.read_text(encoding="utf-8")
        t = re.sub(r"<(script|style)\b.*?</\1>", "", t, flags=re.S)
        t = html.unescape(re.sub(r"<[^>]+>", " ", t))
        chars |= set(t)
    for f in (ROOT / "content").glob("*.json"):
        chars |= set(f.read_text(encoding="utf-8"))
    return {c for c in chars if not c.isspace() or c == " "}


def build(name, text):
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = True
    src = SRC / name
    font = TTFont(src)
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(text)))
    sub.subset(font)
    dst = OUT / name
    font.flavor = "woff2"
    font.save(dst)
    # Warn if the page uses a character the full font has but the cut one lost.
    want = {ord(c) for c in text}
    lost = sorted(c for c in want if c in TTFont(src).getBestCmap() and c not in TTFont(dst).getBestCmap())
    if lost:
        print("  WARNING lost:", [hex(c) for c in lost])
    return src.stat().st_size, dst.stat().st_size


def main():
    seen = page_text()
    latin = ASCII | PUNCT | {c for c in seen if ord(c) < 0x250 or 0x2000 <= ord(c) <= 0x23ff}
    arabic = FA | PUNCT | ASCII & set("0123456789()[]{}.,:;!?-/%+=*\"' ") | {c for c in seen if 0x0600 <= ord(c) <= 0x06FF}
    tot_a = tot_b = 0
    for p in sorted(SRC.glob("*.woff2")):
        n = p.name
        chars = arabic if ("vazirmatn" in n) else latin
        a, b = build(n, chars)
        tot_a += a
        tot_b += b
        print(f"{n:48s} {a/1024:7.1f} KB -> {b/1024:6.1f} KB")
    print(f"{'total':48s} {tot_a/1024:7.1f} KB -> {tot_b/1024:6.1f} KB")


if __name__ == "__main__":
    sys.exit(main())
