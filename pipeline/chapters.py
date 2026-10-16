"""Course-specific groups and safe, consistent artifact names."""
import re
import unicodedata

from .io import identifier, read


def slug(text):
    value = unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9]+', '-', value).strip('-')[:100] or 'Kapitel'


def prefix(course):
    value = course.data['course'].get('export_prefix', course.data['course']['id'])
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value):
        raise ValueError('Exportpräfix muss 1–64 Buchstaben, Ziffern, - oder _ enthalten')
    return value


def discover(course):
    structure = read(course.path('structure'))
    sections = {s['id']: s for s in structure['sections']}
    groups = structure.get('chapters')
    if groups is None:
        groups = [dict(id=s['id'], title=s['title'], sections=[s['id']]) for s in sections.values()]
    chapters, assigned, ids = [], set(), set()
    for number, group in enumerate(groups, 1):
        cid = identifier(group['id'])
        members = group['sections']
        if cid in ids or not members or not isinstance(group['title'], str) or not group['title'].strip():
            raise ValueError('Kapitel benötigen eindeutige IDs, Titel und Abschnitte')
        ids.add(cid)
        for sid in members:
            if sid not in sections or sid in assigned:
                raise ValueError(f'Unbekannter oder mehrfach zugeordneter Abschnitt: {sid}')
            assigned.add(sid)
        chapters.append(dict(id=cid, number=number, title=group['title'], sections=list(members),
                             stem=f'{prefix(course)}-{number}-{slug(group["title"])}'))
    if assigned != set(sections):
        raise ValueError('Jeder Abschnitt muss genau einem Kapitel zugeordnet sein')
    return chapters
