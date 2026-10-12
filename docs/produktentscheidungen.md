# Produktentscheidungen

Festgelegt im Gespräch am 12.10.2026:

| Entscheidung | Festlegung |
|---|---|
| Organisation | Zentraler Generator; jede Vorlesung ein eigenständiges Repo |
| LLM | Gleichwertiger Agenten- und API-Modus mit gemeinsamem Ergebnisformat |
| Erste API | Konfigurierbarer OpenAI-kompatibler Endpunkt; lokale Server möglich |
| Erster Meilenstein | Vollständiger Durchlauf Import → Quellen → Lernmaterial → Anki/LaTeX → Prüfungen |
| Pilot | Entwicklungsmethodik, lokaler Ordner `Entwicklumgsmethodik` |
| Primärquelle Pilot | `EM_Zusammengefügt_gestrichen.pdf`, 475 Seiten |
| Streichungen | Im Quellentext erhalten; nach Sichtprüfung aus Lernmaterial ausschließen |
| Fassungen | Vollständige quellentreue Skriptfassung plus separate didaktische Lernfassung |
| GitHub | Zunächst privat; Freigaben je Kurs später entscheiden |
| LaTeX | Vollständige editierbare .tex-Exporte; PDF bei vorhandener TeX-Installation |
| Kosten | Plan/Kostenschätzung vorab; API erst mit ausdrücklichem Startbefehl |
| Kontrollpunkt | Quellen, Gliederung und Streichungen vor weiterer automatischer Verarbeitung prüfen |
| Lernprodukte | Anki, Leitfaden, Musterlösungen, neue Aufgaben, SVG-Aufträge, Hörspiel-Kontext |

Nicht festgelegt: konkrete API-URL und Modell, Preise/Budget, GitHub-Organisation,
hochzuladende Inhalte, Prüfungstermin und persönliche Lernziele. Diese Angaben gehören
in Kurskonfiguration oder lokalen Lernfortschritt, nicht als feste Annahmen in Python.

Das Industriebetriebslehre-Repo bleibt unverändert und privat. Seine bestehenden
unversionierten Dateien wurden nicht kopiert. Kursspezifische Texte/Abbildungen werden
nicht als generische Vorlage verbreitet.

Nachtrag: Der Eigentümer hat die öffentliche Veröffentlichung des **Generators**
auf GitHub mit Feature-Branch-Commits und denselben Git-Schutzregeln wie die Vorlage
beauftragt. Die Kursrepos bleiben davon getrennt und standardmäßig privat.
