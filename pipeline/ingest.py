"""Local source import. PDF extraction is deliberately not called cleaned text."""
import shutil
from .io import file_hash, identifier, read, write

KINDS = {"script", "exam", "exam-collection", "exercises", "flashcards", "summary"}
TRUST = {"primary", "student-transcript", "student-recollection", "unverified-student"}


def extract(path, spec):
    if path.suffix.lower() == ".pdf":
        import pymupdf
        with pymupdf.open(path) as doc:
            pages = []
            for i, page in enumerate(doc, 1):
                text = page.get_text(sort=True)
                method = "pdf-text"
                if not text.strip() and spec.get("ocr", False):
                    text = page.get_text(textpage=page.get_textpage_ocr(language=spec.get("ocr_language", "deu+eng")))
                    method = "tesseract"
                # Annotation candidates require visual confirmation: never exclude automatically.
                strikeouts = [list(a.rect) for a in (page.annots() or []) if a.type[1] == "StrikeOut"]
                pages.append(dict(pdf_page=i, text=text, extraction=method,
                                  needs_review=not bool(text.strip()), strikeout_candidates=strikeouts))
            return pages
    if path.suffix.lower() == ".apkg":
        from .apkg_reader import read as read_anki
        notes, decks = read_anki(path)
        return [dict(pdf_page=i, text="\n".join(note.fields), extraction="anki-import",
                     needs_review=True, note_id=note.note_id, decks=decks)
                for i, note in enumerate(notes, 1)]
    if path.suffix.lower() in {".md", ".txt", ".tex", ".csv", ".tsv"}:
        return [dict(pdf_page=i, text=text, extraction="text", needs_review=False)
                for i, text in enumerate(path.read_text(encoding="utf-8-sig").split("\f"), 1)]
    raise ValueError(f"Nicht unterstütztes Eingabeformat: {path.suffix}; DOCX vorerst als PDF exportieren")


def run(course):
    old = read(course.path("manifest"), {"sources": {}})
    manifest = {"sources": {}}
    for spec in course.data["sources"]:
        sid = identifier(spec["id"])
        if sid in manifest["sources"]:
            raise ValueError(f"Doppelte Quellen-ID: {sid}")
        if spec["kind"] not in KINDS or spec["trust"] not in TRUST:
            raise ValueError(f"Ungültige Art/Vertrauensstufe: {sid}")
        source = course.local(spec["path"])
        if not source.is_file():
            raise ValueError(f"Quelle fehlt: {source}")
        fingerprint = file_hash(source)
        dest = course.path("originals") / (sid + source.suffix.lower())
        if source != dest and (not dest.exists() or file_hash(dest) != fingerprint):
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        text_path = course.path("extracted") / f"{sid}-pages.json"
        previous = old["sources"].get(sid, {})
        if previous.get("sha256") == fingerprint and previous.get("spec") == spec and text_path.exists():
            pages = read(text_path)
        else:
            pages = extract(dest, spec)
            write(text_path, pages)
        manifest["sources"][sid] = dict(sha256=fingerprint, extraction_sha256=file_hash(text_path), pages=len(pages), spec=spec,
                                         blank_pages=[p["pdf_page"] for p in pages if not p["text"].strip()])
        print(f"{sid}: {len(pages)} Seiten/Notizen, {len(manifest['sources'][sid]['blank_pages'])} ohne Text")
    if not manifest["sources"]:
        raise ValueError("Keine Quellen: zuerst course.yaml konfigurieren")
    write(course.path("manifest"), manifest)
    structure = read(course.path("structure"))
    if not structure["sections"]:
        size = int(course.data["processing"]["pages_per_section"])
        if size < 1:
            raise ValueError("pages_per_section muss positiv sein")
        for sid, entry in manifest["sources"].items():
            if entry["spec"]["kind"] != "script":
                continue
            for first in range(1, entry["pages"] + 1, size):
                pages = list(range(first, min(first + size, entry["pages"] + 1)))
                structure["sections"].append(dict(id=f"sec-{sid}-{first:04d}", source=sid, pages=pages,
                                                   title=f"{sid}: PDF {pages[0]}–{pages[-1]}", needs_review=True))
        write(course.path("structure"), structure)


def page_map(course, sid):
    return {p["pdf_page"]: p for p in read(course.path("extracted") / f"{identifier(sid)}-pages.json", [])}
