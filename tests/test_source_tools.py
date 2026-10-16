import copy
import json

import pytest

from test_pipeline import course, git_available
from pipeline.io import read, write
from pipeline.jobs import approved, review


def correction(course):
    return dict(source='skript', page=1, before='Energie', after='Gesamtenergie',
                source_sha256=read(course.path('manifest'))['sources']['skript']['sha256'],
                reason='gegen Original geprüft', reviewed=True)


def test_correction_is_exact_repeatable_and_preserves_extraction(course):
    from pipeline.source_tools import apply_corrections
    path = course.path('extracted') / 'skript-pages.json'
    before = path.read_bytes()
    write(course.root / 'curation/text-corrections.json', {'corrections': [correction(course)]})
    raw = read(path)
    result = apply_corrections(course, 'skript', raw)
    assert result[0]['text'] == 'Gesamtenergie bleibt erhalten. GESTRICHEN.'
    assert raw[0]['text'].startswith('Energie')
    assert apply_corrections(course, 'skript', raw) == result
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='freigegeben'):
        approved(course)
    review(course, 'test')


@pytest.mark.parametrize('field,value', [('before', 'NICHT VORHANDEN'), ('source_sha256', '0'*64), ('reviewed', False)])
def test_correction_rejects_unmatched_text_stale_source_and_missing_review(course, field, value):
    from pipeline.source_tools import apply_corrections
    item = correction(course)
    item[field] = value
    write(course.root / 'curation/text-corrections.json', {'corrections': [item]})
    with pytest.raises(ValueError):
        apply_corrections(course, 'skript', read(course.path('extracted') / 'skript-pages.json'))


def test_image_detection_only_writes_candidates(course):
    import pymupdf
    from pipeline.figure_tools import detect
    path = course.path('originals') / 'bild.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.draw_rect(pymupdf.Rect(30, 50, 180, 140))
        doc.save(path)
    manifest = read(course.path('manifest'))
    manifest['sources']['bild'] = {'spec': {'path': 'input/bild.pdf'}, 'pages': 1}
    write(course.path('manifest'), manifest)
    before = course.path('structure').read_bytes()
    result = detect(course)
    assert result['candidates'] >= 1
    assert all(item['status'] == 'unreviewed' for item in read(course.path('reports') / 'figure-candidates.json'))
    assert course.path('structure').read_bytes() == before


def test_icons_embed_license_and_reject_active_svg(course):
    from pipeline.figure_tools import icons
    target = course.path('figures') / 'abb-01.svg'
    write(target, '<svg xmlns="http://www.w3.org/2000/svg"><g data-icon="book"/><text>Wissen</text></svg>')
    write(course.root / 'curation/icons/book.svg', '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M1 1h22v22H1z"/></svg>')
    item = dict(id='book', path='curation/icons/book.svg', license='ISC',
                source='https://example.test/book', copyright='Copyright Test')
    write(course.root / 'curation/icon-library.json', {'icons': [item]})
    assert icons(course)['embedded'] == 1
    text = target.read_text(encoding='utf-8')
    assert 'Wissen' in text and 'Copyright Test' in text and 'ISC' in text
    assert icons(course)['embedded'] == 1
    write(course.root / 'curation/icons/book.svg', '<svg><script>alert(1)</script></svg>')
    with pytest.raises(ValueError):
        icons(course)


def test_safe_svg_preserves_local_arrow_markers_and_blocks_external_references():
    from pipeline.figure_tools import safe_svg
    text = '<svg xmlns="http://www.w3.org/2000/svg"><defs><marker id="arrow"><path d="M0 0L5 5"/></marker></defs><path d="M0 0L20 20" marker-end="url(#arrow)"/></svg>'
    assert safe_svg(text).tag.endswith('svg')
    with pytest.raises(ValueError):
        safe_svg(text.replace('url(#arrow)', 'url(https://example.test/evil)'))
