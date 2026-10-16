# Lernrepo-Generator

Ein Werkzeug für eigenständige Wissensrepos zu beliebigen Vorlesungen. Ein Kurs kann
mehrere Skripte, Altklausuren, Übungsangaben, Zusammenfassungen und vorhandene Anki-Decks
enthalten. Python übernimmt Import, Arbeitsaufträge, Prüfungen und Exporte. Das LLM
der jeweiligen Person liefert die didaktischen Inhalte – als Agent oder über API.

Öffentliches Werkzeugrepo: [leobischof/lernrepo-generator](https://github.com/leobischof/lernrepo-generator).
Kursrepos starten weiterhin privat. Beiträge laufen über Feature-Branches, Conventional
Commits und PRs mit `qa` und `konventionen`; Merge ausschließlich per Squash.
Die Schutzregeln gelten auch für Admins. Details: [Git-Regeln](docs/github-regeln.md).

## Start

```powershell
python -m pip install -e ".[pipeline,dev]"
python -m pipeline new "../Meine-Vorlesung-Wissensrepo" --title "Meine Vorlesung" --id meine-vorlesung
```

Das Ziel enthält Werkzeug, Konfiguration, Agentenanleitung und Tests und benötigt
den Generator später nicht mehr. Ist Git installiert, entsteht ein eigenständiges Repo
auf `feature/course-bootstrap` mit einem Initialcommit der Grundstruktur. Spätere
Änderungen lassen sich damit vergleichen. Ohne Git entsteht derselbe nutzbare
Kursordner; Import, LLM-Verarbeitung, Lernen und Exporte funktionieren ebenfalls.
GitHub-Uploads und Modellaufrufe erfolgen nicht beim Erstellen.

Im Kursrepo: Originale unter `input/` ablegen, Quellen in `course.yaml` eintragen und
dem [Arbeitsablauf](docs/arbeitsablauf.md) folgen.

## Lernwerkzeuge und Exporte

Implementiert sind PDF-/Text-/Anki-Import, optionales Tesseract-OCR, Quellenmanifest
mit Hashes, kuratierte Abschnitte und Text-/Seitenausschlüsse, Freigabe mit
Änderungserkennung, begrenzte LLM-Aufträge, gemeinsame Antwortprüfung für Agent/API,
Wiederaufnahme ohne erneute Verarbeitung aktueller Ergebnisse, getrennte echte und
KI-Aufgaben, Musterlösungen, Anki-TSV/APKG mit stabilen IDs, Markdown-/TeX-Export,
optionale PDF-Kompilierung, Hörspiel-Kontext, SVG-Rekonstruktionsaufträge, Ausschnitte
und Blanko-SVGs aus kuratierten Rekonstruktionen, Themenzuordnung, lokale Wiederholungsplanung,
Abdeckungsberichte und Export-ZIP.

Die automatische Erstgliederung besteht aus Seitenblöcken und muss fachlich kuratiert
werden. Extrahierter Skripttext bleibt ausdrücklich ungeprüft; eine verlustfreie,
bereinigte Scan-Rekonstruktion wird nicht behauptet. SVG-Aufträge sind noch keine
visuell geprüften Rekonstruktionen. PDF-Layout, Formeln und Bilder müssen gegen die
Originale geprüft werden. Native Anthropic-/Gemini-Adapter, fertige Audiodateien,
automatische Handschriftbewertung und GitHub-Verwaltung sind spätere Erweiterungen.

Der Ausbau vom 16.10.2026 ergänzt frei konfigurierbare Kapitel und Exportpräfixe,
quellengebundene Textkorrekturen, PDF-Bildkandidaten, lizenzierte lokale SVG-Icons,
eigenständige NotebookLM-Kontexte je Kapitel, direkte PDFs mit Tabellen/Formeln/eigenen
SVGs, zusätzliche Anki-Typen und Kapitelpakete sowie eine belegte Prüfungsanalyse.
Der PDF-/Audio-Reader bietet Suche, Zoom, Zeitmarkierungen, optionale automatische
Navigation und Offline-Kapitel. Vollständig eingebettete HTML-Kapitel und lokale
Release-ZIPs lassen sich separat erzeugen. Lokale Whisper-Transkription ist optional
und startet ausschließlich mit `sync-audio --start`; Audiodateien werden nicht erzeugt.

```powershell
# Im erzeugten Kursrepo, nach Quellenprüfung und build:
python -m pipeline render-pdf
python -m pipeline export-notebooklm
python -m pipeline anki
npm ci --prefix interactive --ignore-scripts
python -m pipeline audio-reader
python -m pipeline serve --open
python -m pipeline package-reader
python -m pipeline release
```

Für den Reader-Build wird zusätzlich Node.js benötigt; das fertige Reader-ZIP läuft
mit Python und Browser ohne Node.js oder Internet. `dev.ps1 setup` richtet die
Werkzeuge ein, `dev.ps1 build|serve|test|package|release` führt die jeweiligen Schritte aus.
Details, Kapitel-/Audio-Konfiguration und Grenzen:
[Reader und Exporte](docs/reader-und-exporte.md).
[Separater Umsetzungsplan](docs/superpowers/plans/2026-10-16-course-tool-parity.md).

Die API-Anbindung nutzt das dokumentierte
[Chat-Completions-Format](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
Kompatibilität hängt vom Endpunkt und Modell ab; ein echter Anbieteraufruf wurde
bei der Erstellung nicht ausgeführt. Preise werden vom Nutzer konfiguriert.

Hintergrund: [Produktentscheidungen](docs/produktentscheidungen.md),
[Architektur](docs/generator-architektur.md), [Herkunft](docs/code-herkunft.md).

```powershell
python -m pytest
```
