"""Turn a reconstruction SVG into a blank drawing exercise.

Every element whose class list contains `answer` is what a learner must
reproduce in the exam, so it is removed. Where such an element carried text,
a dashed placeholder rectangle of roughly the text's extent takes its place:
the learner still sees *where* something belongs and how much, never *what*.
Shapes marked as answers (e.g. a curve) disappear without a placeholder.

Text extents are estimated from attributes only (font size, character count,
anchor, tspan line offsets) - no font metrics, no renderer - which keeps the
stage deterministic and dependency-free. The estimate errs on the large side.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

SVG_NS = "http://www.w3.org/2000/svg"
_NS = {"": SVG_NS, "xlink": "http://www.w3.org/1999/xlink"}
for _prefix, _uri in _NS.items():
    ET.register_namespace(_prefix, _uri)

ANSWER = "answer"
DEFAULT_FONT_SIZE = 16.0
# Average advance width per character as a fraction of the font size (Arial-like).
WIDTH_FACTOR = {"normal": 0.55, "bold": 0.6}
ASCENT, DESCENT = 0.8, 0.25        # line box around the baseline, in em
PAD = 4.0                          # px of air around each placeholder
PLACEHOLDER_STYLE = {
    "fill": "#ffffff", "fill-opacity": "0.9", "stroke": "#888888",
    "stroke-width": "1.5", "stroke-dasharray": "6 4", "rx": "3",
}
_NUMBER = re.compile(r"^\s*(-?[\d.]+)\s*(px|em)?\s*$")


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def union(self, other: "Box") -> "Box":
        return Box(min(self.x0, other.x0), min(self.y0, other.y0),
                   max(self.x1, other.x1), max(self.y1, other.y1))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def is_answer(el: ET.Element) -> bool:
    return ANSWER in (el.get("class") or "").split()


def _length(value: str | None, font_size: float) -> float | None:
    """Parse an SVG length (plain, px or em); None when absent or unsupported."""
    if value is None:
        return None
    m = _NUMBER.match(value)
    if not m:
        return None
    number = float(m.group(1))
    return number * font_size if m.group(2) == "em" else number


class Inherited:
    """Resolves presentation attributes the way SVG inheritance does (nearest ancestor wins)."""

    def __init__(self, root: ET.Element):
        self.parent = {child: parent for parent in root.iter() for child in parent}

    def get(self, el: ET.Element, name: str, default: str | None = None) -> str | None:
        node = el
        while node is not None:
            if node.get(name) is not None:
                return node.get(name)
            node = self.parent.get(node)
        return default

    def font_size(self, el: ET.Element) -> float:
        node = el
        while node is not None:
            size = _length(node.get("font-size"), DEFAULT_FONT_SIZE)
            if size:
                return size
            node = self.parent.get(node)
        return DEFAULT_FONT_SIZE


def _lines(text_el: ET.Element, inh: Inherited) -> list[tuple[str, float, float, ET.Element]]:
    """(content, x, baseline y, element carrying the style) per visual line of a <text>."""
    size = inh.font_size(text_el)
    x = _length(text_el.get("x"), size) or 0.0
    y = (_length(text_el.get("y"), size) or 0.0) + (_length(text_el.get("dy"), size) or 0.0)
    lines = []
    if (text_el.text or "").strip():
        lines.append([text_el.text.strip(), x, y, text_el])
    for span in text_el:
        if _local(span.tag) != "tspan":
            continue
        span_size = inh.font_size(span)
        new_x = _length(span.get("x"), span_size)
        new_y = _length(span.get("y"), span_size)
        dy = _length(span.get("dy"), span_size) or 0.0
        content = "".join(span.itertext()).strip()
        starts_line = new_x is not None or new_y is not None or dy or not lines
        x = new_x if new_x is not None else x
        y = (new_y if new_y is not None else y) + dy
        if starts_line:
            lines.append([content, x, y, span])
        else:                       # inline continuation of the previous line
            lines[-1][0] += " " + content
    return [tuple(line) for line in lines if line[0]]


def text_box(text_el: ET.Element, inh: Inherited) -> Box | None:
    """Estimated bounding box of a <text> in its own user space, None when empty."""
    box = None
    for content, x, y, styled in _lines(text_el, inh):
        size = inh.font_size(styled)
        weight = "bold" if inh.get(styled, "font-weight", "normal") in ("bold", "700", "800", "900") else "normal"
        width = len(content) * size * WIDTH_FACTOR[weight]
        anchor = inh.get(styled, "text-anchor", "start")
        x0 = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
        baseline = inh.get(styled, "dominant-baseline", "auto")
        shift = 0.35 * size if baseline in ("middle", "central") else 0.0
        line = Box(x0, y + shift - ASCENT * size, x0 + width, y + shift + DESCENT * size)
        box = line if box is None else box.union(line)
    return box


def _transform_chain(answer: ET.Element, text_el: ET.Element, inh: Inherited) -> str:
    """Transforms from the answer element down to the text (inclusive), outermost first."""
    chain = []
    node = text_el
    while node is not None:
        if node.get("transform"):
            chain.append(node.get("transform"))
        if node is answer:
            break
        node = inh.parent.get(node)
    return " ".join(reversed(chain))


def placeholders(answer: ET.Element, inh: Inherited) -> list[ET.Element]:
    """One dashed rectangle per <text> inside (or being) the answer element."""
    out = []
    for text_el in answer.iter(f"{{{SVG_NS}}}text"):
        box = text_box(text_el, inh)
        if box is None:
            continue
        attrs = {"class": "placeholder",
                 "x": f"{box.x0 - PAD:.1f}", "y": f"{box.y0 - PAD:.1f}",
                 "width": f"{box.x1 - box.x0 + 2 * PAD:.1f}",
                 "height": f"{box.y1 - box.y0 + 2 * PAD:.1f}", **PLACEHOLDER_STYLE}
        transform = _transform_chain(answer, text_el, inh)
        if transform:
            attrs["transform"] = transform
        out.append(ET.Element(f"{{{SVG_NS}}}rect", attrs))
    return out


def _replace(parent: ET.Element, answer: ET.Element, new: list[ET.Element]) -> None:
    """Swap `answer` for `new` in place, keeping the source's indentation intact."""
    index = list(parent).index(answer)
    for el in new:
        el.tail = answer.tail
    if not new and index == len(parent) - 1 and index > 0:
        parent[index - 1].tail = answer.tail     # closing tag keeps its indentation
    parent.remove(answer)
    for offset, el in enumerate(new):
        parent.insert(index + offset, el)


