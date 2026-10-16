import zipfile

import pymupdf
import pytest

from test_pipeline import course, git_available, answer_all
from pipeline.build import build
from pipeline.io import read, write


def prepare(course):
    answer_all(course)
    build(course)


def test_notebook_context_contains_guide_real_questions_and_full_source(course):
    from pipeline.chapter_exports import notebooklm
    prepare(course)
    result = notebooklm(course)
    assert result['chapters'] == 1
    text = next((course.root / 'build/notebooklm').glob('*.md')).read_text(encoding='utf-8')
    assert 'Energie bleibt erhalten.' in text
    assert 'Erklären Sie die Energieerhaltung.' in text
    assert 'Arbeit ist Energieübertragung.' in text
    assert 'testkurs-1-' in text
    assert 'Rahmenwissen' in text and 'ungeprüft' in text


def test_direct_pdf_has_readable_text_tables_outline_and_own_figure(course):
    from pipeline.pdf_export import run
    # Put a table and formula into the actual input and reimport/review.
    from pipeline.ingest import run as ingest
    from pipeline.jobs import review
    write(course.root / 'input/skript.txt', 'Energie bleibt erhalten. GESTRICHEN.\n\n| Größe | Wert |\n|---|---|\n| Arbeit | 12 |\n\n$$E=mc^2$$\fArbeit ist Energieübertragung.')
    ingest(course)
    structure = read(course.path('structure'))
    structure['figures'] = [dict(id='abb-01', title='Eigene Skizze', source='skript', page=1, bbox=[0, 0, 100, 100])]
    write(course.path('structure'), structure)
    write(course.path('figures') / 'abb-01.svg', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80"><path d="M5 5L90 70" stroke="black"/><text x="10" y="20">Energie</text></svg>')
    review(course, 'test')
    prepare(course)
    result = run(course)
    assert result['chapters'] == 1
    path = course.root / 'build/pdf/testkurs-1-Energie.pdf'
    with pymupdf.open(path) as doc:
        text = ''.join(page.get_text() for page in doc)
        assert 'Energie' in text and 'Arbeit' in text and '12' in text
        assert doc.get_toc()
        assert any(page.get_images() for page in doc)
    with pymupdf.open(course.root / 'build/pdf/testkurs-Gesamtskript.pdf') as doc:
        assert sum(len(page.get_images()) for page in doc) >= 2  # formula and own figure


def test_release_is_deterministic_and_excludes_originals_and_unlisted_files(course):
    from pipeline.chapter_exports import notebooklm
    from pipeline.pdf_export import run as pdf
    from pipeline.export import run as export
    from pipeline.release import run
    prepare(course)
    export(course)
    notebooklm(course)
    pdf(course)
    write(course.root / 'build/pdf/PRIVATE.pdf', 'must not ship')
    first = run(course)
    path = course.root / first['zip']
    before = path.read_bytes()
    run(course)
    assert path.read_bytes() == before
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert any('NotebookLM' in name for name in archive.namelist())
        assert not any('PRIVATE' in name or 'original' in name or 'progress' in name for name in archive.namelist())


def test_exports_reject_modified_generated_material(course):
    from pipeline.chapter_exports import notebooklm
    prepare(course)
    next(course.path('content').glob('*-skript.md')).write_text('tampered', encoding='utf-8')
    with pytest.raises(ValueError, match='verändert'):
        notebooklm(course)


def test_notebook_context_explains_figures_without_original_image_links(course):
    from pipeline.chapter_exports import notebooklm
    structure = read(course.path('structure'))
    structure['figures'] = [dict(id='abb-01', source='skript', page=1, title='Energiekurve', bbox=[0,0,10,10],
                                 description='Die horizontale Achse zeigt die Zeit, die vertikale die Energie.')]
    write(course.path('structure'), structure)
    from pipeline.jobs import review
    review(course, 'test')
    prepare(course)
    notebooklm(course)
    text = next((course.root / 'build/notebooklm').glob('*.md')).read_text(encoding='utf-8')
    assert 'horizontale Achse' in text
    assert '![Energiekurve]' not in text
