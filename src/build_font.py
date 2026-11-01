#!/usr/bin/env python3
"""Build Hangry Grotesk family (Regular, Serif, Pixel, Dotted, Diamond) UFOs, TTFs, WOFF/WOFF2, CSS, preview, and ZIP."""

from __future__ import annotations

import datetime
import json
import math
import shutil
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pathops
import ufo2ft
import ufoLib2
from fontTools.agl import UV2AGL
from fontTools.otlLib.builder import buildStatTable
from fontTools.pens.pointPen import ReverseContourPointPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._f_v_a_r import Axis, NamedInstance
from fontTools.ttLib.tables._g_v_a_r import TupleVariation

ROOT = Path(__file__).resolve().parent.parent
FAMILY = "Hangry Grotesk"
STEM = "HangryGrotesk-Regular"
SERIF_FAMILY = "Hangry Grotesk Serif"
SERIF_STEM = "HangryGroteskSerif-Regular"
PIXEL_FAMILY = "Hangry Grotesk Pixel"
PIXEL_STEM = "HangryGroteskPixel-Regular"
DOTTED_FAMILY = "Hangry Grotesk Dotted"
DOTTED_STEM = "HangryGroteskDotted-Regular"
DIAMOND_FAMILY = "Hangry Grotesk Diamond"
DIAMOND_STEM = "HangryGroteskDiamond-Regular"
EPOCH = datetime.datetime(2026, 10, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)

PROD_NAMES = {
    0x00A0: "uni00A0",
    0x0122: "uni0122",
    0x0123: "uni0123",
    0x0136: "uni0136",
    0x0137: "uni0137",
    0x013B: "uni013B",
    0x013C: "uni013C",
    0x0145: "uni0145",
    0x0146: "uni0146",
    0x0218: "uni0218",
    0x0219: "uni0219",
    0x021A: "uni021A",
    0x021B: "uni021B",
    0x0237: "uni0237",
    0x0302: "uni0302",
    0x0304: "uni0304",
    0x0306: "uni0306",
    0x0307: "uni0307",
    0x0308: "uni0308",
    0x030A: "uni030A",
    0x030B: "uni030B",
    0x030C: "uni030C",
    0x0326: "uni0326",
    0x0327: "uni0327",
    0x0328: "uni0328",
    0x1E9E: "uni1E9E",
}


def glyph_name_for_unicode(cp: int) -> str:
    if cp in PROD_NAMES:
        return PROD_NAMES[cp]
    if cp in UV2AGL:
        return UV2AGL[cp]
    return f"uni{cp:04X}"


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


def contour_signed_area(c: ufoLib2.objects.Contour) -> float:
    pts = [(pt.x, pt.y) for pt in c.points]
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return 0.5 * area


def add_rect(pen, x0: float, y0: float, x1: float, y1: float) -> None:
    """Clockwise rectangle in TrueType UPEM coordinates (x0 < x1, y0 < y1)."""
    pen.moveTo((round(x0), round(y0)))
    pen.lineTo((round(x0), round(y1)))
    pen.lineTo((round(x1), round(y1)))
    pen.lineTo((round(x1), round(y0)))
    pen.closePath()


def add_poly(pen, pts: list[tuple[float, float]], clockwise: bool = True) -> None:
    """Polygon in TrueType UPEM coordinates with guaranteed winding direction."""
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    # In UPEM (Y-up), clockwise has negative signed area
    if (clockwise and area > 0) or (not clockwise and area < 0):
        pts = list(reversed(pts))
    pen.moveTo((round(pts[0][0]), round(pts[0][1])))
    for x, y in pts[1:]:
        pen.lineTo((round(x), round(y)))
    pen.closePath()


def add_circle(pen, cx: float, cy: float, r: float, clockwise: bool = True) -> None:
    k = 0.55228475 * r
    pts = [
        ((cx, cy + r), (cx + k, cy + r), (cx + r, cy + k), (cx + r, cy)),
        ((cx + r, cy), (cx + r, cy - k), (cx + k, cy - r), (cx, cy - r)),
        ((cx, cy - r), (cx - k, cy - r), (cx - r, cy - k), (cx - r, cy)),
        ((cx - r, cy), (cx - r, cy + k), (cx - k, cy + r), (cx, cy + r)),
    ]
    if not clockwise:
        pts = [
            ((cx, cy + r), (cx - k, cy + r), (cx - r, cy + k), (cx - r, cy)),
            ((cx - r, cy), (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r)),
            ((cx, cy - r), (cx + k, cy - r), (cx + r, cy - k), (cx + r, cy)),
            ((cx + r, cy), (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r)),
        ]
    pen.moveTo((round(pts[0][0][0]), round(pts[0][0][1])))
    for _, c1, c2, end in pts:
        pen.curveTo(
            (round(c1[0]), round(c1[1])),
            (round(c2[0]), round(c2[1])),
            (round(end[0]), round(end[1])),
        )
    pen.closePath()


def add_ring(pen, cx: float, cy: float, r_out: float, r_in: float) -> None:
    add_circle(pen, cx, cy, r_out, clockwise=True)
    add_circle(pen, cx, cy, r_in, clockwise=False)


def add_serif_spur_upem(pen, x_stem: float, y_line: float, dx: float, dy: float, h_tip: float = 32.0) -> None:
    """Add a sharp-tipped, concavely curved bracketed serif spur in UPEM (Y-up) coordinates."""
    x_tip = x_stem + dx
    y_stem_end = y_line + dy
    sign_y = 1.0 if dy > 0 else -1.0
    y_tip = y_line + sign_y * min(h_tip, abs(dy) * 0.3)

    cx1 = x_stem + dx * 0.42
    cy1 = y_line + sign_y * (abs(dy) * 0.22)
    cx2 = x_stem + dx * 0.08
    cy2 = y_line + sign_y * (abs(dy) * 0.55)

    # In Y-up UPEM, dx * dy < 0 is clockwise for P0(x_stem, y_line)->P1(x_tip, y_line)->P2(x_tip, y_tip)->P3(x_stem, y_stem_end)
    if dx * dy < 0:
        pen.moveTo((round(x_stem), round(y_line)))
        pen.lineTo((round(x_tip), round(y_line)))
        pen.lineTo((round(x_tip), round(y_tip)))
        pen.curveTo((round(cx1), round(cy1)), (round(cx2), round(cy2)), (round(x_stem), round(y_stem_end)))
        pen.closePath()
    else:
        pen.moveTo((round(x_stem), round(y_line)))
        pen.lineTo((round(x_stem), round(y_stem_end)))
        pen.curveTo((round(cx2), round(cy2)), (round(cx1), round(cy1)), (round(x_tip), round(y_tip)))
        pen.lineTo((round(x_tip), round(y_line)))
        pen.closePath()


def copy_transformed(
    src_glyph: ufoLib2.objects.Glyph,
    dst_pen,
    transform: tuple[float, float, float, float, float, float] = (1, 0, 0, 1, 0, 0),
    contour_indices: list[int] | None = None,
) -> None:
    rec = RecordingPen()
    for idx, c in enumerate(src_glyph.contours):
        if contour_indices is not None and idx not in contour_indices:
            continue
        c.draw(rec)
    tpen = TransformPen(dst_pen, transform)
    rec.replay(tpen)


def glyph_bounds(g: ufoLib2.objects.Glyph) -> tuple[int, int, int, int]:
    if not g.contours:
        return (0, 0, 0, 0)
    xs = [pt.x for c in g.contours for pt in c.points]
    ys = [pt.y for c in g.contours for pt in c.points]
    return (round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys)))


def normalize_lsb(g: ufoLib2.objects.Glyph, lsb: int = 60, rsb: int = 60) -> None:
    if not g.contours:
        return
    xmin, _, xmax, _ = glyph_bounds(g)
    dx = lsb - xmin
    if dx != 0:
        for c in g.contours:
            for pt in c.points:
                pt.x = round(pt.x + dx)
    _, _, new_xmax, _ = glyph_bounds(g)
    g.width = round(new_xmax + rsb)


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
    space.unicodes = [0x0020]
    space.width = 320

    nbspace = ufo.newGlyph("uni00A0")
    nbspace.unicodes = [0x00A0]
    nbspace.width = 320

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
        is_nested_eight = name == "eight" and max(pt.y for pt in pts) < 200
        base = max(pt.y for pt in pts) if is_nested_eight else baselines[name]

        for c in g.contours:
            for pt in c.points:
                pt.x = round((pt.x - xmin) * 10 + sidebearing)
                pt.y = round((base - pt.y) * 10)

        if p.attrib.get("data-reverse-contours") == "1":
            # In hangrygrotesk.svg, contour 1 is the inner lower loop of 'eight'
            reverse_glyph_contours(g, indices=[1])

        clean_duplicate_closing_points(g)
        xmax = max(pt.x for c in g.contours for pt in c.points)
        g.width = round(xmax + sidebearing)


