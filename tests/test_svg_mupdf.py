"""The PDF stage's SVG rewrite: dashes, markers and <g>-inherited text properties for MuPDF."""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

import pytest

from pipeline.svg_blank import SVG_NS
from pipeline.svg_geometry import dash, ends, parse_path
from pipeline.svg_mupdf import for_mupdf

N = f"{{{SVG_NS}}}"


def _svg(body: str) -> bytes:
    return (f'<svg xmlns="{SVG_NS}" viewBox="0 0 200 100" width="200" height="100">'
            f'<defs><marker id="tip" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="4" markerHeight="4" '
            f'orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#000"/></marker></defs>{body}</svg>').encode()


def _root(svg: bytes) -> ET.Element:
    return ET.fromstring(for_mupdf(svg))


def test_dash_cuts_line_into_pattern():
    pieces = dash([(0, 0), (100, 0)], False, [10, 5])
    assert len(pieces) == 7                                  # 0-10, 15-25, … 90-100
    assert pieces[0] == [(0, 0), (10.0, 0.0)]
    assert pieces[1][0] == (15.0, 0.0)
    assert pieces[-1][-1] == (100, 0)


def test_dash_odd_pattern_repeats_and_closed_shape_returns_to_start():
    pieces = dash([(0, 0), (10, 0), (10, 10), (0, 10)], True, [5])
    lengths = [sum(math.dist(a, b) for a, b in zip(p, p[1:])) for p in pieces]
    assert len(pieces) == 4 and all(abs(x - 5) < 1e-9 for x in lengths)


def test_path_parser_handles_relative_curves_arcs_and_close():
    (line, closed), = parse_path("M10 10 h20 v20 c0 5 -5 10 -10 10 a10 10 0 0 1 -10 -10 z")
    assert closed and line[0] == (10, 10)
    assert line[1] == (30, 10) and line[2] == (30, 30)
    assert math.isclose(line[-1][0], 10, abs_tol=1e-6) and math.isclose(line[-1][1], 30, abs_tol=1e-6)


def test_ends_give_direction_of_last_segment():
    (start, a0), (end, a1) = ends([([(0, 0), (10, 0), (10, 10)], False)])
    assert start == (0, 0) and a0 == 0 and end == (10, 10) and a1 == 90


def test_dashed_stroke_becomes_segments_and_original_loses_stroke():
    root = _root(_svg('<line x1="0" y1="50" x2="100" y2="50" stroke="#000" stroke-dasharray="10 10"/>'))
    line, dashes = root.findall(f"{N}line")[0], root.findall(f"{N}path")[-1]
    assert line.get("stroke") == "none"
    assert dashes.get("d").count("M") == 5 and dashes.get("stroke") == "#000"


def test_inherited_dash_from_group_style_attribute():
    root = _root(_svg('<g style="stroke:#333;stroke-dasharray:4 4"><rect x="0" y="0" width="40" height="20"/></g>'))
    g = root.find(f"{N}g")
    assert g.find(f"{N}rect").get("stroke") == "none"
    assert g.find(f"{N}path").get("d").count("M") > 10


def test_marker_end_becomes_rotated_copy_at_line_end():
    root = _root(_svg('<line x1="0" y1="0" x2="0" y2="80" stroke="#000" stroke-width="2" marker-end="url(#tip)"/>'))
    line = root.find(f"{N}line")
    tip = root.find(f"{N}g")
    assert line.get("marker-end") == "none"
    assert tip.get("transform").startswith("translate(0.00 80.00) rotate(90.00) scale(0.8000)")
    assert tip.find(f"{N}path") is not None


def test_text_gets_anchor_and_weight_from_group():
    root = _root(_svg('<g text-anchor="middle" font-weight="bold" font-size="12">'
                      '<text x="50" y="50">A<tspan x="50" dy="14">B</tspan></text></g>'))
    text = root.find(f"{N}g/{N}text")
    assert (text.get("text-anchor"), text.get("font-weight"), text.get("font-size")) == ("middle", "bold", "12")
    assert text.find(f"{N}tspan").get("text-anchor") == "middle"


def test_plain_svg_is_unchanged_in_substance():
    root = _root(_svg('<rect x="1" y="1" width="10" height="10" stroke="#000" fill="none"/>'))
    rect = root.find(f"{N}rect")
    assert rect.get("stroke") == "#000" and root.find(f"{N}path") is None


def test_mupdf_draws_the_dashes():
    pymupdf = pytest.importorskip("pymupdf")
    svg = _svg('<rect width="200" height="100" fill="#fff"/>'
               '<line x1="0" y1="50" x2="200" y2="50" stroke="#000" stroke-width="4" stroke-dasharray="20 20"/>')
    with pymupdf.open("svg", for_mupdf(svg)) as doc:
        pix = doc[0].get_pixmap(alpha=False)
    row = [pix.pixel(x, 50)[0] for x in range(5, 195, 10)]
    assert any(v < 64 for v in row) and any(v > 192 for v in row)   # dark dashes and white gaps
