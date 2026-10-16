# Fachunabhängiger Ausbau der Lernwerkzeuge

## Auftrag und Ausgangspunkt

Am 16.10.2026 beauftragte der Nutzer nach dem Vergleich beider Repos einen
separaten Plan, die Ergänzung der fehlenden Funktionen, Tests und einen Pull Request.
Referenz: Industriebetriebslehre `5bc8fe2307959610243081eb4c076384d89e79d5`;
Generator-Basis: `996e2742734e4829771d9cac00d94f3c67540b58`.
Die Referenz bleibt unverändert. Nur allgemeiner Werkzeugcode wird übernommen,
keine Skripte, Fragen, Audios, Timelines oder Abbildungsdateien des Kurses.

## Architekturentscheidung

Empfohlen und umgesetzt wird ein additiver Ausbau des vorhandenen Generators.
Ein vollständiges Kopieren der Referenz würde deren feste Kapitel, Dateinamen und
Scan-Geometrie übernehmen. Ein gemeinsames externes Laufzeitpaket würde dagegen die
zugesagte Eigenständigkeit erzeugter Kurse aufheben. Deshalb bleiben Werkzeuge und
Reader-Quellen Bestandteil jedes erzeugten Kursrepos.

`course.yaml` bleibt in Version 1 lesbar. Kapitel sind optionale Gruppen expliziter
Abschnitts-IDs in `curation/structure.json`; ohne Kapiteldefinition bildet jeder
Abschnitt ein Kapitel. Ein kurzer Exportpräfix ist konfigurierbar, sonst gilt die
Kurs-ID. Bestehende Agentenantworten bleiben gültig; neue Kartenfelder sind optional.

## Lieferumfang

1. Kapitelmodell und konsistente Exportnamen; `new` kopiert alle Laufzeitdateien.
   `upgrade` prüft Änderungen aller verwalteten Werkzeuge, erhält Kursdaten und
   sichert Werkzeuge ohne Git vor dem Ersetzen. Keine automatische Aktualisierung.
2. Explizite OCR-/Textkorrekturen mit Originaltext-Gegenprobe und Protokoll;
   automatische PDF-Abbildungskandidaten ohne automatische fachliche Freigabe.
   Kuratierte SVGs, Blankovorlagen und lokal bereitgestellte lizenzierte Icons
   werden unterstützt. Kein festes GIL-Seitenlayout und keine geratenen Zeichnungen.
3. Eigenständige NotebookLM-Kontextdatei je Kapitel mit Leitfaden, zugeordneten
   echten Fragen und gesamtem Skript als Rahmen. Kursabhängige Audiotitel.
   Direkter PDF-Export aus Markdown mit Tabellen, Formeln, eigenen SVGs und
   Inhaltsverzeichnis; editierbare TeX-Exporte bleiben verfügbar.
4. Anki-Basiskarten, Lückentexte, echte Prüfungsfragen, Zeichenkarten und importierte
   Studierendenkarten mit Herkunftskennzeichnung und stabilen IDs. Kapitelpakete
   und Gesamtpaket. Häufigkeitsanalyse zählt nur belegte echte Aufgaben und bekannte
   Prüfungstermine; keine Prüfungswahrscheinlichkeiten oder erfundenen Notenschlüssel.
5. PDF-/Audio-Kapitelreader mit Suche, Zoom, Navigation, laufender Wiedergabe,
   optionalem Folgen, Zeitmarkierungen, Offline-Kapiteln und eigenständigen HTMLs.
   Fehlendes Audio verhindert das Lesen nicht. Timeline-Identität bindet Kapitel,
   PDF und Audio per SHA-256; ungültige oder veraltete Timelines stoppen den Build.
   Lokale optionale Whisper-Transkription und lexikalische Zuordnung erzeugen
   ungeprüfte Vorschläge. Kuratierte Timelines werden niemals überschrieben.
6. Deterministische Release-ZIPs; synthetischer vollständiger Durchlauf auch nach
   `new` und `upgrade`, Python-/JS-Tests und lokale Browserprüfung des Readers.

## Verbindliche Grenzen

- Python >=3.11; Node.js >=22.13 für Reader-Build, nicht für die Wiedergabe.
- Deutsch in Dokumentation und Oberfläche; Titel und IDs aus Kurskonfiguration.
- Keine kostenpflichtigen Modellaufrufe oder Übertragung von Kursmaterialien.
- Originale, Extraktionen, Audios und persönlicher Fortschritt bleiben git-ignoriert.
- Automatische Vorschläge sind ausdrücklich ungeprüft; fachliche/visuelle Freigabe
  wird weder von Tests noch von heuristischer Erkennung behauptet.
- Es wird keine allgemeine fehlerfreie Scanbereinigung behauptet: OCR-Korrekturen
  bleiben explizit kuratiert; Kapitelgrenzen und Zeichnungen benötigen Sichtprüfung.
- Kein Merge, Release-Upload oder Ändern von GitHub-Schutzregeln.

## Abnahmekriterien

Ein synthetischer Kurs mit zwei Kapiteln, anderem Präfix und verschiedenen Quellen
durchläuft Import, geprüfte Korrektur, Freigabe, Agentenannahme, Build, Exporte,
Reader, HTML und Release. Derselbe Ablauf muss nach einem Werkzeugupdate funktionieren.
Negative Tests decken veränderte Quellen, veraltete Zeitmarkierungen, Pfadausbrüche,
lokal geänderte Werkzeuge und erfundene Prüfungstermine ab. Im Browser werden PDF,
Kapitelwechsel, Audio-Seeking, Offline-Speicherung und ein eigenständiges HTML geprüft.
Reale Nutzerunterlagen oder Whisper-Modellaufrufe sind dafür nicht erforderlich.
