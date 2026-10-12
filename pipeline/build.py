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
            for key in ("content", "learning", "exams", "figures", "blanks") for p in course.path(key).rglob("*")
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
            for transcript in read(course.path("transcripts"), []):
                if transcript["source"] == section["source"] and transcript["page"] == number:
                    text += "### Visuell geprüfte Seitentranskription\n\n" + transcript["text"] + "\n\n"
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
        job_pages = {(p['source'],p['page']) for p in job['sources']}
        for figure in structure.get('figures',[]):
            fid=identifier(figure['id'])
            if (figure['source'],figure['page']) in job_pages and (course.path('figures')/(fid+'.svg')).exists():
                guide += (f"\n\n[SVG: {figure.get('title',fid)}](../figures/reconstructed/{fid}.svg) · "
                          f"[Leere Übungsvorlage](../figures/exercises/{fid}-blank.svg)\n")
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
    from .figure_tables import table_svg
    metadata = {f['id']: f for f in read(course.path('structure'))['figures']}
    for table in read(course.path('figure_tables'), []):
        fid = identifier(table['id'])
        figure = metadata.get(fid)
        source = read(course.path('manifest'))['sources'].get(table.get('source'))
        if (not figure or not source or table.get('source') != figure['source']
                or table.get('page') != figure['page'] or not table.get('reviewer')
                or table.get('reviewed') is not True or table.get('source_sha256') != source['sha256']):
            raise ValueError('SVG-Tabelle braucht registrierte Figur und aktuelle geprüfte Quelle')
        write(course.path('figures') / (fid+'.svg'), table_svg(table['title'],table['columns'],table['rows'],
              f"{table['source']}, PDF S. {table['page']} – visuell abgeglichene Transkription",table.get('weights')))
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
            if fid in {t['id'] for t in read(course.path('figure_tables'), [])}:
                table = next(t for t in read(course.path('figure_tables')) if t['id']==fid)
                exercise = f"# {table['title']} – Tabellenübung\n\n"
                exercise += 'Rekonstruiere die Inhalte der Tabelle aus dem Gedächtnis. Die Vorlage enthält die Zeilenbezeichnungen.\n\n'
                exercise += f"[Leere Vorlage](../../figures/exercises/{fid}-blank.svg)\n\n"
                exercise += 'Prüfe jede Zelle gegen die [Referenz](../../figures/reconstructed/'+fid+'.svg). '
                exercise += f"Maßgeblich: {figure['source']}, PDF S. {figure['page']}. Formulierungen, Listen und Werte vollständig wiedergeben.\n"
                write(course.path('learning')/'drawing-exercises'/(fid+'-zeichenuebung.md'),exercise)


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
    quality = None
    if jobs:
        from .quality import audit
        quality = audit(course)
        if not quality["ready"]:
            warnings.append(f"Lernqualität offen: {quality['reviewed_pages']}/{quality['script_pages']} Skriptseiten geprüft; "
                            f"{len(quality['missing_guide_pages'])} ohne Leitfadenbeleg; "
                            f"{len(quality['blocked_pages'])} blockiert")
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
          f"Formal gültige Antworten: {complete}/{len(jobs)} (keine fachliche Vollständigkeitsmessung)\n\n"
          + (f"Geprüfte Skriptseiten: {quality['reviewed_pages']}/{quality['script_pages']}\n\n"
             f"Seiten ohne Leitfadenbeleg: {len(quality['missing_guide_pages'])}\n\n" if quality else "")
          + "Fachliche/visuelle Prüfung: nicht automatisch bestätigt.\n")
    return {"errors": errors, "warnings": warnings}
