"""Explicit source-bound text corrections; raw extraction is never overwritten."""
from copy import deepcopy

from .io import read


def corrections(course):
    return read(course.root / 'curation/text-corrections.json', {'corrections': []})['corrections']


def apply_corrections(course, sid, pages):
    result = deepcopy(pages)
    by_page = {p['pdf_page']: p for p in result}
    manifest = read(course.path('manifest'), {'sources': {}})['sources']
    for index, item in enumerate(corrections(course), 1):
        source = manifest.get(item.get('source'))
        if (not source or item.get('source_sha256') != source['sha256'] or item.get('reviewed') is not True
                or not item.get('reason') or type(item.get('page')) is not int
                or not 1 <= item['page'] <= source['pages'] or not isinstance(item.get('before'), str)
                or not item['before'] or not isinstance(item.get('after'), str)):
            raise ValueError(f'Ungeprüfte oder veraltete Textkorrektur: {index}')
        if item['source'] != sid:
            continue
        page = by_page[item['page']]
        expected = item.get('count', 1)
        if type(expected) is not int or expected < 1 or page['text'].count(item['before']) != expected:
            raise ValueError(f'Textkorrektur {index}: Originalstelle nicht exakt gefunden')
        page['text'] = page['text'].replace(item['before'], item['after'])
        page.setdefault('corrections', []).append(index)
    return result
