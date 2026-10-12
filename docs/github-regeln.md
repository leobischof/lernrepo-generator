# Git-Regeln

Der öffentliche Generator verwendet dieselbe Git-Policy wie die Vorlage
Industriebetriebslehre. Deren Inhalte werden dadurch nicht veröffentlicht.

| Regel | Durchsetzung |
|---|---|
| Änderungen an main nur per PR, auch für Admins | Branch Protection und Ruleset ohne Bypass |
| qa und konventionen erfolgreich, Branch aktuell | Required Status Checks, strict |
| Alle Diskussionen aufgelöst | Required Conversation Resolution |
| Nur Squash-Merges, lineare Historie | Repo-Einstellungen, Branch Protection |
| main nicht löschbar | Branch Protection und Ruleset |
| Kein Force-Push auf irgendeinen Branch | Ruleset für alle Branches |
| Erlaubte Branch-Präfixe | Branch-Namen-Ruleset |
| Conventional Commit-/PR-Titel, maximal 72 Zeichen | CI-Job konventionen |
| Owner als Reviewer anfragen, keine Selbstfreigabe erforderlich | CODEOWNERS, 0 Pflichtfreigaben |
| Branch nach Merge löschen | delete_branch_on_merge |

Präfixe und Titeltypen: `.github/scripts/conventions.py` ist die Quelle der Wahrheit.

```powershell
git switch -c feat/meine-aenderung
python -m pytest
python .github/scripts/conventions.py branch (git branch --show-current)
git add <gezielte-dateien>
git commit -m "feat: beschreibung"
python .github/scripts/conventions.py commits origin/main HEAD
git push -u origin feat/meine-aenderung
gh pr create --base main --fill
```

Checks abwarten. Nur autorisiert und bei grüner CI mit `gh pr merge --squash` mergen.
Nach Änderungen an main den Branch mit `git merge origin/main` aktualisieren, nicht
gepushte Historie umschreiben. Schutzregeln niemals zur Umgehung abschalten.

Reproduzierbare serverseitige Einrichtung, nur mit ausdrücklichem Auftrag:
`python scripts/configure_github.py --repo OWNER/REPO --apply`. Ohne `--apply`
zeigt das Skript die Policy, ohne GitHub zu ändern. main muss bereits existieren.

Neue Kursrepos erhalten CI und Konventionen. Der Generator kopiert seinen persönlichen
CODEOWNERS-Eintrag nicht; dort eigene Verantwortliche eintragen. Serverseitige Regeln
werden pro neuem GitHub-Repo eingerichtet und werden durch Kopieren allein nicht aktiv.
