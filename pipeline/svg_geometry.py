"""Plain SVG geometry: a shape as polylines, and a polyline cut into dashes.

Used by svg_mupdf, which redraws dashed strokes and markers for a renderer that ignores
them. Curves and arcs are flattened into short straight pieces – fine for dashes and for
the direction of an arrowhead, both of which only need the outline approximately.
No renderer, no font metrics: attributes in, coordinates out.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET

Point = tuple[float, float]
Polyline = tuple[list[Point], bool]          # points, closed?

CURVE_STEPS = 16                             # straight pieces per Bézier segment
ELLIPSE_STEPS = 96                           # straight pieces for a full circle/ellipse
_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}


def local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def numbers(text: str | None) -> list[float]:
    """Every number in an attribute such as points="…", viewBox="…" or a dash list."""
    return [float(n) for n in _NUMBER.findall(text or "")]


def length(text: str | None, default: float = 0.0) -> float:
    """A plain or px length; anything else (%, em) falls back to the default."""
    found = numbers(text) if text and not text.strip().endswith(("%", "em")) else []
    return found[0] if found else default


def shape_polylines(el: ET.Element) -> list[Polyline] | None:
    """The outline of a basic shape or path; None for anything that is not a shape."""
    tag = local(el.tag)
    if tag == "line":
        return [([(length(el.get("x1")), length(el.get("y1"))),
                  (length(el.get("x2")), length(el.get("y2")))], False)]
    if tag in ("polyline", "polygon"):
        v = numbers(el.get("points"))
        return [(list(zip(v[0::2], v[1::2])), tag == "polygon")]
    if tag == "rect":
        x, y = length(el.get("x")), length(el.get("y"))
        w, h = length(el.get("width")), length(el.get("height"))
        return [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True)]
    if tag in ("circle", "ellipse"):
        cx, cy = length(el.get("cx")), length(el.get("cy"))
        rx = length(el.get("r") if tag == "circle" else el.get("rx"))
        ry = length(el.get("r") if tag == "circle" else el.get("ry"))
        steps = [2 * math.pi * k / ELLIPSE_STEPS for k in range(ELLIPSE_STEPS)]
        return [([(cx + rx * math.cos(t), cy + ry * math.sin(t)) for t in steps], True)]
    if tag == "path":
        return parse_path(el.get("d") or "")
    return None


def _cubic(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    out = []
    for k in range(1, CURVE_STEPS + 1):
        t = k / CURVE_STEPS
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _quadratic(p0: Point, p1: Point, p2: Point) -> list[Point]:
    """A quadratic Bézier is the cubic with control points 2/3 of the way to p1."""
    c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
    return _cubic(p0, c1, c2, p2)


def _angle(ux: float, uy: float, vx: float, vy: float) -> float:
    return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)


def _arc(p0: Point, rx: float, ry: float, rotation: float, large: bool, sweep: bool, p1: Point) -> list[Point]:
    """Elliptical arc via the endpoint-to-centre conversion of the SVG spec (appendix B.2.4)."""
    if p0 == p1:
        return []
    rx, ry = abs(rx), abs(ry)
    if not rx or not ry:
        return [p1]
    phi = math.radians(rotation)
    cos, sin = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cos * dx + sin * dy, -sin * dx + cos * dy
    scale = x1 ** 2 / rx ** 2 + y1 ** 2 / ry ** 2
    if scale > 1:                                # radii too small: grow them, as browsers do
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1 ** 2 - ry ** 2 * x1 ** 2
    den = rx ** 2 * y1 ** 2 + ry ** 2 * x1 ** 2
    coef = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cxp, cyp = coef * rx * y1 / ry, -coef * ry * x1 / rx
    cx = cos * cxp - sin * cyp + (p0[0] + p1[0]) / 2
    cy = sin * cxp + cos * cyp + (p0[1] + p1[1]) / 2
    start = _angle(1, 0, (x1 - cxp) / rx, (y1 - cyp) / ry)
    delta = _angle((x1 - cxp) / rx, (y1 - cyp) / ry, (-x1 - cxp) / rx, (-y1 - cyp) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    n = max(4, int(abs(delta) / (math.pi / 24)))
    out = []
    for k in range(1, n + 1):
        t = start + delta * k / n
        out.append((cx + rx * math.cos(t) * cos - ry * math.sin(t) * sin,
                    cy + rx * math.cos(t) * sin + ry * math.sin(t) * cos))
    return out


def parse_path(d: str) -> list[Polyline]:
    """Path data → one polyline per subpath. Stops quietly at malformed data."""
    tokens = _TOKEN.findall(d)
    subpaths: list[Polyline] = []
    points: list[Point] = []
    cur = start = (0.0, 0.0)
    ctrl: Point | None = None                    # last control point, for S/T reflection
    cmd, i = None, 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd, i = tokens[i], i + 1
        if cmd is None:
            break
        kind, rel = cmd.upper(), cmd.islower()
        if kind == "Z":
            if points:
                subpaths.append((points, True))
            points, cur, ctrl, cmd = [], start, None, None
            continue
        args = tokens[i:i + _ARGS[kind]]
        if len(args) < _ARGS[kind] or any(a.isalpha() for a in args):
            break
        v = [float(a) for a in args]
        i += _ARGS[kind]
        ox, oy = cur if rel else (0.0, 0.0)
        if kind == "M":
            if len(points) > 1:
                subpaths.append((points, False))
            cur = start = (ox + v[0], oy + v[1])
            points, ctrl, cmd = [cur], None, ("l" if rel else "L")
            continue
        if not points:
            points = [cur]
        if kind == "H":
            end, piece, ctrl = ((cur[0] if rel else 0.0) + v[0], cur[1]), None, None
        elif kind == "V":
            end, piece, ctrl = (cur[0], (cur[1] if rel else 0.0) + v[0]), None, None
        elif kind == "L":
            end, piece, ctrl = (ox + v[0], oy + v[1]), None, None
        elif kind in "CS":
            p1 = (ox + v[0], oy + v[1]) if kind == "C" else (
                (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur)
            p2, end = (ox + v[-4], oy + v[-3]), (ox + v[-2], oy + v[-1])
            piece, ctrl = _cubic(cur, p1, p2, end), p2
        elif kind in "QT":
            p1 = (ox + v[0], oy + v[1]) if kind == "Q" else (
                (2 * cur[0] - ctrl[0], 2 * cur[1] - ctrl[1]) if ctrl else cur)
            end = (ox + v[-2], oy + v[-1])
            piece, ctrl = _quadratic(cur, p1, end), p1
        else:                                    # A
            end = (ox + v[5], oy + v[6])
            piece, ctrl = _arc(cur, v[0], v[1], v[2], bool(v[3]), bool(v[4]), end), None
        points += piece if piece is not None else [end]
        cur = end
    if len(points) > 1:
        subpaths.append((points, False))
    return subpaths


def dash(points: list[Point], closed: bool, pattern: list[float], offset: float = 0.0) -> list[list[Point]]:
    """Cut a polyline into the visible pieces of a dash pattern (stroke-dasharray semantics)."""
    pattern = [p for p in pattern if p >= 0]
    if len(pattern) % 2:
        pattern *= 2
    if not pattern or sum(pattern) <= 0 or len(points) < 2:
        return [points + points[:1]] if closed else [points]
    path = points + points[:1] if closed else points
    idx, pos = 0, offset % sum(pattern)
    while pos >= pattern[idx]:
        pos -= pattern[idx]
        idx = (idx + 1) % len(pattern)
    remaining, on = pattern[idx] - pos, idx % 2 == 0
    pieces: list[list[Point]] = []
    current = [path[0]] if on else []
    for a, b in zip(path, path[1:]):
        seg = math.dist(a, b)
        done = 0.0
        while seg - done > remaining:
            done += remaining
            p = (a[0] + (b[0] - a[0]) * done / seg, a[1] + (b[1] - a[1]) * done / seg)
            if on:
                pieces.append(current + [p])
            current = [] if on else [p]
            on, idx = not on, (idx + 1) % len(pattern)
            remaining = pattern[idx]
        remaining -= seg - done
        if on:
            current.append(b)
    if on and len(current) > 1:
        pieces.append(current)
    return pieces


def ends(polylines: list[Polyline]) -> tuple[tuple[Point, float], tuple[Point, float]] | None:
    """(start point, direction in degrees), (end point, direction) of a shape's outline."""
    pts = [p for line, closed in polylines for p in (line + line[:1] if closed else line)]
    distinct = [p for k, p in enumerate(pts) if k == 0 or p != pts[k - 1]]
    if len(distinct) < 2:
        return None
    (a, b), (y, z) = distinct[:2], distinct[-2:]
    return ((a, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))),
            (z, math.degrees(math.atan2(z[1] - y[1], z[0] - y[0]))))
