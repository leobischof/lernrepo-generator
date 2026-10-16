import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Vorlesungsunabhängiger Lernrepo-Generator")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Kursrepo; Standard aktueller Ordner")
    subs = parser.add_subparsers(dest="command", required=True)
    create = subs.add_parser("new", help="Eigenständiges lokales Kursrepo erzeugen")
    create.add_argument("destination", type=Path)
    create.add_argument("--title", required=True)
    create.add_argument("--id", required=True)
    upgrade = subs.add_parser("upgrade", help="Werkzeugkopie eines Kursrepos aktualisieren")
    upgrade.add_argument("destination", type=Path)
    for command in ("ingest", "inspect", "plan", "build", "figures", "offline"):
        subs.add_parser(command)
    for command in ('detect-figures', 'figure-icons', 'render-pdf', 'export-notebooklm', 'anki',
                    'exam-analysis', 'interactive', 'audio-reader', 'package-reader', 'release'):
        subs.add_parser(command)
    sync = subs.add_parser('sync-audio', help='Lokale ASR; ohne --start nur Plan')
    sync.add_argument('--start', action='store_true')
    sync.add_argument('--model', default='tiny')
    serve = subs.add_parser('serve', help='Reader nur auf Loopback bereitstellen')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--open', action='store_true')
    review = subs.add_parser("review", help="Geprüften Quellen-/Strukturstand freigeben")
    review.add_argument("--reviewer", required=True)
    accept = subs.add_parser("accept", help="Agentenantworten validieren und übernehmen")
    accept.add_argument("--model", default="agent:unknown")
    api = subs.add_parser("run-api", help="Ohne --start nur Plan; mit --start kostenpflichtige Verarbeitung")
    api.add_argument("--start", action="store_true")
    api.add_argument("--max-jobs", type=int, default=1)
    export = subs.add_parser("export")
    export.add_argument("--compile", action="store_true", dest="compile_pdf")
    progress = subs.add_parser("progress")
    progress.add_argument("action", choices=["show", "due", "record"])
    progress.add_argument("topic", nargs="?")
    progress.add_argument("competency", nargs="?")
    progress.add_argument("score", type=int, choices=range(6), nargs="?")
    progress.add_argument("--fehler", default="")
    progress.add_argument("--skizze", choices=["ja", "nein"])
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            from .generator import create
            result = str(create(args.destination, args.title, args.id))
        elif args.command == "upgrade":
            from .generator import upgrade
            upgrade(args.destination)
            result = "Werkzeugdateien aktualisiert; Änderungen prüfen"
        else:
            from .config import Course
            course = Course(args.root)
            if args.command == "ingest":
                from .ingest import run
                result = run(course)
            elif args.command == "inspect":
                from .inspect import run
                result = run(course)
            elif args.command == "review":
                from .jobs import review
                result = review(course, args.reviewer)
            elif args.command == "plan":
                from .jobs import plan
                result = plan(course)
            elif args.command == "accept":
                from .jobs import accept
                result = {"accepted": accept(course, args.model)}
            elif args.command == "run-api":
                from .api import run
                result = run(course, start=args.start, max_jobs=args.max_jobs)
            elif args.command == "export":
                from .export import run
                result = run(course, args.compile_pdf)
            elif args.command == 'detect-figures':
                from .figure_tools import detect
                result = detect(course)
            elif args.command == 'figure-icons':
                from .figure_tools import icons
                result = icons(course)
            elif args.command == 'render-pdf':
                from .pdf_export import run
                result = run(course)
            elif args.command == 'export-notebooklm':
                from .chapter_exports import notebooklm
                result = notebooklm(course)
            elif args.command == 'anki':
                from .anki_export import run
                result = run(course)
            elif args.command == 'exam-analysis':
                from .exam_analysis import run
                result = run(course)
            elif args.command == 'interactive':
                from .reader import run
                result = run(course)
            elif args.command == 'audio-reader':
                from .pdf_export import run as pdf
                from .reader import run as reader
                result = {'pdf': pdf(course), 'reader': reader(course)}
            elif args.command == 'sync-audio':
                from .audio_sync import run
                result = run(course, model=args.model, start=args.start)
            elif args.command == 'package-reader':
                from .reader_package import run
                result = run(course)
            elif args.command == 'release':
                from .release import run
                result = run(course)
            elif args.command == 'serve':
                from .reader_serve import main as serve_main
                return serve_main(['--directory', str(course.root / 'build/interactive'), '--port', str(args.port)]
                                  + (['--open'] if args.open else []))
            elif args.command == "progress":
                from .progress import run
                if args.action == "record" and None in (args.topic, args.competency, args.score):
                    raise ValueError("record benötigt Thema, Kompetenz und Ergebnis 0–5")
                result = run(course, args.action, args.topic, args.competency, args.score,
                             args.fehler, {None: None, "ja": True, "nein": False}[args.skizze])
            else:
                from . import build
                result = getattr(build, args.command)(course)
                if args.command == "offline" and result["errors"]:
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 1
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, __import__("jsonschema").ValidationError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
