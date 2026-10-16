"""Shared fail-closed timeline identity and geometry checks."""
import math


def validate(value, chapter, pages, duration=math.inf):
    if (value.get('version') != 1 or value.get('chapter') != chapter['number']
            or not isinstance(value.get('annotations'), list)):
        raise ValueError('Ungültiges Timeline-Format oder anderes Kapitel')
    if any(value.get(key) != chapter.get(key) for key in ('pdf_sha256', 'audio_sha256')):
        raise ValueError('Timeline: PDF/Audio wurde verändert; Zuordnung erneut prüfen')
    ids = set()
    for item in value['annotations']:
        if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in ids:
            raise ValueError('Timeline-IDs müssen eindeutig sein')
        ids.add(item['id'])
        times = [item.get('start'), item.get('end')]
        if not all(type(v) in (int, float) and math.isfinite(v) for v in times) or not 0 <= times[0] < times[1] <= duration:
            raise ValueError('Ungültige Timeline-Zeit')
        if type(item.get('page')) is not int or not 1 <= item['page'] <= pages:
            raise ValueError('Timeline-Seite außerhalb des PDFs')
        if item.get('type') not in {'rect', 'highlight', 'arrow'} or item.get('status') not in {'unreviewed', 'reviewed'}:
            raise ValueError('Ungültiger Timeline-Typ oder Prüfstatus')
        coords = item.get('points' if item['type'] == 'arrow' else 'rect')
        if not isinstance(coords, list) or len(coords) != 4 or not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in coords):
            raise ValueError('Ungültige Timeline-Koordinaten')
        if item['type'] != 'arrow' and (coords[2] <= 0 or coords[3] <= 0 or coords[0]+coords[2] > 1.00001 or coords[1]+coords[3] > 1.00001):
            raise ValueError('Timeline-Rechteck außerhalb der Seite')
        if item.get('animation', 'none') not in {'none', 'pulse'}:
            raise ValueError('Unbekannte Timeline-Animation')
    return value
