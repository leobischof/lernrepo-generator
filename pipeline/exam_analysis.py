"""Descriptive counts of real questions; no guessed dates, relevance or probabilities."""
from collections import Counter
from datetime import date

from .build import assert_build_current
from .chapter_exports import question_sections
from .io import read, write
from .jobs import approved


def run(course):
    approved(course)
    assert_build_current(course)
    return analyze(course)


def analyze(course):
    manifest = read(course.path('manifest'))['sources']
    questions = read(course.path('exams') / 'questions-real.json', [])
    dates, unknown, counts, terms = set(), 0, Counter(), {}
    for question in questions:
        known = set()
        for ref in question['refs']:
            spec = manifest[ref['source']]['spec']
            value = spec.get('exam_date')
            if value:
                if spec['kind'] != 'exam':
                    raise ValueError('exam_date nur für eine einzelne Klausur, nicht für Fragensammlungen')
                date.fromisoformat(value)
                known.add(value)
        dates |= known
        if not known:
            unknown += 1
        for sid in question_sections(course, question):
            counts[sid] += 1
            terms.setdefault(sid, set()).update(known)
    value = {'real_questions': len(questions), 'known_dates': sorted(dates), 'questions_without_date': unknown,
             'by_section': {sid: {'questions': n, 'known_dates': sorted(terms.get(sid, set()))} for sid, n in sorted(counts.items())}}
    write(course.path('exams') / 'frequency-analysis.json', value)
    lines = ['# Häufigkeitsanalyse echter Aufgaben\n',
             f'Echte Fragen: {len(questions)}. Bekannte Termine: {len(dates)}. Fragen ohne bekanntes Datum: {unknown}.\n',
             'Keine Prüfungswahrscheinlichkeiten; KI-Übungsfragen sind ausgeschlossen. Kapitelzuordnung nur aus Kuratierung.\n',
             '| Abschnitt | Echte Fragen | Bekannte Termine |', '|---|---:|---|']
    lines += [f"| {sid} | {item['questions']} | {', '.join(item['known_dates']) or 'unbekannt'} |" for sid, item in value['by_section'].items()]
    write(course.path('exams') / 'frequency-analysis.md', '\n'.join(lines) + '\n')
    return value
