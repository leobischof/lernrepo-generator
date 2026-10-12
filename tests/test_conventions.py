"""Git conventions enforced in CI: commit subjects, branch names, the branch-name ruleset."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "conventions.py"
_SPEC = importlib.util.spec_from_file_location("conventions", _PATH)
conventions = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(conventions)


@pytest.mark.parametrize("subject", ["feat: add Anki deck", "fix(ocr): Seite 51 korrigiert",
                                     "content: Abbildung 12 beschreiben", "refactor!: rename stages"])
def test_good_subjects(subject):
    assert conventions.subject_problems(subject) == []


@pytest.mark.parametrize("subject", ["Update README", "feat:no space", "Feat: upper case type",
                                     "wip: later", "fix: trailing dot.", "feat: " + "x" * 70])
def test_bad_subjects(subject):
    assert conventions.subject_problems(subject)


@pytest.mark.parametrize("name", ["main", "feat/export-md", "feature/neue-uebung", "fix/ocr-seite-51",
                                  "release/v1.1", "docs/agents/abschnitt-7"])
def test_good_branches(name):
    assert conventions.branch_problems(name) == []


@pytest.mark.parametrize("name", ["test-branch", "Feature/x", "feat/", "patch-1", "feat/Großbuchstaben",
                                  "dev"])
def test_bad_branches(name):
    assert conventions.branch_problems(name)


def test_ruleset_allows_main_and_every_prefix_and_blocks_the_rest():
    rs = conventions.ruleset()
    excluded = rs["conditions"]["ref_name"]["exclude"]
    assert "refs/heads/main" in excluded
    assert {f"refs/heads/{p}/**/*" for p in conventions.BRANCH_PREFIXES} <= set(excluded)
    assert rs["rules"] == [{"type": "creation"}] and rs["bypass_actors"] == []
