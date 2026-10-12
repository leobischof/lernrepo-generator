import shutil
import subprocess
from pathlib import Path
import yaml
from .io import identifier, write

TOOL_ROOT = Path(__file__).resolve().parent.parent


def create(destination, title, slug):
    identifier(slug)
    dest = Path(destination).resolve()
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("Ziel muss neu oder leer sein; vorhandene Dateien werden nicht überschrieben")
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("pipeline", "tests", ".github", "scripts"):
        if not (TOOL_ROOT / name).exists():
            continue
        shutil.copytree(TOOL_ROOT / name, dest / name, ignore=shutil.ignore_patterns("__pycache__", "CODEOWNERS"))
    for name in ("pyproject.toml", "AGENTS.md", ".gitignore", ".gitattributes"):
        shutil.copy2(TOOL_ROOT / name, dest / name)
    if (TOOL_ROOT / "docs").exists():
        shutil.copytree(TOOL_ROOT / "docs", dest / "docs")
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
    subprocess.run(["git", "init", "-b", "feature/course-bootstrap", str(dest)], check=True, capture_output=True)
    return dest


def upgrade(destination):
    """Refuse overwriting local edits; update only versioned tool files."""
    dest = Path(destination).resolve()
    if dest == TOOL_ROOT or not (dest / "course.yaml").exists():
        raise ValueError("Ziel muss ein anderes erzeugtes Kursrepo sein")
    status = subprocess.run(["git", "-C", str(dest), "status", "--porcelain", "--", "pipeline", "pyproject.toml"],
                            check=True, text=True, capture_output=True)
    if status.stdout.strip():
        raise ValueError("Werkzeugdateien haben lokale Änderungen: zuerst sichern/committen")
    for path in (TOOL_ROOT / "pipeline").glob("*.py"):
        shutil.copy2(path, dest / "pipeline" / path.name)
    shutil.copy2(TOOL_ROOT / "pyproject.toml", dest / "pyproject.toml")
