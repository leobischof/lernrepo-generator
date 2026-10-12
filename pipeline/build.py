import xml.etree.ElementTree as ET
from .ingest import page_map
from .io import digest, file_hash, identifier, read, write
from .jobs import approved, make_jobs, state, validate_result


def build_fingerprint(course):
    index = read(course.path("job_index"), {"jobs": []})
    return digest({"state": state(course), "results": {
        j["job_id"]: read(course.path("results") / f"{j['job_id']}.json") for j in index["jobs"]}})


def generated_hashes(course):
    return {str(p.relative_to(course.root)): file_hash(p)
            for key in ("content", "learning", "exams") for p in course.path(key).rglob("*")
            if p.is_file() and "progress" not in p.relative_to(course.root).parts}


def assert_build_current(course):
    cached = read(course.path("build_state"), {})
    if cached.get("fingerprint") != build_fingerprint(course):
        raise ValueError("Generierte Inhalte fehlen oder sind veraltet: build ausführen")
    for relative, fingerprint in cached.get("files", {}).items():
        path = course.local(relative)
        if not path.exists() or file_hash(path) != fingerprint:
            raise ValueError(f"Generierte Datei verändert/fehlt: {relative}; build ausführen")


def citation(refs):
    return "; ".join(f"{r['source']}, PDF S. {r['page']}" for r in refs)


def build(course):
    approved(course)
    from .jobs import plan
    plan(course)
    structure = read(course.path("structure"))
    manifest = read(course.path("manifest"))["sources"]
    index = [f"# {course.data['course']['title']} – Skript\n\nSchicht: extrahierter, ungeprüfter Quellentext.\n"]
    for section in structure["sections"]:
        pages = page_map(course, section["source"])
        text = f"# {section['title']}\n\nSchicht: extrahiert, ungeprüft; vollständiger Quellentext einschließlich Ausschlüssen.\n\n"
        for number in section["pages"]:
            page = pages[number]
            text += f"## Quelle {section['source']}, PDF S. {number}\n\n{page['text']}\n\n"
            if page.get("strikeout_candidates"):
                text += "*Streichungsannotation erkannt; Sichtprüfung erforderlich.*\n\n"
            if page["needs_review"]:
                text += "*Extraktion unklar oder unvollständig; Originalseite prüfen.*\n\n"
        write(course.path("content") / f"{section['id']}-skript.md", text)
        index.append(f"- [{section['title']}]({section['id']}-skript.md)")
    write(course.path("content") / "skript-inhalt.md", "\n".join(index) + "\n")
    questions, cards, figures, uncertainties = [], [], [], []
    learning_index = []
    for job in make_jobs(course):
        result = read(course.path("results") / f"{job['job_id']}.json")
        if not result or result.get("input_hash") != job["input_hash"]:
            continue
        validate_result(job, result)
        jid = job["job_id"]
        title = f"# {job['title']}\n\n**KI-Erklärung, ungeprüft.** Quelle: {job['trust']}.\n\n"
        guide = title + "\n\n".join(f"{x['text']}\n\n*{citation(x['refs'])}*" for x in result["guide"])
        guide += "\n\n" + "\n".join(f"- Unsicherheit: {u}" for u in result["uncertainties"])
        write(course.path("learning") / f"{jid}-leitfaden.md", guide + "\n")
        learning_index.append(f"- [{job['title']}]({jid}-leitfaden.md)")
        audio = title + "Verwende nur diesen Kontext für ein ausführliches Lernhörspiel. "
        audio += "Belege, Streichungen und Unsicherheiten beachten. Keine Fakten ergänzen.\n\n"
        audio += "\n\n".join(f"{x['text']}\n\n*{citation(x['refs'])}*" for x in result["audio"])
        audio += "\n\n" + "\n".join(result["uncertainties"])
        write(course.path("learning") / f"{jid}-hoerspiel-kontext.md", audio + "\n")
        for field, collection in (("cards", cards), ("questions", questions), ("figures", figures)):
            for item in result[field]:
                collection.append({**item, "id": f"{jid}-{item['id']}", "section": job["section"],
                                   "trust": job["trust"], "status": "ki-erstellt-ungeprueft"})
        uncertainties.extend(f"{jid}: {u}" for u in result["uncertainties"])
    write(course.path("learning") / "lernmaterial-inhalt.md", "# Lernmaterial\n\n" + "\n".join(learning_index) + "\n")
    write(course.path("learning") / "cards.json", cards)
    write(course.path("learning") / "figure-jobs.json", figures)
    for origin, filename in (("real", "questions-real.json"), ("generated", "questions-generated.json")):
        write(course.path("exams") / filename, [q for q in questions if q["origin"] == origin])
    solutions = ["# Musterlösungen\n\nKI-Erklärung, ungeprüft.\n"]
    for q in questions:
        solutions.append(f"## {q['id']}\n\n{q['prompt']}\n\n{q['solution'] or 'Lösung fehlt.'}\n\n"
                         f"*{citation(q['refs'])}; Herkunft: {q['origin']}*\n")
    write(course.path("learning") / "musterloesungen.md", "\n".join(solutions))
    mapping = {s["id"]: {"questions": [q["id"] for q in questions if q["section"] == s["id"]],
                          "cards": [c["id"] for c in cards if c["section"] == s["id"]]}
               for s in structure["sections"]}
    write(course.path("exams") / "topic-mapping.json", {"by_section": mapping})
    write(course.path("reports") / "unsicherheiten.md", "# Offene Stellen\n\n" + "\n".join(f"- {u}" for u in uncertainties) + "\n")
    write(course.path("build_state"), {"fingerprint": build_fingerprint(course), "files": generated_hashes(course)})
    return dict(sections=len(structure["sections"]), cards=len(cards), questions=len(questions), figure_jobs=len(figures))


