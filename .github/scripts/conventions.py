"""Git conventions of this repository, checked in CI (job `konventionen`) – single source of truth.

GitHub rulesets of a private personal repository cannot match commit messages or branch
names, so CI enforces them and branch protection requires that job:

  python .github/scripts/conventions.py branch feat/neue-abbildung
  python .github/scripts/conventions.py subject "fix: OCR-Fehler auf Seite 51"
  python .github/scripts/conventions.py commits origin/main HEAD    # every non-merge commit
  python .github/scripts/conventions.py ruleset                     # JSON for the GitHub ruleset

`ruleset` prints the "Branch-Namen" ruleset (blocks creating any other branch), so the
allowed prefixes exist only here. Exit code 1 lists every violation.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

# Conventional Commits types; `content` is for changes to the knowledge base itself.
TYPES = ("feat", "fix", "docs", "content", "refactor", "test", "perf", "build", "ci", "chore", "style", "revert")
# Branch prefixes: every type plus the classic long forms.
BRANCH_PREFIXES = (*TYPES, "feature", "hotfix", "release")
PROTECTED = "main"
MAX_SUBJECT = 72

SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([a-z0-9][a-z0-9-]*\))?!?: \S")
BRANCH = re.compile(rf"^(?:{'|'.join(BRANCH_PREFIXES)})/[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*$")


def subject_problems(subject: str) -> list[str]:
    problems = []
    if not SUBJECT.match(subject):
        problems.append(f"„{subject}“: Format `typ: beschreibung` oder `typ(bereich): beschreibung`, "
                        f"typ aus {', '.join(TYPES)}")
    if len(subject) > MAX_SUBJECT:
        problems.append(f"„{subject}“: {len(subject)} Zeichen, höchstens {MAX_SUBJECT}")
    if subject.rstrip() != subject or subject.endswith("."):
        problems.append(f"„{subject}“: kein Punkt und kein Leerzeichen am Ende")
    return problems


def branch_problems(name: str) -> list[str]:
    if name == PROTECTED or BRANCH.match(name):
        return []
    return [f"Branch „{name}“: Format `präfix/kurz-beschreibung` (Kleinbuchstaben, Ziffern, -._), "
            f"präfix aus {', '.join(BRANCH_PREFIXES)}"]


def commit_subjects(base: str, head: str) -> list[str]:
    out = subprocess.run(["git", "log", "--no-merges", "--format=%s", f"{base}..{head}"],
                         check=True, capture_output=True, text=True, encoding="utf-8").stdout
    return [line for line in out.splitlines() if line]


def ruleset() -> dict:
    """Ruleset that blocks creating branches outside the allowed prefixes – for everyone."""
    allowed = [f"refs/heads/{PROTECTED}", *(f"refs/heads/{p}/**/*" for p in BRANCH_PREFIXES)]
    return {"name": "Branch-Namen", "target": "branch", "enforcement": "active", "bypass_actors": [],
            "conditions": {"ref_name": {"include": ["~ALL"], "exclude": allowed}},
            "rules": [{"type": "creation"}]}


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print(__doc__)
        return 2
    command, args = argv[0], argv[1:]
    if command == "ruleset":
        print(json.dumps(ruleset(), indent=2))
        return 0
    if command == "branch":
        problems = branch_problems(args[0])
    elif command == "subject":
        problems = subject_problems(args[0])
    elif command == "commits":
        problems = [p for s in commit_subjects(args[0], args[1]) for p in subject_problems(s)]
    else:
        print(f"unbekannter Befehl: {command}")
        return 2
    for p in problems:
        print(f"::error::{p}")
    print("Konventionen eingehalten" if not problems else f"{len(problems)} Verstoß/Verstöße")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
