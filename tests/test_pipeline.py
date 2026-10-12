"""Synthetic end-to-end and trust-boundary tests; never calls a remote model."""
import copy
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest
import yaml

from pipeline.config import Course
from pipeline.generator import create
from pipeline.ingest import run as ingest
from pipeline.io import read, write
from pipeline.jobs import accept, check_structure, make_jobs, plan, review, validate_result
from pipeline.build import build, offline
from pipeline.export import run as export, latex_document
from pipeline.api import run as api


@pytest.fixture
def course(tmp_path):
    root = create(tmp_path / "kurs", "Testvorlesung", "testkurs")
    config = yaml.safe_load((root / "course.yaml").read_text(encoding="utf-8"))
    config["sources"] = [dict(id="skript", path="input/skript.txt", kind="script", trust="primary"),
                          dict(id="klausur", path="input/klausur.txt", kind="exam", trust="student-transcript")]
    write(root / "course.yaml", yaml.safe_dump(config, allow_unicode=True))
    write(root / "input/skript.txt", "Energie bleibt erhalten. GESTRICHEN.\fArbeit ist Energieübertragung.")
    write(root / "input/klausur.txt", "Erklären Sie die Energieerhaltung. 3 Punkte.")
    c = Course(root)
    ingest(c)
    structure = read(c.path("structure"))
    structure["sections"][0]["title"] = "Energie"
    structure["sections"][0]["needs_review"] = False
    structure["exclusions"] = [dict(source="skript", page=1, text="GESTRICHEN.", reason="gestrichen", reviewed=True)]
    write(c.path("structure"), structure)
    review(c, "test-fixture")
    return c


def response(job):
    refs = [{"source": job["sources"][0]["source"], "page": job["sources"][0]["page"]}]
    result = {"job_id": job["job_id"], "input_hash": job["input_hash"], "guide": [], "cards": [],
              "questions": [], "audio": [], "figures": [], "uncertainties": []}
    if job["kind"] == "script":
        result["guide"] = [dict(text="Energie bleibt erhalten.", refs=refs)]
        result["cards"] = [dict(id="energie", front="Was bleibt erhalten?", back="Energie.", refs=refs)]
        result["audio"] = [dict(text="Besprecht die Energieerhaltung.", refs=refs)]
        result["questions"] = [dict(id="uebung", origin="generated", prompt="Erkläre Energieerhaltung.",
                                    solution="Energie bleibt erhalten.", points=None, refs=refs)]
    else:
        result["questions"] = [dict(id="echt", origin="real", prompt="Erklären Sie die Energieerhaltung.",
                                    solution="Energie bleibt erhalten. (Testantwort)", points=3, refs=refs)]
    return result


def answer_all(course):
    plan(course)
    for job in make_jobs(course):
        write(course.path("responses") / f"{job['job_id']}.json", response(job))
    return accept(course, "synthetic-test")


def test_complete_flow_and_offline_clone(course, tmp_path):
    assert answer_all(course) == 2
    assert accept(course, "synthetic-test") == 0
    assert plan(course)["pending"] == 0
    assert build(course) == dict(sections=1, cards=1, questions=2, figure_jobs=0)
    assert offline(course)["errors"] == []
    exported = export(course)
    assert exported["cards"] == 1
    raw = next(course.path("content").glob("*-skript.md")).read_text(encoding="utf-8")
    assert "GESTRICHEN." in raw
    assert all("GESTRICHEN." not in s["text"] for job in make_jobs(course) for s in job["sources"])
    assert len(read(course.path("exams") / "questions-real.json")) == 1
    assert len(read(course.path("exams") / "questions-generated.json")) == 1
    assert (course.path("exports") / "gesamtskript.tex").exists()
    with zipfile.ZipFile(exported["zip"]) as archive:
        assert "anki-gesamt.apkg" in archive.namelist()
        assert not any("input" in n or "originals" in n or "progress" in n for n in archive.namelist())
    # A clone with no originals/extraction/build can still validate committed results.
    clone = tmp_path / "clone"
    shutil.copytree(course.root, clone, ignore=shutil.ignore_patterns("input", "originals", "extracted", "build", ".git"))
    assert offline(Course(clone))["errors"] == []


def test_review_is_invalidated_by_structure_change(course):
    structure = read(course.path("structure"))
    structure["sections"][0]["title"] = "Geändert"
    write(course.path("structure"), structure)
    with pytest.raises(ValueError, match="freigegeben"):
        make_jobs(course)


def test_extraction_tampering_blocks_review(course):
    path = course.path("extracted") / "skript-pages.json"
    data = read(path)
    data[0]["text"] = "erfunden"
    write(path, data)
    assert any("verändert" in e for e in check_structure(course))


def test_structure_requires_all_pages_and_confirmed_exclusions(course):
    structure = read(course.path("structure"))
    structure["sections"][0]["pages"] = [1]
    structure["exclusions"][0]["reviewed"] = False
    write(course.path("structure"), structure)
    errors = check_structure(course)
    assert any("ohne Abschnitt" in e for e in errors)
    assert any("reviewed=true" in e for e in errors)


