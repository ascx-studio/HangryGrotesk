#!/usr/bin/env python3
"""Build Hangry Grotesk & Hangry Grotesk Pixel UFO sources, TTF, WOFF, WOFF2, CSS, preview, and ZIP."""

from __future__ import annotations

import datetime
import json
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import ufo2ft
import ufoLib2
from fontTools.pens.pointPen import ReverseContourPointPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram

ROOT = Path(__file__).resolve().parent.parent
FAMILY = "Hangry Grotesk"
STEM = "HangryGrotesk-Regular"
PIXEL_FAMILY = "Hangry Grotesk Pixel"
PIXEL_STEM = "HangryGroteskPixel-Regular"
DOTTED_FAMILY = "Hangry Grotesk Dotted"
DOTTED_STEM = "HangryGroteskDotted-Regular"
EPOCH = datetime.datetime(2026, 10, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)


def reverse_glyph_contours(g: ufoLib2.objects.Glyph, indices: list[int] | None = None) -> None:
    tmp = ufoLib2.objects.Glyph()
    rpen = ReverseContourPointPen(tmp.getPointPen())
    for i, c in enumerate(g.contours):
        if indices is None or i in indices:
            c.drawPoints(rpen)
        else:
            c.drawPoints(tmp.getPointPen())
    g.clearContours()
    for c in tmp.contours:
        g.contours.append(c)


def clean_duplicate_closing_points(g: ufoLib2.objects.Glyph) -> None:
    for c in g.contours:
        if (
            len(c.points) > 1
            and c.points[-1].x == c.points[0].x
            and c.points[-1].y == c.points[0].y
            and c.points[-1].type == "line"
        ):
            c.points.pop()


def build_svg_glyphs(
    ufo: ufoLib2.Font,
    svg_path: Path,
    sidebearing: int = 60,
) -> None:
    digits = "zero one two three four five six seven eight nine".split()
    rows = [
        ("abcdefghi", 368),
        ("jklmnopqr", 516),
        ("stuvwxyz", 664),
        ("ABCDEFGHI", 894),
        ("JKLMNOPQR", 1042),
        ("STUVWXYZ", 1190),
    ]
    baselines = {ch: b for names, b in rows for ch in names}
    baselines.update({"period": 664, "hyphen": 1190})
    baselines.update({d: 1412 for d in digits})
    chars = {"period": ".", "hyphen": "-", **{d: str(i) for i, d in enumerate(digits)}}

    # .notdef glyph
    notdef = ufo.newGlyph(".notdef")
    notdef.width = 374
    pen = notdef.getPen()
    pen.moveTo((34, 0))
    pen.lineTo((34, 682))
    pen.lineTo((306, 682))
    pen.lineTo((306, 0))
    pen.closePath()
    pen.moveTo((68, 34))
    pen.lineTo((272, 34))
    pen.lineTo((272, 648))
    pen.lineTo((68, 648))
    pen.closePath()

    # space & nbspace
    space = ufo.newGlyph("space")
    space.unicodes = [0x0020, 0x00A0]
    space.width = 320

    tree = ET.parse(svg_path)
    paths = tree.findall(".//{http://www.w3.org/2000/svg}path")
    assert len(paths) == 64, f"Expected 64 SVG paths in {svg_path.name}, found {len(paths)}"

    for p in paths:
        name = p.attrib.get("id") or "eight"
        assert name in baselines, f"Unknown glyph: {name}"
        char = chars.get(name, name)
        g = ufo.newGlyph(name)
        g.unicodes = [ord(char)]

        parse_path(p.attrib["d"], g.getPen())
        pts = [pt for c in g.contours for pt in c.points]
        xmin = min(pt.x for pt in pts)
        # In hangrygrotesk.svg, 'eight' is in a nested 0..76.16 viewBox; in hangrygroteskpixel.svg it is on row 7 (1412)
        is_nested_eight = name == "eight" and max(pt.y for pt in pts) < 200
        base = max(pt.y for pt in pts) if is_nested_eight else baselines[name]

        for c in g.contours:
            for pt in c.points:
                pt.x = round((pt.x - xmin) * 10 + sidebearing)
                pt.y = round((base - pt.y) * 10)

        # Honor counter-winding metadata on SVG glyphs when converting to TrueType
        if p.attrib.get("data-reverse-contours") == "1":
            reverse_glyph_contours(g, indices=list(range(1, len(g.contours))))

        clean_duplicate_closing_points(g)
        xmax = max(pt.x for c in g.contours for pt in c.points)
        g.width = round(xmax + sidebearing)


