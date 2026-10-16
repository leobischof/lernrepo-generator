"""Rewrite one of our SVGs so MuPDF draws it the way a browser does (PDF export only).

MuPDF (pymupdf), which places the figures in the PDFs, ignores three things that browsers,
Anki and the gist honour – measured with MuPDF 1.28:

- `stroke-dasharray`: dashed lines come out solid;
- markers (`marker-start/-mid/-end`): arrowheads simply vanish;
- `text-anchor` and `font-weight` set on a `<g>`: centred bold labels come out
  left-aligned and regular.

The SVG files stay plain standard SVG, written the natural way. On their way into the PDF
this module turns them into what MuPDF can draw: inherited text properties copied onto
every `<text>`/`<tspan>`, each dashed stroke as separate dash segments, each marker as a
transformed copy of its content. Bytes in, bytes out; nothing on disk changes.
"""
from __future__ import annotations

import copy
import math
import re
import xml.etree.ElementTree as ET

from .svg_blank import SVG_NS
from .svg_geometry import dash, ends, length, local, numbers, shape_polylines

# Properties the renderer must see on the element itself (CSS-inherited in a browser).
TEXT_PROPS = ("font-family", "font-size", "font-weight", "font-style", "text-anchor", "fill")
STROKE_PROPS = ("stroke", "stroke-width", "stroke-dasharray", "stroke-dashoffset", "stroke-linecap",
                "stroke-linejoin", "stroke-opacity", "marker-start", "marker-mid", "marker-end")
INHERITED = TEXT_PROPS + STROKE_PROPS
MARKERS = ("marker-start", "marker-mid", "marker-end")
# Subtrees that are not drawn where they stand (markers are copied in where used).
NOT_DRAWN = {"defs", "marker", "clipPath", "mask", "pattern", "symbol", "title", "desc", "style", "metadata"}
_URL = re.compile(r"url\(\s*#([^)\s]+)\s*\)")


def for_mupdf(svg: bytes) -> bytes:
    """The SVG with dashes, markers and inherited text properties spelled out."""
    root = ET.fromstring(svg)
    for el in root.iter():
        _expand_style(el)
    markers = {m.get("id"): m for m in root.iter(f"{{{SVG_NS}}}marker") if m.get("id")}
    _walk(root, _own({}, root), markers)
    return ET.tostring(root, encoding="utf-8")


def _expand_style(el: ET.Element) -> None:
    """style="a:b; c:d" → attributes (style wins, as in CSS), so inheritance can be traced."""
    style = el.attrib.pop("style", None)
    for decl in (style or "").split(";"):
        name, sep, value = decl.partition(":")
        if sep and name.strip():
            el.set(name.strip(), value.strip())


def _own(inherited: dict[str, str], el: ET.Element) -> dict[str, str]:
    return {**inherited, **{k: el.get(k) for k in INHERITED if el.get(k) is not None}}


def _walk(parent: ET.Element, ctx: dict[str, str], markers: dict[str, ET.Element]) -> None:
    for child in list(parent):
        tag = local(child.tag)
        if tag in NOT_DRAWN:
            continue
        if tag in ("text", "tspan"):
            for k in TEXT_PROPS:
                if child.get(k) is None and ctx.get(k) is not None:
                    child.set(k, ctx[k])
        style = _own(ctx, child)
        added = _redraw_shape(child, style, markers)
        at = list(parent).index(child) + 1
        for k, el in enumerate(added):
            parent.insert(at + k, el)
        _walk(child, style, markers)


def _redraw_shape(el: ET.Element, style: dict[str, str], markers: dict[str, ET.Element]) -> list[ET.Element]:
    """Elements to draw after `el`: its dashes and its markers (and `el` loses both)."""
    wanted = [m for m in MARKERS if _URL.search(style.get(m) or "")]
    dashes = numbers(style.get("stroke-dasharray")) if _stroked(style) else []
    if not (wanted or any(dashes)):
        return []
    outline = shape_polylines(el)
    if not outline:
        return []
    added = []
    if any(dashes):
        added.append(_dash_path(el, style, outline, dashes))
        el.set("stroke", "none")                  # the dashes replace the (solid) stroke
    for name in wanted:
        marker = markers.get(_URL.search(style[name]).group(1))
        if marker is not None:
            added += _marker_copies(el, style, outline, name, marker)
        el.set(name, "none")
    return added


def _stroked(style: dict[str, str]) -> bool:
    return (style.get("stroke") or "none") != "none"


def _dash_path(el: ET.Element, style: dict[str, str], outline, pattern: list[float]) -> ET.Element:
    offset = length(style.get("stroke-dashoffset"))
    pieces = [p for points, closed in outline for p in dash(points, closed, pattern, offset)]
    d = " ".join("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in piece) for piece in pieces)
    attrs = {"d": d, "fill": "none"}
    attrs.update({k: style[k] for k in ("stroke", "stroke-width", "stroke-linecap", "stroke-opacity") if k in style})
    if el.get("transform"):
        attrs["transform"] = el.get("transform")
    return ET.Element(f"{{{SVG_NS}}}path", attrs)


def _marker_copies(el: ET.Element, style: dict[str, str], outline, name: str, marker: ET.Element) -> list[ET.Element]:
    """The marker's content placed at the start/end (or every inner vertex) of the outline."""
    if name == "marker-mid":
        spots = _inner_vertices(outline)
    else:
        found = ends(outline)
        if not found:
            return []
        (start, a0), (end, a1) = found
        spots = [(start, a0, True)] if name == "marker-start" else [(end, a1, False)]
    width = length(marker.get("markerWidth"), 3.0)
    height = length(marker.get("markerHeight"), 3.0)
    box = numbers(marker.get("viewBox"))
    zoom = min(width / box[2], height / box[3]) if len(box) == 4 and box[2] and box[3] else 1.0
    if (marker.get("markerUnits") or "strokeWidth") == "strokeWidth":
        zoom *= length(style.get("stroke-width"), 1.0)
    ref_x, ref_y = length(marker.get("refX")), length(marker.get("refY"))
    orient = (marker.get("orient") or "0").strip()
    out = []
    for (x, y), angle, at_start in spots:
        if orient == "auto-start-reverse" and at_start:
            angle += 180
        elif not orient.startswith("auto"):
            angle = length(orient)
        place = (f"translate({x:.2f} {y:.2f}) rotate({angle:.2f}) scale({zoom:.4f}) "
                 f"translate({-ref_x:.2f} {-ref_y:.2f})")
        if el.get("transform"):
            place = f"{el.get('transform')} {place}"
        group = ET.Element(f"{{{SVG_NS}}}g", {"transform": place})
        group.extend(copy.deepcopy(list(marker)))
        _walk(group, _own({}, marker), {})        # marker content may itself use dashes/g-inherited text
        out.append(group)
    return out


def _inner_vertices(outline) -> list[tuple[tuple[float, float], float, bool]]:
    """Every vertex but the first and last, with the direction of the incoming segment."""
    points = [p for line, _ in outline for p in line]
    return [(b, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), False)
            for a, b in zip(points[:-2], points[1:-1]) if a != b]
