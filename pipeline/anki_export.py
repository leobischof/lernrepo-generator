"""Source-labelled basic, cloze, exam, sketch and imported student card packages."""
from collections import Counter
import html
import re

from .artifacts import index
from .build import assert_build_current
from .chapters import discover
from .chapter_exports import question_sections
from .io import file_hash, read
from .jobs import approved


def stable_id(text):
    import hashlib
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], 'big') & 0x7fffffff


def cards(course):
    output = []
    for card in read(course.path('learning') / 'cards.json', []):
        output.append({**card, 'kind': card.get('kind', 'basic'), 'label': 'KI-Erklärung, ungeprüft'})
    for origin in ('real', 'generated'):
        for question in read(course.path('exams') / f'questions-{origin}.json', []):
            output.append(dict(id='question-' + question['id'], front=question['prompt'],
                               back=question['solution'] or 'Lösung fehlt.', refs=question['refs'],
                               section=question['section'], sections=list(question_sections(course, question)), kind='exam',
                               label=('Echte Aufgabe; ' if origin == 'real' else 'KI-Übungsfrage; ') +
                               'Lösung: KI-Erklärung, ungeprüft'))
    sections = read(course.path('structure'))['sections']
    for figure in read(course.path('structure')).get('figures', []):
        path = course.path('figures') / f"{figure['id']}.svg"
        if not path.is_file() or figure.get('kind') == 'table' or figure['id'].startswith('tab-'):
            continue
        members = [s['id'] for s in sections if s['source'] == figure['source'] and figure['page'] in s['pages']]
        requirements = figure.get('must_know', figure.get('drawing', {}).get('must_know', []))
        output.append(dict(id='sketch-' + figure['id'], front='Zeichne und beschrifte: ' + figure.get('title', figure['id']),
                           back='\n'.join(requirements) or 'Vergleiche mit der kuratierten Rekonstruktion.',
                           refs=[{'source': figure['source'], 'page': figure['page']}],
                           section=members[0] if members else 'unzugeordnet', kind='sketch', media=path,
                           label='Eigene SVG-Rekonstruktion; fachliche Sichtprüfung erforderlich'))
    # Existing imported student notes remain explicitly unverified and carry no borrowed media.
    for sid, source in read(course.path('manifest'))['sources'].items():
        if source['spec']['kind'] != 'flashcards':
            continue
        path = course.path('extracted') / f'{sid}-pages.json'
        if not path.is_file():
            continue
        for page in read(path):
            fields = page.get('fields') or page['text'].split('\n', 1)
            if len(fields) < 2:
                continue
            output.append(dict(id=f"student-{sid}-{page.get('note_id', page['pdf_page'])}",
                               front=re.sub('<[^>]+>', '', fields[0]), back=re.sub('<[^>]+>', '', '\n'.join(fields[1:])),
                               refs=[{'source': sid, 'page': page['pdf_page']}], section='unzugeordnet', kind='student',
                               label='Studierendenkarte, unverifiziert; gegen Primärquelle prüfen'))
    return output


def run(course):
    import genanki
    approved(course)
    assert_build_current(course)
    chapters = discover(course)
    all_cards, media = cards(course), {}
    basic = genanki.Model(stable_id('lernrepo-basic-v1'), 'Lernrepo Frage/Antwort v1',
        fields=[{'name': 'Frage'}, {'name': 'Antwort'}],
        templates=[{'name': 'Offene Frage', 'qfmt': '{{Frage}}', 'afmt': '{{FrontSide}}<hr>{{Antwort}}'}])
    cloze = genanki.Model(stable_id('lernrepo-cloze-v1'), 'Lernrepo Cloze v1', model_type=genanki.Model.CLOZE,
        fields=[{'name': 'Text'}, {'name': 'Quelle'}],
        templates=[{'name': 'Lückentext', 'qfmt': '{{cloze:Text}}', 'afmt': '{{cloze:Text}}<hr>{{Quelle}}'}])
    decks = {}
    notes_by_chapter = {c['id']: [] for c in chapters}
    notes_by_chapter['unzugeordnet'] = []
    chapter_by_section = {sid: c for c in chapters for sid in c['sections']}
    for card in all_cards:
        chapter = chapter_by_section.get(card['section'])
        if not chapter:
            chapter = next((chapter_by_section[sid] for sid in card.get('sections', []) if sid in chapter_by_section), None)
        chapter_id = chapter['id'] if chapter else 'unzugeordnet'
        name = chapter['title'] if chapter else 'Noch nicht zugeordnet'
        key = chapter_id + ':' + card['kind']
        deck = decks.setdefault(key, genanki.Deck(stable_id(course.data['course']['id'] + ':' + key),
                                    course.data['course']['title'] + '::' + name + '::' + card['kind']))
        labels = card['label'] + '\n' + '; '.join(f"{r['source']}, PDF/Einheit {r['page']}" for r in card['refs'])
        if card['kind'] == 'cloze':
            text = card.get('cloze', '')
            if not re.search(r'\{\{c[1-9]\d*::.+?\}\}', text):
                raise ValueError('Lückentext braucht mindestens {{c1::Antwort}}')
            fields, model = [html.escape(text), html.escape(labels)], cloze
        else:
            back = html.escape(card['back']).replace('\n', '<br>') + '<hr>' + html.escape(labels)
            if 'media' in card:
                path = card['media']
                from .figure_tools import safe_svg
                safe_svg(path.read_text(encoding='utf-8'))
                filename = f'figure-{file_hash(path)[:16]}.svg'
                target = course.root / 'build/anki/media' / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                media[filename] = str(target)
                back += f'<br><img src="{filename}">'
            fields, model = [html.escape(card['front']), back], basic
        note = genanki.Note(model=model, fields=fields, tags=[card['kind'], 'quellengebunden'],
                           guid=genanki.guid_for(course.data['course']['id'], card['id']))
        deck.add_note(note)
        notes_by_chapter[chapter_id].append(key)
    output = course.root / 'build/anki'
    output.mkdir(parents=True, exist_ok=True)
    produced = []

    def package(path, selected):
        bundle = genanki.Package(selected)
        bundle.media_files = list(media.values())
        bundle.write_to_file(str(path))
        produced.append(path)

    package(output / 'anki-gesamt.apkg', list(decks.values()))
    for chapter in chapters:
        keys = set(notes_by_chapter[chapter['id']])
        package(output / f"{chapter['stem']}-Anki.apkg", [deck for key, deck in decks.items() if key in keys])
    index(course, output, produced, [course.path('figures') / f"{f['id']}.svg"
                                   for f in read(course.path('structure')).get('figures', [])])
    return {'cards': len(all_cards), 'by_kind': dict(Counter(c['kind'] for c in all_cards)),
            'files': [p.relative_to(course.root).as_posix() for p in produced]}