def build_gf_latin_core_glyphs(
    ufo: ufoLib2.Font,
    is_serif: bool = False,
    sidebearing: int = 60,
) -> None:
    """Construct all remaining GF_Latin_Core Punctuation, Symbols, Currency & Common Latin glyphs."""

    def new_g(cp: int | None, name: str | None = None) -> ufoLib2.objects.Glyph:
        gname = name or glyph_name_for_unicode(cp)
        g = ufo.newGlyph(gname)
        if cp is not None:
            g.unicodes = [cp]
        return g

    # 1. Dotless i and j (derived from i and j without top dot contour)
    dotlessi = new_g(0x0131, "dotlessi")
    # For both Regular and Serif, contour 1 of 'i' is the circular dot (y > 600); keep all contours with ymin < 580
    i_stem_indices = [
        idx for idx, c in enumerate(ufo["i"].contours)
        if min(pt.y for pt in c.points) < 580
    ]
    copy_transformed(ufo["i"], dotlessi.getPen(), contour_indices=i_stem_indices)
    normalize_lsb(dotlessi, sidebearing, sidebearing)

    dotlessj = new_g(0x0237, "uni0237")
    j_stem_indices = [
        idx for idx, c in enumerate(ufo["j"].contours)
        if min(pt.y for pt in c.points) < 580
    ]
    copy_transformed(ufo["j"], dotlessj.getPen(), contour_indices=j_stem_indices)
    normalize_lsb(dotlessj, sidebearing, sidebearing)

    # 2. Diacritic mark drawing helper (matching Hangry Grotesk stencil style)
    def draw_mark(pen, mark_type: str, cx: float, y_base: float) -> None:
        if mark_type == "acute":
            add_poly(pen, [(cx - 55, y_base), (cx + 15, y_base + 145), (cx + 105, y_base + 145), (cx + 25, y_base)])
        elif mark_type == "grave":
            add_poly(pen, [(cx - 25, y_base), (cx - 105, y_base + 145), (cx - 15, y_base + 145), (cx + 55, y_base)])
        elif mark_type == "circumflex":
            add_poly(pen, [(cx - 135, y_base), (cx - 20, y_base + 145), (cx + 20, y_base + 145), (cx + 20, y_base + 65), (cx - 55, y_base)])
            add_poly(pen, [(cx + 45, y_base + 110), (cx + 135, y_base), (cx + 55, y_base), (cx + 45, y_base + 15)])
        elif mark_type == "caron":
            add_poly(pen, [(cx - 135, y_base + 145), (cx - 55, y_base + 145), (cx + 20, y_base + 80), (cx + 20, y_base), (cx - 20, y_base)])
            add_poly(pen, [(cx + 45, y_base + 35), (cx + 45, y_base + 130), (cx + 55, y_base + 145), (cx + 135, y_base + 145)])
        elif mark_type == "macron":
            add_rect(pen, cx - 130, y_base + 35, cx + 130, y_base + 115)
        elif mark_type == "breve":
            add_poly(pen, [
                (cx - 130, y_base + 140), (cx - 55, y_base + 140),
                (cx - 35, y_base + 65), (cx + 35, y_base + 65),
                (cx + 55, y_base + 140), (cx + 130, y_base + 140),
                (cx + 85, y_base), (cx - 85, y_base),
            ])
        elif mark_type == "dotaccent":
            add_circle(pen, cx, y_base + 65, 65)
        elif mark_type == "dieresis":
            add_circle(pen, cx - 95, y_base + 65, 60)
            add_circle(pen, cx + 95, y_base + 65, 60)
        elif mark_type == "ring":
            add_ring(pen, cx, y_base + 80, 85, 35)
        elif mark_type == "tilde":
            add_poly(pen, [
                (cx - 145, y_base + 15), (cx - 65, y_base + 130),
                (cx + 45, y_base + 65), (cx + 85, y_base + 135),
                (cx + 145, y_base + 135), (cx + 65, y_base + 15),
                (cx - 45, y_base + 80), (cx - 85, y_base + 15),
            ])
        elif mark_type == "hungarumlaut":
            add_poly(pen, [(cx - 125, y_base), (cx - 65, y_base + 145), (cx + 5, y_base + 145), (cx - 55, y_base)])
            add_poly(pen, [(cx - 5, y_base), (cx + 55, y_base + 145), (cx + 125, y_base + 145), (cx + 65, y_base)])
        elif mark_type == "cedilla":
            add_poly(pen, [
                (cx - 25, 0), (cx + 45, 0),
                (cx + 75, -110), (cx + 35, -195),
                (cx - 75, -195), (cx - 75, -130),
                (cx - 5, -130), (cx + 5, -90),
            ])
        elif mark_type == "commaaccent":
            add_poly(pen, [
                (cx - 35, -35), (cx + 45, -35),
                (cx + 45, -125), (cx - 15, -205),
                (cx - 65, -205), (cx - 20, -120), (cx - 35, -120),
            ])
        elif mark_type == "ogonek":
            add_poly(pen, [
                (cx - 15, 0), (cx + 55, 0),
                (cx + 15, -115), (cx + 85, -130),
                (cx + 85, -195), (cx - 55, -195),
                (cx - 75, -110),
            ])

    combining_specs = [
        (0x0300, "gravecomb", "grave", 640),
        (0x0301, "acutecomb", "acute", 640),
        (0x0302, "uni0302", "circumflex", 640),
        (0x0303, "tildecomb", "tilde", 640),
        (0x0304, "uni0304", "macron", 640),
        (0x0306, "uni0306", "breve", 640),
        (0x0307, "uni0307", "dotaccent", 640),
        (0x0308, "uni0308", "dieresis", 640),
        (0x030A, "uni030A", "ring", 640),
        (0x030B, "uni030B", "hungarumlaut", 640),
        (0x030C, "uni030C", "caron", 640),
        (0x0326, "uni0326", "commaaccent", 0),
        (0x0327, "uni0327", "cedilla", 0),
        (0x0328, "uni0328", "ogonek", 0),
    ]
    for cp, gname, mtype, y_b in combining_specs:
        g = new_g(cp, gname)
        draw_mark(g.getPen(), mtype, 0, y_b)
        g.width = 0

    spacing_marks = [
        (0x005E, "asciicircum", "circumflex", 580),
        (0x0060, "grave", "grave", 640),
        (0x007E, "asciitilde", "tilde", 320),
        (0x00A8, "dieresis", "dieresis", 640),
        (0x00AF, "macron", "macron", 640),
        (0x00B4, "acute", "acute", 640),
        (0x00B8, "cedilla", "cedilla", 0),
        (0x02C6, "circumflex", "circumflex", 640),
        (0x02C7, "caron", "caron", 640),
        (0x02D8, "breve", "breve", 640),
        (0x02D9, "dotaccent", "dotaccent", 640),
        (0x02DA, "ring", "ring", 640),
        (0x02DB, "ogonek", "ogonek", 0),
        (0x02DC, "tilde", "tilde", 640),
        (0x02DD, "hungarumlaut", "hungarumlaut", 640),
    ]
    for cp, gname, mtype, y_b in spacing_marks:
        g = new_g(cp, gname)
        draw_mark(g.getPen(), mtype, 200, y_b)
        normalize_lsb(g, sidebearing, sidebearing)

    # 3. Punctuation, Symbols, and Currency in stencil style (with curved serifs if is_serif)
    g = new_g(0x0021)
    p = g.getPen()
    add_circle(p, 140, 70, 80)
    add_rect(p, 82, 230, 198, 762)
    if is_serif:
        add_serif_spur_upem(p, 82, 762, -78, -130)
        add_serif_spur_upem(p, 198, 762, 78, -130)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A1)
    p = g.getPen()
    add_circle(p, 140, 528, 80)
    add_rect(p, 82, -164, 198, 368)
    if is_serif:
        add_serif_spur_upem(p, 82, -164, -78, 130)
        add_serif_spur_upem(p, 198, -164, 78, 130)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0027)
    p = g.getPen()
    add_rect(p, 60, 490, 176, 762)
    if is_serif:
        add_serif_spur_upem(p, 60, 762, -62, -100)
        add_serif_spur_upem(p, 176, 762, 62, -100)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0022)
    p = g.getPen()
    add_rect(p, 60, 490, 176, 762)
    add_rect(p, 236, 490, 352, 762)
    if is_serif:
        add_serif_spur_upem(p, 60, 762, -60, -100)
        add_serif_spur_upem(p, 352, 762, 60, -100)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x002C)
    add_poly(g.getPen(), [(60, 150), (180, 150), (180, 10), (110, -140), (45, -140), (95, 10), (60, 10)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003A)
    p = g.getPen()
    add_circle(p, 140, 70, 80)
    add_circle(p, 140, 450, 80)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003B)
    p = g.getPen()
    add_circle(p, 140, 450, 80)
    add_poly(p, [(60, 150), (180, 150), (180, 10), (110, -140), (45, -140), (95, 10), (60, 10)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00B7)
    add_circle(g.getPen(), 140, 381, 80)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2022)
    add_circle(g.getPen(), 190, 381, 130)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2026)
    p = g.getPen()
    add_circle(p, 140, 70, 80)
    add_circle(p, 360, 70, 80)
    add_circle(p, 580, 70, 80)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003F)
    p = g.getPen()
    add_circle(p, 240, 70, 80)
    add_rect(p, 182, 220, 298, 370)
    add_poly(p, [
        (60, 580), (60, 762), (420, 762), (500, 680),
        (500, 440), (298, 345), (182, 345), (384, 480),
        (384, 646), (176, 646), (176, 580),
    ])
    if is_serif:
        add_serif_spur_upem(p, 60, 762, -45, -145)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00BF)
    p = g.getPen()
    add_circle(p, 320, 528, 80)
    add_rect(p, 262, 228, 378, 378)
    add_poly(p, [
        (500, 18), (500, -164), (140, -164), (60, -82),
        (60, 158), (262, 253), (378, 253), (176, 118),
        (176, -48), (384, -48), (384, 18),
    ])
    if is_serif:
        add_serif_spur_upem(p, 500, -164, 45, 145)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x002F)
    add_poly(g.getPen(), [(60, 0), (310, 762), (426, 762), (176, 0)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x005C)
    add_poly(g.getPen(), [(310, 0), (60, 762), (176, 762), (426, 0)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x007C)
    add_rect(g.getPen(), 60, -160, 176, 762)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x005F)
    add_rect(g.getPen(), 60, -120, 560, -10)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2013)
    add_rect(g.getPen(), 60, 325, 560, 434)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2014)
    add_rect(g.getPen(), 60, 325, 860, 434)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2212)
    add_rect(g.getPen(), 60, 325, 520, 434)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x002B)
    p = g.getPen()
    add_rect(p, 60, 325, 520, 434)
    add_rect(p, 232, 150, 348, 285)
    add_rect(p, 232, 474, 348, 610)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003D)
    p = g.getPen()
    add_rect(p, 60, 210, 520, 320)
    add_rect(p, 60, 440, 520, 550)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00D7)
    p = g.getPen()
    add_poly(p, [(60, 190), (390, 570), (480, 570), (150, 190)])
    add_poly(p, [(390, 190), (60, 570), (150, 570), (480, 190)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00F7)
    p = g.getPen()
    add_rect(p, 60, 325, 520, 434)
    add_circle(p, 290, 560, 65)
    add_circle(p, 290, 195, 65)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003C)
    add_poly(g.getPen(), [(460, 130), (60, 340), (60, 420), (460, 630), (460, 520), (195, 380), (460, 240)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x003E)
    add_poly(g.getPen(), [(60, 130), (460, 340), (460, 420), (60, 630), (60, 520), (325, 380), (60, 240)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0028)
    add_poly(g.getPen(), [(310, -120), (160, 30), (60, 210), (60, 430), (160, 610), (310, 762), (390, 680), (255, 545), (176, 400), (176, 240), (255, 95), (390, -40)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0029)
    add_poly(g.getPen(), [(60, -40), (195, 95), (274, 240), (274, 400), (195, 545), (60, 680), (140, 762), (290, 610), (390, 430), (390, 210), (290, 30), (140, -120)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x005B)
    p = g.getPen()
    add_rect(p, 60, -120, 176, 762)
    add_rect(p, 216, 652, 360, 762)
    add_rect(p, 216, -120, 360, -10)
    if is_serif:
        add_serif_spur_upem(p, 60, 762, -70, -115)
        add_serif_spur_upem(p, 60, -120, -70, 115)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x005D)
    p = g.getPen()
    add_rect(p, 244, -120, 360, 762)
    add_rect(p, 60, 652, 204, 762)
    add_rect(p, 60, -120, 204, -10)
    if is_serif:
        add_serif_spur_upem(p, 360, 762, 70, -115)
        add_serif_spur_upem(p, 360, -120, 70, 115)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x007B)
    p = g.getPen()
    add_poly(p, [(380, 762), (200, 762), (140, 680), (140, 410), (60, 360), (60, 280), (140, 230), (140, -40), (200, -120), (380, -120), (380, -10), (256, -10), (256, 270), (176, 320), (256, 370), (256, 652), (380, 652)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x007D)
    p = g.getPen()
    add_poly(p, [(60, 762), (240, 762), (300, 680), (300, 410), (380, 360), (380, 280), (300, 230), (300, -40), (240, -120), (60, -120), (60, -10), (184, -10), (184, 270), (264, 320), (184, 370), (184, 652), (60, 652)])
    normalize_lsb(g, sidebearing, sidebearing)

    def draw_quote_right(pen, x_off: float, y_off: float) -> None:
        add_poly(pen, [
            (x_off, y_off + 150), (x_off + 120, y_off + 150),
            (x_off + 120, y_off + 10), (x_off + 50, y_off - 140),
            (x_off - 15, y_off - 140), (x_off + 35, y_off + 10),
            (x_off, y_off + 10),
        ])

    def draw_quote_left(pen, x_off: float, y_off: float) -> None:
        add_poly(pen, [
            (x_off + 120, y_off - 140), (x_off, y_off - 140),
            (x_off, y_off), (x_off + 70, y_off + 150),
            (x_off + 135, y_off + 150), (x_off + 85, y_off),
            (x_off + 120, y_off),
        ])

    g = new_g(0x2018)
    draw_quote_left(g.getPen(), 60, 612)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2019)
    draw_quote_right(g.getPen(), 60, 612)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x201A)
    draw_quote_right(g.getPen(), 60, 0)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x201C)
    p = g.getPen()
    draw_quote_left(p, 60, 612)
    draw_quote_left(p, 240, 612)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x201D)
    p = g.getPen()
    draw_quote_right(p, 60, 612)
    draw_quote_right(p, 240, 612)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x201E)
    p = g.getPen()
    draw_quote_right(p, 60, 0)
    draw_quote_right(p, 240, 0)
    normalize_lsb(g, sidebearing, sidebearing)

    def draw_guil_left(pen, x_off: float) -> None:
        add_poly(pen, [(x_off + 220, 110), (x_off, 260), (x_off, 338), (x_off + 220, 488), (x_off + 220, 392), (x_off + 100, 299), (x_off + 220, 206)])

    def draw_guil_right(pen, x_off: float) -> None:
        add_poly(pen, [(x_off, 110), (x_off + 220, 260), (x_off + 220, 338), (x_off, 488), (x_off, 392), (x_off + 120, 299), (x_off, 206)])

    g = new_g(0x2039)
    draw_guil_left(g.getPen(), 60)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x203A)
    draw_guil_right(g.getPen(), 60)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00AB)
    p = g.getPen()
    draw_guil_left(p, 60)
    draw_guil_left(p, 240)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00BB)
    p = g.getPen()
    draw_guil_right(p, 60)
    draw_guil_right(p, 240)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0023)
    p = g.getPen()
    add_poly(p, [(140, 0), (220, 762), (320, 762), (240, 0)])
    add_poly(p, [(360, 0), (440, 762), (540, 762), (460, 0)])
    add_rect(p, 60, 460, 620, 560)
    add_rect(p, 60, 200, 620, 300)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x002A)
    p = g.getPen()
    add_rect(p, 195, 420, 285, 762)
    add_poly(p, [(60, 480), (380, 680), (420, 600), (100, 400)])
    add_poly(p, [(100, 680), (420, 480), (380, 400), (60, 600)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0025)
    p = g.getPen()
    add_ring(p, 200, 610, 140, 55)
    add_poly(p, [(140, 0), (540, 762), (640, 762), (240, 0)])
    add_ring(p, 580, 150, 140, 55)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0026)
    p = g.getPen()
    copy_transformed(ufo["eight"], p, (0.9, 0, 0, 1.0, 0, 0))
    add_poly(p, [(450, 350), (680, 0), (550, 0), (350, 300)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0040)
    p = g.getPen()
    add_ring(p, 420, 381, 360, 260)
    copy_transformed(ufo["a"], p, (0.55, 0, 0, 0.55, 210, 210))
    normalize_lsb(g, sidebearing, sidebearing)

    # Currency & Legal symbols
    g = new_g(0x0024)
    p = g.getPen()
    copy_transformed(ufo["S"], p)
    s_xmin, _, s_xmax, s_ymax = glyph_bounds(ufo["S"])
    s_cx = (s_xmin + s_xmax) / 2.0
    add_rect(p, s_cx - 50, s_ymax, s_cx + 50, s_ymax + 98)
    add_rect(p, s_cx - 50, -98, s_cx + 50, 0)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A2)
    p = g.getPen()
    copy_transformed(ufo["c"], p)
    c_xmin, _, c_xmax, c_ymax = glyph_bounds(ufo["c"])
    c_cx = (c_xmin + c_xmax) / 2.0
    add_rect(p, c_cx - 50, c_ymax, c_cx + 50, c_ymax + 100)
    add_rect(p, c_cx - 50, -100, c_cx + 50, 0)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A3)
    p = g.getPen()
    copy_transformed(ufo["L"], p)
    add_rect(p, 20, 350, 480, 450)
    add_rect(p, 176, 652, 540, 762)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A5)
    p = g.getPen()
    copy_transformed(ufo["Y"], p)
    add_rect(p, 60, 290, 658, 380)
    add_rect(p, 60, 150, 658, 240)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x20AC)
    p = g.getPen()
    copy_transformed(ufo["C"], p, (1, 0, 0, 1, 60, 0))
    add_rect(p, 20, 420, 560, 510)
    add_rect(p, 20, 250, 560, 340)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A7)
    p = g.getPen()
    copy_transformed(ufo["S"], p, (0.8, 0, 0, 0.75, 0, 190))
    copy_transformed(ufo["S"], p, (0.8, 0, 0, 0.75, 0, -150))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00A9)
    p = g.getPen()
    add_ring(p, 420, 381, 360, 260)
    copy_transformed(ufo["C"], p, (0.48, 0, 0, 0.48, 245, 198))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00AE)
    p = g.getPen()
    add_ring(p, 420, 381, 360, 260)
    copy_transformed(ufo["R"], p, (0.46, 0, 0, 0.46, 245, 205))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x2122)
    p = g.getPen()
    copy_transformed(ufo["T"], p, (0.5, 0, 0, 0.5, 30, 381))
    copy_transformed(ufo["M"], p, (0.5, 0, 0, 0.5, 370, 381))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00B0)
    add_ring(g.getPen(), 210, 612, 150, 70)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00B6)
    p = g.getPen()
    add_rect(p, 320, -120, 420, 762)
    add_rect(p, 468, -120, 568, 762)
    add_poly(p, [(240, 350), (60, 440), (60, 670), (240, 762), (280, 762), (280, 350)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00AA)
    p = g.getPen()
    copy_transformed(ufo["a"], p, (0.6, 0, 0, 0.6, 24, 404))
    add_rect(p, 60, 280, 419, 355)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00BA)
    p = g.getPen()
    copy_transformed(ufo["o"], p, (0.6, 0, 0, 0.6, 24, 404))
    add_rect(p, 60, 280, 419, 355)
    normalize_lsb(g, sidebearing, sidebearing)

    # 4. Extended non-decomposable Latin letters
    g = new_g(0x00C6)
    p = g.getPen()
    copy_transformed(ufo["A"], p)
    copy_transformed(ufo["E"], p, (1, 0, 0, 1, 560, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00E6)
    p = g.getPen()
    copy_transformed(ufo["a"], p)
    copy_transformed(ufo["e"], p, (1, 0, 0, 1, 520, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0152)
    p = g.getPen()
    copy_transformed(ufo["O"], p)
    copy_transformed(ufo["E"], p, (1, 0, 0, 1, 580, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0153)
    p = g.getPen()
    copy_transformed(ufo["o"], p)
    copy_transformed(ufo["e"], p, (1, 0, 0, 1, 520, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    for cp in (0x00D0, 0x0110):
        g = new_g(cp)
        p = g.getPen()
        copy_transformed(ufo["D"], p, (1, 0, 0, 1, 40, 0))
        add_rect(p, 20, 340, 420, 440)
        normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00F0)
    p = g.getPen()
    copy_transformed(ufo["o"], p)
    add_poly(p, [(450, 560), (240, 762), (360, 762), (570, 560)])
    add_poly(p, [(240, 590), (540, 740), (580, 665), (280, 515)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0111)
    p = g.getPen()
    copy_transformed(ufo["d"], p)
    add_rect(p, 380, 600, 720, 685)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00D8)
    p = g.getPen()
    copy_transformed(ufo["O"], p)
    add_poly(p, [(60, -40), (620, 802), (720, 802), (160, -40)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00F8)
    p = g.getPen()
    copy_transformed(ufo["o"], p)
    add_poly(p, [(60, -40), (560, 638), (660, 638), (160, -40)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00DE)
    p = g.getPen()
    add_rect(p, 60, 0, 176, 762)
    copy_transformed(ufo["P"], p, (1, 0, 0, 1, 0, -110), contour_indices=[1])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00FE)
    p = g.getPen()
    copy_transformed(ufo["p"], p)
    add_rect(p, 60, 480, 176, 762)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x00DF)
    p = g.getPen()
    add_rect(p, 60, 0, 176, 762)
    copy_transformed(ufo["s"], p, (0.95, 0, 0, 1.25, 160, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x1E9E, "uni1E9E")
    p = g.getPen()
    add_rect(p, 60, 0, 176, 762)
    copy_transformed(ufo["S"], p, (0.95, 0, 0, 1.0, 160, 0))
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0126)
    p = g.getPen()
    copy_transformed(ufo["H"], p, (1, 0, 0, 1, 40, 0))
    add_rect(p, 20, 520, 793, 610)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0127)
    p = g.getPen()
    copy_transformed(ufo["h"], p, (1, 0, 0, 1, 40, 0))
    add_rect(p, 20, 580, 340, 665)
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0141)
    p = g.getPen()
    copy_transformed(ufo["L"], p, (1, 0, 0, 1, 50, 0))
    add_poly(p, [(20, 260), (340, 480), (340, 570), (20, 350)])
    normalize_lsb(g, sidebearing, sidebearing)

    g = new_g(0x0142)
    p = g.getPen()
    copy_transformed(ufo["l"], p, (1, 0, 0, 1, 60, 0))
    add_poly(p, [(20, 300), (290, 490), (290, 580), (20, 390)])
    normalize_lsb(g, sidebearing, sidebearing)

    for gname, y_c in [("periodcentered.loclCAT", 299), ("periodcentered.loclCAT.case", 381)]:
        g = ufo.newGlyph(gname)
        add_circle(g.getPen(), 140, y_c, 80)
        normalize_lsb(g, sidebearing, sidebearing)

    # 5. All 145 decomposable accented Latin letters in GF_Latin_Core
    comb_to_mark = {
        0x0300: ("grave", "top"),
        0x0301: ("acute", "top"),
        0x0302: ("circumflex", "top"),
        0x0303: ("tilde", "top"),
        0x0304: ("macron", "top"),
        0x0306: ("breve", "top"),
        0x0307: ("dotaccent", "top"),
        0x0308: ("dieresis", "top"),
        0x030A: ("ring", "top"),
        0x030B: ("hungarumlaut", "top"),
        0x030C: ("caron", "top"),
        0x0326: ("commaaccent", "bottom"),
        0x0327: ("cedilla", "bottom"),
        0x0328: ("ogonek", "bottom"),
    }

    # 5. All decomposable accented Latin letters (Latin-1 Supplement + Latin Extended-A + Romanian/Turkish/Welsh)
    accented_chars = (
        "ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿ"
        "ĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐő"
        "ŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽžȘșȚțẀẁẂẃẄẅỲỳ"
    )
    target_cps = sorted({ord(ch) for ch in accented_chars})
    existing_cps = {cp for g in ufo for cp in g.unicodes}

    for cp in target_cps:
        if cp in existing_cps:
            continue
        decomp = unicodedata.decomposition(chr(cp))
        assert decomp and not decomp.startswith("<"), f"Unexpected non-decomposable U+{cp:04X}"
        base_cp_str, mark_cp_str = decomp.split()
        base_cp = int(base_cp_str, 16)
        mark_cp = int(mark_cp_str, 16)
        mtype, pos = comb_to_mark[mark_cp]

        if base_cp == ord("i") and pos == "top":
            base_glyph = ufo["dotlessi"]
        else:
            base_glyph = ufo[glyph_name_for_unicode(base_cp)]

        g = new_g(cp)
        p = g.getPen()
        copy_transformed(base_glyph, p)
        xmin, ymin, xmax, ymax = glyph_bounds(base_glyph)
        cx = (xmin + xmax) / 2.0

        if mtype == "caron" and base_cp in (ord("d"), ord("l"), ord("L"), ord("t")):
            vx = xmax + 35 if base_cp != ord("L") else xmin + 185
            add_poly(p, [(vx, 560), (vx + 95, 560), (vx + 95, 670), (vx + 30, 810), (vx - 20, 810), (vx + 15, 670), (vx, 670)])
        elif pos == "top":
            y_top = ymax + 35
            draw_mark(p, mtype, cx, y_top)
        else:
            if base_cp == ord("g") and mtype in ("cedilla", "commaaccent"):
                draw_mark(p, "acute", cx, ymax + 35)
            elif mtype == "ogonek" and base_cp in (ord("A"), ord("a"), ord("E"), ord("e"), ord("U"), ord("u")):
                draw_mark(p, mtype, xmax - 55, 0)
            else:
                draw_mark(p, mtype, cx, 0)

        normalize_lsb(g, sidebearing, sidebearing)


def sample_cubic(p0, p1, p2, p3, steps: int = 8) -> list[tuple[float, float]]:
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def glyph_to_rings(g: ufoLib2.objects.Glyph) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    """Convert a UFO glyph's contours into outer shell rings and inner hole rings."""
    shells: list[list[tuple[float, float]]] = []
    holes: list[list[tuple[float, float]]] = []
    for c in g.contours:
        pts = c.points
        if len(pts) < 3:
            continue
        ring: list[tuple[float, float]] = []
        n = len(pts)
        start_idx = next((idx for idx, p in enumerate(pts) if p.type is not None), 0)
        curr = (pts[start_idx].x, pts[start_idx].y)
        ring.append(curr)
        idx = (start_idx + 1) % n
        steps_taken = 0
        while steps_taken < n:
            pt = pts[idx]
            if pt.type in ("line", "move"):
                curr = (pt.x, pt.y)
                ring.append(curr)
                idx = (idx + 1) % n
                steps_taken += 1
            elif pt.type is None:
                p1 = (pt.x, pt.y)
                pt2 = pts[(idx + 1) % n]
                p2 = (pt2.x, pt2.y)
                pt3 = pts[(idx + 2) % n]
                p3 = (pt3.x, pt3.y)
                ring.extend(sample_cubic(curr, p1, p2, p3, steps=6))
                curr = p3
                idx = (idx + 3) % n
                steps_taken += 3
            else:
                curr = (pt.x, pt.y)
                ring.append(curr)
                idx = (idx + 1) % n
                steps_taken += 1
        if len(ring) >= 3:
            if contour_signed_area(c) <= 0:
                shells.append(ring)
            else:
                holes.append(ring)
    return shells, holes


def point_in_ring(px: float, py: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon check."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_glyph_rings(
    px: float,
    py: float,
    shells: list[list[tuple[float, float]]],
    holes: list[list[tuple[float, float]]],
) -> bool:
    in_shell = any(point_in_ring(px, py, s) for s in shells)
    if not in_shell:
        return False
    in_hole = any(point_in_ring(px, py, h) for h in holes)
    return not in_hole


def rasterize_extra_glyphs_to_grid(
    src_ufo: ufoLib2.Font,
    dst_ufo: ufoLib2.Font,
    tile_mode: str,
    sidebearing: int = 68,
    tile_size: float | None = None,
) -> None:
    """Rasterize all non-base glyphs from src_ufo onto the 34-UPEM Pixel/Dotted/Diamond grid in dst_ufo."""
    existing_names = set(dst_ufo.keys())
    step = 34
    probe_offsets = [(0.0, 0.0), (-4.0, 0.0), (4.0, 0.0), (0.0, -4.0), (0.0, 4.0)]
    for gname in src_ufo.keys():
        if gname in existing_names:
            continue
        src_g = src_ufo[gname]
        dst_g = dst_ufo.newGlyph(gname)
        dst_g.unicodes = list(src_g.unicodes)
        if not src_g.contours or src_g.width == 0:
            if src_g.contours:
                copy_transformed(src_g, dst_g.getPen())
            dst_g.width = src_g.width
            continue

        shells, holes = glyph_to_rings(src_g)
        if not shells:
            dst_g.width = src_g.width
            continue

        xmin, ymin, xmax, ymax = glyph_bounds(src_g)
        c_min = math.floor(xmin / step) - 1
        c_max = math.ceil(xmax / step) + 1
        r_min = math.floor(ymin / step) - 1
        r_max = math.ceil(ymax / step) + 1

        pen = dst_g.getPen()
        for r in range(r_min, r_max + 1):
            cy = r * step + 17.0
            for c in range(c_min, c_max + 1):
                cx = c * step + 17.0
                if any(point_in_glyph_rings(cx + dx, cy + dy, shells, holes) for dx, dy in probe_offsets):
                    if tile_mode == "pixel":
                        sz = tile_size if tile_size is not None else 30.0
                        half = sz / 2.0
                        add_rect(pen, cx - half, cy - half, cx + half, cy + half)
                    elif tile_mode == "dotted":
                        rad = tile_size if tile_size is not None else 14.0
                        add_circle(pen, cx, cy, rad, clockwise=True)
                    elif tile_mode == "diamond":
                        rad = tile_size if tile_size is not None else 16.0
                        add_poly(
                            pen,
                            [(cx, cy + rad), (cx + rad, cy), (cx, cy - rad), (cx - rad, cy)],
                            clockwise=True,
                        )
        if dst_g.contours:
            normalize_lsb(dst_g, sidebearing, sidebearing)
        else:
            copy_transformed(src_g, dst_g.getPen())
            normalize_lsb(dst_g, sidebearing, sidebearing)


def build_weighted_outline_ufo(src_ufo: ufoLib2.Font, delta_upem: float) -> ufoLib2.Font:
    """Create a new UFO by offsetting all glyph contours in src_ufo by delta_upem."""
    dst = ufoLib2.Font()
    for gname in src_ufo.keys():
        src_g = src_ufo[gname]
        dst_g = dst.newGlyph(gname)
        dst_g.unicodes = list(src_g.unicodes)
        dst_g.width = src_g.width
        if not src_g.contours or gname == ".notdef" or abs(delta_upem) < 1e-3:
            for c in src_g.contours:
                c.draw(dst_g.getPen())
            continue
        sk_path = pathops.Path()
        src_g.draw(sk_path.getPen())
        sk_path.simplify(fix_winding=True)
        stroke_path = pathops.Path(sk_path)
        stroke_path.stroke(
            abs(delta_upem) * 2.0,
            pathops.LineCap.BUTT_CAP,
            pathops.LineJoin.MITER_JOIN,
            4.0,
        )
        if delta_upem > 0:
            res = pathops.op(sk_path, stroke_path, pathops.PathOp.UNION)
        else:
            res = pathops.op(sk_path, stroke_path, pathops.PathOp.DIFFERENCE)
        res.simplify(fix_winding=True)
        res.draw(dst_g.getPen())
    return dst


def build_weighted_matrix_ufo(
    base_matrix_ufo: ufoLib2.Font,
    tile_mode: str,
    tile_size: float,
) -> ufoLib2.Font:
    """Create a weighted Pixel, Dotted, or Diamond UFO by resizing each discrete 34-UPEM cell tile around its center."""
    dst = ufoLib2.Font()
    for gname in base_matrix_ufo.keys():
        src_g = base_matrix_ufo[gname]
        dst_g = dst.newGlyph(gname)
        dst_g.unicodes = list(src_g.unicodes)
        dst_g.width = src_g.width
        if not src_g.contours or gname == ".notdef" or src_g.width == 0:
            for c in src_g.contours:
                c.draw(dst_g.getPen())
            continue
        pen = dst_g.getPen()
        for c in src_g.contours:
            xs = [pt.x for pt in c.points]
            ys = [pt.y for pt in c.points]
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            if tile_mode == "pixel":
                half = tile_size / 2.0
                add_rect(pen, cx - half, cy - half, cx + half, cy + half)
            elif tile_mode == "dotted":
                add_circle(pen, cx, cy, tile_size, clockwise=True)
            elif tile_mode == "diamond":
                add_poly(
                    pen,
                    [(cx, cy + tile_size), (cx + tile_size, cy), (cx, cy - tile_size), (cx - tile_size, cy)],
                    clockwise=True,
                )
    return dst


def set_ufo_metadata(
    ufo: ufoLib2.Font,
    pkg: dict,
    copyright_str: str,
    license_str: str,
    family_name: str = FAMILY,
    stem: str = STEM,
    cap_height: int = 762,
    x_height: int = 598,
    style_name: str = "Regular",
    weight_class: int = 400,
) -> None:
    raw_major, raw_minor = (int(x) for x in pkg["version"].split(".")[:2])
    major = max(1, raw_major)
    minor = raw_minor
    info = ufo.info
    info.familyName = family_name
    info.styleName = style_name
    info.styleMapFamilyName = family_name if style_name in ("Regular", "Bold") else f"{family_name} {style_name}"
    info.styleMapStyleName = "bold" if style_name == "Bold" else "regular"
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
    info.openTypeOS2WinAscent = 950
    info.openTypeOS2WinDescent = 250
    info.openTypeOS2WeightClass = weight_class
    info.openTypeOS2WidthClass = 5
    info.openTypeOS2Type = []
    info.openTypeOS2VendorID = "ASCX"
    info.openTypeOS2Selection = [7]
    info.postscriptUnderlinePosition = -100
    info.postscriptUnderlineThickness = 50
    info.postscriptIsFixedPitch = False

    ufo.features.text = """\
languagesystem DFLT dflt;
languagesystem latn dflt;
languagesystem latn CAT;

feature locl {
    script latn;
    language CAT;
    sub l periodcentered' l by periodcentered.loclCAT;
    sub L periodcentered' L by periodcentered.loclCAT.case;
    sub L periodcentered' l by periodcentered.loclCAT.case;
} locl;
"""


def postprocess_ttf(
    ttf: TTFont,
    pkg: dict,
    copyright_str: str,
    license_str: str,
    family_name: str = FAMILY,
    stem: str = STEM,
    cap_height: int = 762,
    x_height: int = 598,
    style_name: str = "Regular",
    weight_class: int = 400,
) -> None:
    raw_major, raw_minor = (int(x) for x in pkg["version"].split(".")[:2])
    major = max(1, raw_major)
    minor = raw_minor
    version_str = f"Version {major}.{minor:03d}"

    is_ttf = "glyf" in ttf
    if is_ttf:
        y_max = max((g.yMax for g in ttf["glyf"].glyphs.values() if hasattr(g, "yMax")), default=950)
        y_min = min((g.yMin for g in ttf["glyf"].glyphs.values() if hasattr(g, "yMin")), default=-250)
        ttf["head"].yMax = y_max
        ttf["head"].yMin = y_min
    else:
        y_max = getattr(ttf["head"], "yMax", 950)
        y_min = getattr(ttf["head"], "yMin", -250)
    ttf["head"].fontRevision = float(f"{major}.{minor:03d}")
    ttf["head"].macStyle = 1 if weight_class == 700 else 0

    asc = max(850, y_max)
    desc = min(-250, y_min)
    ttf["hhea"].ascent = asc
    ttf["hhea"].descent = desc
    ttf["hhea"].lineGap = 0

    os2 = ttf["OS/2"]
    os2.version = 4
    os2.sTypoAscender = asc
    os2.sTypoDescender = desc
    os2.sTypoLineGap = 0
    os2.usWinAscent = max(850, y_max)
    os2.usWinDescent = max(250, abs(y_min))
    os2.usWeightClass = weight_class
    os2.fsType = 0
    os2.fsSelection = 0x00A0 if weight_class == 700 else 0x00C0
    os2.achVendID = "ASCX"
    os2.sxHeight = x_height
    os2.sCapHeight = cap_height

    name_table = newTable("name")
    name_table.names = []
    records = {
        0: copyright_str,
        1: family_name if style_name in ("Regular", "Bold") else f"{family_name} {style_name}",
        2: "Bold" if style_name == "Bold" else "Regular",
        3: f"{stem}-{pkg['version']}",
        4: f"{family_name} {style_name}",
        5: version_str,
        6: stem,
        8: pkg["author"]["name"],
        9: pkg["author"]["name"],
        10: pkg["description"],
        13: license_str,
        14: "https://openfontlicense.org",
        19: "The quick brown fox jumps over the lazy dog. 0123456789",
    }
    if style_name not in ("Regular", "Bold"):
        records[16] = family_name
        records[17] = style_name
    for name_id, value in records.items():
        name_table.setName(value, name_id, 3, 1, 0x0409)
    ttf["name"] = name_table

    if is_ttf:
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


def compute_outline_glyph_deltas(
    glyf_glyph, delta_thin: float, delta_black: float
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]] | None:
    if not glyf_glyph.isComposite() and getattr(glyf_glyph, "numberOfContours", 0) > 0:
        coords = glyf_glyph.coordinates
        end_pts = glyf_glyph.endPtsOfContours
        thin_deltas: list[tuple[int, int]] = []
        black_deltas: list[tuple[int, int]] = []
        start = 0
        for end in end_pts:
            pts = [(coords[i][0], coords[i][1]) for i in range(start, end + 1)]
            m = len(pts)
            for i in range(m):
                px, py = pts[i]
                prev_x, prev_y = pts[(i - 1) % m]
                next_x, next_y = pts[(i + 1) % m]
                k = 1
                while k < m and abs(px - prev_x) < 1e-3 and abs(py - prev_y) < 1e-3:
                    prev_x, prev_y = pts[(i - k) % m]
                    k += 1
                k = 1
                while k < m and abs(next_x - px) < 1e-3 and abs(next_y - py) < 1e-3:
                    next_x, next_y = pts[(i + k) % m]
                    k += 1
                dx1, dy1 = px - prev_x, py - prev_y
                l1 = math.hypot(dx1, dy1) or 1.0
                n1x, n1y = -dy1 / l1, dx1 / l1

                dx2, dy2 = next_x - px, next_y - py
                l2 = math.hypot(dx2, dy2) or 1.0
                n2x, n2y = -dy2 / l2, dx2 / l2

                dot = max(-0.8, min(1.0, n1x * n2x + n1y * n2y))
                mx = (n1x + n2x) / (1.0 + dot)
                my = (n1y + n2y) / (1.0 + dot)
                ml = math.hypot(mx, my)
                if ml > 1.35:
                    mx = mx / ml * 1.35
                    my = my / ml * 1.35
                thin_deltas.append((round(mx * delta_thin), round(my * delta_thin)))
                black_deltas.append((round(mx * delta_black), round(my * delta_black)))
            start = end + 1
        thin_deltas.extend([(0, 0)] * 4)
        black_deltas.extend([(0, 0)] * 4)
        return thin_deltas, black_deltas
    return None


def compute_matrix_glyph_deltas(
    glyf_glyph, scale_thin: float, scale_black: float
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]] | None:
    if not glyf_glyph.isComposite() and getattr(glyf_glyph, "numberOfContours", 0) > 0:
        coords = glyf_glyph.coordinates
        end_pts = glyf_glyph.endPtsOfContours
        thin_deltas: list[tuple[int, int]] = []
        black_deltas: list[tuple[int, int]] = []
        start = 0
        for end in end_pts:
            pts = [(coords[i][0], coords[i][1]) for i in range(start, end + 1)]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx = (min(xs) + max(xs)) / 2.0
            cy = (min(ys) + max(ys)) / 2.0
            for px, py in pts:
                thin_deltas.append((round((px - cx) * (scale_thin - 1.0)), round((py - cy) * (scale_thin - 1.0))))
                black_deltas.append((round((px - cx) * (scale_black - 1.0)), round((py - cy) * (scale_black - 1.0))))
            start = end + 1
        thin_deltas.extend([(0, 0)] * 4)
        black_deltas.extend([(0, 0)] * 4)
        return thin_deltas, black_deltas
    return None


