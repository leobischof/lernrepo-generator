import shutil
import subprocess

import pytest

from pipeline.generator import create, upgrade


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.mark.skipif(not shutil.which("git"), reason="Git optional")
def test_scaffold_initial_commit_without_user_identity(tmp_path, monkeypatch):
    config = tmp_path / "empty-git-config"
    config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    root = create(tmp_path / "course", "Test", "test")
    assert git(root, "rev-list", "--count", "HEAD") == "1"
    assert git(root, "branch", "--show-current") == "feature/course-bootstrap"
    assert git(root, "status", "--porcelain") == ""
    assert git(root, "log", "-1", "--format=%an <%ae>") == "Lernrepo Generator <lernrepo-generator@localhost>"
    assert "course.yaml" in git(root, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    readme = root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nNew content\n", encoding="utf-8")
    assert "+New content" in git(root, "diff", "--", "README.md")
    assert subprocess.run(["git", "-C", str(root), "config", "--local", "--get", "user.name"], capture_output=True).returncode == 1


def test_upgrade_without_git_preserves_local_tools(tmp_path, monkeypatch):
    original = shutil.which
    monkeypatch.setattr("pipeline.generator.shutil.which", lambda name: None if name == "git" else original(name))
    with pytest.warns(UserWarning, match="Git nicht gefunden"):
        root = create(tmp_path / "course", "Test", "test")
    assert not (root / ".git").exists()
    tool = root / "pipeline/config.py"
    tool.write_text("# local edits\n", encoding="utf-8")
    with pytest.warns(UserWarning, match="gesichert"):
        upgrade(root)
    backups = list((root / "build/upgrade-backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / "pipeline/config.py").read_text(encoding="utf-8") == "# local edits\n"
    assert tool.read_text(encoding="utf-8") != "# local edits\n"