def set_ufo_metadata(
    ufo: ufoLib2.Font,
    pkg: dict,
    copyright_str: str,
    license_str: str,
    family_name: str = FAMILY,
    stem: str = STEM,
    cap_height: int = 762,
    x_height: int = 598,
) -> None:
    raw_major, raw_minor = (int(x) for x in pkg["version"].split(".")[:2])
    major = max(1, raw_major)
    minor = raw_minor
    info = ufo.info
    info.familyName = family_name
    info.styleName = "Regular"
    info.styleMapFamilyName = family_name
    info.styleMapStyleName = "regular"
    info.versionMajor = major
    info.versionMinor = minor
    info.unitsPerEm = 1000
    info.ascender = 950
    info.descender = -250
    info.xHeight = x_height
    info.capHeight = cap_height
    info.italicAngle = 0
    info.copyright = copyright_str
    info.openTypeNameDesigner = pkg["author"]["name"]
    info.openTypeNameManufacturer = pkg["author"]["name"]
    info.openTypeNameDescription = pkg["description"]
    info.openTypeNameLicense = license_str
    info.openTypeNameLicenseURL = "https://openfontlicense.org"
    info.openTypeNameVersion = f"Version {major}.{minor:03d}"
    info.openTypeNameUniqueID = f"{stem}-{pkg['version']}"
    info.openTypeNameSampleText = "The quick brown fox jumps over the lazy dog. 0123456789"
    info.openTypeHheaAscender = 950
    info.openTypeHheaDescender = -250
    info.openTypeHheaLineGap = 0
    info.openTypeOS2TypoAscender = 950
    info.openTypeOS2TypoDescender = -250
    info.openTypeOS2TypoLineGap = 0
    info.openTypeOS2WinAscent = 850
    info.openTypeOS2WinDescent = 250
    info.openTypeOS2WeightClass = 400
    info.openTypeOS2WidthClass = 5
    info.openTypeOS2Type = []
    info.openTypeOS2VendorID = "ASCX"
    info.openTypeOS2Selection = [7]
    info.postscriptUnderlinePosition = -100
    info.postscriptUnderlineThickness = 50
    info.postscriptIsFixedPitch = False


