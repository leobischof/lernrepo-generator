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

Die allgemeinen Export-/Reader-Werkzeuge wurden am 16.10.2026 ergänzt:
`chapters.py` liefert die fachunabhängigen Kapitel; `artifacts.py` bindet positive
Dateilisten und relevante Exportquellen an den aktuellen Build. PDF, NotebookLM,
Anki, Reader und HTML haben jeweils getrennte Module und Ausgabeverzeichnisse.
`release.py` verpackt ausschließlich aktuelle, unveränderte gelistete Artefakte.
`new` kopiert alle Laufzeitdateien; `upgrade` prüft deren gespeicherte Hashes und
Git-Änderungen bzw. sichert ohne Git den ersetzten Werkzeugbestand vollständig.

Weiterhin offen bleiben vollständige Bereinigung beliebiger komplexer Scans,
semantisch geprüfte Kapitelgrenzen, automatisch verifizierte SVGs und eine fachliche
Freigabe. Bildgeometrie und lokale Audiozuordnung liefern ungeprüfte Vorschläge.
Kursspezifische Notenschlüssel werden nicht geraten. PDF-Layouts werden technisch
getestet, benötigen für reale Formeln/Tabellen/Zeichnungen aber eine Sichtprüfung.
Nicht unterstützte Formeln bleiben als sichtbarer Quelltext mit Warnung erhalten.