def figures(course):
    """Crops and blank templates from explicit, reviewed figure metadata."""
    import pymupdf
    from .svg_blank import blank_svg
    from .jobs import check_structure
    errors = check_structure(course)
    errors = [e for e in errors if not e.startswith("Abschnitt noch ungeprüft")]
    if errors:
        raise ValueError("\n".join(errors))
    for figure in read(course.path("structure"))["figures"]:
        fid = identifier(figure["id"])
        source = read(course.path("manifest"))["sources"][figure["source"]]
        original = course.path("originals") / (figure["source"] + __import__("pathlib").Path(source["spec"]["path"]).suffix.lower())
        with pymupdf.open(original) as doc:
            page = doc[figure["page"] - 1]
            rect = pymupdf.Rect(figure["bbox"])
            if not page.rect.contains(rect) or rect.is_empty:
                raise ValueError(f"Ungültiger Abbildungsausschnitt: {fid}")
            output = course.path("crops") / f"{fid}.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(clip=rect, dpi=180).save(output)
        svg = course.path("figures") / f"{fid}.svg"
        if svg.exists():
            blank, count = blank_svg(svg.read_text(encoding="utf-8"))
            if not count:
                raise ValueError(f"SVG ohne Antwortmarkierungen: {fid}")
            write(course.path("blanks") / f"{fid}-blank.svg", blank)


def offline(course):
    from .jobs import check_structure, state
    from .io import digest
    errors = check_structure(course)
    warnings = []
    current = state(course)
    if read(course.path("review"), {}).get("state_hash") != digest(current):
        warnings.append("Struktur-/Quellenfreigabe fehlt oder ist veraltet")
    jobs = []
    if not errors and not warnings:
        index = read(course.path("job_index"), {})
        if index.get("state_hash") == digest(current):
            jobs = index["jobs"]
        else:
            warnings.append("Auftragsindex fehlt oder ist veraltet: plan ausführen")
    complete = 0
    for job in jobs:
        result = read(course.path("results") / f"{job['job_id']}.json")
        if result and result.get("input_hash") == job["input_hash"]:
            try:
                validate_result(job, result, verify_wording=False)
                complete += 1
            except (ValueError, __import__("jsonschema").ValidationError) as exc:
                errors.append(f"{job['job_id']}: {str(exc)[:200]}")
    if jobs and complete < len(jobs):
        warnings.append(f"Lernmaterial unvollständig: {complete}/{len(jobs)} Aufträge")
    try:
        assert_build_current(course)
    except ValueError as exc:
        warnings.append(str(exc))
    for sid, entry in (current["manifest"] or {"sources": {}})["sources"].items():
        if entry["blank_pages"]:
            warnings.append(f"{sid}: Seiten ohne Text {entry['blank_pages']}; OCR/Original prüfen")
    names = {}
    for base in ("content", "learning", "exams", "reports", "figures"):
        for path in (course.root / base).rglob("*"):
            if path.is_file() and "progress" not in path.parts and "originals" not in path.parts:
                if path.name.casefold() in names:
                    errors.append(f"Doppelter Dateiname: {path.name}")
                names[path.name.casefold()] = path
    text = "# Validierung\n\n" + ("Keine strukturellen Fehler.\n" if not errors else "\n".join(f"- FEHLER: {e}" for e in errors))
    text += "\n" + "\n".join(f"- WARNUNG: {w}" for w in warnings) + "\n"
    text += "\nStrukturprüfungen bestätigen keine fachliche Richtigkeit. KI-Material bleibt ungeprüft.\n"
    write(course.path("reports") / "validation.md", text)
    write(course.path("reports") / "coverage.md", f"# Abdeckung\n\nAbschnitte: {len((current['structure'] or {}).get('sections', []))}\n\n"
          f"Aktuelle Aufträge: {complete}/{len(jobs)}\n\nFachliche/visuelle Prüfung: nicht automatisch bestätigt.\n")
    return {"errors": errors, "warnings": warnings}