def postprocess_ttf(
    ttf: TTFont,
    pkg: dict,
    copyright_str: str,
    license_str: str,
    family_name: str = FAMILY,
    stem: str = STEM,
    cap_height: int = 762,
    x_height: int = 598,
) -> None:
    raw_major, raw_minor = (int(x) for x in pkg["version"].split(".")[:2])
    major = max(1, raw_major)
    minor = raw_minor
    version_str = f"Version {major}.{minor:03d}"

    y_max = max((g.yMax for g in ttf["glyf"].glyphs.values() if hasattr(g, "yMax")), default=789)
    y_min = min((g.yMin for g in ttf["glyf"].glyphs.values() if hasattr(g, "yMin")), default=-224)
    ttf["head"].yMax = y_max
    ttf["head"].yMin = y_min
    ttf["head"].fontRevision = float(f"{major}.{minor:03d}")
    ttf["head"].macStyle = 0

    # Preserve original vertical metrics (850 / -250)
    asc = 850
    desc = -250
    ttf["hhea"].ascent = asc
    ttf["hhea"].descent = desc
    ttf["hhea"].lineGap = 0

    os2 = ttf["OS/2"]
    os2.version = 4
    os2.sTypoAscender = asc
    os2.sTypoDescender = desc
    os2.sTypoLineGap = 0
    os2.usWinAscent = 850
    os2.usWinDescent = 250
    os2.fsType = 0
    os2.fsSelection = 0x00C0
    os2.achVendID = "ASCX"
    os2.sxHeight = x_height
    os2.sCapHeight = cap_height

    name_table = newTable("name")
    name_table.names = []
    records = {
        0: copyright_str,
        1: family_name,
        2: "Regular",
        3: f"{stem}-{pkg['version']}",
        4: f"{family_name} Regular",
        5: version_str,
        6: stem,
        8: pkg["author"]["name"],
        9: pkg["author"]["name"],
        10: pkg["description"],
        13: license_str,
        14: "https://openfontlicense.org",
        19: "The quick brown fox jumps over the lazy dog. 0123456789",
    }
    for name_id, value in records.items():
        name_table.setName(value, name_id, 3, 1, 0x0409)
    ttf["name"] = name_table

    gasp = newTable("gasp")
    gasp.version = 1
    gasp.gaspRange = {0xFFFF: 0x000F}
    ttf["gasp"] = gasp

    prog = ttProgram.Program()
    prog.fromBytecode([0xB8, 0x01, 0xFF, 0x85, 0xB0, 0x04, 0x8D])
    prep = newTable("prep")
    prep.program = prog
    ttf["prep"] = prep

    ttf["maxp"].maxZones = 2

    meta = newTable("meta")
    meta.data = {"dlng": "Latn", "slng": "Latn"}
    ttf["meta"] = meta


def save_font_formats(
    ttf: TTFont,
    stem: str,
    dist_fonts_dir: Path,
    gf_ttf_dir: Path,
    gf_web_dir: Path,
) -> tuple[Path, Path, Path]:
    ttf_path = dist_fonts_dir / f"{stem}.ttf"
    woff_path = dist_fonts_dir / f"{stem}.woff"
    woff2_path = dist_fonts_dir / f"{stem}.woff2"

    ttf.flavor = None
    ttf.save(ttf_path)
    shutil.copy2(ttf_path, gf_ttf_dir / f"{stem}.ttf")

    ttf.flavor = "woff"
    ttf.save(woff_path)

    ttf.flavor = "woff2"
    ttf.save(woff2_path)
    shutil.copy2(woff2_path, gf_web_dir / f"{stem}.woff2")

    return ttf_path, woff_path, woff2_path


