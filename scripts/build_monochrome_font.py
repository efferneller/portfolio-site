"""Create the monochrome Cimero Pro webfont without changing its outlines.

Developer-only dependency: python3 -m pip install 'fonttools[woff]'
Run from the repository root: python3 scripts/build_monochrome_font.py
The generated WOFF2 is committed; the website build needs only Node.js.
"""

from pathlib import Path

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "static/fonts/CimeroPro.otf"
OUTPUT = ROOT / "static/fonts/CimeroPro-Monochrome.woff2"
COLOR_TABLES = ("SVG ", "COLR", "CPAL", "CBDT", "CBLC", "sbix")


def main():
    source = TTFont(SOURCE, recalcBBoxes=False, recalcTimestamp=False)
    removed = [tag for tag in COLOR_TABLES if tag in source]
    for tag in removed:
        del source[tag]
    source.flavor = "woff2"
    source.save(OUTPUT)

    original = TTFont(SOURCE)
    result = TTFont(OUTPUT)
    assert not any(tag in result for tag in COLOR_TABLES)
    assert result.getGlyphOrder() == original.getGlyphOrder()
    assert result.getBestCmap() == original.getBestCmap()
    assert result["hmtx"].metrics == original["hmtx"].metrics
    # CFF outlines, positioning, substitutions and names remain byte-for-byte
    # unchanged. Only the optional color glyph table is removed.
    for tag in ("CFF ", "GPOS", "GSUB", "hhea", "OS/2", "name"):
        assert result.getTableData(tag) == original.getTableData(tag), tag

    print(f"Removed color tables: {', '.join(removed)}")
    print(f"Preserved all {len(result.getGlyphOrder())} glyphs and font metrics")
    print(f"Created {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
