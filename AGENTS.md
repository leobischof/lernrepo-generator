# Lernrepo-Generator: Arbeitsanleitung

Sprache: Deutsch. Dieses Projekt erzeugt eigenständige Vorlesungsrepos. Lies
`docs/produktentscheidungen.md` und `docs/arbeitsablauf.md` vor Änderungen.

## Pflege

- Änderungen auf Feature-Branches, Conventional Commits, Pull Requests, grüne CI,
  Squash-Merge. Nie Force-Push oder direkt auf main committen. Kein automatischer Merge.
- Ursprungsrepo Industriebetriebslehre nur als Referenz lesen; dessen Materialien
  und lokale Änderungen nicht übernehmen. Wiederverwendeten Code dokumentieren.
- `pipeline/` ist die Werkzeugquelle. Neue Kurse erhalten eine eigenständige Kopie.
  Bestehende Kurswerkzeuge nur mit `upgrade` aktualisieren (vorher lokale Änderungen prüfen).
- Originale, extrahierte Volltexte, Schlüssel und persönlichen Fortschritt lokal halten.
  Der Generator ist auf ausdrücklichen Auftrag öffentlich. Erzeugte Kursrepos bleiben
  standardmäßig privat; deren Inhalte nie ohne eigenen Veröffentlichungsauftrag hochladen.
- KI-Arbeit über `pipeline.ailog.append` protokollieren. Unbekannte Tokenzahlen null,
  niemals erfinden. `python -m pytest` muss grün sein.

## Arbeit in einem erzeugten Kursrepo

`course.yaml` beschreibt Kurs und Quellen. `curation/structure.json` ist die
Quelle der Wahrheit für Abschnitte und explizite Ausschlüsse. `review` bindet eine
Freigabe an den aktuellen Quellen- und Strukturstand; Änderungen machen sie ungültig.
Generiertes `content/`, `learning/`, `exams/`, `reports/` nicht von Hand ändern.

1. `python -m pipeline ingest`, dann Quellen, Seiten und Streichungen prüfen.
2. Struktur kuratieren, Ausschlüsse mit Begründung eintragen; `review` ausführen.
3. `plan` erstellt begrenzte Arbeitsaufträge und Kostenschätzung.
4. Agent: jeden JSON-Auftrag in `build/jobs/` lesen und eine Antwort nach seinem
   `response_schema` in `build/results/<job-id>.json` schreiben. `accept` übernimmt
   geprüfte Antworten nach `curation/results/`. Alternativ `run-api --start`.
5. `build`, `export`, `offline`; ungeprüfte Inhalte sichtbar kennzeichnen.

Jede fachliche Erklärung mit Quelle und PDF-Seite belegen. Gedruckte Seiten nur
angeben, wenn bekannt. Keine Inhalte erraten. Studentische Unterlagen sind unverifiziert.
Echte Aufgaben wortgetreu mit Herkunft übernehmen; neue Aufgaben ausschließlich als
KI-Übungsfragen führen. Lösungen nicht aus Prüfungsangaben als gesichert ableiten.
Streichungen nur nach Sichtprüfung ausschließen, keine automatische Gewissheit behaupten.
SVG-Rekonstruktionen gegen Original prüfen; Antwortbestandteile mit `class="answer"`.
Für Hörspiele nur belegte Inhalte verwenden und Unsicherheiten im Kontext behalten.

## Lernen

Modus wählen: Verstehen, offene Einzelabfrage, Prüfungssimulation, Zeichnen oder
fällige Wiederholung. Bei Abfragen zuerst Antwort abwarten. Echte Simulationen nur
mit echten Aufgaben; KI-Aufgaben sichtbar als Training anbieten. Gegen Quellen
bewerten, Ergebnis 0–5 vorschlagen, Bestätigung abwarten, mit `progress record`
speichern. Fortschritt niemals committen. Zeichnungen anhand must_know prüfen;
unleserliche Elemente als unsicher behandeln.

## GitHub-Regeln für diesen Generator

- `main`: Änderungen ausschließlich per PR, auch für Eigentümer/Admins, ohne Bypass.
- `qa` und `konventionen` müssen grün sein; Branch muss aktuell sein.
- Alle PR-Diskussionen müssen aufgelöst sein; nur Squash-Merge, lineare Historie.
- `main` darf nicht gelöscht werden; Force-Push ist auf allen Branches verboten.
- Branches: `typ/beschreibung`, Kleinbuchstaben; erlaubte Präfixe und Conventional
  Commits stehen in `.github/scripts/conventions.py`. Titel höchstens 72 Zeichen.
- CODEOWNERS fragt @leobischof als Reviewer an. Freigaben sind nicht zwingend,
  damit eigene PRs möglich bleiben. Mergen nur mit ausdrücklicher Autorisierung.
- Bereits gepushte Commits nicht umschreiben; bei Bedarf `git merge origin/main`.
- Schutzregeln nur auf ausdrücklichen Auftrag ändern. Reproduzierbare Einrichtung:
  `python scripts/configure_github.py --repo OWNER/REPO --apply`.
