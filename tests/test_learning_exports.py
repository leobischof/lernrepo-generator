import sqlite3
import zipfile

import pytest

from test_pipeline import course, git_available, answer_all, response
from pipeline.build import build
from pipeline.io import read, write
from pipeline.jobs import make_jobs, validate_result


def collection(path, tmp_path):
    with zipfile.ZipFile(path) as archive:
        target = tmp_path / 'collection.sqlite'
        target.write_bytes(archive.read('collection.anki2'))
    return sqlite3.connect(target)


def test_optional_cloze_contract_and_export_stable_guids(course, tmp_path):
    from pipeline.anki_export import run
    job = make_jobs(course)[0]
    result = response(job)
    result['cards'][0].update(kind='cloze', cloze='{{c1::Energie}} bleibt erhalten.')
    validate_result(job, result)
    write(course.path('responses') / f"{job['job_id']}.json", result)
    from pipeline.jobs import accept
    accept(course, 'synthetic')
    build(course)
    first = run(course)
    assert first['cards'] == 2  # supplied cloze plus explicitly labelled KI exercise
    path = course.root / 'build/anki/anki-gesamt.apkg'
    with collection(path, tmp_path) as db:
        notes = db.execute('select guid, flds from notes order by guid').fetchall()
        models = db.execute('select models from col').fetchone()[0]
    assert 'cloze' in models.lower()
    assert any('{{c1::Energie}}' in fields for _, fields in notes)
    run(course)
    with collection(path, tmp_path) as db:
        assert db.execute('select guid, flds from notes order by guid').fetchall() == notes
    assert len(list((course.root / 'build/anki').glob('*-1-*.apkg'))) == 1


def test_sketch_cards_include_only_own_svg_and_source_labels(course, tmp_path):
    from pipeline.anki_export import run
    structure = read(course.path('structure'))
    structure['figures'] = [dict(id='abb-01', source='skript', page=1, title='Energiekurve', bbox=[0,0,20,20],
                                 must_know=['Achsen beschriften'])]
    write(course.path('structure'), structure)
    write(course.path('figures') / 'abb-01.svg', '<svg xmlns="http://www.w3.org/2000/svg"><text>Energie</text></svg>')
    from pipeline.jobs import review
    review(course, 'test')
    answer_all(course)
    build(course)
    assert run(course)['by_kind']['sketch'] == 1
    path = course.root / 'build/anki/anki-gesamt.apkg'
    with zipfile.ZipFile(path) as archive:
        assert 'Achsen beschriften' not in archive.namelist()
        media = archive.read('media').decode()
        assert '.svg' in media and '.png' not in media
    with collection(path, tmp_path) as db:
        assert any('Achsen beschriften' in fields for fields, in db.execute('select flds from notes'))


def test_exam_analysis_counts_only_real_questions_and_known_dates(course):
    from pipeline.exam_analysis import run
    answer_all(course)
    build(course)
    value = run(course)
    assert value['real_questions'] == 1
    assert value['known_dates'] == []
    assert value['questions_without_date'] == 1
    # A configured date is source metadata; a generated question never adds a date.
    course.data['sources'][1]['exam_date'] = '2026-05-20'
    write(course.path('config'), __import__('yaml').safe_dump(course.data))
    from pipeline.ingest import run as ingest
    from pipeline.jobs import review
    ingest(course)
    review(course, 'test')
    answer_all(course)
    build(course)
    value = run(course)
    assert value['known_dates'] == ['2026-05-20']
    assert value['questions_without_date'] == 0


def test_cloze_cannot_silently_drop_a_card_without_deletion_marker(course):
    from pipeline.anki_export import run
    answer_all(course)
    build(course)
    cards = read(course.path('learning') / 'cards.json')
    cards[0].update(kind='cloze', cloze='keine Lücke')
    # Validate the model boundary rather than tampering with generated files.
    job = make_jobs(course)[0]
    result = response(job)
    result['cards'][0].update(kind='cloze', cloze='keine Lücke')
    with pytest.raises(ValueError, match='Lückentext'):
        validate_result(job, result)


def test_tables_do_not_become_sketch_cards(course):
    from pipeline.anki_export import run
    structure = read(course.path('structure'))
    structure['figures'] = [dict(id='tab-01', source='skript', page=1, title='Einheiten', bbox=[0,0,20,20])]
    write(course.path('structure'), structure)
    write(course.path('figures') / 'tab-01.svg', '<svg xmlns="http://www.w3.org/2000/svg"><text>Einheiten</text></svg>')
    from pipeline.jobs import review
    review(course, 'test')
    answer_all(course)
    build(course)
    assert run(course)['by_kind'].get('sketch', 0) == 0