def save_variable_font_formats(
    base_ufo: ufoLib2.Font,
    pkg: dict,
    copyright_str: str,
    license_str: str,
    family_name: str,
    fam_prefix: str,
    cap_height: int,
    x_height: int,
    mode: str,
    t_mode: str | None,
    fonts_fam_dir: Path,
    dist_fam_dir: Path,
) -> tuple[Path, Path]:
    var_stem = f"{fam_prefix}-VariableFont_wght"
    var_ttf = ufo2ft.compileTTF(base_ufo, removeOverlaps=(mode == "outline"), reverseDirection=False, inplace=False)
    postprocess_ttf(
        var_ttf,
        pkg,
        copyright_str,
        license_str,
        family_name=family_name,
        stem=var_stem,
        cap_height=cap_height,
        x_height=x_height,
        style_name="Regular",
        weight_class=400,
    )

    fvar = newTable("fvar")
    axis = Axis()
    axis.axisTag = "wght"
    axis.minValue = 100.0
    axis.defaultValue = 400.0
    axis.maxValue = 900.0
    axis.axisNameID = var_ttf["name"].addName("Weight")
    fvar.axes = [axis]

    instances = [
        ("Thin", 100.0),
        ("ExtraLight", 200.0),
        ("Light", 300.0),
        ("Regular", 400.0),
        ("Medium", 500.0),
        ("SemiBold", 600.0),
        ("Bold", 700.0),
        ("ExtraBold", 800.0),
        ("Black", 900.0),
    ]
    for inst_name, w_val in instances:
        inst = NamedInstance()
        inst.subfamilyNameID = var_ttf["name"].addName(inst_name)
        inst.postscriptNameID = var_ttf["name"].addName(f"{fam_prefix}-{inst_name}")
        inst.coordinates = {"wght": w_val}
        fvar.instances.append(inst)
    var_ttf["fvar"] = fvar

    gvar = newTable("gvar")
    gvar.version = 1
    gvar.reserved = 0
    gvar.variations = {}
    glyf = var_ttf["glyf"]

    if mode == "outline":
        delta_thin, delta_black = -30.0, 25.0
    elif t_mode == "pixel":
        scale_thin, scale_black = 14.0 / 30.0, 36.0 / 30.0
    elif t_mode == "dotted":
        scale_thin, scale_black = 7.0 / 14.0, 17.4 / 14.0
    else:
        scale_thin, scale_black = 8.0 / 16.0, 20.0 / 16.0

    for gname in var_ttf.getGlyphOrder():
        if gname == ".notdef":
            gvar.variations[gname] = []
            continue
        g = glyf[gname]
        if mode == "outline":
            res = compute_outline_glyph_deltas(g, delta_thin, delta_black)
        else:
            res = compute_matrix_glyph_deltas(g, scale_thin, scale_black)
        if res:
            td, bd = res
            gvar.variations[gname] = [
                TupleVariation({"wght": (-1.0, -1.0, 0.0)}, td),
                TupleVariation({"wght": (0.0, 1.0, 1.0)}, bd),
            ]
        else:
            gvar.variations[gname] = []
    var_ttf["gvar"] = gvar

    buildStatTable(
        var_ttf,
        axes=[
            dict(
                tag="wght",
                name="Weight",
                values=[
                    dict(value=w_val, name=inst_name, flags=0x2 if w_val == 400.0 else 0)
                    for inst_name, w_val in instances
                ],
            )
        ],
    )

    fonts_var_dir = fonts_fam_dir / "variable"
    dist_var_dir = dist_fam_dir / "variable"
    fonts_var_dir.mkdir(parents=True, exist_ok=True)
    dist_var_dir.mkdir(parents=True, exist_ok=True)

    var_ttf_path = dist_var_dir / f"{var_stem}.ttf"
    var_woff2_path = dist_var_dir / f"{var_stem}.woff2"

    var_ttf.flavor = None
    var_ttf.save(var_ttf_path)
    shutil.copy2(var_ttf_path, fonts_var_dir / f"{var_stem}.ttf")

    var_ttf.flavor = "woff2"
    var_ttf.save(var_woff2_path)
    shutil.copy2(var_woff2_path, fonts_var_dir / f"{var_stem}.woff2")

    return var_ttf_path, var_woff2_path


