"""Run the copied tools in an independent synthetic course, including an upgrade."""
import json
import subprocess
import sys
import socket
import time
import urllib.request
import zipfile

import yaml

from pipeline.config import Course
from pipeline.generator import create, upgrade
from pipeline.io import read, write
from pipeline.jobs import make_jobs


def cli(root, *args):
    result = subprocess.run([sys.executable, '-m', 'pipeline', *args], cwd=root,
                            capture_output=True, text=True, encoding='utf-8', timeout=90)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    return result.stdout


def test_new_course_cli_through_all_products_and_upgrade(tmp_path):
    root = create(tmp_path / 'independent-course', 'Technische Physik', 'physik')
    config = yaml.safe_load((root / 'course.yaml').read_text(encoding='utf-8'))
    config['course']['export_prefix'] = 'TP'
    config['sources'] = [dict(id='skript', path='input/skript.txt', kind='script', trust='primary'),
                         dict(id='klausur', path='input/klausur.txt', kind='exam', trust='student-transcript', exam_date='2026-04-01')]
    config['processing']['pages_per_section'] = 1
    write(root / 'course.yaml', yaml.safe_dump(config, allow_unicode=True))
    write(root / 'input/skript.txt', 'Energie bleibt erhalten.\fArbeit ist Energieübertragung.')
    write(root / 'input/klausur.txt', 'Was bleibt erhalten?')
    cli(root, 'ingest')
    structure = read(root / 'curation/structure.json')
    for section in structure['sections']:
        section['needs_review'] = False
    structure['chapters'] = [dict(id='energie', title='Energie', sections=[structure['sections'][0]['id']]),
                             dict(id='arbeit', title='Arbeit', sections=[structure['sections'][1]['id']])]
    write(root / 'curation/structure.json', structure)
    cli(root, 'inspect')
    cli(root, 'review', '--reviewer', 'synthetischer Integrationstest')
    cli(root, 'plan')
    course = Course(root)
    for job in make_jobs(course):
        refs = [{'source': s['source'], 'page': s['page']} for s in job['sources']]
        result = dict(job_id=job['job_id'], input_hash=job['input_hash'], guide=[], cards=[],
                      questions=[], audio=[], figures=[], uncertainties=[])
        if job['kind'] == 'script':
            result['guide'] = [dict(text=job['sources'][0]['text'], refs=refs)]
            result['cards'] = [dict(id='karte', front='Was sagt die Quelle?', back=job['sources'][0]['text'], refs=refs)]
        else:
            result['questions'] = [dict(id='echt', origin='real', prompt='Was bleibt erhalten?', solution='Energie.', points=None, refs=refs)]
        write(course.path('responses') / (job['job_id'] + '.json'), result)
    cli(root, 'accept', '--model', 'synthetic')
    cli(root, 'build')
    for command in ('offline', 'export', 'export-notebooklm', 'render-pdf', 'anki', 'exam-analysis', 'detect-figures'):
        cli(root, command)
    # Build-boundary fixture only. The separate browser check uses the real PDF.js dependency.
    vendor = root / 'interactive/node_modules/pdfjs-dist'
    for name in ('build/pdf.mjs', 'build/pdf.worker.mjs', 'web/pdf_viewer.mjs', 'web/pdf_viewer.css', 'LICENSE'):
        write(vendor / name, '/* synthetic PDF.js dependency */')
    cli(root, 'audio-reader')
    assert 'pending' in cli(root, 'sync-audio')
    cli(root, 'package-reader')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    process = subprocess.Popen([sys.executable, '-m', 'pipeline', 'serve', '--port', str(port)],
                               cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for attempt in range(50):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/reader.html', timeout=2) as response:
                    assert response.status == 200
                break
            except OSError:
                if process.poll() is not None:
                    raise AssertionError('serve CLI exited before serving the reader')
                time.sleep(0.1)
        else:
            raise AssertionError('serve CLI did not start')
    finally:
        process.terminate()
        process.wait(timeout=5)
    cli(root, 'release')
    for number in (1, 2):
        assert len([p for p in (root / 'build/pdf').glob(f'TP-{number}-*.pdf') if not p.stem.endswith('-Zusammenfassung')]) == 1
    assert len(list((root / 'build/standalone').glob('*.html'))) == 2
    package = root / 'build/release/TP-Wissensbasis-komplett.zip'
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        assert not any('originals/' in name or 'input/' in name or 'progress/' in name for name in archive.namelist())
    before = (root / 'course.yaml').read_bytes()
    upgrade(root)
    assert (root / 'course.yaml').read_bytes() == before
    cli(root, 'offline')
    cli(root, 'interactive')
    cli(root, 'package-reader')
