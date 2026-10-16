import shutil
import subprocess
import warnings
from pathlib import Path
from uuid import uuid4
import yaml
from .io import file_hash, identifier, read, write

TOOL_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = '.lernrepo-tools.json'
TOOL_DIRS = ('pipeline', 'tests', '.github', 'scripts', 'interactive', 'docs')
TOOL_FILES = ('pyproject.toml', 'AGENTS.md', '.gitignore', '.gitattributes', 'dev.ps1')


def tool_files():
    files = []
    for name in TOOL_DIRS:
        for path in (TOOL_ROOT / name).rglob('*'):
            if path.is_file() and not any(part in {'__pycache__', 'node_modules', '.pytest_cache'}
                                          for part in path.relative_to(TOOL_ROOT).parts) and path.name != 'CODEOWNERS':
                files.append(path.relative_to(TOOL_ROOT).as_posix())
    return sorted(files + [name for name in TOOL_FILES if (TOOL_ROOT / name).is_file()])


def copy_tools(dest):
    for name in tool_files():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TOOL_ROOT / name, target)
    write(dest / MANIFEST, {'version': 1, 'files': {name: file_hash(dest / name) for name in tool_files()}})


def create(destination, title, slug):
    identifier(slug)
    dest = Path(destination).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("Ziel muss neu oder leer sein; vorhandene Dateien werden nicht überschrieben")
    dest.mkdir(parents=True, exist_ok=True)
    copy_tools(dest)
    config = dict(schema_version=1, course=dict(id=slug, title=title, language="de", visibility="private"),
                  sources=[], products=["guide", "cards", "questions", "solutions", "audio", "figures"],
                  processing=dict(pages_per_section=5, max_chars_per_job=18000),
                  llm=dict(base_url="", model="", api_key_env="LEARNREPO_API_KEY",
                           max_output_tokens=6000, token_limit_field="max_completion_tokens",
                           input_per_million=None, output_per_million=None))
    write(dest / "course.yaml", yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
    write(dest / "curation/structure.json", {"sections": [], "exclusions": [], "figures": []})
    write(dest / "README.md", f"# {title}\n\nEigenständiges Wissensrepo, erstellt mit Lernrepo-Generator.\n\n"
          "Start: `python -m pipeline --help`. Ablauf: [Arbeitsablauf](docs/arbeitsablauf.md).\n"
          "Originale und persönlicher Fortschritt bleiben lokal. KI-Inhalte sind ungeprüft.\n")
    git = shutil.which("git")
    if git:
        subprocess.run([git, "init", "-b", "feature/course-bootstrap", str(dest)], check=True, capture_output=True)
        scaffold = [p.name for p in dest.iterdir() if p.name != ".git"]
        subprocess.run([git, "-C", str(dest), "add", "--", *scaffold], check=True, capture_output=True)
        identity = subprocess.run([git, "-C", str(dest), "var", "GIT_AUTHOR_IDENT"], capture_output=True)
        options = [] if identity.returncode == 0 else [
            "-c", "user.name=Lernrepo Generator", "-c", "user.email=lernrepo-generator@localhost"]
        subprocess.run([git, "-C", str(dest), *options, "commit", "-m",
                        "chore: initialize course scaffold"], check=True, capture_output=True)
    else:
        warnings.warn("Git nicht gefunden: Kursordner ohne Versionshistorie erstellt; "
                      "alle Lernfunktionen sind verfügbar.", stacklevel=2)
    return dest


def upgrade(destination):
    """Check Git edits or back up existing tools before updating."""
    dest = Path(destination).resolve()
    if dest == TOOL_ROOT or not (dest / "course.yaml").exists():
        raise ValueError("Ziel muss ein anderes erzeugtes Kursrepo sein")
    git = shutil.which("git")
    recorded = read(dest / MANIFEST, {}).get('files', {})
    names = sorted(set(tool_files()) | set(recorded))
    for name, fingerprint in recorded.items():
        target = (dest / name).resolve()
        if not target.is_relative_to(dest):
            raise ValueError('Ungültiger Werkzeugpfad im Manifest')
        if git and (dest / '.git').exists() and (not target.is_file() or file_hash(target) != fingerprint):
            raise ValueError(f'Werkzeugdateien haben lokale Änderungen: {name}; zuerst sichern')
    if git and (dest / ".git").exists():
        status = subprocess.run([git, "-C", str(dest), "status", "--porcelain", "--", *names, MANIFEST],
                                check=True, text=True, capture_output=True)
        if status.stdout.strip():
            raise ValueError("Werkzeugdateien haben lokale Änderungen: zuerst sichern/committen")
    if not (git and (dest / '.git').exists()) or not recorded:
        backup = dest / "build" / "upgrade-backups" / uuid4().hex
        backup.mkdir(parents=True)
        for name in names + [MANIFEST]:
            if (dest / name).is_file():
                target = backup / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dest / name, target)
        warnings.warn(f'Bisherige Werkzeugdateien gesichert in {backup}', stacklevel=2)
    copy_tools(dest)
