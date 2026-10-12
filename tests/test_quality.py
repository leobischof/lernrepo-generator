import copy
from pathlib import Path

import pytest

from test_pipeline import course, git_available, answer_all, response
from pipeline.agent import prepare, accept_packet
from pipeline.build import build, offline
from pipeline.io import read, write, digest
from pipeline.jobs import make_jobs, review, check_structure
from pipeline.quality import audit


def worker_files(course, packet_info):
    packet = Path(packet_info['packet'])
    result = read(packet / 'previous-result.json')
    write(packet / 'result.json', result)
    checked = read(packet / 'review-template.json')
    checked.update(verified=True, verified_by='forged worker approval')
    for page in checked['pages']:
        page.update(status='covered', reason='Quellenaussage im Leitfaden und in der Lernkarte vorhanden.',
                    evidence=['Energie bleibt erhalten.'], inventory=[dict(
                        item='Energieerhaltung', destination='guide[0]', evidence='Energie bleibt erhalten.')])
    for check in checked['checks'].values():
        check.update(passed=True, note='Im synthetischen Test vollständig kontrolliert.')
    write(packet / 'page-review.json', checked)
    return packet


def test_worker_must_document_inventory_and_self_correction_checks(course):
    answer_all(course)
    packet = worker_files(course, prepare(course, make_jobs(course)[0]['job_id'], [1]))
    assert 'jede Tabellenzelle' in (packet / 'WORKFLOW.md').read_text(encoding='utf-8')
    checked = read(packet / 'page-review.json')
    checked['pages'][0]['inventory'] = []
    write(packet / 'page-review.json', checked)
    with pytest.raises(ValueError, match='Quelleninventar'):
        accept_packet(course, packet)
    checked['pages'][0]['inventory'] = [dict(item='Energie', destination='guide[0]', evidence='Energie bleibt erhalten.')]
    checked['checks']['unsupported_claims']['passed'] = False
    write(packet / 'page-review.json', checked)
    with pytest.raises(ValueError, match='unsupported_claims'):
        accept_packet(course, packet)


def test_valid_json_does_not_claim_complete_learning(course):
    answer_all(course)
    build(course)
    result = audit(course)
    assert result['valid_results'] == result['planned_jobs'] == 2
    assert result['missing_guide_pages'] == [{'source': 'skript', 'page': 2}]
    assert result['reviewed_pages'] == 0 and not result['ready']
    assert any('Lernqualität offen' in w for w in offline(course)['warnings'])


def test_uncertainties_only_are_not_content_coverage(course):
    from pipeline.jobs import plan, accept
    plan(course)
    for job in make_jobs(course):
        result = {k: [] for k in ('guide','cards','questions','audio','figures','uncertainties')}
        result.update(job_id=job['job_id'], input_hash=job['input_hash'], uncertainties=['Bild nicht lesbar.'])
        write(course.path('responses') / (job['job_id']+'.json'), result)
    accept(course)
    result = audit(course)
    assert result['valid_results'] == 2
    assert len(result['missing_guide_pages']) == 2
    assert {x['issue'] for x in result['issues']} == {'empty-guide', 'empty-cards'}
    assert not result['ready']


def test_transcripts_are_bound_to_source_and_exclusions(course):
    job = make_jobs(course)[0]
    entry = dict(source='skript', page=1, reviewed=True, reviewer='independent-test-review',
                 source_sha256=read(course.path('manifest'))['sources']['skript']['sha256'],
                 text='Sichtbarer Bildtext. GESTRICHEN.')
    write(course.path('transcripts'), [entry])
    with pytest.raises(ValueError, match='review erforderlich'):
        make_jobs(course)
    review(course, 'test')
    changed = make_jobs(course)[0]
    assert changed['input_hash'] != job['input_hash']
    assert 'GESTRICHEN.' not in changed['visual_transcripts'][0]['text']
    entry['source_sha256'] = 'outdated-source'
    write(course.path('transcripts'), [entry])
    assert any('aktuellen Quelldatei' in e for e in check_structure(course))


