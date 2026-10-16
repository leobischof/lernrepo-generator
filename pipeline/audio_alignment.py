"""Local lexical alignment, generalized from the reference implementation."""
import math
import re
from collections import Counter
from pathlib import Path

STOP = set("aber alle als also am an auch auf aus bei bis das dass dem den der des die doch ein eine einem einen einer eines er es fuer für hat hier ich im in ist ja kann man mit nach nicht noch nur oder schon sehr sich sie sind so um und uns vom von vor war was wenn werden wie wir wird wo zu zum zur über".split())

def words(text: str) -> Counter:
    return Counter(w for w in re.findall(r"[a-zäöüß]{3,}", text.lower()) if w not in STOP)

def align(segments: list[dict], blocks: list[dict], threshold: float = .16) -> list[dict]:
    """Independent windows: allows audio to change topic out of PDF order. Low scores omitted."""
    counts = [words(b["text"]) for b in blocks]
    df = Counter(w for c in counts for w in c)
    idf = {w: math.log((len(blocks) + 1) / (f + 1)) + 1 for w, f in df.items()}

    def vector(text_counts):
        raw = {w: (1 + math.log(c)) * idf[w] for w, c in text_counts.items() if w in idf}
        norm = math.sqrt(sum(v*v for v in raw.values())) or 1
        return {w: v / norm for w, v in raw.items()}

    vectors = [vector(c) for c in counts]
    windows = []
    for seg in segments:
        if not windows or seg["start"] - windows[-1]["start"] >= 18:
            windows.append(dict(start=seg["start"], end=seg["end"], text=seg["text"]))
        else:
            windows[-1]["end"] = seg["end"]
            windows[-1]["text"] += " " + seg["text"]
    annotations = []
    for window in windows:
        query = words(window["text"])
        v = vector(query)
        candidates = [(sum(v.get(w, 0)*value for w, value in bv.items()), i)
                      for i, bv in enumerate(vectors) if len(query.keys() & counts[i].keys()) >= 3]
        if not candidates:
            continue
        score, i = max(candidates)
        if score < threshold:
            continue
        b = blocks[i]
        # A caption alone is too small to explain a figure: use its curated/rendered bounds when available.
        annotations.append(dict(id=f"auto-{len(annotations)+1}", start=round(window["start"], 3),
                                end=round(window["end"], 3), page=b["page"], type="rect",
                                rect=b["rect"], pointer=True, label=b["text"][:110].strip(),
                                transcript=window["text"].strip(), target_text=b["text"][:500],
                                confidence=round(score, 3), status="unreviewed", origin="local-asr-lexical"))
    return annotations

def pdf_blocks(path: Path) -> list[dict]:
    import pymupdf
    result = []
    with pymupdf.open(path) as doc:
        for n, page in enumerate(doc, 1):
            width, height = page.rect.width, page.rect.height
            text_blocks = page.get_text("blocks")
            images = [r for image in page.get_images(full=True) for r in page.get_image_rects(image[0])]
            for x0, y0, x1, y1, text, _, kind in text_blocks:
                if kind != 0 or len(words(text)) < 4 or y0 < height*.06 or y0 > height*.92:
                    continue
                if re.search(r"Abbildung\s+\d+", text):
                    above = [r for r in images if 0 <= y0-r.y1 < height*.1]
                    if above:
                        r = max(above, key=lambda r: r.y1)
                        x0, y0, x1, y1 = min(x0,r.x0), min(y0,r.y0), max(x1,r.x1), max(y1,r.y1)
                result.append(dict(page=n, text=text, rect=[max(0,x0/width), max(0,y0/height),
                                                           min(1,(x1-x0)/width), min(1,(y1-y0)/height)]))
    return result
