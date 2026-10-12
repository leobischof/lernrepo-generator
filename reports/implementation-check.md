# Stand der ersten Version

Prüfung am 12.10.2026: `python -m pytest` → **40 passed**.

Getestet: vollständiger synthetischer Durchlauf einschließlich eigenständigem
Kursrepo, Agentenantworten, simuliertem API-Transport, Startkontrolle, Wiederaufnahme,
Quellen- und Wortlautprüfung, Ausschlüssen, Quellentexterhalt, Anki-Paket und stabilen
Notiz-GUIDs, Markdown/TeX/ZIP, Offline-Prüfung ohne Originale, Bildausschnitt/Blanko-SVG,
lokalem Fortschritt und Schutz gegen Export veränderter generierter Dateien.
Zusätzlich: Git-Konventionen und reproduzierbare GitHub-Schutzpolicy.

Nicht ausgeführt: echte kostenpflichtige Modellaufrufe, TeX-Kompilierung und visuelle
PDF-Abnahme (keine TeX-Engine gefunden). Die öffentliche GitHub-Veröffentlichung
des Generators ist am 12.10.2026 ausdrücklich beauftragt; Kursmaterialien bleiben lokal.

## Entwicklungsmethodik-Pilot

- Eigenständiges lokales Git-Repo auf `feature/course-bootstrap`.
- 5 registrierte Quellen: Skript, 3 Klausuren, 1 Fragensammlung.
- 475 Skriptseiten und 15 weitere Quellseiten lokal importiert.
- 25 vorgeschlagene Abschnitte decken alle 475 Skriptseiten genau einmal ab.
- Originale, Extraktionen und persönlicher Fortschritt werden von Git ignoriert.
- `offline` ist **noch nicht grün**: 25 Abschnitte sind ausdrücklich ungeprüft;
  Struktur-/Quellenfreigabe fehlt. Vier Klausurseiten haben keine Textschicht.
- Keine Ausschlüsse geraten: Darstellung der Streichungen wird mit der Person geklärt.
- Kein Pilot-Lernmaterial erzeugt, bevor die gewünschte Struktur-/Streichungsprüfung erfolgt.

Noch offene Funktionen und Qualitätsgrenzen: `docs/generator-architektur.md` und README.
