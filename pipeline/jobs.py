import json
from .contracts import SCHEMA, SYSTEM
from .ingest import page_map
from .io import digest, file_hash, identifier, read, write


def state(course):
    value = {"config": course.data, "manifest": read(course.path("manifest")),
             "structure": read(course.path("structure"))}
    for name in ('text-corrections', 'exam-links'):
        path = course.root / f'curation/{name}.json'
        if path.exists():
            value[name] = read(path)
    return value


def review(course, reviewer):
    errors = check_structure(course)
    if errors:
        raise ValueError("\n".join(errors))
    if not reviewer.strip():
        raise ValueError("Reviewer muss angegeben sein")
    write(course.path("review"), {"state_hash": digest(state(course)), "reviewer": reviewer})


def check_structure(course):
    current = state(course)
    manifest, structure = current["manifest"], current["structure"]
    if not manifest or not structure:
        return ["Import oder Struktur fehlt"]
    errors, seen, covered = [], set(), set()
    try:
        from .chapters import discover
        discover(course)
        from .source_tools import apply_corrections
        for sid in manifest['sources']:
            path = course.path('extracted') / f'{identifier(sid)}-pages.json'
            if path.exists():
                apply_corrections(course, sid, read(path))
    except ValueError as exc:
        errors.append(str(exc))
    for section in structure["sections"]:
        identifier(section["id"])
        if section["id"] in seen:
            errors.append(f"Doppelte Abschnitts-ID: {section['id']}")
        seen.add(section["id"])
        source = manifest["sources"].get(section["source"])
        if not source or source["spec"]["kind"] != "script":
            errors.append(f"Abschnittsquelle ist kein Skript: {section['id']}")
            continue
        if section.get("needs_review", True):
            errors.append(f"Abschnitt noch ungeprüft: {section['id']}")
        if not section["pages"] or sorted(set(section["pages"])) != section["pages"]:
            errors.append(f"Seiten müssen eindeutig und aufsteigend sein: {section['id']}")
        for page in section["pages"]:
            if type(page) is not int or not 1 <= page <= source["pages"]:
                errors.append(f"Ungültige Seite: {section['id']}/{page}")
            key = (section["source"], page)
            if key in covered:
                errors.append(f"Seite mehrfach zugeordnet: {section['source']}/{page}")
            covered.add(key)
    for sid, entry in manifest["sources"].items():
        extracted = course.path("extracted") / f"{identifier(sid)}-pages.json"
        if extracted.exists() and file_hash(extracted) != entry.get("extraction_sha256"):
            errors.append(f"Extraktion nachträglich verändert: {sid}; erneut ingest ausführen")
        if entry["spec"]["kind"] == "script":
            missing = [p for p in range(1, entry["pages"] + 1) if (sid, p) not in covered]
            if missing:
                errors.append(f"Skriptseiten ohne Abschnitt: {sid} {missing}")
    for ex in structure["exclusions"]:
        if not ex.get("reason") or not ex.get("reviewed", False):
            errors.append("Jeder Ausschluss braucht Begründung und reviewed=true")
        source = manifest["sources"].get(ex.get("source"))
        if not source or type(ex.get("page")) is not int or not 1 <= ex["page"] <= source["pages"]:
            errors.append("Ausschluss mit ungültigem Quellenverweis")
            continue
        extracted = course.path("extracted") / f"{ex['source']}-pages.json"
        if extracted.exists() and ex.get("text") and ex["text"] not in page_map(course, ex["source"])[ex["page"]]["text"]:
            errors.append("Auszuschließender Text wurde auf der Seite nicht gefunden")
    figure_ids = set()
    for figure in structure.get("figures", []):
        fid = identifier(figure["id"])
        if fid in figure_ids:
            errors.append(f"Doppelte Abbildungs-ID: {fid}")
        figure_ids.add(fid)
        source = manifest["sources"].get(figure.get("source"))
        if not source or type(figure.get("page")) is not int or not 1 <= figure["page"] <= source["pages"]:
            errors.append(f"Ungültige Abbildungsseite: {fid}")
        bbox = figure.get("bbox", [])
        if len(bbox) != 4 or any(type(v) not in (int, float) or not __import__("math").isfinite(v) for v in bbox):
            errors.append(f"Ungültige Abbildungskoordinaten: {fid}")
    return errors


def approved(course):
    if read(course.path("review"), {}).get("state_hash") != digest(state(course)):
        raise ValueError("Quellen/Struktur nicht freigegeben oder seit Freigabe geändert: review erforderlich")


def filtered_text(course, sid, page):
    text = page_map(course, sid)[page]["text"]
    for ex in read(course.path("structure"))["exclusions"]:
        if ex["source"] == sid and ex["page"] == page:
            if not ex.get("text"):
                return ""
            text = text.replace(ex["text"], "")
    return text


