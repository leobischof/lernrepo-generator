import copy
import json
from pathlib import Path

import pymupdf
import pytest

from test_pipeline import course, git_available, answer_all
from pipeline.build import build
from pipeline.io import file_hash, read, write


@pytest.fixture
def reader_course(course):
    answer_all(course)
    build(course)
    from pipeline.pdf_export import run
    run(course)
    vendor = course.root / 'interactive/node_modules/pdfjs-dist'
    for name in ['build/pdf.mjs', 'build/pdf.worker.mjs', 'web/pdf_viewer.mjs', 'web/pdf_viewer.css', 'LICENSE']:
        write(vendor / name, '/* synthetic dependency; browser integration uses real PDF.js */')
    for name in ['cmaps', 'standard_fonts', 'wasm']:
        (vendor / name).mkdir(parents=True)
    return course


def test_reader_without_audio_is_readable_and_contains_only_built_pdf(reader_course):
    from pipeline.reader import run
    c = reader_course
    assert run(c)['chapters'] == 1
    root = c.root / 'build/interactive'
    manifest = read(root / 'reader-manifest.json')
    assert manifest['course']['id'] == 'testkurs'
    assert manifest['chapters'][0]['audio'] is None
    assert 'testkurs' in manifest['chapters'][0]['pdf']
    assert (root / manifest['chapters'][0]['pdf']).is_file()
    assert 'GIL' not in (root / 'reader.html').read_text(encoding='utf-8')
    assert not (root / 'input').exists()


def test_timeline_binds_document_identity_pages_times_and_geometry(reader_course):
    from pipeline.timeline import validate
    chapter = dict(number=1, pdf_sha256='a'*64, audio_sha256='b'*64)
    value = dict(version=1, chapter=1, pdf_sha256='a'*64, audio_sha256='b'*64,
                 annotations=[dict(id='a', page=1, start=0, end=2, type='rect', rect=[0.1,0.2,0.5,0.3], status='unreviewed')])
    validate(value, chapter, pages=2, duration=10)
    for field, replacement in [('pdf_sha256', '0'*64), ('chapter', 4)]:
        bad = {**value, field: replacement}
        with pytest.raises(ValueError):
            validate(bad, chapter, pages=2)
    for field, replacement in [('page', 3), ('start', float('nan')), ('end', 11), ('rect', [0,0,2,1])]:
        bad = copy.deepcopy(value)
        bad['annotations'][0][field] = replacement
        with pytest.raises(ValueError):
            validate(bad, chapter, pages=2, duration=10)


def test_reader_refuses_stale_timeline_before_writing(reader_course):
    from pipeline.reader import run
    c = reader_course
    write(c.root / 'audio/testkurs-1-Audio.wav', 'synthetic media')
    write(c.root / 'curation/interactive/testkurs-1-Timeline.json',
          dict(version=1, chapter=1, pdf_sha256='0'*64, audio_sha256='0'*64, annotations=[]))
    with pytest.raises(ValueError, match='verändert'):
        run(c)
    assert not (c.root / 'build/interactive/reader-manifest.json').exists()


def test_standalone_embeds_pdf_and_escapes_script_terminator(reader_course):
    from pipeline.reader import run
    from pipeline.reader_package import run as package, render_html
    c = reader_course
    run(c)
    assert package(c)['chapters'] == 1
    path = next((c.root / 'build/standalone').glob('*.html'))
    text = path.read_text(encoding='utf-8')
    assert 'application/json' in text and 'JVBER' in text
    html = render_html('<head></head><script type="module" src="reader-app.mjs"></script>', '', '', {'title': '</script><script>evil()</script>'}, {})
    assert '</script><script>evil()' not in html


def test_standalone_has_no_external_favicon_dependency():
    from pipeline.reader_package import render_html
    html = render_html('<head><link rel="icon" href="reader-icon.svg"></head><script type="module" src="reader-app.mjs"></script>', '', '', {}, {})
    assert 'href="reader-icon.svg"' not in html


def test_reader_rejects_ambiguous_or_unassigned_audio(reader_course):
    from pipeline.reader import run
    c = reader_course
    write(c.root / 'audio/testkurs-1-Audio.wav', 'one')
    write(c.root / 'audio/testkurs-1-Anderes.mp3', 'two')
    with pytest.raises(ValueError, match='Mehrere'):
        run(c)


def test_packaging_refuses_timeline_changed_after_reader_build(reader_course):
    from pipeline.reader import run
    from pipeline.reader_package import run as package
    c = reader_course
    run(c)
    write(c.root / 'curation/interactive/testkurs-1-Timeline.json', {'version': 1, 'annotations': []})
    with pytest.raises(ValueError, match='Exportquelle'):
        package(c)