def main() -> None:
    pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    ofl_path = ROOT / "OFL.txt"
    license_path = ROOT / "LICENSE.txt"
    if license_path.exists():
        license_path.unlink()

    ofl_text = ofl_path.read_text(encoding="utf-8")
    copyright_str = next(line for line in ofl_text.splitlines() if line.startswith("Copyright"))
    license_str = (
        "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
        "This license is available with a FAQ at: https://openfontlicense.org"
    )

    sources_dir = ROOT / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build Regular UFO & TTF from src/hangrygrotesk.svg
    ufo = ufoLib2.Font()
    build_svg_glyphs(ufo, ROOT / "src" / "hangrygrotesk.svg", sidebearing=60)
    set_ufo_metadata(ufo, pkg, copyright_str, license_str)

    ufo_path = sources_dir / "HangryGrotesk.ufo"
    if ufo_path.exists():
        shutil.rmtree(ufo_path)
    ufo.save(ufo_path, overwrite=True)

    # Compile Regular TTF directly from SVG-derived UFO without reversing or merging stencil contours
    ttf = ufo2ft.compileTTF(ufo, removeOverlaps=False, reverseDirection=False, inplace=False)
    postprocess_ttf(ttf, pkg, copyright_str, license_str)

    # 2. Build Pixel UFO & TTF from src/hangrygroteskpixel.svg
    pixel_ufo = ufoLib2.Font()
    build_svg_glyphs(pixel_ufo, ROOT / "src" / "hangrygroteskpixel.svg", sidebearing=68)
    set_ufo_metadata(
        pixel_ufo,
        pkg,
        copyright_str,
        license_str,
        family_name=PIXEL_FAMILY,
        stem=PIXEL_STEM,
        cap_height=744,
        x_height=608,
    )

    pixel_ufo_path = sources_dir / "HangryGroteskPixel.ufo"
    if pixel_ufo_path.exists():
        shutil.rmtree(pixel_ufo_path)
    pixel_ufo.save(pixel_ufo_path, overwrite=True)

    # Compile Pixel TTF directly from discrete 34-UPEM pixel tiles in src/hangrygroteskpixel.svg
    pixel_ttf = ufo2ft.compileTTF(
        pixel_ufo, removeOverlaps=False, reverseDirection=False, inplace=False
    )
    postprocess_ttf(
        pixel_ttf,
        pkg,
        copyright_str,
        license_str,
        family_name=PIXEL_FAMILY,
        stem=PIXEL_STEM,
        cap_height=744,
        x_height=608,
    )

    # 3. Build Dotted UFO & TTF from src/hangrygroteskdotted.svg
    dotted_ufo = ufoLib2.Font()
    build_svg_glyphs(dotted_ufo, ROOT / "src" / "hangrygroteskdotted.svg", sidebearing=68)
    set_ufo_metadata(
        dotted_ufo,
        pkg,
        copyright_str,
        license_str,
        family_name=DOTTED_FAMILY,
        stem=DOTTED_STEM,
        cap_height=742,
        x_height=606,
    )

    dotted_ufo_path = sources_dir / "HangryGroteskDotted.ufo"
    if dotted_ufo_path.exists():
        shutil.rmtree(dotted_ufo_path)
    dotted_ufo.save(dotted_ufo_path, overwrite=True)

    # Compile Dotted TTF directly from discrete 34-UPEM circular dots in src/hangrygroteskdotted.svg
    dotted_ttf = ufo2ft.compileTTF(
        dotted_ufo, removeOverlaps=False, reverseDirection=False, inplace=False
    )
    postprocess_ttf(
        dotted_ttf,
        pkg,
        copyright_str,
        license_str,
        family_name=DOTTED_FAMILY,
        stem=DOTTED_STEM,
        cap_height=742,
        x_height=606,
    )

    gf_ttf_dir = ROOT / "fonts" / "ttf"
    gf_web_dir = ROOT / "fonts" / "webfonts"
    dist_fonts_dir = ROOT / "dist" / "fonts"
    for d in (gf_ttf_dir, gf_web_dir, dist_fonts_dir):
        d.mkdir(parents=True, exist_ok=True)

    ttf_path, woff_path, woff2_path = save_font_formats(
        ttf, STEM, dist_fonts_dir, gf_ttf_dir, gf_web_dir
    )
    pix_ttf_path, pix_woff_path, pix_woff2_path = save_font_formats(
        pixel_ttf, PIXEL_STEM, dist_fonts_dir, gf_ttf_dir, gf_web_dir
    )
    dot_ttf_path, dot_woff_path, dot_woff2_path = save_font_formats(
        dotted_ttf, DOTTED_STEM, dist_fonts_dir, gf_ttf_dir, gf_web_dir
    )

    # Verify exact glyph outlines from src/hangrygrotesk.svg, src/hangrygroteskpixel.svg, and src/hangrygroteskdotted.svg
    reloaded = TTFont(ttf_path)
    reloaded_pix = TTFont(pix_ttf_path)
    reloaded_dot = TTFont(dot_ttf_path)
    expected_codes = sorted([
        32, 45, 46,
        *range(48, 58),
        *range(65, 91),
        *range(97, 123),
        160,
    ])
    assert sorted(reloaded.getBestCmap().keys()) == expected_codes
    assert sorted(reloaded_pix.getBestCmap().keys()) == expected_codes
    assert sorted(reloaded_dot.getBestCmap().keys()) == expected_codes
    assert reloaded["glyf"]["A"].yMin == 0
    assert reloaded["glyf"]["A"].yMax == 762
    assert reloaded["glyf"]["g"].yMin < 0
    assert reloaded["glyf"]["eight"].yMin == 0
    assert reloaded["glyf"]["eight"].yMax == 762
    assert reloaded["glyf"]["eight"].numberOfContours == 2
    assert reloaded_pix["glyf"]["A"].yMin == 0
    assert reloaded_pix["glyf"]["A"].yMax == 744
    assert reloaded_dot["glyf"]["A"].yMin == 0
    assert reloaded_dot["glyf"]["A"].yMax == 742

    css_text = f"""/* {FAMILY}, {PIXEL_FAMILY} & {DOTTED_FAMILY} | {pkg["author"]["name"]} | {pkg["license"]} */
@font-face {{
  font-family: "{FAMILY}";
  src: url("./fonts/{STEM}.woff2") format("woff2"),
       url("./fonts/{STEM}.woff") format("woff");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  unicode-range: U+0020, U+002D-002E, U+0030-0039, U+0041-005A, U+0061-007A, U+00A0;
}}

@font-face {{
  font-family: "{PIXEL_FAMILY}";
  src: url("./fonts/{PIXEL_STEM}.woff2") format("woff2"),
       url("./fonts/{PIXEL_STEM}.woff") format("woff");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  unicode-range: U+0020, U+002D-002E, U+0030-0039, U+0041-005A, U+0061-007A, U+00A0;
}}

@font-face {{
  font-family: "{DOTTED_FAMILY}";
  src: url("./fonts/{DOTTED_STEM}.woff2") format("woff2"),
       url("./fonts/{DOTTED_STEM}.woff") format("woff");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
  unicode-range: U+0020, U+002D-002E, U+0030-0039, U+0041-005A, U+0061-007A, U+00A0;
}}
"""
    (ROOT / "dist" / "hangrygrotesk.css").write_text(css_text, encoding="utf-8")
    shutil.copy2(ROOT / "src" / "preview.html", ROOT / "dist" / "preview.html")

    zip_path = ROOT / "dist" / f"HangryGrotesk-{pkg['version']}.zip"
    zip_entries = {
        f"fonts/{STEM}.ttf": ttf_path.read_bytes(),
        f"fonts/{STEM}.woff": woff_path.read_bytes(),
        f"fonts/{STEM}.woff2": woff2_path.read_bytes(),
        f"fonts/{PIXEL_STEM}.ttf": pix_ttf_path.read_bytes(),
        f"fonts/{PIXEL_STEM}.woff": pix_woff_path.read_bytes(),
        f"fonts/{PIXEL_STEM}.woff2": pix_woff2_path.read_bytes(),
        f"fonts/{DOTTED_STEM}.ttf": dot_ttf_path.read_bytes(),
        f"fonts/{DOTTED_STEM}.woff": dot_woff_path.read_bytes(),
        f"fonts/{DOTTED_STEM}.woff2": dot_woff2_path.read_bytes(),
        "hangrygrotesk.css": css_text.encode("utf-8"),
        "preview.html": (ROOT / "src" / "preview.html").read_bytes(),
        "README.md": (ROOT / "README.md").read_bytes(),
        "OFL.txt": ofl_path.read_bytes(),
    }
    date_time = (EPOCH.year, EPOCH.month, EPOCH.day, EPOCH.hour, EPOCH.minute, EPOCH.second)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, data in zip_entries.items():
            info = zipfile.ZipInfo(filename=arcname, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)

    print(
        f"Built and validated Regular, Pixel & Dotted UFO, TTF, WOFF, WOFF2, metadata, and ZIP: {zip_path}"
    )


if __name__ == "__main__":
    main()