def make_jobs(course):
    approved(course)
    manifest = read(course.path("manifest"))["sources"]
    structure = read(course.path("structure"))
    groups = [(s["id"], s["source"], s["pages"], s["title"]) for s in structure["sections"]]
    for sid, entry in manifest.items():
        if entry["spec"]["kind"] != "script":
            for page in range(1, entry["pages"] + 1):
                groups.append((f"source-{sid}-{page:04d}", sid, [page], sid))
    jobs = []
    limit = int(course.data["processing"]["max_chars_per_job"])
    if limit < 1:
        raise ValueError("max_chars_per_job muss positiv sein")
    for group_id, sid, pages, title in groups:
        segments, batch, count = [], [], 0
        for page in pages:
            text = filtered_text(course, sid, page)
            if not text.strip():
                continue
            # Long pages split deterministically; none silently truncated.
            for offset in range(0, len(text), limit):
                fragment = dict(source=sid, page=page, text=text[offset:offset + limit])
                if batch and count + len(fragment["text"]) > limit:
                    segments.append(batch)
                    batch, count = [], 0
                batch.append(fragment)
                count += len(fragment["text"])
        if batch:
            segments.append(batch)
        for part, sources in enumerate(segments, 1):
            jid = f"{group_id}-{part:03d}"
            payload = dict(job_id=jid, section=group_id, title=title, sources=sources,
                           trust=manifest[sid]["spec"]["trust"], kind=manifest[sid]["spec"]["kind"],
                           products=course.data["products"], response_schema=SCHEMA,
                           course=course.data["course"])
            payload["input_hash"] = digest({"payload": payload, "system": SYSTEM})
            jobs.append(payload)
    return jobs


def plan(course):
    jobs = make_jobs(course)
    pending = []
    for job in jobs:
        write(course.path("jobs") / f"{job['job_id']}.json", {"system": SYSTEM, **job})
        cached = read(course.path("results") / f"{job['job_id']}.json", {})
        if cached.get("input_hash") != job["input_hash"]:
            pending.append(job)
    # Public structural job metadata, never raw prompts or full source text.
    write(course.path("job_index"), {"state_hash": digest(state(course)), "jobs": [
        {**{key: j[key] for key in ("job_id", "input_hash", "section", "title", "kind", "trust", "products")},
         "sources": [{"source": s["source"], "page": s["page"]} for s in j["sources"]]} for j in jobs]})
    llm = course.data["llm"]
    tokens = sum((len(json.dumps(j, ensure_ascii=False)) + len(SYSTEM) + 2) // 3 for j in pending)
    output = len(pending) * llm["max_output_tokens"]
    prices = llm.get("input_per_million"), llm.get("output_per_million")
    estimate = None if None in prices else (tokens * prices[0] + output * prices[1]) / 1_000_000
    report = dict(jobs=len(jobs), pending=len(pending), estimated_input_tokens=tokens,
                  maximum_output_tokens=output, estimated_cost=estimate,
                  note="Tokenheuristik (Zeichen/3), keine Preisgarantie. Preise selbst konfigurieren; Währung wie Anbieter.")
    write(course.path("jobs").parent / "plan.json", report)
    return report


def validate_result(job, result, verify_wording=True):
    import jsonschema
    jsonschema.validate(result, SCHEMA)
    if result["job_id"] != job["job_id"] or result["input_hash"] != job["input_hash"]:
        raise ValueError("Antwort passt nicht zum aktuellen Auftrag")
    refs = {(s["source"], s["page"]) for s in job["sources"]}
    seen = set()
    products = set(job["products"])
    allowed = {"guide": "guide", "cards": "cards", "questions": "questions", "audio": "audio", "figures": "figures"}
    for field in ("guide", "cards", "questions", "audio", "figures"):
        if result[field] and allowed[field] not in products:
            raise ValueError(f"Nicht bestelltes Lernprodukt: {field}")
        for item in result[field]:
            if field == 'cards' and item.get('kind') == 'cloze':
                if not __import__('re').search(r'\{\{c[1-9]\d*::.+?\}\}', item.get('cloze', '')):
                    raise ValueError('Lückentext braucht mindestens {{c1::Antwort}}')
            if any((r["source"], r["page"]) not in refs for r in item["refs"]):
                raise ValueError("Quellenverweis außerhalb des Auftrags")
            if "id" in item:
                identifier(item["id"])
                identity = (field, item["id"])
                if identity in seen:
                    raise ValueError("Doppelte Ergebnis-ID")
                seen.add(identity)
            if field == "questions" and item["origin"] == "real":
                if job["kind"] not in {"exam", "exam-collection", "exercises"}:
                    raise ValueError("Echte Aufgabe benötigt eine Aufgabenquelle")
                if verify_wording:
                    normalize = lambda s: " ".join(s.split())
                    joined = normalize("\n".join(s["text"] for s in job["sources"]))
                    if normalize(item["prompt"]) not in joined:
                        raise ValueError("Echte Aufgabe ist nicht wortgetreu in der Quelle enthalten")
            if field == "questions" and item["origin"] == "generated" and item["points"] is not None:
                raise ValueError("KI-Aufgaben haben keine belegte Punktzahl: points=null")
    if not any(result[f] for f in ("guide", "cards", "questions", "audio", "figures", "uncertainties")):
        raise ValueError("Leere Antwort ohne Unsicherheitsmeldung")


def accept(course, model="agent:unknown"):
    from .ailog import append
    count = 0
    for job in make_jobs(course):
        src = course.path("responses") / f"{job['job_id']}.json"
        if not src.exists():
            continue
        result = read(src)
        validate_result(job, result)
        dest = course.path("results") / src.name
        if read(dest) != result:
            write(dest, result)
            append(course.path("log"), stage="accept", model=model,
                   inputs=[job["input_hash"]], result=src.name)
            count += 1
    return count
