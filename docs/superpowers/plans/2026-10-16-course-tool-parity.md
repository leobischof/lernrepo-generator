# Fachunabhängige Lernwerkzeuge Implementation Plan

> **For agentic workers:** Use `executing-plans` to implement this plan task-by-task.
> Schritte mit Checkboxen verfolgen. Standard-Service ist für Unteragenten in dieser
> Sitzung nicht steuerbar; daher erfolgt die Ausführung im Feature-Branch dieser Sitzung.

**Goal:** Die im Referenzrepo vorhandenen allgemeinen Lernwerkzeuge für beliebige
Kurse verfügbar machen und als getesteten Pull Request liefern.

**Architecture:** Additive Module verwenden `Course` und ein zentrales Kapitelmodell.
Reader-Assets werden generalisiert, fachliche Referenzdaten bleiben ausgeschlossen.
Bestehende Version-1-Kurse und Agentenantworten bleiben kompatibel.

**Tech Stack:** Python >=3.11, PyMuPDF, Markdown, matplotlib, genanki; Node.js >=22.13,
PDF.js, Browser-Service-Worker; optional faster-whisper ausschließlich lokal.

**Spec:** [Entwurf](../specs/2026-10-16-course-tool-parity-design.md)

## Global Constraints

- Python >=3.11; Node.js >=22.13 für Reader-Build, nicht für die Wiedergabe.
- Deutsch in Dokumentation und Oberfläche; Titel und IDs aus Kurskonfiguration.
- Keine kostenpflichtigen Modellaufrufe oder Übertragung von Kursmaterialien.
- Originale, Extraktionen, Audios und persönlicher Fortschritt bleiben git-ignoriert.
- Kein Merge, Release-Upload oder Ändern von GitHub-Schutzregeln.
- TDD: zuerst Verhaltenstest schreiben, roten Lauf prüfen, dann implementieren.
- Eigene Commits gezielt stagen; fremde Branches und Änderungen erhalten.

## Task 1: Kapitel und vollständige Werkzeugupdates

**Files:** `pipeline/chapters.py`, `pipeline/config.py`, `pipeline/generator.py`,
`tests/test_course_tools.py`, `.gitignore`.

**Interfaces:** `chapters.discover(course) -> list[dict]` liefert `id`, `number`,
`title`, `sections`, `stem`; `chapters.prefix(course) -> str` validiert Exportpräfix.
`generator.create` und `upgrade` behalten ihre Aufrufsignaturen.

- [x] Rot: zwei Kapitel mit anderem Präfix, Legacy-Fallback und unbekannten/doppelt
  zugeordneten Abschnitten prüfen; erzeugten Kurs als eigenes Python-Programm starten.

```python
chapters = discover(course)
assert chapters[0]['stem'] == 'physik-1-Grundlagen'
assert chapters[1]['sections'] == ['sec-2']
```

- [x] `python -m pytest tests/test_course_tools.py` ausführen; fehlendes Modul bestätigen.
- [x] Kapitelvalidierung und vollständige Asset-Kopie implementieren. Upgrade prüft
  `pipeline/`, `interactive/`, Tests, Konfiguration und Startskript vor jedem Schreiben.
  Ohne Git werden sämtliche ersetzten Dateien gesichert. Kurskonfiguration bleibt erhalten.
- [x] Negativfälle und vollständige bestehende Tests ausführen.
- [x] Commit: `feat: add portable chapters and complete tool upgrades`.

## Task 2: Quellenkorrekturen und Abbildungen

**Files:** `pipeline/source_tools.py`, `pipeline/ingest.py`, `pipeline/build.py`,
`pipeline/jobs.py`, `pipeline/figure_tools.py`, `tests/test_source_tools.py`.

**Interfaces:** `source_tools.apply_corrections(course, sid, pages) -> list[dict]`;
`figure_tools.detect(course) -> dict`; `figure_tools.icons(course) -> dict`.
Korrekturen in `curation/text-corrections.json`, geprüfte Abbildungen in der Struktur.

- [x] Rot: exakter Austausch mit Quellenhash, unverändertes Original, erneute
  Anwendung ohne Doppelkorrektur, Ablehnung nicht auffindbarer Originalstelle testen.

```python
pages = apply_corrections(course, 'skript', extracted_pages)
assert pages[0]['text'] == 'Energie bleibt erhalten.'
```

- [x] Rot: Bildkandidat wird nur vorgeschlagen; Icon ohne Lizenz oder mit externen
  Referenzen wird abgelehnt; Originalausschnitte gelangen nicht in Export.
- [x] Korrekturen nachvollziehbar auf Arbeitskopie der Extraktion anwenden, in
  Freigabe-Hash einbeziehen und im Review-Paket anzeigen. PDF-Bildregionen vorschlagen.
- [x] Lokale Icon-Einbettung mit Lizenzprovenienz und SVG-Prüfung implementieren.
- [x] Tests ausführen und committen: `feat: add reviewed text and figure curation`.

## Task 3: Kapitelkontext, PDFs und Exportpakete

**Files:** `pipeline/chapter_exports.py`, `pipeline/pdf_export.py`, `pipeline/export.py`,
`pipeline/release.py`, `tests/test_chapter_exports.py`.

**Interfaces:** `chapter_exports.notebooklm(course) -> dict`, `pdf_export.run(course)
-> dict`, `release.run(course) -> dict`; PDFs unter `build/pdf/<chapter.stem>.pdf`.

