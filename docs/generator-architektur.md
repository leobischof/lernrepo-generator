# Architektur und Abgrenzung

`pipeline/generator.py` erzeugt eine eigenständige Werkzeugkopie. `course.yaml`
enthält Vorlesung, beliebig viele Quellen, gewünschte Produkte, Chunkgrößen und
LLM-Konfiguration. Pfade stehen zentral in `pipeline/config.py`.

| Schicht | Ort | Aussage |
|---|---|---|
| Original | input/, sources/originals/ | Maßgebliche lokale Eingabe |
| Extraktion | sources/extracted/ | Ungeprüfter PDF-/OCR-/Anki-Text |
| Kuratierung | curation/structure.json, results/ | Geprüfte Struktur; KI-Ergebnisse separat ungeprüft |
| Quellentext | content/ | Deterministisch aus Extraktion, keine LLM-Paraphrase |
| Lernmaterial | learning/, exams/ | KI-Erklärungen, Karten, Aufgaben; Herkunft sichtbar |
| Prüfung | reports/ | Strukturelle Validierung und Abdeckung, keine fachliche Zertifizierung |

Die erste Version hält die quellentreue Fassung bewusst auf der Extraktionsschicht.
Eine spätere Bereinigung braucht ein explizites, nachvollziehbares Korrekturformat
für OCR, Formeln, Tabellen und Gliederung. Die Bezeichnung „bereinigt“ darf erst
nach entsprechender Verarbeitung und Prüfung verwendet werden.

Freigabe-Hash = Konfiguration + Manifest + Struktur. Auftrags-Hash = konkreter
Kontext + Prompt + Antwortschema. Beide LLM-Modi nutzen dieselbe Prüfung.
Originale werden anhand SHA-256 registriert; Extraktionen erhalten eigene Hashes.
Kein ausgelassener Quellentext wird als vollständig verarbeitet ausgegeben.

`curation/jobs-index.json` speichert nur strukturelle Auftragsmetadaten für Offline-
Prüfungen ohne Originale. Die Wortlautkontrolle echter Aufgaben erfolgt lokal bei
der Übernahme. Offline kann Quellenbezug/Schema/Hash geprüft werden, aber keine
erneute Textgegenprobe gegen nicht vorhandene Originale.

Noch auszubauen gegenüber der Industriebetriebslehre-Vorlage: vollständige
Bereinigung komplexer Scans, automatische Layout-/Abbildungserkennung für beliebige
Skripte, semantische Kapitelgrenzen, verifizierte SVGs, Prüfungshäufigkeit nach Termin,
kursspezifische Notenschlüssel, anspruchsvolle Anki-Typen und aufwendige PDF-Layouts.
Diese Punkte sind nicht mit einem bloßen Umbenennen der Vorlage gelöst.