def test_reject_wrong_reference_and_fabricated_real_question(course):
    job = make_jobs(course)[0]
    result = response(job)
    result["guide"][0]["refs"][0]["page"] = 99
    with pytest.raises(ValueError, match="außerhalb"):
        validate_result(job, result)
    result = response(job)
    result["questions"][0]["origin"] = "real"
    with pytest.raises(ValueError, match="Aufgabenquelle"):
        validate_result(job, result)
    exam = make_jobs(course)[1]
    result = response(exam)
    result["questions"][0]["prompt"] = "Eine erfundene Aufgabe"
    with pytest.raises(ValueError, match="wortgetreu"):
        validate_result(exam, result)


def test_no_silent_truncation(course):
    course.data["processing"]["max_chars_per_job"] = 8
    review(course, "test-fixture")
    jobs = make_jobs(course)
    assert len(jobs) > 2
    script = "".join(s["text"] for j in jobs if j["kind"] == "script" for s in j["sources"])
    assert script == "Energie bleibt erhalten. Arbeit ist Energieübertragung."


def test_api_explicit_start_cache_and_key_not_logged(course, monkeypatch):
    course.data["llm"].update(base_url="https://api.example.invalid/v1", model="test-model")
    review(course, "test-fixture")
    monkeypatch.setenv("LEARNREPO_API_KEY", "secret-test-value")
    calls = []

    def transport(request):
        calls.append(request)
        payload = json.loads(request.data)
        job = json.loads(payload["messages"][1]["content"])
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(response(job))}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 100}}

    api(course, transport=transport)
    assert calls == []
    assert api(course, start=True, max_jobs=1, transport=transport)["completed"] == 1
    assert len(calls) == 1
    assert "secret-test-value" not in course.path("log").read_text(encoding="utf-8")
    assert api(course, start=True, max_jobs=5, transport=transport)["completed"] == 1
    assert api(course, start=True, max_jobs=5, transport=transport)["completed"] == 0
    assert len(calls) == 2


def test_incomplete_model_output_not_accepted(course):
    course.data["llm"].update(base_url="http://localhost:1234/v1", model="test")
    review(course, "test-fixture")
    with pytest.raises(ValueError, match="unvollständig"):
        api(course, start=True, transport=lambda _: {"choices": [{"finish_reason": "length"}]})
    assert not list(course.path("results").glob("*.json"))


def test_paths_and_nonempty_target_are_safe(course):
    with pytest.raises(ValueError, match="verlässt"):
        course.local("../secret")
    with pytest.raises(ValueError, match="leer"):
        create(course.root, "Andere", "andere")


def test_progress_is_local_and_unknown_topic_rejected(course):
    from pipeline.progress import run
    topic = read(course.path("structure"))["sections"][0]["id"]
    assert run(course, "due") == {}
    assert run(course, "record", topic, "definition", 4)["schedule"]["interval_days"] == 1
    assert course.path("progress").exists()
    with pytest.raises(ValueError, match="Unbekannt"):
        run(course, "record", "sec-unknown", "definition", 5)


def test_latex_escapes_prose_preserves_common_math_and_blocks_commands():
    text = latex_document("A&B", "# Energie\n\n**Beispiel**: $E = m \\cdot c^2$, 50%.\n\n$\\input{secret}$")
    assert r"A\&B" in text and r"50\%" in text
    assert r"$E = m \cdot c^2$" in text
    assert r"\textbf{Beispiel}" in text
    assert r"$\input{secret}$" not in text
    assert r"\begin{filecontents}" not in latex_document("Test", r"$\begin{filecontents}{secret}x\end{filecontents}$")


def test_anki_guid_stability(course, tmp_path):
    answer_all(course)
    build(course)
    export(course)

    def notes():
        with zipfile.ZipFile(course.path("exports") / "anki-gesamt.apkg") as archive:
            db = tmp_path / "collection.sqlite"
            db.write_bytes(archive.read("collection.anki2"))
        with sqlite3.connect(db) as conn:
            return conn.execute("select guid from notes order by guid").fetchall()

    first = notes()
    export(course)
    assert notes() == first and len(first) == 1


def test_pdf_ingest_and_figure_blank(course):
    import pymupdf
    from pipeline.build import figures
    path = course.root / "input/diagram.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, 30), "Diagramm")
        doc.save(path)
    course.data["sources"].append(dict(id="diagramm", path="input/diagram.pdf", kind="summary", trust="primary"))
    ingest(course)
    structure = read(course.path("structure"))
    structure["figures"] = [dict(id="abb-01", source="diagramm", page=1, bbox=[0, 0, 180, 100])]
    write(course.path("structure"), structure)
    write(course.path("figures") / "abb-01.svg", '<svg xmlns="http://www.w3.org/2000/svg"><text class="answer" x="10" y="20">Antwort</text></svg>')
    figures(course)
    assert (course.path("crops") / "abb-01.png").exists()
    assert "Antwort" not in (course.path("blanks") / "abb-01-blank.svg").read_text(encoding="utf-8")


def test_modified_generated_file_cannot_be_exported(course):
    answer_all(course)
    build(course)
    write(course.path("learning") / "cards.json", [])
    with pytest.raises(ValueError, match="Generierte Datei"):
        export(course)


def test_review_packet_requires_no_llm(course):
    from pipeline.inspect import run
    report = run(course)
    assert report["sources"] == 2
    assert Path(report["report"]).exists()
    assert not course.path("log").exists()
