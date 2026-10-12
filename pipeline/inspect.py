"""Concrete review packet before any learning generation; no model calls."""
from .io import read, write
from .ingest import page_map


def run(course):
    manifest = read(course.path("manifest"))
    if not manifest:
        raise ValueError("Zuerst ingest ausführen")
    lines = ["# Importprüfung\n", "Dieser Bericht ist ein Prüfauftrag, keine Freigabe.\n",
             "## Quellen\n", "| ID | Art | Vertrauen | Seiten/Notizen | Ohne Text |",
             "|---|---|---|---:|---|"]
    for sid, item in manifest["sources"].items():
        lines.append(f"| {sid} | {item['spec']['kind']} | {item['spec']['trust']} | {item['pages']} | {item['blank_pages']} |")
    lines.extend(["\n## Vor Freigabe prüfen\n", "- Gehört jede Quelle zu dieser Vorlesung und zur gewünschten Fassung?",
                  "- Stimmen Abschnittsgrenzen und Titel? Jede Skriptseite genau einmal zuordnen.",
                  "- Streichungen gegen Original ansehen und als begründete Ausschlüsse erfassen.",
                  "- Seiten ohne Text per OCR oder manueller Transkription erschließen.",
                  "- Quellen-/Seitenverknüpfungen für Prüfungsaufgaben kuratieren.",
                  "- Erst danach needs_review=false setzen und review ausführen.\n"])
    for sid, item in manifest["sources"].items():
        lines.append(f"## Seitenprüfung: {sid}\n")
        for number, page in page_map(course, sid).items():
            preview = " / ".join(line.strip() for line in page["text"].splitlines() if line.strip())[:240]
            flags = []
            if not page["text"].strip():
                flags.append("KEIN TEXT")
            if page.get("strikeout_candidates"):
                flags.append("Streichungsannotation: Sichtprüfung")
            lines.append(f"- PDF/Einheit {number}: {preview or '—'}" + (" **[" + "; ".join(flags) + "]**" if flags else ""))
    path = course.path("reports") / "import-review.md"
    write(path, "\n".join(lines) + "\n")
    return {"report": str(path), "sources": len(manifest["sources"])}
