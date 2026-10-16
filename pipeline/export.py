import csv
import hashlib
import html
import re
import shutil
import subprocess
import zipfile
from .io import read, write
from .jobs import approved


def stable_id(text):
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big") & 0x7fffffff


def tex_escape(text):
    mapping = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
               "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(mapping.get(c, c) for c in text)


MATH_COMMANDS = set("frac dfrac tfrac sqrt text mathrm mathbf mathit operatorname left right cdot times div pm mp le ge neq approx sim infty sum prod int partial nabla alpha beta gamma delta epsilon theta lambda mu pi rho sigma tau phi omega Gamma Delta Sigma Omega sin cos tan log ln exp lim to in notin subset forall exists begin end matrix pmatrix bmatrix cases aligned quad qquad overline underline vec hat bar dot ddot cdots ldots lVert rVert vert percent".split())


def inline(text):
    parts = re.split(r"(\$\$[\s\S]*?\$\$|\$[^$\n]+\$)", text)
    out = []
    for i, part in enumerate(parts):
        if i % 2:
            commands = re.findall(r"\\([a-zA-Z]+)", part)
            environments = re.findall(r"\\(?:begin|end)\s*\{([^}]+)\}", part)
            math_envs = {"matrix", "pmatrix", "bmatrix", "cases", "aligned"}
            if all(c in MATH_COMMANDS for c in commands) and all(e in math_envs for e in environments) and "^^" not in part:
                out.append(part)
            else:
                out.append(tex_escape(part))
        else:
            escaped = tex_escape(part)
            escaped = re.sub(r"\*\*(.+?)\*\*", lambda m: r"\textbf{" + m[1] + "}", escaped)
            out.append(escaped)
    return "".join(out)


def latex_document(title, markdown):
    chunks = []
    for paragraph in re.split(r"\n\s*\n", markdown):
        lines = paragraph.splitlines()
        if not lines:
            continue
        if lines[0].startswith("#"):
            for line in lines:
                match = re.match(r"^(#{1,6})\s+(.*)$", line)
                if match:
                    command = {1: "section", 2: "subsection"}.get(len(match[1]), "subsubsection")
                    chunks.append("\\" + command + "{" + tex_escape(match[2]) + "}")
                else:
                    chunks.append(inline(line))
        elif all(line.startswith("- ") for line in lines):
            chunks.append("\\begin{itemize}\n" + "\n".join("\\item " + inline(line[2:]) for line in lines) + "\n\\end{itemize}")
        else:
            chunks.append(inline(paragraph))
    return (r"\documentclass[11pt,a4paper]{article}" + "\n" +
            r"\usepackage{fontspec,amsmath,amssymb,graphicx}" + "\n" +
            r"\usepackage[margin=25mm]{geometry}" + "\n" +
            r"\usepackage[hidelinks]{hyperref}" + "\n" +
            r"\setlength{\emergencystretch}{3em}" + "\n" +
            r"\title{" + tex_escape(title) + "}\n\\date{}\n\\begin{document}\n\\maketitle\n\\tableofcontents\n" +
            "\n\n".join(chunks) + "\n\\end{document}\n")


def run(course, compile_pdf=False):
    approved(course)
    from .build import assert_build_current
    assert_build_current(course)
    output = course.path("exports")
    output.mkdir(parents=True, exist_ok=True)
    title = course.data["course"]["title"]
    docs = {}
    sections = read(course.path("structure"))["sections"]
    for section in sections:
        path = course.path("content") / f"{section['id']}-skript.md"
        docs[path.stem] = path.read_text(encoding="utf-8")
    for job in read(course.path("job_index"))["jobs"]:
        result = read(course.path("results") / f"{job['job_id']}.json", {})
        if result.get("input_hash") != job["input_hash"]:
            continue
        for suffix in ("leitfaden", "hoerspiel-kontext"):
            path = course.path("learning") / f"{job['job_id']}-{suffix}.md"
            docs[path.stem] = path.read_text(encoding="utf-8")
    path = course.path("learning") / "musterloesungen.md"
    docs[path.stem] = path.read_text(encoding="utf-8")
    docs["gesamtskript"] = "\n\n".join(docs[k] for k in sorted(docs) if k.endswith("-skript"))
    docs["lernfassung-gesamt"] = "\n\n".join(docs[k] for k in sorted(docs) if k.endswith("-leitfaden"))
    produced = []
    for name, text in docs.items():
        for extension, body in (("md", text), ("tex", latex_document(title, text))):
            dest = output / f"{name}.{extension}"
            write(dest, body)
            produced.append(dest)
    cards = read(course.path("learning") / "cards.json", [])
    tsv = output / "anki-karten.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["#html:true"])
        for card in cards:
            writer.writerow([html.escape(card["front"]), html.escape(card["back"]) + "<br>" +
                             html.escape(str(card["refs"])) + "<br>KI-Erklärung, ungeprüft", card["section"]])
    produced.append(tsv)
    if cards:
        import genanki
        model = genanki.Model(stable_id("lernrepo-basic-v1"), "Lernrepo Frage/Antwort v1",
                              fields=[{"name": "Frage"}, {"name": "Antwort"}],
                              templates=[{"name": "Offene Frage", "qfmt": "{{Frage}}",
                                          "afmt": "{{FrontSide}}<hr>{{Antwort}}"}])
        decks = {}
        for card in cards:
            section = card["section"]
            decks.setdefault(section, genanki.Deck(stable_id(course.data["course"]["id"] + ":" + section),
                                                   title + "::" + section))
            decks[section].add_note(genanki.Note(model=model, fields=[html.escape(card["front"]),
                html.escape(card["back"]).replace("\n", "<br>") + "<hr>" + html.escape(str(card["refs"])) +
                "<br>KI-Erklärung, ungeprüft"], tags=[section, "ki-ungeprueft"],
                guid=genanki.guid_for(course.data["course"]["id"], card["id"])))
        package = output / "anki-gesamt.apkg"
        genanki.Package(list(decks.values())).write_to_file(str(package))
        produced.append(package)
    for svg in course.path("figures").glob("*.svg"):
        dest = output / svg.name
        shutil.copy2(svg, dest)
        produced.append(dest)
    from .anki_export import run as expanded_anki
    from .chapters import prefix
    expanded = expanded_anki(course)
    for relative in expanded['files']:
        source = course.local(relative)
        name = prefix(course) + '-Anki-alle-Typen.apkg' if source.name == 'anki-gesamt.apkg' else source.name
        dest = output / name
        shutil.copy2(source, dest)
        produced.append(dest)
    if compile_pdf:
        engine = shutil.which("xelatex") or shutil.which("lualatex")
        if not engine:
            raise ValueError("TeX-Quellen exportiert; für PDF fehlt XeLaTeX/LuaLaTeX")
        for path in list(produced):
            if path.suffix == ".tex":
                for _ in range(2):
                    result = subprocess.run([engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", path.name],
                                            cwd=output, capture_output=True, timeout=180)
                    if result.returncode:
                        raise ValueError(f"TeX-Kompilierung fehlgeschlagen: {path.name}; siehe {path.stem}.log")
                produced.append(path.with_suffix(".pdf"))
    release = output / "wissensrepo-export.zip"
    with zipfile.ZipFile(release, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in produced:
            archive.write(path, path.name)
    write(output / "export-manifest.json", [p.name for p in produced])
    from .artifacts import index
    index(course, output, produced, list(course.path('figures').glob('*.svg')))
    return dict(files=len(produced), zip=str(release), cards=len(cards))
