# Kapitel, Exporte und PDF-/Audio-Reader

Die Werkzeuge sind fachunabhängig. Es werden keine Inhalte aus der technischen
Referenzvorlesung übernommen. Originale, rohe Extraktionen, Audios und persönlicher
Fortschritt bleiben lokal. KI-Lernmaterial und automatische Zuordnungen sind ungeprüft.

## Kapitel und Namen

In `course.yaml` kann `course.export_prefix: TP` gesetzt werden. Ohne dieses Feld
gilt die Kurs-ID. Das Präfix darf Buchstaben, Ziffern, `-` und `_` enthalten.
Kapitelgruppen ergänzen die bestehende `curation/structure.json`:

```json
{
  "sections": [
    {"id":"sec-energie","title":"Energie","source":"skript","pages":[1],"needs_review":false},
    {"id":"sec-arbeit","title":"Arbeit","source":"skript","pages":[2],"needs_review":false}
  ],
  "chapters": [
    {"id":"grundlagen","title":"Grundlagen","sections":["sec-energie"]},
    {"id":"anwendung","title":"Anwendung","sections":["sec-arbeit"]}
  ],
  "exclusions": [],
  "figures": []
}
```

Jeder Abschnitt gehört genau einem Kapitel an; die Reihenfolge bestimmt die
Kapitelnummer. Ohne `chapters` wird jeder Abschnitt ein Kapitel. Änderungen machen
die Quellen-/Strukturfreigabe ungültig. Vor `review` die tatsächlichen Quellen prüfen.

## Textkorrekturen und Abbildungen

`curation/text-corrections.json` enthält ein Objekt mit `corrections`:

```json
{"corrections":[{"source":"skript","page":1,"before":"Energic","after":"Energie",
"source_sha256":"SHA-256 aus sources/manifest.json","reason":"gegen Original geprüft","reviewed":true}]}
```

Der tatsächliche SHA-256 muss exakt stimmen; der Beispieltext ist kein gültiger Hash.
Der Originaltext muss genau einmal vorkommen, optional legt `count` eine andere
erwartete Anzahl fest. Die Anwendung erfolgt auf einer Arbeitskopie, nie auf der
rohen Extraktion. Korrekturen werden in `inspect` sichtbar und sind Teil der Freigabe.

`detect-figures` schreibt ausschließlich `reports/figure-candidates.json`.
PDF-Rasterbilder und Vektorgruppen sind nur geometrische Kandidaten; bei Scans kann
das auch die ganze Seite sein. Die Person kuratiert daraus `structure.figures`
mit `id`, `source`, `page`, `bbox`, optional `title`, `description`, `must_know` und
`kind: table`. Quellen und Bounding-Boxes vor Übernahme visuell prüfen.
Eigene Rekonstruktionen liegen unter `figures/reconstructed/<id>.svg`.
`figures` erzeugt lokale Originalausschnitte und Blankovorlagen aus `class="answer"`.

`figure-icons` liest `curation/icon-library.json`, Feld `icons`, mit Einträgen
`id`, `path`, `license`, `copyright`, `source`. Die lokalen SVGs werden an Gruppen
mit `data-icon="<id>"` eingebettet. `data-width`/`data-height` setzen die Größe.
Externe oder aktive SVG-Inhalte werden abgelehnt. Lizenztexte und Provenienz werden
mitgeführt. Das Werkzeug lädt keine Icon-Bibliotheken aus dem Netz.

## Lernprodukte

```powershell
python -m pipeline build
python -m pipeline export
python -m pipeline render-pdf
python -m pipeline export-notebooklm
python -m pipeline anki
python -m pipeline exam-analysis
```

- `build/exports/`: bisherige Markdown-/TeX-Ausgaben und Basiskarten sowie zusätzliche
  Anki-Pakete aller Typen. `anki-gesamt.apkg` hier bleibt aus Kompatibilitätsgründen
  das kompakte bisherige Basiskartenpaket; `<Präfix>-Anki-alle-Typen.apkg` ist vollständig.
- `build/pdf/`: Kapitel-Skript, Kapitel-Zusammenfassung, Gesamtskript und Musterlösungen.
  Ohne TeX-Installation; Standardformeln über matplotlib. Nicht unterstützte Formeln
  bleiben sichtbar und werden gemeldet. Eigene SVGs werden für PDF-kompatible Pfeile
  und Linien angepasst; Original-PDFs und Originalausschnitte werden nicht eingebettet.
- `build/notebooklm/`: je Kapitel Anleitung, Leitfaden, zugeordnete echte Fragen,
  Gesamtskript als Rahmen und Abbildungsbeschreibungen. Ausschlüsse bleiben markiert.
  Audiotitel verwenden bei einer einzigen Kapitelquelle das Kapitelpräfix.
