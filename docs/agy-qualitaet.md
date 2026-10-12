# AGY soll die Arbeit selbst fertigstellen

Die fachliche Reparatur gehört zum Worker-Auftrag. Der betreuende Agent verbessert
die Anleitung und prüft Stichproben; er schreibt mangelhafte Worker-Ergebnisse nicht
heimlich um und meldet anschließend einen erfolgreichen AGY-Test.

## Arbeitsauftrag

`python -m pipeline prepare-agent <job-id> --page <n>` erstellt ein isoliertes Paket
mit Quelle, Originalbild, bisherigem Ergebnis und `WORKFLOW.md`. Die versionierte
Anleitung kommt aus `pipeline/agent_guideline.py` und wird mit den Werkzeugen in
neue und bestehende Kurse übernommen. Sie gilt unabhängig vom verwendeten LLM.

Zunächst eine anspruchsvolle Seite bearbeiten lassen, anschließend kleine Pakete
von höchstens sechs Seiten. Diagramme und dichte Tabellen möglichst einzeln.
Agenten müssen Originalbilder tatsächlich öffnen. Leere OCR ist kein Grund,
lesbare Bilder aus dem Lernmaterial wegzulassen. Quelleninventar → Entwurf →
Vergleich jeder Aussage/Zelle mit dem Original → eigene Korrektur → Abgabe.

Die Delegation erhält den außerhalb des Pakets abgelegten Prompt; nur result.json
und page-review.json dürfen verändert werden. Kein Git, kein Shellzugriff und kein
Durchsuchen des ganzen Kursrepos sind für diese Aufgabe nötig. Nach den beiden
Dateien sofort abschließen, damit ein unnötiger Nachlauf kein Zeitlimit auslöst.

## Abnahme und Rückmeldung

`accept-agent` verlangt bei neuen Paketen ein konkretes Quelleninventar mit Ziel
im Ergebnis sowie dokumentierte Kontrollen von Vollständigkeit, Tabellenzellen,
unbelegten Aussagen und Karten-Lernzielen. Eine gemeldete offene Kontrolle verhindert
die Übernahme. Diese Prüfungen kontrollieren die Dokumentation, nicht automatisch
die fachliche Wahrheit; eine Selbstprüfung bleibt entsprechend gekennzeichnet.

Der betreuende Agent liest Runner-Status und tatsächliche Dateidifferenzen. Ein
Timeout bleibt ein fehlgeschlagener Lauf, auch wenn Ergebnisdateien vorhanden sind.
Stichproben müssen gegen das Original erfolgen, nicht gegen die alte LLM-Antwort.
Bei Fehlern: konkreten Quellenwiderspruch an AGY zurückgeben, korrigieren lassen und
erneut prüfen. Keine manuellen fachlichen Änderungen an einem als AGY-Erfolg
bewerteten Testoutput. Bei Quotenfehlern nicht in einer Wiederholungsschleife laufen.

Wiederkehrende Fehler werden als allgemeine Regel mit einem Gegenbeispiel in der
Worker-Anleitung ergänzt. Danach denselben schwierigen Fall aus seinem alten
Ausgangszustand erneut bearbeiten lassen, ohne nachträgliche Reparatur und ohne
die Lösung als manuell erstellte Transkription vorzugeben. Der Test dokumentiert
Ausgangszustand, Laufstatus, Selbstkorrekturen, verbleibende Fehler und Prüfergebnis.
Ein erfolgreicher Einzelfall ist noch kein Nachweis für alle Seiten einer Vorlesung.

## Fertig bedeutet überprüfbar fertig

`python -m pipeline audit` trennt formale Auftragsantworten, Produktverweise,
Modell-Selbstprüfungen und unabhängige Quellenprüfungen. Fehlende Tabellen,
Bildinhalte und unlesbare Stellen bleiben sichtbar offen. SVG-Aufträge zählen
erst nach Erstellung einer tatsächlichen Datei und Sichtprüfung als fertige SVGs.
Echte Prüfungsfragen dürfen ohne passenden Primärskript-Kontext keine erfundenen
Musterlösungen oder daraus abgeleiteten Lernkarten erhalten.
