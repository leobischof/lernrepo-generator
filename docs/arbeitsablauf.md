# Arbeitsablauf eines neuen Kursrepos

Git ist optional. `new` erzeugt mit installiertem Git einen Initialcommit der
Grundstruktur auf `feature/course-bootstrap`. Danach zeigen `git diff` Änderungen
an vorhandenen Dateien und `git status` auch neu erzeugte Dateien. Für einen Diff
neuer Dateien diese zuerst gezielt mit `git add <dateien>` vormerken und
`git diff --cached` verwenden. Fehlt eine Git-Identität, verwendet ausschließlich
der Initialcommit `Lernrepo Generator <lernrepo-generator@localhost>`; die persönliche
Git-Konfiguration bleibt unverändert. Spätere Commits verwenden die eigene Identität.
Ohne Git lässt sich der gesamte Lernablauf in demselben Kursordner ausführen.

## 1. Quellen konfigurieren

```yaml
sources:
  - id: skript
    path: input/mein-skript.pdf
    kind: script
    trust: primary
    ocr: false
  - id: klausur-2025
    path: input/klausur-2025.pdf
    kind: exam
    trust: student-transcript
```

Arten: `script`, `exam`, `exam-collection`, `exercises`, `flashcards`, `summary`.
Vertrauen: `primary`, `student-transcript`, `student-recollection`, `unverified-student`.
PDF, UTF-8-Text/Markdown/TeX/CSV/TSV und APKG werden unterstützt. Textdateien können
mit Form-Feed (`\f`) in logische Seiten geteilt werden. Bei Anki ist eine Seite eine
Notiz; deren HTML bleibt unverifiziert. DOCX zuerst als PDF exportieren.

```powershell
python -m pipeline ingest
python -m pipeline inspect
```

PDF-Text wird ohne inhaltliche Umdeutung extrahiert. Bei `ocr: true` werden textlose
Seiten mit Tesseract verarbeitet; passende Sprachdateien müssen installiert sein.
Fehlerhafte vorhandene Textschichten werden nicht automatisch erkannt oder ersetzt.
Originale und Extraktionen bleiben lokal, ihr Manifest wird versioniert.

## 2. Struktur und Ausschlüsse prüfen

`curation/structure.json` enthält zunächst Seitenblöcke. Titel, Grenzen und IDs durch
fachlich sinnvolle Abschnitte ersetzen. Jede Skriptseite muss genau einem Abschnitt
zugeordnet sein, auch wenn sie später vom Lernen ausgeschlossen wird.
`reports/import-review.md` enthält dazu Quellenübersicht und einen Vorschautext je Seite.

```json
{
  "sections": [{"id":"sec-1", "source":"skript", "pages":[1,2], "title":"Einführung", "needs_review":false}],
  "exclusions": [{"source":"skript", "page":2, "text":"exakter gestrichener Text", "reason":"im Skript gestrichen", "reviewed":true}],
  "figures": []
}
```

Ohne `text` schließt ein Eintrag eine ganze Seite vom Lernmaterial aus. Der volle
Quellentext bleibt erhalten. Annotationen liefern nur Kandidaten: eingebrannte
Streichungen sind damit nicht sicher erkennbar. Vor Freigabe Originalseiten ansehen.

```powershell
python -m pipeline review --reviewer "Name oder Agent mit dokumentierter Sichtprüfung"
python -m pipeline plan
```

Eine Freigabe ist kein Nachweis der fachlichen Richtigkeit. Sie bestätigt den bewusst
geprüften Strukturstand. Änderungen an Konfiguration, Manifest oder Struktur machen
sie ungültig. `review` niemals ausführen, nur um die Sperre zu umgehen.

## 3. Eigenes LLM verwenden

**Agentenmodus:** Agent im Kursrepo starten, `AGENTS.md` lesen lassen und die JSON-Aufträge
aus `build/jobs/` bearbeiten. Jeder Auftrag enthält Kontext, Schicht/Vertrauen,
Antwortschema und Hash. Antworten nach `build/results/<job-id>.json` schreiben.

```powershell
python -m pipeline accept --model "tatsächlich verwendetes Modell"
```

**API-Modus:** In `course.yaml` URL einschließlich `/v1` (wenn der Anbieter das
verlangt), Modell und optional Preise je Million Tokens eintragen. Keine Schlüssel
in YAML schreiben. `api_key_env` nennt die Umgebungsvariable mit dem Schlüssel.
`token_limit_field` kann für ältere kompatible Server `max_tokens` sein; Standard
ist `max_completion_tokens`. Kein Modell oder Preis wird fest eingebaut.

```powershell
python -m pipeline run-api                       # nur Plan, keine Netzaufrufe
python -m pipeline run-api --start --max-jobs 1   # ausdrücklich ein Auftrag
```

Kostenschätzung: Zeichen/3 als Tokenheuristik, Ausgabeobergrenze je Auftrag,
konfigurierte Preise. Ohne Preise wird kein Geldbetrag behauptet. Keine Geldlimit-
Garantie; `max-jobs` begrenzt die Auftragsanzahl. Aufrufe erfolgen einzeln, ohne
automatische Wiederholungen. Fortsetzen verarbeitet nur fehlende/veraltete Ergebnisse.
API- und Agentenergebnisse bleiben fachlich ungeprüft. Referenzen und echtes
Aufgabenwortlaut werden strukturell geprüft; Halluzinationen sind dadurch nicht ausgeschlossen.