- `build/anki/anki-gesamt.apkg`: Basiskarten, optionale Lückentexte, Prüfungsfragen
  mit KI-Musterlösungen, SVG-Zeichenkarten und vorhandene Studierendenkarten.
  Zusätzlich ein APKG pro Kapitel. Unzugeordnete Karten sind nur im Gesamtpaket.
  Tabellen werden nicht als Zeichenkarten ausgegeben. GUIDs bleiben bei gleicher
  Kurs-/Karten-ID stabil. Lückentextantworten ergänzen `kind: cloze` und
  `cloze: "{{c1::Energie}} bleibt erhalten."`; alte Antworten bleiben schemafähig.
- `exams/frequency-analysis.*`: nur echte Fragen, keine KI-Trainingsfragen.
  Für einzelne Klausurquellen kann `exam_date: '2026-04-01'` in `sources` stehen.
  Fragensammlungen erhalten keinen geratenen gemeinsamen Termin.

Zuordnungen echter Fragen stehen optional in `curation/exam-links.json`:
`{"questions":{"<vollständige-Fragen-ID>":["sec-energie"]}}`. Ohne fachlich
kuratierte Zuordnung werden Fragen ausdrücklich unzugeordnet angezeigt.

## Audio und Reader

Python >=3.11 und Node.js >=22.13 (oder >=24) werden für den Build benötigt.
PDF.js ist im Lockfile festgelegt; fertige Reader-Pakete benötigen kein Node.js.

```powershell
npm ci --prefix interactive --ignore-scripts
python -m pipeline audio-reader
python -m pipeline serve --open
```

`audio-reader` baut direkte PDFs und den Reader ohne Modellaufruf. Audio ist optional:
unter `audio/` etwa `TP-1-Audio.wav` ablegen. Alternativ beliebige lokale Namen in
`course.yaml` ausdrücklich einem Kapitel zuordnen:

```yaml
reader:
  audio:
    grundlagen: audio/meine-aufnahme.m4a
```

Unbekannte Kapitel oder mehrere Aufnahmen je Kapitel stoppen den Build. Das Werkzeug
benennt Nutzermedien nicht um. Unterstützt sind M4A, MP3, WAV, OGG, OPUS, MP4 und WEBM;
die konkrete Wiedergabe hängt von Browser und Codec ab.

```powershell
python -m pipeline sync-audio                    # nur Plan
python -m pip install -e '.[audio]'              # optionale lokale ASR
python -m pipeline sync-audio --start --model tiny
python -m pipeline interactive
```

Erst `--start` lädt ein lokales Whisper-Modell, falls nötig mit initialem Download.
Aufnahmen und Transkripte werden nicht hochgeladen. Der Cache bindet Audiohash und
Modell; PDF-Zuordnung erfolgt lexikalisch und kann falsch oder lückenhaft sein.
Timelines unter `curation/interactive/<Präfix>-<N>-Timeline.json` binden Kapitel,
PDF- und Audiohash. Änderungen daran erfordern einen neuen Reader-Build.
Manuell bearbeitete/geprüfte Timelines bleiben erhalten; neue Vorschläge landen in
`build/transcripts/`. Im Reader können Zeiten/Markierungen korrigiert und heruntergeladen
werden. Die Download-Datei bewusst anstelle der kuratierten Timeline übernehmen.

Der Server bindet nur `127.0.0.1`; Standardadresse `http://127.0.0.1:8765/reader.html`.
Suche, PDF-Navigation und Zoom funktionieren auch ohne Audio. Folgen ist optional.
„Kapitel offline speichern“ lädt PDF, Audio und Timeline in diesen Browser; zunächst
Service Worker und Kapitelcache anlegen, dann die Verbindung trennen. Ein Reader-Update
ersetzt den bisherigen Kapitelcache; gewünschte Kapitel danach erneut speichern.
PWA-Installation erfolgt über das Browsermenü. Mobilgeräte benötigen für einen
anderen Rechner einen separat bereitgestellten HTTPS-Zugang; der lokale Server öffnet kein LAN.

## HTML und lokale Pakete

```powershell
python -m pipeline package-reader
python -m pipeline release
```

`build/standalone/` enthält vollständige HTML-Kapitel mit eingebettetem PDF.js,
PDF, optionalem Audio, Zeitmarkierungen und Lizenzen. Einmal geladen benötigt ein
Kapitel keine weiteren Anwendungsdateien. Das Laden lokaler HTML-Dateien hängt vom
Browser ab; iOS-Dateivorschau ist kein vollständiger Browser. Dort die PWA verwenden.

`build/release/` enthält ZIPs je Exportart und ein Gesamt-ZIP. Eingepackt werden nur
gelistete unveränderte Artefakte des aktuellen Builds, keine zufälligen Dateien aus
`build/`. Geänderte Exportquellen führen zur Ablehnung. Die ZIP-Zeitstempel sind fest;
gleiche Eingabedateien ergeben gleiche ZIP-Bytes. Es erfolgt kein Upload.

Windows: `dev.ps1 setup`, danach `build`, `serve`, `test`, `package` oder `release`.
`-NoOpen` verhindert Browseröffnung, `-Port` wählt den lokalen Port.
