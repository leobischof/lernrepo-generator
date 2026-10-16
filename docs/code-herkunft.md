# Herkunft wiederverwendeter Bausteine

Vorlage: lokales privates Repository „Grundlagen der Industriebetriebslehre und
Innovation“, im Auftrag seines Nutzers ausgewertet am 12.10.2026.

Unverändert übernommene technische Module:

- `pipeline/srs.py`: reine Wiederholungsplanung.
- `pipeline/svg_blank.py`: Blanko-SVG aus Antwortmarkierungen.
- `pipeline/apkg_reader.py`: Lesen verschiedener Anki-Paketgenerationen ohne Medienübernahme.
- `.github/scripts/conventions.py` und `tests/test_conventions.py`: Git-Konventionen
  und deren Tests, übernommen für dieselben Regeln.

Die übrigen Module wurden für den Generator neu erstellt. Vorlesungsinhalte,
Prüfungsfragen, Bilddateien und persönliche Lernstände wurden nicht übernommen.
Der Eigentümer hat am 12.10.2026 die öffentliche Veröffentlichung dieses Generators
einschließlich wiederverwendeter technischer Bausteine ausdrücklich beauftragt.
Das ursprüngliche Wissensrepo und die lokalen Vorlesungsunterlagen bleiben privat.

## Allgemeine Lernwerkzeuge vom 16.10.2026

Technische Referenz: Industriebetriebslehre-Commit
`5bc8fe2307959610243081eb4c076384d89e79d5`. Im Auftrag des Nutzers wurden ausschließlich
Werkzeuge für die fachunabhängige Nutzung übernommen bzw. angepasst:

- `pdf_math.py`, `svg_geometry.py`, `svg_mupdf.py` sowie synthetische SVG-Tests:
  Formelbilder und SVG-Kompatibilität mit dem PDF-Renderer.
- `interactive/reader-{app,navigation,timeline,offline,service-worker,singlefile-boot}.mjs`,
  Reader-HTML/CSS und Timeline-Tests: Kursnamen, Speicher- und Cache-Namensräume,
  Ressourcenpfade und Aktualisierungsverhalten wurden verallgemeinert/korrigiert.
- `reader_serve.py`: Loopback-Server mit Medien-Byte-Ranges, argv-Schnittstelle ergänzt.
- `audio_alignment.py`: reine lexikalische Zuordnung aus `audio_sync.py`.
- `audio_topics.py`: Themenintervalle; Inhaltsverzeichnis-Erkennung ist fachunabhängig.
- `reader_package.py`: Base64-/CSS-/HTML-Hilfsfunktionen aus `package_reader.py`;
  Build und Dateilisten sind an das Generator-Kapitelmodell angepasst.
- PDF.js-Version und Lockfile als technische Abhängigkeitsvorlage, ohne dessen
  Installation oder Binärdateien einzuchecken. PDF.js-Lizenz wird im Reader mitgeführt.

Das Reader-Icon wurde hier als allgemeines Buchsymbol erstellt. Keine Kurs-Icons,
Abbildungen, Prüfungsfragen, Skripttexte, Original-PDFs, Audios oder Timelines der
Referenz wurden übernommen. Neue Tests und Browserdaten sind ausschließlich synthetisch.
