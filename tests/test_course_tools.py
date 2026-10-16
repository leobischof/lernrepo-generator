import subprocess
from pathlib import Path

import pytest
import yaml

from pipeline.config import Course
from pipeline.generator import create, upgrade
from pipeline.io import read, write


@pytest.fixture
def course(tmp_path):
    root = create(tmp_path / 'course', 'Physik', 'physik')
    config = yaml.safe_load((root / 'course.yaml').read_text(encoding='utf-8'))
    config['course']['export_prefix'] = 'physik'
    write(root / 'course.yaml', yaml.safe_dump(config, allow_unicode=True))
    write(root / 'curation/structure.json', {
        'sections': [dict(id='sec-1', title='Energie', source='skript', pages=[1], needs_review=False),
                     dict(id='sec-2', title='Arbeit', source='skript', pages=[2], needs_review=False)],
        'chapters': [dict(id='grundlagen', title='Grundlagen', sections=['sec-1']),
                     dict(id='anwendung', title='Anwendung', sections=['sec-2'])],
        'exclusions': [], 'figures': []})
    return Course(root)


def test_chapters_use_course_prefix_and_explicit_section_groups(course):
    from pipeline.chapters import discover
    chapters = discover(course)
    assert chapters[0]['stem'] == 'physik-1-Grundlagen'
    assert chapters[1]['number'] == 2
    assert chapters[1]['sections'] == ['sec-2']


@pytest.mark.parametrize('groups', [['missing'], ['sec-1', 'sec-1']])
def test_chapters_reject_unknown_or_duplicate_sections(course, groups):
    from pipeline.chapters import discover
    structure = read(course.path('structure'))
    structure['chapters'][0]['sections'] = groups
    write(course.path('structure'), structure)
    with pytest.raises(ValueError):
        discover(course)


def test_legacy_sections_are_chapters_without_configuration(course):
    from pipeline.chapters import discover
    structure = read(course.path('structure'))
    del structure['chapters']
    write(course.path('structure'), structure)
    assert [c['sections'] for c in discover(course)] == [['sec-1'], ['sec-2']]


def test_upgrade_refuses_committed_local_tool_changes(course):
    target = course.root / 'pipeline/config.py'
    target.write_text(target.read_text(encoding='utf-8') + '\n# local customization\n', encoding='utf-8')
    subprocess.run(['git', '-C', str(course.root), 'add', 'pipeline/config.py'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(course.root), '-c', 'user.name=Test', '-c', 'user.email=test@localhost',
                    'commit', '-m', 'chore: customize tools'], check=True, capture_output=True)
    with pytest.raises(ValueError, match='Werkzeug'):
        upgrade(course.root)
    assert '# local customization' in target.read_text(encoding='utf-8')


def test_upgrade_preserves_course_configuration(course):
    before = (course.root / 'course.yaml').read_bytes()
    upgrade(course.root)
    assert (course.root / 'course.yaml').read_bytes() == before
    assert read(course.root / '.lernrepo-tools.json')['files']['pipeline/config.py']