def save_font_formats(
    ttf: TTFont,
    otf: TTFont,
    stem: str,
    fonts_fam_dir: Path,
    dist_fam_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    for base_d in (fonts_fam_dir, dist_fam_dir):
        for sub in ("otf", "ttf", "variable", "webfonts"):
            (base_d / sub).mkdir(parents=True, exist_ok=True)

    otf_path = dist_fam_dir / "otf" / f"{stem}.otf"
    ttf_path = dist_fam_dir / "ttf" / f"{stem}.ttf"
    woff_path = dist_fam_dir / "webfonts" / f"{stem}.woff"
    woff2_path = dist_fam_dir / "webfonts" / f"{stem}.woff2"

    otf.flavor = None
    otf.save(otf_path)
    shutil.copy2(otf_path, fonts_fam_dir / "otf" / f"{stem}.otf")

    ttf.flavor = None
    ttf.save(ttf_path)
    shutil.copy2(ttf_path, fonts_fam_dir / "ttf" / f"{stem}.ttf")

    ttf.flavor = "woff"
    ttf.save(woff_path)
    shutil.copy2(woff_path, fonts_fam_dir / "webfonts" / f"{stem}.woff")

    ttf.flavor = "woff2"
    ttf.save(woff2_path)
    shutil.copy2(woff2_path, fonts_fam_dir / "webfonts" / f"{stem}.woff2")

    return otf_path, ttf_path, woff_path, woff2_path


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

    # 1. Build Regular UFO & TTF/OTF from src/hangrygrotesk.svg + GF_Latin_Core
    ufo = ufoLib2.Font()
    build_svg_glyphs(ufo, ROOT / "src" / "hangrygrotesk.svg", sidebearing=60)
    build_gf_latin_core_glyphs(ufo, is_serif=False, sidebearing=60)
    set_ufo_metadata(ufo, pkg, copyright_str, license_str)

    ufo_path = sources_dir / "HangryGrotesk.ufo"
    if ufo_path.exists():
        shutil.rmtree(ufo_path)
    ufo.save(ufo_path, overwrite=True)

    ttf = ufo2ft.compileTTF(ufo, removeOverlaps=False, reverseDirection=False, inplace=False)
    postprocess_ttf(ttf, pkg, copyright_str, license_str)
    otf = ufo2ft.compileOTF(ufo, removeOverlaps=False, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE)
    postprocess_ttf(otf, pkg, copyright_str, license_str)

    # 2. Build Serif UFO & TTF/OTF from src/hangrygroteskserif.svg + GF_Latin_Core
    serif_ufo = ufoLib2.Font()
    build_svg_glyphs(serif_ufo, ROOT / "src" / "hangrygroteskserif.svg", sidebearing=60)
    build_gf_latin_core_glyphs(serif_ufo, is_serif=True, sidebearing=60)
    set_ufo_metadata(
        serif_ufo,
        pkg,
        copyright_str,
        license_str,
        family_name=SERIF_FAMILY,
        stem=SERIF_STEM,
        cap_height=762,
        x_height=598,
    )

    serif_ufo_path = sources_dir / "HangryGroteskSerif.ufo"
    if serif_ufo_path.exists():
        shutil.rmtree(serif_ufo_path)
    serif_ufo.save(serif_ufo_path, overwrite=True)

    serif_ttf = ufo2ft.compileTTF(serif_ufo, removeOverlaps=True, reverseDirection=False, inplace=False)
    postprocess_ttf(
        serif_ttf,
        pkg,
        copyright_str,
        license_str,
        family_name=SERIF_FAMILY,
        stem=SERIF_STEM,
        cap_height=762,
        x_height=598,
    )
    serif_otf = ufo2ft.compileOTF(
        serif_ufo, removeOverlaps=True, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE
    )
    postprocess_ttf(
        serif_otf,
        pkg,
        copyright_str,
        license_str,
        family_name=SERIF_FAMILY,
        stem=SERIF_STEM,
        cap_height=762,
        x_height=598,
    )

    # 3. Build Pixel UFO & TTF/OTF from src/hangrygroteskpixel.svg + 34u pixel-rasterized GF_Latin_Core
    pixel_ufo = ufoLib2.Font()
    build_svg_glyphs(pixel_ufo, ROOT / "src" / "hangrygroteskpixel.svg", sidebearing=68)
    rasterize_extra_glyphs_to_grid(ufo, pixel_ufo, tile_mode="pixel", sidebearing=68)
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
    pixel_otf = ufo2ft.compileOTF(
        pixel_ufo, removeOverlaps=False, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE
    )
    postprocess_ttf(
        pixel_otf,
        pkg,
        copyright_str,
        license_str,
        family_name=PIXEL_FAMILY,
        stem=PIXEL_STEM,
        cap_height=744,
        x_height=608,
    )

    # 4. Build Dotted UFO & TTF/OTF from src/hangrygroteskdotted.svg + 34u dot-rasterized GF_Latin_Core
    dotted_ufo = ufoLib2.Font()
    build_svg_glyphs(dotted_ufo, ROOT / "src" / "hangrygroteskdotted.svg", sidebearing=68)
    rasterize_extra_glyphs_to_grid(ufo, dotted_ufo, tile_mode="dotted", sidebearing=68)
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
    dotted_otf = ufo2ft.compileOTF(
        dotted_ufo, removeOverlaps=False, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE
    )
    postprocess_ttf(
        dotted_otf,
        pkg,
        copyright_str,
        license_str,
        family_name=DOTTED_FAMILY,
        stem=DOTTED_STEM,
        cap_height=742,
        x_height=606,
    )

    # 5. Build Diamond UFO & TTF/OTF from src/hangrygroteskdiamond.svg + 34u diamond-rasterized GF_Latin_Core
    diamond_ufo = ufoLib2.Font()
    build_svg_glyphs(diamond_ufo, ROOT / "src" / "hangrygroteskdiamond.svg", sidebearing=68)
    rasterize_extra_glyphs_to_grid(ufo, diamond_ufo, tile_mode="diamond", sidebearing=68)
    set_ufo_metadata(
        diamond_ufo,
        pkg,
        copyright_str,
        license_str,
        family_name=DIAMOND_FAMILY,
        stem=DIAMOND_STEM,
        cap_height=746,
        x_height=610,
    )

    diamond_ufo_path = sources_dir / "HangryGroteskDiamond.ufo"
    if diamond_ufo_path.exists():
        shutil.rmtree(diamond_ufo_path)
    diamond_ufo.save(diamond_ufo_path, overwrite=True)

    diamond_ttf = ufo2ft.compileTTF(
        diamond_ufo, removeOverlaps=False, reverseDirection=False, inplace=False
    )
    postprocess_ttf(
        diamond_ttf,
        pkg,
        copyright_str,
        license_str,
        family_name=DIAMOND_FAMILY,
        stem=DIAMOND_STEM,
        cap_height=746,
        x_height=610,
    )
    diamond_otf = ufo2ft.compileOTF(
        diamond_ufo, removeOverlaps=False, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE
    )
    postprocess_ttf(
        diamond_otf,
        pkg,
        copyright_str,
        license_str,
        family_name=DIAMOND_FAMILY,
        stem=DIAMOND_STEM,
        cap_height=746,
        x_height=610,
    )

    fonts_root = ROOT / "fonts"
    dist_fonts_dir = ROOT / "dist" / "fonts"
    if fonts_root.exists():
        shutil.rmtree(fonts_root)
    if dist_fonts_dir.exists():
        shutil.rmtree(dist_fonts_dir)
    fonts_root.mkdir(parents=True, exist_ok=True)
    dist_fonts_dir.mkdir(parents=True, exist_ok=True)

    otf_path, ttf_path, woff_path, woff2_path = save_font_formats(
        ttf, otf, STEM, fonts_root / "HangryGrotesk", dist_fonts_dir / "HangryGrotesk"
    )
    ser_otf_path, ser_ttf_path, ser_woff_path, ser_woff2_path = save_font_formats(
        serif_ttf, serif_otf, SERIF_STEM, fonts_root / "HangryGroteskSerif", dist_fonts_dir / "HangryGroteskSerif"
    )
    pix_otf_path, pix_ttf_path, pix_woff_path, pix_woff2_path = save_font_formats(
        pixel_ttf, pixel_otf, PIXEL_STEM, fonts_root / "HangryGroteskPixel", dist_fonts_dir / "HangryGroteskPixel"
    )
    dot_otf_path, dot_ttf_path, dot_woff_path, dot_woff2_path = save_font_formats(
        dotted_ttf, dotted_otf, DOTTED_STEM, fonts_root / "HangryGroteskDotted", dist_fonts_dir / "HangryGroteskDotted"
    )
    dia_otf_path, dia_ttf_path, dia_woff_path, dia_woff2_path = save_font_formats(
        diamond_ttf,
        diamond_otf,
        DIAMOND_STEM,
        fonts_root / "HangryGroteskDiamond",
        dist_fonts_dir / "HangryGroteskDiamond",
    )

    # 6. Build all 8 non-Regular weights (100–900: Thin, ExtraLight, Light, Medium, SemiBold, Bold, ExtraBold, Black) + Variable Fonts across all 5 families
    extra_weight_specs = [
        ("Thin", 100, -30.0, 14.0, 7.0, 8.0),
        ("ExtraLight", 200, -22.5, 18.0, 9.0, 10.0),
        ("Light", 300, -15.0, 24.0, 11.5, 13.0),
        ("Medium", 500, 7.0, 31.6, 15.0, 17.0),
        ("SemiBold", 600, 12.5, 32.8, 15.6, 17.8),
        ("Bold", 700, 17.5, 34.0, 16.2, 18.5),
        ("ExtraBold", 800, 21.5, 35.0, 16.8, 19.2),
        ("Black", 900, 25.0, 36.0, 17.4, 20.0),
    ]
    family_configs = [
        (FAMILY, "HangryGrotesk", ufo, 762, 598, "outline", None),
        (SERIF_FAMILY, "HangryGroteskSerif", serif_ufo, 762, 598, "outline", None),
        (PIXEL_FAMILY, "HangryGroteskPixel", pixel_ufo, 744, 608, "matrix", "pixel"),
        (DOTTED_FAMILY, "HangryGroteskDotted", dotted_ufo, 742, 606, "matrix", "dotted"),
        (DIAMOND_FAMILY, "HangryGroteskDiamond", diamond_ufo, 746, 610, "matrix", "diamond"),
    ]
    extra_saved_files: list[tuple[str, str, str, int, Path, Path, Path, Path]] = []
    variable_saved_files: list[tuple[str, str, Path, Path]] = []

    for fam_name, fam_prefix, base_u, cap_h, x_h, mode, t_mode in family_configs:
        f_fam_dir = fonts_root / fam_prefix
        d_fam_dir = dist_fonts_dir / fam_prefix
        var_ttf_p, var_woff2_p = save_variable_font_formats(
            base_u,
            pkg,
            copyright_str,
            license_str,
            family_name=fam_name,
            fam_prefix=fam_prefix,
            cap_height=cap_h,
            x_height=x_h,
            mode=mode,
            t_mode=t_mode,
            fonts_fam_dir=f_fam_dir,
            dist_fam_dir=d_fam_dir,
        )
        variable_saved_files.append((fam_name, fam_prefix, var_ttf_p, var_woff2_p))

        for w_name, w_num, d_upem, px_sz, dot_r, dia_r in extra_weight_specs:
            w_stem = f"{fam_prefix}-{w_name}"
            if mode == "outline":
                w_ufo = build_weighted_outline_ufo(base_u, d_upem)
            else:
                sz = px_sz if t_mode == "pixel" else (dot_r if t_mode == "dotted" else dia_r)
                w_ufo = build_weighted_matrix_ufo(base_u, t_mode, sz)
            set_ufo_metadata(
                w_ufo,
                pkg,
                copyright_str,
                license_str,
                family_name=fam_name,
                stem=w_stem,
                cap_height=cap_h,
                x_height=x_h,
                style_name=w_name,
                weight_class=w_num,
            )
            w_ttf = ufo2ft.compileTTF(
                w_ufo, removeOverlaps=False, reverseDirection=False, inplace=False
            )
            postprocess_ttf(
                w_ttf,
                pkg,
                copyright_str,
                license_str,
                family_name=fam_name,
                stem=w_stem,
                cap_height=cap_h,
                x_height=x_h,
                style_name=w_name,
                weight_class=w_num,
            )
            w_otf = ufo2ft.compileOTF(
                w_ufo, removeOverlaps=False, inplace=False, optimizeCFF=ufo2ft.CFFOptimization.NONE
            )
            postprocess_ttf(
                w_otf,
                pkg,
                copyright_str,
                license_str,
                family_name=fam_name,
                stem=w_stem,
                cap_height=cap_h,
                x_height=x_h,
                style_name=w_name,
                weight_class=w_num,
            )
            w_otf_p, w_ttf_p, w_woff_p, w_woff2_p = save_font_formats(
                w_ttf, w_otf, w_stem, f_fam_dir, d_fam_dir
            )
            extra_saved_files.append((fam_name, fam_prefix, w_stem, w_num, w_otf_p, w_ttf_p, w_woff_p, w_woff2_p))

    # Validate full Latin + Punctuation coverage across all styles
    expected_cps = {cp for g in ufo for cp in g.unicodes}
    for check_path in (ttf_path, ser_ttf_path, pix_ttf_path, dot_ttf_path, dia_ttf_path):
        reloaded = TTFont(check_path)
        cmap_cps = set(reloaded.getBestCmap().keys())
        missing = expected_cps - cmap_cps
        assert not missing, f"{check_path.name} missing codepoints: {[hex(c) for c in sorted(missing)]}"

    css_blocks = [
        f"/* {FAMILY}, {SERIF_FAMILY}, {PIXEL_FAMILY}, {DOTTED_FAMILY} & {DIAMOND_FAMILY} (100–900 + Variable) | {pkg['author']['name']} | {pkg['license']} */"
    ]
    for fam_n, fam_p, _, _ in variable_saved_files:
        css_blocks.append(
            f"""@font-face {{
  font-family: "{fam_n} Variable";
  src: url("./fonts/{fam_p}/variable/{fam_p}-VariableFont_wght.woff2") format("woff2-variations");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}}"""
        )
    all_css_faces = [
        (FAMILY, "HangryGrotesk", STEM, 400),
        (SERIF_FAMILY, "HangryGroteskSerif", SERIF_STEM, 400),
        (PIXEL_FAMILY, "HangryGroteskPixel", PIXEL_STEM, 400),
        (DOTTED_FAMILY, "HangryGroteskDotted", DOTTED_STEM, 400),
        (DIAMOND_FAMILY, "HangryGroteskDiamond", DIAMOND_STEM, 400),
        *((fam_n, fam_p, st_n, w_n) for fam_n, fam_p, st_n, w_n, _, _, _, _ in extra_saved_files),
    ]
    for fam_n, fam_p, st_n, w_n in all_css_faces:
        css_blocks.append(
            f"""@font-face {{
  font-family: "{fam_n}";
  src: url("./fonts/{fam_p}/webfonts/{st_n}.woff2") format("woff2"),
       url("./fonts/{fam_p}/webfonts/{st_n}.woff") format("woff");
  font-weight: {w_n};
  font-style: normal;
  font-display: swap;
}}"""
        )
    css_text = "\n\n".join(css_blocks) + "\n"
    (ROOT / "dist" / "hangrygrotesk.css").write_text(css_text, encoding="utf-8")
    shutil.copy2(ROOT / "src" / "preview.html", ROOT / "dist" / "preview.html")

    # Remove any old zip files in dist/
    for old_zip in (ROOT / "dist").glob("*.zip"):
        old_zip.unlink()

    date_time = (EPOCH.year, EPOCH.month, EPOCH.day, EPOCH.hour, EPOCH.minute, EPOCH.second)
    built_zips: list[Path] = []
    for fam_name, fam_prefix, _, _, _, _, _ in family_configs:
        fam_zip_path = ROOT / "dist" / f"{fam_prefix}-{pkg['version']}.zip"
        fam_dist_dir = dist_fonts_dir / fam_prefix

        fam_css_blocks = [
            f"/* {fam_name} (100–900 + Variable) | {pkg['author']['name']} | {pkg['license']} */",
            f"""@font-face {{
  font-family: "{fam_name} Variable";
  src: url("./variable/{fam_prefix}-VariableFont_wght.woff2") format("woff2-variations");
  font-weight: 100 900;
  font-style: normal;
  font-display: swap;
}}""",
        ]
        for f_n, f_p, st_n, w_n in all_css_faces:
            if f_p == fam_prefix:
                fam_css_blocks.append(
                    f"""@font-face {{
  font-family: "{f_n}";
  src: url("./webfonts/{st_n}.woff2") format("woff2"),
       url("./webfonts/{st_n}.woff") format("woff");
  font-weight: {w_n};
  font-style: normal;
  font-display: swap;
}}"""
                )
        fam_css_text = "\n\n".join(fam_css_blocks) + "\n"

        zip_entries: dict[str, bytes] = {
            f"{fam_prefix.lower()}.css": fam_css_text.encode("utf-8"),
            "README.md": (ROOT / "README.md").read_bytes(),
            "OFL.txt": ofl_path.read_bytes(),
        }
        for font_file in sorted(fam_dist_dir.rglob("*")):
            if font_file.is_file():
                rel_path = font_file.relative_to(fam_dist_dir).as_posix()
                zip_entries[rel_path] = font_file.read_bytes()

        with zipfile.ZipFile(fam_zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for arcname, data in zip_entries.items():
                info = zipfile.ZipInfo(filename=arcname, date_time=date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, data)
        built_zips.append(fam_zip_path)

    print(
        f"Built and validated all 5 families × 9 weights (OTF, TTF, Variable, Webfonts; {len(expected_cps)} codepoints each): {[z.name for z in built_zips]}"
    )


if __name__ == "__main__":
    main()