def test_worker_cannot_approve_own_output(course):
    answer_all(course)
    job = make_jobs(course)[0]
    info = prepare(course, job['job_id'], [1])
    assert not Path(info['prompt']).is_relative_to(Path(info['packet']))
    assert 'Punkte nur wenn angegeben' in read(Path(info['packet'])/'input.json')['system']
    packet = worker_files(course, info)
    accepted = accept_packet(course, packet)
    assert not accepted['verified']
    result = audit(course)
    assert result['reviewed_pages'] == 0 and result['worker_checked_pages'] == 1
    accept_packet(course, packet, verified_by='independent-test-review')
    assert audit(course)['reviewed_pages'] == 1
    cached = read(course.path('results') / (job['job_id']+'.json'))
    cached['cards'][0]['back'] = 'Changed after review'
    write(course.path('results') / (job['job_id']+'.json'), cached)
    assert audit(course)['reviewed_pages'] == 0


def test_focused_repair_must_preserve_unrelated_content(course):
    answer_all(course)
    job = make_jobs(course)[0]
    path = course.path('results') / (job['job_id']+'.json')
    old = read(path)
    old['guide'].append(dict(text='Arbeit ist Energieübertragung.', refs=[dict(source='skript',page=2)]))
    write(path,old)
    packet = worker_files(course,prepare(course,job['job_id'],[1]))
    result = read(packet/'result.json'); result['guide'].pop()
    write(packet/'result.json', result)
    with pytest.raises(ValueError, match='Nicht betroffene Inhalte'):
        accept_packet(course,packet)


def test_packet_cannot_overwrite_newer_result(course):
    answer_all(course)
    job=make_jobs(course)[0]
    packet=worker_files(course,prepare(course,job['job_id'],[1]))
    path=course.path('results')/(job['job_id']+'.json')
    cached=read(path);cached['uncertainties'].append('Newer independent correction')
    write(path,cached)
    with pytest.raises(ValueError,match='seit Paketvorbereitung'):
        accept_packet(course,packet)


def test_job_planning_reads_each_source_once(course,monkeypatch):
    import pipeline.jobs as jobs
    original=jobs.page_map; calls=[]
    def counted(c,sid):
        calls.append(sid)
        return original(c,sid)
    monkeypatch.setattr(jobs,'page_map',counted)
    make_jobs(course)
    assert sorted(calls)==['klausur','skript']


def test_packet_renders_and_checks_actual_pdf(course):
    import pymupdf
    from pipeline.ingest import run as ingest
    pdf=course.root/'input/render.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40,40),'Energie bleibt erhalten.')
        doc.new_page().insert_text((40,40),'Arbeit ist Energieuebertragung.')
        doc.save(pdf)
    course.data['sources'][0]['path']='input/render.pdf'
    ingest(course)
    structure=read(course.path('structure')); structure['exclusions']=[]
    write(course.path('structure'),structure)
    review(course,'test source check')
    job=make_jobs(course)[0]
    info=prepare(course,job['job_id'],[1])
    assert (Path(info['packet'])/'skript-page-1.png').read_bytes().startswith(b'\x89PNG')
    (course.path('originals')/'skript.pdf').write_bytes(b'tampered PDF')
    with pytest.raises(ValueError,match='Quellenmanifest'):
        prepare(course,job['job_id'],[1])


def test_exam_only_source_cannot_substantiate_answer(course):
    from pipeline.jobs import validate_result
    job=next(j for j in make_jobs(course) if j['kind']=='exam')
    result=response(job)
    result['questions'][0]['solution']='An invented answer from general model knowledge'
    with pytest.raises(ValueError,match='ohne Musterlösung'):
        validate_result(job,result)


def test_export_formats_source_tables_and_human_citations(course):
    from pipeline.export import latex_document, run as export
    table='# Tabelle\n| Größe | Wert |\n|---|---|\n| Spannung | 20 % & mehr |'
    tex=latex_document('Test',table)
    assert r'\begin{longtable}' in tex and r'\endhead' in tex
    assert r'20 \% \& mehr' in tex
    assert '| Spannung |' not in tex
    answer_all(course);build(course);export(course)
    tsv=(course.path('exports')/'anki-karten.tsv').read_text(encoding='utf-8')
    assert 'skript, PDF S. 1' in tsv and '&#x27;source&#x27;' not in tsv