def _relabel(root: ET.Element, removed: int) -> None:
    """Mark the document as exercise and replace the description (it may name answers)."""
    root.set("data-exercise", "blank")
    title = root.find(f"{{{SVG_NS}}}title")
    if title is not None and title.text:
        title.text = f"{title.text.strip()} – Zeichenübung (leer)"
    desc = root.find(f"{{{SVG_NS}}}desc")
    if desc is not None:
        desc.text = (f"Leere Zeichenübung: {removed} Lösungselemente entfernt; gestrichelte "
                     "Kästen markieren, wo Text hingehört.")


def blank_svg(svg_text: str) -> tuple[str, int]:
    """Return (blank SVG text, number of removed answer elements)."""
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    root = ET.fromstring(svg_text, parser=parser)
    inh = Inherited(root)
    # Outermost answers only: a nested answer goes away with its ancestor.
    answers = [el for el in root.iter() if is_answer(el)
               and not any(is_answer(a) for a in _ancestors(el, inh))]
    for answer in answers:
        _replace(inh.parent[answer], answer, placeholders(answer, inh))
    _relabel(root, len(answers))
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n", len(answers)


def _ancestors(el: ET.Element, inh: Inherited):
    node = inh.parent.get(el)
    while node is not None:
        yield node
        node = inh.parent.get(node)