## 4. Erzeugen und exportieren

```powershell
python -m pipeline build
python -m pipeline offline
python -m pipeline export
python -m pipeline export --compile   # optional: XeLaTeX oder LuaLaTeX
```

Ein Teilstand ist zulässig und wird im Abdeckungsbericht sichtbar. `content/` enthält
vollständige extrahierte Abschnittstexte; `learning/` die separate KI-Lernfassung.
Echte und erzeugte Fragen liegen getrennt in `exams/`. Musterlösungen bleiben
KI-Erklärung. Neue Aufgaben haben keine belegten Prüfungspunkte.

`build/exports/` enthält Einzeldateien und Gesamtausgaben, Anki-TSV/APKG und ein ZIP.
Stabile Anki-IDs vermeiden neue Notizen bei wiederholtem Import, solange Kurs- und
Karten-IDs erhalten bleiben. TSV ist ein zusätzlicher einfacher Importweg.
LaTeX unterstützt grundlegende Überschriften, Aufzählungen, Fettdruck und häufige
Mathematikbefehle. Komplexe Tabellen/Umgebungen und SVG-Einbettung benötigen weitere
Layoutarbeit; unbekannte TeX-Befehle bleiben als Text erhalten. Kein Shell-Escape.
Das Layout muss visuell geprüft werden; ohne installierte TeX-Engine erfolgt kein PDF-Test.

Alternativ erzeugt `python -m pipeline render-pdf` direkte PDFs ohne TeX-Installation,
einschließlich Tabellen, Formeln und eigener SVGs. `export-notebooklm` erzeugt
eigenständige Kapitelkontexte, `anki` die erweiterten Kartentypen und Kapitelpakete.
Konfiguration und Reader-Ablauf: [Reader und Exporte](reader-und-exporte.md).

## 5. Abbildungen

LLM-Ergebnisse `learning/figure-jobs.json` enthalten Rekonstruktionsaufträge. Ein Agent
betrachtet das Original und erstellt anschließend `figures/reconstructed/<id>.svg`.
Sichtprüfung ist erforderlich. Für Ausschnitt/Blankovorlage in `structure.json`:

```json
{"id":"abb-01", "source":"skript", "page":2, "bbox":[30,80,500,400]}
```

Koordinaten in PDF-Punkten, Ursprung links oben. `python -m pipeline figures` erzeugt
lokale Ausschnitte und entfernt `class="answer"`-Elemente aus vorhandenen SVGs.
Bewertungsmerkmale und typische Fehler stehen im zugehörigen Rekonstruktionsauftrag.

## 6. Lernen und Pflege

```powershell
python -m pipeline progress due
python -m pipeline progress record sec-1 definition 3 --fehler "Begriff verwechselt"
python -m pipeline progress record abb-01 zeichnung 2 --skizze nein --fehler "Achsen vergessen"
```

Lernagenten folgen `AGENTS.md`: offene Fragen einzeln, Lösung erst nach Antwort,
Bewertung gegen Quelle, Ergebnis bestätigen lassen. Persönlicher Fortschritt bleibt lokal.

Werkzeugaktualisierung aus dem Generator: `python -m pipeline upgrade <kursrepo>`.
Lokale Werkzeugänderungen vorher sichern; Upgrade erzeugt nur eine prüfbare Änderung.
Ohne installiertes Git oder ohne Git-Repo sichert `upgrade` die bisherigen Werkzeuge
vorher unter `build/upgrade-backups/<kennung>/`. Der Sicherungspfad wird angezeigt.
Struktur-/Ergebnisformate müssen bei künftigen inkompatiblen Versionen migriert werden.
Der Werkzeugumfang umfasst jetzt auch Reader-Quellen, Tests, Startskript und
mitgelieferte Anleitungen. `.lernrepo-tools.json` erkennt selbst committete lokale
Anpassungen; diese zuerst separat sichern und bewusst abgleichen. Ein Upgrade
übernimmt keine Kursdaten und führt keine automatische Freigabe oder Verarbeitung aus.

## 7. GitHub

Mit Git hat jeder Kurs sein eigenes Git-Repo. Ohne Git kann ein Kursordner später
mit `git init -b feature/course-bootstrap` und einem eigenen Initialcommit versioniert
werden. Originale, extrahierte Volltexte, Fortschritt und
Schlüssel bleiben ignoriert. Auch abgeleitete Skriptfassungen und Abbildungsexporte
vor einem Upload anhand der Nutzungsrechte prüfen. Der Entwicklungsmethodik-Pilot
bleibt vorerst vollständig lokal; das Titelblatt beschränkt Weitergabe/Bereitstellung.

Änderungen: Feature-Branch → Conventional Commit → privater PR → grüne CI →
autorisierter Squash-Merge. Das Werkzeug richtet keine Remotes, Schutzregeln oder
Releases selbst ein. Ein Veröffentlichungsauftrag kann später auf konkrete Inhalte
und ein bestimmtes privates Zielrepo bezogen werden.