- [x] Rot: Kontext enthält Leitfaden, echte Fragen und gesamten Kurs; Kapitelpräfix
  folgt Konfiguration; PDF lässt sich öffnen und hat Text/Inhaltsverzeichnis.

```python
with pymupdf.open(pdf_path) as pdf:
    assert 'Energie' in ''.join(page.get_text() for page in pdf)
    assert pdf.get_toc()
```

- [x] Direkte PDFs mit Tabellen, Formeln und kuratierten SVGs bauen; keine Kopie der
  Original-PDFs oder -Bilder. Bestehende Markdown-/TeX-Ausgaben beibehalten.
- [x] Deterministische Kapitel- und Gesamt-ZIPs mit Positivliste der erzeugten
  Dateien; veraltete Build-Artefakte nicht stillschweigend verpacken.
- [x] Tests ausführen und committen: `feat: export chapter contexts and rich PDFs`.

## Task 4: Anki-Typen und belegte Prüfungsanalyse

**Files:** `pipeline/anki_export.py`, `pipeline/exam_analysis.py`, `pipeline/contracts.py`,
`pipeline/export.py`, `tests/test_learning_exports.py`.

**Interfaces:** `anki_export.run(course) -> dict`, `exam_analysis.run(course) -> dict`.
Optionale Kartenfelder `kind` und `cloze`; unbekannte Felder bleiben verboten.

- [x] Rot: APKG öffnen, Lückentextmodell, Kapitelpakete, SVG-Zeichenkarten und
  gleichbleibende GUIDs prüfen; Studierendenkarten als unverifiziert kennzeichnen.
- [x] Rot: echte Aufgaben zweier belegter Termine zählen, KI-Fragen ausschließen;
  ohne Datum keine erfundene Terminzahl.
- [x] Implementieren, bestehende Antwortfixtures unverändert akzeptieren.
- [x] Tests ausführen und committen: `feat: expand Anki exports and exam analysis`.

## Task 5: Reader, lokale Audiozuordnung und HTML

**Files:** `interactive/*`, `pipeline/reader.py`, `pipeline/timeline.py`,
`pipeline/audio_sync.py`, `pipeline/reader_package.py`, `pipeline/reader_serve.py`,
`dev.ps1`, `pyproject.toml`, `tests/test_reader.py`, `tests/test_audio_sync.py`.

**Interfaces:** `reader.run(course) -> dict`, `audio_sync.run(course, model, start=False)
-> dict`, `reader_package.run(course) -> dict`. Timeline-Vertrag Version 1 bindet
Kapitelnummer und SHA-256 von PDF/Audio, Zeitintervalle und normierte Koordinaten.

- [x] Rot: Reader ohne Audio baubar; richtige Medien-/PDF-Zuordnung; veralteter
  Hash, ungültige Seiten und Pfade werden abgelehnt; kuratierte Timeline bleibt erhalten.
- [x] Allgemeine Reader-Assets und Range-Server aus Referenz übernehmen; GIL-Namen,
  Kurs-Icons und feste Kapitel durch Kurskonfiguration ersetzen.
- [x] Lokale ASR erst mit `--start`; Cache berücksichtigt Audio und Modell, neue
  Zuordnungen bleiben ungeprüft; keine automatische Modellinstallation beim Build.
- [x] HTML mit eingebettetem PDF.js, PDF, optionalem Audio und Timeline erzeugen;
  Sonderzeichen im Titel dürfen HTML/JavaScript nicht beenden.
- [x] `node --test interactive/*.test.mjs` und Python-Tests ausführen.
- [x] Commit: `feat: add portable PDF audio reader and offline chapters`.

## Task 6: Integration, Dokumentation und Pull Request

**Files:** `pipeline/__main__.py`, `.github/workflows/qa.yml`, `README.md`, `AGENTS.md`,
`docs/arbeitsablauf.md`, `docs/code-herkunft.md`, `docs/generator-architektur.md`,
`tests/test_tool_parity.py`, `curation/ai-log.jsonl`.

- [x] Synthetischen neuen Kurs durch sämtliche CLI-Befehle und Werkzeugupdate
  führen; alter Version-1-Kurs bleibt kompatibel. Vollständige Python-/JS-Suite.
- [x] Im Browser Desktop/Mobilansicht, PDF-Navigation, Audio-Sprung, Offline-Cache
  und eigenständiges HTML mit ausschließlich synthetischen Daten prüfen.
- [x] Herkunft jedes übernommenen technischen Moduls, Grenzen und Befehle
  dokumentieren; KI-Durchgang über `pipeline.ailog.append` protokollieren.
- [x] `git diff --check`, Branch-/Commit-Konventionen und Diff auf Kursdaten prüfen.
- [x] Commit: `test: verify complete course tooling and document workflow`.
- [x] Branch normal in `WernerBi/lernrepo-generator` pushen und
  [PR #4](https://github.com/leobischof/lernrepo-generator/pull/4) gegen das Ursprungsrepo
  erstellen. Der aktive Zugang hat dort keine Schreibrechte; der Fork gehört zum
  autorisierten PR-Weg. Kein Merge.
- [ ] GitHub-CI nach Maintainer-Freigabe prüfen. GitHub meldet ausdrücklich
  „This workflow is awaiting approval from a maintainer in #4“ (`action_required`,
  keine Jobs gestartet). Die Freigabe kann der aktive Zugang nicht erteilen.

## Prüfnachweis

[Lokale Prüfungen und Grenzen](../../pruefung-2026-10-16.md). Lokale Umsetzung,
Prüfungen und PR sind abgeschlossen; der GitHub-CI-Start wartet auf den Maintainer.
