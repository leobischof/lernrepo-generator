from pathlib import Path
import yaml

PATHS = {
    "config": "course.yaml", "manifest": "sources/manifest.json",
    "extracted": "sources/extracted", "originals": "sources/originals",
    "structure": "curation/structure.json", "review": "curation/review.json",
    "results": "curation/results", "jobs": "build/jobs", "responses": "build/results",
    "log": "curation/ai-log.jsonl", "content": "content", "learning": "learning",
    "exams": "exams", "reports": "reports", "exports": "build/exports",
    "progress": "learning/progress/progress.json", "figures": "figures/reconstructed",
    "blanks": "figures/exercises", "crops": "figures/originals",
    "job_index": "curation/jobs-index.json", "build_state": "reports/build-state.json",
}


class Course:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.data = yaml.safe_load(self.path("config").read_text(encoding="utf-8"))
        if not isinstance(self.data, dict) or self.data.get("schema_version") != 1:
            raise ValueError("course.yaml: schema_version muss 1 sein")

    def path(self, key):
        return self.root / PATHS[key]

    def local(self, relative):
        dest = (self.root / relative).resolve()
        if not dest.is_relative_to(self.root):
            raise ValueError("Pfad verlässt das Kursrepo")
        return dest
